"""早期検知の案A〜Cの検証（5分足・全銘柄日）。

    py -3.11 -m kane.early "C:/Users/takuy/Downloads/_backtest_data/intraday_agg*.parquet"

通常のバックテストは「結果的に±5%動いた日」だけを対象にするため、早い段階の買いシグナルは
実力以上に良く見える。ここでは選別せず全銘柄日を対象にし、シグナルが出た5分足の「次の足」で
買ったとして（見てから買う想定）、15分・30分・60分後と大引けまでのリターンを測る。

- A 点火：その5分の出来高が、過去60日の同じ時刻の5分出来高の平均のX倍以上
          × 株価はまだVWAP −0.5%〜+2% × 前日比 +1〜+4%
- B 寄り後の初動：9:30まで × RVOL X倍以上 × 前日比 +3〜+5% × VWAP乖離 0〜+3%
- C 高値の手前：年初来高値まであと2%以内（まだ抜けていない） × RVOL X倍以上
- 比較：現行の買い候補（年初来高値を抜けて+2%以内 × RVOL 2〜10倍）と、条件なしの平均
- ショート側（下がれば当たり）：R2 VWAP乖離+8%/+10%以上 × RVOL20倍以上、利確警戒 前日比+25%以上 × RVOL10倍以上
  （R3失速・R4ダブルトップは1分足の形を見るルールなので、5分足のここでは検証しない）
- 出来高の年初来記録（R15）：当日の出来高が今年の最大日を超えた / この時刻までで今年最大の日を上回るペース。
  方向を決めない「注目」の知らせなので、上がればプラスで表示する（その後どちらに動きやすいかを見る）
どれも1銘柄1日1回（最初に条件を満たした足）、その時点の売買代金の累計が --min-value 以上だけ。
"""
from __future__ import annotations

import argparse
import glob
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

from .backtest import bar_minutes, load_bars, period_of
from .config import load_config
from .evaluate import OUTLIER, write_csv

HORIZONS = {"15分": 15, "30分": 30, "60分": 60}
PERIODS = ["12〜2月", "3〜4月", "5〜6月"]


def variants():
    """(キー, 名前, 条件)。条件は各配列（日×足）を受け取り True/False の配列を返す。"""
    def a(x):
        return lambda c: ((c["burst"] >= x) & (c["dev"] >= -0.005) & (c["dev"] <= 0.02)
                          & (c["chg"] >= 0.01) & (c["chg"] <= 0.04))

    def b(x):
        return lambda c: ((c["smin"] < 30) & (c["rvol"] >= x) & (c["chg"] >= 0.03) & (c["chg"] <= 0.05)
                          & (c["dev"] >= 0) & (c["dev"] <= 0.03))

    def cc(x):
        return lambda c: (c["P"] >= c["ytd"] * 0.98) & (c["P"] < c["ytd"]) & (c["rvol"] >= x)

    return [
        ("A3", "A 点火 5分出来高3倍以上", a(3)),
        ("A5", "A 点火 5分出来高5倍以上", a(5)),
        ("A10", "A 点火 5分出来高10倍以上", a(10)),
        ("A5x", "参考 A 5倍（価格条件なし・前日比プラス）", lambda c: (c["burst"] >= 5) & (c["chg"] > 0)),
        ("B3", "B 寄り後の初動 RVOL3倍以上", b(3)),
        ("B5", "B 寄り後の初動 RVOL5倍以上", b(5)),
        ("C2", "C 高値の手前 RVOL2倍以上", cc(2)),
        ("C5", "C 高値の手前 RVOL5倍以上", cc(5)),
        ("BUY", "現行 買い候補（高値抜け×RVOL2〜10倍）",
         lambda c: (c["P"] > c["ytd"]) & (c["P"] <= c["ytd"] * 1.02) & (c["rvol"] >= 2) & (c["rvol"] < 10)),
        ("V_YTD", "出来高 年初来更新（当日累計＞今年の最大日）", lambda c: c["cumV"] > c["ytdv"]),
        ("V_PACE", "出来高 年初来ペース（9:05以降）",
         lambda c: (c["cumV"] >= c["ytdv"] * c["frac"]) & (c["smin"] >= 5)),
        ("V_PACE_UP", "出来高 年初来ペース × 前日比プラス",
         lambda c: (c["cumV"] >= c["ytdv"] * c["frac"]) & (c["smin"] >= 5) & (c["chg"] > 0)),
        ("S_R2_8", "売 R2 VWAP乖離+8%以上×RVOL20倍以上", lambda c: (c["dev"] >= 0.08) & (c["rvol"] >= 20)),
        ("S_R2_10", "売 R2 VWAP乖離+10%以上×RVOL20倍以上", lambda c: (c["dev"] >= 0.10) & (c["rvol"] >= 20)),
        ("S_R2_8x", "参考 売 VWAP乖離+8%以上（出来高条件なし）", lambda c: c["dev"] >= 0.08),
        ("S_FADE", "売 利確警戒 前日比+25%以上×RVOL10倍以上", lambda c: (c["chg"] >= 0.25) & (c["rvol"] >= 10)),
    ]


