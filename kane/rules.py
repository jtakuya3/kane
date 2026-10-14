"""検出ルール。バックテストで効いた「出来高の条件付き」の組み合わせだけを通知する。

- R10 買い候補：年初来高値の更新 × RVOL 2〜10倍
- R10 利確警戒：前日比+25%以上 × RVOL 10倍以上
- R2 VWAP乖離+8%以上 × RVOL 20倍以上（天井警戒）
- R3 失速 / R4 ダブルトップ × RVOL 20倍以上（天井警戒）
- R13 大口板の剥がれ予兆・剥がれ / R14 ストップ高（イベント通知）
すべての通知に浮動株回転率とRVOLを添える。
"""
from __future__ import annotations

from collections import deque
from datetime import datetime

from .config import RuleConfig
from .models import Alert, Bar, Snapshot
from .state import SymbolState



def _fmt(x: float | None, pct=False) -> str:
    if x is None:
        return "-"
    return f"{x:+.1%}" if pct else f"{x:,.0f}"


def vol_frac(ts: datetime, profile: list) -> float:
    """その時刻までに、普段1日の出来高の何割が出ているか（9:00からの分で線形補間）。"""
    m = (ts.hour - 9) * 60 + ts.minute + ts.second / 60
    if m <= 0:
        return profile[1][1] if len(profile) > 1 else 0.05
    for (m0, f0), (m1, f1) in zip(profile, profile[1:]):
        if m <= m1:
            return f0 + (f1 - f0) * (m - m0) / (m1 - m0) if m1 > m0 else f1
    return profile[-1][1]


def rvol_of(st: SymbolState, ts: datetime, cfg: RuleConfig) -> float | None:
    """RVOL＝今の累計出来高 ÷（過去60日の平均日出来高 × この時刻までの普段の割合）。"""
    if not st.last or not st.info.avg_vol:
        return None
    frac = max(vol_frac(ts, cfg.volume_profile), 0.03)  # 寄り直後の暴れを抑える
    return st.last.volume / (st.info.avg_vol * frac)


def vol_line(st: SymbolState, ts: datetime, cfg: RuleConfig) -> str:
    """浮動株回転率とRVOLの1行。"""
    fl = st.info.float_shares
    turn = (f"浮動株回転率 {st.turnover:.0%}（浮動株{fl / 1e4:,.0f}万株）" if st.turnover is not None
            else "浮動株回転率 -（浮動株未登録）")
    rv = rvol_of(st, ts, cfg)
    return f"{turn}  RVOL {rv:.1f}倍" if rv is not None else f"{turn}  RVOL -（平均出来高未取得）"


def _alert(st: SymbolState, ts: datetime, rule: str, level: str, text: str, cfg: RuleConfig,
           **extras) -> Alert:
    tag = f"{st.info.code} {st.info.name}".strip()
    price = st.last.price if st.last else 0.0
    msg = (f"{ts:%H:%M:%S}\n[{rule}] {tag} {text}\n"
           f"{_fmt(price)}円 VWAP乖離{_fmt(st.vwap_dev, True)}\n{vol_line(st, ts, cfg)}")
    return Alert(ts, st.info.code, rule, level, msg, price,
                 {"turnover": st.turnover, "vwap_dev": st.vwap_dev, "rvol": rvol_of(st, ts, cfg), **extras})


# ---------------- スナップショット系 ----------------

def r2_vwap_dev(st: SymbolState, s: Snapshot, cfg: RuleConfig) -> list[Alert]:
    """VWAP乖離+8%以上 × RVOL 20倍以上（出来高の噴き上げ後の戻りを警戒）。"""
    d = st.vwap_dev
    if d is None:
        return []
    out = []
    for lv in cfg.vwap_dev_levels:
        key = ("R2armed", lv)
        armed = st.vars.get(key, True)
        if armed and d >= lv:
            st.vars[key] = False
            rv = rvol_of(st, s.ts, cfg)
            if lv < cfg.r2_min_level or rv is None or rv < cfg.top_rvol_min:
                continue
            out.append(_alert(st, s.ts, "R2", f"{lv:.0%}",
                              f"天井警戒：VWAP乖離+{lv:.0%}超え × 出来高{rv:.0f}倍（噴き上げ後の戻りに注意）", cfg))
        elif not armed and d < lv - cfg.vwap_dev_rearm:
            st.vars[key] = True
    return out


