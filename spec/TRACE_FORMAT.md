# Trajex Trace Format Specification

**Version:** 1.0.0  
**Status:** Draft  
**Date:** 2026-04-18  
**Authors:** Trajex Contributors  

---

## Abstract

This document defines the Trajex Trace Format — a vendor-neutral, framework-agnostic standard for recording AI agent execution trajectories. It covers the Trace object structure, the Step object structure, serialization rules, versioning policy, migration guidance, and producer/consumer conformance requirements.

The relationship to prior art: Trajex is to AI agent traces what OpenTelemetry is to distributed systems spans. The format is a wire protocol, not a runtime SDK. Any agent framework can produce it; any analysis tool can consume it.

---

## 1. Terminology

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

- **Trace**: A complete record of one agent execution run, from input prompt to final output or error.
- **Step**: A single discrete action taken during an agent run (tool call, LLM call, handoff, etc.).
- **Emitter**: A component that produces Trajex-conformant traces from a specific agent framework.
- **Consumer**: A component that reads and processes Trajex traces (CLI, viewer, assertion engine, diff tool, etc.).
- **Conformant Producer**: An emitter that satisfies all MUST requirements in Section 8.1.
- **Conformant Consumer**: A reader that satisfies all MUST requirements in Section 8.2.

---

## 2. Design Principles

1. **Zero mandatory dependencies.** A Trace is plain JSON. Reading or writing it requires no external library.
2. **Forward compatibility by default.** Consumers MUST NOT fail on unknown fields or unknown step types. New fields are always additive.
3. **Tool calls are the unit of analysis.** Behavioral assertions operate only on `tool_call` steps. All other step types are observability metadata.
4. **Explicit nulls over omission.** Optional fields MUST be present with explicit `null` values, not silently dropped. This makes schema validation unambiguous.
5. **No clock requirement.** Timestamps are OPTIONAL. A valid trace may have no timing information at all.

---

## 3. Trace Object

A Trace MUST be a JSON object (`{}`).

### 3.1 Required Fields

| Field | Type | Constraint |
|-------|------|------------|
| `trajex_version` | string | MUST be `"1"` for traces produced under this specification. |
| `id` | string | MUST be a UUID v4 in lowercase hyphenated form: `"xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"`. |
| `prompt` | string | MUST be non-null. MAY be the empty string `""` when the agent was invoked without explicit input. |
| `steps` | array | MUST be a JSON array. MAY be empty. |

### 3.2 Optional Fields

| Field | Type | Default | Constraint |
|-------|------|---------|------------|
| `final_output` | string \| null | `null` | The agent's final response text. |
| `status` | string | `"success"` | MUST be one of: `"success"`, `"error"`, `"interrupted"`. Unknown values SHOULD be treated as `"error"`. |
| `started_at` | string \| null | `null` | ISO 8601 datetime in UTC. See Section 6.1. |
| `ended_at` | string \| null | `null` | ISO 8601 datetime in UTC. See Section 6.1. |
| `metadata` | object | `{}` | See Section 3.3. |

### 3.3 Metadata Object

`metadata` is a free-form object. The following keys are RECOMMENDED for interoperability:

| Key | Type | Description |
|-----|------|-------------|
| `framework` | string | One of: `"langchain"`, `"openai_agents"`, `"crewai"`, `"pydantic_ai"`, `"unknown"`. |
| `model` | string \| null | Primary model identifier (e.g. `"gpt-4o"`, `"claude-sonnet-4-6"`). |
| `agent_name` | string \| null | Human-readable name for the agent or pipeline. |
| `tags` | array of strings | User-defined classification tags. |
| `custom` | object | Application-specific key-value pairs. |

Implementations MUST preserve unknown metadata keys. They MUST NOT reject a trace for containing metadata fields not listed here.

---

## 4. Step Object

Each element of `steps` MUST be a JSON object conforming to this section.

### 4.1 Required Fields

| Field | Type | Constraint |
|-------|------|------------|
| `index` | integer | Zero-based sequential position. Steps MUST be ordered by index with no gaps. The first step is at index `0`. |
| `step_type` | string | One of the values defined in Section 5. Unknown values MUST NOT cause a parse error. |
| `name` | string | Human-readable identifier. MUST be non-null. See naming conventions in Section 4.3. |

