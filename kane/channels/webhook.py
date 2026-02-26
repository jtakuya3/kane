"""Webhook channel - HTTP-based messaging interface."""

from __future__ import annotations

import json
import asyncio
from typing import Any

from kane.channels.base import BaseChannel, InboundMessage, OutboundMessage


class WebhookChannel(BaseChannel):
    """HTTP webhook-based channel for integrating with external services."""

    name = "webhook"

    def __init__(self, host: str = "127.0.0.1", port: int = 8322) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._server: asyncio.Server | None = None
        self._pending_responses: dict[str, asyncio.Future[str]] = {}

    async def start(self) -> None:
        """Start the webhook HTTP server."""
        self._server = await asyncio.start_server(
            self._handle_connection, self._host, self._port
        )
        print(f"Webhook channel listening on {self._host}:{self._port}")

    async def stop(self) -> None:
        """Stop the webhook server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def send(self, message: OutboundMessage) -> None:
        """Resolve a pending response future for the given recipient."""
        msg_id = message.metadata.get("reply_to", "")
        if msg_id in self._pending_responses:
            self._pending_responses[msg_id].set_result(message.content)

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming HTTP connection."""
        try:
            raw = await reader.read(65536)
            request_text = raw.decode("utf-8", errors="replace")

            # Parse simple HTTP request
            header_end = request_text.find("\r\n\r\n")
            if header_end == -1:
                await self._send_http_response(writer, 400, {"error": "Bad request"})
                return

            body = request_text[header_end + 4 :]
            first_line = request_text.split("\r\n")[0]
            method, path, *_ = first_line.split(" ")

            if method == "POST" and path == "/message":
                await self._handle_message(writer, body)
            elif method == "GET" and path == "/health":
                await self._send_http_response(writer, 200, {"status": "ok"})
            else:
                await self._send_http_response(writer, 404, {"error": "Not found"})
        except Exception as e:
            await self._send_http_response(writer, 500, {"error": str(e)})
        finally:
            writer.close()

    async def _handle_message(
        self, writer: asyncio.StreamWriter, body: str
    ) -> None:
        """Process an incoming webhook message."""
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            await self._send_http_response(writer, 400, {"error": "Invalid JSON"})
            return

        message = InboundMessage(
            channel=self.name,
            sender=data.get("sender", "webhook_user"),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
        )

        # Create a future to wait for the response
        future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
        self._pending_responses[message.id] = future

        # Route the message
        await self.on_message(message)

        # Wait for response with timeout
        try:
            response_content = await asyncio.wait_for(future, timeout=60.0)
            await self._send_http_response(
                writer, 200, {"response": response_content}
            )
        except asyncio.TimeoutError:
            await self._send_http_response(writer, 504, {"error": "Timeout"})
        finally:
            self._pending_responses.pop(message.id, None)

    async def _send_http_response(
        self, writer: asyncio.StreamWriter, status: int, body: dict[str, Any]
    ) -> None:
        """Send an HTTP response."""
        status_text = {200: "OK", 400: "Bad Request", 404: "Not Found", 500: "Internal Server Error", 504: "Gateway Timeout"}
        body_bytes = json.dumps(body).encode("utf-8")
        response = (
            f"HTTP/1.1 {status} {status_text.get(status, 'Unknown')}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"\r\n"
        ).encode("utf-8") + body_bytes
        writer.write(response)
        await writer.drain()
