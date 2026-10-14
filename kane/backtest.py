"""過去データで判定を答え合わせする（バックテスト）。

    # まずファイルの中身（列名）を確認
    python -m kane.backtest --inspect "C:/Users/takuy/Downloads/_backtest_data/min1_xxx.parquet"

    # 1分足（parquet / csv）で実行。急騰・急落した日（前日比±5%以上動いた日）だけを対象にする
    python -m kane.backtest "C:/Users/takuy/Downloads/_backtest_data/min1*.parquet"

    # 歩み値（csv）から1分足を作って実行
    python -m kane.backtest --kind ticks "D:/tick/2026-03/*.csv"

列名が自動で見つからないときは --col time=日時 --col code=銘柄コード のように指定する。
元データは読むだけで、書き換えない。結果は data_dir/backtest_日時/ に保存する。
"""
from __future__ import annotations

import argparse
import glob
from datetime import datetime, timedelta
from pathlib import Path

from .config import RuleConfig, SymbolInfo, load_config
from .engine import Engine
from .evaluate import AlertRow, PriceBook, evaluate, format_summary, summarize, write_csv
from .models import Snapshot

CANDIDATES = {
    "time": ["datetime", "timestamp", "time", "date_time", "dt", "ts", "日時", "約定日時", "時刻"],
    "date": ["date", "日付", "trade_date"],
    "code": ["code", "symbol", "ticker", "sym", "securitiescode", "銘柄コード", "コード", "銘柄"],
    "open": ["open", "始値", "o"],
    "high": ["high", "高値", "h"],
    "low": ["low", "安値", "l"],
    "close": ["close", "終値", "c", "price", "現在値"],
    "volume": ["volume", "出来高", "vol", "v", "qty", "size", "約定数量"],
    "price": ["price", "約定値", "約定価格", "p", "現在値"],
}


def detect(columns: list[str], kind: str, override: dict) -> dict:
    """列名を推定する。戻り値は {役割: 実際の列名}。"""
    low = {c.lower().strip(): c for c in columns}
    need = ["code", "open", "high", "low", "close", "volume"] if kind == "bars" else ["code", "price", "volume"]
    out = {}
    for role in need + ["time", "date"]:
        if role in override:
            out[role] = override[role]
            continue
        for cand in CANDIDATES[role]:
            if cand in low and low[cand] not in out.values():
                out[role] = low[cand]
                break
    if "time" not in out and "date" not in out:
        raise SystemExit(f"時刻の列が見つかりません。--col time=列名 で指定してください。列: {columns}")
    missing = [r for r in need if r not in out]
    if missing:
        raise SystemExit(f"列が見つかりません: {missing}。--col 役割=列名 で指定してください。列: {columns}")
    return out


def _read(path: str, columns=None):
    import pandas as pd

    if path.lower().endswith(".parquet"):
        return pd.read_parquet(path, columns=columns)
    for enc in ("utf-8-sig", "cp932"):
        try:
            return pd.read_csv(path, usecols=columns, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"文字コードが読めません: {path}")


def _datetime(df, m):
    import pandas as pd

    if "time" in m and "date" in m and m["time"] != m["date"]:
        s = pd.to_datetime(df[m["date"]].astype(str) + " " + df[m["time"]].astype(str), errors="coerce")
    else:
        col = df[m.get("time", m.get("date"))]
        if pd.api.types.is_numeric_dtype(col):  # UNIX時間
            unit = "ms" if col.max() > 1e11 else "s"
            s = pd.to_datetime(col, unit=unit, utc=True)
        else:
            s = pd.to_datetime(col, errors="coerce")
    if getattr(s.dt, "tz", None) is not None:
        s = s.dt.tz_convert("Asia/Tokyo").dt.tz_localize(None)
    return s


def _from_min1_agg(df):
    """_backtest_data の min1*.parquet 形式：code(5桁), d(YYYYMMDD), min1(0時からの分),
    n(約定回数), pv(売買代金), vv(出来高)。四本値が無いので1分ごとのVWAP（pv÷vv）を株価として使う。"""
    import pandas as pd

    code = df["code"].astype(str).str.strip()
    code = code.where(code.str.len() != 5, code.str[:4])  # 5桁コードの末尾（チェック桁）を落とす
    dt = pd.to_datetime(df["d"].astype(str), format="%Y%m%d") + pd.to_timedelta(df["min1"], unit="m")
    px = df["pv"] / df["vv"]
    f = pd.DataFrame({"code": code, "dt": dt, "open": px, "high": px, "low": px, "close": px,
                      "volume": df["vv"]})
    return f[(df["vv"] > 0)].dropna(subset=["close"])


