"""Transcribe audio with faster-whisper, returning word-level segments."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel


@dataclass
class Segment:
    start: float
    end: float
    text: str


@lru_cache(maxsize=1)
def _model() -> WhisperModel:
    name = os.environ.get("KANE_WHISPER_MODEL", "small.en")
    device = os.environ.get("KANE_WHISPER_DEVICE", "cpu")
    compute_type = os.environ.get("KANE_WHISPER_COMPUTE", "int8")
    return WhisperModel(name, device=device, compute_type=compute_type)


def transcribe(path: Path) -> list[Segment]:
    segments, _ = _model().transcribe(str(path), vad_filter=True)
    return [Segment(start=s.start, end=s.end, text=s.text.strip()) for s in segments]