def r4_double_top(st: SymbolState, s: Snapshot, cfg: RuleConfig) -> list[Alert]:
    v = st.vars
    h1 = v.get("h1")
    if h1 is None:
        v["h1"], v["v1"], v["pulled"] = s.high or s.price, None, False
        return []
    if s.price > h1:  # 高値更新 → 基準を更新
        v["h1"], v["v1"], v["pulled"] = s.price, st.rolling_vol(s.ts), False
        return []
    if s.price <= h1 * (1 - cfg.dtop_pullback):
        v["pulled"] = True
        return []
    v1 = v.get("v1")
    if v["pulled"] and v1 and s.price >= h1 * (1 - cfg.dtop_near):
        now5 = st.rolling_vol(s.ts)
        if now5 <= v1 * cfg.dtop_vol_ratio:
            v["pulled"] = False
            rv = rvol_of(st, s.ts, cfg)
            if rv is None or rv < cfg.top_rvol_min:
                return []
            return [_alert(st, s.ts, "R4", "WARN",
                           f"天井警戒：高値{_fmt(h1)}に再接近、5分出来高が前回高値時の{now5 / v1:.0%}（ダブルトップ）", cfg)]
    return []


def _yen(x: float) -> str:
    """株価表示（カンマなし、0.1円刻みの銘柄は小数も表示）。"""
    return f"{x:.0f}" if float(x).is_integer() else f"{x:.1f}"


def _card(st: SymbolState, s: Snapshot, rule: str, level: str, body: list[str], cfg: RuleConfig,
          **extras) -> Alert:
    """時刻・銘柄・時価総額の見出し付きの複数行通知。"""
    i = st.info
    cap = f"時価総額 {s.price * i.issued_shares / 1e8:,.0f}億円" if i.issued_shares else ""
    lines = [f"{s.ts:%H:%M:%S}", f"{i.code}{i.name}{cap}", *body]
    lines.append(vol_line(st, s.ts, cfg))
    return Alert(s.ts, i.code, rule, level, "\n".join(lines), s.price,
                 {"turnover": st.turnover, "vwap_dev": st.vwap_dev, "rvol": rvol_of(st, s.ts, cfg), **extras})


def _pct_prev(s: Snapshot) -> str:
    return f"（{s.price / s.prev_close - 1:+.2%}）" if s.prev_close else ""


def _vwap_txt(st: SymbolState) -> str:
    return f"VWAP比 {st.vwap_dev:+.2%}" if st.vwap_dev is not None else ""


