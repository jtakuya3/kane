"""Base skill interface for the plugin system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillResult:
    """Result returned from a skill execution."""

    success: bool
    output: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class BaseSkill(ABC):
    """Abstract base class for all skills (plugins)."""

    name: str = "base_skill"
    description: str = ""
    version: str = "0.1.0"

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> SkillResult:
        """Execute the skill with the given parameters."""

    def to_tool_spec(self) -> dict[str, Any]:
        """Convert this skill to an LLM tool/function spec."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters_schema(),
            },
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        """Return JSON Schema for skill parameters. Override in subclasses."""
        return {"type": "object", "properties": {}}
