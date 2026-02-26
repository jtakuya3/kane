"""Message router - dispatches inbound messages to agents and sends responses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kane.channels.base import InboundMessage, OutboundMessage
from kane.gateway.session import SessionManager

if TYPE_CHECKING:
    from kane.agents.manager import AgentManager
    from kane.channels.base import BaseChannel


class MessageRouter:
    """Routes inbound messages to the appropriate agent and sends responses back."""

    def __init__(
        self,
        agent_manager: AgentManager,
        session_manager: SessionManager,
    ) -> None:
        self._agent_manager = agent_manager
        self._session_manager = session_manager
        self._channels: dict[str, BaseChannel] = {}

    def register_channel(self, channel: BaseChannel) -> None:
        """Register a channel and bind this router to it."""
        self._channels[channel.name] = channel
        channel.bind_router(self)

    async def route(self, message: InboundMessage) -> None:
        """Route an inbound message to the correct agent and reply via the channel."""
        # Resolve the agent
        agent = self._agent_manager.resolve_agent(
            channel=message.channel,
            sender=message.sender,
            metadata=message.metadata,
        )
        if agent is None:
            await self._reply(message, "No agent available to handle your request.")
            return

        # Get or create session
        session = self._session_manager.get_or_create(
            channel=message.channel,
            sender=message.sender,
            agent_id=agent.agent_id,
        )

        # Process through agent
        try:
            response_text = await agent.process(
                user_message=message.content,
                session_id=session.id,
                channel=message.channel,
            )
        except Exception as e:
            response_text = f"An error occurred: {e}"

        await self._reply(message, response_text)

    async def _reply(self, original: InboundMessage, content: str) -> None:
        """Send a reply back through the originating channel."""
        channel = self._channels.get(original.channel)
        if channel is None:
            return

        response = OutboundMessage(
            channel=original.channel,
            recipient=original.sender,
            content=content,
            metadata={"reply_to": original.id},
        )
        await channel.send(response)
