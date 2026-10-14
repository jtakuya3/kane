"""通知の答え合わせ：各通知の後、株価がどう動いたかを測り、ルールごとに当たり率を集計する。

    python -m kane.evaluate --date 20261015      # その日のライブ記録（alerts / bars）を評価
    python -m kane.evaluate --all                 # data_dir にある全日を合算

結果は data_dir に eval_*.csv（通知ごと）と evalsum_*.csv（ルールごとの集計）として保存する。
"""
from __future__ import annotations

import argparse
import bisect
import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

HORIZONS = [1, 5, 15, 30]  # 分
MFE_WINDOW = 15  # 分
OUTLIER = 0.30  # これを超えるリターンは集計から外す


@dataclass
class AlertRow:
    ts: datetime
    symbol: str
    rule: str
    level: str
    price: float


def expected_dir(rule: str, level: str) -> int:
    """その通知が当たったとみなす方向。+1=上がれば当たり、-1=下がれば当たり、0=方向なし（参考）。"""
    if rule == "R1":
        try:
            lv = float(level.rstrip("%")) / 100
        except ValueError:
            return 0
        return -1 if lv < 0.6 else (1 if lv >= 0.85 else -1)
    if rule in ("R2", "R3", "R4"):
        return -1
    if rule == "R9":
        return 1
    if rule == "R13":
        return 1 if level == "買い" else -1 if level == "売り" else 0
    if rule == "R14":
        return {"張り付き": 1, "警戒": -1, "剥がれ": -1}.get(level, 0)
    return 0  # R10 などは方向を決めず、上げ下げをそのまま記録する


class PriceBook:
    """銘柄ごとの1分足（開始時刻, 高値, 安値, 終値）。"""

    def __init__(self):
        self._bars: dict[str, list[tuple[datetime, float, float, float]]] = defaultdict(list)
        self._keys: dict[str, list[datetime]] = {}

    def add(self, symbol: str, start: datetime, high: float, low: float, close: float):
        self._bars[symbol].append((start, high, low, close))

    def freeze(self):
        for s, bars in self._bars.items():
            bars.sort(key=lambda b: b[0])
            self._keys[s] = [b[0] for b in bars]

    def close_at(self, symbol: str, t: datetime) -> float | None:
        """時刻 t までに確定した足の最後の終値（同じ日の中だけ）。"""
        keys = self._keys.get(symbol)
        if not keys:
            return None
        i = bisect.bisect_right(keys, t - timedelta(minutes=1)) - 1
        if i < 0 or keys[i].date() != t.date():
            return None
        return self._bars[symbol][i][3]

    def window(self, symbol: str, t0: datetime, t1: datetime):
        keys = self._keys.get(symbol) or []
        lo = bisect.bisect_left(keys, t0.replace(second=0, microsecond=0))
        hi = bisect.bisect_left(keys, t1)
        return [b for b in self._bars[symbol][lo:hi] if b[0].date() == t0.date()]

    def last_time(self, symbol: str, day) -> datetime | None:
        bars = [b[0] for b in self._bars.get(symbol, []) if b[0].date() == day]
        return max(bars) if bars else None


def evaluate(alerts: list[AlertRow], book: PriceBook) -> list[dict]:
    out = []
    for a in alerts:
        d = expected_dir(a.rule, a.level)
        row = {"ts": a.ts.isoformat(timespec="seconds"), "symbol": a.symbol, "rule": a.rule,
               "level": a.level, "price": a.price, "dir": d}
        end = book.last_time(a.symbol, a.ts.date())
        for h in HORIZONS:
            t = a.ts + timedelta(minutes=h)
            px = book.close_at(a.symbol, t) if end and t <= end + timedelta(minutes=1) else None
            row[f"ret{h}"] = (px / a.price - 1) if px and a.price else None
        w = book.window(a.symbol, a.ts, a.ts + timedelta(minutes=MFE_WINDOW))
        if w and a.price:
            hi, lo = max(b[1] for b in w), min(b[2] for b in w)
            up, down = hi / a.price - 1, lo / a.price - 1
            if d >= 0:
                row["mfe15"], row["mae15"] = up, down
            else:  # 下落を期待する通知は、下げ幅が「伸び」
                row["mfe15"], row["mae15"] = -down, -up
        else:
            row["mfe15"] = row["mae15"] = None
        out.append(row)
    return out


