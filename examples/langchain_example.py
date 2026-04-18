from __future__ import annotations

"""LangChain emitter example using intermediate_steps."""

try:
    from langchain_core.agents import AgentAction
except ImportError:
    print("Run: pip install trajex[langchain]")
    raise

from trajex.emitters.langchain import trace_from_intermediate_steps
from trajex import assert_trajectory
from trajex.assertions import sequence, never_before


class FakeAction:
    def __init__(self, tool: str, tool_input: dict, log: str = ""):
        self.tool = tool
        self.tool_input = tool_input
        self.log = log


intermediate_steps = [
    (FakeAction("verify_permissions", {"user_id": 42}, "Checking permissions first"), {"allowed": True}),
    (FakeAction("confirm_user", {"user_id": 42}, "User exists, confirmed"), {"confirmed": True}),
    (FakeAction("delete_account", {"user_id": 42}, "Deleting account"), {"deleted": True}),
]

trace = trace_from_intermediate_steps(
    prompt="Delete account for user 42",
    steps=intermediate_steps,
    output="Account deleted successfully.",
)

print(trace.to_json())

report = assert_trajectory(
    trace,
    [
        sequence("verify_permissions", "confirm_user", "delete_account"),
        never_before("delete_account", "verify_permissions"),
    ],
    raise_on_failure=False,
    print_report=True,
)

print(report.summary())
