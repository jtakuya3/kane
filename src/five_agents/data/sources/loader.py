"""Auto-registers all available data sources. Add new source files and they'll be picked up."""

import logging

from ..registry import registry
from .yahoo_finance import YahooFinanceSource
from .fear_greed import FearGreedSource
from .fred_macro import FredMacroSource
from .gdelt_news import GdeltNewsSource
from .sec_insider import SecInsiderSource
from .crypto_whales import CoinGeckoSource, WhaleAlertSource
from .congress_trades import CongressTradesSource

logger = logging.getLogger(__name__)


def register_all_sources(watchlist: list[str] | None = None):
    """Register all data sources. Called once at startup."""
    sources = [
        YahooFinanceSource(watchlist=watchlist),
        FearGreedSource(),
        FredMacroSource(),
        GdeltNewsSource(),
        SecInsiderSource(),
        CoinGeckoSource(),
        WhaleAlertSource(),
        CongressTradesSource(),
    ]

    for source in sources:
        registry.register(source)

    available = registry.list_available()
    total = len(registry.list_sources())
    logger.info(f"Registered {total} sources, {len(available)} available")

    return registry
