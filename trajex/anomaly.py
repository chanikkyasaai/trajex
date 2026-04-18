from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class AnomalyFinding:
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    check_name: str
    title: str
    detail: str
    confidence: float
    expected: str
    observed: str
    step_indices: list[int] = field(default_factory=list)


_SEV_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def detect_anomalies(trace, baseline) -> list[AnomalyFinding]:
    findings: list[AnomalyFinding] = []

    # CHECK 1: step_count_anomaly
    sc = baseline.patterns.get("step_count")
    if sc:
        bm = sc["mean"]
        bs = sc["std"]
        observed = len(trace.steps)
        z = abs(observed - bm) / max(bs, 0.1)
        if z > 2.0:
            sev: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH" if z > 3.0 else "MEDIUM"
            conf = round(min(0.99, z / 5) if z > 3.0 else min(0.85, z / 4), 4)
            findings.append(AnomalyFinding(
                severity=sev,
                check_name="step_count_anomaly",
                title="Unusual step count",
                detail=(
                    f"This trace has {observed} steps. "
                    f"Baseline: {bm:.1f} +/- {bs:.1f}. "
                    f"{observed} steps is {z:.1f} standard deviations from normal."
                ),
                confidence=conf,
                expected=f"{bm:.1f} +/- {bs:.1f} steps",
                observed=f"{observed} steps",
            ))

    # CHECK 2: new_tool_appeared
    tf = baseline.patterns.get("tool_frequency", {})
    if tf:
        baseline_tools = set(tf.keys())
        trace_tool_names = trace.tool_names()
        trace_tools = set(trace_tool_names)
        for tool in sorted(trace_tools - baseline_tools):
            indices = [i for i, n in enumerate(trace_tool_names) if n == tool]
            findings.append(AnomalyFinding(
                severity="HIGH",
                check_name="new_tool_appeared",
                title=f"New tool appeared: '{tool}'",
                detail=(
                    f"'{tool}' was never called in any of the "
                    f"{baseline.trace_count} baseline traces. "
                    f"This tool call has no historical precedent."
                ),
                confidence=1.0,
                expected=f"tool not seen in {baseline.trace_count} baseline traces",
                observed=f"called {trace_tool_names.count(tool)} time(s)",
                step_indices=indices,
            ))

    # CHECK 3: tool_disappeared
    if tf:
        always_present = {t for t, s in tf.items() if s["present_in_pct"] >= 0.95}
        trace_tools = set(trace.tool_names())
        for tool in sorted(always_present - trace_tools):
            pct = tf[tool]["present_in_pct"]
            findings.append(AnomalyFinding(
                severity="HIGH",
                check_name="tool_disappeared",
                title=f"Expected tool missing: '{tool}'",
                detail=(
                    f"'{tool}' was present in {pct*100:.0f}% of baseline traces. "
                    f"It was not called in this trace."
                ),
                confidence=round(pct, 4),
                expected=f"present in {pct*100:.0f}% of baseline traces",
                observed="not called",
            ))

    # CHECK 4: ordering_violation
    orderings = baseline.patterns.get("tool_ordering", {}).get("strong_orderings", [])
    trace_names = trace.tool_names()
    for ordering in orderings:
        bt = ordering["before"]
        at = ordering["after"]
        conf = ordering["confidence"]
        b_idx = next((i for i, n in enumerate(trace_names) if n == bt), None)
        a_idx = next((i for i, n in enumerate(trace_names) if n == at), None)
        if b_idx is not None and a_idx is not None and a_idx < b_idx:
            findings.append(AnomalyFinding(
                severity="HIGH",
                check_name="ordering_violation",
                title=f"Ordering reversal: '{at}' before '{bt}'",
                detail=(
                    f"In {conf*100:.0f}% of baseline traces, "
                    f"'{bt}' comes before '{at}'. "
                    f"In this trace the order is reversed."
                ),
                confidence=round(conf, 4),
                expected=f"'{bt}' before '{at}'",
                observed=f"'{at}' at step {a_idx}, '{bt}' at step {b_idx}",
                step_indices=[a_idx, b_idx],
            ))

    # CHECK 5: tool_frequency_spike
    if tf:
        trace_tool_names = trace.tool_names()
        for tool in set(trace_tool_names):
            if tool not in tf:
                continue
            stats = tf[tool]
            count = trace_tool_names.count(tool)
            z = (count - stats["mean"]) / max(stats["std"], 0.1)
            if z > 2.5:
                sev2: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH" if z >= 3.5 else "MEDIUM"
                indices = [i for i, n in enumerate(trace_tool_names) if n == tool]
                findings.append(AnomalyFinding(
                    severity=sev2,
                    check_name="tool_frequency_spike",
                    title=f"'{tool}' called {count}x -- unusually high",
                    detail=(
                        f"Baseline: {stats['mean']:.1f} +/- {stats['std']:.1f} calls. "
                        f"This trace called it {count} times "
                        f"({z:.1f} standard deviations above normal)."
                    ),
                    confidence=round(min(0.95, z / 4), 4),
                    expected=f"{stats['mean']:.1f} +/- {stats['std']:.1f} calls",
                    observed=f"{count} calls",
                    step_indices=indices,
                ))

    # CHECK 6: unexpected_first_tool
    bf = baseline.patterns.get("first_tool", {})
    if bf:
        dist = bf.get("distribution", {})
        total = bf.get("total", 0)
        calls = trace.tool_calls()
        if total > 0 and calls:
            actual_first = calls[0].name
            hist_pct = dist.get(actual_first, 0) / total
            if hist_pct < 0.05:
                most_common = max(dist, key=dist.get) if dist else "unknown"
                findings.append(AnomalyFinding(
                    severity="MEDIUM",
                    check_name="unexpected_first_tool",
                    title=f"Unexpected first tool: '{actual_first}'",
                    detail=(
                        f"'{actual_first}' was the first tool called in only "
                        f"{hist_pct*100:.1f}% of baseline traces. "
                        f"Most common first tool: '{most_common}' "
                        f"({dist.get(most_common, 0)/total*100:.0f}% of traces)."
                    ),
                    confidence=round(1.0 - hist_pct, 4),
                    expected=f"first tool is '{most_common}' in most baseline traces",
                    observed=f"first tool is '{actual_first}'",
                    step_indices=[0],
                ))

    findings.sort(key=lambda f: _SEV_ORDER[f.severity])
    return findings
