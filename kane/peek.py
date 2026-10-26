"""監視中の Excel シート（スキャン・固定）から、指定銘柄の行をそのまま表示する診断ツール。

    py -3.11 -m kane.peek 9656 8123 3224

A列のコード・各列の数式（RssMarket の銘柄コードと項目名）・いまの値を並べて出す。
「行がずれていないか」「項目名が正しいか」「値が別銘柄のものになっていないか」を目で確かめる。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .rss import SCAN_SHEET, WATCH_SHEET, ExcelRss, com_retry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="+")
    ap.add_argument("--config", default="config.toml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    wb = Path(cfg.rss.workbook)
    rss = ExcelRss(cfg.rss, wb if wb.is_absolute() else cfg.base_dir / wb)
    rss.connect()
    for name in (WATCH_SHEET, SCAN_SHEET):
        ws = com_retry(rss._sheet, name)
        last_row = com_retry(lambda: ws.Cells(ws.Rows.Count, 1).End(-4162).Row)  # xlUp
        last_col = com_retry(lambda: ws.Cells(1, ws.Columns.Count).End(-4159).Column)  # xlToLeft
        header = com_retry(lambda: ws.Range(ws.Cells(1, 1), ws.Cells(1, last_col)).Value)[0]
        col_a = com_retry(lambda: ws.Range(ws.Cells(1, 1), ws.Cells(last_row, 1)).Value)
        codes_in_sheet = [str(r[0]).strip() if r[0] is not None else "" for r in col_a]
        print(f"\n=== シート {name}：{last_row - 1}行 × {last_col - 1}項目 ===")
        print("  項目:", [h for h in header[1:]])
        for c in args.codes:
            # Excel が数値にしてしまったコードにも対応（9656 → 9656.0）
            idx = next((i for i, v in enumerate(codes_in_sheet) if v == c or v == f"{c}.0"), None)
            if idx is None:
                print(f"  {c}: このシートに無い")
                continue
            row = idx + 1
            vals = com_retry(lambda: ws.Range(ws.Cells(row, 1), ws.Cells(row, last_col)).Value)[0]
            forms = com_retry(lambda: ws.Range(ws.Cells(row, 1), ws.Cells(row, last_col)).Formula)[0]
            print(f"  {c}: Excel {row}行目  前後のA列 = {codes_in_sheet[max(0, idx - 2):idx + 3]}")
            for h, f, v in zip(header, forms, vals):
                print(f"      {str(h):14s} {str(v):>16s}   {f}")


if __name__ == "__main__":
    main()