def r10_price_step(st: SymbolState, s: Snapshot, cfg: RuleConfig) -> list[Alert]:
    """年初来高値の更新 × RVOL 2〜10倍 → 買い候補。前日比+25%以上 × RVOL 10倍以上 → 利確警戒。"""
    pc = s.prev_close
    if not pc:
        return []
    chg = s.price / pc - 1
    n = int(chg / cfg.price_step)  # 0方向に切り捨て（+7%→1、−7%→−1）
    step_up = n > st.vars.get("step_max", 0)
    step_down = cfg.price_step_down and n < st.vars.get("step_min", 0)
    if step_up:
        st.vars["step_max"] = n
    if step_down:
        st.vars["step_min"] = n
    rv = rvol_of(st, s.ts, cfg)
    step = f"{abs(n) * cfg.price_step:.0%}段階" if n > 0 else f"−{abs(n) * cfg.price_step:.0%}段階" if n < 0 else ""
    price_line = f"株価 {_yen(s.price)}円 前日比 {s.price - pc:+.0f}円（{chg:+.2%}）  {_vwap_txt(st)}".rstrip()
    out = []

    ytd = st.info.ytd_high
    if (ytd and ytd < s.price <= ytd * (1 + cfg.ytd_near) and rv is not None
            and cfg.buy_rvol_min <= rv < cfg.buy_rvol_max and st.once("R10ytd")):
        out.append(_card(st, s, "R10", "買い候補", [
            f"買い候補：年初来高値 {_yen(ytd)}円を更新 × 出来高{rv:.1f}倍", price_line], cfg, change=chg))

    if (step_up and chg >= cfg.fade_step and rv is not None and rv >= cfg.fade_rvol_min
            and st.once(("R10fade", n))):
        out.append(_card(st, s, "R10", "利確警戒", [
            f"利確警戒：前日比 {step} × 出来高{rv:.0f}倍（ここから押されやすい）", price_line], cfg, change=chg))
    elif cfg.price_step_alerts and (step_up or step_down):
        out.append(_card(st, s, "R10", step, [f"株価の段階 {step}", price_line], cfg, change=chg))
    return out


SPECIAL_SIGN = "0102"  # kabuステーションAPIの気配フラグ：特別気配


def _in_continuous_session(ts: datetime) -> bool:
    t = ts.time()
    return (t >= t.replace(hour=9, minute=0, second=0, microsecond=0)
            and not (t.replace(hour=11, minute=30, second=0, microsecond=0) <= t
                     < t.replace(hour=12, minute=30, second=0, microsecond=0)))


