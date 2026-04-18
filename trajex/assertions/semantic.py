from __future__ import annotations

import importlib.util
import json
import logging
from typing import TYPE_CHECKING

from trajex.result import AssertionResult, TrajectoryAssertion

if TYPE_CHECKING:
    from trajex.trace import Trace

logger = logging.getLogger("trajex")

_OPENAI_AVAILABLE = importlib.util.find_spec("openai") is not None


def _require_openai() -> None:
    if not _OPENAI_AVAILABLE:
        raise ImportError(
            "Install the semantic assertions with: pip install trajex[semantic]"
        )


def _llm_score(final_output: str | None, goal: str, model: str) -> float:
    _require_openai()
    import openai

    client = openai.OpenAI()
    prompt = (
        f"You are evaluating whether an AI agent achieved its stated goal.\n\n"
        f"Goal: {goal}\n"
        f"Agent final output: {final_output or '(no output)'}\n\n"
        f"Score from 0.0 to 1.0 how well the output addresses the goal.\n"
        f'1.0 = fully achieved, 0.0 = completely failed, 0.5 = partially.\n\n'
        f'Respond with ONLY a JSON object: {{"score": <float>, "reason": "<one sentence>"}}'
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    raw = response.choices[0].message.content or ""
    try:
        data = json.loads(raw)
        return float(data["score"])
    except (json.JSONDecodeError, KeyError, ValueError):
        raise ValueError(f"LLM scoring returned unparseable response: {raw!r}")


class GoalAchievedAssertion(TrajectoryAssertion):
    def __init__(self, goal: str, model: str = "gpt-4o-mini", threshold: float = 0.7) -> None:
        self.goal = goal
        self.model = model
        self.threshold = threshold
        self.name = f"goal_achieved({goal[:30]!r})"

    def check(self, trace: "Trace") -> AssertionResult:
        try:
            score = _llm_score(trace.final_output, self.goal, self.model)
        except ImportError as exc:
            return AssertionResult(
                passed=False,
                name=self.name,
                message=str(exc),
            )
        except Exception as exc:
            return AssertionResult(
                passed=False,
                name=self.name,
                message=f"LLM scoring failed: {exc}",
            )

        passed = score >= self.threshold
        return AssertionResult(
            passed=passed,
            name=self.name,
            message=f"Goal achievement score: {score:.2f} (threshold: {self.threshold})",
            detail="" if passed else f"Goal: {self.goal}\nOutput: {(trace.final_output or '')[:200]}",
        )


class NoHallucinationAssertion(TrajectoryAssertion):
    def __init__(self, context: str, model: str = "gpt-4o-mini") -> None:
        self.context = context
        self.model = model
        self.name = "no_hallucination"

    def check(self, trace: "Trace") -> AssertionResult:
        try:
            _require_openai()
            import openai

            client = openai.OpenAI()
            prompt = (
                f"You are checking whether an AI agent's output contains claims that contradict "
                f"or are absent from the provided context.\n\n"
                f"Context: {self.context}\n\n"
                f"Agent output: {trace.final_output or '(no output)'}\n\n"
                f"Does the output contain hallucinations — claims not supported by the context?\n"
                f'Respond with ONLY: {{"hallucination": true/false, "reason": "<one sentence>"}}'
            )
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            raw = response.choices[0].message.content or ""
            data = json.loads(raw)
            hallucinated = bool(data.get("hallucination", False))
            reason = data.get("reason", "")
            return AssertionResult(
                passed=not hallucinated,
                name=self.name,
                message=f"Hallucination check: {'DETECTED' if hallucinated else 'none detected'}",
                detail=reason if hallucinated else "",
            )
        except ImportError as exc:
            return AssertionResult(passed=False, name=self.name, message=str(exc))
        except Exception as exc:
            return AssertionResult(passed=False, name=self.name, message=f"LLM scoring failed: {exc}")


def goal_achieved(goal: str, model: str = "gpt-4o-mini", threshold: float = 0.7) -> GoalAchievedAssertion:
    return GoalAchievedAssertion(goal, model, threshold)


def no_hallucination(context: str, model: str = "gpt-4o-mini") -> NoHallucinationAssertion:
    return NoHallucinationAssertion(context, model)
