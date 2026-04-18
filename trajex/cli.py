from __future__ import annotations

import argparse
import json
import sys


def cmd_scan(args: argparse.Namespace) -> int:
    from trajex.trace import Trace
    from trajex.scanner import scan
    from trajex.formatter import format_scan_report

    try:
        trace = Trace.from_json(args.trace_file)
    except FileNotFoundError:
        print(f"Error: file not found: {args.trace_file}", file=sys.stderr)
        return 2
    except (ValueError, KeyError) as exc:
        print(f"Error: invalid trace format: {exc}", file=sys.stderr)
        return 3

    schema = None
    if args.schema:
        try:
            with open(args.schema, encoding="utf-8") as f:
                schema = json.load(f)
        except FileNotFoundError:
            print(f"Error: schema file not found: {args.schema}", file=sys.stderr)
            return 2

    color = not args.no_color
    report = scan(trace, schema=schema)
    output = format_scan_report(report, trace, color=color)
    print(output, end="")
    return 1 if report.has_failures else 0


def cmd_init(args: argparse.Namespace) -> int:
    from trajex.trace import Trace
    from trajex.scanner import scan, generate_test_file

    try:
        trace = Trace.from_json(args.trace_file)
    except FileNotFoundError:
        print(f"Error: file not found: {args.trace_file}", file=sys.stderr)
        return 2
    except (ValueError, KeyError) as exc:
        print(f"Error: invalid trace format: {exc}", file=sys.stderr)
        return 3

    report = scan(trace)
    code = generate_test_file(report, trace_path=args.trace_file)

    out_path = args.out or "test_agent_trajectory.py"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Generated: {out_path}")
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    from trajex.trace import Trace
    from trajex.viewer import write_viewer

    try:
        trace = Trace.from_json(args.trace_file)
    except FileNotFoundError:
        print(f"Error: file not found: {args.trace_file}", file=sys.stderr)
        return 2
    except (ValueError, KeyError) as exc:
        print(f"Error: invalid trace format: {exc}", file=sys.stderr)
        return 3

    out = getattr(args, "out", None)
    path = write_viewer(trace, path=out)
    print(path)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """CI check. Without --baseline: runs scanner (exit 1 on failures).
    With --baseline: runs anomaly detection (exit 1=HIGH, 2=MEDIUM)."""
    from trajex.trace import Trace

    try:
        trace = Trace.from_json(args.trace_file)
    except FileNotFoundError:
        print(f"Error: file not found: {args.trace_file}", file=sys.stderr)
        return 3
    except (ValueError, KeyError) as exc:
        print(f"Error: invalid trace format: {exc}", file=sys.stderr)
        return 3

    baseline_ref = getattr(args, "baseline", None)

    if baseline_ref is None:
        # Legacy scanner CI mode
        schema = None
        if getattr(args, "schema", None):
            try:
                with open(args.schema, encoding="utf-8") as f:
                    schema = json.load(f)
            except FileNotFoundError:
                print(f"Error: schema file not found: {args.schema}", file=sys.stderr)
                return 3
        from trajex.scanner import scan
        report = scan(trace, schema=schema)
        if report.has_failures:
            for finding in report.failures:
                print(f"FAIL  {finding.title}", file=sys.stderr)
            return 1
        return 0

    # Anomaly-detection mode
    from trajex.store import TraceStore
    from trajex.anomaly import detect_anomalies

    store = TraceStore()
    baseline = store.find_baseline(baseline_ref)
    if baseline is None:
        try:
            baseline = store.load_baseline(baseline_ref)
        except KeyError:
            print(f"Error: baseline not found: {baseline_ref!r}", file=sys.stderr)
            return 3

    findings = detect_anomalies(trace, baseline)
    if not findings:
        print("No anomalies detected.")
        return 0

    _RED = "\033[91m"
    _YLW = "\033[93m"
    _RST = "\033[0m"
    has_high = False
    has_medium = False
    for f in findings:
        color = _RED if f.severity == "HIGH" else (_YLW if f.severity == "MEDIUM" else "")
        print(f"{color}[{f.severity}]{_RST}  {f.title}")
        print(f"       {f.detail}")
        print(f"       Expected: {f.expected}")
        print(f"       Observed: {f.observed}")
        print(f"       Confidence: {f.confidence:.0%}")
        print()
        if f.severity == "HIGH":
            has_high = True
        elif f.severity == "MEDIUM":
            has_medium = True

    if has_high:
        return 1
    if has_medium:
        return 2
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    from trajex.trace import Trace

    try:
        trace = Trace.from_json(args.trace_file)
    except FileNotFoundError:
        print(f"Error: file not found: {args.trace_file}", file=sys.stderr)
        return 2
    except (ValueError, KeyError) as exc:
        print(f"Error: invalid trace format: {exc}", file=sys.stderr)
        return 3

    dur = trace.total_duration_ms()
    dur_str = f"{dur:.0f}ms" if dur is not None else "unknown"
    tools_str = ", ".join(trace.unique_tools_called()) or "(none)"

    print(f"Trace ID:      {trace.id}")
    print(f"Prompt:        {trace.prompt[:80]}")
    print(f"Status:        {trace.status}")
    print(f"Steps:         {len(trace.steps)} total  ({trace.total_tool_calls()} tool calls)")
    print(f"Tools called:  {tools_str}")
    print(f"Duration:      {dur_str}")
    print(f"Framework:     {trace.metadata.get('framework', 'unknown')}")
    print(f"Model:         {trace.metadata.get('model', 'unknown')}")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    from trajex.trace import Trace
    from trajex.diff import diff_traces, format_diff

    color = not getattr(args, "no_color", False)
    traces = []
    for path in [args.before, args.after]:
        try:
            traces.append(Trace.from_json(path))
        except FileNotFoundError:
            print(f"Error: file not found: {path}", file=sys.stderr)
            return 2
        except (ValueError, KeyError) as exc:
            print(f"Error: invalid trace format ({path}): {exc}", file=sys.stderr)
            return 3

    before, after = traces
    diff = diff_traces(before, after)
    print(format_diff(diff, color=color), end="")
    return 1 if diff.has_regressions else 0


