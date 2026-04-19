"""Find candidate videos for each target using yt-dlp's search backend."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import yt_dlp

from .config import Target


@dataclass
class Candidate:
    video_id: str
    url: str
    title: str
    uploader: str
    duration: int | None
    upload_date: str | None  # YYYYMMDD
    target_key: str


def _flat_entries(query: str, limit: int) -> list[dict]:
    opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "default_search": f"ytsearchdate{limit}",
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(query, download=False)
    return info.get("entries", []) or []


def _hydrate(video_id: str) -> dict | None:
    opts = {"quiet": True, "skip_download": True, "noplaylist": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False
            )
    except yt_dlp.utils.DownloadError:
        return None


def search_target(target: Target, lookback_hours: int, limit: int = 8) -> list[Candidate]:
    """Return recent candidate videos for a target, sorted newest first."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    results: list[Candidate] = []
    for entry in _flat_entries(target.query, limit):
        vid = entry.get("id")
        if not vid:
            continue
        info = _hydrate(vid)
        if not info:
            continue
        upload_date = info.get("upload_date")
        if upload_date:
            try:
                uploaded = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
            except ValueError:
                uploaded = None
            if uploaded and uploaded < cutoff:
                continue
        results.append(
            Candidate(
                video_id=vid,
                url=info.get("webpage_url", f"https://www.youtube.com/watch?v={vid}"),
                title=info.get("title", ""),
                uploader=info.get("uploader", ""),
                duration=info.get("duration"),
                upload_date=upload_date,
                target_key=target.key,
            )
        )
    results.sort(key=lambda c: c.upload_date or "", reverse=True)
    return results
