"""日々公表・増担（増し担保規制）ライン付近の値動きの検証（価格条件だけで近似）。

    py -3.11 -m kane.kisei "C:/Users/takuy/Downloads/_backtest_data/intraday_agg*.parquet"

JPXの基準は「25日移動平均からの乖離（終値ベース）」と信用残・新規買付比率の組み合わせ。
ここでは手元データで分かる価格条件（乖離30%）だけを使い、次を測る。

1. ライン（終値で乖離30%になる株価）に対して、終値がどこで止まりやすいか
   （ライン直下に終値が溜まる＝回避の値動き、があるか）
2. 乖離30%超えの連続日数ごとの、翌日・5日後の値動き
   （1日目・2日目・3日目＝日々公表ライン、4日目以降）
3. 場中にラインを超えたのに終値でライン下に戻した日（押し戻し）と、終値で超えた日の、その後の差

信用残・新規買付比率のデータが無いので、実際に日々公表・増担になったかは分からない。
過去の日々公表・増担の銘柄一覧があれば、それで正確に検証できる。
"""
from __future__ import annotations

import argparse
import glob
from collections import defaultdict
from datetime import datetime

import numpy as np

from .backtest import load_bars, period_of
from .config import load_config
from .evaluate import write_csv

LINE = 0.30  # 乖離30%


def daily(bars):
    """5分足 → 日足（始値・高値・安値・終値・出来高）。株価は各足のVWAP。"""
    b = bars.assign(day=bars["dt"].dt.normalize())
    g = b.sort_values("dt").groupby(["code", "day"])
    d = g.agg(open=("close", "first"), high=("high", "max"), low=("low", "min"),
              close=("close", "last"), volume=("volume", "sum")).reset_index()
    return d.sort_values(["code", "day"]).reset_index(drop=True)


def line_price(prev24_sum: np.ndarray, k: float = LINE) -> np.ndarray:
    """当日の終値 C で 乖離＝C÷(25日平均, 当日を含む)−1 が k になる株価。
    C = (1+k)·S24 ÷ (25 − (1+k))  （S24＝前日までの24日の終値の合計）"""
    return (1 + k) * prev24_sum / (25 - (1 + k))


def study(d):
    recs = []
    for code, g in d.groupby("code", sort=False):
        if len(g) < 30:
            continue
        c = g["close"].to_numpy(float)
        o, h, lo = g["open"].to_numpy(float), g["high"].to_numpy(float), g["low"].to_numpy(float)
        days = g["day"].to_numpy()
        cs = np.concatenate([[0.0], np.cumsum(c)])
        n = len(c)
        idx = np.arange(n)
        ok = idx >= 24
        ma = np.full(n, np.nan)
        ma[ok] = (cs[idx[ok] + 1] - cs[idx[ok] - 24]) / 25
        s24 = np.full(n, np.nan)
        ok2 = idx >= 24
        s24[ok2] = cs[idx[ok2]] - cs[idx[ok2] - 24]
        dev = c / ma - 1
        ln = line_price(s24)
        streak = np.zeros(n, int)
        for i in range(n):
            if dev[i] == dev[i] and dev[i] >= LINE:
                streak[i] = (streak[i - 1] if i else 0) + 1
        for i in range(25, n - 1):
            if ln[i] != ln[i] or c[i - 1] <= 0:
                continue
            j5 = min(i + 5, n - 1)
            rec = {
                "code": code, "day": str(days[i])[:10],
                "period": period_of(days[i].astype("datetime64[ms]").astype(datetime)),
                "dev": dev[i], "streak": streak[i], "prev_streak": streak[i - 1],
                "close_vs_line": c[i] / ln[i] - 1, "high_vs_line": h[i] / ln[i] - 1,
                "day_ret": c[i] / c[i - 1] - 1,
                "next_gap": o[i + 1] / c[i] - 1, "next_ret": c[i + 1] / c[i] - 1,
                "next_high": h[i + 1] / c[i] - 1, "next_low": lo[i + 1] / c[i] - 1,
                "ret5": c[j5] / c[i] - 1,
                "next_above": bool(dev[i + 1] >= LINE) if dev[i + 1] == dev[i + 1] else None,
                "dev5": dev[j5],
            }
            recs.append(rec)
    return recs