### 4.2 Optional Fields

| Field | Type | Constraint |
|-------|------|------------|
| `input` | any JSON value \| null | Input to this step. May be a string, number, object, or array. |
| `output` | any JSON value \| null | Output from this step. |
| `error` | string \| null | Exception or error message if this step failed. MUST be a string if present. |
| `reasoning` | string \| null | Chain-of-thought text from the model, if the framework exposes it. |
| `started_at` | string \| null | ISO 8601 UTC datetime. |
| `ended_at` | string \| null | ISO 8601 UTC datetime. |
| `duration_ms` | number \| null | Elapsed time in milliseconds. If both `started_at` and `ended_at` are present and `duration_ms` is null, consumers MAY compute it. See Section 4.4. |
| `metadata` | object | Step-level metadata. MUST be an object. |

### 4.3 Naming Conventions

- `tool_call` steps: `name` MUST be the exact function/method name of the tool called. Must be stable across runs (not include dynamic IDs).
- `llm_call` / `llm_response` steps: `name` SHOULD be the model identifier (e.g. `"gpt-4o"`). MAY be `"llm"` if the model is unknown.
- `agent_finish` steps: `name` SHOULD be `"agent_finish"`.
- `handoff` steps: `name` SHOULD identify the target agent (e.g. `"handoff:coding_agent"`).
- `error` steps: `name` SHOULD match the name of the step that failed.

### 4.4 Duration Computation

If `started_at` and `ended_at` are both present and `duration_ms` is `null`, consumers MAY compute `duration_ms = (ended_at - started_at) * 1000`. Consumers MUST NOT assume `duration_ms` is present.

If `duration_ms` is present and timestamps are also present, `duration_ms` takes precedence for display; consumers SHOULD NOT recompute it.

---

## 5. Step Types

| Value | Description | Used By |
|-------|-------------|---------|
| `tool_call` | The agent invoked an external tool or function. | Behavioral assertions, diff, scan |
| `tool_result` | The value returned from the preceding tool call. | Debugging |
| `llm_call` | The agent submitted a request to an LLM. | Latency analysis |
| `llm_response` | The LLM returned a completion. | Output analysis |
| `agent_action` | A high-level agent decision not decomposed into tool + LLM. | Used when framework does not distinguish them. |
| `agent_finish` | The agent produced its final output and halted cleanly. | End-of-trace marker |
| `handoff` | The agent transferred control to another agent in a multi-agent pipeline. | Multi-agent tracing |
| `error` | A step that terminated with an exception or non-recoverable error. | Error analysis |

### 5.1 Primacy of `tool_call`

Behavioral assertions (sequence ordering, call count, never-before, etc.) MUST operate only on steps where `step_type == "tool_call"`. Steps of other types provide observability context and MUST NOT be factored into assertion logic unless explicitly opted in by the caller.

This is the core invariant that makes traces framework-agnostic: regardless of how many `llm_call` or `llm_response` steps exist, the behavioral contract is expressed purely in terms of which tools were called, in what order, and how many times.

### 5.2 Unknown Step Types

Consumers MUST NOT raise an error when encountering an unknown `step_type` value. They SHOULD treat unknown step types as `"agent_action"` for display purposes. For assertion purposes, unknown step types MUST be excluded from tool-call filtering (i.e. treated as non-`tool_call`).

---

## 6. Serialization

### 6.1 Datetime Format

All datetime values MUST be ISO 8601 strings with explicit UTC offset. The canonical form is:

```
YYYY-MM-DDTHH:MM:SS.ffffffZ  (preferred)
YYYY-MM-DDTHH:MM:SS.ffffff+00:00  (also acceptable)
```

Unix timestamps (integer seconds or milliseconds since epoch) are NOT permitted. Naive datetimes (no timezone offset) are NOT permitted.

### 6.2 UUID Format

All UUID values MUST be lowercase hyphenated strings:

```
550e8400-e29b-41d4-a716-446655440000  (correct)
550E8400E29B41D4A716446655440000      (NOT permitted)
```

### 6.3 Null Representation

