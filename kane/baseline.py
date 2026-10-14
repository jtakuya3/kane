"""RVOL（相対出来高）の基準データを作る。

    # 平均日出来高（過去60営業日）：楽天RSSの日足（RssChart）から作り data_dir/baseline.csv に保存
    python -m kane.baseline daily            # 固定銘柄＋universe.csv の全銘柄
    python -m kane.baseline daily --check    # 1銘柄だけ取得して、RssChart の返す表を表示

    # 時刻ごとの出来高の配分カーブ：手元の5分足データから data_dir/volume_profile.csv を作る
    python -m kane.baseline profile "C:/Users/takuy/Downloads/_backtest_data/intraday_agg*.parquet"

毎朝、寄り付き前に daily を1回実行する（または前日の夜）。profile は一度作れば十分。
"""
from __future__ import annotations

import argparse
import csv
import glob
import time
from datetime import date
from pathlib import Path

from .config import load_config
from .rss import ExcelRss, load_universe, num

SHEET = "kane_baseline"
BLOCK = 12  # 1銘柄ぶんの表の列幅


def chart_formula(code: str, bars: int, suffix: str) -> str:
    return f'=RssChart(,"{code}{suffix}","D",{bars})'


def parse_chart(table, today: date | None = None) -> list[float]:
    """RssChart の表（ヘッダー行つき）から日ごとの出来高を取り出す（今日の行は除く）。"""
    rows = [list(r) for r in table if r]
    hi = next((i for i, r in enumerate(rows) if any(str(c).strip() == "出来高" for c in r)), None)
    if hi is None:
        return []
    header = [str(c).strip() for c in rows[hi]]
    vi = header.index("出来高")
    di = next((i for i, h in enumerate(header) if h in ("日付", "年月日")), None)
    today_s = (today or date.today()).strftime("%Y/%m/%d")
    vols = []
    for r in rows[hi + 1:]:
        if vi >= len(r):
            continue
        if di is not None and str(r[di]).replace("-", "/").startswith(today_s):
            continue
        v = num(r[vi])
        if v is not None:
            vols.append(v)
    return vols


def fetch_daily(cfg, codes: list[str], bars: int = 61, batch: int = 40, wait: float = 15.0) -> dict:
    """RssChart を銘柄ごとに横に並べて書き込み、値が出そろったら読む（batch 銘柄ずつ）。"""
    rss = ExcelRss(cfg.rss, Path(cfg.rss.workbook) if Path(cfg.rss.workbook).is_absolute()
                   else cfg.base_dir / cfg.rss.workbook)
    rss.connect()
    ws = rss._sheet(SHEET)
    out = {}
    for k in range(0, len(codes), batch):
        part = codes[k:k + batch]
        ws.Cells.Clear()
        for j, c in enumerate(part):
            ws.Cells(1, 1 + j * BLOCK).Formula = chart_formula(c, bars, cfg.rss.code_suffix)
        t0 = time.time()
        pending = set(part)
        while pending and time.time() - t0 < wait:
            time.sleep(1.0)
            for j, c in enumerate(part):
                if c not in pending:
                    continue
                rng = ws.Range(ws.Cells(1, 1 + j * BLOCK), ws.Cells(bars + 3, (j + 1) * BLOCK))
                vols = parse_chart(rng.Value)
                if len(vols) >= 20:
                    out[c] = vols[-60:]
                    pending.discard(c)
        print(f"  {min(k + batch, len(codes))}/{len(codes)} 銘柄（取得できなかった {len(pending)}銘柄）")
    ws.Cells.Clear()
    return out


def write_baseline(path: Path, vols: dict):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "avg_vol", "days", "updated"])
        for c, v in sorted(vols.items()):
            w.writerow([c, round(sum(v) / len(v)), len(v), date.today().isoformat()])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["daily", "profile"])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)

    if args.cmd == "profile":
        from .backtest import bar_minutes, load_bars, volume_profile_from_bars

        paths = sorted({p for pat in args.paths for p in glob.glob(pat)}) or args.paths
        bars = load_bars(paths, "bars", {})
        prof = volume_profile_from_bars(bars, bar_minutes(bars))
        out = cfg.data_dir / "volume_profile.csv"
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["minute", "frac"])
            w.writerows(prof)
        marks = {5: "9:05", 30: "9:30", 60: "10:00", 150: "11:30", 270: "13:30", 360: "15:00"}
        for m, f_ in prof:
            if m in marks:
                print(f"  {marks[m]} までに 1日の出来高の {f_:.0%}")
        print(f"保存: {out}")
        return

    codes = [s.code for s in cfg.symbols]
    codes += [s.code for s in load_universe(cfg.base_dir / cfg.rss.universe_csv, set(codes), cfg.rss.max_scan)]
    if args.check:
        rss = ExcelRss(cfg.rss, Path(cfg.rss.workbook) if Path(cfg.rss.workbook).is_absolute()
                       else cfg.base_dir / cfg.rss.workbook)
        rss.connect()
        ws = rss._sheet(SHEET)
        ws.Cells.Clear()
        ws.Cells(1, 1).Formula = chart_formula(codes[0], 61, cfg.rss.code_suffix)
        print(f"{codes[0]} の RssChart を書き込みました。10秒待って先頭を表示します…")
        time.sleep(10)
        table = ws.Range(ws.Cells(1, 1), ws.Cells(6, BLOCK)).Value
        for r in table:
            print("  ", r)
        full = ws.Range(ws.Cells(1, 1), ws.Cells(64, BLOCK)).Value
        vols = parse_chart(full)
        print(f"出来高 {len(vols)}日分を取得" + (f"（平均 {sum(vols) / len(vols):,.0f}株）" if vols else
              "：取れていません。上の表を送ってください"))
        return
    print(f"{len(codes)}銘柄の日足を取得します…")
    vols = fetch_daily(cfg, codes)
    out = cfg.data_dir / "baseline.csv"
    write_baseline(out, vols)
    print(f"保存: {out}（{len(vols)}/{len(codes)}銘柄）")


if __name__ == "__main__":
    main()