def cmd_learn(args: argparse.Namespace) -> int:
    from pathlib import Path
    from trajex.trace import Trace
    from trajex.baseline import BaselineModel

    traces_dir = Path(args.traces_dir)
    if not traces_dir.is_dir():
        print(f"Error: directory not found: {traces_dir}", file=sys.stderr)
        return 2

    trace_files = sorted(traces_dir.glob("*.json"))
    if not trace_files:
        print(f"Error: no .json files found in {traces_dir}", file=sys.stderr)
        return 2

    traces = []
    for f in trace_files:
        try:
            traces.append(Trace.from_json(str(f)))
        except Exception as exc:
            print(f"  Warning: skipping {f.name} -- {exc}")

    if not traces:
        print("Error: no valid traces loaded.", file=sys.stderr)
        return 2

    name = getattr(args, "name", None) or None
    description = getattr(args, "description", None) or ""
    baseline = BaselineModel.learn(traces, name=name, description=description)
    baseline.save()

    print(f"Learned baseline '{baseline.name}' from {baseline.trace_count} traces.")
    print(f"ID: {baseline.id}")
    print(baseline.summary())
    return 0


def cmd_baseline(args: argparse.Namespace) -> int:
    sub = getattr(args, "baseline_cmd", None)
    if sub == "list":
        return _baseline_list()
    if sub == "delete":
        return _baseline_delete(args.id_or_name)
    print("Usage: trajex baseline {list|delete <id_or_name>}")
    return 1


def _baseline_list() -> int:
    from trajex.store import TraceStore
    store = TraceStore()
    rows = store.list_baselines()
    if not rows:
        print("No baselines saved. Run: trajex learn <dir>")
        return 0
    print(f"{'ID':10}  {'Name':30}  {'Traces':7}  {'Created':20}  Agent")
    print("-" * 80)
    for r in rows:
        bid = r["id"][:8]
        agent = r.get("agent_name") or "-"
        created = (r["created_at"] or "")[:19]
        print(f"{bid:10}  {r['name']:30}  {r['trace_count']:7}  {created:20}  {agent}")
    return 0


