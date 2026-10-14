"""検出ルール R1〜R9。

スナップショットごとに判定するもの（R1, R2, R4, R5, R8の発火, R9）と、
1分足の確定ごとに判定するもの（R3, R6, R7, R8の準備）に分かれる。
"""
from __future__ import annotations

from datetime import datetime

from .config import RuleConfig
from .models import Alert, Bar, Snapshot
from .state import SymbolState

R1_LABEL = {0.5: "天井警戒", 0.8: "急落警戒", 0.95: "底候補（1回転）"}
R2_LABEL = {0.05: "伸び切り", 0.08: "過熱", 0.10: "過熱+"}


def _fmt(x: float | None, pct=False) -> str:
    if x is None:
        return "-"
    return f"{x:+.1%}" if pct else f"{x:,.0f}"


def _alert(st: SymbolState, ts: datetime, rule: str, level: str, text: str, **extras) -> Alert:
    tag = f"{st.info.code} {st.info.name}".strip()
    price = st.last.price if st.last else 0.0
    turn = f"{st.turnover:.0%}" if st.turnover is not None else "-"
    tail = f"｜{_fmt(price)}円 回転率{turn} VWAP乖離{_fmt(st.vwap_dev, True)}"
    return Alert(ts, st.info.code, rule, level, f"[{rule}] {tag} {text}{tail}", price,
                 {"turnover": st.turnover, "vwap_dev": st.vwap_dev, **extras})


# ---------------- スナップショット系 ----------------

def r1_turnover(st: SymbolState, s: Snapshot, cfg: RuleConfig) -> list[Alert]:
    t = st.turnover
    if t is None:
        return []
    out = []
    for lv in cfg.turnover_levels:
        if t >= lv and st.once(("R1", lv)):
            label = R1_LABEL.get(lv, "")
            out.append(_alert(st, s.ts, "R1", f"{lv:.0%}", f"浮動株回転率{lv:.0%}到達 {label}"))
    return out


def r2_vwap_dev(st: SymbolState, s: Snapshot, cfg: RuleConfig) -> list[Alert]:
    d = st.vwap_dev
    if d is None:
        return []
    out = []
    for lv in cfg.vwap_dev_levels:
        key = ("R2armed", lv)
        armed = st.vars.get(key, True)
        if armed and d >= lv:
            st.vars[key] = False
            out.append(_alert(st, s.ts, "R2", f"{lv:.0%}", f"VWAP乖離+{lv:.0%}超え {R2_LABEL.get(lv, '')}"))
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
            return [_alert(st, s.ts, "R4", "WARN",
                           f"高値{_fmt(h1)}に再接近、5分出来高{_fmt(now5)}（前回高値時{_fmt(v1)}の{now5 / v1:.0%}）ダブルトップ警戒")]
    return []


def r5_board(st: SymbolState, s: Snapshot, cfg: RuleConfig) -> list[Alert]:
    if not s.buy5 or not s.sell5:  # ストップ高・安や気配なしは対象外
        st.vars.pop("board_side", None)
        return []
    ratio = s.buy5 / s.sell5
    side = "weak" if ratio <= cfg.board_weak else "strong" if ratio >= cfg.board_strong else None
    if side != st.vars.get("board_side"):
        st.vars["board_side"], st.vars["board_since"] = side, s.ts
        return []
    if side is None or (s.ts - st.vars["board_since"]).total_seconds() < cfg.board_sustain_sec:
        return []
    if not st.cooled(("R5", side), s.ts, cfg.board_cooldown_sec):
        return []
    text = "売り優勢" if side == "weak" else "買い板が厚い"
    return [_alert(st, s.ts, "R5", side, f"板比率{ratio:.2f}（上位5本 買/売）{text}", board_ratio=ratio)]


def r8_trigger(st: SymbolState, s: Snapshot, cfg: RuleConfig) -> list[Alert]:
    arm = st.vars.get("r8")
    if not arm or s.price <= arm["trigger"]:
        return []
    st.vars["r8"] = None
    target = s.vwap
    return [_alert(st, s.ts, "R8", "BUY",
                   f"1回転反発の買い：大陰線の高値{_fmt(arm['trigger'])}を上抜け 損切り{_fmt(arm['stop'])} 目標VWAP{_fmt(target)}",
                   stop=arm["stop"], target=target)]


