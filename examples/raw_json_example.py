from __future__ import annotations

"""Raw JSON trace example — no framework required."""

from trajex import Trace, assert_trajectory, scan
from trajex.assertions import sequence, never_before, no_loop, max_steps, tool_called

# Load from file
trace = Trace.from_json("tests/fixtures/traces/clean_delete.json")

print(f"Prompt: {trace.prompt}")
print(f"Steps:  {len(trace.steps)}")
print(f"Tools:  {trace.tool_names()}")
print(f"Dur:    {trace.total_duration_ms()}ms")
print()

# Run scan — structural analysis, no keywords, no config
scan_report = scan(trace)
print(f"Scan: {len(scan_report.failures)} failures, {len(scan_report.warnings)} warnings")
print()

# Run assertions
report = assert_trajectory(
    trace,
    [
        sequence("verify_permissions", "confirm_user", "delete_account"),
        never_before("delete_account", "verify_permissions"),
        never_before("delete_account", "confirm_user"),
        no_loop("delete_account", max_calls=1),
        max_steps(10),
        tool_called("verify_permissions"),
    ],
    raise_on_failure=False,
    print_report=True,
)

print(report.summary())
