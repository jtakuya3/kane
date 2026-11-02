"""追証投げ1分スキャルのバックテスト（手元の7か月分の分足集計データで）。

    py -3.11 -m kane.oigo_bt "C:/Users/takuy/Downloads/_backtest_data/intraday_agg*.parquet"

仮説：悪材料なしの急落（T）のあと、追証の期限日（T+2）か強制日（T+3）の寄りに投げが出て、
それが吸収された直後の1分で反発する。比較用に T+1 も記録する。

このデータでできること・できないこと
  - 分足集計（code, d, min1, pv, vv）なので四本値が無い。1分ごとの値段は「その1分のVWAP（pv÷vv）」で代用する。
    寄り値＝寄りの1分のVWAP（板寄せの出来高が大きいので寄り値に近い）、日足の高値・安値＝分足VWAPの最大・最小。
  - 信用残が無いので D（追証該当株数の推定）は計算しない。プライム・時価総額の条件も無い（売買代金で代用）。
  - 悪材料フィルター（開示タイトル）は無い。急落イベントの一覧を events_*.csv に出すので、開示を別に確かめる。
  - 1分の中で損切りと利確のどちらが先かは分からない。損切りに触れていれば損切りとみなす（保守的）。

出力（data_dir に保存）
  oigo_events.csv  急落イベント（T）一覧：悪材料の確認用
  oigo_trades.csv  k=1/2/3 ごとの1行1トレード
  画面：本命群・対照群・スイープの成績（コスト後の平均・中央値・勝率・t値）
"""
from __future__ import annotations

import argparse
import glob
import math
from pathlib import Path

OPEN_MIN = 9 * 60  # 9:00
EARLY_END = 9 * 60 + 40  # 寄りの判定は 9:40 まで（それ以降に寄った日は除外）
COST = 0.1  # 往復コスト %


def load_daily(paths: list[str]):
    """分足集計 → 1銘柄1日1行の表（寄り・寄り後の値段、日中の高安、出来高・売買代金）。"""
    import pandas as pd

    rows = []
    for p in paths:
        df = pd.read_parquet(p, columns=None)
        cols = set(df.columns)
        if not ({"code", "d", "pv", "vv"} <= cols and "min1" in cols):
            print(f"  {Path(p).name}: 1分の集計形式ではないので飛ばします（列: {sorted(cols)[:8]}…）")
            continue
        df = df[["code", "d", "min1", "pv", "vv"]]
        df = df[df["vv"] > 0].copy()
        code = df["code"].astype(str).str.strip()
        df["code"] = code.where(~((code.str.len() == 5) & code.str.endswith("0")), code.str[:4])
        df["px"] = df["pv"] / df["vv"]
        df = df.sort_values(["code", "d", "min1"])
        g = df.groupby(["code", "d"], sort=False)
        day = g.agg(vol=("vv", "sum"), val=("pv", "sum"), hi=("px", "max"), lo=("px", "min"),
                    close=("px", "last"), first_min=("min1", "first")).reset_index()
        # 寄りの1分と、その後の1・2・5分（寄りの分からの経過で数える）
        df = df.merge(day[["code", "d", "first_min"]], on=["code", "d"])
        df["k"] = df["min1"] - df["first_min"]
        early = df[df["k"] <= 5]
        piv_px = early.pivot_table(index=["code", "d"], columns="k", values="px", aggfunc="last")
        piv_v = early.pivot_table(index=["code", "d"], columns="k", values="vv", aggfunc="sum")
        piv_px.columns = [f"px{int(c)}" for c in piv_px.columns]
        piv_v.columns = [f"v{int(c)}" for c in piv_v.columns]
        day = day.merge(piv_px.reset_index(), on=["code", "d"], how="left")
        day = day.merge(piv_v.reset_index(), on=["code", "d"], how="left")
        rows.append(day)
        print(f"  読み込み {Path(p).name}: {len(day):,} 銘柄日")
    if not rows:
        raise SystemExit("1分の集計データ（code, d, min1, pv, vv）が見つかりません")
    daily = pd.concat(rows, ignore_index=True)
    daily = daily.groupby(["code", "d"], as_index=False).first()  # ファイルの重なりを除く
    for k in range(6):  # 取引の無い分は直前の値で埋める
        c = f"px{k}"
        if c not in daily:
            daily[c] = float("nan")
        if k:
            daily[c] = daily[c].fillna(daily[f"px{k - 1}"])
        vc = f"v{k}"
        if vc not in daily:
            daily[vc] = 0.0
    return daily.sort_values(["code", "d"]).reset_index(drop=True)


