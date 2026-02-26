"""Tests for the skills module."""

import pytest

from kane.skills.base import BaseSkill, SkillResult
from kane.skills.registry import SkillRegistry
from kane.skills.builtin.shell import ShellSkill
from kane.skills.builtin.file_manager import FileManagerSkill


class EchoSkill(BaseSkill):
    """A simple test skill that echoes input."""

    name = "echo"
    description = "Echo input back."

    async def execute(self, params):
        text = params.get("text", "")
        return SkillResult(success=True, output=text)


class TestSkillRegistry:
    def test_register_and_get(self) -> None:
        registry = SkillRegistry()
        skill = EchoSkill()
        registry.register(skill)
        assert registry.get("echo") is skill
        assert "echo" in registry
        assert len(registry) == 1

    def test_unregister(self) -> None:
        registry = SkillRegistry()
        registry.register(EchoSkill())
        assert registry.unregister("echo") is True
        assert registry.get("echo") is None
        assert registry.unregister("echo") is False

    def test_list_skills(self) -> None:
        registry = SkillRegistry()
        registry.register(EchoSkill())
        skills = registry.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "echo"

    def test_get_tool_specs(self) -> None:
        registry = SkillRegistry()
        registry.register(EchoSkill())
        specs = registry.get_tool_specs()
        assert len(specs) == 1
        assert specs[0]["type"] == "function"
        assert specs[0]["function"]["name"] == "echo"

    @pytest.mark.asyncio
    async def test_execute(self) -> None:
        registry = SkillRegistry()
        registry.register(EchoSkill())
        result = await registry.execute("echo", {"text": "hello"})
        assert result.success is True
        assert result.output == "hello"

    @pytest.mark.asyncio
    async def test_execute_not_found(self) -> None:
        registry = SkillRegistry()
        result = await registry.execute("missing", {})
        assert result.success is False
        assert "not found" in result.error


class TestShellSkill:
    @pytest.mark.asyncio
    async def test_basic_command(self) -> None:
        skill = ShellSkill()
        result = await skill.execute({"command": "echo hello"})
        assert result.success is True
        assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_empty_command(self) -> None:
        skill = ShellSkill()
        result = await skill.execute({"command": ""})
        assert result.success is False

    @pytest.mark.asyncio
    async def test_blocked_command(self) -> None:
        skill = ShellSkill()
        result = await skill.execute({"command": "rm -rf /"})
        assert result.success is False
        assert "blocked" in result.error.lower()

    @pytest.mark.asyncio
    async def test_allowed_commands_filter(self) -> None:
        skill = ShellSkill(allowed_commands=["echo"])
        result = await skill.execute({"command": "ls"})
        assert result.success is False
        assert "not in the allowed list" in result.error

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        skill = ShellSkill(timeout=0.1)
        result = await skill.execute({"command": "sleep 10"})
        assert result.success is False
        assert "timed out" in result.error.lower()


class TestFileManagerSkill:
    @pytest.mark.asyncio
    async def test_write_and_read(self, tmp_path) -> None:
        skill = FileManagerSkill(base_dir=str(tmp_path))
        write_result = await skill.execute({
            "action": "write",
            "path": "test.txt",
            "content": "hello world",
        })
        assert write_result.success is True

        read_result = await skill.execute({
            "action": "read",
            "path": "test.txt",
        })
        assert read_result.success is True
        assert read_result.output == "hello world"

    @pytest.mark.asyncio
    async def test_list_directory(self, tmp_path) -> None:
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        skill = FileManagerSkill(base_dir=str(tmp_path))
        result = await skill.execute({"action": "list", "path": "."})
        assert result.success is True
        assert "a.txt" in result.output
        assert "b.txt" in result.output

    @pytest.mark.asyncio
    async def test_exists(self, tmp_path) -> None:
        (tmp_path / "exists.txt").write_text("yes")
        skill = FileManagerSkill(base_dir=str(tmp_path))

        result = await skill.execute({"action": "exists", "path": "exists.txt"})
        assert result.data["exists"] is True

        result = await skill.execute({"action": "exists", "path": "missing.txt"})
        assert result.data["exists"] is False

    @pytest.mark.asyncio
    async def test_delete(self, tmp_path) -> None:
        (tmp_path / "delete_me.txt").write_text("bye")
        skill = FileManagerSkill(base_dir=str(tmp_path))
        result = await skill.execute({"action": "delete", "path": "delete_me.txt"})
        assert result.success is True
        assert not (tmp_path / "delete_me.txt").exists()

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path) -> None:
        skill = FileManagerSkill(base_dir=str(tmp_path))
        result = await skill.execute({"action": "read", "path": "../../etc/passwd"})
        assert result.success is False
        assert "traversal" in result.error.lower()
