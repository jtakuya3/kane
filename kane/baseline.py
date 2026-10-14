"""RVOL（相対出来高）の基準データを作る。

    # 平均日出来高（過去60営業日）と今年の最大日出来高：楽天RSSの日足（RssChart）から作り data_dir/baseline.csv に保存
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
from datetime import date, datetime
from datetime import time as dtime
from pathlib import Path

from .config import load_config
from .rss import ExcelRss, com_retry, load_universe, num

SHEET = "kane_baseline"
BLOCK = 12  # 1銘柄ぶんの表の列幅


def chart_formula(code: str, bars: int, suffix: str) -> str:
    return f'=RssChart(,"{code}{suffix}","D",{bars})'


def parse_chart(table, today: date | None = None) -> list[float]:
    """RssChart の表（ヘッダー行つき）から日ごとの出来高を取り出す（今日の行は除く）。"""
    return [v for _, v in parse_chart_rows(table, today)]


def parse_chart_rows(table, today: date | None = None) -> list[tuple[str, float]]:
    """RssChart の表から（日付 YYYY/MM/DD, 出来高）を古い順に取り出す（今日の行は除く）。"""
    rows = [list(r) for r in table if r]
    hi = next((i for i, r in enumerate(rows) if any(str(c).strip() == "出来高" for c in r)), None)
    if hi is None:
        return []
    header = [str(c).strip() for c in rows[hi]]
    vi = header.index("出来高")
    di = next((i for i, h in enumerate(header) if h in ("日付", "年月日")), None)
    if today is None:
        now = datetime.now()
        # 取引時間中は今日の足が途中なので除く（大引け後に実行したときは今日も含める）
        today = now.date() if now.time() < dtime(15, 30) else None
    today_s = today.strftime("%Y/%m/%d") if today else "-"
    out = []
    for r in rows[hi + 1:]:
        if vi >= len(r):
            continue
        d = str(r[di]).replace("-", "/")[:10] if di is not None else ""
        if d.startswith(today_s):
            continue
        v = num(r[vi])
        if v is not None:
            out.append((d, v))
    return sorted(out)  # 日付順（新しい順で返る場合にそなえる）


MIN_DAYS = 5  # 上場まもない銘柄（IPO）も、5日分あれば平均を出す
BARS = 250  # 約1年分（平均出来高は直近60日、年初来の最大出来高は今年の分から計算）


def fetch_daily(cfg, codes: list[str], bars: int = BARS, batch: int = 40, wait: float = 90.0,
                on_batch=None, stall: float = 15.0) -> dict:
    """RssChart を銘柄ごとに横に並べて書き込み、値が出そろったら読む（batch 銘柄ずつ）。
    Excelが計算中で呼び出しを拒否したときは待ってやり直す。on_batch(out) で途中経過を保存できる。"""
    rss = ExcelRss(cfg.rss, Path(cfg.rss.workbook) if Path(cfg.rss.workbook).is_absolute()
                   else cfg.base_dir / cfg.rss.workbook)
    rss.connect()
    ws = com_retry(rss._sheet, SHEET)
    out = {}
    t_all = time.time()
    for k in range(0, len(codes), batch):
        part = codes[k:k + batch]
        com_retry(lambda: ws.Cells.Clear())
        for j, c in enumerate(part):
            def put(j=j, c=c):
                ws.Cells(1, 1 + j * BLOCK).Formula = chart_formula(c, bars, cfg.rss.code_suffix)
            com_retry(put)
        t0 = last = time.time()
        pending = set(part)
        while pending and time.time() - t0 < wait:
            if len(pending) < len(part) and time.time() - last > stall:
                break  # 他の銘柄は取れたのに、残りが stall 秒届かない（上場廃止・コード違いなど）→ 先へ進む
            time.sleep(1.0)
            # 1回でまとめて読む（Excelへの呼び出し回数を減らす）
            table = com_retry(lambda: ws.Range(ws.Cells(1, 1), ws.Cells(bars + 3, len(part) * BLOCK)).Value)
            for j, c in enumerate(part):
                if c not in pending:
                    continue
                rows = parse_chart_rows([r[j * BLOCK:(j + 1) * BLOCK] for r in table])
                if len(rows) >= MIN_DAYS:
                    out[c] = rows
                    pending.discard(c)
                    last = time.time()
        done = min(k + batch, len(codes))
        el = time.time() - t_all
        print(f"  {done}/{len(codes)} 銘柄（この回で取れなかった {len(pending)}銘柄）"
              f" 経過{el / 60:.0f}分 残り約{el / done * (len(codes) - done) / 60:.0f}分")
        if on_batch:
            on_batch(out)
    com_retry(lambda: ws.Cells.Clear())
    return out


def summarize_rows(rows: list[tuple[str, float]], year: int | None = None) -> dict:
    """平均日出来高（直近60日）と、今年の最大日出来高とその日付。"""
    vols = [v for _, v in rows][-60:]
    y = str(year or date.today().year)
    this_year = [(v, d) for d, v in rows if d.startswith(y)]
    mx = max(this_year) if this_year else (None, "")
    return {"avg_vol": round(sum(vols) / len(vols)) if vols else None, "days": len(vols),
            "ytd_max_vol": round(mx[0]) if mx[0] else None, "ytd_max_date": mx[1]}


def write_baseline(path: Path, data: dict):
    """今回取れた銘柄を書き込む。取れなかった銘柄は、前回の baseline.csv の値を残す。"""
    keep = {}
    if path.exists():
        with open(path, encoding="utf-8-sig", newline="") as f:
            keep = {r["code"]: r for r in csv.DictReader(f) if r.get("code") and r["code"] not in data}
    cols = ["code", "avg_vol", "days", "ytd_max_vol", "ytd_max_date", "updated"]
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for c, rows in sorted(data.items()):
            r = summarize_rows(rows)
            w.writerow([c, r["avg_vol"], r["days"], r["ytd_max_vol"], r["ytd_max_date"], date.today().isoformat()])
        for c, r in sorted(keep.items()):
            w.writerow([r.get(k, "") for k in cols])
    tmp.replace(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["daily", "profile"])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true", help="今日すでに取れた銘柄も取り直す")
    ap.add_argument("--batch", type=int, default=40, help="一度に書き込む RssChart の数")
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
    # 平均出来高は universe.csv の全銘柄ぶん取る（max_scan に関係なく）
    codes += [s.code for s in load_universe(cfg.base_dir / cfg.rss.universe_csv, set(codes), 100_000)]
    if args.check:
        rss = ExcelRss(cfg.rss, Path(cfg.rss.workbook) if Path(cfg.rss.workbook).is_absolute()
                       else cfg.base_dir / cfg.rss.workbook)
        rss.connect()
        ws = rss._sheet(SHEET)
        ws.Cells.Clear()
        ws.Cells(1, 1).Formula = chart_formula(codes[0], BARS, cfg.rss.code_suffix)
        print(f"{codes[0]} の RssChart を書き込みました。値が入るまで最大90秒待ちます…")
        vols, t0 = [], time.time()
        while time.time() - t0 < 90:
            time.sleep(5)
            full = ws.Range(ws.Cells(1, 1), ws.Cells(BARS + 3, BLOCK)).Value
            vols = parse_chart(full)
            print(f"  {time.time() - t0:.0f}秒: {str(full[0][0])[-30:]}  出来高 {len(vols)}日分")
            if len(vols) >= 20:
                break
        for r in ws.Range(ws.Cells(1, 1), ws.Cells(5, BLOCK)).Value:
            print("  ", r)
        if vols:
            r = summarize_rows(parse_chart_rows(full))
            print(f"出来高 {len(vols)}日分を取得（直近60日の平均 {r['avg_vol']:,}株 / "
                  f"今年の最大 {r['ytd_max_vol'] or 0:,}株 {r['ytd_max_date']}）")
        else:
            print("出来高 0日分：取れていません。上の表を送ってください")
        return
    out = cfg.data_dir / "baseline.csv"
    if not args.force and out.exists():
        with open(out, encoding="utf-8-sig", newline="") as f:
            today = {r["code"] for r in csv.DictReader(f) if r.get("updated") == date.today().isoformat()}
        if today:
            print(f"今日すでに取れた {len(today)}銘柄は飛ばします（取り直すときは --force）")
        codes = [c for c in codes if c not in today]
    print(f"{len(codes)}銘柄の日足を取得します…（途中で止めても、取れた分は保存されます）")
    vols = fetch_daily(cfg, codes, batch=args.batch, on_batch=lambda d: write_baseline(out, d))
    write_baseline(out, vols)
    missing = [c for c in codes if c not in vols]
    miss_path = cfg.data_dir / "baseline_missing.csv"
    with open(miss_path, "w", encoding="utf-8", newline="") as f:
        f.write("code\n" + "".join(f"{c}\n" for c in missing))
    print(f"保存: {out}（{len(vols)}/{len(codes)}銘柄）")
    if missing:
        print(f"取れなかった {len(missing)}銘柄: {miss_path}（もう一度実行すると、その銘柄だけ取り直します）"
              f"\n  例: {' '.join(missing[:15])}")


if __name__ == "__main__":
    main()