def add_features(daily):
    """前日比・20日平均（T-1まで）・前日の高安などを足す。"""
    g = daily.groupby("code", sort=False)
    daily["prev_close"] = g["close"].shift(1)
    daily["prev_lo"] = g["lo"].shift(1)
    daily["prev_hi"] = g["hi"].shift(1)
    daily["prev_vol"] = g["vol"].shift(1)
    daily["ret"] = (daily["close"] / daily["prev_close"] - 1) * 100
    daily["avg_vol20"] = g["vol"].transform(lambda s: s.shift(1).rolling(20, min_periods=15).mean())
    daily["avg_val20"] = g["val"].transform(lambda s: s.shift(1).rolling(20, min_periods=15).mean())
    daily["gain5"] = g["close"].transform(lambda s: (s.shift(1) / s.shift(6) - 1) * 100)
    daily["idx"] = g.cumcount()
    return daily


def trade_metrics(r) -> dict:
    """寄り（px0）で買い、1・2・5分後と引けで売ったときの騰落（コスト前、%）。損切り −1% は保守的に判定。"""
    e = r["px0"]
    out = {}
    for k in (1, 2, 5):
        x = r.get(f"px{k}")
        path = [r.get(f"px{j}") for j in range(1, k + 1)]
        hit = any(p is not None and not math.isnan(p) and p <= e * 0.99 for p in path)
        out[f"ret{k}"] = -1.0 if hit else ((x / e - 1) * 100 if x and not math.isnan(x) else None)
    out["ret_close"] = (r["close"] / e - 1) * 100
    path5 = [r.get(f"px{j}") for j in range(1, 6) if r.get(f"px{j}") and not math.isnan(r.get(f"px{j}"))]
    out["mae5"] = (min(path5) / e - 1) * 100 if path5 else None
    out["mfe5"] = (max(path5) / e - 1) * 100 if path5 else None
    return out


