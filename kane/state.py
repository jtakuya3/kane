"""銘柄ごとの当日状態と、累計出来高からの1分足生成。"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta

from .config import SymbolInfo
from .models import Bar, Snapshot


def minute_of(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


class SymbolState:
    def __init__(self, info: SymbolInfo, default_vol5m_ratio: float):
        self.info = info
        self.bars: deque[Bar] = deque(maxlen=400)  # 確定した1分足
        self.cur: Bar | None = None  # 作成中の1分足
        self.last: Snapshot | None = None
        self._last_cum: float | None = None
        self.peak_bar_vol = 0.0
        self.peak_bar_start: datetime | None = None
        # ルールが使う状態
        self.fired: set = set()
        self.cool_until: dict = {}
        self.vars: dict = {}
        if info.breakout_vol5m:
            self.breakout_vol5m = info.breakout_vol5m
        elif info.float_shares:
            self.breakout_vol5m = info.float_shares * default_vol5m_ratio
        else:
            self.breakout_vol5m = None

    # ---- 1分足 ----
    def update(self, snap: Snapshot) -> list[Bar]:
        """スナップショットを取り込み、確定した足を返す。"""
        closed = self.close_due(snap.ts)
        if self._last_cum is None or snap.volume < self._last_cum:
            dv = 0.0  # 起動直後・日付替わりは基準だけ取る
        else:
            dv = snap.volume - self._last_cum
        self._last_cum = snap.volume
        m = minute_of(snap.ts)
        if self.cur is None:
            self.cur = Bar(m, snap.price, snap.price, snap.price, snap.price, dv)
        else:
            c = self.cur
            c.high = max(c.high, snap.price)
            c.low = min(c.low, snap.price)
            c.close = snap.price
            c.volume += dv
        self.last = snap
        return closed

    def close_due(self, now: datetime) -> list[Bar]:
        """分が変わっていれば作成中の足を確定する。"""
        if self.cur is None or minute_of(now) <= self.cur.start:
            return []
        bar = self.cur
        self.cur = None
        self.bars.append(bar)
        if bar.volume > self.peak_bar_vol:
            self.peak_bar_vol = bar.volume
            self.peak_bar_start = bar.start
        return [bar]

    # ---- 指標 ----
    @property
    def turnover(self) -> float | None:
        if not self.last or not self.info.float_shares:
            return None
        return self.last.volume / self.info.float_shares

    @property
    def vwap_dev(self) -> float | None:
        s = self.last
        if not s or not s.vwap:
            return None
        return s.price / s.vwap - 1

    @property
    def day_high(self) -> float | None:
        highs = [b.high for b in self.bars]
        if self.cur:
            highs.append(self.cur.high)
        if self.last and self.last.high:
            highs.append(self.last.high)
        return max(highs) if highs else None

    def rolling_vol(self, now: datetime, minutes: int = 5) -> float:
        """直近 minutes 分の出来高（作成中の足を含む）。"""
        since = minute_of(now) - timedelta(minutes=minutes - 1)
        v = sum(b.volume for b in self.bars if b.start >= since)
        if self.cur and self.cur.start >= since:
            v += self.cur.volume
        return v

    def rsi(self, period: int) -> float | None:
        closes = [b.close for b in self.bars]
        if len(closes) < period + 1:
            return None
        gains = losses = 0.0
        diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        for d in diffs[:period]:
            gains += max(d, 0)
            losses += max(-d, 0)
        ag, al = gains / period, losses / period
        for d in diffs[period:]:  # Wilderの平滑化
            ag = (ag * (period - 1) + max(d, 0)) / period
            al = (al * (period - 1) + max(-d, 0)) / period
        if al == 0:
            return 100.0
        return 100 - 100 / (1 + ag / al)

    # ---- 通知の重複防止 ----
    def once(self, key) -> bool:
        if key in self.fired:
            return False
        self.fired.add(key)
        return True

    def cooled(self, key, now: datetime, seconds: int) -> bool:
        until = self.cool_until.get(key)
        if until and now < until:
            return False
        self.cool_until[key] = now + timedelta(seconds=seconds)
        return True
