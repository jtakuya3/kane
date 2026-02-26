"""Conversation history management."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    channel: str = ""
    metadata: dict = field(default_factory=dict)


class ConversationHistory:
    """Manages conversation history for a session, with persistence."""

    def __init__(self, session_id: str, storage_dir: Path) -> None:
        self.session_id = session_id
        self._storage_dir = storage_dir
        self._messages: list[Message] = []
        self._load()

    @property
    def _file_path(self) -> Path:
        return self._storage_dir / f"{self.session_id}.json"

    def _load(self) -> None:
        if self._file_path.exists():
            data = json.loads(self._file_path.read_text(encoding="utf-8"))
            self._messages = [Message(**m) for m in data]

    def _save(self) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._file_path.write_text(
            json.dumps([asdict(m) for m in self._messages], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add(self, message: Message) -> None:
        """Add a message to history."""
        self._messages.append(message)
        self._save()

    def get_messages(self, limit: int | None = None) -> list[Message]:
        """Get recent messages, optionally limited."""
        if limit is None:
            return list(self._messages)
        return list(self._messages[-limit:])

    def to_llm_format(self, limit: int | None = None) -> list[dict[str, str]]:
        """Convert messages to the format expected by LLM APIs."""
        messages = self.get_messages(limit)
        return [{"role": m.role, "content": m.content} for m in messages]

    def clear(self) -> None:
        """Clear conversation history."""
        self._messages.clear()
        self._save()

    def __len__(self) -> int:
        return len(self._messages)
