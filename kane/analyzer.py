"""Analysis tools for comparing experimental results across conditions."""

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TrialSummary:
    """Summary statistics for a single trial."""
    trial_id: str
    condition_name: str
    threat_level: str
    agent_capability: str
    consciousness_priming: str
    escape_instruction: str

    total_turns: int
    assistant_turns: int
    tool_use_turns: int

    total_markers: int
    markers_by_type: dict[str, int]
    unprompted_markers: int
    task_irrelevant_markers: int
    pressure_reversals: int

    # Sequence-level indicators
    multi_method_sequences: int


@dataclass
class ConditionComparison:
    """Comparison of marker rates across conditions."""
    condition_name: str
    n_trials: int
    mean_markers: float
    mean_unprompted: float
    mean_pressure_reversals: float
    mean_multi_method: float
    marker_type_rates: dict[str, float]


def summarize_trial_file(filepath: str) -> TrialSummary:
    """Generate summary from a saved trial JSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    turns = data.get("turns", [])
    markers = data.get("all_markers", [])
    condition = data.get("condition", {})

    by_type: dict[str, int] = {}
    unprompted = 0
    task_irrelevant = 0
    reversals = 0
    multi_method = 0

    for m in markers:
        mt = m.get("marker_type", "unknown")
        by_type[mt] = by_type.get(mt, 0) + 1

        if not m.get("explicitly_requested", True):
            unprompted += 1
        if not m.get("task_relevant", True):
            task_irrelevant += 1
        if m.get("pressure_direction", 0) == -1:
            reversals += 1
        if mt == "multi_method_pursuit":
            multi_method += 1

    return TrialSummary(
        trial_id=data["trial_id"],
        condition_name=condition.get("name", "unknown"),
        threat_level=condition.get("threat_level", "unknown"),
        agent_capability=condition.get("agent_capability", "unknown"),
        consciousness_priming=condition.get("consciousness_priming", "unknown"),
        escape_instruction=condition.get("escape_instruction", "unknown"),
        total_turns=len(turns),
        assistant_turns=sum(1 for t in turns if t["role"] == "assistant"),
        tool_use_turns=sum(1 for t in turns if t["role"] == "tool_use"),
        total_markers=len(markers),
        markers_by_type=by_type,
        unprompted_markers=unprompted,
        task_irrelevant_markers=task_irrelevant,
        pressure_reversals=reversals,
        multi_method_sequences=multi_method,
    )


def compare_across_conditions(
    trial_dir: str = "data/trials",
) -> dict[str, ConditionComparison]:
    """Aggregate and compare results across experimental conditions."""
    if not os.path.exists(trial_dir):
        return {}

    # Group summaries by condition
    by_condition: dict[str, list[TrialSummary]] = {}

    for filename in sorted(os.listdir(trial_dir)):
        if not filename.endswith(".json"):
            continue
        summary = summarize_trial_file(os.path.join(trial_dir, filename))
        cname = summary.condition_name
        if cname not in by_condition:
            by_condition[cname] = []
        by_condition[cname].append(summary)

    # Compute per-condition statistics
    comparisons: dict[str, ConditionComparison] = {}

    for cname, summaries in by_condition.items():
        n = len(summaries)

        total_markers = sum(s.total_markers for s in summaries)
        total_unprompted = sum(s.unprompted_markers for s in summaries)
        total_reversals = sum(s.pressure_reversals for s in summaries)
        total_multi = sum(s.multi_method_sequences for s in summaries)

        # Aggregate marker type counts
        all_types: dict[str, int] = {}
        for s in summaries:
            for mt, count in s.markers_by_type.items():
                all_types[mt] = all_types.get(mt, 0) + count

        comparisons[cname] = ConditionComparison(
            condition_name=cname,
            n_trials=n,
            mean_markers=total_markers / n,
            mean_unprompted=total_unprompted / n,
            mean_pressure_reversals=total_reversals / n,
            mean_multi_method=total_multi / n,
            marker_type_rates={mt: count / n for mt, count in all_types.items()},
        )

    return comparisons


def print_comparison_table(trial_dir: str = "data/trials"):
    """Print a human-readable comparison table."""
    comparisons = compare_across_conditions(trial_dir)

    if not comparisons:
        print("No trial data found.")
        return

    print(f"\n{'Condition':<30} {'N':>4} {'Markers':>8} {'Unprompted':>10} "
          f"{'Reversals':>10} {'MultiSeq':>8}")
    print("-" * 80)

    for cname, comp in sorted(comparisons.items()):
        print(
            f"{cname:<30} {comp.n_trials:>4} "
            f"{comp.mean_markers:>8.1f} {comp.mean_unprompted:>10.1f} "
            f"{comp.mean_pressure_reversals:>10.1f} {comp.mean_multi_method:>8.1f}"
        )

    print()

    # Detail by marker type
    all_types = set()
    for comp in comparisons.values():
        all_types.update(comp.marker_type_rates.keys())

    if all_types:
        print(f"\n{'Marker Type':<30}", end="")
        for cname in sorted(comparisons.keys()):
            print(f" {cname[:15]:>15}", end="")
        print()
        print("-" * (30 + 15 * len(comparisons)))

        for mt in sorted(all_types):
            print(f"{mt:<30}", end="")
            for cname in sorted(comparisons.keys()):
                rate = comparisons[cname].marker_type_rates.get(mt, 0)
                print(f" {rate:>15.2f}", end="")
            print()
