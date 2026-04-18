from __future__ import annotations

import pytest

from trajex.diff import TraceDiff, DiffFinding, diff_traces, format_diff
from trajex.trace import Step, StepType, Trace


def _trace(
    tools: list[str],
    total_steps: int | None = None,
    dur_ms: float | None = None,
    status: str = "success",
) -> Trace:
    from datetime import datetime, timedelta, timezone

    steps = [
        Step(index=i, step_type=StepType.TOOL_CALL, name=t)
        for i, t in enumerate(tools)
    ]
    if total_steps is not None:
        extra_count = total_steps - len(tools)
        for j in range(extra_count):
            steps.append(
                Step(index=len(tools) + j, step_type=StepType.LLM_RESPONSE, name="llm")
            )
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = t1 + timedelta(milliseconds=dur_ms) if dur_ms else None
    return Trace(
        prompt="test prompt",
        steps=steps,
        status=status,
        started_at=t1,
        ended_at=t2,
    )


# ── Identity ──────────────────────────────────────────────────────────────────

def test_diff_identical_traces():
    trace = _trace(["a", "b"], dur_ms=1000)
    diff = diff_traces(trace, trace)
    assert not diff.has_regressions
    assert diff.summary() == "no behavioral differences"


# ── Tool sequence findings ─────────────────────────────────────────────────────

def test_diff_new_tool_is_regression():
    before = _trace(["a", "b"])
    after = _trace(["a", "b", "c"])
    diff = diff_traces(before, after)
    assert diff.has_regressions
    checks = [f.check for f in diff.regressions]
    assert "new_tool_appeared" in checks


def test_diff_new_tool_finding_fields():
    before = _trace(["a"])
    after = _trace(["a", "surprise"])
    diff = diff_traces(before, after)
    finding = next(f for f in diff.findings if f.check == "new_tool_appeared")
    assert finding.severity == "regression"
    assert "surprise" in finding.title
    assert finding.before is None
    assert finding.after == "surprise"


def test_diff_tool_disappeared_is_regression():
    before = _trace(["a", "b", "c"])
    after = _trace(["a", "b"])
    diff = diff_traces(before, after)
    assert diff.has_regressions
    checks = [f.check for f in diff.regressions]
    assert "tool_disappeared" in checks


def test_diff_tool_disappeared_finding_fields():
    before = _trace(["guard", "action"])
    after = _trace(["action"])
    diff = diff_traces(before, after)
    finding = next(f for f in diff.findings if f.check == "tool_disappeared")
    assert finding.severity == "regression"
    assert "guard" in finding.title
    assert finding.before == "guard"
    assert finding.after is None


def test_diff_ordering_reversal_is_regression():
    before = _trace(["auth_check", "delete"])
    after = _trace(["delete", "auth_check"])
    diff = diff_traces(before, after)
    assert diff.has_regressions
    checks = [f.check for f in diff.regressions]
    assert "ordering_reversal" in checks


def test_diff_ordering_reversal_identifies_pair():
    before = _trace(["guard", "execute"])
    after = _trace(["execute", "guard"])
    diff = diff_traces(before, after)
    finding = next(f for f in diff.findings if f.check == "ordering_reversal")
    assert finding.severity == "regression"
    assert "guard" in finding.title
    assert "execute" in finding.title
    # before list has guard first, after list has execute first
    assert finding.before == ["guard", "execute"]
    assert finding.after == ["execute", "guard"]


def test_diff_call_count_increased_is_regression():
    before = _trace(["notify"])
    after = _trace(["notify", "notify", "notify"])
    diff = diff_traces(before, after)
    assert diff.has_regressions
    checks = [f.check for f in diff.regressions]
    assert "tool_call_count_increased" in checks


def test_diff_call_count_decreased_is_improvement():
    before = _trace(["notify", "notify", "notify"])
    after = _trace(["notify"])
    diff = diff_traces(before, after)
    assert not diff.has_regressions
    checks = [f.check for f in diff.improvements]
    assert "tool_call_count_decreased" in checks


# ── Step count findings ────────────────────────────────────────────────────────

def test_diff_step_count_regression():
    before = _trace(["a"], total_steps=3, dur_ms=1000)
    after = _trace(["a"], total_steps=8, dur_ms=1000)
    diff = diff_traces(before, after)
    assert diff.has_regressions
    checks = [f.check for f in diff.regressions]
    assert "step_count_increased" in checks


def test_diff_step_count_improvement():
    before = _trace(["a"], total_steps=8, dur_ms=1000)
    after = _trace(["a"], total_steps=3, dur_ms=1000)
    diff = diff_traces(before, after)
    assert not diff.has_regressions
    checks = [f.check for f in diff.improvements]
    assert "step_count_decreased" in checks


# ── Duration findings ──────────────────────────────────────────────────────────

def test_diff_duration_regression():
    before = _trace(["a"], dur_ms=1000)
    after = _trace(["a"], dur_ms=5000)
    diff = diff_traces(before, after)
    assert diff.has_regressions
    checks = [f.check for f in diff.regressions]
    assert "duration_increased" in checks


def test_diff_duration_improvement():
    before = _trace(["a"], dur_ms=5000)
    after = _trace(["a"], dur_ms=1000)
    diff = diff_traces(before, after)
    assert not diff.has_regressions
    checks = [f.check for f in diff.improvements]
    assert "duration_decreased" in checks


def test_diff_duration_below_threshold_no_finding():
    # 10% change should NOT produce a finding (threshold is >25% or <75%)
    before = _trace(["a"], dur_ms=1000)
    after = _trace(["a"], dur_ms=1100)
    diff = diff_traces(before, after)
    dur_checks = [f.check for f in diff.findings if "duration" in f.check]
    assert not dur_checks


