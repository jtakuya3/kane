"""Shell command execution skill."""

from __future__ import annotations

import asyncio
import shlex
from typing import Any

from kane.skills.base import BaseSkill, SkillResult

# Commands that are never allowed for safety
BLOCKED_COMMANDS = frozenset({
    "rm -rf /", "mkfs", "dd if=/dev/zero", ":(){:|:&};:",
    "format", "deltree",
})


class ShellSkill(BaseSkill):
    """Execute shell commands safely."""

    name = "shell"
    description = "Execute a shell command and return its output."
    version = "0.1.0"

    def __init__(self, timeout: float = 30.0, allowed_commands: list[str] | None = None) -> None:
        self._timeout = timeout
        self._allowed_commands = set(allowed_commands) if allowed_commands else None

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for the command.",
                },
            },
            "required": ["command"],
        }

    async def execute(self, params: dict[str, Any]) -> SkillResult:
        command = params.get("command", "")
        working_dir = params.get("working_dir")

        if not command:
            return SkillResult(success=False, error="No command provided.")

        # Safety check
        for blocked in BLOCKED_COMMANDS:
            if blocked in command:
                return SkillResult(
                    success=False, error=f"Command blocked for safety: {command}"
                )

        if self._allowed_commands is not None:
            base_cmd = shlex.split(command)[0] if command else ""
            if base_cmd not in self._allowed_commands:
                return SkillResult(
                    success=False,
                    error=f"Command '{base_cmd}' is not in the allowed list.",
                )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )

            output = stdout.decode("utf-8", errors="replace")
            error_output = stderr.decode("utf-8", errors="replace")

            return SkillResult(
                success=proc.returncode == 0,
                output=output,
                error=error_output if proc.returncode != 0 else "",
                data={"return_code": proc.returncode},
            )
        except asyncio.TimeoutError:
            return SkillResult(
                success=False, error=f"Command timed out after {self._timeout}s."
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))
