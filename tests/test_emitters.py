from __future__ import annotations

import pytest

from trajex.trace import StepType, Trace


def test_generic_capture_trace():
    from trajex.emitters.generic import capture_trace, record_tool_call

    @record_tool_call
    def my_tool(x: str) -> str:
        return f"result:{x}"

    @capture_trace(prompt="run the test")
    def run_agent(input: str) -> str:
        my_tool(input)
        return "done"

    run_agent("hello")
    trace = run_agent.last_trace
    assert isinstance(trace, Trace)
    assert trace.prompt == "run the test"
    assert len(trace.tool_calls()) == 1
    assert trace.tool_calls()[0].name == "my_tool"
    assert trace.tool_calls()[0].input == "hello"
    assert trace.tool_calls()[0].output == "result:hello"


def test_generic_capture_trace_no_context():
    from trajex.emitters.generic import record_tool_call

    @record_tool_call
    def standalone_tool(x: str) -> str:
        return "ok"

    # No active trace context — should be a no-op
    result = standalone_tool("test")
    assert result == "ok"


def test_generic_capture_multiple_tools():
    from trajex.emitters.generic import capture_trace, record_tool_call

    @record_tool_call
    def tool_a(x: str) -> str:
        return "a"

    @record_tool_call
    def tool_b(x: str) -> str:
        return "b"

    @capture_trace(prompt="multi tool test")
    def agent(input: str) -> str:
        tool_a(input)
        tool_b(input)
        return "done"

    agent("x")
    trace = agent.last_trace
    assert trace.tool_names() == ["tool_a", "tool_b"]


def test_generic_capture_trace_error_status():
    from trajex.emitters.generic import capture_trace, record_tool_call

    @record_tool_call
    def bad_tool(x: str) -> str:
        raise ValueError("boom")

    @capture_trace(prompt="error test")
    def run_agent(input: str) -> str:
        bad_tool(input)
        return "done"

    with pytest.raises(ValueError):
        run_agent("x")
    trace = run_agent.last_trace
    assert trace.status == "error"
    assert trace.tool_calls()[0].error == "boom"


def test_generic_capture_trace_async():
    import asyncio
    from trajex.emitters.generic import capture_trace_async, record_tool_call_async

    @record_tool_call_async
    async def async_tool(x: str) -> str:
        return f"async:{x}"

    @capture_trace_async(prompt="async test")
    async def run_agent(input: str) -> str:
        await async_tool(input)
        return "done"

    asyncio.run(run_agent("hello"))
    trace = run_agent.last_trace
    assert isinstance(trace, Trace)
    assert trace.prompt == "async test"
    assert len(trace.tool_calls()) == 1
    assert trace.tool_calls()[0].name == "async_tool"
    assert trace.tool_calls()[0].output == "async:hello"
    assert trace.status == "success"


def test_generic_async_sequential_tools_ordered():
    import asyncio
    from trajex.emitters.generic import capture_trace_async, record_tool_call_async

    @record_tool_call_async
    async def step_one(x: str) -> str:
        return "one"

    @record_tool_call_async
    async def step_two(x: str) -> str:
        return "two"

    @capture_trace_async(prompt="sequential")
    async def run_agent(input: str) -> str:
        await step_one(input)
        await step_two(input)
        return "done"

    asyncio.run(run_agent("x"))
    trace = run_agent.last_trace
    assert trace.tool_names() == ["step_one", "step_two"]
    assert trace.tool_calls()[0].index == 0
    assert trace.tool_calls()[1].index == 1


def test_generic_async_no_context_noop():
    import asyncio
    from trajex.emitters.generic import record_tool_call_async

    @record_tool_call_async
    async def standalone(x: str) -> str:
        return "ok"

    result = asyncio.run(standalone("test"))
    assert result == "ok"


def test_generic_async_error_status():
    import asyncio
    from trajex.emitters.generic import capture_trace_async, record_tool_call_async

    @record_tool_call_async
    async def failing_tool(x: str) -> str:
        raise RuntimeError("async fail")

    @capture_trace_async(prompt="async error")
    async def run_agent(input: str) -> str:
        await failing_tool(input)
        return "done"

    with pytest.raises(RuntimeError):
        asyncio.run(run_agent("x"))
    trace = run_agent.last_trace
    assert trace.status == "error"
    assert trace.tool_calls()[0].error == "async fail"


def test_langchain_import_guard():
    try:
        from trajex.emitters.langchain import TrajexCallbackHandler, trace_from_intermediate_steps
    except ImportError as e:
        assert "trajex[langchain]" in str(e)


def test_openai_import_guard():
    try:
        from trajex.emitters.openai import trace_from_openai_run, trace_from_openai_messages
    except ImportError as e:
        assert "trajex[openai]" in str(e)


def test_crewai_import_guard():
    try:
        from trajex.emitters.crewai import trace_from_crew_output
    except ImportError as e:
        assert "trajex[crewai]" in str(e)


def test_pydantic_ai_import_guard():
    try:
        from trajex.emitters.pydantic_ai import trace_from_pydantic_run
    except ImportError as e:
        assert "trajex[pydantic-ai]" in str(e)


def test_langchain_trace_from_intermediate_steps():
    pytest.importorskip("langchain_core")
    from trajex.emitters.langchain import trace_from_intermediate_steps

    class FakeAction:
        tool = "search"
        tool_input = {"query": "langchain"}
        log = "Searching for langchain info"

    steps = [(FakeAction(), "Search result 1")]
    trace = trace_from_intermediate_steps("What is langchain?", steps, output="LangChain is...")
    assert trace.tool_names() == ["search"]
    assert trace.steps[0].reasoning == "Searching for langchain info"
    assert trace.metadata["framework"] == "langchain"


def test_openai_trace_from_messages():
    pytest.importorskip("openai")
    from trajex.emitters.openai import trace_from_openai_messages

    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {"name": "get_weather", "arguments": '{"city": "NYC"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "72F, sunny"},
        {"role": "assistant", "content": "The weather in NYC is 72F and sunny."},
    ]
    trace = trace_from_openai_messages("What is the weather in NYC?", messages, final_output="72F")
    assert "get_weather" in trace.tool_names()
    tool_step = trace.tool_calls()[0]
    assert tool_step.output == "72F, sunny"
