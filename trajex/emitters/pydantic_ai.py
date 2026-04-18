from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("trajex")

try:
    import pydantic_ai  # noqa: F401
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def _require() -> None:
    if not _AVAILABLE:
        raise ImportError(
            "Install the pydantic-ai emitter with: pip install trajex[pydantic-ai]"
        )


def trace_from_pydantic_run(prompt: str, result: Any) -> Any:
    _require()
    from trajex.trace import Step, StepType, Trace

    steps: list[Step] = []
    counter = 0
    tool_call_id_map: dict[str, int] = {}

    messages = result.all_messages() if hasattr(result, "all_messages") else []

    for msg in messages:
        parts = getattr(msg, "parts", []) or []
        for part in parts:
            part_type = type(part).__name__
            if part_type == "ToolCallPart":
                tc_id = str(getattr(part, "tool_call_id", "") or "")
                name = getattr(part, "tool_name", "unknown_tool")
                args = getattr(part, "args", None)
                step = Step(
                    index=counter,
                    step_type=StepType.TOOL_CALL,
                    name=str(name),
                    input=args,
                )
                if tc_id:
                    tool_call_id_map[tc_id] = counter
                steps.append(step)
                counter += 1

            elif part_type == "ToolReturnPart":
                tc_id = str(getattr(part, "tool_call_id", "") or "")
                content = getattr(part, "content", None)
                if tc_id in tool_call_id_map:
                    steps[tool_call_id_map[tc_id]].output = content

            elif part_type == "TextPart":
                content = getattr(part, "content", "")
                if content:
                    steps.append(
                        Step(
                            index=counter,
                            step_type=StepType.LLM_RESPONSE,
                            name="llm_response",
                            output=str(content),
                        )
                    )
                    counter += 1

    final_output = None
    if hasattr(result, "data"):
        final_output = str(result.data)
    else:
        for step in reversed(steps):
            if step.step_type == StepType.LLM_RESPONSE and step.output:
                final_output = str(step.output)
                break

    return Trace(
        prompt=prompt,
        steps=steps,
        final_output=final_output,
        status="success",
        metadata={"framework": "pydantic_ai"},
    )
