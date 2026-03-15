"""Yahoo Finance — Stock prices, volume, fundamentals."""

import asyncio
from datetime import datetime

import yfinance as yf

from ..base import DataCategory, DataPoint, DataSource, UpdateFrequency


class YahooFinanceSource(DataSource):
    name = "yahoo_finance"
    category = DataCategory.MARKET
    frequency = UpdateFrequency.REALTIME
    requires_api_key = False

    def __init__(self, watchlist: list[str] | None = None):
        self.watchlist = watchlist or [
            "^GSPC",  # S&P 500
            "^DJI",  # Dow Jones
            "^IXIC",  # Nasdaq
            "^N225",  # Nikkei 225
            "^VIX",  # VIX
            "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META",
            "GC=F",  # Gold
            "CL=F",  # Oil
            "BTC-USD",
            "JPY=X",  # USD/JPY
        ]

    def is_available(self) -> bool:
        return True

    async def fetch(self) -> list[DataPoint]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[DataPoint]:
        points = []
        tickers = yf.Tickers(" ".join(self.watchlist))

        for symbol in self.watchlist:
            try:
                ticker = tickers.tickers.get(symbol)
                if not ticker:
                    continue
                info = ticker.fast_info
                hist = ticker.history(period="5d")
                if hist.empty:
                    continue

                close = hist["Close"].iloc[-1]
                prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else close
                change_pct = ((close - prev_close) / prev_close) * 100
                volume = hist["Volume"].iloc[-1]

                avg_vol_20d = None
                hist_20 = ticker.history(period="1mo")
                if len(hist_20) >= 5:
                    avg_vol_20d = hist_20["Volume"].mean()

                vol_ratio = volume / avg_vol_20d if avg_vol_20d and avg_vol_20d > 0 else None
                vol_alert = f" ⚠️出来高{vol_ratio:.1f}x平均" if vol_ratio and vol_ratio > 2.0 else ""

                sign = "+" if change_pct >= 0 else ""
                content = f"{close:,.2f} ({sign}{change_pct:.2f}%){vol_alert}"

                points.append(DataPoint(
                    source=self.name,
                    category=self.category,
                    timestamp=datetime.now(),
                    title=symbol,
                    content=content,
                    relevance_tickers=[symbol],
                    metadata={
                        "close": close,
                        "change_pct": change_pct,
                        "volume": volume,
                        "volume_ratio": vol_ratio,
                    },
                ))
            except Exception:
                continue

        return points