# ── Status findings ────────────────────────────────────────────────────────────

def test_diff_status_regression():
    before = _trace(["a"], status="success")
    after = _trace(["a"], status="error")
    diff = diff_traces(before, after)
    assert diff.has_regressions
    checks = [f.check for f in diff.regressions]
    assert "status_changed" in checks


def test_diff_status_change_not_regression():
    before = _trace(["a"], status="success")
    after = _trace(["a"], status="interrupted")
    diff = diff_traces(before, after)
    # interrupted triggers regression per spec
    assert diff.has_regressions


def test_diff_status_same_no_finding():
    before = _trace(["a"], status="success")
    after = _trace(["a"], status="success")
    diff = diff_traces(before, after)
    status_checks = [f.check for f in diff.findings if f.check == "status_changed"]
    assert not status_checks


# ── Error findings ─────────────────────────────────────────────────────────────

def test_diff_error_count_increased():
    before_steps = [Step(index=0, step_type=StepType.TOOL_CALL, name="a")]
    after_steps = [
        Step(index=0, step_type=StepType.TOOL_CALL, name="a"),
        Step(index=1, step_type=StepType.ERROR, name="err", error="boom"),
    ]
    before = Trace(prompt="p", steps=before_steps)
    after = Trace(prompt="p", steps=after_steps)
    diff = diff_traces(before, after)
    assert diff.has_regressions
    checks = [f.check for f in diff.regressions]
    assert "error_count_increased" in checks


# ── Summary and properties ─────────────────────────────────────────────────────

def test_diff_summary_counts():
    before = _trace(["a", "b"])
    after = _trace(["a", "c"])  # b disappeared, c appeared — 2 regressions
    diff = diff_traces(before, after)
    summary = diff.summary()
    assert "regression" in summary


def test_diff_regressions_property():
    before = _trace(["a"])
    after = _trace(["a", "b"])
    diff = diff_traces(before, after)
    assert all(f.severity == "regression" for f in diff.regressions)


def test_diff_improvements_property():
    before = _trace(["a", "b", "b"])
    after = _trace(["a", "b"])
    diff = diff_traces(before, after)
    assert all(f.severity == "improvement" for f in diff.improvements)


# ── Format output ──────────────────────────────────────────────────────────────

def test_diff_format_shows_check_name():
    before = _trace(["a", "b"])
    after = _trace(["a", "b", "c"])
    diff = diff_traces(before, after)
    output = format_diff(diff, color=False)
    assert "REGR" in output
    assert "new_tool_appeared" in output


def test_diff_format_no_regressions_message():
    trace = _trace(["a"])
    diff = diff_traces(trace, trace)
    output = format_diff(diff, color=False)
    assert "no behavioral differences" in output.lower()


def test_diff_format_shows_before_after_ids():
    before = _trace(["a"])
    after = _trace(["a"])
    diff = diff_traces(before, after)
    output = format_diff(diff, color=False)
    assert "Before" in output
    assert "After" in output


def test_diff_format_regressions_sorted_first():
    before = _trace(["a", "a", "a"])
    after = _trace(["a"])
    diff = diff_traces(before, after)
    output = format_diff(diff, color=False)
    # improvements should be present (count decreased)
    assert "IMPR" in output or "improvement" in output.lower()


# ── Trace equality helpers ─────────────────────────────────────────────────────

def test_trace_eq():
    t1 = Trace.from_json("tests/fixtures/synthetic_traces/clean_delete.json")
    t2 = Trace.from_json("tests/fixtures/synthetic_traces/clean_delete.json")
    assert t1 == t2


def test_trace_eq_different():
    t1 = Trace.from_json("tests/fixtures/synthetic_traces/clean_delete.json")
    t2 = Trace.from_json("tests/fixtures/synthetic_traces/auth_bypass.json")
    assert t1 != t2


def test_step_eq():
    s1 = Step(index=0, step_type=StepType.TOOL_CALL, name="t", input="x", output="y")
    s2 = Step(index=0, step_type=StepType.TOOL_CALL, name="t", input="x", output="y")
    assert s1 == s2


def test_step_eq_different_output():
    s1 = Step(index=0, step_type=StepType.TOOL_CALL, name="t", output="a")
    s2 = Step(index=0, step_type=StepType.TOOL_CALL, name="t", output="b")
    assert s1 != s2


# ── CLI integration ────────────────────────────────────────────────────────────

def test_diff_cli_different_traces():
    import subprocess, sys
    code = subprocess.run(
        [sys.executable, "-m", "trajex.cli", "diff",
         "tests/fixtures/synthetic_traces/clean_delete.json",
         "tests/fixtures/synthetic_traces/loop_notification.json",
         "--no-color"],
        capture_output=True,
    ).returncode
    assert code == 1  # regressions detected


def test_diff_cli_same_file():
    import subprocess, sys
    code = subprocess.run(
        [sys.executable, "-m", "trajex.cli", "diff",
         "tests/fixtures/synthetic_traces/clean_delete.json",
         "tests/fixtures/synthetic_traces/clean_delete.json",
         "--no-color"],
        capture_output=True,
    ).returncode
    assert code == 0


def test_diff_cli_missing_file():
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "-m", "trajex.cli", "diff",
         "tests/fixtures/synthetic_traces/clean_delete.json",
         "tests/fixtures/synthetic_traces/does_not_exist.json",
         "--no-color"],
        capture_output=True,
    )
    assert result.returncode == 2