def _baseline_delete(id_or_name: str) -> int:
    from trajex.store import TraceStore
    store = TraceStore()

    # Try by name first, then by id prefix
    baseline = store.find_baseline(id_or_name)
    if baseline is None:
        rows = store.list_baselines()
        matches = [r for r in rows if r["id"].startswith(id_or_name)]
        if not matches:
            print(f"Error: baseline not found: {id_or_name!r}", file=sys.stderr)
            return 1
        if len(matches) > 1:
            print(f"Error: ambiguous id prefix '{id_or_name}' matches {len(matches)} baselines")
            return 1
        baseline_id = matches[0]["id"]
        baseline_name = matches[0]["name"]
    else:
        baseline_id = baseline.id
        baseline_name = baseline.name

    answer = input(f"Delete baseline '{baseline_name}'? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled.")
        return 0
    store.delete_baseline(baseline_id)
    print(f"Deleted baseline '{baseline_name}'.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="trajex",
        description="The open format for AI agent execution traces",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan a trace for issues")
    p_scan.add_argument("trace_file", metavar="trace.json")
    p_scan.add_argument("--schema", metavar="schema.json", default=None)
    p_scan.add_argument("--no-color", action="store_true", default=False)

    # init
    p_init = subparsers.add_parser("init", help="Generate a test file from a trace")
    p_init.add_argument("trace_file", metavar="trace.json")
    p_init.add_argument("--out", metavar="test_file.py", default=None)

    # view
    p_view = subparsers.add_parser(
        "view",
        help="Generate a self-contained HTML viewer for a trace (prints path to stdout)",
    )
    p_view.add_argument("trace_file", metavar="trace.json")
    p_view.add_argument("--out", metavar="output.html", default=None)

    # check
    p_check = subparsers.add_parser(
        "check",
        help="CI mode: scanner check, or anomaly check against a baseline",
    )
    p_check.add_argument("trace_file", metavar="trace.json")
    p_check.add_argument("--schema", metavar="schema.json", default=None)
    p_check.add_argument(
        "--baseline", metavar="id_or_name", default=None,
        help="Check against a saved baseline (anomaly detection mode)",
    )

    # info
    p_info = subparsers.add_parser("info", help="Print trace summary")
    p_info.add_argument("trace_file", metavar="trace.json")

    # diff
    p_diff = subparsers.add_parser(
        "diff",
        help="Compare two traces for regressions",
    )
    p_diff.add_argument("before", metavar="before.json")
    p_diff.add_argument("after", metavar="after.json")
    p_diff.add_argument("--no-color", action="store_true", default=False)

    # learn
    p_learn = subparsers.add_parser(
        "learn",
        help="Learn a behavioral baseline from a directory of passing traces",
    )
    p_learn.add_argument("traces_dir", metavar="traces_dir")
    p_learn.add_argument("--name", metavar="name", default=None)
    p_learn.add_argument("--description", metavar="description", default="")

    # baseline
    p_baseline = subparsers.add_parser("baseline", help="Manage saved baselines")
    baseline_sub = p_baseline.add_subparsers(dest="baseline_cmd", metavar="SUBCOMMAND")
    baseline_sub.add_parser("list", help="List all saved baselines")
    p_bdel = baseline_sub.add_parser("delete", help="Delete a baseline by id or name")
    p_bdel.add_argument("id_or_name", metavar="id_or_name")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "scan": cmd_scan,
        "init": cmd_init,
        "view": cmd_view,
        "check": cmd_check,
        "info": cmd_info,
        "diff": cmd_diff,
        "learn": cmd_learn,
        "baseline": cmd_baseline,
    }
    code = dispatch[args.command](args)
    sys.exit(code)


if __name__ == "__main__":
    main()
