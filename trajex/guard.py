from __future__ import annotations

from typing import Literal

try:
    from langgraph.prebuilt import ToolNode
    from langgraph.types import interrupt
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False


class TrajexGuardNode:
    """
    A LangGraph node that checks tool calls against a Trajex baseline
    BEFORE executing them.

    Usage:
        from trajex.guard import TrajexGuardNode
        from trajex import BaselineModel

        baseline = BaselineModel.load("my-baseline-id")
        guard = TrajexGuardNode(
            baseline=baseline,
            tools=[search_tool, write_tool, commit_tool],
            on_anomaly="interrupt",   # or "warn" or "block"
        )

        # In your LangGraph graph:
        graph.add_node("tools", guard)
    """

    def __init__(
        self,
        baseline,
        tools: list,
        on_anomaly: Literal["interrupt", "warn", "block"] = "interrupt",
        min_severity: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH",
    ):
        if not _LANGGRAPH_AVAILABLE:
            raise ImportError(
                "LangGraph required for TrajexGuardNode.\n"
                "Install with: pip install trajex[langchain]"
            )
        self.baseline = baseline
        self.tools = {t.name: t for t in tools}
        self.on_anomaly = on_anomaly
        self.min_severity = min_severity

    def __call__(self, state: dict) -> dict:
        from trajex.trace import Trace
        from trajex.anomaly import detect_anomalies

        messages = state.get("messages", [])
        partial_steps = self._extract_steps_from_messages(messages)
        partial_trace = Trace(
            prompt=self._extract_prompt(messages),
            steps=partial_steps,
        )

        findings = detect_anomalies(partial_trace, self.baseline)

        _sev = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        min_num = _sev[self.min_severity]
        critical = [f for f in findings if _sev[f.severity] <= min_num]

        if critical:
            if self.on_anomaly == "interrupt":
                response = interrupt({
                    "type": "trajex_anomaly",
                    "findings": [
                        {
                            "severity": f.severity,
                            "title": f.title,
                            "detail": f.detail,
                            "confidence": f.confidence,
                        }
                        for f in critical
                    ],
                    "message": (
                        f"Trajex detected {len(critical)} anomaly(ies). "
                        f"Review and approve to continue, or reject to stop."
                    ),
                })
                if not response.get("approved"):
                    raise ValueError(
                        "Agent execution blocked by Trajex guard.\n"
                        + "\n".join(f"  {f.title}" for f in critical)
                    )
            elif self.on_anomaly == "warn":
                warnings = list(state.get("trajex_warnings", []))
                warnings.extend([f.title for f in critical])
                state = {**state, "trajex_warnings": warnings}
            elif self.on_anomaly == "block":
                raise ValueError(
                    "Trajex guard blocked execution.\n"
                    + "\n".join(f"  [{f.severity}] {f.title}" for f in critical)
                )

        tool_node = ToolNode(list(self.tools.values()))
        return tool_node(state)

    def _extract_steps_from_messages(self, messages: list) -> list:
        from trajex.trace import Step, StepType
        steps = []
        idx = 0
        for msg in messages:
            for tc in (getattr(msg, "tool_calls", None) or []):
                name = tc.get("name") if isinstance(tc, dict) else tc.name
                args = tc.get("args") if isinstance(tc, dict) else tc.args
                steps.append(Step(
                    index=idx,
                    step_type=StepType.TOOL_CALL,
                    name=name,
                    input=args,
                ))
                idx += 1
        return steps

    def _extract_prompt(self, messages: list) -> str:
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "human":
                return str(msg.content)[:200]
        return ""
