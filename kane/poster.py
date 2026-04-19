"""Post a rendered clip to X via the v1.1 media upload + v2 tweet endpoints."""

from __future__ import annotations

from pathlib import Path

import tweepy

from .config import SETTINGS


def _clients() -> tuple[tweepy.API, tweepy.Client]:
    auth = tweepy.OAuth1UserHandler(
        SETTINGS.x_api_key,
        SETTINGS.x_api_secret,
        SETTINGS.x_access_token,
        SETTINGS.x_access_secret,
    )
    api = tweepy.API(auth)
    client = tweepy.Client(
        bearer_token=SETTINGS.x_bearer_token or None,
        consumer_key=SETTINGS.x_api_key,
        consumer_secret=SETTINGS.x_api_secret,
        access_token=SETTINGS.x_access_token,
        access_token_secret=SETTINGS.x_access_secret,
    )
    return api, client


def post(video_path: Path, text: str) -> str:
    """Upload the clip and publish a tweet. Returns tweet URL (or id)."""
    if not all(
        [
            SETTINGS.x_api_key,
            SETTINGS.x_api_secret,
            SETTINGS.x_access_token,
            SETTINGS.x_access_secret,
        ]
    ):
        raise RuntimeError("X API credentials are not fully configured")

    api, client = _clients()
    media = api.media_upload(
        filename=str(video_path),
        media_category="tweet_video",
        chunked=True,
        wait_for_async_finalize=True,
    )
    media_id = media.media_id_string
    resp = client.create_tweet(text=text, media_ids=[media_id])
    tweet_id = resp.data.get("id") if resp and resp.data else None
    if tweet_id is None:
        raise RuntimeError(f"X post did not return an id: {resp}")
    return f"https://x.com/i/web/status/{tweet_id}"