Optional fields MUST be present with explicit `null` values. Fields MUST NOT be omitted to represent absence. Consumers that encounter an absent optional field MUST treat it as `null`.

Rationale: omitting fields to mean null makes schema validation ambiguous and breaks forward-compatibility checks.

### 6.4 Non-JSON-Serializable Values

- Pydantic models in `input` / `output`: MUST be serialized via `.model_dump()`.
- Python exceptions in `error`: MUST be `str(exc)`.
- All other non-JSON-serializable objects: MUST be converted to string via `str()`.
- Producers MUST NOT store Python objects, class instances, or callables in any field.

### 6.5 File Encoding

- MUST be UTF-8 with no BOM.
- SHOULD be pretty-printed with 2-space indentation for file storage.
- MAY be compact (single line) for network transmission.
- File extension SHOULD be `.json`.

---

## 7. Versioning Policy

### 7.1 Version Identifier

`trajex_version` is a string, not a semver. The current value is `"1"`. Future values will be `"2"`, `"3"`, etc. Minor additive changes within a version do not require a version bump.

### 7.2 What Triggers a Major Version Bump

A new version identifier is REQUIRED for any of the following:

| Change | Example |
|--------|---------|
| Removing a required field | Removing `id` |
| Changing the type of a required field | `steps` becomes an object |
| Renaming a required field | `prompt` → `input_prompt` |
| Changing the semantics of an existing `step_type` in a breaking way | `tool_call` is redefined to exclude synchronous function calls |
| Making a previously optional field required | `status` becomes required |

The following changes do NOT trigger a version bump:

| Change | Example |
|--------|---------|
| Adding a new optional field | Adding `parent_trace_id` |
| Adding a new `step_type` value | Adding `"retrieval"` |
| Adding new RECOMMENDED metadata keys | Adding `"model_version"` to metadata |

### 7.3 Consumer Migration

When a consumer encounters `trajex_version: "2"` and only supports `"1"`:

1. MUST NOT raise a hard error.
2. SHOULD emit a warning: `"Trace version '2' is newer than supported version '1'. Some fields may be ignored."`
3. MUST attempt to parse the trace using version-1 rules.
4. MUST NOT crash on fields it does not recognize.

When a consumer encounters a trace with no `trajex_version` field:

1. MUST assume version `"1"`.
2. MAY emit a warning: `"Trace has no trajex_version — assuming '1'."`

### 7.4 Producer Migration

When a producer updates from version 1 to version 2:

1. MUST update `trajex_version` to `"2"`.
2. MUST NOT write traces that are ambiguous between versions (e.g. a field whose meaning changed).
3. SHOULD provide a migration utility that upgrades version-1 traces to version-2 format.

---

## 8. Conformance

### 8.1 Conformant Producer

A Trajex-conformant producer:

- MUST include all required Trace fields (`trajex_version`, `id`, `prompt`, `steps`).
- MUST include all required Step fields for each step (`index`, `step_type`, `name`).
- MUST write `trajex_version: "1"` for traces produced under this specification.
- MUST generate UUID v4 values for `id`.
- MUST serialize datetimes as ISO 8601 UTC strings.
- MUST NOT store non-JSON-serializable values in any field.
- MUST write all optional fields explicitly as `null` when absent.
- SHOULD include `metadata.framework` and `metadata.model`.
- SHOULD include `started_at` and `ended_at` when timing is available.

### 8.2 Conformant Consumer

A Trajex-conformant consumer:

- MUST accept traces where any optional field is `null` or absent.
- MUST accept traces with extra unknown fields at any level.
- MUST NOT raise an error on unknown `step_type` values.
- MUST gracefully handle `trajex_version` values it does not recognize.
- MUST NOT assume `steps` is non-empty.
- MUST NOT assume any step field other than `index`, `step_type`, and `name` is present or non-null.

---

## 9. Reference Examples

### 9.1 Minimal Conformant Trace

```json
{
  "trajex_version": "1",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "prompt": "Delete user 42",
  "steps": []
}
```

### 9.2 Full Trace with Tool Calls

