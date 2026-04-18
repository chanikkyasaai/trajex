from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class BaselineModel:
    id: str
    name: str
    created_at: datetime
    trace_count: int
    agent_name: str | None
    description: str
    patterns: dict = field(default_factory=dict)

    @classmethod
    def learn(
        cls,
        traces: list,
        name: str | None = None,
        description: str = "",
    ) -> "BaselineModel":
        """
        Learn a baseline from a list of traces.

        Usage:
            traces = [Trace.from_json(p) for p in Path("traces/").glob("*.json")]
            baseline = BaselineModel.learn(traces, name="my-agent-v1")
            baseline.save()
        """
        from trajex.learner import extract_patterns

        patterns = extract_patterns(traces)
        agent_name = None
        if traces:
            agent_name = traces[0].metadata.get("agent_name")
        return cls(
            id=str(uuid4()),
            name=name or f"baseline-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            created_at=datetime.now(timezone.utc),
            trace_count=len(traces),
            agent_name=agent_name,
            description=description,
            patterns=patterns,
        )

    def save(self, store=None) -> str:
        """Save to SQLite. Returns baseline id."""
        from trajex.store import TraceStore
        s = store or TraceStore()
        return s.save_baseline(self)

    @classmethod
    def load(cls, baseline_id: str, store=None) -> "BaselineModel":
        from trajex.store import TraceStore
        s = store or TraceStore()
        return s.load_baseline(baseline_id)

    def summary(self) -> str:
        """One-line human summary of what was learned."""
        tools = list(self.patterns.get("tool_frequency", {}).keys())
        return (
            f"BaselineModel '{self.name}' -- "
            f"{self.trace_count} traces, "
            f"{len(tools)} tools: {', '.join(tools[:5])}"
            f"{'...' if len(tools) > 5 else ''}"
        )