def load_bars(paths: list[str], kind: str, override: dict):
    """1分足の DataFrame（code, dt, open, high, low, close, volume）にそろえる。"""
    import pandas as pd

    frames = []
    for p in paths:
        df = _read(p)
        if {"code", "d", "min1", "pv", "vv"} <= set(df.columns) and not override:
            frames.append(_from_min1_agg(df))
            print(f"読み込み {Path(p).name}: {len(frames[-1]):,}本（1分集計形式）")
            continue
        m = detect(list(df.columns), kind, override)
        dt = _datetime(df, m)
        code = df[m["code"]].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        if kind == "bars":
            f = pd.DataFrame({"code": code, "dt": dt.dt.floor("min"), "open": df[m["open"]],
                              "high": df[m["high"]], "low": df[m["low"]], "close": df[m["close"]],
                              "volume": df[m["volume"]]})
        else:  # 歩み値 → 1分足
            t = pd.DataFrame({"code": code, "dt": dt.dt.floor("min"), "price": df[m["price"]],
                              "volume": df[m["volume"]]})
            f = t.groupby(["code", "dt"], sort=False).agg(
                open=("price", "first"), high=("price", "max"), low=("price", "min"),
                close=("price", "last"), volume=("volume", "sum")).reset_index()
        frames.append(f.dropna(subset=["dt", "close"]))
        print(f"読み込み {Path(p).name}: {len(f):,}本")
    bars = pd.concat(frames, ignore_index=True)
    bars = bars.groupby(["code", "dt"], sort=False).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum")).reset_index()
    return bars.sort_values(["dt", "code"]).reset_index(drop=True)


