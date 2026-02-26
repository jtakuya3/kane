"""Configuration and settings management for Kane."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_DIR = Path.home() / ".kane"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""

    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class GatewayConfig:
    """Configuration for the Gateway server."""

    host: str = "127.0.0.1"
    port: int = 8321
    debug: bool = False


@dataclass
class Settings:
    """Global settings for Kane."""

    config_dir: Path = field(default_factory=lambda: DEFAULT_CONFIG_DIR)
    llm: LLMConfig = field(default_factory=LLMConfig)
    gateway: GatewayConfig = field(default_factory=GatewayConfig)
    default_agent: str = "default"
    enabled_channels: list[str] = field(default_factory=lambda: ["cli"])
    enabled_skills: list[str] = field(
        default_factory=lambda: ["shell", "web_search", "file_manager"]
    )

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        """Load settings from a JSON config file."""
        path = path or DEFAULT_CONFIG_FILE
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls._from_dict(data)

    def save(self, path: Path | None = None) -> None:
        """Save settings to a JSON config file."""
        path = path or DEFAULT_CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Settings:
        settings = cls()
        if "config_dir" in data:
            settings.config_dir = Path(data["config_dir"])
        if "llm" in data:
            llm_data = data["llm"]
            settings.llm = LLMConfig(**{
                k: v for k, v in llm_data.items() if k in LLMConfig.__dataclass_fields__
            })
        if "gateway" in data:
            gw_data = data["gateway"]
            settings.gateway = GatewayConfig(**{
                k: v
                for k, v in gw_data.items()
                if k in GatewayConfig.__dataclass_fields__
            })
        if "default_agent" in data:
            settings.default_agent = data["default_agent"]
        if "enabled_channels" in data:
            settings.enabled_channels = data["enabled_channels"]
        if "enabled_skills" in data:
            settings.enabled_skills = data["enabled_skills"]
        return settings

    def _to_dict(self) -> dict[str, Any]:
        return {
            "config_dir": str(self.config_dir),
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "api_key": self.llm.api_key,
                "base_url": self.llm.base_url,
                "temperature": self.llm.temperature,
                "max_tokens": self.llm.max_tokens,
            },
            "gateway": {
                "host": self.gateway.host,
                "port": self.gateway.port,
                "debug": self.gateway.debug,
            },
            "default_agent": self.default_agent,
            "enabled_channels": self.enabled_channels,
            "enabled_skills": self.enabled_skills,
        }
