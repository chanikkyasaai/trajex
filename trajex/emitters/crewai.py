from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("trajex")

try:
    import crewai  # noqa: F401
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def _require() -> None:
    if not _AVAILABLE:
        raise ImportError(
            "Install the crewai emitter with: pip install trajex[crewai]"
        )


def trace_from_crew_output(prompt: str, crew_output: Any) -> Any:
    _require()
    from trajex.trace import Step, StepType, Trace

    steps: list[Step] = []
    tasks_output = getattr(crew_output, "tasks_output", []) or []

    for i, task_output in enumerate(tasks_output):
        agent_name = getattr(task_output, "agent", "unknown_agent")
        raw_output = getattr(task_output, "raw", None) or getattr(task_output, "output", None)
        steps.append(
            Step(
                index=i,
                step_type=StepType.AGENT_ACTION,
                name=f"{agent_name}_task",
                output=str(raw_output) if raw_output is not None else None,
                # TrajexCrewCallbackHandler needed for tool-level granularity (future work)
            )
        )

    final_output = str(getattr(crew_output, "raw", None) or "")

    return Trace(
        prompt=prompt,
        steps=steps,
        final_output=final_output or None,
        status="success",
        metadata={"framework": "crewai"},
    )
