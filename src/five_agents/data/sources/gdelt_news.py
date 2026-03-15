"""GDELT Project — Global news and conflict event monitoring."""

import asyncio
from datetime import datetime

import requests

from ..base import DataCategory, DataPoint, DataSource, UpdateFrequency


class GdeltNewsSource(DataSource):
    name = "gdelt"
    category = DataCategory.GEOPOLITICAL
    frequency = UpdateFrequency.HOURLY
    requires_api_key = False

    API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    def is_available(self) -> bool:
        return True

    async def fetch(self) -> list[DataPoint]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[DataPoint]:
        points = []

        queries = [
            ("market crash OR recession OR financial crisis", "金融危機シグナル"),
            ("military conflict OR war OR invasion", "軍事紛争"),
            ("sanctions OR trade war OR tariff", "制裁・貿易戦争"),
            ("central bank OR interest rate OR inflation", "金融政策"),
            ("oil supply OR OPEC OR energy crisis", "エネルギー"),
            ("semiconductor OR chip shortage OR AI regulation", "テック・半導体"),
        ]

        for query, label in queries:
            try:
                resp = requests.get(
                    self.API_URL,
                    params={
                        "query": query,
                        "mode": "ArtList",
                        "maxrecords": 5,
                        "format": "json",
                        "timespan": "24h",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                articles = data.get("articles", [])

                for article in articles[:3]:
                    title = article.get("title", "")
                    url = article.get("url", "")
                    domain = article.get("domain", "")
                    tone = article.get("tone", 0)

                    points.append(DataPoint(
                        source=self.name,
                        category=self.category,
                        timestamp=datetime.now(),
                        title=f"[{label}] {title[:80]}",
                        content=f"Tone: {tone:.1f} | {domain}",
                        metadata={"url": url, "tone": tone, "query_label": label},
                    ))
            except Exception:
                continue

        return points
