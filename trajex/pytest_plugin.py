from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "trajectory: marks a test as a trajectory behavior test (run with pytest -m trajectory)",
    )


@pytest.fixture
def trajex_trace():
    from trajex.trace import Trace

    def _load(path: str) -> Trace:
        return Trace.from_json(path)

    return _load


@pytest.fixture
def trajex_trace_from_dict():
    from trajex.trace import Trace

    def _build(data: dict) -> Trace:
        return Trace.from_dict(data)

    return _build


def pytest_terminal_summary(terminalreporter: object, exitstatus: int, config: pytest.Config) -> None:
    reports = getattr(terminalreporter, "stats", {})
    failed = reports.get("failed", [])
    trajectory_failures = []
    for report in failed:
        if hasattr(report, "keywords") and "trajectory" in report.keywords:
            trajectory_failures.append(report)
    if trajectory_failures:
        terminalreporter.write_sep("=", "Trajex trajectory failures", red=True)
        for report in trajectory_failures:
            terminalreporter.write_line(f"  TRAJECTORY FAIL: {report.nodeid}", red=True)
            if hasattr(report, "longreprtext"):
                for line in report.longreprtext.splitlines()[:10]:
                    terminalreporter.write_line(f"    {line}")
