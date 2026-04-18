"""
Audit all trace fixtures and classify REAL vs SYNTHETIC.

REAL = captured from a live LLM execution (any provider)
SYNTHETIC = hand-constructed for testing, with round timestamps and/or explicit model labels

Usage:
    python scripts/audit_traces.py [--move]

Without --move: prints the audit report only.
With --move: physically moves files into the correct directories.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from pathlib import Path

FIXTURE_ROOT = Path(__file__).parent.parent / "tests" / "fixtures"
REAL_DIR = FIXTURE_ROOT / "real_traces"
SYNTHETIC_DIR = FIXTURE_ROOT / "synthetic_traces"


def audit_file(path: Path) -> tuple[str, list[str]]:
    """
    Return (verdict, indicators) where verdict is REAL, SYNTHETIC, or AMBIGUOUS.
    """
    try:
        with open(path) as f:
            d = json.load(f)
    except Exception as e:
        return "AMBIGUOUS", [f"parse_error: {e}"]

    indicators: list[str] = []
    synthetic_score = 0
    real_score = 0

    # ── UUID version ──────────────────────────────────────────────────────────
    try:
        u = uuid.UUID(d.get("id", ""))
        if u.version == 5:
            indicators.append("uuid_v5 (synthetic uuid.uuid5)")
            synthetic_score += 2
        elif u.version == 4:
            indicators.append("uuid_v4")
            real_score += 1
    except Exception:
        indicators.append("no/bad uuid")

    # ── Model + framework fields ──────────────────────────────────────────────
    # Key insight: real traces captured by @capture_trace have model=None
    # and framework="unknown" because the decorator doesn't inject those fields.
    # Synthetic traces have explicit model/framework set by the generator script.
    meta = d.get("metadata") or {}
    model = meta.get("model") or d.get("model") or ""
    framework = meta.get("framework", "")

    if model == "" or model is None:
        if framework == "unknown":
            indicators.append("model=None, framework=unknown (capture_trace signature)")
            real_score += 3  # strong real signal
        else:
            indicators.append(f"model=None but framework={framework}")
    elif "gpt-4" in str(model) or "gpt-3.5" in str(model):
        indicators.append(f"model={model} (OpenAI — not used in live runs)")
        synthetic_score += 3
    else:
        # Any explicitly named model was set by the generator script
        indicators.append(f"model={model}, framework={framework} (explicit — generator-set)")
        synthetic_score += 2

    # ── Trace-level timestamps ────────────────────────────────────────────────
    started_at = d.get("started_at", "")
    if started_at:
        if "." in started_at:
            indicators.append("trace started_at has microseconds ✓")
            real_score += 2
        else:
            indicators.append("trace started_at lacks microseconds ✗")
            synthetic_score += 2

    # ── Step-level timestamps ─────────────────────────────────────────────────
    steps = d.get("steps", [])
    step_times = [s.get("started_at", "") for s in steps if s.get("started_at")]
    has_microseconds = any("." in t for t in step_times)
    if step_times:
        if has_microseconds:
            indicators.append("step timestamps have microseconds ✓")
            real_score += 2
        else:
            indicators.append("step timestamps lack microseconds ✗")
            synthetic_score += 2

    # ── Duration values ───────────────────────────────────────────────────────
    durations = [s.get("duration_ms") for s in steps if s.get("duration_ms") not in (None, 0.0, 0)]
    if durations:
        round_count = sum(1 for d_ in durations if isinstance(d_, (int, float)) and d_ == int(d_) and int(d_) % 500 == 0)
        if round_count == len(durations) and len(durations) >= 2:
            indicators.append(f"all {len(durations)} non-zero durations are round multiples of 500ms ✗")
            synthetic_score += 2
        else:
            indicators.append("durations have sub-ms variation ✓")
            real_score += 1

    # ── Verdict ───────────────────────────────────────────────────────────────
    if synthetic_score >= 3:
        verdict = "SYNTHETIC"
    elif real_score >= 3:
        verdict = "REAL"
    else:
        verdict = "AMBIGUOUS"

    return verdict, indicators


def run(move: bool = False) -> None:
    if move:
        REAL_DIR.mkdir(exist_ok=True)
        SYNTHETIC_DIR.mkdir(exist_ok=True)

    real_files: list[tuple[Path, list[str]]] = []
    synthetic_files: list[tuple[Path, list[str]]] = []
    ambiguous_files: list[tuple[Path, list[str]]] = []

    for root, dirs, files in os.walk(FIXTURE_ROOT):
        # Skip the destination dirs to avoid double-counting during --move
        dirs[:] = [d for d in dirs if d not in ("agents",)]
        for fname in sorted(files):
            if not fname.endswith(".json"):
                continue
            path = Path(root) / fname
            # Skip files already in synthetic_traces
            if "synthetic_traces" in str(path):
                continue
            verdict, indicators = audit_file(path)
            if verdict == "REAL":
                real_files.append((path, indicators))
            elif verdict == "SYNTHETIC":
                synthetic_files.append((path, indicators))
            else:
                ambiguous_files.append((path, indicators))

    # ── Print report ──────────────────────────────────────────────────────────
    print("═" * 72)
    print("TRAJEX TRACE AUDIT")
    print("═" * 72)

    print(f"\nREAL traces ({len(real_files)}) — live LLM execution evidence:")
    for path, ind in real_files:
        rel = path.relative_to(FIXTURE_ROOT)
        short = ", ".join(ind[:2])
        print(f"  ✓  {str(rel):<50}  {short}")

    print(f"\nSYNTHETIC traces ({len(synthetic_files)}) — hand-constructed:")
    for path, ind in synthetic_files:
        rel = path.relative_to(FIXTURE_ROOT)
        short = next((i for i in ind if "✗" in i or "synthetic" in i.lower() or "OpenAI" in i), ind[0])
        print(f"  ✗  {str(rel):<50}  {short}")

    if ambiguous_files:
        print(f"\nAMBIGUOUS ({len(ambiguous_files)}) — manual review needed:")
        for path, ind in ambiguous_files:
            rel = path.relative_to(FIXTURE_ROOT)
            print(f"  ?  {str(rel):<50}  {' | '.join(ind)}")

    print(f"\nSUMMARY: {len(real_files)} real, {len(synthetic_files)} synthetic, {len(ambiguous_files)} ambiguous")

    if not move:
        print("\nRun with --move to physically separate files into:")
        print(f"  REAL      → {REAL_DIR}")
        print(f"  SYNTHETIC → {SYNTHETIC_DIR}")
        return

    # ── Move files ────────────────────────────────────────────────────────────
    print("\nMoving files...")
    moved = 0

    for path, _ in real_files:
        dest = REAL_DIR / path.name
        if path.resolve() != dest.resolve():
            shutil.move(str(path), str(dest))
            print(f"  REAL      → {path.name}")
            moved += 1

    for path, _ in synthetic_files:
        dest = SYNTHETIC_DIR / path.name
        if path.resolve() != dest.resolve():
            shutil.move(str(path), str(dest))
            print(f"  SYNTHETIC → {path.name}")
            moved += 1

    print(f"\n{moved} files moved. Directories:")
    print(f"  {REAL_DIR}: {len(list(REAL_DIR.glob('*.json')))} files")
    print(f"  {SYNTHETIC_DIR}: {len(list(SYNTHETIC_DIR.glob('*.json')))} files")


if __name__ == "__main__":
    move = "--move" in sys.argv
    run(move=move)
