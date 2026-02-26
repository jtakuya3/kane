"""Tests for the agents module."""

import pytest

from kane.agents.llm import LLMClient, LLMResponse, ToolCall
from kane.agents.manager import AgentManager, RoutingRule
from kane.config.settings import Settings, LLMConfig
from kane.skills.registry import SkillRegistry


class TestLLMResponse:
    def test_text_response(self) -> None:
        response = LLMResponse(content="Hello!")
        assert response.content == "Hello!"
        assert response.has_tool_calls is False

    def test_tool_calls(self) -> None:
        tc = ToolCall(id="tc1", name="shell", arguments={"command": "ls"})
        response = LLMResponse(content="", tool_calls=[tc])
        assert response.has_tool_calls is True
        assert response.tool_calls[0].name == "shell"


class TestToolCall:
    def test_repr(self) -> None:
        tc = ToolCall(id="tc1", name="shell", arguments={})
        assert "shell" in repr(tc)


class TestAgentManager:
    def test_create_and_get_agent(self) -> None:
        settings = Settings()
        manager = AgentManager(settings)
        llm = LLMClient(LLMConfig())
        registry = SkillRegistry()

        agent = manager.create_agent("test_agent", llm, registry)
        assert manager.get_agent("test_agent") is agent

    def test_list_agents(self) -> None:
        settings = Settings()
        manager = AgentManager(settings)
        llm = LLMClient(LLMConfig())
        registry = SkillRegistry()

        manager.create_agent("agent1", llm, registry)
        manager.create_agent("agent2", llm, registry)
        assert sorted(manager.list_agents()) == ["agent1", "agent2"]

    def test_remove_agent(self) -> None:
        settings = Settings()
        manager = AgentManager(settings)
        llm = LLMClient(LLMConfig())
        registry = SkillRegistry()

        manager.create_agent("agent1", llm, registry)
        assert manager.remove_agent("agent1") is True
        assert manager.get_agent("agent1") is None
        assert manager.remove_agent("agent1") is False

    def test_resolve_agent_default(self) -> None:
        settings = Settings()
        settings.default_agent = "default"
        manager = AgentManager(settings)
        llm = LLMClient(LLMConfig())
        registry = SkillRegistry()

        manager.create_agent("default", llm, registry)
        agent = manager.resolve_agent("cli", "user1")
        assert agent is not None
        assert agent.agent_id == "default"

    def test_routing_rules(self) -> None:
        settings = Settings()
        manager = AgentManager(settings)
        llm = LLMClient(LLMConfig())
        registry = SkillRegistry()

        manager.create_agent("cli_agent", llm, registry)
        manager.create_agent("webhook_agent", llm, registry)

        manager.add_routing_rule(RoutingRule(agent_id="cli_agent", channel="cli"))
        manager.add_routing_rule(RoutingRule(agent_id="webhook_agent", channel="webhook"))

        assert manager.resolve_agent("cli", "user1").agent_id == "cli_agent"
        assert manager.resolve_agent("webhook", "user1").agent_id == "webhook_agent"


class TestRoutingRule:
    def test_matches_channel(self) -> None:
        rule = RoutingRule(agent_id="a", channel="cli")
        assert rule.matches("cli", "user1") is True
        assert rule.matches("webhook", "user1") is False

    def test_matches_sender(self) -> None:
        rule = RoutingRule(agent_id="a", sender="vip_user")
        assert rule.matches("cli", "vip_user") is True
        assert rule.matches("cli", "regular_user") is False

    def test_matches_all(self) -> None:
        rule = RoutingRule(agent_id="a")
        assert rule.matches("cli", "anyone") is True
