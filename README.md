# Trajex

**The open format for AI agent execution traces.**

Assert what your agent *did*, not just what it *said*.

---

## The Problem

Every AI agent framework emits execution data in a completely different shape. LangChain traces look nothing like OpenAI Agents traces. CrewAI output is incompatible with LangGraph tooling. A developer who switches frameworks loses all their traces. There is no standard.

This is the exact problem the infrastructure world had before OpenTelemetry.

## The Solution

Trajex defines a canonical Trace format — the **OpenTelemetry of agent trajectories** — with a testing layer on top.

1. **A spec** — the canonical Trace format, versioned like a protocol
2. **Emitters** — one-line integrations for LangChain, OpenAI Agents, CrewAI, Pydantic AI, and any custom agent
3. **Assertions** — behavioral tests that run against any trace, any framework
4. **CLI** — auto-detects failures in a trace file without writing any tests
5. **Viewer** — local HTML trace explorer, no cloud, no login

---

## Demo

```
$ trajex scan tests/fixtures/traces/loop_notification.json --no-color

Trajex v0.2.0  -  5 step(s) . 4 tool call(s) . 'Send a welcome notification to user 99'

  FAIL  Loop detected: 'send_notification' called 4 times consecutively
        'send_notification' was called 4 times in a row.
        Consecutive repeated tool calls almost always indicate a logic loop.
        Steps involved: [0, 1, 2, 3]
        -> fix: no_loop('send_notification', max_calls=1)

  WARN  'send_notification' called twice in a row with identical inputs
        Steps 0 and 1 are identical calls to 'send_notification'.
        Input: {'user_id': 99, 'message': 'Welcome!'}
        -> fix: no_loop('send_notification', max_calls=1)

  --------------------------------------------------
  1 silent failure(s). These pass all current tests and will corrupt production.
  Run: trajex init  ->  generate test file that catches them
```

---

## Install

```bash
pip install trajex
```

Zero mandatory dependencies. Works offline. No cloud, no API key.

---

## 5-Minute Quickstart

### With LangChain

```python
from langchain.agents import AgentExecutor
from trajex.emitters.langchain import TrajexCallbackHandler
from trajex import assert_trajectory
from trajex.assertions import sequence, never_before

handler = TrajexCallbackHandler(prompt="Delete account for user 42")

# Pass the handler to your agent
agent.invoke({"input": "Delete account for user 42"}, callbacks=[handler])

trace = handler.build_trace()

assert_trajectory(trace, [
    sequence("verify_permissions", "confirm_user", "delete_account"),
    never_before("delete_account", "verify_permissions"),
])
```

### With OpenAI Agents SDK

```python
from trajex.emitters.openai import trace_from_openai_run
from trajex import assert_trajectory, scan
from trajex.assertions import tool_called, no_loop

# result = await Runner.run(agent, prompt)
trace = trace_from_openai_run(prompt, result)

scan_report = scan(trace)
print(scan_report.suggested_assertions())

assert_trajectory(trace, [
    tool_called("get_weather"),
    no_loop("get_weather", max_calls=3),
])
```

### With Raw JSON

```python
from trajex import Trace, assert_trajectory, scan
from trajex.assertions import sequence, max_steps, tool_called

trace = Trace.from_json("trace.json")

# Structural scan — no keywords, no config
report = scan(trace)
print(report.suggested_assertions())  # copy-paste these into your test file

# Behavioral assertions
assert_trajectory(trace, [
    sequence("verify_permissions", "delete_account"),
    max_steps(10),
    tool_called("verify_permissions"),
])
```

### Auto-generate a test file

```bash
trajex init trace.json --out tests/test_agent.py
```

Generates a valid pytest file from scan findings. Review and commit.

---

## Why Not DeepEval / Langfuse?

| | Trajex | DeepEval | Langfuse |
|---|---|---|---|
| Open format / spec | Yes | No | No |
| Works offline | Yes | Partial | No (cloud) |
| Zero dependencies | Yes | No | No |
| Framework-agnostic | Yes | Partial | Yes |
| Behavioral assertions | Yes | LLM-based | No |
| Structural loop detection | Yes | No | No |
| CI-native (exit codes) | Yes | Partial | No |
| No account required | Yes | Yes | No |

Trajex is not a competitor to Langfuse. Langfuse is a SaaS observability product. Trajex is a wire format and testing library — the layer under everything else.

