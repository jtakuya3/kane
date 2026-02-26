"""Web search skill using HTTP requests."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from kane.skills.base import BaseSkill, SkillResult


class WebSearchSkill(BaseSkill):
    """Perform web searches and return results."""

    name = "web_search"
    description = "Search the web for information and return summarized results."
    version = "0.1.0"

    def __init__(self, api_key: str = "", search_engine: str = "duckduckgo") -> None:
        self._api_key = api_key
        self._search_engine = search_engine

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return.",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> SkillResult:
        query = params.get("query", "")
        num_results = params.get("num_results", 5)

        if not query:
            return SkillResult(success=False, error="No query provided.")

        try:
            results = await self._search_duckduckgo(query, num_results)
            return SkillResult(
                success=True,
                output=self._format_results(results),
                data={"results": results},
            )
        except Exception as e:
            return SkillResult(success=False, error=f"Search failed: {e}")

    async def _search_duckduckgo(
        self, query: str, num_results: int
    ) -> list[dict[str, str]]:
        """Search using DuckDuckGo Instant Answer API."""
        import asyncio

        encoded = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1"

        def _fetch() -> list[dict[str, str]]:
            req = urllib.request.Request(url, headers={"User-Agent": "Kane/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results: list[dict[str, str]] = []

            # Abstract
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", ""),
                    "snippet": data["AbstractText"],
                    "url": data.get("AbstractURL", ""),
                })

            # Related topics
            for topic in data.get("RelatedTopics", [])[:num_results]:
                if "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:80],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", ""),
                    })

            return results[:num_results]

        return await asyncio.get_event_loop().run_in_executor(None, _fetch)

    def _format_results(self, results: list[dict[str, str]]) -> str:
        if not results:
            return "No results found."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   {r['snippet']}")
            if r.get("url"):
                lines.append(f"   URL: {r['url']}")
            lines.append("")
        return "\n".join(lines)
