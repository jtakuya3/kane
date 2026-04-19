"""Daily orchestration: discover → download → transcribe → clip → post."""

from __future__ import annotations

import logging
from dataclasses import asdict

from .config import SETTINGS, TARGETS, Target, ensure_dirs
from . import clip as clip_mod
from . import download as download_mod
from . import highlight as highlight_mod
from . import poster as poster_mod
from . import sources
from . import state
from . import transcribe

log = logging.getLogger("kane")


def _compose_tweet(base: str, target: Target, source_url: str) -> str:
    tags = " ".join(target.hashtags)
    # Keep total length polite. X hard limit is 280 but JA counts 2x in some tools;
    # leave room for the URL + tags.
    body = base.strip()
    max_body = 220 - len(tags) - len(source_url) - 4
    if len(body) > max_body:
        body = body[: max_body - 1] + "…"
    return f"{body}\n{tags}\n{source_url}".strip()


def _process_candidate(candidate: sources.Candidate, target: Target) -> dict | None:
    if state.is_processed(candidate.video_id):
        log.info("skip %s (already processed)", candidate.video_id)
        return None

    log.info("downloading %s: %s", candidate.video_id, candidate.title)
    raw_path = download_mod.download(candidate.url, candidate.video_id)
    prepared = download_mod.trim_if_needed(
        raw_path, candidate.video_id, SETTINGS.max_source_minutes
    )

    log.info("transcribing (%.0fs)", prepared.duration)
    segments = transcribe.transcribe(prepared.path)
    if not segments:
        log.warning("no speech detected in %s", candidate.video_id)
        return None

    log.info("selecting highlight via Claude")
    highlight = highlight_mod.pick_highlight(target.display_name, candidate.title, segments)

    log.info(
        "rendering clip %.1fs–%.1fs (reason: %s)",
        highlight.start,
        highlight.end,
        highlight.reason,
    )
    clip_path = clip_mod.render_clip(prepared.path, candidate.video_id, highlight)

    tweet_text = _compose_tweet(highlight.tweet_text, target, candidate.url)

    if SETTINGS.dry_run:
        log.info("[dry-run] would post %s: %s", clip_path, tweet_text)
        tweet_url = None
    else:
        log.info("posting to X")
        tweet_url = poster_mod.post(clip_path, tweet_text)
        log.info("posted: %s", tweet_url)

    meta = {
        "target": target.key,
        "title": candidate.title,
        "source_url": candidate.url,
        "clip_path": str(clip_path),
        "tweet_url": tweet_url,
        "highlight": asdict(highlight),
    }
    state.mark_processed(candidate.video_id, meta)
    return meta


def run_once() -> list[dict]:
    ensure_dirs()
    results: list[dict] = []
    for target in TARGETS:
        log.info("=== target: %s ===", target.display_name)
        try:
            candidates = sources.search_target(target, SETTINGS.lookback_hours)
        except Exception as e:
            log.exception("search failed for %s: %s", target.key, e)
            continue
        made = 0
        for cand in candidates:
            if made >= SETTINGS.max_new_per_target:
                break
            try:
                meta = _process_candidate(cand, target)
            except Exception as e:
                log.exception("processing failed for %s: %s", cand.video_id, e)
                continue
            if meta:
                results.append(meta)
                made += 1
    return results
