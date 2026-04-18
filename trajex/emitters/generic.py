from __future__ import annotations

import contextvars
import functools
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger("trajex")

# ContextVar propagates into child tasks created via asyncio.create_task() because
# Python copies the current context at task creation time. However, two *concurrent*
# tasks that share the same parent context both see the same trace object, so
# simultaneous tool calls from asyncio.gather() will interleave their steps.
#
# Safe patterns:
#   - Sequential async calls inside a single coroutine (await a(); await b()) — OK.
#   - asyncio.create_task() where only one task calls tools at a time — OK.
#
# Unsafe pattern:
#   - asyncio.gather(tool_a(), tool_b()) — both coroutines mutate trace.steps
#     concurrently; step indices will be wrong and ordering is undefined.
#
# Workaround for concurrent async tools: serialize tool calls with an asyncio.Lock,
# or use the per-coroutine pattern shown in the README.

_active_trace: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "_active_trace", default=None
)


def capture_trace(
    prompt: str | None = None,
    *,
    prompt_arg: str = "input",
) -> Callable:
    """Decorator that creates a Trace around a synchronous agent function.

    The trace is accessible after the call via `fn.last_trace`.
    For async functions use `capture_trace_async`.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from trajex.trace import Trace

            resolved_prompt = prompt
            if resolved_prompt is None:
                resolved_prompt = str(kwargs.get(prompt_arg, args[0] if args else ""))

            trace = Trace(
                prompt=resolved_prompt,
                started_at=datetime.now(timezone.utc),
                metadata={"framework": "unknown"},
            )
            token = _active_trace.set(trace)
            try:
                result = fn(*args, **kwargs)
                trace.final_output = str(result) if result is not None else None
                trace.status = "success"
                return result
            except Exception:
                trace.status = "error"
                raise
            finally:
                trace.ended_at = datetime.now(timezone.utc)
                _active_trace.reset(token)
                wrapper.last_trace = trace

        wrapper.last_trace = None
        return wrapper

    return decorator


def capture_trace_async(
    prompt: str | None = None,
    *,
    prompt_arg: str = "input",
) -> Callable:
    """Decorator that creates a Trace around an async agent coroutine.

    WARNING — concurrent tool calls:
        `asyncio.gather(tool_a(), tool_b())` is NOT safe inside a captured
        coroutine. Both awaitables share the same trace context and will race
        when appending steps. Use sequential `await` calls, or protect shared
        mutations with an `asyncio.Lock` passed into each tool.

    Safe usage::

        @capture_trace_async("delete user")
        async def run_agent(user_id: str) -> str:
            result = await fetch_user(user_id)   # sequential — safe
            await delete_record(user_id)          # sequential — safe
            return result

        asyncio.run(run_agent("123"))
        trace = run_agent.last_trace
    """
    def decorator(fn: Callable[..., Coroutine]) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            from trajex.trace import Trace

            resolved_prompt = prompt
            if resolved_prompt is None:
                resolved_prompt = str(kwargs.get(prompt_arg, args[0] if args else ""))

            trace = Trace(
                prompt=resolved_prompt,
                started_at=datetime.now(timezone.utc),
                metadata={"framework": "unknown"},
            )
            token = _active_trace.set(trace)
            try:
                result = await fn(*args, **kwargs)
                trace.final_output = str(result) if result is not None else None
                trace.status = "success"
                return result
            except Exception:
                trace.status = "error"
                raise
            finally:
                trace.ended_at = datetime.now(timezone.utc)
                _active_trace.reset(token)
                wrapper.last_trace = trace

        wrapper.last_trace = None
        return wrapper

    return decorator


def record_tool_call(fn: Callable) -> Callable:
    """Decorator that records a synchronous tool call into the active trace.

    No-ops if there is no active trace (i.e. called outside `capture_trace`).
    For async tools use `record_tool_call_async`.
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        trace = _active_trace.get()
        if trace is None:
            return fn(*args, **kwargs)

        from trajex.trace import Step, StepType

        started_at = datetime.now(timezone.utc)
        index = len(trace.steps)
        tool_input = args[0] if len(args) == 1 else (dict(kwargs) if kwargs else list(args))

        try:
            result = fn(*args, **kwargs)
            ended_at = datetime.now(timezone.utc)
            trace.steps.append(
                Step(
                    index=index,
                    step_type=StepType.TOOL_CALL,
                    name=fn.__name__,
                    input=tool_input,
                    output=str(result) if result is not None else None,
                    started_at=started_at,
                    ended_at=ended_at,
                )
            )
            return result
        except Exception as exc:
            ended_at = datetime.now(timezone.utc)
            trace.steps.append(
                Step(
                    index=index,
                    step_type=StepType.TOOL_CALL,
                    name=fn.__name__,
                    input=tool_input,
                    error=str(exc),
                    started_at=started_at,
                    ended_at=ended_at,
                )
            )
            raise

    return wrapper


def record_tool_call_async(fn: Callable[..., Coroutine]) -> Callable:
    """Decorator that records an async tool call into the active trace.

    WARNING — concurrent calls: if two `@record_tool_call_async` tools are
    awaited concurrently (e.g. via `asyncio.gather`), step indices will be
    assigned by whichever coroutine reaches `len(trace.steps)` first, and the
    interleaved ordering in `trace.steps` will be non-deterministic.

    Use sequential `await` calls inside `@capture_trace_async` functions, or
    pass an `asyncio.Lock` explicitly and acquire it before mutating the trace.
    """
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        trace = _active_trace.get()
        if trace is None:
            return await fn(*args, **kwargs)

        from trajex.trace import Step, StepType

        started_at = datetime.now(timezone.utc)
        index = len(trace.steps)
        tool_input = args[0] if len(args) == 1 else (dict(kwargs) if kwargs else list(args))

        try:
            result = await fn(*args, **kwargs)
            ended_at = datetime.now(timezone.utc)
            trace.steps.append(
                Step(
                    index=index,
                    step_type=StepType.TOOL_CALL,
                    name=fn.__name__,
                    input=tool_input,
                    output=str(result) if result is not None else None,
                    started_at=started_at,
                    ended_at=ended_at,
                )
            )
            return result
        except Exception as exc:
            ended_at = datetime.now(timezone.utc)
            trace.steps.append(
                Step(
                    index=index,
                    step_type=StepType.TOOL_CALL,
                    name=fn.__name__,
                    input=tool_input,
                    error=str(exc),
                    started_at=started_at,
                    ended_at=ended_at,
                )
            )
            raise

    return wrapper
