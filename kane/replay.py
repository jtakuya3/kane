"""録画した snapshots_YYYYMMDD.csv を流し直してルールを検証する（Slack通知なし）。

    python -m kane.replay data/snapshots_20261015.csv
    python -m kane.replay data/snapshots_20261015.csv --out alerts_replay.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .config import load_config
from .engine import Engine
from .sinks import ALERT_COLS, read_snapshots


def replay(cfg, path: Path):
    engine = Engine(cfg.symbols, cfg.rules)
    alerts, last = [], None
    for snap in read_snapshots(path):
        if last and snap.ts > last:
            alerts += engine.tick(snap.ts)
        alerts += engine.process(snap)
        last = snap.ts
    return alerts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    alerts = replay(load_config(args.config), args.csv)
    for a in alerts:
        print(f"{a.ts:%H:%M:%S} {a.message}")
    print(f"--- 通知 {len(alerts)}件")
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=ALERT_COLS)
            w.writeheader()
            for a in alerts:
                w.writerow({"ts": a.ts.isoformat(timespec="seconds"), "symbol": a.symbol,
                            "rule": a.rule, "level": a.level, "price": a.price,
                            "turnover": a.extras.get("turnover"), "vwap_dev": a.extras.get("vwap_dev"),
                            "message": a.message})


if __name__ == "__main__":
    main()
