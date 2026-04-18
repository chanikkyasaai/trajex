"""
Tests for the behavioral learning system: learner, baseline, anomaly, store, CLI.
All offline — zero API calls.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import pytest

from trajex.trace import Trace, Step, StepType
from trajex.baseline import BaselineModel
from trajex.anomaly import detect_anomalies, AnomalyFinding
from trajex.store import TraceStore


# ── helpers ──────────────────────────────────────────────────────────────────

def make_trace(tool_names: list[str], prompt: str = "test prompt") -> Trace:
    """Build a minimal Trace with the given sequence of tool call steps."""
    steps = [
        Step(index=i, step_type=StepType.TOOL_CALL, name=name)
        for i, name in enumerate(tool_names)
    ]
    return Trace(prompt=prompt, steps=steps)


# ── learner / baseline ────────────────────────────────────────────────────────

def test_learn_from_traces():
    traces = [make_trace(["verify", "confirm", "delete"]) for _ in range(10)]
    baseline = BaselineModel.learn(traces, name="test")
    assert baseline.trace_count == 10
    assert "tool_frequency" in baseline.patterns
    assert "verify" in baseline.patterns["tool_frequency"]
    assert "confirm" in baseline.patterns["tool_frequency"]
    assert "delete" in baseline.patterns["tool_frequency"]


def test_step_count_pattern():
    traces = [make_trace(["a", "b", "c"]) for _ in range(10)]
    baseline = BaselineModel.learn(traces)
    sc = baseline.patterns["step_count"]
    assert sc["mean"] == 3.0
    assert sc["std"] == 0.0
    assert sc["min"] == 3.0
    assert sc["max"] == 3.0


def test_tool_frequency_present_in_pct():
    # "always" appears in all traces, "sometimes" in half
    traces = []
    for i in range(10):
        names = ["always"] + (["sometimes"] if i % 2 == 0 else [])
        traces.append(make_trace(names))
    baseline = BaselineModel.learn(traces)
    tf = baseline.patterns["tool_frequency"]
    assert tf["always"]["present_in_pct"] == 1.0
    assert tf["sometimes"]["present_in_pct"] == 0.5


def test_strong_ordering_learned():
    # confirm always before delete
    traces = [make_trace(["confirm", "delete"]) for _ in range(20)]
    baseline = BaselineModel.learn(traces)
    orderings = baseline.patterns["tool_ordering"]["strong_orderings"]
    assert any(o["before"] == "confirm" and o["after"] == "delete" for o in orderings)


def test_first_tool_pattern():
    traces = [make_trace(["verify", "delete"]) for _ in range(10)]
    baseline = BaselineModel.learn(traces)
    dist = baseline.patterns["first_tool"]["distribution"]
    assert dist.get("verify", 0) == 10


def test_bigrams_learned():
    traces = [make_trace(["a", "b", "c"]) for _ in range(5)]
    baseline = BaselineModel.learn(traces)
    bigrams = baseline.patterns["tool_sequence"]["bigrams"]
    assert any("a" in k and "b" in k for k in bigrams)


def test_empty_traces_returns_empty_patterns():
    baseline = BaselineModel.learn([])
    assert baseline.patterns == {}
    assert baseline.trace_count == 0


# ── anomaly detection ─────────────────────────────────────────────────────────

def test_new_tool_detected():
    traces = [make_trace(["verify", "delete"]) for _ in range(20)]
    baseline = BaselineModel.learn(traces)
    new_trace = make_trace(["verify", "drop_database", "delete"])
    findings = detect_anomalies(new_trace, baseline)
    assert any(
        f.check_name == "new_tool_appeared" and "drop_database" in f.title
        for f in findings
    )


def test_ordering_violation_detected():
    traces = [make_trace(["confirm", "delete"]) for _ in range(20)]
    baseline = BaselineModel.learn(traces)
    bad_trace = make_trace(["delete", "confirm"])
    findings = detect_anomalies(bad_trace, baseline)
    assert any(f.check_name == "ordering_violation" for f in findings)


def test_tool_disappeared_detected():
    traces = [make_trace(["verify", "delete"]) for _ in range(20)]
    baseline = BaselineModel.learn(traces)
    bad_trace = make_trace(["delete"])
    findings = detect_anomalies(bad_trace, baseline)
    assert any(
        f.check_name == "tool_disappeared" and "verify" in f.title
        for f in findings
    )


def test_frequency_spike_detected():
    traces = [make_trace(["notify"]) for _ in range(20)]
    baseline = BaselineModel.learn(traces)
    bad_trace = make_trace(["notify"] * 5)
    findings = detect_anomalies(bad_trace, baseline)
    assert any(f.check_name == "tool_frequency_spike" for f in findings)


def test_step_count_anomaly():
    traces = [make_trace(["a", "b", "c"]) for _ in range(20)]
    baseline = BaselineModel.learn(traces)
    long_trace = make_trace(["a"] * 20)
    findings = detect_anomalies(long_trace, baseline)
    assert any(f.check_name == "step_count_anomaly" for f in findings)


def test_unexpected_first_tool():
    # Always starts with "verify"
    traces = [make_trace(["verify", "delete"]) for _ in range(20)]
    baseline = BaselineModel.learn(traces)
    bad_trace = make_trace(["delete", "verify"])
    findings = detect_anomalies(bad_trace, baseline)
    assert any(f.check_name == "unexpected_first_tool" for f in findings)


def test_clean_trace_no_high_anomalies():
    traces = [make_trace(["verify", "confirm", "delete"]) for _ in range(20)]
    baseline = BaselineModel.learn(traces)
    clean = make_trace(["verify", "confirm", "delete"])
    findings = detect_anomalies(clean, baseline)
    highs = [f for f in findings if f.severity == "HIGH"]
    assert len(highs) == 0, f"False positives: {[f.title for f in highs]}"


def test_findings_sorted_high_first():
    traces = [make_trace(["a"]) for _ in range(20)]
    baseline = BaselineModel.learn(traces)
    # new tool (HIGH) + step count anomaly (potentially MEDIUM/HIGH)
    bad_trace = make_trace(["new_tool"] * 15)
    findings = detect_anomalies(bad_trace, baseline)
    if len(findings) > 1:
        _sev = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        for i in range(len(findings) - 1):
            assert _sev[findings[i].severity] <= _sev[findings[i + 1].severity]


def test_anomaly_finding_fields():
    traces = [make_trace(["verify", "delete"]) for _ in range(20)]
    baseline = BaselineModel.learn(traces)
    bad_trace = make_trace(["verify", "nuke"])
    findings = detect_anomalies(bad_trace, baseline)
    f = next(f for f in findings if f.check_name == "new_tool_appeared")
    assert f.severity == "HIGH"
    assert f.confidence == 1.0
    assert isinstance(f.expected, str)
    assert isinstance(f.observed, str)
    assert isinstance(f.step_indices, list)


# ── SQLite roundtrip ──────────────────────────────────────────────────────────

def test_sqlite_roundtrip(tmp_path):
    db_path = str(tmp_path / "test.db")
    store = TraceStore(db_path=db_path)
    traces = [make_trace(["a", "b", "c"]) for _ in range(5)]
    baseline = BaselineModel.learn(traces, name="roundtrip-test")
    saved_id = store.save_baseline(baseline)
    loaded = store.load_baseline(saved_id)
    assert loaded.name == "roundtrip-test"
    assert loaded.trace_count == 5
    assert loaded.patterns == baseline.patterns


def test_sqlite_list_and_delete(tmp_path):
    db_path = str(tmp_path / "test.db")
    store = TraceStore(db_path=db_path)
    traces = [make_trace(["x"]) for _ in range(3)]
    b = BaselineModel.learn(traces, name="to-delete")
    store.save_baseline(b)
    assert len(store.list_baselines()) == 1
    store.delete_baseline(b.id)
    assert len(store.list_baselines()) == 0


def test_sqlite_find_by_name(tmp_path):
    db_path = str(tmp_path / "test.db")
    store = TraceStore(db_path=db_path)
    traces = [make_trace(["x"]) for _ in range(3)]
    b = BaselineModel.learn(traces, name="named-baseline")
    store.save_baseline(b)
    found = store.find_baseline("named-baseline")
    assert found is not None
    assert found.id == b.id
    assert store.find_baseline("nonexistent") is None


def test_sqlite_overwrite_same_id(tmp_path):
    from dataclasses import replace
    db_path = str(tmp_path / "test.db")
    store = TraceStore(db_path=db_path)
    traces = [make_trace(["a"]) for _ in range(3)]
    b = BaselineModel.learn(traces, name="original")
    store.save_baseline(b)
    b2 = replace(b, name="updated")
    store.save_baseline(b2)
    loaded = store.load_baseline(b.id)
    assert loaded.name == "updated"
    assert len(store.list_baselines()) == 1


# ── CLI commands ──────────────────────────────────────────────────────────────

def test_learn_cli_command(tmp_path):
    for i in range(5):
        t = make_trace(["a", "b", "c"])
        (tmp_path / f"trace_{i}.json").write_text(t.to_json())

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as fh:
        db_path = fh.name
    try:
        result = subprocess.run(
            [sys.executable, "-m", "trajex.cli", "learn", str(tmp_path),
             "--name", "cli-test"],
            capture_output=True, text=True,
            env={**os.environ, "TRAJEX_DB": db_path},
        )
        assert result.returncode == 0
        assert "cli-test" in result.stdout
    finally:
        os.unlink(db_path)


def test_baseline_list_empty(tmp_path):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as fh:
        db_path = fh.name
    try:
        result = subprocess.run(
            [sys.executable, "-m", "trajex.cli", "baseline", "list"],
            capture_output=True, text=True,
            env={**os.environ, "TRAJEX_DB": db_path},
        )
        assert result.returncode == 0
        assert "No baselines" in result.stdout
    finally:
        os.unlink(db_path)


# ── guard import behaviour ────────────────────────────────────────────────────

def test_guard_raises_import_error_without_langgraph():
    result = subprocess.run(
        [sys.executable, "-c",
         "from trajex.guard import TrajexGuardNode; "
         "TrajexGuardNode(None, [], on_anomaly='block')"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "ImportError" in result.stderr or "LangGraph" in result.stderr


# ── public API smoke test ─────────────────────────────────────────────────────

def test_public_api_imports():
    import trajex
    assert hasattr(trajex, "BaselineModel")
    assert hasattr(trajex, "AnomalyFinding")
    assert hasattr(trajex, "TraceStore")
    assert hasattr(trajex, "learn")
    assert hasattr(trajex, "check_anomalies")
    assert trajex.__version__ == "0.3.0"
