"""CLI channel - interactive terminal interface."""

from __future__ import annotations

import asyncio
import sys
from typing import Callable, Awaitable

from kane.channels.base import BaseChannel, InboundMessage, OutboundMessage


class CLIChannel(BaseChannel):
    """Interactive command-line channel."""

    name = "cli"

    def __init__(self) -> None:
        super().__init__()
        self._running = False
        self._response_callback: Callable[[str], Awaitable[None]] | None = None

    async def start(self) -> None:
        """Start the CLI input loop."""
        self._running = True
        print("Kane AI Assistant - Type 'exit' or 'quit' to stop.")
        print("-" * 50)

        while self._running:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("You: ")
                )
            except (EOFError, KeyboardInterrupt):
                break

            user_input = user_input.strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Goodbye!")
                break

            message = InboundMessage(
                channel=self.name,
                sender="cli_user",
                content=user_input,
            )
            await self.on_message(message)

        self._running = False

    async def stop(self) -> None:
        """Stop the CLI channel."""
        self._running = False

    async def send(self, message: OutboundMessage) -> None:
        """Print a message to the terminal."""
        print(f"Kane: {message.content}")
