"""Agent manager for multi-agent routing."""

from __future__ import annotations

from typing import Any

from kane.agents.base import BaseAgent
from kane.agents.llm import LLMClient
from kane.config.settings import Settings
from kane.skills.registry import SkillRegistry


class AgentManager:
    """Manages multiple agents and routes messages to the correct one."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._agents: dict[str, BaseAgent] = {}
        self._routing_rules: list[RoutingRule] = []

    def create_agent(
        self,
        agent_id: str,
        llm: LLMClient,
        skill_registry: SkillRegistry,
    ) -> BaseAgent:
        """Create and register a new agent."""
        agent = BaseAgent(
            agent_id=agent_id,
            settings=self._settings,
            llm=llm,
            skill_registry=skill_registry,
        )
        self._agents[agent_id] = agent
        return agent

    def get_agent(self, agent_id: str) -> BaseAgent | None:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent. Returns True if it existed."""
        return self._agents.pop(agent_id, None) is not None

    def list_agents(self) -> list[str]:
        """Return all agent IDs."""
        return list(self._agents.keys())

    def add_routing_rule(self, rule: RoutingRule) -> None:
        """Add a routing rule for message dispatch."""
        self._routing_rules.append(rule)

    def resolve_agent(
        self, channel: str, sender: str, metadata: dict[str, Any] | None = None,
    ) -> BaseAgent | None:
        """Resolve which agent should handle a message based on routing rules."""
        for rule in self._routing_rules:
            if rule.matches(channel, sender, metadata):
                agent = self._agents.get(rule.agent_id)
                if agent is not None:
                    return agent

        # Fallback to default agent
        default_id = self._settings.default_agent
        return self._agents.get(default_id)


class RoutingRule:
    """A rule that maps channel/sender patterns to an agent."""

    def __init__(
        self,
        agent_id: str,
        channel: str | None = None,
        sender: str | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.channel = channel
        self.sender = sender

    def matches(
        self, channel: str, sender: str, metadata: dict[str, Any] | None = None,
    ) -> bool:
        if self.channel and self.channel != channel:
            return False
        if self.sender and self.sender != sender:
            return False
        return True
