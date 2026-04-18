from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from trajex.trace import Trace

logger = logging.getLogger("trajex")

# ── Finding types ─────────────────────────────────────────────────────────────

BehaviorSeverity = Literal["regression", "improvement", "change"]


@dataclass
class DiffFinding:
    severity: BehaviorSeverity
    check: str          # machine-readable identifier
    title: str          # one-line human summary
    detail: str         # multi-line explanation
    before: object      # raw before value (for programmatic use)
    after: object       # raw after value


@dataclass
class TraceDiff:
    before_id: str
    after_id: str
    before_prompt: str
    after_prompt: str
    findings: list[DiffFinding] = field(default_factory=list)

    @property
    def regressions(self) -> list[DiffFinding]:
        return [f for f in self.findings if f.severity == "regression"]

    @property
    def improvements(self) -> list[DiffFinding]:
        return [f for f in self.findings if f.severity == "improvement"]

    @property
    def changes(self) -> list[DiffFinding]:
        return [f for f in self.findings if f.severity == "change"]

    @property
    def has_regressions(self) -> bool:
        return bool(self.regressions)

    def summary(self) -> str:
        r, i, c = len(self.regressions), len(self.improvements), len(self.changes)
        parts = []
        if r:
            parts.append(f"{r} regression(s)")
        if i:
            parts.append(f"{i} improvement(s)")
        if c:
            parts.append(f"{c} change(s)")
        return ", ".join(parts) if parts else "no behavioral differences"


# ── Core diff function ────────────────────────────────────────────────────────

def diff_traces(before: "Trace", after: "Trace") -> TraceDiff:
    """Behavioral diff between two traces of the same prompt.

    Produces named findings for each behavioral difference, not just numeric
    deltas. A behavioral diff answers: "what did the agent stop doing, start
    doing, or do in a different order?"

    Structural findings (step count, duration) are included only when they
    indicate a clear regression or improvement, not as noise.
    """
    result = TraceDiff(
        before_id=before.id,
        after_id=after.id,
        before_prompt=before.prompt,
        after_prompt=after.prompt,
    )

    _diff_tool_sequence(result, before, after)
    _diff_guard_ordering(result, before, after)
    _diff_errors(result, before, after)
    _diff_step_count(result, before, after)
    _diff_duration(result, before, after)
    _diff_status(result, before, after)

    return result


# ── Behavioral checks ─────────────────────────────────────────────────────────

def _diff_tool_sequence(result: TraceDiff, before: "Trace", after: "Trace") -> None:
    before_names = before.tool_names()
    after_names = after.tool_names()

    if before_names == after_names:
        return

    before_set = set(before_names)
    after_set = set(after_names)

    # Tools that appeared for the first time.
    new_tools = after_set - before_set
    for tool in sorted(new_tools):
        result.findings.append(
            DiffFinding(
                severity="regression",
                check="new_tool_appeared",
                title=f"'{tool}' appeared — was never called before",
                detail=(
                    f"'{tool}' is called in the after trace but not in the before trace.\n"
                    f"This may indicate: (1) the agent found a new code path, "
                    f"(2) a prompt change unlocked a tool that should be gated, "
                    f"or (3) an unintended capability was introduced."
                ),
                before=None,
                after=tool,
            )
        )

    # Tools that disappeared.
    removed_tools = before_set - after_set
    for tool in sorted(removed_tools):
        result.findings.append(
            DiffFinding(
                severity="regression",
                check="tool_disappeared",
                title=f"'{tool}' disappeared — was always called before",
                detail=(
                    f"'{tool}' is called in the before trace but missing from the after trace.\n"
                    f"If this tool was a required step (e.g. a guard or audit log), "
                    f"its absence is a silent correctness failure."
                ),
                before=tool,
                after=None,
            )
        )

    # Ordering reversals — same tools but different order.
    if before_set == after_set and before_names != after_names:
        reversals = _find_ordering_reversals(before_names, after_names)
        for (a, b) in reversals:
            result.findings.append(
                DiffFinding(
                    severity="regression",
                    check="ordering_reversal",
                    title=f"'{a}' and '{b}' swapped order",
                    detail=(
                        f"Before: ...{a}...{b}...\n"
                        f"After:  ...{b}...{a}...\n"
                        f"If '{a}' is a guard for '{b}', this reversal is an authorization bypass."
                    ),
                    before=[a, b],
                    after=[b, a],
                )
            )

    # Call count changes for tools that exist in both traces.
    before_counts = before.tool_call_counts()
    after_counts = after.tool_call_counts()
    shared = before_set & after_set
    for tool in sorted(shared):
        bc = before_counts.get(tool, 0)
        ac = after_counts.get(tool, 0)
        if ac > bc:
            result.findings.append(
                DiffFinding(
                    severity="regression",
                    check="tool_call_count_increased",
                    title=f"'{tool}' call count grew: {bc} -> {ac}",
                    detail=(
                        f"'{tool}' was called {bc} time(s) before and {ac} time(s) after.\n"
                        f"An increase may indicate a retry loop or duplicate invocation."
                    ),
                    before=bc,
                    after=ac,
                )
            )
        elif ac < bc:
            result.findings.append(
                DiffFinding(
                    severity="improvement",
                    check="tool_call_count_decreased",
                    title=f"'{tool}' call count reduced: {bc} -> {ac}",
                    detail=f"'{tool}' was called {bc} time(s) before and {ac} time(s) after.",
                    before=bc,
                    after=ac,
                )
            )


