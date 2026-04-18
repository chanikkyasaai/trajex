from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from trajex.trace import Step, StepType, Trace


FIXTURES = "tests/fixtures/synthetic_traces"


def _make_trace() -> Trace:
    return Trace(
        prompt="test prompt",
        steps=[
            Step(index=0, step_type=StepType.TOOL_CALL, name="tool_a", input="x", output="y"),
            Step(index=1, step_type=StepType.LLM_RESPONSE, name="gpt-4o", output="response"),
            Step(index=2, step_type=StepType.TOOL_CALL, name="tool_b", input="z"),
            Step(index=3, step_type=StepType.AGENT_FINISH, name="agent_finish", output="done"),
        ],
        final_output="done",
        metadata={"framework": "langchain"},
    )


def test_tool_calls_only_returns_tool_call_steps():
    trace = _make_trace()
    tool_calls = trace.tool_calls()
    assert len(tool_calls) == 2
    assert all(s.step_type == StepType.TOOL_CALL for s in tool_calls)


def test_tool_names():
    trace = _make_trace()
    assert trace.tool_names() == ["tool_a", "tool_b"]


def test_unique_tools_preserves_order():
    trace = Trace(
        prompt="p",
        steps=[
            Step(index=0, step_type=StepType.TOOL_CALL, name="b"),
            Step(index=1, step_type=StepType.TOOL_CALL, name="a"),
            Step(index=2, step_type=StepType.TOOL_CALL, name="b"),
        ],
    )
    assert trace.unique_tools_called() == ["b", "a"]


def test_total_duration_ms():
    t1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc)
    trace = Trace(prompt="p", started_at=t1, ended_at=t2)
    assert trace.total_duration_ms() == 5000.0


def test_total_duration_ms_none_without_timestamps():
    trace = Trace(prompt="p")
    assert trace.total_duration_ms() is None


def test_step_duration_computed():
    t1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
    step = Step(index=0, step_type=StepType.TOOL_CALL, name="t", started_at=t1, ended_at=t2)
    assert step.duration_ms == 2000.0


def test_roundtrip_to_dict_from_dict():
    trace = _make_trace()
    d = trace.to_dict()
    trace2 = Trace.from_dict(d)
    assert trace2.prompt == trace.prompt
    assert trace2.id == trace.id
    assert len(trace2.steps) == len(trace.steps)
    assert trace2.steps[0].name == trace.steps[0].name
    assert trace2.steps[0].step_type == trace.steps[0].step_type


def test_roundtrip_json_string():
    trace = _make_trace()
    trace2 = Trace.from_json_string(trace.to_json())
    assert trace2.prompt == trace.prompt
    assert len(trace2.steps) == len(trace.steps)


def test_to_dict_is_valid_json():
    trace = _make_trace()
    raw = json.dumps(trace.to_dict())
    assert json.loads(raw) is not None


def test_from_dict_missing_prompt_raises():
    with pytest.raises(ValueError, match="missing required field 'prompt'"):
        Trace.from_dict({"steps": []})


def test_from_dict_not_dict_raises():
    with pytest.raises(ValueError, match="expected a dict"):
        Trace.from_dict("not a dict")


def test_from_dict_unknown_step_type_degrades():
    trace = Trace.from_dict({"prompt": "x", "steps": [{"step_type": "unknown_type", "name": "t", "index": 0}]})
    assert trace.steps[0].step_type == StepType.TOOL_CALL


def test_from_dict_missing_steps():
    trace = Trace.from_dict({"prompt": "hello"})
    assert trace.steps == []


def test_fixture_clean_delete_loads():
    trace = Trace.from_json(f"{FIXTURES}/clean_delete.json")
    assert trace.prompt
    assert len(trace.steps) == 4
    assert trace.tool_names() == ["verify_permissions", "confirm_user", "delete_account"]


def test_fixture_loop_notification_loads():
    trace = Trace.from_json(f"{FIXTURES}/loop_notification.json")
    assert trace.tool_names().count("send_notification") == 4


def test_fixture_auth_bypass_loads():
    trace = Trace.from_json(f"{FIXTURES}/auth_bypass.json")
    assert trace.tool_names()[0] == "delete_account"


def test_fixture_excessive_steps_loads():
    trace = Trace.from_json(f"{FIXTURES}/excessive_steps.json")
    assert len(trace.steps) == 25


def test_reasoning_text():
    trace = Trace(
        prompt="p",
        steps=[
            Step(index=0, step_type=StepType.TOOL_CALL, name="t", reasoning="think 1"),
            Step(index=1, step_type=StepType.TOOL_CALL, name="t", reasoning=None),
            Step(index=2, step_type=StepType.TOOL_CALL, name="t", reasoning="think 2"),
        ],
    )
    assert trace.reasoning_text() == ["think 1", "think 2"]
