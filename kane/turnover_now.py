"""いま監視中の全銘柄（固定＋スキャン）で、出来高が発行済株式数の何回転かを出し、高値圏の銘柄を並べる。

    py -3.11 -m kane.turnover_now            # 発行済の30%以上回った銘柄
    py -3.11 -m kane.turnover_now --min 50   # 50%以上だけ

監視（kane 朝 監視）が動いている Excel のシートをそのまま読む。発行済株式数は
「時価総額（百万円）÷ 現在値」で出す（楽天RSSに発行済の項目が無いため）。symbols.csv に発行済があればそれを使う。
「引けまでの見込み」＝いまの出来高 ÷ この時刻までに普段出る割合（出来高の時間配分）。
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .config import load_config
from .rss import SCAN_SHEET, WATCH_SHEET, ExcelRss, com_retry, num


def read_sheet(rss: ExcelRss, name: str) -> list[dict]:
    ws = com_retry(rss._sheet, name)
    v = com_retry(lambda: ws.UsedRange.Value)
    if not v or len(v) < 2:
        return []
    head = [str(h).strip() if h is not None else "" for h in v[0]]
    out = []
    for row in v[1:]:
        d = dict(zip(head, row))
        code = d.get("code")
        if code is None:
            continue
        d["code"] = str(int(code)) if isinstance(code, float) else str(code).strip()
        out.append(d)
    return out


def analyse(rows: list[dict], issued: dict, names: dict, frac: float) -> list[dict]:
    out = []
    for d in rows:
        price, vol = num(d.get("現在値")), num(d.get("出来高"))
        if not price or not vol:
            continue
        sh = issued.get(d["code"])
        if not sh:
            cap = num(d.get("時価総額"))
            sh = cap * 1e6 / price if cap else None
        if not sh:
            continue
        hi, prev, ytd = num(d.get("高値")), num(d.get("前日終値")), num(d.get("年初来高値"))
        out.append({
            "code": d["code"], "name": names.get(d["code"], ""), "price": price,
            "chg": (price / prev - 1) * 100 if prev else None,
            "turn": vol / sh * 100, "proj": vol / sh * 100 / frac if frac else None,
            "from_hi": (price / hi - 1) * 100 if hi else None,
            "ytd_high": bool(ytd and price >= ytd * 0.995),
            "vol": vol, "issued": sh, "value_oku": price * vol / 1e8,
        })
    return out


def main():
    from .rules import vol_frac

    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=30.0, help="発行済に対する出来高の％（この値以上を表示）")
    ap.add_argument("--config", default="config.toml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    wb = Path(cfg.rss.workbook)
    rss = ExcelRss(cfg.rss, wb if wb.is_absolute() else cfg.base_dir / wb)
    rss.connect()
    rows = read_sheet(rss, WATCH_SHEET) + read_sheet(rss, SCAN_SHEET)
    issued = {s.code: s.issued_shares for s in cfg.symbols if s.issued_shares}
    names = {s.code: s.name for s in cfg.symbols}
    try:
        import csv
        with open(cfg.base_dir / cfg.rss.universe_csv, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                names.setdefault((r.get("code") or "").strip(), (r.get("name") or "").strip())
    except OSError:
        pass
    now = datetime.now()
    frac = max(vol_frac(now, cfg.rules.volume_profile), 0.03)
    res = [r for r in analyse(rows, issued, names, frac) if r["turn"] >= args.min or (r["proj"] or 0) >= 100]
    res.sort(key=lambda r: -r["turn"])
    print(f"{now:%H:%M:%S} 監視中 {len(rows)}銘柄のうち、発行済の{args.min:.0f}%以上回った（または引けまでに1回転の見込み）銘柄 {len(res)}件")
    print(f"（この時刻までに普段1日の出来高の {frac:.0%} が出る前提で、引けまでの見込みを計算）\n")
    print("コード  銘柄              現在値   前日比   発行済の回転  引けの見込み  高値から  年初来高値  売買代金")
    for r in res:
        chg = f"{r['chg']:+6.1f}%" if r["chg"] is not None else "     -"
        fh = f"{r['from_hi']:+5.1f}%" if r["from_hi"] is not None else "    -"
        proj = f"{r['proj']:6.0f}%" if r["proj"] is not None else "     -"
        mark = "  ★1回転" if r["turn"] >= 100 else ("  ◎見込み1回転" if (r["proj"] or 0) >= 100 else "")
        print(f"{r['code']:6s}{r['name'][:14]:14s} {r['price']:>8,.0f} {chg}   {r['turn']:7.0f}%      {proj}     {fh}    {'更新' if r['ytd_high'] else '  -'}   {r['value_oku']:6.1f}億{mark}")
    print("\n高値から 0% に近いほど当日高値圏。『更新』は年初来高値圏。監視に入っていない銘柄は出ない。")


if __name__ == "__main__":
    main()
