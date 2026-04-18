from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger("trajex")


class StepType(str, Enum):
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    LLM_CALL = "llm_call"
    LLM_RESPONSE = "llm_response"
    AGENT_ACTION = "agent_action"
    AGENT_FINISH = "agent_finish"
    HANDOFF = "handoff"
    ERROR = "error"


@dataclass
class Step:
    index: int
    step_type: StepType
    name: str
    input: Any = None
    output: Any = None
    error: str | None = None
    reasoning: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: float | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.started_at and self.ended_at and self.duration_ms is None:
            delta = self.ended_at - self.started_at
            self.duration_ms = delta.total_seconds() * 1000

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Step):
            return NotImplemented
        return (
            self.index == other.index
            and self.step_type == other.step_type
            and self.name == other.name
            and self.input == other.input
            and self.output == other.output
            and self.error == other.error
            and self.reasoning == other.reasoning
            and self.metadata == other.metadata
        )

    def __repr__(self) -> str:
        return (
            f"Step(index={self.index}, step_type={self.step_type.value!r}, "
            f"name={self.name!r}, input={self.input!r})"
        )

    @property
    def succeeded(self) -> bool:
        return self.error is None

    @property
    def failed(self) -> bool:
        return self.error is not None


@dataclass
class Trace:
    prompt: str
    id: str = field(default_factory=lambda: str(uuid4()))
    trajex_version: str = "1"
    steps: list[Step] = field(default_factory=list)
    final_output: str | None = None
    status: str = "success"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Trace):
            return NotImplemented
        return (
            self.id == other.id
            and self.prompt == other.prompt
            and self.trajex_version == other.trajex_version
            and self.steps == other.steps
            and self.final_output == other.final_output
            and self.status == other.status
            and self.metadata == other.metadata
        )

    def tool_calls(self) -> list[Step]:
        """ONLY tool_call steps. This is what assertions operate on."""
        return [s for s in self.steps if s.step_type == StepType.TOOL_CALL]

    def tool_names(self) -> list[str]:
        return [s.name for s in self.tool_calls()]

    def llm_steps(self) -> list[Step]:
        return [s for s in self.steps if s.step_type in (StepType.LLM_CALL, StepType.LLM_RESPONSE)]

    def error_steps(self) -> list[Step]:
        return [s for s in self.steps if s.step_type == StepType.ERROR or s.error is not None]

    def reasoning_text(self) -> list[str]:
        return [s.reasoning for s in self.steps if s.reasoning is not None]

    def total_duration_ms(self) -> float | None:
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds() * 1000
        return None

    def total_tool_calls(self) -> int:
        return len(self.tool_calls())

    def unique_tools_called(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for name in self.tool_names():
            if name not in seen:
                seen.add(name)
                result.append(name)
        return result

    def tool_call_counts(self) -> dict[str, int]:
        """Returns {tool_name: call_count} for all tool_call steps."""
        counts: dict[str, int] = {}
        for name in self.tool_names():
            counts[name] = counts.get(name, 0) + 1
        return counts

    def steps_by_type(self, step_type: StepType) -> list[Step]:
        return [s for s in self.steps if s.step_type == step_type]

    def get_step(self, index: int) -> Step | None:
        for step in self.steps:
            if step.index == index:
                return step
        return None

    def token_estimate(self) -> int | None:
        """Sum of token counts from metadata['token_usage'] across LLM steps, if present."""
        total = 0
        found = False
        for step in self.llm_steps():
            usage = step.metadata.get("token_usage") or step.metadata.get("usage")
            if usage and isinstance(usage, dict):
                total += usage.get("total_tokens", 0)
                found = True
        return total if found else None

    def to_dict(self) -> dict:
        return {
            "trajex_version": self.trajex_version,
            "id": self.id,
            "prompt": self.prompt,
            "final_output": self.final_output,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "metadata": self.metadata,
            "steps": [
                {
                    "index": s.index,
                    "step_type": s.step_type.value,
                    "name": s.name,
                    "input": s.input,
                    "output": s.output,
                    "error": s.error,
                    "reasoning": s.reasoning,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                    "duration_ms": s.duration_ms,
                    "metadata": s.metadata,
                }
                for s in self.steps
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    def summary(self) -> str:
        dur = self.total_duration_ms()
        dur_str = f"{dur:.0f}ms" if dur is not None else "unknown"
        tools = ", ".join(self.unique_tools_called()) or "(none)"
        errors = len(self.error_steps())
        return (
            f"[{self.status}] {len(self.steps)} steps, "
            f"{self.total_tool_calls()} tool calls, "
            f"{errors} errors, {dur_str} — tools: {tools}"
        )

    @classmethod
    def from_dict(cls, data: dict) -> "Trace":
        if not isinstance(data, dict):
            raise ValueError("Invalid Trajex trace: expected a dict")
        if "prompt" not in data:
            raise ValueError("Invalid Trajex trace: missing required field 'prompt'")

        def parse_dt(v: Any) -> datetime | None:
            if v is None:
                return None
            if isinstance(v, datetime):
                return v
            return datetime.fromisoformat(v)

        steps: list[Step] = []
        for i, s in enumerate(data.get("steps") or []):
            step_type_raw = s.get("step_type", "tool_call")
            try:
                step_type = StepType(step_type_raw)
            except ValueError:
                step_type = StepType.TOOL_CALL

            steps.append(
                Step(
                    index=s.get("index", i),
                    step_type=step_type,
                    name=s.get("name", "unknown"),
                    input=s.get("input"),
                    output=s.get("output"),
                    error=s.get("error"),
                    reasoning=s.get("reasoning"),
                    started_at=parse_dt(s.get("started_at")),
                    ended_at=parse_dt(s.get("ended_at")),
                    duration_ms=s.get("duration_ms"),
                    metadata=s.get("metadata") or {},
                )
            )

        return cls(
            trajex_version=data.get("trajex_version", "1"),
            id=data.get("id") or str(uuid4()),
            prompt=data["prompt"],
            steps=steps,
            final_output=data.get("final_output"),
            status=data.get("status", "success"),
            started_at=parse_dt(data.get("started_at")),
            ended_at=parse_dt(data.get("ended_at")),
            metadata=data.get("metadata") or {},
        )

    @classmethod
    def from_json(cls, path: str) -> "Trace":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_json_string(cls, s: str) -> "Trace":
        return cls.from_dict(json.loads(s))
