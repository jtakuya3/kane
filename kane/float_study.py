"""浮動株回転率（当日累計出来高 ÷ 浮動株数）と値動きの関係を、symbols.csv に浮動株がある銘柄で測る。

    py -3.11 -m kane.float_study "C:/Users/takuy/Downloads/_backtest_data/intraday_agg*.parquet"
    py -3.11 -m kane.float_study ... --codes 4498 3909      # 銘柄を絞る

測るもの
 A) 1日の回転率の区分ごとに、当日・翌日・5日後のリターン（回転率が高い日の翌日はどうなるか）
 B) 大きく上げた日（高値が前日比+10%以上）で、高値・安値が付いた時点の回転率（「50%で天井」は本当か）
 C) 回転率が 30/50/100/150/200% を超えた直後（次の足）に買った場合の、引けまで・翌日のリターンと、
    その時点で既に高値を付けていた割合
 D) 連日の累計回転率（回転率10%以上の日が続く「相場」の中での累計）と、天井日の位置
 E) 銘柄ごとの要約
浮動株は symbols.csv の float_shares（推定値を含む）。
symbols.csv の loan（1＝貸借銘柄、0＝信用銘柄）があれば、A〜D を貸借／非貸借で分けても出す
（貸借銘柄は空売りの買い戻しがあるぶん、回転率と天井の関係が変わる可能性があるため）。
"""
from __future__ import annotations

import argparse
import glob
from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd

from .backtest import load_bars
from .config import load_config
from .evaluate import write_csv

LEVELS = [0.3, 0.5, 1.0, 1.5, 2.0]
DAY_BUCKETS = [(0, 0.1, "〜10%"), (0.1, 0.3, "10〜30%"), (0.3, 0.5, "30〜50%"), (0.5, 1.0, "50〜100%"),
               (1.0, 2.0, "100〜200%"), (2.0, 99, "200%以上")]
RUN_BUCKETS = [(0, 0.5, "〜50%"), (0.5, 1.0, "50〜100%"), (1.0, 2.0, "100〜200%"), (2.0, 4.0, "200〜400%"),
               (4.0, 999, "400%以上")]


def bucket(x: float, table) -> str | None:
    for lo, hi, name in table:
        if lo <= x < hi:
            return name
    return None


def daily_table(b: pd.DataFrame, flt: float) -> pd.DataFrame:
    g = b.groupby("day", sort=True)
    d = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
              volume=("volume", "sum")).reset_index()
    d["prev_close"] = d["close"].shift(1)
    d["turn"] = d["volume"] / flt
    d["day_ret"] = d["close"] / d["prev_close"] - 1
    d["gap"] = d["open"] / d["prev_close"] - 1
    d["high_ret"] = d["high"] / d["prev_close"] - 1
    d["next_ret"] = d["close"].shift(-1) / d["close"] - 1
    d["next_high"] = d["high"].shift(-1) / d["close"] - 1
    d["next_low"] = d["low"].shift(-1) / d["close"] - 1
    d["ret5"] = d["close"].shift(-5) / d["close"] - 1
    # 連日の累計回転率：回転率10%以上の日が続く間は足し上げる（間が空いたらリセット）
    run, cum, n = [], 0.0, 0
    runs_n = []
    for t in d["turn"]:
        if t >= 0.10:
            cum += t
            n += 1
        else:
            cum, n = 0.0, 0
        run.append(cum)
        runs_n.append(n)
    d["run_turn"] = run
    d["run_day"] = runs_n
    return d


