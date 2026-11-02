"""あるトレーダーが買ったタイミングで、テクニカル（RSI・RCI・乖離率・下落率・出来高）がどうだったかを並べる。

    py -3.11 -m kane.pro_study                 # 下の TRADES を楽天RSSの日足で調べる
    py -3.11 -m kane.pro_study --bars 900      # 日足の本数（古い取引まで届かないときに増やす）

各取引について「買う直前に確定していた日足」で指標を出す（夜・朝の注文はその日の寄りで買ったとみなす）。
最後に全取引の平均・中央値と、買ったあと（寄り値から）+1日・+5日・+20日の騰落を出す。
信用倍率の過去分は楽天RSSに無いので、ここでは出さない（週次の信用残は株探などで別に見る）。
"""
from __future__ import annotations

import argparse
import csv
import time
from datetime import date, datetime
from datetime import time as dtime
from pathlib import Path
from statistics import mean, median, pstdev

from .config import load_config
from .rss import ExcelRss, com_retry, num

# (コード, 銘柄, 投稿・購入の時刻, メモ)
TRADES = [
    ("4461", "第一工業製薬", "2026-11-02 06:58", "9730円で300株（寄り）"),
    ("4704", "トレンドマイクロ", "2026-10-09 11:56", "3億円"),
    ("4170", "Kaizen Platform", "2026-08-25 08:11", "4万株"),
    ("285A", "キオクシア", "2026-07-30 00:07", "1.9億円（決算跨ぎ）"),
    ("285A", "キオクシア", "2026-07-28 01:08", "買い増し 計7000株"),
    ("285A", "キオクシア", "2026-07-28 00:37", "1億円"),
    ("285A", "キオクシア", "2026-07-17 08:12", "2億円"),
    ("5621", "ヒューマンテクノロジーズ", "2026-05-20 07:50", "28万株 保有を発表"),
    ("3350", "メタプラネット", "2025-10-16 00:40", "1.7億円 40万株"),
    ("3350", "メタプラネット", "2025-06-08 23:39", "1641円で10万株"),
    ("7201", "日産自動車", "2024-11-01 05:50", "約2億円 再購入"),
    ("7201", "日産自動車", "2024-09-15 12:00", "大量購入（9月頃・日付不明）"),
    ("7003", "三井E&S", "2024-02-15 12:00", "約800円で10万株（2月頃・日付不明）"),
]

SHEET = "kane_prostudy"
BLOCK = 12


# ---------------- 指標 ----------------

def sma(xs, n):
    return mean(xs[-n:]) if len(xs) >= n else None


def rsi(closes, n=14):
    """Wilder の RSI。"""
    if len(closes) <= n:
        return None
    gains = [max(0.0, b - a) for a, b in zip(closes, closes[1:])]
    losses = [max(0.0, a - b) for a, b in zip(closes, closes[1:])]
    ag, al = mean(gains[:n]), mean(losses[:n])
    for g, l in zip(gains[n:], losses[n:]):
        ag = (ag * (n - 1) + g) / n
        al = (al * (n - 1) + l) / n
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)


def rci(closes, n=9):
    """RCI：日付の順位（新しい=1）と値段の順位（高い=1）の順位相関 ×100。+100 天井圏、−100 底値圏。"""
    if len(closes) < n:
        return None
    xs = closes[-n:]
    date_rank = list(range(n, 0, -1))  # 古い日ほど大きい順位
    order = sorted(range(n), key=lambda i: -xs[i])
    price_rank = [0.0] * n
    i = 0
    while i < n:  # 同値は平均順位
        j = i
        while j + 1 < n and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            price_rank[order[k]] = r
        i = j + 1
    d2 = sum((a - b) ** 2 for a, b in zip(date_rank, price_rank))
    return (1 - 6 * d2 / (n * (n * n - 1))) * 100


def down_streak(closes):
    k = 0
    for a, b in zip(reversed(closes[:-1]), reversed(closes[1:])):
        if b < a:
            k += 1
        else:
            break
    return k


