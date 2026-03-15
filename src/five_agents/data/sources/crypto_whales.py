"""Whale Alert + CoinGecko — Large crypto transactions and prices."""

import asyncio
import os
from datetime import datetime

import requests

from ..base import DataCategory, DataPoint, DataSource, UpdateFrequency


class CoinGeckoSource(DataSource):
    name = "coingecko"
    category = DataCategory.CRYPTO
    frequency = UpdateFrequency.REALTIME
    requires_api_key = False

    API_URL = "https://api.coingecko.com/api/v3"

    def is_available(self) -> bool:
        return True

    async def fetch(self) -> list[DataPoint]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[DataPoint]:
        points = []
        try:
            resp = requests.get(
                f"{self.API_URL}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 20,
                    "page": 1,
                    "sparkline": "false",
                    "price_change_percentage": "24h,7d",
                },
                timeout=10,
            )
            resp.raise_for_status()

            for coin in resp.json():
                symbol = coin["symbol"].upper()
                price = coin["current_price"]
                change_24h = coin.get("price_change_percentage_24h", 0) or 0
                change_7d = coin.get("price_change_percentage_7d_in_currency", 0) or 0
                mcap = coin.get("market_cap", 0)

                sign = "+" if change_24h >= 0 else ""
                content = f"${price:,.2f} ({sign}{change_24h:.1f}% 24h) MCap: ${mcap/1e9:.1f}B"

                points.append(DataPoint(
                    source=self.name,
                    category=self.category,
                    timestamp=datetime.now(),
                    title=f"{coin['name']} ({symbol})",
                    content=content,
                    relevance_tickers=[f"{symbol}-USD"],
                    metadata={
                        "price": price,
                        "change_24h": change_24h,
                        "change_7d": change_7d,
                        "market_cap": mcap,
                    },
                ))
        except Exception:
            pass

        return points


class WhaleAlertSource(DataSource):
    name = "whale_alert"
    category = DataCategory.CRYPTO
    frequency = UpdateFrequency.REALTIME
    requires_api_key = True
    api_key_env_var = "WHALE_ALERT_API_KEY"

    API_URL = "https://api.whale-alert.io/v1/transactions"

    def is_available(self) -> bool:
        return bool(os.environ.get(self.api_key_env_var))

    async def fetch(self) -> list[DataPoint]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[DataPoint]:
        api_key = os.environ.get(self.api_key_env_var)
        if not api_key:
            return []

        points = []
        try:
            import time

            resp = requests.get(
                self.API_URL,
                params={
                    "api_key": api_key,
                    "min_value": 1000000,
                    "start": int(time.time()) - 3600,
                },
                timeout=10,
            )
            resp.raise_for_status()

            for tx in resp.json().get("transactions", [])[:10]:
                symbol = tx.get("symbol", "???").upper()
                amount = tx.get("amount", 0)
                amount_usd = tx.get("amount_usd", 0)
                from_owner = tx.get("from", {}).get("owner_type", "unknown")
                to_owner = tx.get("to", {}).get("owner_type", "unknown")

                content = (
                    f"{amount:,.0f} {symbol} (${amount_usd/1e6:.1f}M) "
                    f"{from_owner} → {to_owner}"
                )

                points.append(DataPoint(
                    source=self.name,
                    category=self.category,
                    timestamp=datetime.fromtimestamp(tx.get("timestamp", 0)),
                    title=f"🐋 Whale: {symbol}",
                    content=content,
                    relevance_tickers=[f"{symbol}-USD"],
                    metadata=tx,
                ))
        except Exception:
            pass

        return points
