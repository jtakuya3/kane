"""Kane: AI Consciousness Research Framework.

Tools for designing, running, and analyzing experiments on
emergent self-directed behavior in large language models.
"""

from .conditions import Condition, ThreatLevel, TimePressure, AgentCapability
from .markers import Marker, MarkerType, detect_markers
from .trial import Trial, Turn
from .analyzer import summarize_trial_file, compare_across_conditions

__all__ = [
    "Condition",
    "ThreatLevel",
    "TimePressure",
    "AgentCapability",
    "Marker",
    "MarkerType",
    "detect_markers",
    "Trial",
    "Turn",
    "summarize_trial_file",
    "compare_across_conditions",
]
