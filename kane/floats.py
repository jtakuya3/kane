"""symbols.csv の浮動株・発行済株式数の一覧を表示する。--live を付けると楽天RSSから今日の出来高を読んで回転率も出す。

    py -3.11 -m kane.floats          # 一覧だけ
    py -3.11 -m kane.floats --live   # 今日の出来高・回転率つき（MS2 ログイン＋Excel RSS接続が必要）
"""
import argparse
import time
from pathlib import Path

from .config import load_config

LOAN = {"1": "貸借", "0": "信用", "": "未確認"}
FIELDS = [("price", "現在値"), ("prev_close", "前日終値"), ("volume", "出来高"), ("value", "売買代金")]


def fetch_live(cfg, codes: list[str], wait: float = 20.0) -> dict:
    from .rss import ExcelRss, com_retry, num

    rss = ExcelRss(cfg.rss, Path(cfg.rss.workbook) if Path(cfg.rss.workbook).is_absolute()
                   else cfg.base_dir / cfg.rss.workbook)
    rss.connect()
    rss.setup("floats", codes, FIELDS)
    out, t0 = {}, time.time()
    while time.time() - t0 < wait:
        time.sleep(1.0)
        rows = rss.read("floats", len(codes), len(FIELDS))
        out = {}
        for c, r in zip(codes, rows):
            vals = {k: num(v) for (k, _), v in zip(FIELDS, r)}
            if vals.get("volume") is not None:
                out[c] = vals
        if len(out) == len(codes):
            break
    com_retry(lambda: rss._sheet("floats").Cells.Clear())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="楽天RSSから今日の出来高を読んで回転率を出す")
    ap.add_argument("--config", default="config.toml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    live = fetch_live(cfg, [s.code for s in cfg.symbols]) if args.live else {}
    head = f"{'コード':<6}{'銘柄':<16}{'浮動株':>12}{'発行済':>13}{'浮動比':>7}{'貸借':>5}"
    if live:
        head += f"{'現在値':>9}{'前日比':>8}{'出来高':>12}{'浮動株回転率':>10}{'発行済比':>8}{'売買代金':>9}"
    print(head)
    for s in cfg.symbols:
        f = f"{s.float_shares:,.0f}" if s.float_shares else "-"
        i = f"{s.issued_shares:,.0f}" if s.issued_shares else "-"
        r = f"{s.float_shares / s.issued_shares:.0%}" if s.float_shares and s.issued_shares else "-"
        line = f"{s.code:<6}{s.name:<16}{f:>12}{i:>13}{r:>7}{LOAN.get(s.loan, s.loan):>5}"
        v = live.get(s.code)
        if live:
            if v and v.get("volume") is not None:
                vol = v["volume"]
                chg = (v["price"] / v["prev_close"] - 1) if v.get("price") and v.get("prev_close") else None
                ft = f"{vol / s.float_shares:.0%}" if s.float_shares else "-"
                it = f"{vol / s.issued_shares:.1%}" if s.issued_shares else "-"
                val = f"{v['value'] * cfg.rss.value_unit / 1e8:,.1f}億" if v.get("value") else "-"
                line += (f"{v['price'] or 0:>9,.0f}{(f'{chg:+.1%}' if chg is not None else '-'):>8}{vol:>12,.0f}"
                         f"{ft:>10}{it:>8}{val:>9}")
            else:
                line += f"{'(取得できず)':>20}"
        print(line)
    print("※浮動株は推定を含む（大株主からの逆算）。IPOは公開株数＝浮動株。回転率30%＝検証で「買いは不利・利確の目安」、"
          "大きく上げた日の高値は回転率13%（中央値）の時点。")


if __name__ == "__main__":
    main()
