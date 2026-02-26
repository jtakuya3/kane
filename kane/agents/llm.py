"""LLM client abstraction supporting multiple providers."""

from __future__ import annotations

import json
import urllib.request
import asyncio
from typing import Any

from kane.config.settings import LLMConfig


class LLMClient:
    """Model-agnostic LLM client that supports OpenAI-compatible APIs."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    @property
    def _base_url(self) -> str:
        if self._config.base_url:
            return self._config.base_url.rstrip("/")
        providers = {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1",
        }
        return providers.get(self._config.provider, "https://api.openai.com/v1")

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to the LLM."""
        if self._config.provider == "anthropic":
            return await self._chat_anthropic(messages, tools, system_prompt)
        return await self._chat_openai(messages, tools, system_prompt)

    async def _chat_openai(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """OpenAI-compatible chat completion."""
        all_messages = list(messages)
        if system_prompt:
            all_messages.insert(0, {"role": "system", "content": system_prompt})

        body: dict[str, Any] = {
            "model": self._config.model,
            "messages": all_messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }
        if tools:
            body["tools"] = tools

        data = await self._post(f"{self._base_url}/chat/completions", body)
        choice = data["choices"][0]
        message = choice["message"]

        tool_calls = []
        for tc in message.get("tool_calls", []):
            tool_calls.append(ToolCall(
                id=tc["id"],
                name=tc["function"]["name"],
                arguments=json.loads(tc["function"]["arguments"]),
            ))

        return LLMResponse(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            raw=data,
        )

    async def _chat_anthropic(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Anthropic Claude API chat completion."""
        body: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "max_tokens": self._config.max_tokens,
        }
        if system_prompt:
            body["system"] = system_prompt
        if tools:
            # Convert OpenAI tool format to Anthropic format
            anthropic_tools = []
            for t in tools:
                func = t.get("function", {})
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {}),
                })
            body["tools"] = anthropic_tools

        data = await self._post(f"{self._base_url}/messages", body, anthropic=True)

        content_text = ""
        tool_calls = []
        for block in data.get("content", []):
            if block["type"] == "text":
                content_text += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCall(
                    id=block["id"],
                    name=block["name"],
                    arguments=block["input"],
                ))

        return LLMResponse(content=content_text, tool_calls=tool_calls, raw=data)

    async def _post(
        self, url: str, body: dict[str, Any], anthropic: bool = False
    ) -> dict[str, Any]:
        """Send a POST request."""
        def _do() -> dict[str, Any]:
            payload = json.dumps(body).encode("utf-8")
            headers: dict[str, str] = {"Content-Type": "application/json"}

            if anthropic:
                headers["x-api-key"] = self._config.api_key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {self._config.api_key}"

            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))

        return await asyncio.get_event_loop().run_in_executor(None, _do)


class ToolCall:
    """Represents an LLM tool call request."""

    def __init__(self, id: str, name: str, arguments: dict[str, Any]) -> None:
        self.id = id
        self.name = name
        self.arguments = arguments

    def __repr__(self) -> str:
        return f"ToolCall(id={self.id!r}, name={self.name!r})"


class LLMResponse:
    """Response from an LLM API call."""

    def __init__(
        self,
        content: str = "",
        tool_calls: list[ToolCall] | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls or []
        self.raw = raw or {}

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0
