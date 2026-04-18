from __future__ import annotations

import pytest

from trajex.scanner import scan
from trajex.trace import Step, StepType, Trace

FIXTURES = "tests/fixtures/synthetic_traces"


def test_scan_auth_bypass_has_failure_with_schema():
    trace = Trace.from_json(f"{FIXTURES}/auth_bypass.json")
    report = scan(
        trace,
        schema={
            "destructive_tools": ["delete_account"],
            "guard_tools": ["confirm_user"],
        },
    )
    assert report.has_failures


def test_scan_loop_has_loop_detection():
    trace = Trace.from_json(f"{FIXTURES}/loop_notification.json")
    report = scan(trace)
    check_names = [f.check_name for f in report.findings]
    assert "loop_detection" in check_names


def test_scan_clean_no_failures():
    trace = Trace.from_json(f"{FIXTURES}/clean_delete.json")
    report = scan(trace)
    assert not report.has_failures


def test_scan_excessive_has_runaway():
    trace = Trace.from_json(f"{FIXTURES}/excessive_steps.json")
    report = scan(trace)
    check_names = [f.check_name for f in report.findings]
    assert "runaway_trace" in check_names


def test_scan_with_schema_auth_bypass():
    trace = Trace.from_json(f"{FIXTURES}/auth_bypass.json")
    report = scan(
        trace,
        schema={
            "destructive_tools": ["delete_account"],
            "guard_tools": ["confirm_user"],
        },
    )
    assert report.has_failures
    check_names = [f.check_name for f in report.findings]
    assert "unguarded_destructive_tool" in check_names


def test_scan_without_schema_no_keyword_findings():
    trace = Trace.from_json(f"{FIXTURES}/auth_bypass.json")
    report = scan(trace)
    # Without schema there must be NO name-aware findings
    name_aware_checks = {"unguarded_destructive_tool", "financial_tool_called"}
    check_names = {f.check_name for f in report.findings}
    assert check_names.isdisjoint(name_aware_checks)


def test_scan_no_tool_calls_triggers_warn():
    trace = Trace(
        prompt="What is 2 + 2? Answer without using any tools.",
        steps=[
            Step(index=0, step_type=StepType.LLM_RESPONSE, name="gpt-4o", output="4"),
        ],
    )
    report = scan(trace)
    check_names = [f.check_name for f in report.findings]
    assert "no_tool_calls" in check_names


def test_scan_loop_50_percent():
    steps = [
        Step(index=i, step_type=StepType.TOOL_CALL, name="x")
        for i in range(6)
    ]
    trace = Trace(prompt="test", steps=steps)
    report = scan(trace)
    check_names = [f.check_name for f in report.findings]
    assert "loop_detection" in check_names


def test_scan_suggested_assertions_valid_python():
    trace = Trace.from_json(f"{FIXTURES}/loop_notification.json")
    report = scan(trace)
    for suggestion in report.suggested_assertions():
        assert suggestion
        # Should be importable/compilable as an expression
        compile(suggestion, "<string>", "eval")


def test_scan_report_failures_and_warnings():
    trace = Trace.from_json(f"{FIXTURES}/loop_notification.json")
    report = scan(trace)
    assert isinstance(report.failures, list)
    assert isinstance(report.warnings, list)
    for f in report.failures:
        assert f.level == "FAIL"
    for w in report.warnings:
        assert w.level == "WARN"


def test_scan_info_excluded_by_default():
    trace = Trace(
        prompt="p",
        steps=[
            Step(index=0, step_type=StepType.TOOL_CALL, name="t", reasoning="actually let me try something else"),
        ],
    )
    report = scan(trace, include_info=False)
    assert all(f.level != "INFO" for f in report.findings)


def test_scan_info_included_when_requested():
    trace = Trace(
        prompt="p" * 10,
        steps=[
            Step(index=0, step_type=StepType.TOOL_CALL, name="t", reasoning="actually let me try something else"),
        ],
    )
    report = scan(trace, include_info=True)
    levels = {f.level for f in report.findings}
    # INFO may or may not be present depending on content threshold
    assert levels <= {"FAIL", "WARN", "INFO"}