def features(bars: list[dict]) -> dict:
    """bars（古い順、最後が「買う直前に確定した日」）から指標を出す。"""
    c = [b["close"] for b in bars]
    v = [b["volume"] for b in bars]
    last = c[-1]
    out = {"close": last}
    for n in (5, 25, 75):
        m = sma(c, n)
        out[f"dev{n}"] = (last / m - 1) * 100 if m else None
    m20 = sma(c, 20)
    sd = pstdev(c[-20:]) if len(c) >= 20 else None
    out["bb_sigma"] = (last - m20) / sd if m20 and sd else None
    out["rsi14"] = rsi(c, 14)
    out["rci9"] = rci(c, 9)
    out["rci26"] = rci(c, 26)
    for n in (1, 3, 5, 20):
        out[f"ret{n}"] = (last / c[-1 - n] - 1) * 100 if len(c) > n else None
    hi60 = max(b["high"] for b in bars[-60:])
    out["from_hi60"] = (last / hi60 - 1) * 100
    hi250 = max(b["high"] for b in bars[-250:])
    out["from_hi250"] = (last / hi250 - 1) * 100
    lo250 = min(b["low"] for b in bars[-250:])
    out["from_lo250"] = (last / lo250 - 1) * 100
    out["down_streak"] = down_streak(c)
    av20 = sma(v[:-1], 20)
    out["vol_x"] = v[-1] / av20 if av20 else None
    return out


def entry_index(dates: list[str], t: datetime) -> tuple[int, str]:
    """買った日足の位置と、値段の扱い（寄り／場中）。夜・朝の注文はその日（休みなら次の営業日）の寄り。"""
    if t.time() >= dtime(15, 30):
        target, how = t.date(), "翌営業日の寄り"
        key = target.strftime("%Y/%m/%d")
        idx = next((i for i, d in enumerate(dates) if d > key), None)
        return (idx if idx is not None else -1), how
    key = t.date().strftime("%Y/%m/%d")
    how = "寄り" if t.time() < dtime(9, 0) else "場中（終値で代用）"
    idx = next((i for i, d in enumerate(dates) if d >= key), None)
    if idx is not None and dates[idx] != key:
        how = "次の営業日の寄り"
    return (idx if idx is not None else -1), how


# ---------------- 楽天RSS の日足 ----------------

def parse_ohlcv(block) -> list[dict]:
    rows = [list(r) for r in block if r]
    hi = next((i for i, r in enumerate(rows) if any(str(x).strip() == "終値" for x in r)), None)
    if hi is None:
        return []
    h = [str(x).strip() for x in rows[hi]]
    ix = {k: h.index(k) for k in ("日付", "始値", "高値", "安値", "終値", "出来高") if k in h}
    out = []
    for r in rows[hi + 1:]:
        try:
            d = str(r[ix["日付"]]).replace("-", "/")[:10]
            o, hgh, low, cl = (num(r[ix[k]]) for k in ("始値", "高値", "安値", "終値"))
            vol = num(r[ix["出来高"]]) or 0.0
        except (KeyError, IndexError):
            continue
        if d and cl:
            out.append({"date": d, "open": o or cl, "high": hgh or cl, "low": low or cl, "close": cl, "volume": vol})
    return sorted(out, key=lambda b: b["date"])


def fetch(cfg, codes: list[str], bars: int, wait: float = 120.0) -> dict:
    rss = ExcelRss(cfg.rss, Path(cfg.rss.workbook) if Path(cfg.rss.workbook).is_absolute()
                   else cfg.base_dir / cfg.rss.workbook)
    rss.connect()
    ws = com_retry(rss._sheet, SHEET)
    com_retry(lambda: ws.Cells.Clear())
    for j, c in enumerate(codes):
        def put(j=j, c=c):
            ws.Cells(1, 1 + j * BLOCK).Formula = f'=RssChart(,"{c}{cfg.rss.code_suffix}","D",{bars})'
        com_retry(put)
    out, seen, t0 = {}, {}, time.time()
    while len(out) < len(codes) and time.time() - t0 < wait:
        time.sleep(2)
        table = com_retry(lambda: ws.Range(ws.Cells(1, 1), ws.Cells(bars + 3, len(codes) * BLOCK)).Value)
        for j, c in enumerate(codes):
            if c in out:
                continue
            rows = parse_ohlcv([r[j * BLOCK:(j + 1) * BLOCK] for r in table])
            if rows and seen.get(c) == len(rows):
                out[c] = rows
            seen[c] = len(rows)
        print(f"  {time.time() - t0:.0f}秒 取得 {len(out)}/{len(codes)}")
    com_retry(lambda: ws.Cells.Clear())
    return out