def summarize(rows: list[dict]) -> list[dict]:
    """ルール×レベルごとの件数・当たり率・平均リターン（期待方向に合わせた符号）。"""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["rule"], r["level"])].append(r)
    out = []
    for (rule, level), rs in sorted(groups.items()):
        d = rs[0]["dir"]
        s = {"rule": rule, "level": level, "dir": {1: "上", -1: "下", 0: "-"}[d], "n": len(rs)}
        for h in (5, 15, 30):
            # 30分で±30%超はデータ不整合の可能性が高いので集計から外す
            vals = [r[f"ret{h}"] for r in rs if r[f"ret{h}"] is not None and abs(r[f"ret{h}"]) <= OUTLIER]
            sign = d if d else 1
            s[f"hit{h}"] = (sum(1 for v in vals if v * sign > 0) / len(vals)) if (vals and d) else None
            s[f"avg{h}"] = (sum(v * sign for v in vals) / len(vals)) if vals else None
            s[f"med{h}"] = (sorted(v * sign for v in vals)[len(vals) // 2]) if vals else None
        for k in ("mfe15", "mae15"):
            vals = [r[k] for r in rs if r[k] is not None and abs(r[k]) <= OUTLIER]
            s[k] = sum(vals) / len(vals) if vals else None
        out.append(s)
    return out


def format_summary(summary: list[dict], min_n: int = 20) -> str:
    def pct(v, signed=True):
        return "-" if v is None else (f"{v:+.2%}" if signed else f"{v:.0%}")

    lines = ["ルール レベル        方向   件数  当たり15分 当たり30分  平均15分 中央15分  平均30分 中央30分  伸び15分 逆行15分"]
    for s in summary:
        if s["n"] < min_n:
            continue
        lines.append(
            f"{s['rule']:<5} {s['level']:<12} {s['dir']:^3} {s['n']:>6}  "
            f"{pct(s['hit15'], False):>9} {pct(s['hit30'], False):>9}  "
            f"{pct(s['avg15']):>8} {pct(s['med15']):>8}  {pct(s['avg30']):>8} {pct(s['med30']):>8}  "
            f"{pct(s['mfe15']):>8} {pct(s['mae15']):>8}")
    lines.append(f"※件数{min_n}件未満の行は省略（CSVには全行あり）。平均・中央値は「期待した方向に動いたらプラス」。"
                 "方向「-」（R10など）は上がればプラス。±30%超のリターンはデータ不整合として除外。")
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ---- ライブ記録（alerts_YYYYMMDD.csv / bars_YYYYMMDD.csv）の読み込み ----

def load_live_day(data_dir: Path, day: str) -> tuple[list[AlertRow], PriceBook]:
    book = PriceBook()
    alerts: list[AlertRow] = []
    bp, ap = data_dir / f"bars_{day}.csv", data_dir / f"alerts_{day}.csv"
    if bp.exists():
        with open(bp, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                book.add(r["symbol"], datetime.fromisoformat(r["start"]),
                         float(r["high"]), float(r["low"]), float(r["close"]))
    if ap.exists():
        with open(ap, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                alerts.append(AlertRow(datetime.fromisoformat(r["ts"]), r["symbol"], r["rule"],
                                       r["level"], float(r["price"])))
    book.freeze()
    return alerts, book


def main():
    from .config import load_config

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--date", help="YYYYMMDD（省略時は今日）")
    ap.add_argument("--all", action="store_true", help="data_dir の全日を合算")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.all:
        days = sorted(p.stem.split("_")[1] for p in cfg.data_dir.glob("alerts_*.csv"))
        tag = "all"
    else:
        days = [args.date or datetime.now().strftime("%Y%m%d")]
        tag = days[0]
    rows = []
    for d in days:
        alerts, book = load_live_day(cfg.data_dir, d)
        rows += evaluate(alerts, book)
    if not rows:
        print("評価する通知がありません（alerts_*.csv を確認してください）")
        return
    summary = summarize(rows)
    write_csv(cfg.data_dir / f"eval_{tag}.csv", rows)
    write_csv(cfg.data_dir / f"evalsum_{tag}.csv", summary)
    print(f"対象 {len(days)}日 / 通知 {len(rows)}件\n")
    print(format_summary(summary))
    print(f"\n保存: {cfg.data_dir / f'evalsum_{tag}.csv'}")


if __name__ == "__main__":
    main()
