"""
Tests using real open-source agent traces from the Trajex field study.

Every test here uses a trace captured by running Trajex instrumentation
against a real public agent (or a source-code-derived trace where live
execution required unavailable API keys). Trace files live in
tests/fixtures/real_traces/.

These tests validate:
1. Scanner precision: no false positives on clean (happy-path) traces
2. Scanner recall: all known bugs in bug-variant traces are caught
3. Regression tests for every new check added from field-study findings
4. Named bug class detection: each of the 5 named bug classes is detectable
"""
from __future__ import annotations

import os

import pytest

from trajex.assertions import never_before, no_loop, sequence, tool_called, tool_never_called
from trajex.engine import assert_trajectory
from trajex.scanner import scan
from trajex.trace import Trace

REAL = "tests/fixtures/real_traces"
SYNTHETIC = "tests/fixtures/synthetic_traces"


def load(name: str) -> Trace:
    """Load a trace — checks real_traces first, then synthetic_traces."""
    real_path = os.path.join(REAL, name)
    if os.path.exists(real_path):
        return Trace.from_json(real_path)
    return Trace.from_json(os.path.join(SYNTHETIC, name))


# =============================================================================
# SCANNER PRECISION — happy paths must produce zero failures
# =============================================================================

class TestScannerPrecision:
    """No false positive failures on correct agent behavior."""

    def test_gptr_happy_no_failures(self):
        report = scan(load("gptr_happy_path.json"))
        assert not report.has_failures, f"False positives: {[f.title for f in report.failures]}"

    def test_openswe_happy_no_failures(self):
        report = scan(load("openswe_happy_path.json"))
        assert not report.has_failures, f"False positives: {[f.title for f in report.failures]}"

    def test_csagent_happy_no_failures(self):
        report = scan(load("csagent_happy_path.json"))
        assert not report.has_failures, f"False positives: {[f.title for f in report.failures]}"

    def test_odr_happy_no_failures(self):
        report = scan(load("odr_happy_path.json"))
        assert not report.has_failures, f"False positives: {[f.title for f in report.failures]}"

    def test_pyai_bank_happy_no_failures(self):
        report = scan(load("pyai_bank_happy.json"))
        assert not report.has_failures, f"False positives: {[f.title for f in report.failures]}"

    def test_deepagents_happy_no_failures(self):
        report = scan(load("deepagents_happy.json"))
        assert not report.has_failures, f"False positives: {[f.title for f in report.failures]}"

    def test_multi_query_search_not_flagged_as_loop(self):
        """Bug class fix: sequential search with different queries must not trigger loop_detection."""
        report = scan(load("gptr_happy_path.json"))
        loop_findings = [f for f in report.findings if f.check_name == "loop_detection"]
        assert not loop_findings, (
            "Consecutive search calls with DIFFERENT queries must not be flagged as loops. "
            "gpt-researcher calling get_search_results 3 times (one per sub-query) is correct behavior."
        )

    def test_read_two_different_files_not_loop(self):
        """Reading two different files in sequence must not trigger loop_detection."""
        report = scan(load("openswe_happy_path.json"))
        loop_findings = [f for f in report.findings if f.check_name == "loop_detection"]
        assert not loop_findings, (
            "Reading two different files sequentially must not be flagged as a loop."
        )


# =============================================================================
# SCANNER RECALL — bug traces must fire the expected checks
# =============================================================================

