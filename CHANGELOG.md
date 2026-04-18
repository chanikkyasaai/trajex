# Changelog

All notable changes to Trajex are documented here.
This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] — 2026-04-18

### Added

- **Behavioral diff engine** (`trajex diff`): named finding types for tool sequence changes —
  `new_tool_appeared`, `tool_disappeared`, `ordering_reversal`, `tool_call_count_increased/decreased`,
  `error_count_increased/decreased`, `step_count_increased/decreased`, `duration_increased/decreased`,
  `status_changed`. Output sorted regressions-first.
- **`_find_ordering_reversals()`**: pairwise first-occurrence comparison to detect guard ordering bypasses.
- **Async emitter support**: `capture_trace_async` and `record_tool_call_async` decorators for wrapping
  async agent coroutines and tool functions. Both use `contextvars.ContextVar` for propagation.
- **`--out` flag on `trajex view`**: write the HTML viewer to a specific path instead of a temp file.
- **Emitter exports** in `trajex.__init__`: `capture_trace`, `capture_trace_async`, `record_tool_call`,
  `record_tool_call_async` are now importable from the top-level package.
- **Formal spec** (`spec/TRACE_FORMAT.md`): versioning policy with explicit major-bump triggers,
  producer/consumer conformance levels per RFC 2119, migration guidance, async limitation documented.

### Changed

- **`trajex view`** no longer calls `webbrowser.open()`. The CLI prints the absolute file path to stdout.
  Callers that want to open a browser must do so explicitly. This fixes silent failures in CI environments.
- **`format_scan_report()`** now takes `trace: Trace` as its second argument (previously required a
  separate `trace` kwarg). `format_scan_report_with_trace()` kept as deprecated alias.
- **`DiffFinding`** fields renamed: `field` → `check`, `description` → `detail`. Added `before` and `after`
  fields carrying raw values for programmatic use.
- **`no_loop` assertion detail**: removed the `count * 1000` scale-impact claim (was a fabricated metric).
  Detail now reports exact call count, limit, excess count, and step indices.
- **`TraceDiff.summary()`**: returns `"no behavioral differences"` (was `"no differences"`).

### Fixed

- `TrajexCallbackHandler` (LangChain emitter): rewritten as conditional class definition at module level
  (`if _AVAILABLE: class ... else: class stub`). The previous runtime `type(...)` class-swap broke `isinstance` checks.
- `pyproject.toml` build backend: was `setuptools.backends.legacy:build` (does not exist).
  Corrected to `setuptools.build_meta`.
- Non-ASCII em-dash in `goal_drift` scanner output: replaced with `--` for Windows CMD compatibility.

### Removed

- `webbrowser` import from `trajex/viewer.py`.
- `open_viewer()` no longer opens a browser. Use `write_viewer()` and open manually.

---

## [0.1.0] — 2026-04-17

### Added

- Initial release.
- Core trace format: `Trace`, `Step`, `StepType` dataclasses with full JSON round-trip serialization.
- Assertion engine: `sequence`, `never_before`, `no_loop`, `max_steps`, `tool_called`, `tool_never_called`.
- Scanner: 10 structural checks + 3 semantic checks (goal_drift, abandoned_plan, repetitive_reasoning)
  + 4 schema-aware checks (unguarded_destructive_tool, guard_too_late, financial_tool_called, notification_spam).
- HTML trace viewer: self-contained, no CDN dependencies, syntax-highlighted JSON, step timeline, search.
- CLI: `scan`, `init`, `check`, `info`, `view`, `diff` subcommands.
- Emitters: LangChain, OpenAI Agents, CrewAI, Pydantic AI, generic decorator API.
- pytest plugin: `assert_trajectory` fixture for test file integration.
- Zero mandatory runtime dependencies.
