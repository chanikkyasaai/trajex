from __future__ import annotations

from trajex.trace import Trace, Step, StepType
from trajex.result import AssertionResult, TrajectoryAssertion, TrajectoryReport
from trajex.engine import assert_trajectory
from trajex.scanner import scan, ScanReport, ScanFinding
from trajex.diff import diff_traces, TraceDiff, DiffFinding
from trajex.emitters.generic import (
    capture_trace,
    capture_trace_async,
    record_tool_call,
    record_tool_call_async,
)
from trajex.baseline import BaselineModel
from trajex.anomaly import detect_anomalies, AnomalyFinding
from trajex.store import TraceStore

__version__ = "0.3.0"


def learn(
    traces_dir: str | None = None,
    traces: list | None = None,
    name: str | None = None,
    description: str = "",
    save: bool = True,
) -> BaselineModel:
    """
    Learn a behavioral baseline from passing traces.

    Usage:
        # From a directory of trace files
        baseline = trajex.learn("tests/fixtures/real_traces/")

        # From trace objects
        baseline = trajex.learn(traces=[trace1, trace2, trace3])

        # Without saving to SQLite
        baseline = trajex.learn("traces/", save=False)
    """
    from pathlib import Path

    if traces is None:
        if traces_dir is None:
            raise ValueError("Provide traces_dir or traces")
        trace_files = list(Path(traces_dir).glob("*.json"))
        if not trace_files:
            raise ValueError(f"No .json files found in {traces_dir}")
        traces = []
        for f in trace_files:
            try:
                traces.append(Trace.from_json(str(f)))
            except Exception as exc:
                print(f"  Warning: skipping {f.name} -- {exc}")

    baseline = BaselineModel.learn(traces, name=name, description=description)

    if save:
        baseline.save()
        print(f"Saved baseline '{baseline.name}' (ID: {baseline.id[:8]})")

    return baseline


def check_anomalies(
    trace: Trace,
    baseline: "BaselineModel | str | None" = None,
) -> list[AnomalyFinding]:
    """
    Check a trace for behavioral anomalies against a baseline.

    Usage:
        findings = trajex.check_anomalies(trace, baseline)
        findings = trajex.check_anomalies(trace, "baseline-id")
        findings = trajex.check_anomalies(trace)  # uses most recent
    """
    if baseline is None:
        store = TraceStore()
        baselines = store.list_baselines()
        if not baselines:
            raise ValueError("No baselines saved. Run trajex.learn() first.")
        baseline = store.load_baseline(baselines[-1]["id"])
    elif isinstance(baseline, str):
        store = TraceStore()
        b = store.find_baseline(baseline)
        if b is None:
            b = store.load_baseline(baseline)
        baseline = b

    return detect_anomalies(trace, baseline)


__all__ = [
    # Core model
    "Trace",
    "Step",
    "StepType",
    # Assertion primitives
    "AssertionResult",
    "TrajectoryAssertion",
    "TrajectoryReport",
    # Main entry points
    "assert_trajectory",
    "scan",
    "ScanReport",
    "ScanFinding",
    # Regression testing
    "diff_traces",
    "TraceDiff",
    "DiffFinding",
    # Emitter decorators
    "capture_trace",
    "capture_trace_async",
    "record_tool_call",
    "record_tool_call_async",
    # Learning system
    "BaselineModel",
    "AnomalyFinding",
    "TraceStore",
    "learn",
    "check_anomalies",
    # Version
    "__version__",
]