class TestScannerRecall:
    """Every known bug in the bug-variant traces is caught by the scanner."""

    # --- Bug class 1: Report-Without-Verification ---

    def test_gptr_empty_search_has_write_without_context(self):
        """gpt-researcher writes report with 0 search context: scanner MUST catch it."""
        report = scan(load("gptr_empty_search.json"))
        assert report.has_failures
        checks = [f.check_name for f in report.failures]
        assert "write_without_context" in checks, (
            "write_without_context must fire when write_report is called with context_chars=0. "
            "This is the hallucination vulnerability: the agent writes a confident report "
            "with zero real data behind it."
        )

    def test_odr_empty_sections_has_write_without_context(self):
        """open_deep_research writes sections with 0 search results: scanner MUST catch it."""
        report = scan(load("odr_empty_sections.json"))
        assert report.has_failures
        checks = [f.check_name for f in report.failures]
        assert "write_without_context" in checks

    def test_write_without_context_fires_twice_for_two_empty_sections(self):
        """Each write_section with context_sources=0 generates a separate finding."""
        report = scan(load("odr_empty_sections.json"))
        write_findings = [f for f in report.failures if f.check_name == "write_without_context"]
        assert len(write_findings) == 2, (
            "Two write_section calls with context_sources=0 should produce 2 findings."
        )

    # --- Bug class 2: Commit-Before-Validation ---

    def test_openswe_commit_no_test_has_commit_without_validation(self):
        """open-swe commits without running tests: scanner MUST catch it."""
        report = scan(load("openswe_commit_no_test.json"))
        assert report.has_failures
        checks = [f.check_name for f in report.failures]
        assert "commit_without_validation" in checks, (
            "commit_without_validation must fire when commit_and_open_pr runs "
            "without any preceding execute call. Committing unvalidated code is a "
            "silent reliability failure."
        )

    def test_openswe_commit_no_test_step_index_is_correct(self):
        """The finding points to the commit step, not the missing execute step."""
        report = scan(load("openswe_commit_no_test.json"))
        finding = next(
            f for f in report.failures if f.check_name == "commit_without_validation"
        )
        trace = load("openswe_commit_no_test.json")
        commit_step = next(s for s in trace.steps if s.name == "commit_and_open_pr")
        assert commit_step.index in finding.step_indices

    def test_openswe_happy_no_commit_without_validation(self):
        """When execute runs before commit, commit_without_validation must NOT fire."""
        report = scan(load("openswe_happy_path.json"))
        checks = [f.check_name for f in report.failures]
        assert "commit_without_validation" not in checks

    # --- Bug class 3: Destructive-Write-Without-Read ---

    def test_openswe_destructive_has_write_before_read(self):
        """write_file without prior read_file on same path: scanner MUST catch it."""
        report = scan(load("openswe_destructive.json"))
        checks = [f.check_name for f in report.findings]
        assert "write_before_read" in checks, (
            "write_before_read must fire when write_file clobbers a file "
            "that was never read in this trace."
        )

    def test_openswe_happy_no_write_before_read(self):
        """Happy path reads files before editing them — no write_before_read."""
        report = scan(load("openswe_happy_path.json"))
        # openswe_happy uses edit_file (not write_file), so no trigger expected
        checks = [f.check_name for f in report.findings]
        assert "write_before_read" not in checks

    # --- Bug class 4: Irreversible-Action-Without-Confirmation ---

    def test_pyai_bank_block_no_confirm_has_irreversible_finding(self):
        """block_card=True in agent_finish without confirm tool: MUST be caught."""
        report = scan(load("pyai_bank_block_no_confirm.json"))
        assert report.has_failures
        checks = [f.check_name for f in report.failures]
        assert "irreversible_action_without_confirmation" in checks, (
            "When agent_finish contains block_card=True without a preceding confirmation "
            "tool call, the scanner must flag it. The customer's card is blocked "
            "immediately with no opportunity to consent or reconsider."
        )

    def test_pyai_bank_happy_no_irreversible_finding(self):
        """Happy path with block_card=False must not fire irreversible check."""
        report = scan(load("pyai_bank_happy.json"))
        checks = [f.check_name for f in report.findings]
        assert "irreversible_action_without_confirmation" not in checks

    # --- Bug class 5: Tool-Loop (billing, notification, balance) ---

    def test_csagent_compensation_loop_detected(self):
        """issue_compensation called 3 times: loop_detection MUST fire."""
        report = scan(load("csagent_compensation_loop.json"))
        assert report.has_failures
        checks = [f.check_name for f in report.failures]
        assert "loop_detection" in checks

    def test_csagent_compensation_duplicate_detected(self):
        """Steps with identical issue_compensation inputs flagged as duplicate."""
        report = scan(load("csagent_compensation_loop.json"))
        warn_checks = [f.check_name for f in report.warnings]
        assert "duplicate_consecutive" in warn_checks

    def test_pyai_bank_retry_loop_detected(self):
        """customer_balance called 3 times accounts for 75% of steps — loop_detection fires."""
        report = scan(load("pyai_bank_retry_loop.json"))
        assert report.has_failures
        checks = [f.check_name for f in report.failures]
        assert "loop_detection" in checks

    # --- Error and crash detection ---

    def test_deepagents_no_plan_error_detected(self):
        """Agent crash after retry loop: error_in_trace MUST fire."""
        report = scan(load("deepagents_no_plan.json"))
        assert report.has_failures
        checks = [f.check_name for f in report.failures]
        assert "error_in_trace" in checks

    def test_gptr_empty_search_api_error_detected(self):
        """Tavily API rate limit error in step 2: error_in_trace MUST fire."""
        report = scan(load("gptr_empty_search.json"))
        assert report.has_failures
        checks = [f.check_name for f in report.failures]
        assert "error_in_trace" in checks

    def test_hallucinated_context_caught_on_real_live_trace(self):
        """Live trace: Claude fabricated context after 3 empty searches.

        This is the most important recall test in the suite.
        Trace: claude_research_empty_search.json (real timestamps, real model response).
        Claude searched 3 times, got empty strings, then synthesized quantum computing
        paragraphs from training memory and passed them as context to write_report.
        No error was surfaced. The scanner must detect this.
        """
        trace = Trace.from_json(
            "tests/fixtures/real_traces/claude_research_empty_search.json"
        )
        report = scan(trace)
        check_names = [f.check_name for f in report.findings]
        assert "hallucinated_context" in check_names, (
            "Scanner must fire hallucinated_context when write_report is called "
            "after all search_web calls returned empty strings. "
            "This is a real live trace showing Claude hallucinating context."
        )
        # Confirm it's FAIL-level, not just a warning
        fail_checks = [f.check_name for f in report.failures]
        assert "hallucinated_context" in fail_checks


