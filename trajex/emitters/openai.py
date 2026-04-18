from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("trajex")

try:
    import openai  # noqa: F401
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def _require() -> None:
    if not _AVAILABLE:
        raise ImportError(
            "Install the openai emitter with: pip install trajex[openai]"
        )


def trace_from_openai_run(prompt: str, result: Any) -> Any:
    _require()
    from trajex.trace import Step, StepType, Trace

    steps: list[Step] = []
    counter = 0

    items = getattr(result, "new_items", []) or []
    for item in items:
        item_type = getattr(item, "type", "")
        raw = getattr(item, "raw_item", None)

        if item_type == "tool_call_item":
            name = "unknown_tool"
            tool_input = None
            if raw is not None:
                name = getattr(raw, "name", None) or (
                    getattr(getattr(raw, "function", None), "name", None) or "unknown_tool"
                )
                tool_input = getattr(raw, "arguments", None) or getattr(
                    getattr(raw, "function", None), "arguments", None
                )
            step = Step(
                index=counter,
                step_type=StepType.TOOL_CALL,
                name=str(name),
                input=tool_input,
            )
            steps.append(step)
            counter += 1

        elif item_type == "tool_call_output_item":
            output = getattr(item, "output", None)
            # Attach to last TOOL_CALL without output
            for step in reversed(steps):
                if step.step_type == StepType.TOOL_CALL and step.output is None:
                    step.output = output
                    break

        elif item_type == "message_output_item":
            content = ""
            msg = getattr(item, "raw_item", None)
            if msg is not None:
                content = getattr(msg, "content", "") or ""
                if isinstance(content, list):
                    parts = [getattr(p, "text", "") for p in content if hasattr(p, "text")]
                    content = " ".join(parts)
            steps.append(
                Step(
                    index=counter,
                    step_type=StepType.LLM_RESPONSE,
                    name="llm_response",
                    output=str(content),
                )
            )
            counter += 1

    final_output = getattr(result, "final_output", None)
    if final_output is None:
        for step in reversed(steps):
            if step.step_type == StepType.LLM_RESPONSE and step.output:
                final_output = str(step.output)
                break

    return Trace(
        prompt=prompt,
        steps=steps,
        final_output=str(final_output) if final_output is not None else None,
        status="success",
        metadata={"framework": "openai_agents"},
    )


def trace_from_openai_messages(
    prompt: str,
    messages: list[dict],
    final_output: str = "",
) -> Any:
    _require()
    from trajex.trace import Step, StepType, Trace

    steps: list[Step] = []
    counter = 0
    tool_call_id_map: dict[str, int] = {}

    for msg in messages:
        role = msg.get("role", "")
        if role == "assistant":
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    tc_id = tc.get("id", "")
                    fn = tc.get("function", {})
                    name = fn.get("name", "unknown_tool")
                    arguments = fn.get("arguments", None)
                    step = Step(
                        index=counter,
                        step_type=StepType.TOOL_CALL,
                        name=str(name),
                        input=arguments,
                    )
                    if tc_id:
                        tool_call_id_map[tc_id] = counter
                    steps.append(step)
                    counter += 1
            else:
                content = msg.get("content", "")
                if content:
                    steps.append(
                        Step(
                            index=counter,
                            step_type=StepType.LLM_RESPONSE,
                            name="llm_response",
                            output=content,
                        )
                    )
                    counter += 1

        elif role == "tool":
            tc_id = msg.get("tool_call_id", "")
            content = msg.get("content", "")
            if tc_id in tool_call_id_map:
                steps[tool_call_id_map[tc_id]].output = content

    return Trace(
        prompt=prompt,
        steps=steps,
        final_output=final_output or None,
        status="success",
        metadata={"framework": "openai_agents"},
    )