def intraday_records(b: pd.DataFrame, d: pd.DataFrame, flt: float, code: str) -> tuple[list[dict], list[dict]]:
    """B（高値・安値の時点の回転率）と C（節目を超えた直後に買う）の記録。"""
    peaks, events = [], []
    prev_close = dict(zip(d["day"], d["prev_close"]))
    nxt_close = dict(zip(d["day"], d["close"].shift(-1)))
    for day, g in b.groupby("day", sort=True):
        pc = prev_close.get(day)
        if pc is None or pc != pc or pc <= 0:
            continue
        g = g.sort_values("dt")
        cum = g["volume"].cumsum().to_numpy(float) / flt
        hi = g["high"].to_numpy(float)
        lo = g["low"].to_numpy(float)
        cl = g["close"].to_numpy(float)
        ts = g["dt"].to_numpy()
        day_high, day_low = hi.max(), lo.min()
        ih, il = int(hi.argmax()), int(lo.argmin())
        big_up = day_high / pc - 1 >= 0.10
        peaks.append({"code": code, "day": str(day)[:10], "big_up": big_up, "day_turn": cum[-1],
                      "high_ret": day_high / pc - 1, "close_ret": cl[-1] / pc - 1,
                      "turn_at_high": cum[ih], "turn_at_low": cum[il],
                      "high_frac_of_day_turn": cum[ih] / cum[-1] if cum[-1] > 0 else np.nan,
                      "high_time": pd.Timestamp(ts[ih]).strftime("%H:%M"),
                      "low_time": pd.Timestamp(ts[il]).strftime("%H:%M")})
        nc = nxt_close.get(day)
        for lv in LEVELS:
            k = int(np.argmax(cum >= lv)) if (cum >= lv).any() else -1
            if k < 0 or k + 1 >= len(cl):
                continue
            entry = cl[k + 1]  # 次の足で入る
            after_hi = hi[k + 1:].max()
            after_lo = lo[k + 1:].min()
            events.append({"code": code, "day": str(day)[:10], "level": lv, "big_up": big_up,
                           "time": pd.Timestamp(ts[k]).strftime("%H:%M"),
                           "chg_at": cl[k] / pc - 1, "to_close": cl[-1] / entry - 1,
                           "mfe": after_hi / entry - 1, "mae": after_lo / entry - 1,
                           "high_done": after_hi / entry - 1 < 0.02,
                           "next_close": (nc / entry - 1) if nc == nc and nc else np.nan})
    return peaks, events


def _q(v, q):
    v = [x for x in v if x == x]
    return float(np.quantile(v, q)) if v else float("nan")


def _mean(v):
    v = [x for x in v if x == x and abs(x) < 1.0]
    return sum(v) / len(v) if v else float("nan")


def _rate(v):
    v = [x for x in v if x == x]
    return sum(1 for x in v if x > 0) / len(v) if v else float("nan")


def pct(x, signed=True):
    return "-" if x != x else (f"{x:+.2%}" if signed else f"{x:.0%}")


LOAN_NAME = {"1": "貸借銘柄", "0": "信用銘柄（非貸借）", "": "区分未確認"}


def report_by_loan(days: pd.DataFrame, peaks: list[dict], events: list[dict], loan: dict) -> str:
    """貸借区分ごとに A〜D を出し直す（区分が2つ以上あるときだけ）。"""
    pk, ev = pd.DataFrame(peaks), pd.DataFrame(events)
    groups = sorted({loan.get(c, "") for c in days["code"].unique()}, key=lambda x: {"1": 0, "0": 1}.get(x, 2))
    if len(groups) < 2:
        return "（貸借区分が1種類しかないので、区分別の比較は省略）"
    out = ["＝＝ 貸借区分別（symbols.csv の loan 列。1＝貸借、0＝信用のみ） ＝＝"]
    for g in groups:
        codes = [c for c in days["code"].unique() if loan.get(c, "") == g]
        d = days[days["code"].isin(codes)]
        p = [r for r in peaks if r["code"] in codes]
        e = [r for r in events if r["code"] in codes]
        if d.empty:
            continue
        out.append("")
        out.append(f"■ {LOAN_NAME.get(g, g)}：{len(codes)}銘柄 {', '.join(codes)}")
        text, _ = report(d, p, e, include_e=False)
        out.append(text)
    return "\n".join(out)


