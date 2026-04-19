"""Download videos with yt-dlp and trim overly-long sources."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from .config import RAW_DIR, WORK_DIR, ensure_dirs


@dataclass
class DownloadedVideo:
    video_id: str
    path: Path
    duration: float
    trimmed: bool


def _probe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    return float(out.strip())


def download(url: str, video_id: str) -> Path:
    ensure_dirs()
    out_template = str(RAW_DIR / f"{video_id}.%(ext)s")
    opts = {
        "outtmpl": out_template,
        "format": "bv*[height<=720]+ba/b[height<=720]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "noprogress": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    # yt-dlp may have chosen a different extension; find the real file.
    for p in RAW_DIR.glob(f"{video_id}.*"):
        if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".m4a"}:
            return p
    raise FileNotFoundError(f"Could not locate downloaded file for {video_id} ({info.get('title')})")


def trim_if_needed(src: Path, video_id: str, max_minutes: int) -> DownloadedVideo:
    duration = _probe_duration(src)
    max_seconds = max_minutes * 60
    if duration <= max_seconds:
        return DownloadedVideo(video_id=video_id, path=src, duration=duration, trimmed=False)

    # Sample the middle of the source to capture substantive content without
    # the long intros common in interviews and keynotes.
    start = max(0, (duration - max_seconds) / 2)
    trimmed_path = WORK_DIR / f"{video_id}.trimmed.mp4"
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start:.2f}",
            "-i",
            str(src),
            "-t",
            str(max_seconds),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(trimmed_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return DownloadedVideo(
        video_id=video_id,
        path=trimmed_path,
        duration=_probe_duration(trimmed_path),
        trimmed=True,
    )
