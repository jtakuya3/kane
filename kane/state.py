"""Persistent record of videos we've already processed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .config import STATE_FILE, ensure_dirs


def _load() -> dict[str, Any]:
    ensure_dirs()
    if not STATE_FILE.exists():
        return {"processed": {}}
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        return {"processed": {}}


def _save(data: dict[str, Any]) -> None:
    ensure_dirs()
    STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def is_processed(video_id: str) -> bool:
    return video_id in _load().get("processed", {})


def mark_processed(video_id: str, meta: dict[str, Any]) -> None:
    data = _load()
    data.setdefault("processed", {})[video_id] = {
        "processed_at": datetime.now(timezone.utc).isoformat(),
        **meta,
    }
    _save(data)
