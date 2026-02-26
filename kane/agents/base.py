"""Base agent with LLM integration and skill execution loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kane.agents.llm import LLMClient, LLMResponse
from kane.config.settings import Settings
from kane.memory.conversation import ConversationHistory, Message
from kane.memory.store import MemoryStore
from kane.skills.registry import SkillRegistry


class BaseAgent:
    """An AI agent that uses an LLM and skills to respond to messages."""

    def __init__(
        self,
        agent_id: str,
        settings: Settings,
        llm: LLMClient,
        skill_registry: SkillRegistry,
    ) -> None:
        self.agent_id = agent_id
        self._settings = settings
        self._llm = llm
        self._skills = skill_registry
        self._store = MemoryStore(
            settings.config_dir / "agents" / agent_id / "memory.json"
        )
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        personality = self._store.get("personality", "")
        skills_list = ", ".join(s.name for s in self._skills.list_skills())
        return (
            "You are Kane, a helpful personal AI assistant. "
            "You can use the available tools to help the user.\n"
            f"Available skills: {skills_list}\n"
            f"{personality}"
        ).strip()

    async def process(
        self,
        user_message: str,
        session_id: str,
        channel: str = "",
    ) -> str:
        """Process a user message and return a response.

        Implements the agent loop: LLM call -> tool calls -> LLM call -> ...
        until the LLM produces a text response without tool calls.
        """
        conversations_dir = (
            self._settings.config_dir / "agents" / self.agent_id / "sessions"
        )
        history = ConversationHistory(session_id, conversations_dir)
        history.add(Message(role="user", content=user_message, channel=channel))

        tools = self._skills.get_tool_specs() if len(self._skills) > 0 else None
        messages = history.to_llm_format()

        max_iterations = 10
        for _ in range(max_iterations):
            response = await self._llm.chat(
                messages=messages,
                tools=tools,
                system_prompt=self._system_prompt,
            )

            if not response.has_tool_calls:
                # Final text response
                reply = response.content or "(No response)"
                history.add(Message(role="assistant", content=reply, channel=channel))
                return reply

            # Execute tool calls
            for tool_call in response.tool_calls:
                result = await self._skills.execute(
                    tool_call.name, tool_call.arguments
                )
                # Add tool result to conversation for context
                tool_msg = (
                    f"[Tool: {tool_call.name}] "
                    f"{'Success' if result.success else 'Error'}: "
                    f"{result.output or result.error}"
                )
                messages.append({"role": "assistant", "content": response.content or ""})
                messages.append({"role": "user", "content": tool_msg})

        # Fallback if loop exhausts
        fallback = "I've reached the maximum number of steps. Here's what I have so far."
        if response.content:
            fallback = response.content
        history.add(Message(role="assistant", content=fallback, channel=channel))
        return fallback