def _stats(rs, key):
    v = sorted(r[key] for r in rs if r[key] is not None and r[key] == r[key] and abs(r[key]) < 0.6)
    if not v:
        return None, None
    return sum(v) / len(v), v[len(v) // 2]


def report(recs) -> tuple[str, list[dict]]:
    out, rows = [], []

    def pct(x, signed=True):
        return "-" if x is None else (f"{x:+.2%}" if signed else f"{x:.0%}")

    def line(name, rs):
        if len(rs) < 20:
            return
        a1, m1 = _stats(rs, "next_ret")
        g1, _ = _stats(rs, "next_gap")
        hi, _ = _stats(rs, "next_high")
        lw, _ = _stats(rs, "next_low")
        a5, m5 = _stats(rs, "ret5")
        up = [r["next_ret"] for r in rs if r["next_ret"] == r["next_ret"]]
        stay = [r["next_above"] for r in rs if r["next_above"] is not None]
        cool = [r["dev5"] < 0.15 for r in rs if r["dev5"] == r["dev5"]]
        row = {"group": name, "n": len(rs), "next_up": sum(x > 0 for x in up) / len(up) if up else None,
               "next_gap": g1, "next_ret": a1, "next_ret_med": m1, "next_high": hi, "next_low": lw,
               "ret5": a5, "ret5_med": m5,
               "next_above30": sum(stay) / len(stay) if stay else None,
               "cool5": sum(cool) / len(cool) if cool else None}
        rows.append(row)
        out.append(f"{name:<34}{len(rs):>7,}{pct(row['next_up'], False):>7}{pct(g1):>9}{pct(a1):>9}{pct(m1):>9}"
                   f"{pct(hi):>9}{pct(lw):>9}{pct(a5):>9}{pct(m5):>9}{pct(row['next_above30'], False):>9}"
                   f"{pct(row['cool5'], False):>9}")

    head = (f"{'グループ':<34}{'件数':>7}{'翌日↑':>7}{'翌寄り':>9}{'翌日終':>9}{'翌中央':>9}"
            f"{'翌高値':>9}{'翌安値':>9}{'5日後':>9}{'5日中央':>9}{'翌30%超':>9}{'5日冷え':>9}")

    out += ["1) 乖離30%超えの連続日数ごと（終値ベース。3日目＝日々公表の価格条件がそろう日）", head]
    for k, name in ((1, "1日目（初めて30%超え）"), (2, "2日目"), (3, "3日目（日々公表ライン）"),
                    (4, "4〜5日目"), (6, "6日目以降")):
        rs = [r for r in recs if (r["streak"] == k if k < 4 else
                                  (4 <= r["streak"] <= 5 if k == 4 else r["streak"] >= 6))]
        line(name, rs)
    out.append("")
    out += ["2) 乖離の大きさ別（30%超えの日）", head]
    for lo_, hi_, name in ((0.30, 0.50, "乖離30〜50%"), (0.50, 1.0, "乖離50〜100%"), (1.0, 9, "乖離100%以上")):
        line(name, [r for r in recs if lo_ <= r["dev"] < hi_])
    out.append("")
    out += ["3) ラインの手前・押し戻し（前日まで30%超えが0〜2日の日）", head]
    near = [r for r in recs if r["prev_streak"] <= 2]
    line("終値がライン直下（−3%〜0%）", [r for r in near if -0.03 <= r["close_vs_line"] < 0])
    line("終値がラインの少し下（−8%〜−3%）", [r for r in near if -0.08 <= r["close_vs_line"] < -0.03])
    line("場中で超えたが終値でライン下（押し戻し）", [r for r in near if r["high_vs_line"] >= 0 > r["close_vs_line"]])
    line("終値でラインを超えた", [r for r in near if r["close_vs_line"] >= 0])
    line("2日連続中で3日目にライン下で終わった", [r for r in recs if r["prev_streak"] == 2 and r["streak"] == 0])
    out.append("")

    # 終値がライン付近に溜まるか（回避の値動き）
    out.append("4) 終値がラインの前後どこで止まったか（前日まで2日連続30%超え＝3日目に乗るかどうかの日）")
    d3 = [r["close_vs_line"] for r in recs if r["prev_streak"] == 2]
    d1 = [r["close_vs_line"] for r in recs if r["prev_streak"] == 0 and r["high_vs_line"] >= -0.10]
    bins = [(-0.10, -0.06), (-0.06, -0.03), (-0.03, 0.0), (0.0, 0.03), (0.03, 0.06), (0.06, 0.10)]
    out.append(f"{'終値÷ライン−1':<16}" + "".join(f"{f'{a:+.0%}〜{b:+.0%}':>14}" for a, b in bins))
    for name, arr in (("3日目に乗る日", d3), ("比較：初日付近", d1)):
        tot = sum(1 for x in arr if -0.10 <= x < 0.10) or 1
        out.append(f"{name:<16}" + "".join(f"{sum(1 for x in arr if a <= x < b) / tot:>14.0%}" for a, b in bins)
                   + f"   （{tot}件）")
    out.append("※ライン直下（−3%〜0%）が「比較」より明らかに多ければ、3日目を避ける値動きがある。")
    out.append("※翌30%超＝翌日も終値で乖離30%以上の割合。5日冷え＝5日後に乖離15%未満（規制解除の水準）まで冷えた割合。")
    out.append("※株価は5分足のVWAPから作った近似の日足（高値・安値は実際より狭い）。±60%超のリターンは除外。")
    return "\n".join(out), rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--config", default="config.toml")
    args = ap.parse_args()
    paths = sorted({p for pat in args.paths for p in glob.glob(pat)}) or args.paths
    cfg = load_config(args.config)
    bars = load_bars(paths, "bars", {})
    print("日足を作成中…")
    d = daily(bars)
    recs = study(d)
    text, rows = report(recs)
    out = cfg.data_dir / f"kisei_{datetime.now():%Y%m%d_%H%M}"
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "kisei_days.csv", [r for r in recs if r["dev"] >= 0.2 or r["high_vs_line"] >= -0.1])
    write_csv(out / "kisei_summary.csv", rows)
    print("\n" + text)
    print(f"\n保存先: {out}")


if __name__ == "__main__":
    main()
