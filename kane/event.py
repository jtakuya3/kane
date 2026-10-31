"""材料（IR・ニュース）が出た時刻の前後で、本命と監視銘柄がどう動いたかを snapshots から調べる。

    py -3.11 -m kane.event 3858 "2026-10-27 12:30"
    py -3.11 -m kane.event 3858 "2026-10-27 12:30" --after 90 --group security

出すもの
  1) 本命：材料の時刻の前後を1分ごとに（値段・前日比・1分出来高・特別気配）
  2) 監視銘柄全部：材料の時刻の値段を基準に +1/+5/+15/+30/+60分後の騰落率と、その間の出来高
     （どの銘柄が何分遅れで連れ高したか、または逆に売られたか）
材料が昼休み（11:30〜12:30）に出たときは、基準を「前引け」、反応を「後場寄り」から数える。
"""
from __future__ import annotations

import argparse
import csv
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .config import load_config

MARKS = [1, 5, 15, 30, 60]


def load_day(path: Path, codes: set[str] | None = None):
    """snapshots_YYYYMMDD.csv → 銘柄ごとの [(時刻, 値段, 累計出来高, 前日終値, 特別気配)]（時刻順）。"""
    out: dict[str, list] = defaultdict(list)
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            c = r["symbol"]
            if codes and c not in codes:
                continue
            try:
                ts = datetime.fromisoformat(r["ts"])
                p = float(r["price"])
                v = float(r["volume"] or 0)
            except (ValueError, KeyError):
                continue
            pc = float(r["prev_close"]) if r.get("prev_close") else None
            sp = "特買" if r.get("buy1_sign") == "0102" else ("特売" if r.get("sell1_sign") == "0102" else "")
            out[c].append((ts, p, v, pc, sp))
    for c in out:
        out[c].sort(key=lambda x: x[0])
    return out


def at(rows, t: datetime):
    """t 以前の最後の値（無ければ None）。"""
    i = bisect_right([r[0] for r in rows], t)
    return rows[i - 1] if i else None


def session_time(t: datetime) -> tuple[datetime, datetime]:
    """（基準の時刻, 反応を数え始める時刻）。昼休みなら 前引け と 後場寄り。"""
    hm = t.hour * 60 + t.minute
    if 11 * 60 + 30 <= hm < 12 * 60 + 30:
        return t.replace(hour=11, minute=30, second=0), t.replace(hour=12, minute=30, second=0)
    if hm >= 15 * 60 + 30:
        return t.replace(hour=15, minute=30, second=0), t + timedelta(days=1)  # 引け後：翌日（別ファイル）
    return t, t


def pct(a, b):
    return (a / b - 1) * 100 if a and b else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code")
    ap.add_argument("when", help='"2026-10-27 12:30"')
    ap.add_argument("--before", type=int, default=10, help="本命の1分ごとの表：材料の何分前から")
    ap.add_argument("--after", type=int, default=60, help="何分後まで")
    ap.add_argument("--group", help="監視銘柄をこのグループだけに（security など）")
    ap.add_argument("--config", default="config.toml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    t0 = datetime.fromisoformat(args.when)
    path = cfg.data_dir / f"snapshots_{t0:%Y%m%d}.csv"
    if not path.exists():
        print(f"{path} がありません（その日の監視が動いていない）")
        return
    names = {s.code: s.name for s in cfg.symbols}
    groups = {s.code: s.group for s in cfg.symbols}
    codes = {s.code for s in cfg.symbols if not args.group or s.group == args.group} | {args.code}
    data = load_day(path, codes)
    base_t, react_t = session_time(t0)
    if base_t != t0:
        print(f"材料 {t0:%H:%M} は取引時間外 → 基準 {base_t:%H:%M}、反応は {react_t:%H:%M} から数える")

    # 1) 本命
    rows = data.get(args.code)
    print(f"\n■ {args.code} {names.get(args.code, '')}  材料 {t0:%Y-%m-%d %H:%M}")
    if not rows:
        print("  この銘柄の記録がありません（その日は固定監視に入っていなかった）")
    else:
        b = at(rows, base_t)
        print(f"  基準 {base_t:%H:%M} の値段 {b[1]:,.0f}円（前日比 {pct(b[1], b[3]) or 0:+.1f}%）" if b else "  基準の値段なし")
        print("  時刻    値段     前日比   1分出来高   特別気配")
        start = base_t - timedelta(minutes=args.before)
        end = react_t + timedelta(minutes=args.after)
        t = start.replace(second=0)
        prev = at(rows, t)
        while t <= end:
            t2 = t + timedelta(minutes=1)
            r = at(rows, t2)
            if r and (11 * 60 + 30 > t.hour * 60 + t.minute or t.hour * 60 + t.minute >= 12 * 60 + 30):
                dv = r[2] - (prev[2] if prev else r[2])
                mark = " ←材料" if t <= t0 < t2 else (" ←後場寄り" if t == react_t and base_t != t0 else "")
                print(f"  {t:%H:%M}  {r[1]:>7,.0f}  {pct(r[1], r[3]) or 0:+6.1f}%  {dv:>10,.0f}   {r[4]}{mark}")
                prev = r
            t = t2

    # 2) 監視銘柄全部
    print(f"\n■ 監視銘柄の反応（基準 {base_t:%H:%M} の値段から、{react_t:%H:%M} 以降 +N分後）")
    head = "  コード  銘柄              " + "".join(f"{'+' + str(m) + '分':>8s}" for m in MARKS) + "   出来高(+60分)  基準時の出来高"
    print(head)
    res = []
    for c, rs in data.items():
        b = at(rs, base_t)
        if not b:
            continue
        chg = []
        for m in MARKS:
            r = at(rs, react_t + timedelta(minutes=m))
            chg.append(pct(r[1], b[1]) if r else None)
        r60 = at(rs, react_t + timedelta(minutes=60))
        dv = (r60[2] - b[2]) if r60 else None
        res.append((c, chg, dv, b[2]))
    res.sort(key=lambda x: -(x[1][2] if x[1][2] is not None else -999))  # +15分の騰落率で並べる
    for c, chg, dv, v0 in res:
        cells = "".join(f"{x:+7.1f}%" if x is not None else "      -" for x in chg)
        star = " ★本命" if c == args.code else ""
        g = f"[{groups.get(c, '')}]"
        print(f"  {c:6s}{(names.get(c, '') + g)[:16]:16s} {cells}   {dv or 0:>12,.0f}  {v0:>12,.0f}{star}")
    print("\n並びは +15分後の騰落率の高い順。本命と同じ向きに動いた銘柄が「連想で動く仲間」。")


if __name__ == "__main__":
    main()