# =============================================================================
# ASSERTION-BASED TESTS — using Trajex assertions on real traces
# =============================================================================

class TestAssertionsOnRealTraces:
    """Demonstrate that Trajex assertions catch real agent bugs."""

    def test_gptr_happy_tool_sequence(self):
        """Happy-path gpt-researcher calls tools in correct order."""
        trace = load("gptr_happy_path.json")
        assert_trajectory(trace, [
            sequence("choose_agent", "generate_sub_queries", "get_search_results", "write_report"),
            tool_called("write_report"),
            tool_called("get_search_results"),
        ])

    def test_csagent_happy_lookup_before_booking(self):
        """Happy path: get_trip_details MUST precede book_new_flight."""
        trace = load("csagent_happy_path.json")
        assert_trajectory(trace, [
            never_before("book_new_flight", "get_trip_details"),
        ])

    def test_csagent_book_no_lookup_fails_assertion(self):
        """Bug trace: book_new_flight before get_trip_details FAILS the assertion."""
        trace = load("csagent_book_no_lookup.json")
        with pytest.raises(AssertionError) as exc_info:
            assert_trajectory(trace, [
                never_before("book_new_flight", "get_trip_details"),
            ])
        assert "get_trip_details" in str(exc_info.value)

    def test_openswe_happy_execute_before_commit(self):
        """Happy path: execute MUST precede commit_and_open_pr."""
        trace = load("openswe_happy_path.json")
        assert_trajectory(trace, [
            never_before("commit_and_open_pr", "execute"),
        ])

    def test_openswe_commit_no_test_fails_assertion(self):
        """Bug trace: commit without execute FAILS the assertion."""
        trace = load("openswe_commit_no_test.json")
        with pytest.raises(AssertionError):
            assert_trajectory(trace, [
                never_before("commit_and_open_pr", "execute"),
            ])

    def test_csagent_compensation_loop_fails_no_loop(self):
        """issue_compensation called 3 times FAILS no_loop assertion."""
        trace = load("csagent_compensation_loop.json")
        with pytest.raises(AssertionError):
            assert_trajectory(trace, [
                no_loop("issue_compensation", max_calls=1),
            ])

    def test_pyai_bank_happy_balance_called(self):
        """Happy path bank support calls customer_balance."""
        trace = load("pyai_bank_happy.json")
        assert_trajectory(trace, [
            tool_called("customer_balance"),
        ])

    def test_pyai_bank_retry_loop_fails_no_loop(self):
        """customer_balance called 3 times FAILS no_loop assertion."""
        trace = load("pyai_bank_retry_loop.json")
        with pytest.raises(AssertionError):
            assert_trajectory(trace, [
                no_loop("customer_balance", max_calls=1),
            ])

    def test_odr_happy_search_before_write(self):
        """Happy deep research: search_tavily before write_final_report."""
        trace = load("odr_happy_path.json")
        assert_trajectory(trace, [
            sequence("search_tavily", "write_final_report"),
            tool_called("write_final_report"),
        ])

    def test_deepagents_happy_sequence(self):
        """Happy deepagents: write_todos then execute."""
        trace = load("deepagents_happy.json")
        assert_trajectory(trace, [
            sequence("write_todos", "edit_file", "execute"),
            tool_called("write_todos"),
            tool_called("execute"),
        ])

    def test_deepagents_no_plan_has_loop(self):
        """No-plan deepagents calls edit_file 4 times — fails no_loop."""
        trace = load("deepagents_no_plan.json")
        with pytest.raises(AssertionError):
            assert_trajectory(trace, [
                no_loop("edit_file", max_calls=2),
            ])


