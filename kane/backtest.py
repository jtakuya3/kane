"""過去データで判定を答え合わせする（バックテスト）。

    # まずファイルの中身（列名）を確認
    python -m kane.backtest --inspect "C:/Users/takuy/Downloads/_backtest_data/min1_xxx.parquet"

    # 1分足（parquet / csv）で実行。急騰・急落した日（前日比±5%以上動いた日）だけを対象にする
    python -m kane.backtest "C:/Users/takuy/Downloads/_backtest_data/min1*.parquet"

    # 歩み値（csv）から1分足を作って実行
    python -m kane.backtest --kind ticks "D:/tick/2026-03/*.csv"

列名が自動で見つからないときは --col time=日時 --col code=銘柄コード のように指定する。
元データは読むだけで、書き換えない。結果は data_dir/backtest_日時/ に保存する。
"""
from __future__ import annotations

import argparse
import glob
from datetime import datetime, timedelta
from pathlib import Path

from .config import RuleConfig, SymbolInfo, load_config
from .engine import Engine
from .evaluate import AlertRow, PriceBook, evaluate, format_summary, summarize, write_csv
from .models import Snapshot

CANDIDATES = {
    "time": ["datetime", "timestamp", "time", "date_time", "dt", "ts", "日時", "約定日時", "時刻"],
    "date": ["date", "日付", "trade_date"],
    "code": ["code", "symbol", "ticker", "sym", "securitiescode", "銘柄コード", "コード", "銘柄"],
    "open": ["open", "始値", "o"],
    "high": ["high", "高値", "h"],
    "low": ["low", "安値", "l"],
    "close": ["close", "終値", "c", "price", "現在値"],
    "volume": ["volume", "出来高", "vol", "v", "qty", "size", "約定数量"],
    "price": ["price", "約定値", "約定価格", "p", "現在値"],
}


def detect(columns: list[str], kind: str, override: dict) -> dict:
    """列名を推定する。戻り値は {役割: 実際の列名}。"""
    low = {c.lower().strip(): c for c in columns}
    need = ["code", "open", "high", "low", "close", "volume"] if kind == "bars" else ["code", "price", "volume"]
    out = {}
    for role in need + ["time", "date"]:
        if role in override:
            out[role] = override[role]
            continue
        for cand in CANDIDATES[role]:
            if cand in low and low[cand] not in out.values():
                out[role] = low[cand]
                break
    if "time" not in out and "date" not in out:
        raise SystemExit(f"時刻の列が見つかりません。--col time=列名 で指定してください。列: {columns}")
    missing = [r for r in need if r not in out]
    if missing:
        raise SystemExit(f"列が見つかりません: {missing}。--col 役割=列名 で指定してください。列: {columns}")
    return out


def _read(path: str, columns=None):
    import pandas as pd

    if path.lower().endswith(".parquet"):
        return pd.read_parquet(path, columns=columns)
    for enc in ("utf-8-sig", "cp932"):
        try:
            return pd.read_csv(path, usecols=columns, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"文字コードが読めません: {path}")


def _datetime(df, m):
    import pandas as pd

    if "time" in m and "date" in m and m["time"] != m["date"]:
        s = pd.to_datetime(df[m["date"]].astype(str) + " " + df[m["time"]].astype(str), errors="coerce")
    else:
        col = df[m.get("time", m.get("date"))]
        if pd.api.types.is_numeric_dtype(col):  # UNIX時間
            unit = "ms" if col.max() > 1e11 else "s"
            s = pd.to_datetime(col, unit=unit, utc=True)
        else:
            s = pd.to_datetime(col, errors="coerce")
    if getattr(s.dt, "tz", None) is not None:
        s = s.dt.tz_convert("Asia/Tokyo").dt.tz_localize(None)
    return s


