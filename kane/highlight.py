"""Pick the best highlight range and produce Japanese subtitles via Claude."""

from __future__ import annotations

import json
from dataclasses import dataclass

import anthropic

from .config import SETTINGS
from .transcribe import Segment


@dataclass
class SubtitleCue:
    start: float  # seconds, relative to clip start
    end: float
    text: str  # Japanese


@dataclass
class Highlight:
    start: float  # seconds in source
    end: float
    reason: str
    tweet_text: str  # Japanese post body (<=140 chars)
    cues: list[SubtitleCue]


SYSTEM_PROMPT = (
    "あなたはソーシャル動画編集者です。英語の長尺インタビュー書き起こしから、"
    "X(旧Twitter)で最も視聴・シェアされる30〜55秒の切り抜き区間を1つ選び、"
    "日本語字幕と日本語の投稿文を生成します。"
    "選定基準: 具体的で驚きのある発言・数字・新しい情報・強い主張・感情的な瞬間。"
    "必ずJSONのみを返してください。"
)


def _format_transcript(segments: list[Segment]) -> str:
    lines = []
    for s in segments:
        lines.append(f"[{s.start:7.2f}-{s.end:7.2f}] {s.text}")
    return "\n".join(lines)


def _build_user_prompt(
    target_name: str, title: str, transcript: str, min_sec: int, max_sec: int
) -> str:
    return (
        f"対象人物: {target_name}\n"
        f"元動画タイトル: {title}\n"
        f"許容される切り抜き長: {min_sec}〜{max_sec}秒\n\n"
        "次の書き起こし(タイムコード秒)から最良の区間を1つ選び、"
        "その区間に収まる日本語字幕を自然な文節で2〜4秒ごとに区切って生成してください。\n\n"
        "出力スキーマ(JSONのみ):\n"
        "{\n"
        '  "start": <秒>,\n'
        '  "end": <秒>,\n'
        '  "reason": "選定理由(日本語, 1行)",\n'
        '  "tweet_text": "X投稿本文(日本語, 140字以内, ハッシュタグ無し)",\n'
        '  "cues": [ {"start": <クリップ開始からの秒>, "end": <秒>, "text": "日本語字幕"} ]\n'
        "}\n\n"
        "書き起こし:\n"
        f"{transcript}\n"
    )


def pick_highlight(
    target_name: str, title: str, segments: list[Segment]
) -> Highlight:
    if not SETTINGS.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=SETTINGS.anthropic_api_key)
    transcript = _format_transcript(segments)
    user_prompt = _build_user_prompt(
        target_name,
        title,
        transcript,
        SETTINGS.highlight_min_seconds,
        SETTINGS.highlight_max_seconds,
    )

    msg = client.messages.create(
        model=SETTINGS.anthropic_model,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = "".join(block.text for block in msg.content if block.type == "text").strip()
    # Strip fenced code blocks if present.
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]

    data = json.loads(raw)
    cues = [
        SubtitleCue(start=float(c["start"]), end=float(c["end"]), text=c["text"])
        for c in data.get("cues", [])
    ]
    return Highlight(
        start=float(data["start"]),
        end=float(data["end"]),
        reason=str(data.get("reason", "")),
        tweet_text=str(data["tweet_text"]),
        cues=cues,
    )
