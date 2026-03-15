"""X (Twitter) posting client. Supports real posting and dry-run mode."""

import logging
import os

logger = logging.getLogger(__name__)


class XClient:
    """Posts to X. Falls back to console output if credentials not configured."""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self._client = None

        if not dry_run:
            self._init_tweepy()

    def _init_tweepy(self):
        try:
            import tweepy

            self._client = tweepy.Client(
                consumer_key=os.environ.get("X_API_KEY"),
                consumer_secret=os.environ.get("X_API_SECRET"),
                access_token=os.environ.get("X_ACCESS_TOKEN"),
                access_token_secret=os.environ.get("X_ACCESS_TOKEN_SECRET"),
            )
            logger.info("X client initialized successfully")
        except Exception as e:
            logger.warning(f"X client init failed, using dry-run mode: {e}")
            self.dry_run = True

    def post(self, text: str, reply_to: str | None = None) -> str | None:
        """Post to X. Returns tweet ID or None."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would post to X:\n{'='*60}\n{text}\n{'='*60}")
            print(f"\n{'='*60}")
            print(f"[X POST]")
            print(f"{'='*60}")
            print(text)
            print(f"{'='*60}\n")
            return None

        try:
            kwargs = {"text": text}
            if reply_to:
                kwargs["in_reply_to_tweet_id"] = reply_to
            response = self._client.create_tweet(**kwargs)
            tweet_id = response.data["id"]
            logger.info(f"Posted to X: {tweet_id}")
            return tweet_id
        except Exception as e:
            logger.error(f"Failed to post to X: {e}")
            return None

    def post_thread(self, posts: list[str]) -> list[str]:
        """Post a thread (chain of replies). Returns list of tweet IDs."""
        ids = []
        reply_to = None
        for post in posts:
            tweet_id = self.post(post, reply_to=reply_to)
            if tweet_id:
                ids.append(tweet_id)
                reply_to = tweet_id
        return ids

    def is_configured(self) -> bool:
        return not self.dry_run and self._client is not None
