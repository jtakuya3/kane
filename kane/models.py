"""共通のデータ型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Snapshot:
    """PUSH配信1回分（または録画CSVの1行）。"""

    ts: datetime
    symbol: str
    price: float
    volume: float  # 当日の累計出来高
    vwap: float | None = None
    high: float | None = None
    low: float | None = None
    open: float | None = None
    prev_close: float | None = None
    buy5: float | None = None  # 買い気配 上位5本の数量合計
    sell5: float | None = None  # 売り気配 上位5本の数量合計
    bid: float | None = None  # 最良買い気配
    ask: float | None = None  # 最良売り気配


@dataclass
class Bar:
    start: datetime  # 足の開始分（秒は0）
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def bearish(self) -> bool:
        return self.close < self.open


@dataclass
class Alert:
    ts: datetime
    symbol: str
    rule: str  # "R1" など
    level: str  # "50%" "BUY" など
    message: str
    price: float
    extras: dict = field(default_factory=dict)