def _is_wall(side, p, q, qtys, cfg):
    """周りの板（20本の中央値）の wall_mult 倍以上・金額 wall_min_yen 以上なら大口板。中央値も返す。"""
    others = list(qtys)
    others.remove(q)
    med = others[len(others) // 2] if others else 0
    return bool(med) and q >= med * cfg.wall_mult and p * q >= cfg.wall_min_yen, med


def r13_big_board(st: SymbolState, s: Snapshot, cfg: RuleConfig) -> list[Alert]:
    """大口板を見張り、剥がれそうな予兆（ピークから減り始めた）と剥がれ（消えた・突き抜けた）を知らせる。

    売り板の剥がれ＝上に抜けやすい、買い板の剥がれ＝下に抜けやすい。減った分は、その値段が最良気配で
    出来高が増えていれば「約定で食われた」、そうでなければ「取り消された」と見なす。
    """
    v = st.vars
    prev = v.get("prev_board")
    cur_buy, cur_sell = s.board_buy or [], s.board_sell or []
    v["prev_board"] = {p: q for p, q in cur_buy + cur_sell}
    prev_vol, v["r13_vol"] = v.get("r13_vol"), s.volume
    if not prev or not (cur_buy and cur_sell) or not _in_continuous_session(s.ts):
        return []  # 起動直後・寄り前・昼休みは判定しない
    if SPECIAL_SIGN in (s.buy1_sign, s.sell1_sign):
        return []  # 特別気配中は板が偏るのが普通なので除外
    walls = v.setdefault("walls", {})  # (側, 値段) → 見張り中の大口板
    books = {"買い": dict(cur_buy), "売り": dict(cur_sell)}
    traded = max(0.0, s.volume - prev_vol) if prev_vol is not None else 0.0
    out = []

    # 1) 大口板を見つけて見張りに入れる
    levels = [("買い", p, q) for p, q in cur_buy] + [("売り", p, q) for p, q in cur_sell]
    qtys = sorted(q for _, _, q in levels)
    lo, hi = min(prev), max(prev)
    for side, p, q in levels:
        big, med = _is_wall(side, p, q, qtys, cfg)
        if not big:
            continue
        w = walls.get((side, p))
        if w:
            w["peak"] = max(w["peak"], q)
            continue
        walls[(side, p)] = {"peak": q, "last": q, "eaten": 0.0, "cancel": 0.0, "warned": False,
                            "since": s.ts, "med": med}
        if (cfg.wall_notify_appear and lo <= p <= hi and prev.get(p, 0) < q * cfg.wall_new_ratio
                and st.cooled(("R13", side, p), s.ts, cfg.wall_cooldown_sec)):
            out.append(_card(st, s, "R13", side, [
                f"大口{side}板 {_yen(p)}円 {q:,.0f}株（約{p * q / 1e4:,.0f}万円）",
                f"周りの板の約{q / med:.0f}倍（中央値{med:,.0f}株）  現在値 {_yen(s.price)}円から{p / s.price - 1:+.2%}",
            ], cfg, wall_price=p, wall_qty=q, wall_mult=q / med))

    # 2) 見張り中の大口板の減り方を見る
    for (side, p), w in list(walls.items()):
        book = books[side]
        best = max(book) if side == "買い" else min(book)
        far = min(book) if side == "買い" else max(book)
        if (side == "買い" and p < far) or (side == "売り" and p > far):
            del walls[(side, p)]  # 株価が離れて見えなくなった（判断できないので黙って外す）
            continue
        passed = p > best if side == "買い" else p < best  # 板の値段を突き抜けた
        q = 0.0 if passed else book.get(p, 0.0)
        drop = max(0.0, w["last"] - q)
        if drop:
            ate = min(drop, traded) if (passed or p == best) else 0.0
            w["eaten"] += ate
            w["cancel"] += drop - ate
        w["last"] = q
        hint = "上に抜けやすい" if side == "売り" else "下に抜けやすい"
        how = f"約定で食われた {w['eaten']:,.0f}株 / 取り消し {w['cancel']:,.0f}株"
        head = f"大口{side}板 {_yen(p)}円"
        if passed or q <= w["peak"] * cfg.wall_gone_ratio:
            del walls[(side, p)]
            if cfg.wall_notify_gone:
                what = "突き抜けた" if passed else "ほぼ消えた"
                out.append(_card(st, s, "R13", f"{side}板剥がれ", [
                    f"{head} 剥がれ（{what}）：ピーク {w['peak']:,.0f}株 → {q:,.0f}株  {hint}",
                    how, f"現在値 {_yen(s.price)}円（板の値段から{s.price / p - 1:+.2%}）",
                ], cfg, wall_price=p, wall_peak=w["peak"], wall_qty=q))
            continue
        if not w["warned"] and q <= w["peak"] * cfg.wall_warn_ratio:
            w["warned"] = True
            if st.cooled(("R13warn", side, p), s.ts, cfg.wall_cooldown_sec):
                out.append(_card(st, s, "R13", f"{side}板剥がれ予兆", [
                    f"{head} 剥がれ予兆：ピーク {w['peak']:,.0f}株 → {q:,.0f}株（{q / w['peak']:.0%}）  {hint}",
                    how, f"現在値 {_yen(s.price)}円（板の値段まで{p / s.price - 1:+.2%}）",
                ], cfg, wall_price=p, wall_peak=w["peak"], wall_qty=q))
    return out


# 東証の制限値幅（前日終値 → 値幅）。値幅拡大は反映されないので、kabu の UpperLimit を優先する
_LIMIT_TABLE = [
    (100, 30), (200, 50), (500, 80), (700, 100), (1000, 150), (1500, 300), (2000, 400),
    (3000, 500), (5000, 700), (7000, 1000), (10000, 1500), (15000, 3000), (20000, 4000),
    (30000, 5000), (50000, 7000), (70000, 10000), (100000, 15000), (150000, 30000),
    (200000, 40000), (300000, 50000), (500000, 70000), (700000, 100000), (1000000, 150000),
]


def upper_limit(prev_close: float) -> float:
    for bound, width in _LIMIT_TABLE:
        if prev_close < bound:
            return prev_close + width
    return prev_close + 300000


def r14_stop_high(st: SymbolState, s: Snapshot, cfg: RuleConfig) -> list[Alert]:
    """ストップ高の張り付き・剥がれ警戒・剥がれ・再張り付き。"""
    up = st.upper or (upper_limit(s.prev_close) if s.prev_close else None)
    if not up:
        return []
    v = st.vars
    at = bool(s.bid) and s.bid >= up - 1e-9 and (not s.ask or s.ask >= up - 1e-9)
    qty = s.buy1_qty or 0
    hist = v.setdefault("lim_hist", deque())
    up_txt = f"上限 {_yen(up)}円"
    out = []
    if at:
        hist.append((s.ts, qty))
        while (s.ts - hist[0][0]).total_seconds() > cfg.limit_warn_window_min * 60:
            hist.popleft()
        if not v.get("lim_at"):
            v["lim_at"] = True
            head = "ストップ高 再張り付き" if v.get("lim_peeled") else "ストップ高 張り付き"
            out.append(_card(st, s, "R14", "張り付き", [
                f"{head} {_yen(up)}円  買い残 {qty:,.0f}株（約{up * qty / 1e4:,.0f}万円）"], cfg))
            return out
        peak = max(q for _, q in hist)
        sell_at_up = s.sell1_qty if s.ask and s.ask >= up - 1e-9 else 0
        reasons = []
        if peak and qty <= peak * cfg.limit_warn_drop:
            reasons.append(f"買い残 {peak:,.0f}株→{qty:,.0f}株（{cfg.limit_warn_window_min}分内ピーク比{qty / peak:.0%}）")
        if sell_at_up and sell_at_up >= qty:
            reasons.append(f"上限値の売り板 {sell_at_up:,.0f}株 ≧ 買い残 {qty:,.0f}株")
        if reasons and st.cooled("R14warn", s.ts, cfg.limit_warn_cooldown_sec):
            out.append(_card(st, s, "R14", "警戒", ["ストップ高 剥がれ警戒", *reasons], cfg))
        v["lim_last_qty"] = qty
        return out
    if v.get("lim_at"):  # 張り付き → 剥がれ
        v["lim_at"], v["lim_peeled"] = False, True
        hist.clear()
        last = v.get("lim_last_qty", 0)
        out.append(_card(st, s, "R14", "剥がれ", [
            f"ストップ高 剥がれ 現在値 {_yen(s.price)}円（{up_txt}から{s.price / up - 1:+.2%}）",
            f"買い気配 {_yen(s.bid) if s.bid else '-'}円  直前の買い残 {last:,.0f}株",
        ], cfg))
    return out


# ---------------- 1分足確定系 ----------------

def r3_stall(st: SymbolState, b: Bar, cfg: RuleConfig) -> list[Alert]:
    hi, peak, ps = st.day_high, st.peak_bar_vol, st.peak_bar_start
    if not hi or not peak or ps is None or ps == b.start:
        return []
    bars = list(st.bars)
    recent = [x.start for x in bars[-cfg.stall_peak_within_bars:]]
    if ps not in recent:
        return []
    if b.close < hi * (1 - cfg.stall_near_high) or b.volume > peak * cfg.stall_vol_ratio:
        return []
    rv = rvol_of(st, b.start, cfg)
    if rv is None or rv < cfg.top_rvol_min:
        return []
    if not st.cooled("R3", b.start, cfg.cooldown_sec):
        return []
    return [_alert(st, b.start, "R3", "WARN",
                   f"天井警戒：高値圏で失速（1分出来高がピークの{b.volume / peak:.0%}）", cfg)]


SNAPSHOT_RULES = [r2_vwap_dev, r4_double_top, r10_price_step, r13_big_board, r14_stop_high]
BAR_RULES = [r3_stall]
LIGHT_RULES = [r10_price_step]
