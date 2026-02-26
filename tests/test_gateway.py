"""Tests for the gateway module."""

import pytest

from kane.gateway.session import Session, SessionManager
from kane.gateway.router import MessageRouter
from kane.gateway.server import Gateway
from kane.agents.manager import AgentManager
from kane.config.settings import Settings
from kane.channels.base import InboundMessage, OutboundMessage, BaseChannel


class TestSession:
    def test_creation(self) -> None:
        session = Session(agent_id="agent1", channel="cli", sender="user1")
        assert session.agent_id == "agent1"
        assert session.channel == "cli"
        assert session.id  # auto-generated

    def test_touch(self) -> None:
        session = Session()
        old_time = session.last_active
        import time
        time.sleep(0.01)
        session.touch()
        assert session.last_active > old_time


class TestSessionManager:
    def test_get_or_create(self) -> None:
        manager = SessionManager()
        s1 = manager.get_or_create("cli", "user1", "agent1")
        s2 = manager.get_or_create("cli", "user1", "agent1")
        assert s1.id == s2.id  # same session

    def test_different_users_get_different_sessions(self) -> None:
        manager = SessionManager()
        s1 = manager.get_or_create("cli", "user1")
        s2 = manager.get_or_create("cli", "user2")
        assert s1.id != s2.id

    def test_expired_session(self) -> None:
        manager = SessionManager(session_timeout=0.0)
        s1 = manager.get_or_create("cli", "user1")
        import time
        time.sleep(0.01)
        s2 = manager.get_or_create("cli", "user1")
        assert s1.id != s2.id  # new session created

    def test_active_count(self) -> None:
        manager = SessionManager()
        manager.get_or_create("cli", "user1")
        manager.get_or_create("cli", "user2")
        assert manager.active_count() == 2

    def test_remove(self) -> None:
        manager = SessionManager()
        session = manager.get_or_create("cli", "user1")
        manager.remove(session.id)
        assert manager.active_count() == 0

    def test_cleanup_expired(self) -> None:
        manager = SessionManager(session_timeout=0.0)
        manager.get_or_create("cli", "user1")
        import time
        time.sleep(0.01)
        removed = manager.cleanup_expired()
        assert removed == 1
        assert manager.active_count() == 0


class MockChannel(BaseChannel):
    name = "mock"

    def __init__(self):
        super().__init__()
        self.sent_messages: list[OutboundMessage] = []

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send(self, message: OutboundMessage):
        self.sent_messages.append(message)


class TestGateway:
    def test_setup(self) -> None:
        settings = Settings()
        settings.enabled_channels = []  # don't start real channels
        gateway = Gateway(settings)
        gateway.setup()
        assert "default" in gateway.agent_manager.list_agents()

    def test_session_manager_accessible(self) -> None:
        gateway = Gateway()
        assert gateway.session_manager is not None
        assert gateway.session_manager.active_count() == 0
