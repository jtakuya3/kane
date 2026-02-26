"""Session management for Kane gateway."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    """Represents a user session with an agent."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    agent_id: str = ""
    channel: str = ""
    sender: str = ""
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Update the last_active timestamp."""
        self.last_active = time.time()


class SessionManager:
    """Manages active sessions."""

    def __init__(self, session_timeout: float = 3600.0) -> None:
        self._sessions: dict[str, Session] = {}
        self._sender_sessions: dict[str, str] = {}  # sender -> session_id
        self._timeout = session_timeout

    def get_or_create(
        self, channel: str, sender: str, agent_id: str = ""
    ) -> Session:
        """Get an existing session for a sender, or create a new one."""
        key = f"{channel}:{sender}"
        session_id = self._sender_sessions.get(key)

        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            if time.time() - session.last_active < self._timeout:
                session.touch()
                return session
            # Expired
            self._cleanup_session(session_id)

        session = Session(agent_id=agent_id, channel=channel, sender=sender)
        self._sessions[session.id] = session
        self._sender_sessions[key] = session.id
        return session

    def get(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        """Remove a session."""
        self._cleanup_session(session_id)

    def _cleanup_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            key = f"{session.channel}:{session.sender}"
            self._sender_sessions.pop(key, None)

    def active_count(self) -> int:
        """Return the number of active sessions."""
        return len(self._sessions)

    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns the count of removed sessions."""
        now = time.time()
        expired = [
            sid
            for sid, s in self._sessions.items()
            if now - s.last_active >= self._timeout
        ]
        for sid in expired:
            self._cleanup_session(sid)
        return len(expired)