---

## Assertions Reference

### `sequence(*tools)`

Asserts that the given tools were called in this order (gaps allowed).

```python
sequence("verify_permissions", "confirm_user", "delete_account")
```

Fails if any tool in the sequence is missing or appears out of order.

### `never_before(tool_a, tool_b)`

Asserts that `tool_a` must never run before `tool_b` has run.

```python
never_before("delete_account", "verify_permissions")
# delete_account must not run before verify_permissions
```

**Pass cases:**
- `tool_a` was never called
- `tool_b` was called before `tool_a`

**Fail cases:**
- `tool_a` called but `tool_b` never called (silent bypass)
- `tool_a` called at earlier step than `tool_b`

### `no_loop(tool, max_calls=1)`

Asserts a tool is not called more than `max_calls` times.

```python
no_loop("send_email", max_calls=1)
no_loop("search", max_calls=3)
```

Includes scale impact in failure message: `3x calls per user. At 1,000 users: 3,000 invocations.`

### `max_steps(limit)`

Asserts the total step count does not exceed `limit` (counts ALL steps, not just tool calls).

```python
max_steps(15)
```

### `tool_called(tool)` / `tool_never_called(tool)`

```python
tool_called("verify_permissions")       # must have been called
tool_never_called("drop_table")         # must never have been called
```

---

## Emitters Reference

### LangChain — live capture

```python
from trajex.emitters.langchain import TrajexCallbackHandler

handler = TrajexCallbackHandler(prompt="...")
agent.invoke({"input": "..."}, callbacks=[handler])
trace = handler.build_trace()
```

### LangChain — from intermediate_steps

```python
from trajex.emitters.langchain import trace_from_intermediate_steps

result = agent.invoke({"input": "..."}, return_intermediate_steps=True)
trace = trace_from_intermediate_steps(
    prompt="...",
    steps=result["intermediate_steps"],
    output=result["output"],
)
```

### LangGraph

```python
from trajex.emitters.langchain import trace_from_langgraph_result

result = graph.invoke({"messages": [...]})
trace = trace_from_langgraph_result(prompt="...", result=result)
```

### OpenAI Agents SDK

```python
from trajex.emitters.openai import trace_from_openai_run

result = await Runner.run(agent, prompt)
trace = trace_from_openai_run(prompt, result)
```

### OpenAI raw messages

```python
from trajex.emitters.openai import trace_from_openai_messages

trace = trace_from_openai_messages(prompt, messages, final_output=output)
```

### CrewAI

```python
from trajex.emitters.crewai import trace_from_crew_output

output = crew.kickoff(inputs={"prompt": "..."})
trace = trace_from_crew_output(prompt="...", crew_output=output)
```

### Pydantic AI

```python
from trajex.emitters.pydantic_ai import trace_from_pydantic_run

result = await agent.run(prompt)
trace = trace_from_pydantic_run(prompt, result)
```

### Any custom agent

```python
from trajex.emitters.generic import capture_trace, record_tool_call

@record_tool_call
def my_tool(query: str) -> str:
    return search(query)

@capture_trace(prompt="my task")
def run_agent(input: str) -> str:
    result = my_tool(input)
    return result

run_agent("find users")
trace = run_agent.last_trace
```

---

## Behavioral learning (new in 0.3.0)

Trajex can learn what correct behavior looks like from your passing traces — no rules to write.

```python
import trajex

# Step 1: Learn from your passing traces
baseline = trajex.learn("tests/fixtures/passing_traces/")
# Saved baseline 'baseline-20260418' (ID: a3f1c2b8)

# Step 2: Check new traces against the baseline
from trajex import Trace
trace = Trace.from_json("new_run.json")
findings = trajex.check_anomalies(trace, baseline)

for f in findings:
    print(f"[{f.severity}] {f.title}")
    print(f"  Expected: {f.expected}")
    print(f"  Observed: {f.observed}")
    print(f"  Confidence: {f.confidence:.0%}")
```

```
[HIGH]   New tool appeared: 'drop_database'
         Expected: never seen in 47 baseline traces
         Observed: called at step 2
         Confidence: 100%

[HIGH]   Ordering reversal: 'delete_account' before 'confirm_user'
         Expected: confirm_user before delete_account (94% of traces)
         Observed: delete_account at step 0, confirm_user at step 2
         Confidence: 94%

[MEDIUM] 'send_notification' called 4x -- unusually high
         Expected: 1.1 +/- 0.3 calls per trace
         Observed: 4 calls (9.7 standard deviations above normal)
         Confidence: 91%
```