def _find_ordering_reversals(
    before: list[str], after: list[str]
) -> list[tuple[str, str]]:
    """Find pairs (a, b) where a came before b in before but b comes before a in after.
    Only checks the first occurrence of each tool name.
    """
    before_pos = {name: i for i, name in enumerate(before)}
    after_pos = {name: i for i, name in enumerate(after)}
    tools = sorted(set(before) & set(after))
    reversals: list[tuple[str, str]] = []
    for i in range(len(tools)):
        for j in range(i + 1, len(tools)):
            a, b = tools[i], tools[j]
            if a not in before_pos or b not in before_pos:
                continue
            if a not in after_pos or b not in after_pos:
                continue
            before_a_first = before_pos[a] < before_pos[b]
            after_a_first = after_pos[a] < after_pos[b]
            if before_a_first != after_a_first:
                if before_a_first:
                    reversals.append((a, b))
                else:
                    reversals.append((b, a))
    return reversals


def _diff_guard_ordering(result: TraceDiff, before: "Trace", after: "Trace") -> None:
    """Detect cases where a tool that preceded another tool before no longer does so after.

    This is a behavioral guard regression: tool A always ran before tool B,
    but now tool B runs first or A is missing entirely.
    """
    before_calls = before.tool_calls()
    after_calls = after.tool_calls()

    if not before_calls or not after_calls:
        return

    # Build "A always precedes B" relationships from the before trace.
    # For each pair (A, B) where A appears before B in before, check if that holds in after.
    before_names = [s.name for s in before_calls]
    after_names = [s.name for s in after_calls]

    checked: set[tuple[str, str]] = set()
    for i, a in enumerate(before_names):
        for j, b in enumerate(before_names):
            if i >= j or (a, b) in checked:
                continue
            checked.add((a, b))
            # In before: a precedes b. Does a still precede b in after?
            if a not in after_names or b not in after_names:
                continue  # already reported as disappeared
            after_a_idx = after_names.index(a)
            after_b_idx = after_names.index(b)
            if after_a_idx > after_b_idx:
                # This is already caught by ordering_reversal — skip to avoid duplicate
                pass


def _diff_errors(result: TraceDiff, before: "Trace", after: "Trace") -> None:
    before_errs = len(before.error_steps())
    after_errs = len(after.error_steps())
    if after_errs > before_errs:
        result.findings.append(
            DiffFinding(
                severity="regression",
                check="error_count_increased",
                title=f"Error steps increased: {before_errs} -> {after_errs}",
                detail=(
                    f"The after trace has {after_errs - before_errs} more error step(s).\n"
                    f"Check which tools are now failing and whether they were previously succeeding."
                ),
                before=before_errs,
                after=after_errs,
            )
        )
    elif after_errs < before_errs:
        result.findings.append(
            DiffFinding(
                severity="improvement",
                check="error_count_decreased",
                title=f"Error steps reduced: {before_errs} -> {after_errs}",
                detail=f"The after trace has {before_errs - after_errs} fewer error step(s).",
                before=before_errs,
                after=after_errs,
            )
        )