# ---------------- 集計 ----------------

COLS = [("rsi14", "RSI14", "{:.0f}"), ("rci9", "RCI9", "{:+.0f}"), ("rci26", "RCI26", "{:+.0f}"),
        ("dev5", "5日乖離", "{:+.1f}%"), ("dev25", "25日乖離", "{:+.1f}%"), ("dev75", "75日乖離", "{:+.1f}%"),
        ("bb_sigma", "BBσ", "{:+.1f}"), ("ret3", "3日騰落", "{:+.1f}%"), ("ret5", "5日騰落", "{:+.1f}%"),
        ("ret20", "20日騰落", "{:+.1f}%"), ("from_hi60", "60日高値から", "{:+.1f}%"),
        ("from_hi250", "1年高値から", "{:+.1f}%"), ("down_streak", "連続安", "{:.0f}日"),
        ("vol_x", "出来高倍率", "{:.1f}倍"), ("gap", "寄りの窓", "{:+.1f}%"),
        ("after1", "+1日", "{:+.1f}%"), ("after5", "+5日", "{:+.1f}%"), ("after20", "+20日", "{:+.1f}%")]


def fmt(v, f):
    return f.format(v) if v is not None else "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=800)
    ap.add_argument("--config", default="config.toml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    codes = sorted({c for c, *_ in TRADES})
    print(f"日足を取得中…（{len(codes)}銘柄 × {args.bars}本）")
    data = fetch(cfg, codes, args.bars)
    results = []
    for code, name, when, note in TRADES:
        bars = data.get(code) or []
        t = datetime.fromisoformat(when)
        if not bars:
            print(f"■ {code} {name} {when}：日足が取れません")
            continue
        dates = [b["date"] for b in bars]
        i, how = entry_index(dates, t)
        if i <= 30:
            print(f"■ {code} {name} {when}：日足が足りません（--bars を増やす）")
            continue
        f = features(bars[:i])  # 買う直前に確定していた日まで
        e = bars[i]
        price = e["open"] if "寄り" in how else e["close"]
        f["gap"] = (e["open"] / bars[i - 1]["close"] - 1) * 100
        for n in (1, 5, 20):
            f[f"after{n}"] = (bars[i + n]["close"] / price - 1) * 100 if i + n < len(bars) else None
        f.update({"code": code, "name": name, "when": when, "note": note, "day": e["date"], "how": how, "price": price})
        results.append(f)

    print()
    for r in results:
        print(f"■ {r['code']} {r['name']}  {r['when']}（{r['note']}）→ {r['day']} {r['how']} {r['price']:,.0f}円")
        print("   " + "  ".join(f"{lab} {fmt(r.get(k), f)}" for k, lab, f in COLS))
    if results:
        print("\n■ 全取引の中央値（平均）")
        for k, lab, f in COLS:
            xs = [r[k] for r in results if r.get(k) is not None]
            if xs:
                print(f"   {lab:10s} {fmt(median(xs), f):>9s}（{fmt(mean(xs), f)}）  n={len(xs)}")
        out = cfg.data_dir / "pro_study.csv"
        with open(out, "w", encoding="utf-8-sig", newline="") as fh:
            keys = ["code", "name", "when", "note", "day", "how", "price"] + [k for k, *_ in COLS]
            w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(results)
        print(f"\n保存: {out}")


if __name__ == "__main__":
    main()