def r9_breakout(st: SymbolState, s: Snapshot, cfg: RuleConfig) -> list[Alert]:
    bars = list(st.bars)
    q = cfg.breakout_quiet_bars
    if st.breakout_vol5m is None or len(bars) <= q:
        return []
    prior_high = max(b.high for b in bars[:-q])
    recent_high = max(b.high for b in bars[-q:])
    if recent_high > prior_high or s.price <= prior_high:
        return []
    v5 = st.rolling_vol(s.ts)
    if v5 < st.breakout_vol5m or not st.once(("R9", prior_high)):
        return []
    return [_alert(st, s.ts, "R9", "BREAK",
                   f"高値{_fmt(prior_high)}を出来高を伴って上抜け（5分出来高{_fmt(v5)}≧{_fmt(st.breakout_vol5m)}）")]


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
    if not st.cooled("R3", b.start, cfg.cooldown_sec):
        return []
    return [_alert(st, b.start, "R3", "WARN",
                   f"高値圏で失速：1分出来高{_fmt(b.volume)}（ピーク{_fmt(peak)}の{b.volume / peak:.0%}）")]


def r6_rsi(st: SymbolState, b: Bar, cfg: RuleConfig) -> list[Alert]:
    r = st.rsi(cfg.rsi_period)
    if r is None:
        return []
    if r > cfg.rsi_arm:
        st.vars["rsi_armed"] = True
    elif st.vars.get("rsi_armed") and r < cfg.rsi_fire:
        st.vars["rsi_armed"] = False
        return [_alert(st, b.start, "R6", "WARN", f"RSI({cfg.rsi_period})が{cfg.rsi_arm:.0f}超えから{r:.0f}へ反落")]
    return []


def r7_rebound(st: SymbolState, b: Bar, cfg: RuleConfig) -> list[Alert]:
    bars = list(st.bars)[-cfg.rebound_window_bars:]
    if len(bars) < cfg.rebound_hold_bars + 4 or not st.peak_bar_vol:
        return []
    cur, prev = bars[-1], bars[-2]
    low_i = min(range(len(bars) - 1), key=lambda i: bars[i].low)  # 現在足を除く安値
    low = bars[low_i].low
    hi = st.day_high
    if not hi or (hi - low) / hi < cfg.rebound_min_drawdown:
        return []
    hold = bars[low_i + 1:-1]
    if len(hold) < cfg.rebound_hold_bars or cur.low < low:  # ① 安値を更新しない足が2本以上
        return []
    prior3 = bars[-4:-1]
    avg3 = sum(x.volume for x in prior3) / 3
    if avg3 > st.peak_bar_vol * cfg.rebound_dry_ratio:  # ② 売りが枯れている
        return []
    if not (cur.close > prev.high and cur.volume >= avg3 * cfg.rebound_vol_mult):  # ③ 出来高を伴う上抜け
        return []
    if not st.cooled("R7", b.start, cfg.cooldown_sec):
        return []
    return [_alert(st, b.start, "R7", "BUY",
                   f"切り返し3条件成立：安値{_fmt(low)}を割らず、前足高値{_fmt(prev.high)}を出来高{cur.volume / max(avg3, 1):.1f}倍で上抜け 損切り{_fmt(low)}",
                   stop=low)]


def r8_arm(st: SymbolState, b: Bar, cfg: RuleConfig) -> list[Alert]:
    arm = st.vars.get("r8")
    if arm:
        arm["left"] -= 1
        if arm["left"] <= 0:
            st.vars["r8"] = None
    t = st.turnover
    if t is None or not (cfg.r8_turnover_low <= t <= cfg.r8_turnover_high):
        return []
    prior = list(st.bars)[-11:-1]
    if len(prior) < 5:
        return []
    avg = sum(x.volume for x in prior) / len(prior)
    body = (b.open - b.close) / b.open if b.open else 0
    if b.bearish and body >= cfg.r8_min_body and b.volume >= avg * cfg.r8_vol_mult:
        st.vars["r8"] = {"trigger": b.high, "stop": b.low, "left": cfg.r8_expire_bars}
        return [_alert(st, b.start, "R8", "ARM",
                       f"回転率{t:.0%}で大陰線（実体{body:.1%}・出来高{b.volume / max(avg, 1):.1f}倍）→ {_fmt(b.high)}上抜けで買い")]
    return []


SNAPSHOT_RULES = [r1_turnover, r2_vwap_dev, r4_double_top, r5_board, r8_trigger, r9_breakout]
BAR_RULES = [r3_stall, r6_rsi, r7_rebound, r8_arm]