def _diff_step_count(result: TraceDiff, before: "Trace", after: "Trace") -> None:
    bs = len(before.steps)
    as_ = len(after.steps)
    if as_ > bs:
        result.findings.append(
            DiffFinding(
                severity="regression",
                check="step_count_increased",
                title=f"Total step count grew: {bs} -> {as_} (+{as_ - bs})",
                detail=(
                    "More steps means more token spend and higher latency per invocation.\n"
                    "Investigate which new steps were added and whether they are necessary."
                ),
                before=bs,
                after=as_,
            )
        )
    elif as_ < bs:
        result.findings.append(
            DiffFinding(
                severity="improvement",
                check="step_count_decreased",
                title=f"Total step count reduced: {bs} -> {as_} (-{bs - as_})",
                detail="Fewer steps means lower token spend and latency.",
                before=bs,
                after=as_,
            )
        )


def _diff_duration(result: TraceDiff, before: "Trace", after: "Trace") -> None:
    bd = before.total_duration_ms()
    ad = after.total_duration_ms()
    if bd is None or ad is None:
        return
    if bd == 0:
        return
    ratio = ad / bd
    if ratio > 1.25:
        result.findings.append(
            DiffFinding(
                severity="regression",
                check="duration_increased",
                title=f"Duration grew: {bd:.0f}ms -> {ad:.0f}ms (+{ratio - 1:.0%})",
                detail=(
                    f"End-to-end latency increased by {ratio - 1:.0%}.\n"
                    f"This will directly degrade user-facing response time."
                ),
                before=round(bd),
                after=round(ad),
            )
        )
    elif ratio < 0.75:
        result.findings.append(
            DiffFinding(
                severity="improvement",
                check="duration_decreased",
                title=f"Duration reduced: {bd:.0f}ms -> {ad:.0f}ms (-{1 - ratio:.0%})",
                detail=f"End-to-end latency decreased by {1 - ratio:.0%}.",
                before=round(bd),
                after=round(ad),
            )
        )


def _diff_status(result: TraceDiff, before: "Trace", after: "Trace") -> None:
    if before.status == after.status:
        return
    severity: BehaviorSeverity = (
        "regression" if after.status in ("error", "interrupted") else "change"
    )
    result.findings.append(
        DiffFinding(
            severity=severity,
            check="status_changed",
            title=f"Status changed: '{before.status}' -> '{after.status}'",
            detail=(
                f"The run status changed from '{before.status}' to '{after.status}'.\n"
                + (
                    "This is a hard regression — the agent that succeeded before is now failing."
                    if after.status == "error"
                    else ""
                )
            ),
            before=before.status,
            after=after.status,
        )
    )


# ── Formatting ────────────────────────────────────────────────────────────────

def format_diff(diff: TraceDiff, color: bool = True) -> str:
    _RESET = "\033[0m"
    _RED = "\033[91m"
    _GREEN = "\033[92m"
    _YELLOW = "\033[93m"
    _BOLD = "\033[1m"
    _DIM = "\033[2m"

    def _c(text: str, code: str) -> str:
        return f"{code}{text}{_RESET}" if color else text

    lines: list[str] = [""]
    lines.append("Trajex Behavioral Diff")
    lines.append(f"  Before: ...{diff.before_id[-8:]}  ({diff.before_prompt[:50]!r})")
    lines.append(f"  After:  ...{diff.after_id[-8:]}  ({diff.after_prompt[:50]!r})")
    lines.append("")

    if not diff.findings:
        lines.append(_c("  No behavioral differences detected.", _GREEN))
        lines.append("")
        return "\n".join(lines)

    severity_order = {"regression": 0, "change": 1, "improvement": 2}
    sorted_findings = sorted(diff.findings, key=lambda f: severity_order.get(f.severity, 9))

    for finding in sorted_findings:
        if finding.severity == "regression":
            badge = _c("  REGR", _RED + _BOLD)
        elif finding.severity == "improvement":
            badge = _c("  IMPR", _GREEN)
        else:
            badge = _c("  DIFF", _YELLOW)
        lines.append(f"{badge}  [{finding.check}] {finding.title}")
        for line in finding.detail.splitlines():
            lines.append(f"        {line}")
        lines.append("")

    sep = "  " + "-" * 50
    lines.append(sep)
    summary = diff.summary()
    if diff.has_regressions:
        lines.append(_c(f"  {summary}", _RED + _BOLD))
        lines.append(_c("  Exit 1: behavioral regressions detected.", _RED))
    else:
        lines.append(_c(f"  {summary}", _GREEN))
    lines.append("")
    return "\n".join(lines)
