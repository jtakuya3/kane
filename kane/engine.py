"""スナップショットを受け取り、足を作ってルールを回す。ライブとリプレイで共通。"""
from __future__ import annotations

from datetime import date, datetime

from .config import RuleConfig, SymbolInfo
from .models import Alert, Bar, Snapshot
from .rules import BAR_RULES, SNAPSHOT_RULES
from .state import SymbolState


class Engine:
    def __init__(self, symbols: list[SymbolInfo], rules: RuleConfig, on_bar=None):
        self.symbols = {s.code: s for s in symbols}
        self.rules = rules
        self.on_bar = on_bar  # 確定足のコールバック（録画用）
        self._day: date | None = None
        self.states: dict[str, SymbolState] = {}

    def _reset_if_new_day(self, ts: datetime):
        if self._day != ts.date():
            self._day = ts.date()
            self.states = {
                c: SymbolState(info, self.rules.breakout_default_vol5m_ratio)
                for c, info in self.symbols.items()
            }

    def process(self, snap: Snapshot) -> list[Alert]:
        self._reset_if_new_day(snap.ts)
        st = self.states.get(snap.symbol)
        if st is None:
            return []
        alerts = self._bars(st, st.update(snap))
        for rule in SNAPSHOT_RULES:
            alerts += rule(st, snap, self.rules)
        return alerts

    def tick(self, now: datetime) -> list[Alert]:
        """出来高が無くても分が変われば足を確定させる（毎秒呼ぶ）。"""
        if self._day != now.date():
            return []
        alerts = []
        for st in self.states.values():
            alerts += self._bars(st, st.close_due(now))
        return alerts

    def _bars(self, st: SymbolState, bars: list[Bar]) -> list[Alert]:
        alerts = []
        for b in bars:
            if self.on_bar:
                self.on_bar(st, b)
            for rule in BAR_RULES:
                alerts += rule(st, b, self.rules)
        return alerts