def report(days: pd.DataFrame, peaks: list[dict], events: list[dict], include_e: bool = True) -> tuple[str, dict]:
    out, tables = [], {}
    # A
    out += ["A) 1日の浮動株回転率の区分ごと（全銘柄日）",
            f"{'回転率':<12}{'件数':>7}{'当日':>9}{'翌日↑':>8}{'翌日':>9}{'翌日中央':>9}{'翌高値':>9}{'翌安値':>9}{'5日後':>9}"]
    rows = []
    for lo, hi, name in DAY_BUCKETS:
        s = days[(days["turn"] >= lo) & (days["turn"] < hi)]
        if len(s) < 5:
            continue
        r = {"bucket": name, "n": len(s), "day_ret": _mean(s["day_ret"]), "next_up": _rate(s["next_ret"]),
             "next_ret": _mean(s["next_ret"]), "next_med": _q(s["next_ret"], 0.5),
             "next_high": _mean(s["next_high"]), "next_low": _mean(s["next_low"]), "ret5": _mean(s["ret5"])}
        rows.append(r)
        out.append(f"{name:<12}{r['n']:>7,}{pct(r['day_ret']):>9}{pct(r['next_up'], False):>8}{pct(r['next_ret']):>9}"
                   f"{pct(r['next_med']):>9}{pct(r['next_high']):>9}{pct(r['next_low']):>9}{pct(r['ret5']):>9}")
    tables["A_day_buckets"] = rows
    out.append("")
    # B
    pk = pd.DataFrame(peaks)
    big = pk[pk["big_up"]] if len(pk) else pk
    out += ["B) 大きく上げた日（高値が前日比+10%以上）で、高値・安値を付けた時点の回転率",
            f"  件数 {len(big)}"]
    if len(big):
        out.append(f"  高値の時点の回転率：25% {pct(_q(big['turn_at_high'], .25), False)} / 中央 {pct(_q(big['turn_at_high'], .5), False)}"
                   f" / 75% {pct(_q(big['turn_at_high'], .75), False)}   （その日の総回転率：中央 {pct(_q(big['day_turn'], .5), False)}）")
        out.append(f"  高値が「その日の出来高の何%消化時点」か：中央 {pct(_q(big['high_frac_of_day_turn'], .5), False)}"
                   f"（25〜75%：{pct(_q(big['high_frac_of_day_turn'], .25), False)}〜{pct(_q(big['high_frac_of_day_turn'], .75), False)}）")
        out.append(f"  安値の時点の回転率：中央 {pct(_q(big['turn_at_low'], .5), False)}")
        # 高値時点の回転率の分布
        bins = [(0, .1), (.1, .3), (.3, .5), (.5, 1.0), (1.0, 2.0), (2.0, 99)]
        tot = len(big)
        out.append("  高値時点の回転率の分布：" + "  ".join(
            f"{a:.0%}〜{b:.0%}:{(sum((big['turn_at_high'] >= a) & (big['turn_at_high'] < b)) / tot):.0%}"
            for a, b in bins))
        # 総回転率が高い日ほど高値は遅いか
        for lo, hi, name in DAY_BUCKETS:
            s = big[(big["day_turn"] >= lo) & (big["day_turn"] < hi)]
            if len(s) >= 5:
                out.append(f"    総回転率 {name:<9} 件数 {len(s):>4}  高値時点の回転率 中央 {pct(_q(s['turn_at_high'], .5), False):>5}"
                           f"  高値→引け {pct(_mean(s['close_ret'] - s['high_ret'])):>8}")
    tables["B_peaks"] = peaks
    out.append("")
    # C
    ev = pd.DataFrame(events)
    out += ["C) 回転率の節目を超えた直後（次の足）に買った場合",
            f"{'節目':<8}{'件数':>6}{'時刻中央':>9}{'引けまで':>9}{'中央':>9}{'伸び':>8}{'逆行':>8}{'翌日':>9}{'既に高値済':>10}"]
    rows = []
    for lv in LEVELS:
        s = ev[ev["level"] == lv] if len(ev) else ev
        if len(s) < 5:
            continue
        r = {"level": lv, "n": len(s), "time_med": sorted(s["time"])[len(s) // 2], "to_close": _mean(s["to_close"]),
             "to_close_med": _q(s["to_close"], .5), "mfe": _mean(s["mfe"]), "mae": _mean(s["mae"]),
             "next": _mean(s["next_close"]), "high_done": s["high_done"].mean()}
        rows.append(r)
        out.append(f"{lv:<8.0%}{r['n']:>6}{r['time_med']:>9}{pct(r['to_close']):>9}{pct(r['to_close_med']):>9}"
                   f"{pct(r['mfe']):>8}{pct(r['mae']):>8}{pct(r['next']):>9}{pct(r['high_done'], False):>10}")
    tables["C_level_events"] = rows
    out.append("  ※既に高値済＝その後、買値から+2%以上の高値を付けなかった割合。高いほど「その回転率を超えたら天井圏」。")
    out.append("")
    # D
    out += ["D) 連日の累計回転率（回転率10%以上の日が続く間の累計）",
            f"{'累計回転率':<12}{'件数':>7}{'翌日↑':>8}{'翌日':>9}{'翌高値':>9}{'翌安値':>9}{'5日後':>9}"]
    rows = []
    run = days[days["run_day"] >= 1]
    for lo, hi, name in RUN_BUCKETS:
        s = run[(run["run_turn"] >= lo) & (run["run_turn"] < hi)]
        if len(s) < 5:
            continue
        r = {"bucket": name, "n": len(s), "next_up": _rate(s["next_ret"]), "next_ret": _mean(s["next_ret"]),
             "next_high": _mean(s["next_high"]), "next_low": _mean(s["next_low"]), "ret5": _mean(s["ret5"])}
        rows.append(r)
        out.append(f"{name:<12}{r['n']:>7,}{pct(r['next_up'], False):>8}{pct(r['next_ret']):>9}{pct(r['next_high']):>9}"
                   f"{pct(r['next_low']):>9}{pct(r['ret5']):>9}")
    tables["D_run_buckets"] = rows
    # 相場（run）の天井日は累計の何%で来たか
    tops = []
    for code, g in days.groupby("code"):
        g = g.reset_index(drop=True)
        i = 0
        while i < len(g):
            if g.loc[i, "run_day"] == 1:
                j = i
                while j + 1 < len(g) and g.loc[j + 1, "run_day"] > 0:
                    j += 1
                seg = g.loc[i:j]
                if len(seg) >= 3 and seg["high"].max() / seg["prev_close"].iloc[0] - 1 >= 0.2:
                    k = seg["high"].idxmax()
                    tops.append({"code": code, "start": str(seg["day"].iloc[0])[:10], "days": len(seg),
                                 "top_day": int(g.loc[k, "run_day"]), "top_run_turn": g.loc[k, "run_turn"],
                                 "total_run_turn": seg["run_turn"].iloc[-1], "gain": seg["high"].max() / seg["prev_close"].iloc[0] - 1})
                i = j + 1
            else:
                i += 1
    if tops:
        t = pd.DataFrame(tops)
        out.append(f"  3日以上続き+20%以上上げた相場 {len(t)}件：天井は {t['top_day'].median():.0f}日目（中央）、"
                   f"天井日までの累計回転率 中央 {pct(_q(t['top_run_turn'], .5), False)}（25〜75%：{pct(_q(t['top_run_turn'], .25), False)}〜{pct(_q(t['top_run_turn'], .75), False)}）、"
                   f"相場全体の累計 中央 {pct(_q(t['total_run_turn'], .5), False)}")
    tables["D_runs"] = tops
    out.append("")
    if not include_e:
        return "\n".join(out), tables
    # E
    out += ["E) 銘柄ごと", f"{'コード':<7}{'日数':>5}{'平均回転率':>10}{'最大':>8}{'+10%日':>7}{'高値時点回転率(中央)':>20}"]
    rows = []
    for code, g in days.groupby("code"):
        p = pk[(pk["code"] == code) & pk["big_up"]] if len(pk) else pk
        r = {"code": code, "days": len(g), "turn_mean": g["turn"].mean(), "turn_max": g["turn"].max(),
             "big_up_days": int(len(p)), "turn_at_high_med": _q(p["turn_at_high"], .5) if len(p) else float("nan")}
        rows.append(r)
        out.append(f"{code:<7}{r['days']:>5}{pct(r['turn_mean'], False):>10}{pct(r['turn_max'], False):>8}{r['big_up_days']:>7}"
                   f"{pct(r['turn_at_high_med'], False):>20}")
    tables["E_symbols"] = rows
    out.append("")
    out.append("※浮動株は symbols.csv の推定値。件数が少ない区分（5件未満）は表示しない。±100%超のリターンは平均から除外。")
    return "\n".join(out), tables


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--codes", nargs="*", default=None)
    args = ap.parse_args()
    cfg = load_config(args.config)
    floats = {s.code: s.float_shares for s in cfg.symbols if s.float_shares}
    loan = {s.code: s.loan for s in cfg.symbols}
    if args.codes:
        floats = {c: f for c, f in floats.items() if c in set(args.codes)}
    if not floats:
        print("symbols.csv に浮動株（float_shares）のある銘柄がありません")
        return
    paths = sorted({p for pat in args.paths for p in glob.glob(pat)}) or args.paths
    bars = load_bars(paths, "bars", {})
    bars = bars[bars["code"].isin(floats)].copy()
    if bars.empty:
        print(f"データ内に対象銘柄がありません: {sorted(floats)}")
        return
    bars["day"] = bars["dt"].dt.normalize()
    all_days, peaks, events = [], [], []
    for code, b in bars.groupby("code", sort=True):
        flt = floats[code]
        d = daily_table(b, flt)
        d["code"] = code
        all_days.append(d)
        p, e = intraday_records(b, d, flt, code)
        peaks += p
        events += e
        print(f"{code}: {len(d)}日 浮動株 {flt:,.0f} 平均回転率 {d['turn'].mean():.0%} 最大 {d['turn'].max():.0%}")
    days = pd.concat(all_days, ignore_index=True)
    days["loan"] = days["code"].map(loan)
    text, tables = report(days, peaks, events)
    text += "\n\n" + report_by_loan(days, peaks, events, loan)
    out = cfg.data_dir / f"float_{datetime.now():%Y%m%d_%H%M}"
    out.mkdir(parents=True, exist_ok=True)
    days.assign(day=days["day"].astype(str).str[:10]).to_csv(out / "float_days.csv", index=False, encoding="utf-8-sig")
    for name, rows in tables.items():
        if rows:
            write_csv(out / f"{name}.csv", rows)
    print("\n" + text)
    print(f"\n保存先: {out}")


if __name__ == "__main__":
    main()
