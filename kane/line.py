"""日々公表・増担の乖離ラインの株価を計算する（楽天RSSの日足から）。

    py -3.11 -m kane.line 4498 3909 6721 3143 4240 5133 4382

25日移動平均は当日の終値を含む（JPXの乖離率と同じ考え方）。当日の終値を C、前日までの24日の終値の合計を S24 とすると
    乖離 = C ÷ ((S24 + C) ÷ 25) − 1   →   乖離が k になる株価 C = (1+k)·S24 ÷ (25 − (1+k))
引け後に実行すると「次の営業日のライン」、取引時間中に実行すると「今日のライン」を出す。
翌々日のラインは、次の営業日の終値が「今日と同じ」「30%ライン」「−10%」だった場合の3通りで出す。
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from .baseline import BLOCK, SHEET, chart_formula, parse_chart_rows
from .config import load_config
from .rss import ExcelRss, com_retry

LEVELS = [(0.30, "30%（日々公表・増担の乖離基準）"), (0.20, "20%（1日回転率基準・IPO）"), (0.15, "15%（規制解除の基準）")]


def line(s24: float, k: float) -> float:
    return (1 + k) * s24 / (25 - (1 + k))


def analyze(closes: list[float]) -> dict:
    """closes：古い順の終値（最低25本）。"""
    c = closes[-25:]
    ma = sum(c) / 25
    dev = c[-1] / ma - 1
    streak = 0
    for i in range(len(closes) - 1, 23, -1):  # 乖離30%以上の連続日数
        m = sum(closes[i - 24:i + 1]) / 25
        if closes[i] / m - 1 >= 0.30:
            streak += 1
        else:
            break
    s24 = sum(closes[-24:])  # 次の営業日から見た「前日までの24日」
    nxt = {k: line(s24, k) for k, _ in LEVELS}
    after = {}
    for name, tomorrow in (("今日と同じ", closes[-1]), ("30%ライン", nxt[0.30]), ("−10%", closes[-1] * 0.9)):
        s = sum(closes[-23:]) + tomorrow
        after[name] = (tomorrow, line(s, 0.30))
    return {"close": c[-1], "ma25": ma, "dev": dev, "streak": streak, "next": nxt, "after": after}


def fmt(code: str, r: dict) -> str:
    out = [f"■ {code}  終値 {r['close']:,.0f}円  25日平均 {r['ma25']:,.0f}円  乖離 {r['dev']:+.1%}"
           f"  （乖離30%以上の連続 {r['streak']}日）"]
    for k, name in LEVELS:
        p = r["next"][k]
        out.append(f"   次の営業日 乖離{name}：終値 {p:,.0f}円 {'以上' if k >= 0.2 else '未満で達成'}"
                   f"（今日の終値から {p / r['close'] - 1:+.1%}）")
    out.append("   翌々日の30%ライン：" + " / ".join(
        f"次の日が{n}（{t:,.0f}円）なら {l:,.0f}円" for n, (t, l) in r["after"].items()))
    return "\n".join(out)


def fetch_closes(cfg, codes: list[str], bars: int = 40, wait: float = 60.0) -> dict:
    rss = ExcelRss(cfg.rss, Path(cfg.rss.workbook) if Path(cfg.rss.workbook).is_absolute()
                   else cfg.base_dir / cfg.rss.workbook)
    rss.connect()
    ws = com_retry(rss._sheet, SHEET)
    com_retry(lambda: ws.Cells.Clear())
    for j, c in enumerate(codes):
        def put(j=j, c=c):
            ws.Cells(1, 1 + j * BLOCK).Formula = chart_formula(c, bars, cfg.rss.code_suffix)
        com_retry(put)
    out, t0 = {}, time.time()
    while len(out) < len(codes) and time.time() - t0 < wait:
        time.sleep(1.0)
        table = com_retry(lambda: ws.Range(ws.Cells(1, 1), ws.Cells(bars + 3, len(codes) * BLOCK)).Value)
        for j, c in enumerate(codes):
            if c in out:
                continue
            rows = parse_chart_rows([r[j * BLOCK:(j + 1) * BLOCK] for r in table], column="終値")
            if len(rows) >= 26:
                out[c] = [v for _, v in rows]
    com_retry(lambda: ws.Cells.Clear())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="+")
    ap.add_argument("--config", default="config.toml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    data = fetch_closes(cfg, args.codes)
    for c in args.codes:
        print(fmt(c, analyze(data[c])) if c in data else f"■ {c}：日足が取れませんでした")
        print()
    print("※取引時間中に実行すると、今日の途中の値は使わず「今日のライン」を出す。引け後なら次の営業日のライン。")


if __name__ == "__main__":
    main()
