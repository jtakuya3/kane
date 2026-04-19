# Kane

Daily pipeline that watches for new media appearances by **Elon Musk** and the
**Anthropic CEO (Dario Amodei)**, auto-selects the most compelling 30–55
second moment, burns in Japanese subtitles, and posts the resulting clip to X.

## How it works

1. **Discover** – `yt-dlp`'s date-sorted YouTube search returns recent uploads
   mentioning each target, filtered to a configurable lookback window.
2. **Download + trim** – the source video is downloaded at ≤720p. If longer
   than `KANE_MAX_SOURCE_MIN` minutes (default 20), the middle portion is
   sampled with `ffmpeg` so we keep compute bounded and skip long intros.
3. **Transcribe** – `faster-whisper` produces timestamped segments.
4. **Highlight + translate** – the transcript is sent to Claude
   (`claude-sonnet-4-6` by default), which picks the single best range and
   returns Japanese subtitle cues plus an X post body as JSON.
5. **Render** – `ffmpeg` cuts the chosen range and burns the JA subtitles
   from a generated ASS file (Noto Sans CJK JP).
6. **Post** – the finished clip is uploaded to X via `tweepy` and a tweet is
   composed from the Japanese body + hashtags + source link.
7. **State** – processed video IDs are recorded in `data/state.json` so we
   never repost the same source twice.

Each target produces at most `KANE_MAX_NEW_PER_TARGET` clips per run
(default 1), so a normal day yields up to two posts.

## Setup

### Prerequisites
- Python 3.12 (managed via pyenv)
- `ffmpeg` and Noto Sans CJK JP available on PATH
- Poetry

### Install
```bash
poetry install
```

### Required environment variables

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude API key for highlight selection + JA translation |
| `X_API_KEY` / `X_API_SECRET` | X app consumer keys |
| `X_ACCESS_TOKEN` / `X_ACCESS_SECRET` | X user tokens with write scope |
| `X_BEARER_TOKEN` | optional, for read endpoints |

### Optional tuning
| Variable | Default | Meaning |
| --- | --- | --- |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | highlight model |
| `KANE_MAX_SOURCE_MIN` | `20` | trim threshold for long sources |
| `KANE_HIGHLIGHT_MIN_SEC` / `_MAX_SEC` | `25` / `55` | clip length bounds |
| `KANE_LOOKBACK_HOURS` | `30` | how far back to scan |
| `KANE_MAX_NEW_PER_TARGET` | `1` | posts per target per run |
| `KANE_WHISPER_MODEL` | `small.en` | faster-whisper checkpoint |
| `KANE_DRY_RUN` | `0` | `1` = render but don't post |

## Run

```bash
# one-off
poetry run kane -v

# render only, skip posting
KANE_DRY_RUN=1 poetry run kane -v
```

Outputs land in `data/clips/<video_id>.jp.mp4` and `data/state.json`.

## Daily automation

`.github/workflows/daily.yml` runs the pipeline daily at 07:00 JST on GitHub
Actions. Set the API keys as repo secrets and the workflow will download
sources, render clips, post, and upload clips + state as an artifact.

## Layout

```
kane/
  config.py     # env-var settings + target list
  state.py      # processed-video ledger
  sources.py    # YouTube search via yt-dlp
  download.py   # yt-dlp download + trim-if-long
  transcribe.py # faster-whisper wrapper
  highlight.py  # Claude highlight + JA subtitle generation
  clip.py       # ffmpeg cut + ASS subtitle burn
  poster.py     # X upload + tweet
  pipeline.py   # orchestration
  __main__.py   # CLI
```
