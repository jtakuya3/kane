"""CNN Fear & Greed Index — Market sentiment indicator."""

import asyncio
from datetime import datetime

import requests

from ..base import DataCategory, DataPoint, DataSource, UpdateFrequency


class FearGreedSource(DataSource):
    name = "fear_greed"
    category = DataCategory.SENTIMENT
    frequency = UpdateFrequency.DAILY
    requires_api_key = False

    API_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

    def is_available(self) -> bool:
        return True

    async def fetch(self) -> list[DataPoint]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[DataPoint]:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(self.API_URL, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            score = data.get("fear_and_greed", {}).get("score", None)
            rating = data.get("fear_and_greed", {}).get("rating", "unknown")

            if score is None:
                return []

            return [DataPoint(
                source=self.name,
                category=self.category,
                timestamp=datetime.now(),
                title="Fear & Greed Index",
                content=f"Score: {score:.0f}/100 ({rating})",
                metadata={"score": score, "rating": rating},
            )]
        except Exception:
            return []