def day_table(bars):
    """銘柄×日の四本値と前日終値・年初来高値（データ内で計算）。"""
    d = bars.assign(day=bars["dt"].dt.date).groupby(["code", "day"]).agg(
        high=("high", "max"), low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum")).reset_index().sort_values(["code", "day"])
    d["prev_close"] = d.groupby("code")["close"].shift(1)
    d["year"] = [x.year for x in d["day"]]
    d["ytd_high"] = d.groupby(["code", "year"])["high"].transform(lambda s: s.shift(1).cummax())
    first_day = d.groupby("year")["day"].transform("min")
    # データが年初から揃っていない年は、年初来高値を使わない
    d.loc[[fd.month > 1 or fd.day > 10 for fd in first_day], "ytd_high"] = None
    return d


def run(bars, cfg_rules: RuleConfig, known: dict[str, SymbolInfo], min_day_change: float,
        codes: set[str] | None):
    days = day_table(bars)
    days["move"] = [max(h / p - 1, 1 - lo / p) if p == p and p else 0
                    for h, lo, p in zip(days["high"], days["low"], days["prev_close"])]
    sel = days[(days["move"] >= min_day_change) & days["prev_close"].notna()]
    if codes:
        sel = sel[sel["code"].isin(codes)]
    keys = set(zip(sel["code"], sel["day"]))
    info = {r.code: r for r in sel.itertuples()}  # 銘柄ごとの最新行（使わない）
    del info
    print(f"対象：{len(keys):,} 銘柄日（前日比±{min_day_change:.0%}以上動いた日）")

    infos = {c: known.get(c) or SymbolInfo(c, "", None) for c in sel["code"].unique()}
    engine = Engine(list(infos.values()), cfg_rules)
    meta = {(r.code, r.day): r for r in sel.itertuples()}
    book = PriceBook()
    alerts: list[AlertRow] = []
    b = bars.assign(day=bars["dt"].dt.date)
    b = b[[k in keys for k in zip(b["code"], b["day"])]]
    for day, g in b.groupby("day", sort=True):
        cum: dict[str, list[float]] = {}
        for code in g["code"].unique():
            m = meta[(code, day)]
            base = known.get(code)
            infos[code].ytd_high = base.ytd_high if base and base.ytd_high else (
                m.ytd_high if m.ytd_high == m.ytd_high else None)
        for r in g.itertuples():
            book.add(r.code, r.dt.to_pydatetime(), r.high, r.low, r.close)
            m = meta[(r.code, day)]
            c = cum.setdefault(r.code, [0.0, 0.0, 0.0])  # 累計出来高, 累計代金, 当日高値
            path = (r.open, r.low, r.high, r.close) if r.close >= r.open else (r.open, r.high, r.low, r.close)
            for k, px in enumerate(path):
                dv = r.volume / 4
                c[0] += dv
                c[1] += dv * px
                c[2] = max(c[2], px)
                ts = r.dt.to_pydatetime() + timedelta(seconds=15 * k)
                snap = Snapshot(ts, r.code, float(px), c[0], vwap=c[1] / c[0] if c[0] else None,
                                high=c[2], prev_close=float(m.prev_close))
                for a in engine.process(snap):
                    alerts.append(AlertRow(a.ts, a.symbol, a.rule, a.level, a.price))
        end = datetime.combine(day, datetime.min.time()) + timedelta(hours=15, minutes=31)
        for a in engine.tick(end):
            alerts.append(AlertRow(a.ts, a.symbol, a.rule, a.level, a.price))
    book.freeze()
    return alerts, book, b


def turnover_study(b, known: dict[str, SymbolInfo]) -> list[dict]:
    """「高値・安値は当日出来高の何%時点で付いたか」（浮動株があれば浮動株回転率も）。"""
    out = []
    for (code, day), g in b.groupby(["code", "day"], sort=False):
        g = g.sort_values("dt")
        cum = g["volume"].cumsum()
        total = cum.iloc[-1]
        if not total:
            continue
        ih, il = g["high"].idxmax(), g["low"].idxmin()
        fl = known.get(code).float_shares if known.get(code) else None
        out.append({
            "code": code, "day": str(day), "total_volume": total,
            "high_time": g.loc[ih, "dt"].strftime("%H:%M"), "high_vol_share": cum.loc[ih] / total,
            "low_time": g.loc[il, "dt"].strftime("%H:%M"), "low_vol_share": cum.loc[il] / total,
            "high_float_turnover": (cum.loc[ih] / fl) if fl else None,
            "low_float_turnover": (cum.loc[il] / fl) if fl else None,
        })
    return out


def inspect(path: str):
    if path.lower().endswith(".7z"):
        try:
            import py7zr
        except ImportError:
            raise SystemExit("7zの中身を見るには: py -3.11 -m pip install py7zr （または 7-Zip で1ファイルだけ展開して指定）")
        with py7zr.SevenZipFile(path) as z:
            names = z.getnames()
        print(f"{len(names)} ファイル。先頭:", *names[:20], sep="\n  ")
        return
    df = _read(path)
    print(f"{path}\n行数: {len(df):,}\n列と型:")
    for c, t in df.dtypes.items():
        print(f"  {c!r}: {t}")
    print("\n先頭5行:")
    print(df.head().to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="ファイル（* 可）")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--kind", choices=["bars", "ticks"], default="bars")
    ap.add_argument("--inspect", action="store_true", help="列名と先頭行を表示して終了")
    ap.add_argument("--col", action="append", default=[], help="役割=列名（time/date/code/open/high/low/close/volume/price）")
    ap.add_argument("--min-day-change", type=float, default=0.05)
    ap.add_argument("--codes", nargs="*")
    ap.add_argument("--start")
    ap.add_argument("--end")
    args = ap.parse_args()

    paths = sorted({p for pat in args.paths for p in glob.glob(pat)}) or args.paths
    if args.inspect:
        inspect(paths[0])
        return
    cfg = load_config(args.config)
    override = dict(c.split("=", 1) for c in args.col)
    bars = load_bars(paths, args.kind, override)
    if args.start:
        bars = bars[bars["dt"] >= args.start]
    if args.end:
        bars = bars[bars["dt"] < (datetime.fromisoformat(args.end) + timedelta(days=1))]
    known = {s.code: s for s in cfg.symbols}
    alerts, book, used = run(bars, cfg.rules, known, args.min_day_change,
                             set(args.codes) if args.codes else None)
    out = cfg.data_dir / f"backtest_{datetime.now():%Y%m%d_%H%M}"
    out.mkdir(parents=True, exist_ok=True)
    rows = evaluate(alerts, book)
    summary = summarize(rows)
    write_csv(out / "eval.csv", rows)
    write_csv(out / "evalsum.csv", summary)
    write_csv(out / "turnover_study.csv", turnover_study(used, known))
    print(f"\n通知 {len(rows):,}件\n")
    print(format_summary(summary))
    print(f"\n保存先: {out}")


if __name__ == "__main__":
    main()
