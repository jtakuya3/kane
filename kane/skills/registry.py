"""Skill registry for managing available skills."""

from __future__ import annotations

from typing import Any

from kane.skills.base import BaseSkill, SkillResult


class SkillRegistry:
    """Central registry for discovering and managing skills."""

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        """Register a skill by its name."""
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> bool:
        """Unregister a skill. Returns True if it existed."""
        return self._skills.pop(name, None) is not None

    def get(self, name: str) -> BaseSkill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[BaseSkill]:
        """Return all registered skills."""
        return list(self._skills.values())

    def get_tool_specs(self) -> list[dict[str, Any]]:
        """Get LLM tool specs for all registered skills."""
        return [skill.to_tool_spec() for skill in self._skills.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> SkillResult:
        """Execute a skill by name."""
        skill = self._skills.get(name)
        if skill is None:
            return SkillResult(
                success=False, error=f"Skill '{name}' not found."
            )
        return await skill.execute(params)

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills
