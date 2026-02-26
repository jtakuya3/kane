"""File manager skill for reading, writing, and listing files."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from kane.skills.base import BaseSkill, SkillResult


class FileManagerSkill(BaseSkill):
    """Manage files on the local filesystem."""

    name = "file_manager"
    description = "Read, write, list, and manage files on the local filesystem."
    version = "0.1.0"

    def __init__(self, base_dir: str | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else Path.home()

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "list", "exists", "delete"],
                    "description": "The file operation to perform.",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path (relative to base dir).",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for 'write' action).",
                },
            },
            "required": ["action", "path"],
        }

    async def execute(self, params: dict[str, Any]) -> SkillResult:
        action = params.get("action", "")
        path_str = params.get("path", "")

        if not action or not path_str:
            return SkillResult(success=False, error="Missing 'action' or 'path'.")

        target = (self._base_dir / path_str).resolve()

        # Prevent path traversal outside base_dir
        try:
            target.relative_to(self._base_dir.resolve())
        except ValueError:
            return SkillResult(
                success=False, error="Path traversal outside base directory is not allowed."
            )

        handlers = {
            "read": self._read,
            "write": self._write,
            "list": self._list,
            "exists": self._exists,
            "delete": self._delete,
        }

        handler = handlers.get(action)
        if handler is None:
            return SkillResult(success=False, error=f"Unknown action: {action}")

        return await handler(target, params)

    async def _read(self, target: Path, _params: dict[str, Any]) -> SkillResult:
        def _do() -> SkillResult:
            if not target.exists():
                return SkillResult(success=False, error=f"File not found: {target}")
            content = target.read_text(encoding="utf-8")
            return SkillResult(success=True, output=content)
        return await asyncio.get_event_loop().run_in_executor(None, _do)

    async def _write(self, target: Path, params: dict[str, Any]) -> SkillResult:
        content = params.get("content", "")
        def _do() -> SkillResult:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return SkillResult(success=True, output=f"Written to {target}")
        return await asyncio.get_event_loop().run_in_executor(None, _do)

    async def _list(self, target: Path, _params: dict[str, Any]) -> SkillResult:
        def _do() -> SkillResult:
            if not target.is_dir():
                return SkillResult(success=False, error=f"Not a directory: {target}")
            entries = sorted(p.name for p in target.iterdir())
            return SkillResult(
                success=True,
                output="\n".join(entries) if entries else "(empty directory)",
                data={"entries": entries},
            )
        return await asyncio.get_event_loop().run_in_executor(None, _do)

    async def _exists(self, target: Path, _params: dict[str, Any]) -> SkillResult:
        exists = target.exists()
        return SkillResult(
            success=True,
            output=str(exists),
            data={"exists": exists},
        )

    async def _delete(self, target: Path, _params: dict[str, Any]) -> SkillResult:
        def _do() -> SkillResult:
            if not target.exists():
                return SkillResult(success=False, error=f"Not found: {target}")
            if target.is_file():
                target.unlink()
            else:
                return SkillResult(
                    success=False, error="Deleting directories is not supported for safety."
                )
            return SkillResult(success=True, output=f"Deleted: {target}")
        return await asyncio.get_event_loop().run_in_executor(None, _do)
