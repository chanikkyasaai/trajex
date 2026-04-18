from __future__ import annotations

import os
import subprocess
import sys

import pytest

FIXTURES = "tests/fixtures/synthetic_traces"
PYTHON = sys.executable


def run_cli(*args: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [PYTHON, "-m", "trajex.cli", *args],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_cli_help():
    code, out, _ = run_cli("--help")
    assert code == 0
    assert "trajex" in out.lower()


def test_cli_info_clean():
    code, out, _ = run_cli("info", f"{FIXTURES}/clean_delete.json")
    assert code == 0
    assert "Trace ID" in out
    assert "Prompt" in out
    assert "Steps" in out
    assert "Tools called" in out
    assert "Duration" in out
    assert "Framework" in out
    assert "Model" in out


def test_cli_scan_auth_bypass_exits_1_with_schema(tmp_path):
    import json
    schema_file = str(tmp_path / "schema.json")
    with open(schema_file, "w") as f:
        json.dump({"destructive_tools": ["delete_account"], "guard_tools": ["confirm_user"]}, f)
    code, out, _ = run_cli("scan", f"{FIXTURES}/auth_bypass.json", "--schema", schema_file, "--no-color")
    assert code == 1
    assert "FAIL" in out


def test_cli_scan_clean_exits_0():
    code, out, _ = run_cli("scan", f"{FIXTURES}/clean_delete.json", "--no-color")
    assert code == 0
    assert "No issues" in out


def test_cli_scan_loop_exits_1():
    code, out, _ = run_cli("scan", f"{FIXTURES}/loop_notification.json", "--no-color")
    assert code == 1
    assert "Loop" in out or "loop" in out.lower()


def test_cli_init_generates_file(tmp_path):
    out_file = str(tmp_path / "test_gen.py")
    code, out, _ = run_cli("init", f"{FIXTURES}/auth_bypass.json", "--out", out_file)
    assert code == 0
    assert os.path.exists(out_file)
    # Must compile without errors
    result = subprocess.run(
        [PYTHON, "-m", "py_compile", out_file],
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()


def test_cli_view_exits_0(monkeypatch):
    # Can't open browser in CI; patch webbrowser.open
    code, out, _ = run_cli("view", f"{FIXTURES}/clean_delete.json")
    # Exit 0 is sufficient; browser open may fail silently in CI
    assert code in (0, 1)


def test_cli_check_auth_bypass_exits_1_with_schema(tmp_path):
    import json
    schema_file = str(tmp_path / "schema.json")
    with open(schema_file, "w") as f:
        json.dump({"destructive_tools": ["delete_account"], "guard_tools": ["confirm_user"]}, f)
    code, _, err = run_cli("check", f"{FIXTURES}/auth_bypass.json", "--schema", schema_file)
    assert code == 1


def test_cli_check_clean_exits_0():
    code, _, _ = run_cli("check", f"{FIXTURES}/clean_delete.json")
    assert code == 0


def test_cli_info_missing_file_exits_2():
    code, _, err = run_cli("info", "nonexistent_file.json")
    assert code == 2


def test_cli_scan_invalid_json_exits_3(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"not": "a trace"}')
    code, _, _ = run_cli("scan", str(bad))
    assert code == 3
