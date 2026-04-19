"""Central configuration pulled from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("KANE_DATA_DIR", ROOT / "data"))
CLIPS_DIR = DATA_DIR / "clips"
RAW_DIR = DATA_DIR / "raw"
WORK_DIR = DATA_DIR / "work"
STATE_FILE = DATA_DIR / "state.json"


@dataclass(frozen=True)
class Target:
    key: str
    query: str
    display_name: str
    hashtags: tuple[str, ...] = field(default_factory=tuple)


TARGETS: tuple[Target, ...] = (
    Target(
        key="elon_musk",
        query="Elon Musk interview",
        display_name="Elon Musk",
        hashtags=("#ElonMusk", "#Tesla", "#SpaceX"),
    ),
    Target(
        key="dario_amodei",
        query="Dario Amodei Anthropic interview",
        display_name="Dario Amodei",
        hashtags=("#Anthropic", "#Claude", "#AI"),
    ),
)


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    x_api_key: str = os.environ.get("X_API_KEY", "")
    x_api_secret: str = os.environ.get("X_API_SECRET", "")
    x_access_token: str = os.environ.get("X_ACCESS_TOKEN", "")
    x_access_secret: str = os.environ.get("X_ACCESS_SECRET", "")
    x_bearer_token: str = os.environ.get("X_BEARER_TOKEN", "")

    # If the source video is longer than this, we sample/trim it before
    # transcription so we don't burn CPU on hour-long podcasts.
    max_source_minutes: int = int(os.environ.get("KANE_MAX_SOURCE_MIN", "20"))
    highlight_min_seconds: int = int(os.environ.get("KANE_HIGHLIGHT_MIN_SEC", "25"))
    highlight_max_seconds: int = int(os.environ.get("KANE_HIGHLIGHT_MAX_SEC", "55"))
    lookback_hours: int = int(os.environ.get("KANE_LOOKBACK_HOURS", "30"))
    max_new_per_target: int = int(os.environ.get("KANE_MAX_NEW_PER_TARGET", "1"))
    dry_run: bool = os.environ.get("KANE_DRY_RUN", "0") == "1"


SETTINGS = Settings()


def ensure_dirs() -> None:
    for d in (DATA_DIR, CLIPS_DIR, RAW_DIR, WORK_DIR):
        d.mkdir(parents=True, exist_ok=True)