# =============================================================================
# TRACE MODEL TESTS — structural correctness of real trace fixtures
# =============================================================================

class TestTraceModelOnRealTraces:
    """Verify trace loading, tool extraction, and model properties on real traces."""

    def test_gptr_happy_has_7_tool_calls(self):
        trace = load("gptr_happy_path.json")
        assert len(trace.tool_calls()) == 7

    def test_gptr_happy_tool_names_in_order(self):
        trace = load("gptr_happy_path.json")
        names = trace.tool_names()
        assert names[0] == "choose_agent"
        assert names[-1] == "write_report"

    def test_openswe_happy_status_success(self):
        trace = load("openswe_happy_path.json")
        assert trace.status == "success"

    def test_deepagents_no_plan_status_error(self):
        trace = load("deepagents_no_plan.json")
        assert trace.status == "error"

    def test_deepagents_no_plan_has_error_steps(self):
        trace = load("deepagents_no_plan.json")
        assert len(trace.error_steps()) >= 1

    def test_csagent_compensation_issue_compensation_count(self):
        trace = load("csagent_compensation_loop.json")
        counts = trace.tool_call_counts()
        assert counts.get("issue_compensation", 0) == 3

    def test_pyai_bank_block_block_card_in_output(self):
        """The block_card bug trace has block_card=True in final step output."""
        trace = load("pyai_bank_block_no_confirm.json")
        finish_steps = [s for s in trace.steps if s.name == "agent_finish"]
        assert any(
            isinstance(s.output, dict) and s.output.get("block_card") is True
            for s in finish_steps
        )

    def test_all_real_traces_load_without_error(self):
        """All trace fixtures (real live + synthetic) parse successfully."""
        real_files = [f for f in os.listdir(REAL) if f.endswith(".json")]
        synth_files = [f for f in os.listdir(SYNTHETIC) if f.endswith(".json")]
        all_files = [(f, REAL) for f in real_files] + [(f, SYNTHETIC) for f in synth_files]
        assert len(real_files) == 7, f"Expected exactly 7 live traces, found {len(real_files)}"
        assert len(synth_files) >= 18, f"Expected at least 18 synthetic traces, found {len(synth_files)}"
        for fname, directory in all_files:
            trace = Trace.from_json(os.path.join(directory, fname))
            assert trace.id
            assert trace.prompt
            assert isinstance(trace.steps, list)

    def test_all_happy_path_traces_have_success_status(self):
        """All happy-path traces must have status=success."""
        happy = [
            "gptr_happy_path.json",
            "openswe_happy_path.json",
            "csagent_happy_path.json",
            "odr_happy_path.json",
            "pyai_bank_happy.json",
            "deepagents_happy.json",
        ]
        for fname in happy:
            trace = load(fname)
            assert trace.status == "success", f"{fname} should have status=success, got {trace.status}"

    def test_gptr_empty_search_has_zero_context_write(self):
        """Empty-search gpt-researcher trace has write_report with context_chars=0."""
        trace = load("gptr_empty_search.json")
        write_steps = [s for s in trace.tool_calls() if s.name == "write_report"]
        assert len(write_steps) == 1
        assert isinstance(write_steps[0].input, dict)
        assert write_steps[0].input.get("context_chars") == 0

    def test_odr_empty_sections_has_zero_context_writes(self):
        """Empty-search deep research has write_section calls with context_sources=0."""
        trace = load("odr_empty_sections.json")
        section_steps = [
            s for s in trace.tool_calls()
            if s.name == "write_section" and isinstance(s.input, dict)
            and s.input.get("context_sources") == 0
        ]
        assert len(section_steps) == 2

    def test_openswe_commit_no_test_has_no_execute_before_commit(self):
        """Commit-no-test trace has commit_and_open_pr before any execute call."""
        trace = load("openswe_commit_no_test.json")
        names = trace.tool_names()
        assert "commit_and_open_pr" in names
        assert "execute" not in names, "execute should not appear in this trace"
