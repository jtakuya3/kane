"""Base class for all data sources. New sources just subclass DataSource."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class UpdateFrequency(Enum):
    REALTIME = "realtime"  # < 60s
    HOURLY = "hourly"  # 1-6h
    DAILY = "daily"
    WEEKLY = "weekly"
    EVENT = "event"  # on-demand


class DataCategory(Enum):
    MARKET = "market"
    GEOPOLITICAL = "geopolitical"
    MACRO = "macro"
    SENTIMENT = "sentiment"
    SUPPLY_CHAIN = "supply_chain"
    INSIDER = "insider"
    POLITICAL = "political"
    PATENT = "patent"
    INFRASTRUCTURE = "infrastructure"
    WEATHER = "weather"
    CRYPTO = "crypto"
    FUNDAMENTAL = "fundamental"
    OSINT = "osint"
    ALTERNATIVE = "alternative"


@dataclass
class DataPoint:
    """A single piece of intelligence from any source."""

    source: str
    category: DataCategory
    timestamp: datetime
    title: str
    content: str
    relevance_tickers: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_brief(self) -> str:
        tickers = f" [{', '.join(self.relevance_tickers)}]" if self.relevance_tickers else ""
        return f"[{self.source}]{tickers} {self.title}: {self.content}"


class DataSource(ABC):
    """Base class for all data sources. Subclass and implement fetch()."""

    name: str
    category: DataCategory
    frequency: UpdateFrequency
    requires_api_key: bool = False
    api_key_env_var: str | None = None

    @abstractmethod
    async def fetch(self) -> list[DataPoint]:
        """Fetch latest data from this source. Returns list of DataPoints."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this source is configured and reachable."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} [{self.category.value}] freq={self.frequency.value}>"
