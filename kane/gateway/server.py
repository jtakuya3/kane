"""Gateway server - the central control plane for Kane."""

from __future__ import annotations

import asyncio
from typing import Any

from kane.agents.llm import LLMClient
from kane.agents.manager import AgentManager
from kane.channels.base import BaseChannel
from kane.channels.cli import CLIChannel
from kane.channels.webhook import WebhookChannel
from kane.config.settings import Settings
from kane.gateway.router import MessageRouter
from kane.gateway.session import SessionManager
from kane.skills.builtin.file_manager import FileManagerSkill
from kane.skills.builtin.shell import ShellSkill
from kane.skills.builtin.web_search import WebSearchSkill
from kane.skills.registry import SkillRegistry


class Gateway:
    """Central gateway that ties together channels, agents, skills, and sessions.

    This is the main entry point for running Kane. It initializes all components,
    starts channels, and manages the event loop.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._session_manager = SessionManager()
        self._agent_manager = AgentManager(self._settings)
        self._router = MessageRouter(self._agent_manager, self._session_manager)
        self._channels: list[BaseChannel] = []
        self._running = False

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def agent_manager(self) -> AgentManager:
        return self._agent_manager

    @property
    def session_manager(self) -> SessionManager:
        return self._session_manager

    def setup(self) -> None:
        """Initialize default agents, skills, and channels."""
        # Create skill registry with built-in skills
        registry = self._create_default_skill_registry()

        # Create LLM client
        llm = LLMClient(self._settings.llm)

        # Create default agent
        self._agent_manager.create_agent(
            agent_id=self._settings.default_agent,
            llm=llm,
            skill_registry=registry,
        )

        # Set up channels
        self._setup_channels()

    def _create_default_skill_registry(self) -> SkillRegistry:
        """Create a skill registry with default built-in skills."""
        registry = SkillRegistry()
        enabled = set(self._settings.enabled_skills)

        if "shell" in enabled:
            registry.register(ShellSkill())
        if "web_search" in enabled:
            registry.register(WebSearchSkill())
        if "file_manager" in enabled:
            registry.register(FileManagerSkill())

        return registry

    def _setup_channels(self) -> None:
        """Initialize and register enabled channels."""
        enabled = set(self._settings.enabled_channels)

        if "cli" in enabled:
            channel = CLIChannel()
            self._router.register_channel(channel)
            self._channels.append(channel)

        if "webhook" in enabled:
            channel = WebhookChannel(
                host=self._settings.gateway.host,
                port=self._settings.gateway.port + 1,  # Use next port
            )
            self._router.register_channel(channel)
            self._channels.append(channel)

    async def start(self) -> None:
        """Start the gateway and all channels."""
        self._running = True
        tasks = []
        for channel in self._channels:
            tasks.append(asyncio.create_task(channel.start()))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        """Stop the gateway and all channels."""
        self._running = False
        for channel in self._channels:
            await channel.stop()

    def run(self) -> None:
        """Set up and run the gateway (blocking)."""
        self.setup()
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            print("\nShutting down...")
