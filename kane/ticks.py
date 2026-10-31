"""snapshots から1銘柄の「約定に近い」動きを復元する（歩み値の代わり）。

    py -3.11 -m kane.ticks 3858 "2026-10-27 12:29" "2026-10-27 13:20"
    py -3.11 -m kane.ticks 3858 "2026-10-27 12:29" "2026-10-27 13:20" --board   # 板の上位3本も出す

監視は固定銘柄を約0.3秒ごとに読み、値が変わったときだけ記録している。累計出来高の増え方＝その間の約定。
0.3秒の間に複数の約定があればまとめて1行になる（本物の歩み値ほど細かくはない）。
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime

from .config import load_config
from .sinks import decode_board


def fmt_q(q):
    return f"{q:,.0f}" if q not in (None, "") else "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code")
    ap.add_argument("start", help='"2026-10-27 12:29"')
    ap.add_argument("end", help='"2026-10-27 13:20"')
    ap.add_argument("--board", action="store_true", help="板の上位3本も表示")
    ap.add_argument("--all", action="store_true", help="出来高が増えていない行（気配の変化だけ）も全部出す")
    ap.add_argument("--config", default="config.toml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    t0, t1 = datetime.fromisoformat(args.start), datetime.fromisoformat(args.end)
    path = cfg.data_dir / f"snapshots_{t0:%Y%m%d}.csv"
    if not path.exists():
        print(f"{path} がありません")
        return
    name = next((s.name for s in cfg.symbols if s.code == args.code), "")
    print(f"■ {args.code} {name}  {t0:%Y-%m-%d %H:%M:%S} 〜 {t1:%H:%M:%S}")
    print("  時刻(ミリ秒)      約定値   約定株数   累計出来高     売気配(数量)       買気配(数量)     状態")
    prev_v = prev_p = prev_bid = prev_ask = None
    n_trade = 0
    tot = 0.0
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["symbol"] != args.code:
                continue
            ts = datetime.fromisoformat(r["ts"])
            v = float(r["volume"] or 0)
            p = float(r["price"])
            if ts < t0:
                prev_v, prev_p = v, p
                continue
            if ts > t1:
                break
            dv = v - prev_v if prev_v is not None else 0.0
            bid, ask = r.get("bid") or "", r.get("ask") or ""
            sign = "特買" if r.get("buy1_sign") == "0102" else ("特売" if r.get("sell1_sign") == "0102" else "")
            changed_quote = (bid, ask) != (prev_bid, prev_ask)
            if dv > 0 or args.all or (changed_quote and sign):
                mark = "約定" if dv > 0 else "気配"
                ask_s = f"{float(ask):,.0f}({fmt_q(float(r['sell1_qty']) if r.get('sell1_qty') else None)})" if ask else "-"
                bid_s = f"{float(bid):,.0f}({fmt_q(float(r['buy1_qty']) if r.get('buy1_qty') else None)})" if bid else "-"
                print(f"  {ts:%H:%M:%S}.{ts.microsecond // 1000:03d}  {p:>8,.0f}  {dv:>9,.0f}  {v:>11,.0f}   {ask_s:>16s}  {bid_s:>16s}   {sign or mark}")
                if args.board and r.get("board"):
                    buy, sell = decode_board(r["board"])
                    s3 = "  ".join(f"{pp:,.0f}×{qq:,.0f}" for pp, qq in (sell or [])[:3])
                    b3 = "  ".join(f"{pp:,.0f}×{qq:,.0f}" for pp, qq in (buy or [])[:3])
                    print(f"        売板 {s3}\n        買板 {b3}")
                if dv > 0:
                    n_trade += 1
                    tot += dv
            prev_v, prev_p, prev_bid, prev_ask = v, p, bid, ask
    print(f"\n約定のあった更新 {n_trade} 回、合計 {tot:,.0f}株")
    print("※ 0.3秒ごとの読み取りなので、同じ0.3秒の中の複数の約定は1行にまとまる")


if __name__ == "__main__":
    main()
