"""JPXの上場銘柄一覧（data_j.xls）からスキャン用の universe.csv を作る。

    python -m kane.universe C:/Users/takuy/Downloads/data_j.xls --market グロース --market スタンダード

data_j.xls は JPX「東証上場銘柄一覧」からダウンロードする。読み込みには Excel（COM）を使う。
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

EXCLUDE_WORDS = ("ETF", "ETN", "REIT", "PRO Market", "出資証券", "ファンド")


def filter_rows(rows: list[list], markets: list[str]) -> list[tuple[str, str]]:
    """ヘッダー付きの表から（コード, 銘柄名）を市場で絞り込む。"""
    header = [str(h).strip() for h in rows[0]]
    ci, ni, mi = header.index("コード"), header.index("銘柄名"), header.index("市場・商品区分")
    out = []
    for r in rows[1:]:
        market = str(r[mi] or "")
        if any(w in market for w in EXCLUDE_WORDS):
            continue
        if markets and not any(m in market for m in markets):
            continue
        code = r[ci]
        code = str(int(code)) if isinstance(code, float) else str(code).strip()
        out.append((code, str(r[ni]).strip()))
    return out


def read_xls(path: Path) -> list[list]:
    import win32com.client

    xl = win32com.client.DispatchEx("Excel.Application")
    xl.Visible = False
    try:
        wb = xl.Workbooks.Open(str(path.resolve()), ReadOnly=True)
        rows = [list(r) for r in wb.Worksheets(1).UsedRange.Value]
        wb.Close(False)
        return rows
    finally:
        xl.Quit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xls", type=Path)
    ap.add_argument("--market", action="append", default=[], help="グロース / スタンダード / プライム（複数可）")
    ap.add_argument("--out", type=Path, default=Path("universe.csv"))
    args = ap.parse_args()
    pairs = filter_rows(read_xls(args.xls), args.market)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "name"])
        w.writerows(pairs)
    print(f"{args.out} に {len(pairs)} 銘柄を書き出しました")


if __name__ == "__main__":
    main()
