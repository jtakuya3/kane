"""Cut the highlight range and burn Japanese subtitles with ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .config import CLIPS_DIR, WORK_DIR, ensure_dirs
from .highlight import Highlight


def _seconds_to_ass_time(t: float) -> str:
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _write_ass(path: Path, highlight: Highlight) -> None:
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1280\n"
        "PlayResY: 720\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: JA,Noto Sans CJK JP,44,&H00FFFFFF,&H00000000,&H80000000,1,1,3,0,2,60,60,60,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = [header]
    for cue in highlight.cues:
        text = cue.text.replace("\n", "\\N").replace(",", "\uFF0C")
        lines.append(
            f"Dialogue: 0,{_seconds_to_ass_time(cue.start)},"
            f"{_seconds_to_ass_time(cue.end)},JA,,0,0,0,,{text}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")


def render_clip(source: Path, video_id: str, highlight: Highlight) -> Path:
    ensure_dirs()
    duration = max(1.0, highlight.end - highlight.start)
    ass_path = WORK_DIR / f"{video_id}.ass"
    _write_ass(ass_path, highlight)

    out = CLIPS_DIR / f"{video_id}.jp.mp4"
    vf = f"subtitles={ass_path.as_posix()}"
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{highlight.start:.2f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.2f}",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(out),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return out
