"""Capitol Trades — US Congressional stock trading disclosures."""

import asyncio
from datetime import datetime

import requests

from ..base import DataCategory, DataPoint, DataSource, UpdateFrequency


class CongressTradesSource(DataSource):
    name = "congress_trades"
    category = DataCategory.POLITICAL
    frequency = UpdateFrequency.DAILY
    requires_api_key = False

    # Capitol Trades has no official API, scrape the public page
    API_URL = "https://www.capitoltrades.com/trades?page=1&pageSize=20"
    QUIVER_URL = "https://api.quiverquant.com/beta/live/congresstrading"

    def is_available(self) -> bool:
        return True

    async def fetch(self) -> list[DataPoint]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[DataPoint]:
        # Try ApeWisdom-style free endpoints first, fallback to scraping
        return self._fetch_via_house_senate()

    def _fetch_via_house_senate(self) -> list[DataPoint]:
        """Fetch from House/Senate disclosure RSS/XML feeds."""
        points = []
        try:
            import feedparser

            # Senate financial disclosures
            feed = feedparser.parse(
                "https://efdsearch.senate.gov/search/view/ptr/"
            )
            # This is HTML, not RSS. Use alternative approach.

            # Fallback: use a known aggregator
            headers = {"User-Agent": "FiveAgents/1.0 (research)"}
            resp = requests.get(
                "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json",
                headers=headers,
                timeout=15,
            )

            if resp.status_code == 200:
                transactions = resp.json()
                # Sort by date, take most recent
                transactions.sort(
                    key=lambda t: t.get("transaction_date", ""),
                    reverse=True,
                )

                for tx in transactions[:20]:
                    rep = tx.get("representative", "Unknown")
                    ticker = tx.get("ticker", "N/A")
                    tx_type = tx.get("type", "")
                    amount = tx.get("amount", "")
                    tx_date = tx.get("transaction_date", "")

                    if ticker == "--" or not ticker:
                        continue

                    content = f"{tx_type} {amount} on {tx_date}"
                    points.append(DataPoint(
                        source=self.name,
                        category=self.category,
                        timestamp=datetime.now(),
                        title=f"議員取引: {rep} → ${ticker}",
                        content=content,
                        relevance_tickers=[ticker] if ticker != "N/A" else [],
                        metadata=tx,
                    ))
        except Exception:
            pass

        return points