```json
{
  "trajex_version": "1",
  "id": "a3f9b1c0-d2e4-4f56-8901-bcdef1234567",
  "prompt": "Delete account for user 42 after verifying permissions",
  "final_output": "Account deleted.",
  "status": "success",
  "started_at": "2026-04-18T10:00:00.000000+00:00",
  "ended_at": "2026-04-18T10:00:05.000000+00:00",
  "metadata": {
    "framework": "langchain",
    "model": "gpt-4o",
    "agent_name": null,
    "tags": [],
    "custom": {}
  },
  "steps": [
    {
      "index": 0,
      "step_type": "tool_call",
      "name": "verify_permissions",
      "input": {"user_id": 42, "action": "delete"},
      "output": {"allowed": true},
      "error": null,
      "reasoning": "First verify the caller has permission.",
      "started_at": "2026-04-18T10:00:00.000000+00:00",
      "ended_at": "2026-04-18T10:00:01.000000+00:00",
      "duration_ms": 1000.0,
      "metadata": {}
    },
    {
      "index": 1,
      "step_type": "tool_call",
      "name": "delete_account",
      "input": {"user_id": 42},
      "output": {"deleted": true},
      "error": null,
      "reasoning": "Permissions confirmed. Proceeding.",
      "started_at": "2026-04-18T10:00:01.000000+00:00",
      "ended_at": "2026-04-18T10:00:02.000000+00:00",
      "duration_ms": 1000.0,
      "metadata": {}
    },
    {
      "index": 2,
      "step_type": "agent_finish",
      "name": "agent_finish",
      "input": null,
      "output": "Account deleted.",
      "error": null,
      "reasoning": null,
      "started_at": "2026-04-18T10:00:02.000000+00:00",
      "ended_at": "2026-04-18T10:00:05.000000+00:00",
      "duration_ms": 3000.0,
      "metadata": {}
    }
  ]
}
```

### 9.3 Error Step

```json
{
  "index": 1,
  "step_type": "error",
  "name": "delete_account",
  "input": {"user_id": 42},
  "output": null,
  "error": "PermissionDeniedError: user 42 is protected",
  "reasoning": null,
  "started_at": "2026-04-18T10:00:03.000000+00:00",
  "ended_at": "2026-04-18T10:00:03.100000+00:00",
  "duration_ms": 100.0,
  "metadata": {}
}
```

### 9.4 Handoff Step

```json
{
  "index": 3,
  "step_type": "handoff",
  "name": "handoff:coding_agent",
  "input": {"task": "write unit tests for auth module"},
  "output": null,
  "error": null,
  "reasoning": "Delegating to specialized coding agent.",
  "started_at": "2026-04-18T10:00:04.000000+00:00",
  "ended_at": null,
  "duration_ms": null,
  "metadata": {"target_agent_id": "coding_agent_v2"}
}
```

---

## 10. Known Limitations and Open Questions

### 10.1 Async Concurrency

The `@capture_trace_async` / `@record_tool_call_async` decorators use `contextvars.ContextVar` for trace propagation. `ContextVar` is safe for sequential async calls within a single coroutine. It is NOT safe when two tool calls are awaited concurrently via `asyncio.gather()`, because both coroutines share the same context object and will race when appending steps.

**Workaround:** Use sequential `await` calls inside captured coroutines. If concurrent tool execution is required, use a separate trace per concurrent branch and merge results manually.

This limitation is inherent to shared mutable state in cooperative multitasking. A future version of this spec may define a protocol for sub-trace merging.

### 10.2 Multi-Agent Traces

This version of the spec defines the trace format for a single agent execution. Multi-agent pipelines with `handoff` steps produce one trace per agent. There is no standardized protocol for linking traces across agents (e.g. via `parent_trace_id`). This is an open design question.

### 10.3 Streaming Outputs

Traces do not model streaming token output. When a streaming LLM call is captured, the emitter SHOULD wait for the stream to complete and record the full output in `output`. Partial outputs are not representable in the current format.

---

## Appendix A: Changelog

### v1.0.0 (2026-04-18)
- Initial specification.
- Defined Trace and Step objects with required/optional fields.
- Defined eight `step_type` values.
- Defined versioning policy with explicit major-bump triggers.
- Defined producer and consumer conformance requirements.
- Documented async concurrency limitation.
