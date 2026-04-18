from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from trajex.result import AssertionResult, TrajectoryAssertion, TrajectoryReport

if TYPE_CHECKING:
    from trajex.trace import Trace

logger = logging.getLogger("trajex")


def assert_trajectory(
    trace: "Trace",
    assertions: list[TrajectoryAssertion],
    *,
    raise_on_failure: bool = True,
    print_report: bool = False,
) -> TrajectoryReport:
    report = TrajectoryReport(trace_prompt=trace.prompt, trace_id=trace.id)

    for assertion in assertions:
        try:
            result = assertion.check(trace)
        except Exception as exc:
            result = AssertionResult(
                passed=False,
                name=getattr(assertion, "name", "unknown"),
                message=f"Assertion raised an unexpected error: {exc}",
            )
        report.results.append(result)

    if print_report:
        from trajex.formatter import format_trajectory_report
        print(format_trajectory_report(report))

    if raise_on_failure and report.failed:
        lines = [
            f"Trajex: {len(report.failures)} assertion(s) failed",
            f"Prompt: {trace.prompt[:80]!r}",
            f"Trace ID: {trace.id}",
            "",
        ]
        for result in report.failures:
            lines.append(f"  x {result.name}")
            lines.append(f"    {result.message}")
            if result.detail:
                for detail_line in result.detail.splitlines():
                    lines.append(f"    {detail_line}")
            lines.append("")
        raise AssertionError("\n".join(lines))

    return report
