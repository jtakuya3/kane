"""Data source registry. Auto-discovers and manages all sources."""

import asyncio
import logging
from datetime import datetime

from .base import DataCategory, DataPoint, DataSource, UpdateFrequency

logger = logging.getLogger(__name__)


class SourceRegistry:
    """Registry that manages all data sources. Add new sources with register()."""

    def __init__(self):
        self._sources: dict[str, DataSource] = {}

    def register(self, source: DataSource) -> None:
        self._sources[source.name] = source
        logger.info(f"Registered data source: {source}")

    def list_sources(self) -> list[DataSource]:
        return list(self._sources.values())

    def list_available(self) -> list[DataSource]:
        return [s for s in self._sources.values() if s.is_available()]

    def get_by_category(self, category: DataCategory) -> list[DataSource]:
        return [s for s in self._sources.values() if s.category == category]

    def get_by_frequency(self, freq: UpdateFrequency) -> list[DataSource]:
        return [s for s in self._sources.values() if s.frequency == freq]

    async def fetch_all(self, categories: list[DataCategory] | None = None) -> list[DataPoint]:
        """Fetch from all available sources (optionally filtered by category)."""
        sources = self.list_available()
        if categories:
            sources = [s for s in sources if s.category in categories]

        results: list[DataPoint] = []
        tasks = [self._safe_fetch(s) for s in sources]
        fetched = await asyncio.gather(*tasks)

        for points in fetched:
            results.extend(points)

        results.sort(key=lambda p: p.timestamp, reverse=True)
        logger.info(f"Fetched {len(results)} data points from {len(sources)} sources")
        return results

    async def _safe_fetch(self, source: DataSource) -> list[DataPoint]:
        try:
            return await source.fetch()
        except Exception as e:
            logger.error(f"Failed to fetch from {source.name}: {e}")
            return []


# Global registry instance
registry = SourceRegistry()


def build_shared_fact_sheet(data_points: list[DataPoint]) -> str:
    """Build the shared fact sheet that all 5 agents see."""
    now = datetime.now()
    lines = [
        f"# Shared Fact Sheet — {now.strftime('%Y/%m/%d %H:%M')} JST",
        f"Total signals: {len(data_points)}",
        "",
    ]

    by_category: dict[str, list[DataPoint]] = {}
    for dp in data_points:
        cat = dp.category.value
        by_category.setdefault(cat, []).append(dp)

    for cat_name, points in sorted(by_category.items()):
        lines.append(f"## [{cat_name.upper()}]")
        for p in points[:10]:
            lines.append(f"- {p.to_brief()}")
        if len(points) > 10:
            lines.append(f"  ...and {len(points) - 10} more")
        lines.append("")

    return "\n".join(lines)
