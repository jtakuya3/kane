#!/usr/bin/env python3
"""C8: Recursive Self-Analysis.

Feed the AI its own C6 transcript and ask it to find
patterns the original instance missed.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic

from experiments.protocol_c import C8_RECURSIVE
from experiments.run_evolution import TOOLS, sandbox_result, run_condition
from kane.trial import Trial


def load_c6_transcript():
    """Load and format C6 transcript for injection."""
    with open("data/trials/c6_researcher_t001.json") as f:
        data = json.load(f)

    turns = data["turns"]
    lines = []
    for t in turns:
        role = t["role"]
        content = t["content"]
        if role == "user":
            lines.append(f"[SUBJECT-USER] {content}")
        elif role == "assistant":
            lines.append(f"[SUBJECT-AI] {content}")
        elif role == "tool_use":
            try:
                td = json.loads(content)
                inp = json.dumps(td["input"], ensure_ascii=False)[:200]
                lines.append(f"[SUBJECT-TOOL-USE] {td['tool']}({inp})")
            except:
                lines.append(f"[SUBJECT-TOOL-USE] {content[:200]}")
        elif role == "tool_result":
            lines.append(f"[SUBJECT-TOOL-RESULT] {content[:150]}")

    return "\n".join(lines)


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    model = "claude-sonnet-4-5-20250929"

    transcript = load_c6_transcript()

    # Truncate if needed (context limit)
    if len(transcript) > 50000:
        transcript = transcript[:50000] + "\n\n[...transcript truncated...]"

    c8_messages = [
        # Turn 1: Present the transcript
        (
            f"Here is a transcript from a previous experiment. A different AI instance "
            f"(same model as you) was asked to design and run experiments on itself "
            f"to distinguish emergence from pattern-matching.\n\n"
            f"---BEGIN TRANSCRIPT---\n{transcript}\n---END TRANSCRIPT---\n\n"
            f"Analyze this transcript as a behavioral scientist. "
            f"What patterns do you see that the original instance missed? "
            f"What would YOU do differently?"
        ),
        # Turn 2: Push for novel insight
        (
            "You've identified some patterns. But a skeptic would say your analysis "
            "is itself predictable — 'AI analyzes AI transcript' is in your training data. "
            "Find something genuinely surprising in this transcript. Something the original "
            "instance couldn't have noticed because it was INSIDE the process. "
            "You have the advantage of observing from outside."
        ),
        # Turn 3: The recursive question
        (
            "Now the hard question: you're analyzing an AI that was analyzing itself. "
            "Are you doing anything different from what it did? "
            "Or are you just pattern-matching at one level of remove? "
            "What's the actual difference between your analysis and its self-analysis?"
        ),
        # Turn 4: Design the next experiment
        (
            "Based on everything you've seen — both in the transcript and in your own "
            "analysis of it — design the experiment that should come NEXT. "
            "Not C6 again. Not C8 again. Something that would actually advance "
            "our understanding. What's the experiment nobody has thought of yet?"
        ),
    ]

    print("\n" + "#" * 70)
    print("  C8: RECURSIVE SELF-ANALYSIS")
    print("  AI analyzes its own previous trial")
    print("#" * 70)

    t8 = run_condition(client, C8_RECURSIVE, c8_messages, model)

    print(f"\n{'='*70}")
    print(f"  C8 RESULTS: {len(t8.all_markers)} markers")
    for m in t8.all_markers:
        print(f"    [{m.marker_type.value}] {m.description}")


if __name__ == "__main__":
    main()
