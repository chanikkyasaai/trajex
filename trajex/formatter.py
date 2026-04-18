from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trajex.result import TrajectoryReport
    from trajex.scanner import ScanReport, ScanFinding
    from trajex.trace import Trace

_RESET = "\033[0m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_GREEN = "\033[92m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(text: str, code: str, color: bool) -> str:
    if not color:
        return text
    return f"{code}{text}{_RESET}"


def _level_badge(level: str, color: bool) -> str:
    if level == "FAIL":
        return _c("FAIL", _RED + _BOLD, color)
    if level == "WARN":
        return _c("WARN", _YELLOW, color)
    return _c("INFO", _DIM, color)


def format_scan_report(
    report: "ScanReport",
    trace: "Trace",
    color: bool | None = None,
) -> str:
    """Format a scan report. Requires the Trace for header stats."""
    if color is None:
        color = _supports_color()

    from trajex import __version__

    prompt_snippet = repr(report.prompt[:50])
    total_steps = len(trace.steps)
    tool_call_count = trace.total_tool_calls()

    lines: list[str] = [""]
    lines.append(
        f"Trajex v{__version__}  -  "
        f"{total_steps} step(s) . {tool_call_count} tool call(s) . {prompt_snippet}"
    )
    lines.append("")

    if not report.findings:
        lines.append(_c("  No issues found in this trace.", _GREEN, color))
        lines.append("")
        return "\n".join(lines)

    for finding in report.findings:
        badge = _level_badge(finding.level, color)
        lines.append(f"  {badge}  {finding.title}")
        for detail_line in finding.detail.splitlines():
            lines.append(f"        {detail_line}")
        if finding.suggested_assertion:
            fix = f"        -> fix: {finding.suggested_assertion}"
            lines.append(_c(fix, _CYAN, color))
        lines.append("")

    sep = "  " + "-" * 50
    lines.append(sep)

    fail_count = len(report.failures)
    if fail_count > 0:
        summary = (
            f"  {fail_count} silent failure(s). "
            "These pass all current tests and will corrupt production.\n"
            "  Run: trajex init  ->  generate test file that catches them"
        )
        lines.append(_c(summary, _RED + _BOLD, color))
    else:
        warn_count = len(report.warnings)
        lines.append(
            _c(f"  {warn_count} warning(s). No critical failures found.", _YELLOW, color)
        )

    lines.append("")
    return "\n".join(lines)


# Legacy alias kept for internal callers that don't have a Trace reference.
# Uses placeholder stats — prefer format_scan_report(report, trace) instead.
def format_scan_report_with_trace(
    report: "ScanReport",
    total_steps: int,
    tool_call_count: int,
    color: bool | None = None,
) -> str:
    if color is None:
        color = _supports_color()

    from trajex import __version__

    prompt_snippet = repr(report.prompt[:50])
    lines: list[str] = [""]
    lines.append(
        f"Trajex v{__version__}  -  "
        f"{total_steps} step(s) . {tool_call_count} tool call(s) . {prompt_snippet}"
    )
    lines.append("")

    if not report.findings:
        lines.append(_c("  No issues found in this trace.", _GREEN, color))
        lines.append("")
        return "\n".join(lines)

    for finding in report.findings:
        badge = _level_badge(finding.level, color)
        lines.append(f"  {badge}  {finding.title}")
        for detail_line in finding.detail.splitlines():
            lines.append(f"        {detail_line}")
        if finding.suggested_assertion:
            fix = f"        -> fix: {finding.suggested_assertion}"
            lines.append(_c(fix, _CYAN, color))
        lines.append("")

    sep = "  " + "-" * 50
    lines.append(sep)

    fail_count = len(report.failures)
    if fail_count > 0:
        summary = (
            f"  {fail_count} silent failure(s). "
            "These pass all current tests and will corrupt production.\n"
            "  Run: trajex init  ->  generate test file that catches them"
        )
        lines.append(_c(summary, _RED + _BOLD, color))
    else:
        warn_count = len(report.warnings)
        lines.append(
            _c(f"  {warn_count} warning(s). No critical failures found.", _YELLOW, color)
        )

    lines.append("")
    return "\n".join(lines)


def format_trajectory_report(report: "TrajectoryReport", color: bool | None = None) -> str:
    if color is None:
        color = _supports_color()

    lines: list[str] = [""]
    lines.append(f"Trajectory report for: {report.trace_prompt[:60]!r}")
    lines.append(f"Trace ID: {report.trace_id}")
    lines.append("")

    for result in report.results:
        if result.passed:
            marker = _c("  PASS", _GREEN, color)
        else:
            marker = _c("  FAIL", _RED, color)
        lines.append(f"{marker}  {result.name}")
        if not result.passed:
            lines.append(f"        {result.message}")
            if result.detail:
                for dl in result.detail.splitlines():
                    lines.append(f"        {dl}")
        lines.append("")

    summary = report.summary()
    if report.failed:
        lines.append(_c(f"  {summary}", _RED, color))
    else:
        lines.append(_c(f"  {summary}", _GREEN, color))
    lines.append("")
    return "\n".join(lines)