def direction(key: str) -> int:
    """+1＝上がれば当たり、−1＝下がれば当たり（S_ で始まる案）。"""
    return -1 if key.startswith("S_") else 1


def _rolling_prev_mean(x: np.ndarray, window: int = 60, min_periods: int = 20) -> np.ndarray:
    """行（日）方向に、前日までの window 日の平均（min_periods 日未満は NaN）。"""
    d = x.shape[0]
    cs = np.vstack([np.zeros((1, x.shape[1])), np.cumsum(x, axis=0)])
    idx = np.arange(d)
    lo = np.maximum(0, idx - window)
    cnt = (idx - lo).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        m = (cs[idx] - cs[lo]) / cnt[:, None]
    m[cnt < min_periods] = np.nan
    return m


def _ffill(a: np.ndarray) -> np.ndarray:
    """行ごとに左から NaN を埋める。"""
    mask = np.isnan(a)
    idx = np.where(~mask, np.arange(a.shape[1]), 0)
    np.maximum.accumulate(idx, axis=1, out=idx)
    out = a[np.arange(a.shape[0])[:, None], idx]
    out[np.cumsum(~mask, axis=1) == 0] = np.nan
    return out


def study(bars, min_value: float, max_day_change: float = 0.4):
    """シグナルごとの記録と、比較用の「条件なし」の集計を返す。"""
    step = bar_minutes(bars)
    b = bars[["code", "dt", "close", "volume"]].copy()
    b["day"] = b["dt"].dt.normalize()
    b["smin"] = ((b["dt"] - b["day"]).dt.total_seconds() // 60 - 540).astype(int)
    b = b[(b["smin"] >= 0) & (b["smin"] < 390)]
    slots = np.sort(b["smin"].unique())
    smap = {m: i for i, m in enumerate(slots)}
    b["si"] = b["smin"].map(smap)
    days_all = np.sort(b["day"].unique())
    first_of_year = {}
    for d in days_all:
        first_of_year.setdefault(d.astype("datetime64[Y]").astype(int) + 1970, d)
    ytd_ok = {y: (str(d)[5:10] <= "01-10") for y, d in first_of_year.items()}
    n_days = defaultdict(int)
    for d in days_all:
        n_days[period_of(d.astype("datetime64[ms]").astype(datetime))] += 1
    hz = {k: max(1, v // step) for k, v in HORIZONS.items()}
    from .backtest import volume_profile_from_bars
    from .rules import vol_frac

    prof = volume_profile_from_bars(bars, step)
    base = datetime(2000, 1, 1, 9, 0)
    # 足の終わりの時刻までに、普段1日の出来高の何割が出ているか（市場全体の平均。下限3%）
    frac = np.array([max(vol_frac(base + timedelta(minutes=int(m) + step), prof), 0.03) for m in slots])
    mfe_n = hz["30分"]

    S = len(slots)
    recs = []
    ctrl = defaultdict(lambda: [0, 0, 0.0])  # 期間 → [件数, 上がった数, 30分リターン合計]
    b = b.sort_values(["code", "day", "si"])
    codes = b["code"].to_numpy()
    cut = np.flatnonzero(codes[1:] != codes[:-1]) + 1
    for g in np.split(np.arange(len(b)), cut):
        sub = b.iloc[g]
        days, di = np.unique(sub["day"].to_numpy(), return_inverse=True)
        D = len(days)
        if D < 21:
            continue
        si = sub["si"].to_numpy()
        V = np.zeros((D, S))
        PV = np.zeros((D, S))
        np.add.at(V, (di, si), sub["volume"].to_numpy(float))
        np.add.at(PV, (di, si), (sub["close"] * sub["volume"]).to_numpy(float))
        with np.errstate(invalid="ignore", divide="ignore"):
            raw = np.where(V > 0, PV / V, np.nan)
        P = _ffill(raw)
        cumV, cumPV = np.cumsum(V, axis=1), np.cumsum(PV, axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            vwap = np.where(cumV > 0, cumPV / cumV, np.nan)
            close = P[:, -1]
            pc = np.concatenate([[np.nan], close[:-1]])
            hi, lo = np.nanmax(raw, axis=1), np.nanmin(raw, axis=1)
            move = np.maximum(hi / pc - 1, 1 - lo / pc)
            base_cum, base_bar = _rolling_prev_mean(cumV), _rolling_prev_mean(V)
            rvol = np.where(base_cum > 0, cumV / base_cum, np.nan)
            burst = np.where(base_bar > 0, V / base_bar, np.nan)
            chg = P / pc[:, None] - 1
            dev = P / vwap - 1
        years = days.astype("datetime64[Y]").astype(int) + 1970
        ytd = np.full(D, np.nan)
        ytdv = np.full(D, np.nan)  # 今年の最大日出来高（前日まで）
        dayv = V.sum(axis=1)
        for y in np.unique(years):
            if not ytd_ok.get(y):
                continue
            ix = np.flatnonzero(years == y)
            h = np.fmax.accumulate(hi[ix])
            ytd[ix[1:]] = h[:-1]
            hv = np.maximum.accumulate(dayv[ix])
            ytdv[ix[1:]] = hv[:-1]
        valid_day = np.isfinite(pc) & ~(move > max_day_change)
        # 次の足で買う
        E = np.full((D, S), np.nan)
        E[:, :-1] = P[:, 1:]
        fwd = {}
        for k, n in hz.items():
            f = np.full((D, S), np.nan)
            f[:, :-1 - n] = P[:, 1 + n:]
            fwd[k] = f / E - 1
        fwd["大引け"] = close[:, None] / E - 1
        ok = valid_day[:, None] & np.isfinite(E) & (cumPV >= min_value) & np.isfinite(P)
        ctx = {"P": P, "chg": chg, "dev": dev, "rvol": rvol, "burst": burst, "ytd": ytd[:, None],
               "smin": slots[None, :], "cumV": cumV, "ytdv": ytdv[:, None], "frac": frac[None, :]}
        # 比較用：条件なし（売買代金の条件だけ）の30分後
        r30 = fwd["30分"]
        cm = ok & np.isfinite(r30) & (np.abs(r30) <= OUTLIER)
        for d in np.flatnonzero(cm.any(axis=1)):
            per = period_of(days[d].astype("datetime64[ms]").astype(datetime))
            vals = r30[d][cm[d]]
            c = ctrl[per]
            c[0] += len(vals)
            c[1] += int((vals > 0).sum())
            c[2] += float(vals.sum())
        code = sub["code"].iloc[0]
        for key, _, cond in variants():
            with np.errstate(invalid="ignore"):
                m = cond(ctx) & ok
            for d in np.flatnonzero(m.any(axis=1)):
                j = int(np.argmax(m[d]))
                e = E[d, j]
                w = P[d, j + 1:j + 2 + mfe_n]
                t = days[d].astype("datetime64[ms]").astype(datetime) + timedelta(minutes=540 + int(slots[j]) + step)
                rec = {"variant": key, "code": code, "day": str(days[d])[:10], "time": t.strftime("%H:%M"),
                       "period": period_of(t), "chg": chg[d, j], "dev": dev[d, j], "rvol": rvol[d, j],
                       "burst": burst[d, j], "value_oku": cumPV[d, j] / 1e8}
                sg = direction(key)  # 記録するリターンは「期待した方向に動いたらプラス」
                for k in fwd:
                    rec[f"ret_{k}"] = fwd[k][d, j] * sg
                up = np.nanmax(w) / e - 1 if len(w) else np.nan
                down = np.nanmin(w) / e - 1 if len(w) else np.nan
                rec["mfe30"], rec["mae30"] = (up, down) if sg > 0 else (-down, -up)
                recs.append(rec)
    return recs, ctrl, n_days


def _clean(vals):
    return [v for v in vals if v == v and abs(v) <= OUTLIER]


def summary(recs, ctrl, n_days) -> tuple[str, list[dict]]:
    names = {k: n for k, n, _ in variants()}
    total_days = sum(n_days.values()) or 1
    rows = []
    by = defaultdict(list)
    for r in recs:
        by[(r["variant"], "全期間")].append(r)
        by[(r["variant"], r["period"])].append(r)

    def pct(v, signed=True):
        return "-" if v is None else (f"{v:+.2%}" if signed else f"{v:.0%}")

    def med(v):
        v = sorted(v)
        return v[len(v) // 2] if v else None

    def avg(v):
        return sum(v) / len(v) if v else None

    lines = ["早期検知 A〜C とショート側の成績（全銘柄日・次の5分足で入った場合。プラス＝期待した方向に動いた）",
             f"{'案':<34}{'件数':>7}{'件/日':>7}{'当たり30分':>10}{'平均30分':>9}{'中央30分':>9}"
             f"{'平均60分':>9}{'平均大引け':>10}{'伸び30分':>9}{'逆行30分':>9}  中央時刻 中央前日比"]
    keys = [k for k, _, _ in variants()]
    for k in keys:
        rs = by.get((k, "全期間"), [])
        if not rs:
            continue
        r30 = _clean(r["ret_30分"] for r in rs)
        rec = {"variant": k, "name": names[k], "period": "全期間", "n": len(rs), "per_day": len(rs) / total_days,
               "hit30": (sum(v > 0 for v in r30) / len(r30)) if r30 else None, "avg30": avg(r30),
               "med30": med(r30), "avg60": avg(_clean(r["ret_60分"] for r in rs)),
               "avg_close": avg(_clean(r["ret_大引け"] for r in rs)),
               "mfe30": avg(_clean(r["mfe30"] for r in rs)), "mae30": avg(_clean(r["mae30"] for r in rs)),
               "med_time": med([r["time"] for r in rs]), "med_chg": med([r["chg"] for r in rs])}
        rows.append(rec)
        lines.append(f"{names[k]:<34}{rec['n']:>7,}{rec['per_day']:>7.1f}{pct(rec['hit30'], False):>10}"
                     f"{pct(rec['avg30']):>9}{pct(rec['med30']):>9}{pct(rec['avg60']):>9}{pct(rec['avg_close']):>10}"
                     f"{pct(rec['mfe30']):>9}{pct(rec['mae30']):>9}  {rec['med_time']:>6} {pct(rec['med_chg']):>8}")
    cn = sum(c[0] for c in ctrl.values())
    if cn:
        lines.append(f"{'比較：条件なし（全銘柄・全時刻）':<34}{cn:>7,}{'':>7}{sum(c[1] for c in ctrl.values()) / cn:>10.0%}"
                     f"{sum(c[2] for c in ctrl.values()) / cn:>+9.2%}")

    periods = [p for p in PERIODS if n_days.get(p)]
    lines += ["", "期間別の安定性（30分後の 平均 / 中央値 / 件数）",
              f"{'案':<34}" + "".join(f"{p:>26}" for p in periods)]
    for k in keys:
        cells = []
        for p in periods:
            rs = by.get((k, p), [])
            r30 = _clean(r["ret_30分"] for r in rs)
            rows.append({"variant": k, "name": names[k], "period": p, "n": len(rs),
                         "per_day": len(rs) / n_days[p], "avg30": avg(r30), "med30": med(r30)})
            cells.append("-" if not r30 else f"{avg(r30):+.2%} / {med(r30):+.2%} / {len(rs)}")
        lines.append(f"{names[k]:<34}" + "".join(f"{c:>26}" for c in cells))
    ctl = [f"{ctrl[p][2] / ctrl[p][0]:+.2%}" if ctrl[p][0] else "-" for p in periods]
    lines.append(f"{'比較：条件なし':<34}" + "".join(f"{c:>26}" for c in ctl))
    lines.append("※「条件なし」より明らかに上で、3期間とも平均・中央値がプラスなら採用候補。"
                 "件/日は全銘柄での1日あたりの通知数（少ないほど絞れている）。"
                 "「売」の行は下がればプラス（比較の「条件なし」は上がればプラスなので、ほぼ0との比較）。")
    return "\n".join(lines), rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--min-value", type=float, default=1e8, help="シグナル時点の売買代金の累計（円）の下限")
    args = ap.parse_args()
    paths = sorted({p for pat in args.paths for p in glob.glob(pat)}) or args.paths
    cfg = load_config(args.config)
    bars = load_bars(paths, "bars", {})
    print("計算中…（全銘柄日を対象にするので数分かかります）")
    recs, ctrl, n_days = study(bars, args.min_value)
    text, rows = summary(recs, ctrl, n_days)
    out = cfg.data_dir / f"early_{datetime.now():%Y%m%d_%H%M}"
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "early_signals.csv", recs)
    write_csv(out / "early_summary.csv", rows)
    print("\n" + text)
    print(f"\n保存先: {out}")


if __name__ == "__main__":
    main()
