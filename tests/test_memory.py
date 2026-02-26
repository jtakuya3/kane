"""Tests for the memory module."""

import json
from pathlib import Path

import pytest

from kane.memory.store import MemoryStore
from kane.memory.conversation import ConversationHistory, Message


class TestMemoryStore:
    def test_set_and_get(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "store.json")
        store.set("key1", "value1")
        assert store.get("key1") == "value1"

    def test_get_default(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "store.json")
        assert store.get("missing") is None
        assert store.get("missing", "fallback") == "fallback"

    def test_delete(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "store.json")
        store.set("key1", "value1")
        assert store.delete("key1") is True
        assert store.get("key1") is None
        assert store.delete("key1") is False

    def test_contains(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "store.json")
        store.set("key1", "value1")
        assert "key1" in store
        assert "missing" not in store

    def test_keys(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "store.json")
        store.set("a", 1)
        store.set("b", 2)
        assert sorted(store.keys()) == ["a", "b"]

    def test_clear(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "store.json")
        store.set("a", 1)
        store.clear()
        assert len(store) == 0

    def test_persistence(self, tmp_path: Path) -> None:
        path = tmp_path / "store.json"
        store1 = MemoryStore(path)
        store1.set("key1", "value1")

        store2 = MemoryStore(path)
        assert store2.get("key1") == "value1"

    def test_complex_values(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "store.json")
        store.set("nested", {"a": [1, 2, 3], "b": {"c": True}})
        assert store.get("nested") == {"a": [1, 2, 3], "b": {"c": True}}


class TestConversationHistory:
    def test_add_and_get(self, tmp_path: Path) -> None:
        history = ConversationHistory("session1", tmp_path)
        history.add(Message(role="user", content="Hello"))
        history.add(Message(role="assistant", content="Hi there!"))
        messages = history.get_messages()
        assert len(messages) == 2
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi there!"

    def test_get_with_limit(self, tmp_path: Path) -> None:
        history = ConversationHistory("session2", tmp_path)
        for i in range(5):
            history.add(Message(role="user", content=f"msg{i}"))
        messages = history.get_messages(limit=2)
        assert len(messages) == 2
        assert messages[0].content == "msg3"
        assert messages[1].content == "msg4"

    def test_to_llm_format(self, tmp_path: Path) -> None:
        history = ConversationHistory("session3", tmp_path)
        history.add(Message(role="user", content="What time is it?"))
        history.add(Message(role="assistant", content="I don't have a clock."))
        llm_msgs = history.to_llm_format()
        assert llm_msgs == [
            {"role": "user", "content": "What time is it?"},
            {"role": "assistant", "content": "I don't have a clock."},
        ]

    def test_persistence(self, tmp_path: Path) -> None:
        h1 = ConversationHistory("persist_test", tmp_path)
        h1.add(Message(role="user", content="Hello"))

        h2 = ConversationHistory("persist_test", tmp_path)
        assert len(h2) == 1
        assert h2.get_messages()[0].content == "Hello"

    def test_clear(self, tmp_path: Path) -> None:
        history = ConversationHistory("clear_test", tmp_path)
        history.add(Message(role="user", content="Hello"))
        history.clear()
        assert len(history) == 0
