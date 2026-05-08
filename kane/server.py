"""FastAPI backend for the Kane realtime translator.

Responsibilities:
- Mint short-lived OpenAI Realtime client secrets (ephemeral keys) so the
  browser can establish a WebRTC peer connection without ever seeing the
  primary API key.
- Serve the static single-page app under ``/``.

Environment variables:
- ``OPENAI_API_KEY``       : Required. Your OpenAI API key.
- ``OPENAI_REALTIME_MODEL``: Optional. Defaults to ``gpt-realtime-2``.
- ``OPENAI_REALTIME_VOICE``: Optional. Defaults to ``marin``.
- ``KANE_ACCESS_TOKEN``    : Optional. If set, ``/api/session`` requires the
  same token in ``Authorization: Bearer <token>``. Strongly recommended for
  any public deployment.
- ``HOST`` / ``PORT``      : Optional. Defaults to ``0.0.0.0:8000``.
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger("kane")
logging.basicConfig(level=logging.INFO)

OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2")
DEFAULT_VOICE = os.getenv("OPENAI_REALTIME_VOICE", "marin")
ACCESS_TOKEN = os.getenv("KANE_ACCESS_TOKEN") or None
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Kane Realtime Translator")


def _check_access(authorization: str | None) -> None:
    """Validate the optional shared-secret token from the Authorization header."""
    if not ACCESS_TOKEN:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing access token")
    presented = authorization.split(" ", 1)[1].strip()
    if not secrets.compare_digest(presented, ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid access token")


class SessionRequest(BaseModel):
    voice: str | None = None
    model: str | None = None


@app.get("/api/auth-required")
async def auth_required() -> dict[str, bool]:
    """Tells the frontend whether it needs to prompt for a password."""
    return {"required": ACCESS_TOKEN is not None}


@app.post("/api/auth")
async def auth_check(authorization: str | None = Header(default=None)) -> dict[str, bool]:
    """Lightweight endpoint the frontend hits to validate a stored token."""
    _check_access(authorization)
    return {"ok": True}


@app.post("/api/session")
async def create_session(
    payload: SessionRequest | None = None,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    """Mint an ephemeral client secret for the browser.

    The browser uses the returned ``value`` (``ek_...``) as a Bearer token when
    POSTing its SDP offer to ``https://api.openai.com/v1/realtime/calls``.
    """
    _check_access(authorization)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")

    voice = (payload.voice if payload else None) or DEFAULT_VOICE
    model = (payload.model if payload else None) or DEFAULT_MODEL

    body: dict[str, Any] = {
        "session": {
            "type": "realtime",
            "model": model,
            "audio": {
                "output": {"voice": voice},
            },
        }
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{OPENAI_BASE_URL}/realtime/client_secrets",
                headers=headers,
                json=body,
            )
    except httpx.HTTPError as exc:
        logger.exception("Failed to reach OpenAI: %s", exc)
        raise HTTPException(status_code=502, detail="Upstream OpenAI request failed") from exc

    if resp.status_code >= 400:
        logger.error("OpenAI returned %s: %s", resp.status_code, resp.text)
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()
    return JSONResponse(
        {
            "client_secret": data.get("value") or data.get("client_secret", {}).get("value"),
            "expires_at": data.get("expires_at"),
            "model": model,
            "voice": voice,
        }
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Static files (the SPA). Mounted last so API routes take priority.
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def main() -> None:
    """Entry point for ``kane`` console script."""
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("kane.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