def _from_min_agg(df, step: int = 1):
    """_backtest_data の集計形式：code(5桁), d(YYYYMMDD), min1(0時からの分) または min5(0時からの5分単位),
    n(約定回数), pv(売買代金), vv(出来高)。四本値が無いので、各足のVWAP（pv÷vv）を株価として使う。"""
    import pandas as pd

    code = df["code"].astype(str).str.strip()
    # 5桁コードは末尾0（普通株）のときだけ4桁にする。末尾が0以外（優先株など別銘柄）は5桁のまま残す
    code = code.where(~((code.str.len() == 5) & code.str.endswith("0")), code.str[:4])
    minutes = df["min1"] if step == 1 else df["min5"] * 5
    dt = pd.to_datetime(df["d"].astype(str), format="%Y%m%d") + pd.to_timedelta(minutes, unit="m")
    px = df["pv"] / df["vv"]
    f = pd.DataFrame({"code": code, "dt": dt, "open": px, "high": px, "low": px, "close": px,
                      "volume": df["vv"]})
    return f[(df["vv"] > 0)].dropna(subset=["close"])


def load_bars(paths: list[str], kind: str, override: dict):
    """1分足の DataFrame（code, dt, open, high, low, close, volume）にそろえる。"""
    import pandas as pd

    frames = []
    for p in paths:
        df = _read(p)
        cols = set(df.columns)
        if {"code", "d", "pv", "vv"} <= cols and ({"min1", "min5"} & cols) and not override:
            step = 1 if "min1" in cols else 5
            frames.append(_from_min_agg(df, step))
            print(f"読み込み {Path(p).name}: {len(frames[-1]):,}本（{step}分集計形式）")
            continue
        m = detect(list(df.columns), kind, override)
        dt = _datetime(df, m)
        code = df[m["code"]].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        if kind == "bars":
            f = pd.DataFrame({"code": code, "dt": dt.dt.floor("min"), "open": df[m["open"]],
                              "high": df[m["high"]], "low": df[m["low"]], "close": df[m["close"]],
                              "volume": df[m["volume"]]})
        else:  # 歩み値 → 1分足
            t = pd.DataFrame({"code": code, "dt": dt.dt.floor("min"), "price": df[m["price"]],
                              "volume": df[m["volume"]]})
            f = t.groupby(["code", "dt"], sort=False).agg(
                open=("price", "first"), high=("price", "max"), low=("price", "min"),
                close=("price", "last"), volume=("volume", "sum")).reset_index()
        frames.append(f.dropna(subset=["dt", "close"]))
        print(f"読み込み {Path(p).name}: {len(f):,}本")
    bars = pd.concat(frames, ignore_index=True)
    bars = bars.groupby(["code", "dt"], sort=False).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum")).reset_index()
    return bars.sort_values(["dt", "code"]).reset_index(drop=True)


