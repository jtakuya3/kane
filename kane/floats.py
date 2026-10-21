"""symbols.csv の浮動株・発行済株式数の一覧を表示する。--live を付けると楽天RSSから今日の出来高を読んで回転率も出す。

    py -3.11 -m kane.floats          # 一覧だけ
    py -3.11 -m kane.floats --live   # 今日の出来高・回転率つき（MS2 ログイン＋Excel RSS接続が必要）
"""
import argparse
import html
import os
import sys
import time
from datetime import datetime
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
    ap.add_argument("--no-open", action="store_true", help="HTML をブラウザで開かない")
    args = ap.parse_args()
    cfg = load_config(args.config)
    measured = datetime.now()
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
    if live:
        out = write_html(cfg, live, measured)
        print(f"HTML: {out}")
        if not args.no_open and sys.platform.startswith("win"):
            os.startfile(out)  # noqa: S606


FLOAT_HI, ISSUED_HI = 0.45, 0.90  # ハイライトの水準


def write_html(cfg, live: dict, measured: datetime) -> Path:
    """計測時刻つきの一覧を HTML に書く。浮動株回転率 45% 以上・発行済比 90% 以上を強調。"""
    rows = []
    for s in cfg.symbols:
        v = live.get(s.code) or {}
        vol = v.get("volume")
        ft = (vol / s.float_shares) if vol is not None and s.float_shares else None
        it = (vol / s.issued_shares) if vol is not None and s.issued_shares else None
        chg = (v["price"] / v["prev_close"] - 1) if v.get("price") and v.get("prev_close") else None
        rows.append((s, v, vol, ft, it, chg))
    rows.sort(key=lambda r: -(r[3] if r[3] is not None else -1))

    def td(x, cls=""):
        return f"<td class='{cls}'>{x}</td>"

    def pct(x, d=0):
        return "-" if x is None else f"{x * 100:.{d}f}%"

    body = []
    for s, v, vol, ft, it, chg in rows:
        cls = []
        if ft is not None and ft >= FLOAT_HI:
            cls.append("hi-float")
        if it is not None and it >= ISSUED_HI:
            cls.append("hi-issued")
        ft_cls = "warn" if ft is not None and ft >= 0.30 else ("note" if ft is not None and ft >= 0.13 else "")
        chg_cls = "up" if chg is not None and chg > 0 else ("down" if chg is not None and chg < 0 else "")
        body.append(
            f"<tr class='{' '.join(cls)}'>" + td(s.code) + td(html.escape(s.name)) + td(html.escape(s.group))
            + td(f"{s.float_shares:,.0f}" if s.float_shares else "-", "num")
            + td(f"{s.issued_shares:,.0f}" if s.issued_shares else "-", "num")
            + td(pct(s.float_shares / s.issued_shares) if s.float_shares and s.issued_shares else "-", "num")
            + td(LOAN.get(s.loan, s.loan))
            + td(f"{v['price']:,.0f}" if v.get("price") else "-", "num")
            + td(pct(chg, 1), f"num {chg_cls}")
            + td(f"{vol:,.0f}" if vol is not None else "(取得できず)", "num")
            + td(pct(ft), f"num {ft_cls}") + td(pct(it, 1), "num")
            + td(f"{v['value'] * cfg.rss.value_unit / 1e8:,.1f}億" if v.get("value") else "-", "num")
            + "</tr>")
    doc = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>浮動株回転率 {measured:%Y-%m-%d %H:%M}</title>
<style>
body{{font-family:"Yu Gothic UI","Meiryo",sans-serif;margin:16px;background:#fff;color:#222}}
h1{{font-size:18px;margin:0 0 4px}} .meta{{color:#666;font-size:13px;margin-bottom:10px}}
table{{border-collapse:collapse;font-size:13px}} th,td{{border:1px solid #ddd;padding:4px 8px;white-space:nowrap}}
th{{background:#f3f3f3;position:sticky;top:0}} td.num{{text-align:right}}
tr.hi-float td{{background:#fff3b0}} tr.hi-issued td{{background:#ffd1d1}} tr.hi-float.hi-issued td{{background:#ffb3b3}}
td.warn{{color:#c62828;font-weight:bold}} td.note{{color:#ef6c00;font-weight:bold}}
td.up{{color:#c62828}} td.down{{color:#1565c0}}
.legend span{{display:inline-block;padding:2px 8px;margin-right:8px;border:1px solid #ccc}}
</style></head><body>
<h1>浮動株回転率（今日の出来高 ÷ 浮動株）</h1>
<div class="meta">計測時刻 <b>{measured:%Y-%m-%d %H:%M:%S}</b>（楽天RSS の値。出来高は当日累計）　
<span class="legend"><span style="background:#fff3b0">浮動株回転率 {FLOAT_HI:.0%} 以上</span><span style="background:#ffd1d1">発行済比 {ISSUED_HI:.0%} 以上</span>
<span style="color:#ef6c00;font-weight:bold">13%以上＝大きく上げた日の高値の中央値</span> <span style="color:#c62828;font-weight:bold">30%以上＝利確の目安</span></span></div>
<table><thead><tr><th>コード</th><th>銘柄</th><th>区分</th><th>浮動株</th><th>発行済</th><th>浮動比</th><th>貸借</th>
<th>現在値</th><th>前日比</th><th>出来高</th><th>浮動株回転率</th><th>発行済比</th><th>売買代金</th></tr></thead>
<tbody>{''.join(body)}</tbody></table>
<p class="meta">浮動株は推定を含む（大株主からの逆算）。IPO は公開株数＝浮動株。回転率の目安は kane.float_study（12〜6月・14銘柄）の検証値。</p>
</body></html>"""
    out_dir = cfg.data_dir / "floats"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"floats_{measured:%Y%m%d_%H%M}.html"
    out.write_text(doc, encoding="utf-8")
    (out_dir / "latest.html").write_text(doc, encoding="utf-8")
    return out


if __name__ == "__main__":
    main()
