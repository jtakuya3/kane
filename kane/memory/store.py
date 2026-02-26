"""Key-value memory store with JSON file persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MemoryStore:
    """Simple persistent key-value store backed by a JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value by key."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value and persist to disk."""
        self._data[key] = value
        self._save()

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if the key existed."""
        if key in self._data:
            del self._data[key]
            self._save()
            return True
        return False

    def keys(self) -> list[str]:
        """Return all keys."""
        return list(self._data.keys())

    def clear(self) -> None:
        """Remove all data."""
        self._data.clear()
        self._save()

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)
