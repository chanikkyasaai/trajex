from __future__ import annotations

"""OpenAI raw messages emitter example."""

try:
    import openai
except ImportError:
    print("Run: pip install trajex[openai]")
    raise

from trajex.emitters.openai import trace_from_openai_messages
from trajex import assert_trajectory, scan
from trajex.assertions import tool_called, no_loop

messages = [
    {
        "role": "user",
        "content": "What is the weather in NYC and London?",
    },
    {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_001",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city": "NYC"}'},
            },
            {
                "id": "call_002",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city": "London"}'},
            },
        ],
    },
    {"role": "tool", "tool_call_id": "call_001", "content": "72F, sunny"},
    {"role": "tool", "tool_call_id": "call_002", "content": "58F, cloudy"},
    {
        "role": "assistant",
        "content": "NYC is 72F and sunny. London is 58F and cloudy.",
    },
]

trace = trace_from_openai_messages(
    prompt="What is the weather in NYC and London?",
    messages=messages,
    final_output="NYC is 72F and sunny. London is 58F and cloudy.",
)

print(f"Tool calls: {trace.tool_names()}")

scan_report = scan(trace)
print(f"Scan: {len(scan_report.failures)} failures, {len(scan_report.warnings)} warnings")

assert_trajectory(
    trace,
    [
        tool_called("get_weather"),
        no_loop("get_weather", max_calls=5),
    ],
    raise_on_failure=False,
    print_report=True,
)
