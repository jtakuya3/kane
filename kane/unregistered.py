"""今日アラートが出たのに symbols.csv に無い銘柄（＝浮動株未登録）を、RVOL の高い順に並べる。

    py -3.11 -m kane.unregistered            # 今日
    py -3.11 -m kane.unregistered 20261029   # 日付指定

出来高が急に増えた銘柄（R15 年初来・R2 など）で、浮動株を調べて CSV に入れるべき候補を探す。
"""
from __future__ import annotations

import argparse
import csv
import re
from datetime import date

from .config import load_config

RVOL = re.compile(r"RVOL\s*([0-9.]+)倍")
VOL = re.compile(r"出来高\s*([0-9,]+)株")
NAME = re.compile(r"^\s*([0-9]{3}[0-9A-Z])\s*([^\s時]+)", re.M)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("day", nargs="?", default=date.today().strftime("%Y%m%d"))
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()
    cfg = load_config(args.config)
    known = {s.code for s in cfg.symbols}
    path = cfg.data_dir / f"alerts_{args.day}.csv"
    if not path.exists():
        print(f"{path} がありません（その日の監視が動いていないか、日付違い）")
        return
    rows: dict[str, dict] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            code = (r.get("symbol") or "").strip()
            if not code or code in known:
                continue
            msg = r.get("message") or ""
            rv = RVOL.search(msg)
            vol = VOL.search(msg)
            nm = NAME.search(msg)
            d = rows.setdefault(code, {"n": 0, "rules": set(), "rvol": 0.0, "vol": 0, "name": "", "last": ""})
            d["n"] += 1
            d["rules"].add(r.get("rule") or "")
            if rv:
                d["rvol"] = max(d["rvol"], float(rv.group(1)))
            if vol:
                d["vol"] = max(d["vol"], int(vol.group(1).replace(",", "")))
            if nm and not d["name"]:
                d["name"] = nm.group(2)
            d["last"] = (r.get("ts") or "")[11:19]
    if not rows:
        print("今日のアラートは全部登録済みの銘柄でした")
        return
    out = sorted(rows.items(), key=lambda kv: (-kv[1]["rvol"], -kv[1]["vol"]))[: args.top]
    print(f"{args.day} アラートが出た未登録銘柄 {len(rows)} 件（RVOL の高い順、上位{len(out)}）")
    print(f"{'コード':6s} {'銘柄':16s} {'RVOL':>7s} {'出来高':>14s} {'件数':>4s}  最後  ルール")
    for code, d in out:
        print(f"{code:6s} {d['name'][:16]:16s} {d['rvol']:7.1f} {d['vol']:14,d} {d['n']:4d}  {d['last']}  {','.join(sorted(d['rules']))}")
    print("\n浮動株を調べて symbols.csv に入れたい銘柄のコードを Claude に送る")


if __name__ == "__main__":
    main()
