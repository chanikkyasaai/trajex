from __future__ import annotations

from trajex.emitters.generic import capture_trace, record_tool_call


@record_tool_call
def verify_permissions(user_id: int) -> dict:
    return {"allowed": True}


@record_tool_call
def delete_account(user_id: int) -> dict:
    return {"deleted": True}


@capture_trace(prompt="Delete account for user 1 after verifying permissions")
def run_mock_agent(input: str) -> str:
    verify_permissions(1)
    delete_account(1)
    return "Done"


if __name__ == "__main__":
    result = run_mock_agent("run")
    trace = run_mock_agent.last_trace
    print(trace.to_json())
