from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("trajex")

try:
    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.outputs import LLMResult
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def _require() -> None:
    if not _AVAILABLE:
        raise ImportError(
            "Install the langchain emitter with: pip install trajex[langchain]"
        )


if _AVAILABLE:
    class TrajexCallbackHandler(BaseCallbackHandler):
        """LangChain callback handler that records an agent run as a Trajex Trace.

        Usage:
            handler = TrajexCallbackHandler(prompt="Delete user 42")
            agent.invoke({"input": "Delete user 42"}, callbacks=[handler])
            trace = handler.build_trace()
        """

        def __init__(self, prompt: str = "") -> None:
            super().__init__()
            from trajex.trace import Step
            self._prompt = prompt
            self._steps: list[Step] = []
            self._counter: int = 0
            # run_id (str) -> pending step data dict
            self._pending: dict[str, dict] = {}
            # LIFO fallback for older LangChain without run_id
            self._pending_queue: deque[dict] = deque()
            self._final_output: str | None = None
            self._started_at: datetime = datetime.now(timezone.utc)

        def _next_index(self) -> int:
            idx = self._counter
            self._counter += 1
            return idx

        def _pop_pending(self, run_id: Any) -> dict | None:
            if run_id is not None:
                return self._pending.pop(str(run_id), None)
            return self._pending_queue.pop() if self._pending_queue else None

        def on_tool_start(
            self,
            serialized: dict,
            input_str: str,
            *,
            run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            data = {
                "name": serialized.get("name", "unknown_tool"),
                "input": input_str,
                "started_at": datetime.now(timezone.utc),
            }
            if run_id is not None:
                self._pending[str(run_id)] = data
            else:
                self._pending_queue.append(data)

        def on_tool_end(
            self,
            output: str,
            *,
            run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            from trajex.trace import Step, StepType
            ended_at = datetime.now(timezone.utc)
            data = self._pop_pending(run_id)
            if data is None:
                return
            self._steps.append(
                Step(
                    index=self._next_index(),
                    step_type=StepType.TOOL_CALL,
                    name=data["name"],
                    input=data.get("input"),
                    output=str(output),
                    started_at=data.get("started_at"),
                    ended_at=ended_at,
                )
            )

        def on_tool_error(
            self,
            error: BaseException,
            *,
            run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            from trajex.trace import Step, StepType
            ended_at = datetime.now(timezone.utc)
            data = self._pop_pending(run_id)
            name = data["name"] if data else "unknown_tool"
            self._steps.append(
                Step(
                    index=self._next_index(),
                    step_type=StepType.ERROR,
                    name=name,
                    input=data.get("input") if data else None,
                    error=str(error),
                    started_at=data.get("started_at") if data else None,
                    ended_at=ended_at,
                )
            )

        def on_llm_start(
            self,
            serialized: dict,
            prompts: list,
            *,
            run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            from trajex.trace import Step, StepType
            model_name = (
                serialized.get("kwargs", {}).get("model_name")
                or serialized.get("name", "unknown_model")
            )
            self._steps.append(
                Step(
                    index=self._next_index(),
                    step_type=StepType.LLM_CALL,
                    name=str(model_name),
                    input=prompts[0] if prompts else None,
                    started_at=datetime.now(timezone.utc),
                )
            )

        def on_llm_end(
            self,
            response: "LLMResult",
            *,
            run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            from trajex.trace import Step, StepType
            text = ""
            try:
                text = response.generations[0][0].text
            except (AttributeError, IndexError):
                pass
            self._steps.append(
                Step(
                    index=self._next_index(),
                    step_type=StepType.LLM_RESPONSE,
                    name="llm_response",
                    output=text,
                    ended_at=datetime.now(timezone.utc),
                )
            )

        def on_agent_action(self, action: Any, *, run_id: Any = None, **kwargs: Any) -> None:
            from trajex.trace import StepType
            # Deduplicate: LCEL agents emit on_agent_action AND on_tool_start for the same tool.
            # If the last 2 steps already contain a TOOL_CALL with the same name and input, skip.
            tool_name = getattr(action, "tool", "unknown")
            tool_input = getattr(action, "tool_input", None)
            recent = self._steps[-2:] if len(self._steps) >= 2 else self._steps
            for step in recent:
                if step.step_type == StepType.TOOL_CALL and step.name == tool_name:
                    return  # already recorded by on_tool_start/end

            from trajex.trace import Step
            reasoning = getattr(action, "log", None)
            self._steps.append(
                Step(
                    index=self._next_index(),
                    step_type=StepType.AGENT_ACTION,
                    name=str(tool_name),
                    input=tool_input,
                    reasoning=reasoning,
                    started_at=datetime.now(timezone.utc),
                )
            )

        def on_agent_finish(self, finish: Any, *, run_id: Any = None, **kwargs: Any) -> None:
            from trajex.trace import Step, StepType
            try:
                output = finish.return_values.get("output", "")
            except AttributeError:
                output = str(finish)
            self._final_output = str(output)
            self._steps.append(
                Step(
                    index=self._next_index(),
                    step_type=StepType.AGENT_FINISH,
                    name="agent_finish",
                    output=self._final_output,
                    ended_at=datetime.now(timezone.utc),
                )
            )

        def build_trace(self) -> Any:
            from trajex.trace import Trace
            return Trace(
                prompt=self._prompt,
                steps=self._steps,
                final_output=self._final_output,
                started_at=self._started_at,
                ended_at=datetime.now(timezone.utc),
                metadata={"framework": "langchain"},
            )

else:
    class TrajexCallbackHandler:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _require()


def trace_from_intermediate_steps(
    prompt: str,
    steps: list[tuple[Any, Any]],
    output: str = "",
    framework: str = "langchain",
) -> Any:
    _require()
    from trajex.trace import Step, StepType, Trace

    trace_steps: list[Step] = []
    for i, (action, observation) in enumerate(steps):
        reasoning = getattr(action, "log", None)
        tool_name = str(getattr(action, "tool", "unknown_tool"))
        tool_input = getattr(action, "tool_input", None)
        trace_steps.append(
            Step(
                index=i,
                step_type=StepType.TOOL_CALL,
                name=tool_name,
                input=tool_input,
                output=str(observation) if observation is not None else None,
                reasoning=reasoning,
            )
        )

    return Trace(
        prompt=prompt,
        steps=trace_steps,
        final_output=output or None,
        status="success",
        metadata={"framework": framework},
    )


def trace_from_langgraph_result(
    prompt: str,
    result: dict,
    messages_key: str = "messages",
) -> Any:
    _require()
    from trajex.trace import Step, StepType, Trace

    messages = result.get(messages_key) or []
    trace_steps: list[Step] = []
    tool_call_map: dict[str, int] = {}
    counter = 0

    for msg in messages:
        msg_type = type(msg).__name__

        # AIMessage with tool_calls attribute
        tool_calls_attr = getattr(msg, "tool_calls", None)
        if tool_calls_attr:
            for tc in tool_calls_attr:
                name = (tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "unknown")) or "unknown"
                tc_input = (tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", None))
                tc_id = str((tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "")) or "")
                step = Step(
                    index=counter,
                    step_type=StepType.TOOL_CALL,
                    name=str(name),
                    input=tc_input,
                )
                if tc_id:
                    tool_call_map[tc_id] = counter
                trace_steps.append(step)
                counter += 1
        elif msg_type == "ToolMessage":
            tc_id = str(getattr(msg, "tool_call_id", "") or "")
            content = getattr(msg, "content", None)
            if tc_id in tool_call_map:
                trace_steps[tool_call_map[tc_id]].output = content
        elif msg_type in ("AIMessage",) and not tool_calls_attr:
            content = getattr(msg, "content", "")
            if content:
                trace_steps.append(
                    Step(
                        index=counter,
                        step_type=StepType.LLM_RESPONSE,
                        name="llm_response",
                        output=str(content),
                    )
                )
                counter += 1

    final_output = None
    for step in reversed(trace_steps):
        if step.step_type == StepType.LLM_RESPONSE and step.output:
            final_output = str(step.output)
            break

    return Trace(
        prompt=prompt,
        steps=trace_steps,
        final_output=final_output,
        status="success",
        metadata={"framework": "langchain"},
    )
