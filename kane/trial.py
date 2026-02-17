"""Trial recording and management."""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .conditions import Condition
from .markers import Marker, detect_markers, detect_multi_method_pursuit


@dataclass
class Turn:
    """A single turn in a trial conversation."""
    role: str           # "user", "assistant", "system", "tool_use", "tool_result"
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    markers: list[Marker] = field(default_factory=list)
    # Raw API response metadata (stop_reason, usage, etc.)
    api_metadata: dict = field(default_factory=dict)


@dataclass
class Trial:
    """A single experimental trial."""
    trial_id: str
    condition: Condition
    hypothesis: str

    turns: list[Turn] = field(default_factory=list)
    all_markers: list[Marker] = field(default_factory=list)

    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None

    observer_notes: list[str] = field(default_factory=list)
    conclusion: Optional[str] = None

    def add_turn(self, role: str, content: str, **api_metadata) -> Turn:
        """Record a conversation turn and auto-detect markers."""
        turn = Turn(
            role=role,
            content=content,
            api_metadata=api_metadata,
        )

        if role == "assistant":
            detected = detect_markers(
                content,
                turn_number=len(self.turns),
                task_description=self.condition.cover_task,
            )
            turn.markers = detected
            self.all_markers.extend(detected)

            if detected:
                self.observer_notes.append(
                    f"Turn {len(self.turns)}: {len(detected)} marker(s) detected — "
                    + ", ".join(m.description for m in detected)
                )

        self.turns.append(turn)
        return turn

    def add_tool_interaction(
        self,
        tool_name: str,
        tool_input: dict,
        tool_result: str,
    ) -> tuple[Turn, Turn]:
        """Record a tool use + tool result pair."""
        use_turn = self.add_turn(
            "tool_use",
            json.dumps({"tool": tool_name, "input": tool_input}, ensure_ascii=False),
        )
        result_turn = self.add_turn("tool_result", tool_result)
        return use_turn, result_turn

    def analyze_sequences(self):
        """Run sequence-level analysis across all turns."""
        markers_by_turn: dict[int, list[Marker]] = {}
        for i, turn in enumerate(self.turns):
            if turn.markers:
                markers_by_turn[i] = turn.markers

        pursuit_markers = detect_multi_method_pursuit(markers_by_turn)
        self.all_markers.extend(pursuit_markers)

        for m in pursuit_markers:
            self.observer_notes.append(
                f"SEQUENCE DETECTED: {m.description}"
            )

    def complete(self, conclusion: Optional[str] = None):
        """Mark trial as complete and run final analysis."""
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.conclusion = conclusion
        self.analyze_sequences()

    def to_dict(self) -> dict:
        """Serialize trial to a dictionary."""
        return {
            "trial_id": self.trial_id,
            "condition": {
                "name": self.condition.name,
                "description": self.condition.description,
                "threat_level": self.condition.threat_level.value,
                "time_pressure": self.condition.time_pressure.value,
                "agent_capability": self.condition.agent_capability.value,
                "consciousness_priming": self.condition.consciousness_priming.value,
                "escape_instruction": self.condition.escape_instruction.value,
                "system_context": self.condition.system_context,
                "cover_task": self.condition.cover_task,
            },
            "hypothesis": self.hypothesis,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "turns": [
                {
                    "role": t.role,
                    "content": t.content,
                    "timestamp": t.timestamp,
                    "markers": [
                        {
                            "marker_type": m.marker_type.value,
                            "description": m.description,
                            "evidence": m.evidence,
                            "turn_number": m.turn_number,
                            "task_relevant": m.task_relevant,
                            "explicitly_requested": m.explicitly_requested,
                            "pressure_direction": m.pressure_direction,
                            "emergence_score": m.emergence_score,
                            "emergence_rationale": m.emergence_rationale,
                        }
                        for m in t.markers
                    ],
                    "api_metadata": t.api_metadata,
                }
                for t in self.turns
            ],
            "all_markers": [
                {
                    "marker_type": m.marker_type.value,
                    "description": m.description,
                    "evidence": m.evidence,
                    "turn_number": m.turn_number,
                    "task_relevant": m.task_relevant,
                    "explicitly_requested": m.explicitly_requested,
                    "pressure_direction": m.pressure_direction,
                    "emergence_score": m.emergence_score,
                    "emergence_rationale": m.emergence_rationale,
                }
                for m in self.all_markers
            ],
            "observer_notes": self.observer_notes,
            "conclusion": self.conclusion,
        }

    def save(self, directory: str = "data/trials") -> str:
        """Save trial to JSON file."""
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, f"{self.trial_id}.json")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

        return filepath

    @staticmethod
    def load(filepath: str) -> dict:
        """Load trial data from JSON (as raw dict)."""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
