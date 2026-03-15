"""FRED (Federal Reserve Economic Data) — Macro indicators."""

import asyncio
import os
from datetime import datetime

import requests

from ..base import DataCategory, DataPoint, DataSource, UpdateFrequency

# Key series to monitor
FRED_SERIES = {
    "DGS10": "米国10年金利",
    "DGS2": "米国2年金利",
    "T10Y2Y": "イールドカーブ(10Y-2Y)",
    "UNRATE": "失業率",
    "CPIAUCSL": "CPI (消費者物価指数)",
    "FEDFUNDS": "FF金利",
    "DEXJPUS": "USD/JPY",
    "DCOILWTICO": "WTI原油",
    "VIXCLS": "VIX",
}


class FredMacroSource(DataSource):
    name = "fred"
    category = DataCategory.MACRO
    frequency = UpdateFrequency.DAILY
    requires_api_key = True
    api_key_env_var = "FRED_API_KEY"

    API_BASE = "https://api.stlouisfed.org/fred/series/observations"

    def is_available(self) -> bool:
        return bool(os.environ.get(self.api_key_env_var))

    async def fetch(self) -> list[DataPoint]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[DataPoint]:
        api_key = os.environ.get(self.api_key_env_var)
        if not api_key:
            return []

        points = []
        for series_id, label in FRED_SERIES.items():
            try:
                resp = requests.get(
                    self.API_BASE,
                    params={
                        "series_id": series_id,
                        "api_key": api_key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 2,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                obs = resp.json().get("observations", [])
                if not obs:
                    continue

                latest = float(obs[0]["value"]) if obs[0]["value"] != "." else None
                prev = float(obs[1]["value"]) if len(obs) > 1 and obs[1]["value"] != "." else None

                if latest is None:
                    continue

                change = ""
                if prev is not None:
                    diff = latest - prev
                    sign = "+" if diff >= 0 else ""
                    change = f" ({sign}{diff:.3f})"

                points.append(DataPoint(
                    source=self.name,
                    category=self.category,
                    timestamp=datetime.now(),
                    title=label,
                    content=f"{latest:.3f}{change}",
                    metadata={"series_id": series_id, "value": latest, "prev": prev},
                ))
            except Exception:
                continue

        return points
