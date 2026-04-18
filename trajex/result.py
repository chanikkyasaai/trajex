from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trajex.trace import Trace


@dataclass
class AssertionResult:
    passed: bool
    name: str
    message: str
    detail: str = ""
    step_index: int | None = None
    suggestion: str = ""

    @property
    def failed(self) -> bool:
        return not self.passed

    def __bool__(self) -> bool:
        return self.passed


class TrajectoryAssertion:
    """Base class. Subclass and implement check()."""

    name: str = "unnamed"

    def check(self, trace: "Trace") -> AssertionResult:
        raise NotImplementedError


@dataclass
class TrajectoryReport:
    trace_prompt: str
    trace_id: str
    results: list[AssertionResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failed(self) -> bool:
        return not self.passed

    @property
    def failures(self) -> list[AssertionResult]:
        return [r for r in self.results if r.failed]

    def summary(self) -> str:
        total = len(self.results)
        fails = len(self.failures)
        return f"{total - fails}/{total} assertions passed, {fails} failed"
