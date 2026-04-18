from __future__ import annotations

import pytest

from trajex.assertions import (
    max_steps,
    never_before,
    no_loop,
    sequence,
    tool_called,
    tool_never_called,
)
from trajex.trace import Step, StepType, Trace

FIXTURES = "tests/fixtures/synthetic_traces"


def _trace(*tool_names: str) -> Trace:
    steps = [
        Step(index=i, step_type=StepType.TOOL_CALL, name=name)
        for i, name in enumerate(tool_names)
    ]
    return Trace(prompt="test", steps=steps)


def _trace_with_steps(count: int) -> Trace:
    steps = [Step(index=i, step_type=StepType.LLM_CALL, name="llm") for i in range(count)]
    return Trace(prompt="test", steps=steps)


# --- sequence ---

def test_sequence_pass():
    trace = Trace.from_json(f"{FIXTURES}/clean_delete.json")
    result = sequence("verify_permissions", "confirm_user", "delete_account").check(trace)
    assert result.passed


def test_sequence_fail_wrong_order():
    trace = Trace.from_json(f"{FIXTURES}/auth_bypass.json")
    result = sequence("verify_permissions", "delete_account").check(trace)
    assert result.failed
    assert "Missing" in result.detail


def test_sequence_fail_missing_tool():
    trace = _trace("a", "c")
    result = sequence("a", "b", "c").check(trace)
    assert result.failed


def test_sequence_gaps_allowed():
    trace = _trace("a", "x", "y", "b")
    result = sequence("a", "b").check(trace)
    assert result.passed


def test_sequence_duplicate_names():
    trace = _trace("a", "x", "a", "b")
    result = sequence("a", "a", "b").check(trace)
    assert result.passed


def test_sequence_requires_two():
    with pytest.raises(ValueError):
        sequence("only_one")


def test_sequence_empty_trace():
    trace = Trace(prompt="p")
    result = sequence("a", "b").check(trace)
    assert result.failed


# --- never_before ---

def test_never_before_pass():
    trace = Trace.from_json(f"{FIXTURES}/clean_delete.json")
    result = never_before("delete_account", "confirm_user").check(trace)
    assert result.passed


def test_never_before_fail_no_guard():
    trace = Trace.from_json(f"{FIXTURES}/auth_bypass.json")
    result = never_before("delete_account", "verify_permissions").check(trace)
    assert result.failed
    assert "never called" in result.detail


def test_never_before_fail_wrong_order():
    trace = Trace.from_json(f"{FIXTURES}/auth_bypass.json")
    result = never_before("delete_account", "confirm_user").check(trace)
    assert result.failed
    assert "BEFORE" in result.detail


def test_never_before_tool_a_not_called():
    trace = _trace("a", "b")
    result = never_before("c", "a").check(trace)
    assert result.passed


# --- no_loop ---

def test_no_loop_fail():
    trace = Trace.from_json(f"{FIXTURES}/loop_notification.json")
    result = no_loop("send_notification", max_calls=1).check(trace)
    assert result.failed
    assert "4 times" in result.detail
    assert "3 excess" in result.detail


def test_no_loop_pass():
    trace = Trace.from_json(f"{FIXTURES}/clean_delete.json")
    result = no_loop("verify_permissions", max_calls=1).check(trace)
    assert result.passed


def test_no_loop_higher_limit():
    trace = Trace.from_json(f"{FIXTURES}/loop_notification.json")
    result = no_loop("send_notification", max_calls=5).check(trace)
    assert result.passed


def test_no_loop_zero_raises():
    with pytest.raises(ValueError):
        no_loop("x", max_calls=0)


def test_no_loop_excess_count_in_detail():
    trace = _trace("x", "x", "x")
    result = no_loop("x", max_calls=1).check(trace)
    assert result.failed
    assert "2 excess" in result.detail
    assert "steps: [0, 1, 2]" in result.detail


# --- max_steps ---

def test_max_steps_fail():
    trace = Trace.from_json(f"{FIXTURES}/excessive_steps.json")
    result = max_steps(10).check(trace)
    assert result.failed
    assert "over budget" in result.detail


def test_max_steps_pass():
    trace = Trace.from_json(f"{FIXTURES}/clean_delete.json")
    result = max_steps(10).check(trace)
    assert result.passed


def test_max_steps_zero_raises():
    with pytest.raises(ValueError):
        max_steps(0)


def test_max_steps_exact_limit():
    trace = _trace_with_steps(5)
    result = max_steps(5).check(trace)
    assert result.passed


# --- tool_called ---

def test_tool_called_pass():
    trace = Trace.from_json(f"{FIXTURES}/clean_delete.json")
    result = tool_called("verify_permissions").check(trace)
    assert result.passed


def test_tool_called_fail():
    trace = Trace.from_json(f"{FIXTURES}/auth_bypass.json")
    result = tool_called("verify_permissions").check(trace)
    assert result.failed
    assert "skipped entirely" in result.detail


# --- tool_never_called ---

def test_tool_never_called_pass():
    trace = Trace.from_json(f"{FIXTURES}/clean_delete.json")
    result = tool_never_called("drop_table").check(trace)
    assert result.passed


def test_tool_never_called_fail():
    trace = _trace("a", "b", "bad_tool")
    result = tool_never_called("bad_tool").check(trace)
    assert result.failed
    assert "NEVER" in result.detail
