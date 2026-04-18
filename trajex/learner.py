from __future__ import annotations

import math
from collections import Counter


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    return round(math.sqrt(sum((x - m) ** 2 for x in values) / len(values)), 4)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = min(int(pct / 100 * len(sorted_vals)), len(sorted_vals) - 1)
    return round(sorted_vals[idx], 4)


def extract_patterns(traces: list) -> dict:
    if not traces:
        return {}

    n = len(traces)
    all_tool_names: set[str] = set()
    for t in traces:
        all_tool_names.update(t.tool_names())

    patterns: dict = {}

    # PATTERN 1: tool_frequency
    tool_freq: dict[str, dict] = {}
    for tool in all_tool_names:
        counts = [float(t.tool_names().count(tool)) for t in traces]
        present = sum(1 for c in counts if c > 0)
        tool_freq[tool] = {
            "mean": _mean(counts),
            "std": _std(counts),
            "min": round(min(counts), 4),
            "max": round(max(counts), 4),
            "present_in_pct": round(present / n, 4),
        }
    patterns["tool_frequency"] = tool_freq

    # PATTERN 2: step_count
    step_counts = [float(len(t.steps)) for t in traces]
    patterns["step_count"] = {
        "mean": _mean(step_counts),
        "std": _std(step_counts),
        "min": round(min(step_counts), 4),
        "max": round(max(step_counts), 4),
        "p95": _percentile(step_counts, 95),
    }

    # PATTERN 3: tool_sequence (bigrams + trigrams)
    bigram_counter: Counter = Counter()
    trigram_counter: Counter = Counter()
    for t in traces:
        names = t.tool_names()
        for i in range(len(names) - 1):
            bigram_counter[(names[i], names[i + 1])] += 1
        for i in range(len(names) - 2):
            trigram_counter[(names[i], names[i + 1], names[i + 2])] += 1
    patterns["tool_sequence"] = {
        "bigrams": {str(k): v for k, v in bigram_counter.most_common(20)},
        "trigrams": {str(k): v for k, v in trigram_counter.most_common(20)},
    }

    # PATTERN 4: tool_ordering
    strong_orderings: list[dict] = []
    tool_list = sorted(all_tool_names)
    for i, tool_a in enumerate(tool_list):
        for tool_b in tool_list[i + 1:]:
            a_before_b = 0
            b_before_a = 0
            for t in traces:
                names = t.tool_names()
                a_idx = next((j for j, nm in enumerate(names) if nm == tool_a), None)
                b_idx = next((j for j, nm in enumerate(names) if nm == tool_b), None)
                if a_idx is not None and b_idx is not None:
                    if a_idx < b_idx:
                        a_before_b += 1
                    else:
                        b_before_a += 1
            total = a_before_b + b_before_a
            if total == 0:
                continue
            if a_before_b / total >= 0.8:
                strong_orderings.append({
                    "before": tool_a,
                    "after": tool_b,
                    "confidence": round(a_before_b / total, 4),
                })
            elif b_before_a / total >= 0.8:
                strong_orderings.append({
                    "before": tool_b,
                    "after": tool_a,
                    "confidence": round(b_before_a / total, 4),
                })
    patterns["tool_ordering"] = {"strong_orderings": strong_orderings}

    # PATTERN 5: first_tool
    first_counter: Counter = Counter()
    for t in traces:
        calls = t.tool_calls()
        if calls:
            first_counter[calls[0].name] += 1
    patterns["first_tool"] = {
        "distribution": dict(first_counter),
        "total": n,
    }

    # PATTERN 6: duration_range (only when timestamps present)
    duration_data: dict[str, list[float]] = {}
    for t in traces:
        for step in t.tool_calls():
            if step.duration_ms is not None:
                duration_data.setdefault(step.name, []).append(step.duration_ms)
    duration_range: dict[str, dict] = {}
    for tool, durs in duration_data.items():
        if len(durs) >= 3:
            duration_range[tool] = {
                "mean": _mean(durs),
                "std": _std(durs),
                "p95": _percentile(durs, 95),
            }
    if duration_range:
        patterns["duration_range"] = duration_range

    return patterns
