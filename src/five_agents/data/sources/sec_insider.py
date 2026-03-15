"""SEC EDGAR — Insider trading (Form 4) monitoring."""

import asyncio
from datetime import datetime

import requests

from ..base import DataCategory, DataPoint, DataSource, UpdateFrequency


class SecInsiderSource(DataSource):
    name = "sec_insider"
    category = DataCategory.INSIDER
    frequency = UpdateFrequency.DAILY
    requires_api_key = False

    RECENT_FILINGS_URL = "https://efts.sec.gov/LATEST/search-index?q=%22Form+4%22&dateRange=custom&startdt={date}&enddt={date}&forms=4"
    FULL_TEXT_URL = "https://efts.sec.gov/LATEST/search-index"

    def is_available(self) -> bool:
        return True

    async def fetch(self) -> list[DataPoint]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[DataPoint]:
        points = []
        try:
            headers = {
                "User-Agent": "FiveAgents/1.0 (investment-research@example.com)",
                "Accept": "application/json",
            }
            resp = requests.get(
                "https://efts.sec.gov/LATEST/search-index",
                params={
                    "q": '"Form 4"',
                    "forms": "4",
                    "dateRange": "custom",
                    "startdt": datetime.now().strftime("%Y-%m-%d"),
                    "enddt": datetime.now().strftime("%Y-%m-%d"),
                },
                headers=headers,
                timeout=15,
            )

            if resp.status_code != 200:
                # Fallback: use RSS feed
                return self._fetch_via_rss()

            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])

            for hit in hits[:20]:
                source_data = hit.get("_source", {})
                entity = source_data.get("entity_name", "Unknown")
                form_type = source_data.get("form_type", "4")
                filed = source_data.get("file_date", "")

                points.append(DataPoint(
                    source=self.name,
                    category=self.category,
                    timestamp=datetime.now(),
                    title=f"Form 4: {entity}",
                    content=f"Filed {filed}",
                    metadata={"entity": entity, "form_type": form_type},
                ))
        except Exception:
            return self._fetch_via_rss()

        return points

    def _fetch_via_rss(self) -> list[DataPoint]:
        """Fallback: fetch recent Form 4 filings via EDGAR RSS."""
        try:
            import feedparser

            feed = feedparser.parse(
                "https://www.sec.gov/cgi-bin/browse-edgar"
                "?action=getcurrent&type=4&dateb=&owner=include&count=20&search_text=&output=atom"
            )
            points = []
            for entry in feed.entries[:20]:
                points.append(DataPoint(
                    source=self.name,
                    category=self.category,
                    timestamp=datetime.now(),
                    title=entry.get("title", "Form 4 Filing")[:100],
                    content=entry.get("summary", "")[:200],
                    metadata={"link": entry.get("link", "")},
                ))
            return points
        except Exception:
            return []
