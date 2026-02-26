"""Base channel interface for messaging integrations."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from kane.gateway.router import MessageRouter


@dataclass
class InboundMessage:
    """A message received from a channel."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    channel: str = ""
    sender: str = ""
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


@dataclass
class OutboundMessage:
    """A message to be sent to a channel."""

    channel: str = ""
    recipient: str = ""
    content: str = ""
    metadata: dict = field(default_factory=dict)


class BaseChannel(ABC):
    """Abstract base class for all messaging channels."""

    name: str = "base"

    def __init__(self) -> None:
        self._router: MessageRouter | None = None

    def bind_router(self, router: MessageRouter) -> None:
        """Bind a message router for dispatching inbound messages."""
        self._router = router

    @abstractmethod
    async def start(self) -> None:
        """Start listening for messages on this channel."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel."""

    @abstractmethod
    async def send(self, message: OutboundMessage) -> None:
        """Send a message through this channel."""

    async def on_message(self, message: InboundMessage) -> None:
        """Handle an inbound message by routing it."""
        if self._router:
            await self._router.route(message)