def day_table(bars):
    """銘柄×日の四本値と前日終値・年初来高値（データ内で計算）。"""
    d = bars.assign(day=bars["dt"].dt.date).groupby(["code", "day"]).agg(
        high=("high", "max"), low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum")).reset_index().sort_values(["code", "day"])
    d["prev_close"] = d.groupby("code")["close"].shift(1)
    d["year"] = [x.year for x in d["day"]]
    d["ytd_high"] = d.groupby(["code", "year"])["high"].transform(lambda s: s.shift(1).cummax())
    first_day = d.groupby("year")["day"].transform("min")
    # データが年初から揃っていない年は、年初来高値を使わない
    d.loc[[fd.month > 1 or fd.day > 10 for fd in first_day], "ytd_high"] = None
    return d


def bar_minutes(bars) -> int:
    """足の長さ（分）を推定する（1分足なら1、5分足なら5）。"""
    import numpy as np

    d = bars.sort_values(["code", "dt"]).groupby("code")["dt"].diff().dropna()
    d = d[d > np.timedelta64(0, "s")]
    return max(1, int(d.min().total_seconds() // 60)) if len(d) else 1


def run(bars, cfg_rules: RuleConfig, known: dict[str, SymbolInfo], min_day_change: float,
        codes: set[str] | None, max_day_change: float = 0.4):
    days = day_table(bars)
    days["move"] = [max(h / p - 1, 1 - lo / p) if p == p and p else 0
                    for h, lo, p in zip(days["high"], days["low"], days["prev_close"])]
    # 1日で±40%を超える動き（株式分割・併合やデータ不整合の可能性が高い）は除外する
    bad = days["move"] > max_day_change
    sel = days[(days["move"] >= min_day_change) & ~bad & days["prev_close"].notna()]
    if bad.any():
        print(f"除外：1日で±{max_day_change:.0%}超動いた {int(bad.sum()):,} 銘柄日（分割・データ不整合の疑い）")
    if codes:
        sel = sel[sel["code"].isin(codes)]
    keys = set(zip(sel["code"], sel["day"]))
    info = {r.code: r for r in sel.itertuples()}  # 銘柄ごとの最新行（使わない）
    del info
    step = bar_minutes(bars)
    per_day = len(bars[[k in keys for k in zip(bars["code"], bars["dt"].dt.date)]]) / max(len(keys), 1)
    full = 300 / step  # 取引時間5時間ぶんの本数
    print(f"対象：{len(keys):,} 銘柄日（前日比±{min_day_change:.0%}以上動いた日）")
    print(f"足の長さ {step}分 / 1銘柄日あたり平均 {per_day:.0f}本（全部そろえば約{full:.0f}本 → 充足率 {per_day / full:.0%}）")

    infos = {c: known.get(c) or SymbolInfo(c, "", None) for c in sel["code"].unique()}
    engine = Engine(list(infos.values()), cfg_rules)
    meta = {(r.code, r.day): r for r in sel.itertuples()}
    book = PriceBook()
    alerts: list[AlertRow] = []
    b = bars.assign(day=bars["dt"].dt.date)
    b = b[[k in keys for k in zip(b["code"], b["day"])]]
    for day, g in b.groupby("day", sort=True):
        cum: dict[str, list[float]] = {}
        for code in g["code"].unique():
            m = meta[(code, day)]
            base = known.get(code)
            infos[code].ytd_high = base.ytd_high if base and base.ytd_high else (
                m.ytd_high if m.ytd_high == m.ytd_high else None)
        for r in g.itertuples():
            book.add(r.code, r.dt.to_pydatetime(), r.high, r.low, r.close)
            m = meta[(r.code, day)]
            c = cum.setdefault(r.code, [0.0, 0.0, 0.0])  # 累計出来高, 累計代金, 当日高値
            path = (r.open, r.low, r.high, r.close) if r.close >= r.open else (r.open, r.high, r.low, r.close)
            for k, px in enumerate(path):
                dv = r.volume / 4
                c[0] += dv
                c[1] += dv * px
                c[2] = max(c[2], px)
                ts = r.dt.to_pydatetime() + timedelta(seconds=step * 15 * k)
                snap = Snapshot(ts, r.code, float(px), c[0], vwap=c[1] / c[0] if c[0] else None,
                                high=c[2], prev_close=float(m.prev_close))
                for a in engine.process(snap):
                    alerts.append(AlertRow(a.ts, a.symbol, a.rule, a.level, a.price))
        end = datetime.combine(day, datetime.min.time()) + timedelta(hours=15, minutes=31)
        for a in engine.tick(end):
            alerts.append(AlertRow(a.ts, a.symbol, a.rule, a.level, a.price))
    book.freeze()
    return alerts, book, b


def turnover_study(b, known: dict[str, SymbolInfo]) -> list[dict]:
    """「高値・安値は当日出来高の何%時点で付いたか」（浮動株があれば浮動株回転率も）。"""
    out = []
    for (code, day), g in b.groupby(["code", "day"], sort=False):
        g = g.sort_values("dt")
        cum = g["volume"].cumsum()
        total = cum.iloc[-1]
        if not total:
            continue
        ih, il = g["high"].idxmax(), g["low"].idxmin()
        fl = known.get(code).float_shares if known.get(code) else None
        out.append({
            "code": code, "day": str(day), "total_volume": total,
            "high_time": g.loc[ih, "dt"].strftime("%H:%M"), "high_vol_share": cum.loc[ih] / total,
            "low_time": g.loc[il, "dt"].strftime("%H:%M"), "low_vol_share": cum.loc[il] / total,
            "high_float_turnover": (cum.loc[ih] / fl) if fl else None,
            "low_float_turnover": (cum.loc[il] / fl) if fl else None,
        })
    return out


def summarize_study(study: list[dict]) -> str:
    """高値・安値が当日出来高の何%時点で付いたかの分布。"""
    import pandas as pd

    if not study:
        return ""
    df = pd.DataFrame(study)
    out = ["高値・安値が「当日出来高の何%を消化した時点」で付いたか（前日比±5%以上の銘柄日）"]
    for col, name in (("high_vol_share", "高値"), ("low_vol_share", "安値")):
        q = df[col].quantile([0.25, 0.5, 0.75])
        out.append(f"  {name}: 中央値 {q[0.5]:.0%}（25%〜75%の範囲 {q[0.25]:.0%}〜{q[0.75]:.0%}）")
    early = (df["high_time"] < "09:30").mean()
    out.append(f"  高値が9:30より前（寄り天型）: {early:.0%} / 14:30以降（引け高型）: {(df['high_time'] >= '14:30').mean():.0%}")
    fl = df.dropna(subset=["high_float_turnover"])
    if len(fl):
        out.append(f"  浮動株回転率（{len(fl)}件）: 高値時 中央値 {fl['high_float_turnover'].median():.0%}"
                   f" / 安値時 中央値 {fl['low_float_turnover'].median():.0%}")
    return "\n".join(out)


# ---------------- 時間帯をそろえた相対出来高（RVOL） ----------------

RVOL_BUCKETS = [(0, 1, "1倍未満"), (1, 2, "1〜2倍"), (2, 3, "2〜3倍"), (3, 5, "3〜5倍"),
                (5, 10, "5〜10倍"), (10, 20, "10〜20倍"), (20, float("inf"), "20倍以上")]


def rvol_bucket(v) -> str:
    if v is None or v != v:
        return "不明（過去データ不足）"
    for lo, hi, name in RVOL_BUCKETS:
        if lo <= v < hi:
            return name
    return "不明（過去データ不足）"


def compute_rvol(bars, keys: set, window: int = 60, min_periods: int = 20) -> dict:
    """銘柄×日×時刻ごとの RVOL＝その時刻までの累計出来高 ÷ 過去window営業日の同じ時刻までの累計出来高の平均。
    戻り値は {(銘柄, 足の開始時刻): RVOL}（keys に含まれる銘柄日だけ）。"""
    b = bars[["code", "dt", "volume"]].copy()
    b["day"] = b["dt"].dt.normalize()
    b["slot"] = b["dt"] - b["day"]
    piv = b.pivot_table(index=["code", "day"], columns="slot", values="volume",
                        aggfunc="sum", fill_value=0).astype("float32")
    cum = piv.cumsum(axis=1)
    base = cum.groupby(level="code", group_keys=False).apply(
        lambda g: g.rolling(window, min_periods=min_periods).mean().shift(1))
    rv = (cum / base.where(base > 0))
    import pandas as pd

    idx = pd.MultiIndex.from_tuples([(c, pd.Timestamp(d)) for c, d in keys], names=["code", "day"])
    rv = rv.reindex(idx.intersection(rv.index))
    out = {}
    for (code, day), row in rv.iterrows():
        for slot, v in row.items():
            if v == v:
                out[(code, (day + slot).to_pydatetime())] = float(v)
    return out


def group_label(rule: str, level: str) -> str:
    """RVOL別の集計で、R10の段階はまとめて見る。"""
    if rule == "R10" and level.endswith("段階"):
        try:
            n = int(level.replace("−", "-").rstrip("段階").rstrip("%"))
        except ValueError:
            return level
        if n >= 25:
            return "+25%以上の段階"
        if n >= 10:
            return "+10〜20%の段階"
        if n <= -15:
            return "−15%以下の段階"
        return "±5〜10%の段階"
    return level


def rvol_table(rows: list[dict], min_n: int = 30) -> tuple[str, list[dict]]:
    from collections import defaultdict

    from .evaluate import OUTLIER

    groups = defaultdict(list)
    for r in rows:
        groups[(r["rule"], group_label(r["rule"], r["level"]), r["rvol_bucket"])].append(r)
    order = [name for _, _, name in RVOL_BUCKETS] + ["不明（過去データ不足）"]
    recs = []
    for (rule, label, bucket), rs in groups.items():
        d = rs[0]["dir"] or 1
        vals = [r["ret30"] * d for r in rs if r["ret30"] is not None and abs(r["ret30"]) <= OUTLIER]
        v15 = [r["ret15"] * d for r in rs if r["ret15"] is not None and abs(r["ret15"]) <= OUTLIER]
        recs.append({
            "rule": rule, "level": label, "rvol": bucket, "n": len(rs),
            "hit30": (sum(1 for v in vals if v > 0) / len(vals)) if vals and rs[0]["dir"] else None,
            "avg15": sum(v15) / len(v15) if v15 else None,
            "avg30": sum(vals) / len(vals) if vals else None,
            "med30": sorted(vals)[len(vals) // 2] if vals else None,
        })
    recs.sort(key=lambda x: (x["rule"], x["level"], order.index(x["rvol"])))

    def pct(v, signed=True):
        return "-" if v is None else (f"{v:+.2%}" if signed else f"{v:.0%}")

    lines = ["RVOL（その時刻までの出来高が、過去60日の同じ時刻の平均の何倍か）別の成績",
             "ルール 種類              RVOL                件数  当たり30分 平均15分 平均30分 中央30分"]
    for r in recs:
        if r["n"] < min_n:
            continue
        lines.append(f"{r['rule']:<5} {r['level']:<16} {r['rvol']:<18} {r['n']:>6}  "
                     f"{pct(r['hit30'], False):>9} {pct(r['avg15']):>8} {pct(r['avg30']):>8} {pct(r['med30']):>8}")
    lines.append(f"※件数{min_n}件未満の行は省略。平均・中央値は期待方向に動いたらプラス（R10は上がればプラス）。")
    return "\n".join(lines), recs


def inspect(path: str):
    if path.lower().endswith(".7z"):
        try:
            import py7zr
        except ImportError:
            raise SystemExit("7zの中身を見るには: py -3.11 -m pip install py7zr （または 7-Zip で1ファイルだけ展開して指定）")
        with py7zr.SevenZipFile(path) as z:
            names = z.getnames()
        print(f"{len(names)} ファイル。先頭:", *names[:20], sep="\n  ")
        return
    df = _read(path)
    print(f"{path}\n行数: {len(df):,}\n列と型:")
    for c, t in df.dtypes.items():
        print(f"  {c!r}: {t}")
    print("\n先頭5行:")
    print(df.head().to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="ファイル（* 可）")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--kind", choices=["bars", "ticks"], default="bars")
    ap.add_argument("--inspect", action="store_true", help="列名と先頭行を表示して終了")
    ap.add_argument("--col", action="append", default=[], help="役割=列名（time/date/code/open/high/low/close/volume/price）")
    ap.add_argument("--min-day-change", type=float, default=0.05)
    ap.add_argument("--codes", nargs="*")
    ap.add_argument("--start")
    ap.add_argument("--end")
    args = ap.parse_args()

    paths = sorted({p for pat in args.paths for p in glob.glob(pat)}) or args.paths
    if args.inspect:
        inspect(paths[0])
        return
    cfg = load_config(args.config)
    override = dict(c.split("=", 1) for c in args.col)
    bars = load_bars(paths, args.kind, override)
    if args.start:
        bars = bars[bars["dt"] >= args.start]
    if args.end:
        bars = bars[bars["dt"] < (datetime.fromisoformat(args.end) + timedelta(days=1))]
    known = {s.code: s for s in cfg.symbols}
    alerts, book, used = run(bars, cfg.rules, known, args.min_day_change,
                             set(args.codes) if args.codes else None)
    out = cfg.data_dir / f"backtest_{datetime.now():%Y%m%d_%H%M}"
    out.mkdir(parents=True, exist_ok=True)
    rows = evaluate(alerts, book)
    print("RVOL（相対出来高）を計算中…")
    keys = set(zip(used["code"], used["day"]))
    rv = compute_rvol(bars, keys)
    step = bar_minutes(bars)
    for r, a in zip(rows, alerts):
        t = a.ts.replace(second=0, microsecond=0)
        t = t.replace(minute=t.minute - t.minute % step)
        r["rvol"] = rv.get((a.symbol, t))
        r["rvol_bucket"] = rvol_bucket(r["rvol"])
    summary = summarize(rows)
    write_csv(out / "eval.csv", rows)
    write_csv(out / "evalsum.csv", summary)
    study = turnover_study(used, known)
    write_csv(out / "turnover_study.csv", study)
    print(f"\n通知 {len(rows):,}件\n")
    print(format_summary(summary))
    print("\n" + summarize_study(study))
    text, recs = rvol_table(rows)
    write_csv(out / "evalsum_rvol.csv", recs)
    print("\n" + text)
    print(f"\n保存先: {out}")


if __name__ == "__main__":
    main()
