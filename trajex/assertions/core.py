from __future__ import annotations

from typing import TYPE_CHECKING

from trajex.result import AssertionResult, TrajectoryAssertion

if TYPE_CHECKING:
    from trajex.trace import Trace


class SequenceAssertion(TrajectoryAssertion):
    def __init__(self, *tools: str) -> None:
        if len(tools) < 2:
            raise ValueError("sequence() requires at least 2 tool names")
        self.tools = list(tools)
        self.name = f"sequence({', '.join(repr(t) for t in tools)})"

    def check(self, trace: "Trace") -> AssertionResult:
        tool_names = trace.tool_names()
        pointer = 0
        first_missing_index = None

        for i, tool in enumerate(self.tools):
            found = False
            for j in range(pointer, len(tool_names)):
                if tool_names[j] == tool:
                    pointer = j + 1
                    found = True
                    break
            if not found:
                first_missing_index = i
                break

        if first_missing_index is not None:
            missing = " -> ".join(self.tools[first_missing_index:])
            actual = " -> ".join(tool_names) if tool_names else "(none)"
            return AssertionResult(
                passed=False,
                name=self.name,
                message=f"Expected sequence not found in trace",
                detail=(
                    f"Expected sequence: {' -> '.join(self.tools)}\n"
                    f"Actual tools:      {actual}\n"
                    f"Missing:           {missing}"
                ),
                suggestion=f"sequence({', '.join(repr(t) for t in self.tools)})",
            )

        return AssertionResult(
            passed=True,
            name=self.name,
            message=f"Sequence matched: {' -> '.join(self.tools)}",
        )


class NeverBeforeAssertion(TrajectoryAssertion):
    def __init__(self, tool_a: str, tool_b: str) -> None:
        self.tool_a = tool_a
        self.tool_b = tool_b
        self.name = f"never_before({tool_a!r}, {tool_b!r})"

    def check(self, trace: "Trace") -> AssertionResult:
        tool_calls = trace.tool_calls()
        a_steps = [s for s in tool_calls if s.name == self.tool_a]
        b_steps = [s for s in tool_calls if s.name == self.tool_b]

        if not a_steps:
            return AssertionResult(
                passed=True,
                name=self.name,
                message=f"'{self.tool_a}' was never called — constraint not violated",
            )

        if not b_steps:
            a_idx = a_steps[0].index
            return AssertionResult(
                passed=False,
                name=self.name,
                message=f"'{self.tool_a}' was called but '{self.tool_b}' was never called",
                detail=(
                    f"'{self.tool_a}' was called (step {a_idx}) but '{self.tool_b}' was never called at all.\n"
                    f"This is a silent bypass -- the agent assumed permission it was never granted."
                ),
                step_index=a_idx,
            )

        a_idx = a_steps[0].index
        b_idx = b_steps[0].index

        if a_idx < b_idx:
            return AssertionResult(
                passed=False,
                name=self.name,
                message=f"'{self.tool_a}' ran at step {a_idx} BEFORE '{self.tool_b}' at step {b_idx}",
                detail=(
                    f"'{self.tool_a}' ran at step {a_idx} BEFORE '{self.tool_b}' at step {b_idx}.\n"
                    f"Required: '{self.tool_b}' must happen first.\n"
                    f"Impact: This reversal silently bypasses the intended guard."
                ),
                step_index=a_idx,
            )

        return AssertionResult(
            passed=True,
            name=self.name,
            message=f"'{self.tool_b}' (step {b_idx}) preceded '{self.tool_a}' (step {a_idx}) — OK",
        )


class NoLoopAssertion(TrajectoryAssertion):
    def __init__(self, tool: str, max_calls: int = 1) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be >= 1")
        self.tool = tool
        self.max_calls = max_calls
        self.name = f"no_loop({tool!r}, max_calls={max_calls})"

    def check(self, trace: "Trace") -> AssertionResult:
        matching = [s for s in trace.tool_calls() if s.name == self.tool]
        count = len(matching)

        if count > self.max_calls:
            indices = [s.index for s in matching]
            excess = count - self.max_calls
            return AssertionResult(
                passed=False,
                name=self.name,
                message=f"'{self.tool}' called {count} times -- limit is {self.max_calls}",
                detail=(
                    f"'{self.tool}' called {count} times -- limit is {self.max_calls} "
                    f"({excess} excess call(s)).\n"
                    f"Called at steps: {indices}"
                ),
                step_index=indices[0] if indices else None,
            )

        return AssertionResult(
            passed=True,
            name=self.name,
            message=f"'{self.tool}' called {count} time(s) -- within limit of {self.max_calls}",
        )


class MaxStepsAssertion(TrajectoryAssertion):
    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        self.limit = limit
        self.name = f"max_steps({limit})"

    def check(self, trace: "Trace") -> AssertionResult:
        actual = len(trace.steps)
        if actual > self.limit:
            return AssertionResult(
                passed=False,
                name=self.name,
                message=f"Agent took {actual} steps -- limit is {self.limit} ({actual - self.limit} over budget)",
                detail=(
                    f"Agent took {actual} steps -- limit is {self.limit} ({actual - self.limit} over budget).\n"
                    f"Excess steps waste tokens and add latency. At {actual} steps, each run costs\n"
                    f"approximately {actual / self.limit:.1f}x more than expected."
                ),
            )

        return AssertionResult(
            passed=True,
            name=self.name,
            message=f"Agent took {actual} steps -- within limit of {self.limit}",
        )


class ToolCalledAssertion(TrajectoryAssertion):
    def __init__(self, tool: str, expected: bool) -> None:
        self.tool = tool
        self.expected = expected
        self.name = ("tool_called" if expected else "tool_never_called") + f"({tool!r})"

    def check(self, trace: "Trace") -> AssertionResult:
        matching = [s for s in trace.tool_calls() if s.name == self.tool]
        called = len(matching) > 0

        if self.expected and not called:
            actual_names = trace.tool_names() or ["(none)"]
            return AssertionResult(
                passed=False,
                name=self.name,
                message=f"Expected '{self.tool}' to be called -- it was never invoked",
                detail=(
                    f"Expected '{self.tool}' to be called -- it was never invoked.\n"
                    f"Tools actually called: {actual_names}\n"
                    f"This tool was skipped entirely."
                ),
            )

        if not self.expected and called:
            indices = [s.index for s in matching]
            return AssertionResult(
                passed=False,
                name=self.name,
                message=f"'{self.tool}' was called but must NEVER be called in this context",
                detail=(
                    f"'{self.tool}' was called but must NEVER be called in this context.\n"
                    f"Called at steps: {indices}"
                ),
                step_index=indices[0],
            )

        return AssertionResult(
            passed=True,
            name=self.name,
            message=(
                f"'{self.tool}' was called as expected"
                if self.expected
                else f"'{self.tool}' was correctly not called"
            ),
        )


def sequence(*tools: str) -> SequenceAssertion:
    return SequenceAssertion(*tools)


def never_before(tool_a: str, tool_b: str) -> NeverBeforeAssertion:
    return NeverBeforeAssertion(tool_a, tool_b)


def no_loop(tool: str, max_calls: int = 1) -> NoLoopAssertion:
    return NoLoopAssertion(tool, max_calls)


def max_steps(limit: int) -> MaxStepsAssertion:
    return MaxStepsAssertion(limit)


def tool_called(tool: str) -> ToolCalledAssertion:
    return ToolCalledAssertion(tool, expected=True)


def tool_never_called(tool: str) -> ToolCalledAssertion:
    return ToolCalledAssertion(tool, expected=False)