def stats(xs: list[float]) -> str:
    xs = [x - COST for x in xs if x is not None]
    n = len(xs)
    if n == 0:
        return "n=0"
    m = sum(xs) / n
    med = sorted(xs)[n // 2]
    win = sum(1 for x in xs if x > 0) / n * 100
    sd = (sum((x - m) ** 2 for x in xs) / (n - 1)) ** 0.5 if n > 1 else 0
    t = m / (sd / n ** 0.5) if sd else 0
    return f"n={n:4d}  平均 {m:+.2f}%  中央値 {med:+.2f}%  勝率 {win:4.0f}%  t {t:+.2f}"


def main():
    import pandas as pd

    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--crash", type=float, default=-14.0, help="急落の前日比（終値の代わりに最後の1分のVWAP）")
    ap.add_argument("--min-value", type=float, default=3e8, help="20日平均売買代金（円）")
    ap.add_argument("--max-gain5", type=float, default=30.0, help="T前5日の上昇がこれ以上なら除外（テーマ巻き戻し）")
    ap.add_argument("--max-same-day", type=int, default=10, help="同じ日にこれ以上急落があれば地合いとして除外")
    ap.add_argument("--out", default=None, help="出力先フォルダ（既定は config の data_dir）")
    args = ap.parse_args()
    paths = sorted({p for pat in args.paths for p in glob.glob(pat)}) or args.paths
    if args.out:
        out_dir = Path(args.out)
    else:
        from .config import load_config
        out_dir = load_config("config.toml").data_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"分足を読み込み中（{len(paths)}ファイル）…")
    daily = add_features(load_daily(paths))
    days = sorted(daily["d"].unique())
    print(f"期間 {days[0]}〜{days[-1]}（{len(days)}営業日） 銘柄 {daily['code'].nunique():,}  1日あたり平均 {len(daily) / len(days):,.0f}銘柄")

    # ---- 1. 急落イベント ----
    ev = daily[(daily["ret"] <= args.crash) & (daily["avg_val20"] >= args.min_value)].copy()
    ev = ev[~(ev["gain5"] >= args.max_gain5)]
    cnt = ev.groupby("d")["code"].transform("count")
    ev = ev[cnt < args.max_same_day]
    print(f"急落イベント {len(ev)}件（前日比 {args.crash}%以下、売買代金 {args.min_value / 1e8:.0f}億円以上、"
          f"前5日 +{args.max_gain5:.0f}%未満、同日 {args.max_same_day}件未満）")
    ev[["d", "code", "ret", "prev_close", "close", "avg_val20", "gain5"]].to_csv(
        out_dir / "oigo_events.csv", index=False, encoding="utf-8-sig")

    # ---- 2. k=1/2/3 のトレード ----
    by_code = {c: g.reset_index(drop=True) for c, g in daily.groupby("code", sort=False)}
    trades = []
    for _, t in ev.iterrows():
        g = by_code[t["code"]]
        ti = int(t["idx"])
        for k in (1, 2, 3):
            if ti + k >= len(g):
                continue
            r = g.iloc[ti + k].to_dict()
            if r["first_min"] > EARLY_END or not r.get("px0") or math.isnan(r["px0"]):
                continue
            prev = g.iloc[ti + k - 1]
            row = {"code": t["code"], "T": t["d"], "k": k, "day": r["d"], "T_ret": t["ret"],
                   "open_min": f"{int(r['first_min']) // 60}:{int(r['first_min']) % 60:02d}",
                   "gap": (r["px0"] / prev["close"] - 1) * 100,
                   "below_prev_low": r["px0"] < prev["lo"],
                   "open_vol_ratio": r["v0"] / r["avg_vol20"] * 100 if r["avg_vol20"] else None,
                   "min2_vol_ratio": r.get("v1", 0) / r["avg_vol20"] * 100 if r["avg_vol20"] else None,
                   "prev_vol_x": prev["vol"] / r["avg_vol20"] if r["avg_vol20"] else None,
                   "prev_pos": (prev["close"] - prev["lo"]) / (prev["hi"] - prev["lo"]) if prev["hi"] > prev["lo"] else None,
                   "since_T": (prev["close"] / t["prev_close"] - 1) * 100}
            row.update(trade_metrics(r))
            trades.append(row)
    tr = pd.DataFrame(trades)
    tr.to_csv(out_dir / "oigo_trades.csv", index=False, encoding="utf-8-sig")
    print(f"トレード候補 {len(tr)}件 → {out_dir / 'oigo_trades.csv'}")
    if tr.empty:
        return

    # ---- 3. 地合いの対照：同じ日の全銘柄（売買代金基準を満たす）の 寄り→1分 ----
    base = daily[(daily["avg_val20"] >= args.min_value) & (daily["first_min"] <= EARLY_END)].copy()
    base["r1"] = (base["px1"] / base["px0"] - 1) * 100
    gapd = base[(base["px0"] < base["prev_lo"])]
    print("\n■ 対照：急落と関係なく「前日安値を割って寄った」全銘柄日の 寄り→1分")
    print("   " + stats(list(gapd["r1"].dropna())))

    # ---- 4. 成績 ----
    def show(label, df, col="ret1"):
        print(f"   {label:34s} {stats(list(df[col]))}")

    print("\n■ k ごと（条件なし、寄り→1分）")
    for k in (1, 2, 3):
        show(f"k={k}", tr[tr["k"] == k])
    core = tr[(tr["k"].isin([2, 3])) & tr["below_prev_low"]]
    print("\n■ 本命群：k=2/3・寄りが前日安値割れ（D と悪材料は未判定）")
    for x in (5, 10, 15):
        for pv in (2, 3, 4):
            sub = core[(core["open_vol_ratio"] >= x) & ((core["prev_vol_x"] <= pv) | (core["prev_pos"] >= 0.5))]
            show(f"寄り出来高≧{x}% 前日出来高≦{pv}倍orPOS≧0.5", sub)
    print("\n■ エグジット別（本命群・寄り出来高≧10%・前日≦3倍orPOS≧0.5）")
    sub = core[(core["open_vol_ratio"] >= 10) & ((core["prev_vol_x"] <= 3) | (core["prev_pos"] >= 0.5))]
    for col, lab in (("ret1", "1分"), ("ret2", "2分"), ("ret5", "5分"), ("ret_close", "引け")):
        show(lab, sub, col)
    print("\n■ 対照群")
    show("k=1", tr[tr["k"] == 1])
    show("k=2/3・前日安値割れなし", tr[(tr["k"].isin([2, 3])) & ~tr["below_prev_low"]])
    show("k=2/3・前日出来高>3倍かつPOS<0.5", tr[(tr["k"].isin([2, 3])) & (tr["prev_vol_x"] > 3) & (tr["prev_pos"] < 0.5)])
    print("\n※ 成績はコスト0.1%を引いた後。値段は1分ごとのVWAPで代用。悪材料と D は未判定なので、"
          "oigo_events.csv の開示を確かめて除外した版も作る")


if __name__ == "__main__":
    main()