CLI:
```bash
# Learn from a directory of traces
trajex learn tests/fixtures/passing_traces/ --name "my-agent-v2"

# Check a new trace against the baseline
trajex check new_run.json --baseline "my-agent-v2"

# List all saved baselines
trajex baseline list

# Remove a baseline
trajex baseline delete my-agent-v2
```

Baselines are stored in `~/.trajex/baselines.db` (SQLite, stdlib only — zero new dependencies).

Six anomaly checks run automatically:

| Check | Fires when |
|-------|-----------|
| `new_tool_appeared` | A tool is called that never appeared in baseline traces |
| `tool_disappeared` | A tool present in 95%+ of baselines is absent |
| `ordering_violation` | A strong ordering learned from baselines is reversed |
| `tool_frequency_spike` | A tool is called significantly more than baseline mean |
| `step_count_anomaly` | Total steps deviate > 2 standard deviations from baseline |
| `unexpected_first_tool` | First tool called appears as first step in < 5% of baselines |

## Real-time interception (LangGraph)

```python
from trajex.guard import TrajexGuardNode
from trajex import BaselineModel

baseline = BaselineModel.load("my-agent-v2")
guard = TrajexGuardNode(
    baseline=baseline,
    tools=[search_tool, write_tool, commit_tool],
    on_anomaly="interrupt",   # pause for human review
)

# Drop into your LangGraph graph
graph.add_node("tools", guard)
graph.add_edge("agent", "tools")
```

When an anomaly is detected before tool execution:
- `"interrupt"` — pauses the graph, waits for human approval via `langgraph.types.interrupt`
- `"warn"` — adds warning to state under `trajex_warnings`, continues running
- `"block"` — raises `ValueError`, stops execution immediately

Requires `pip install trajex[langchain]`. The guard module fails gracefully with a clear
`ImportError` message when LangGraph is not installed.

---

## CLI Reference

```bash
trajex scan  <trace.json> [--schema schema.json] [--no-color]
```
Scans for structural and behavioral anomalies. Exits 1 if failures found.

```bash
trajex init  <trace.json> [--out test_agent.py]
```
Generates a pytest test file from scan findings.

```bash
trajex view  <trace.json>
```
Opens a self-contained HTML trace viewer in your browser. No server. No login.

```bash
trajex check <trace.json> [--schema schema.json]
```
CI mode — silent scan, exits 1 on failures.

```bash
trajex info  <trace.json>
```
Prints trace summary (ID, prompt, steps, tools, duration, framework, model).

### Schema file (for name-aware checks)

```json
{
  "destructive_tools": ["delete_user", "drop_table"],
  "guard_tools": ["confirm_action", "verify_permissions"],
  "financial_tools": ["charge_card", "transfer_funds"],
  "notification_tools": ["send_email", "send_sms"]
}
```

Without a schema, the scanner uses structural analysis only (no keyword guessing).

---

## The Trace Format

Trajex defines a versioned, open trace format. Any framework can emit it. Any tool can consume it.

See [`spec/TRACE_FORMAT.md`](spec/TRACE_FORMAT.md) for the full specification.

```json
{
  "trajex_version": "1",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "prompt": "Delete account for user 42",
  "status": "success",
  "steps": [
    {
      "index": 0,
      "step_type": "tool_call",
      "name": "verify_permissions",
      "input": {"user_id": 42},
      "output": {"allowed": true}
    }
  ]
}
```

---

## Contributing

### Adding an emitter for a new framework

1. Create `trajex/emitters/<framework>.py`
2. Add an import guard at the top (`try: import framework; _AVAILABLE = True`)
3. Implement a `trace_from_<framework>_result(prompt, result) -> Trace` function
4. Map framework-specific objects to `Step` objects with appropriate `step_type`
5. Set `metadata["framework"]` to your framework name
6. Add tests in `tests/test_emitters.py`
7. Add an example in `examples/`
8. Update this README's Emitters Reference section

The key rule: `tool_call` steps are what assertions operate on. Make sure your emitter maps the framework's tool calls to `StepType.TOOL_CALL`.

### Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## License

MIT — see [LICENSE](LICENSE).
