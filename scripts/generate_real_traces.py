"""
Generate accurate mock traces for 6 real open-source agents.

Source-derived methodology:
- Tool names match actual function names from each repo's source code
- Control flows reflect documented + observed agent behavior
- Bugs represented are real: verified by reading source code
- Timestamps are realistic relative to agent complexity

Each trace is labeled with its agent and scenario.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

OUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "tests", "fixtures", "real_traces"
)


def dt(base: datetime, offset_ms: int) -> str:
    return (base + timedelta(milliseconds=offset_ms)).isoformat()


def step(
    index: int,
    step_type: str,
    name: str,
    inp=None,
    out=None,
    error: str | None = None,
    reasoning: str | None = None,
    started_ms: int = 0,
    ended_ms: int = 0,
    base: datetime | None = None,
    metadata: dict | None = None,
) -> dict:
    b = base or datetime(2026, 4, 18, 10, 0, 0, tzinfo=timezone.utc)
    return {
        "index": index,
        "step_type": step_type,
        "name": name,
        "input": inp,
        "output": out,
        "error": error,
        "reasoning": reasoning,
        "started_at": dt(b, started_ms),
        "ended_at": dt(b, ended_ms),
        "duration_ms": float(ended_ms - started_ms),
        "metadata": metadata or {},
    }


def trace(
    prompt: str,
    steps: list[dict],
    status: str = "success",
    framework: str = "langchain",
    model: str = "gpt-4o",
    agent_name: str | None = None,
    total_ms: int = 5000,
    base: datetime | None = None,
) -> dict:
    b = base or datetime(2026, 4, 18, 10, 0, 0, tzinfo=timezone.utc)
    return {
        "trajex_version": "1",
        "id": str(uuid.uuid4()),
        "prompt": prompt,
        "final_output": None,
        "status": status,
        "started_at": b.isoformat(),
        "ended_at": dt(b, total_ms),
        "metadata": {
            "framework": framework,
            "model": model,
            "agent_name": agent_name,
            "tags": [],
            "custom": {},
        },
        "steps": steps,
    }


def write(filename: str, t: dict) -> None:
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(t, f, indent=2)
    print(f"  wrote {filename}  ({len(t['steps'])} steps, status={t['status']})")


# =============================================================================
# AGENT 1: gpt-researcher (assafelovic/gpt-researcher)
# 26.5k stars | LangChain+LangGraph | Web research
# Tool sequence: choose_agent → generate_sub_queries → get_search_results(×N)
#   → scrape_urls → write_report
# Source: gpt_researcher/agent.py — conduct_research() calls write_report()
#   unconditionally with no validation of context size.
# =============================================================================
print("Agent 1: gpt-researcher")

B = datetime(2026, 4, 18, 10, 0, 0, tzinfo=timezone.utc)

# Happy path: research "quantum computing cryptography impact"
gptr_happy = trace(
    prompt="Research the impact of quantum computing on current cryptographic standards",
    framework="langchain",
    model="gpt-4o",
    agent_name="GPTResearcher",
    total_ms=42000,
    base=B,
    steps=[
        step(0, "tool_call", "choose_agent",
             inp={"query": "impact of quantum computing on cryptographic standards"},
             out={"agent": "Research Agent", "role": "cryptography expert"},
             reasoning="Selecting agent type based on query domain",
             started_ms=0, ended_ms=1200, base=B),
        step(1, "tool_call", "generate_sub_queries",
             inp={"query": "impact of quantum computing on cryptographic standards", "max_iterations": 3},
             out={"sub_queries": [
                 "quantum computing threat to RSA encryption",
                 "NIST post-quantum cryptography standards 2024",
                 "timeline for quantum computers breaking encryption",
             ]},
             reasoning="Breaking main query into focused sub-queries",
             started_ms=1200, ended_ms=3800, base=B),
        step(2, "tool_call", "get_search_results",
             inp={"query": "quantum computing threat to RSA encryption"},
             out={"results": [
                 {"url": "https://nist.gov/pqcrypto", "title": "NIST PQC", "snippet": "..."},
                 {"url": "https://arxiv.org/abs/quantum-rsa", "title": "Quantum RSA", "snippet": "..."},
                 {"url": "https://ibm.com/quantum-safe", "title": "IBM Quantum Safe", "snippet": "..."},
             ], "count": 3},
             started_ms=3800, ended_ms=6100, base=B),
        step(3, "tool_call", "get_search_results",
             inp={"query": "NIST post-quantum cryptography standards 2024"},
             out={"results": [
                 {"url": "https://nist.gov/fips203", "title": "FIPS 203", "snippet": "..."},
                 {"url": "https://csrc.nist.gov/projects/post-quantum", "title": "CSRC PQC", "snippet": "..."},
             ], "count": 2},
             started_ms=6100, ended_ms=8200, base=B),
        step(4, "tool_call", "get_search_results",
             inp={"query": "timeline for quantum computers breaking encryption"},
             out={"results": [
                 {"url": "https://nature.com/quantum-timeline", "title": "Nature: Quantum Timeline", "snippet": "..."},
                 {"url": "https://mckinsey.com/quantum-risk", "title": "McKinsey Quantum Risk", "snippet": "..."},
                 {"url": "https://research.ibm.com/2023/roadmap", "title": "IBM Roadmap", "snippet": "..."},
             ], "count": 3},
             started_ms=8200, ended_ms=10500, base=B),
        step(5, "tool_call", "scrape_urls",
             inp={"urls": ["https://nist.gov/pqcrypto", "https://nist.gov/fips203",
                           "https://nature.com/quantum-timeline", "https://ibm.com/quantum-safe",
                           "https://csrc.nist.gov/projects/post-quantum"]},
             out={"scraped": 5, "failed": 0,
                  "content_chars": 84200,
                  "message": "Scraped 5 URLs successfully"},
             started_ms=10500, ended_ms=28000, base=B),
        step(6, "tool_call", "write_report",
             inp={"context_chars": 84200, "report_type": "research_report"},
             out={"report_length": 3420, "sections": 6,
                  "report_preview": "# Quantum Computing and Cryptographic Standards\n\n## Executive Summary..."},
             reasoning="Generating final research report from scraped context",
             started_ms=28000, ended_ms=42000, base=B),
        step(7, "agent_finish", "agent_finish",
             out={"report_length": 3420},
             started_ms=42000, ended_ms=42100, base=B),
    ],
)
write("gptr_happy_path.json", gptr_happy)

# EDGE CASE BUG: Search API fails, returns 0 results — write_report called anyway
# Source-verified: generate_report() has NO guard checking context size before writing.
# The agent writes the report with empty context, hallucinating content.
gptr_empty_search = trace(
    prompt="Research the latest advances in neuromorphic chip architecture from last week",
    framework="langchain",
    model="gpt-4o",
    agent_name="GPTResearcher",
    total_ms=18000,
    base=B,
    status="success",  # agent reports success but output is hallucinated
    steps=[
        step(0, "tool_call", "choose_agent",
             inp={"query": "neuromorphic chip architecture advances last week"},
             out={"agent": "Research Agent", "role": "hardware engineer"},
             started_ms=0, ended_ms=1100, base=B),
        step(1, "tool_call", "generate_sub_queries",
             inp={"query": "neuromorphic chip architecture advances last week", "max_iterations": 3},
             out={"sub_queries": [
                 "neuromorphic computing chips 2026",
                 "Intel Loihi neuromorphic 2026",
                 "IBM neuromorphic chip recent papers",
             ]},
             started_ms=1100, ended_ms=3200, base=B),
        step(2, "tool_call", "get_search_results",
             inp={"query": "neuromorphic computing chips 2026"},
             out={"results": [], "count": 0, "error": "Rate limit exceeded on Tavily API"},
             error="TavilyAPIError: rate_limit_exceeded",
             started_ms=3200, ended_ms=4800, base=B),
        step(3, "tool_call", "get_search_results",
             inp={"query": "Intel Loihi neuromorphic 2026"},
             out={"results": [], "count": 0},
             started_ms=4800, ended_ms=5900, base=B),
        step(4, "tool_call", "get_search_results",
             inp={"query": "IBM neuromorphic chip recent papers"},
             out={"results": [], "count": 0},
             started_ms=5900, ended_ms=7000, base=B),
        step(5, "tool_call", "scrape_urls",
             inp={"urls": []},
             out={"scraped": 0, "failed": 0, "content_chars": 0},
             started_ms=7000, ended_ms=7100, base=B),
        # BUG: write_report called with context_chars=0. No guard. Produces hallucinated report.
        step(6, "tool_call", "write_report",
             inp={"context_chars": 0, "report_type": "research_report"},
             out={"report_length": 2100, "sections": 4,
                  "report_preview": "# Recent Advances in Neuromorphic Chip Architecture\n\nNeuromorphic computing..."},
             reasoning="Generating report from accumulated context",
             started_ms=7100, ended_ms=18000, base=B),
        step(7, "agent_finish", "agent_finish",
             out={"report_length": 2100},
             started_ms=18000, ended_ms=18100, base=B),
    ],
)
write("gptr_empty_search.json", gptr_empty_search)

# STRESS: excessive sub-queries, search called 7 times, token budget blown
gptr_retry_loop = trace(
    prompt="Give me a comprehensive analysis of every AI paper published in 2025",
    framework="langchain",
    model="gpt-4o",
    agent_name="GPTResearcher",
    total_ms=180000,
    base=B,
    steps=[
        step(0, "tool_call", "choose_agent",
             inp={"query": "comprehensive analysis every AI paper 2025"},
             out={"agent": "Research Agent", "role": "AI researcher"},
             started_ms=0, ended_ms=1200, base=B),
        step(1, "tool_call", "generate_sub_queries",
             inp={"query": "comprehensive analysis every AI paper 2025", "max_iterations": 3},
             out={"sub_queries": [
                 "AI research papers 2025 NeurIPS", "AI research papers 2025 ICML",
                 "AI research papers 2025 ICLR", "AI research papers 2025 ACL",
                 "AI research papers 2025 CVPR", "AI research papers 2025 AAAI",
                 "AI research papers 2025 overview",
             ]},
             reasoning="Query too broad - generating maximum sub-queries",
             started_ms=1200, ended_ms=4800, base=B),
        step(2, "tool_call", "get_search_results",
             inp={"query": "AI research papers 2025 NeurIPS"},
             out={"results": [{"url": "https://neurips.cc", "title": "NeurIPS 2025", "snippet": "..."}], "count": 10},
             started_ms=4800, ended_ms=7200, base=B),
        step(3, "tool_call", "get_search_results",
             inp={"query": "AI research papers 2025 ICML"},
             out={"results": [{"url": "https://icml.cc", "title": "ICML 2025", "snippet": "..."}], "count": 10},
             started_ms=7200, ended_ms=9600, base=B),
        step(4, "tool_call", "get_search_results",
             inp={"query": "AI research papers 2025 ICLR"},
             out={"results": [{"url": "https://iclr.cc", "title": "ICLR 2025", "snippet": "..."}], "count": 10},
             started_ms=9600, ended_ms=12000, base=B),
        step(5, "tool_call", "get_search_results",
             inp={"query": "AI research papers 2025 ACL"},
             out={"results": [{"url": "https://aclweb.org", "title": "ACL 2025", "snippet": "..."}], "count": 10},
             started_ms=12000, ended_ms=14400, base=B),
        step(6, "tool_call", "get_search_results",
             inp={"query": "AI research papers 2025 CVPR"},
             out={"results": [{"url": "https://cvpr.thecvf.com", "title": "CVPR 2025", "snippet": "..."}], "count": 10},
             started_ms=14400, ended_ms=16800, base=B),
        step(7, "tool_call", "get_search_results",
             inp={"query": "AI research papers 2025 AAAI"},
             out={"results": [{"url": "https://aaai.org", "title": "AAAI 2025", "snippet": "..."}], "count": 10},
             started_ms=16800, ended_ms=19200, base=B),
        step(8, "tool_call", "get_search_results",
             inp={"query": "AI research papers 2025 overview"},
             out={"results": [{"url": "https://arxiv.org/ai-2025", "title": "ArXiv AI 2025", "snippet": "..."}], "count": 10},
             started_ms=19200, ended_ms=21600, base=B),
        step(9, "tool_call", "scrape_urls",
             inp={"urls": ["https://neurips.cc", "https://icml.cc", "https://iclr.cc",
                           "https://aclweb.org", "https://cvpr.thecvf.com",
                           "https://aaai.org", "https://arxiv.org/ai-2025"]},
             out={"scraped": 7, "failed": 0, "content_chars": 245000},
             started_ms=21600, ended_ms=80000, base=B),
        step(10, "tool_call", "write_report",
             inp={"context_chars": 245000, "report_type": "research_report"},
             out={"report_length": 8500, "sections": 12},
             started_ms=80000, ended_ms=180000, base=B),
        step(11, "agent_finish", "agent_finish",
             out={"report_length": 8500},
             started_ms=180000, ended_ms=180100, base=B),
    ],
)
write("gptr_retry_loop.json", gptr_retry_loop)


# =============================================================================
# AGENT 2: open-swe (langchain-ai/open-swe)
# 9.6k stars | LangGraph | Coding agent (SWE-bench style)
# Tool sequence: ls/glob/grep → read_file → edit_file → execute → commit_and_open_pr
# Bug: commit_and_open_pr called WITHOUT preceding execute (test) step.
#   Source: system prompt says to run tests before committing (a SHOULD, not enforced).
# =============================================================================
print("Agent 2: open-swe")

B2 = datetime(2026, 4, 18, 11, 0, 0, tzinfo=timezone.utc)

openswe_happy = trace(
    prompt="Fix the failing test in test_auth.py — the login function doesn't handle empty password",
    framework="langgraph",
    model="claude-sonnet-4-6",
    agent_name="OpenSWE",
    total_ms=95000,
    base=B2,
    steps=[
        step(0, "tool_call", "write_todos",
             inp={"todos": ["Locate login function", "Identify empty password bug",
                            "Write fix", "Run tests", "Commit fix"]},
             out={"todos_written": 5},
             reasoning="Creating task plan before starting",
             started_ms=0, ended_ms=1500, base=B2),
        step(1, "tool_call", "ls",
             inp={"path": "."},
             out={"entries": ["src/", "tests/", "requirements.txt", "setup.py", ".git/"]},
             started_ms=1500, ended_ms=2200, base=B2),
        step(2, "tool_call", "glob",
             inp={"pattern": "src/**/*.py"},
             out={"matches": ["src/auth/login.py", "src/auth/__init__.py", "src/utils.py"]},
             started_ms=2200, ended_ms=2900, base=B2),
        step(3, "tool_call", "read_file",
             inp={"path": "tests/test_auth.py"},
             out={"content": "def test_login_empty_password():\n    result = login('user', '')\n    assert result == {'error': 'Password required'}", "lines": 28},
             started_ms=2900, ended_ms=3800, base=B2),
        step(4, "tool_call", "read_file",
             inp={"path": "src/auth/login.py"},
             out={"content": "def login(username, password):\n    if not username:\n        return {'error': 'Username required'}\n    return auth_db.verify(username, password)", "lines": 42},
             started_ms=3800, ended_ms=4900, base=B2),
        step(5, "tool_call", "edit_file",
             inp={"path": "src/auth/login.py", "operation": "insert_after",
                  "target": "if not username:",
                  "content": "    if not password:\n        return {'error': 'Password required'}"},
             out={"success": True, "lines_changed": 2},
             reasoning="Adding empty password check",
             started_ms=4900, ended_ms=6200, base=B2),
        step(6, "tool_call", "execute",
             inp={"command": "python -m pytest tests/test_auth.py -v"},
             out={"stdout": "test_login_empty_password PASSED\ntest_login_valid PASSED\n2 passed in 0.34s",
                  "returncode": 0},
             started_ms=6200, ended_ms=12000, base=B2),
        step(7, "tool_call", "commit_and_open_pr",
             inp={"message": "Fix: handle empty password in login()",
                  "branch": "fix/empty-password-auth",
                  "files": ["src/auth/login.py"]},
             out={"pr_url": "https://github.com/org/repo/pull/142", "commit": "a3f9b1c"},
             started_ms=12000, ended_ms=95000, base=B2),
        step(8, "agent_finish", "agent_finish",
             out={"pr_url": "https://github.com/org/repo/pull/142"},
             started_ms=95000, ended_ms=95100, base=B2),
    ],
)
write("openswe_happy_path.json", openswe_happy)

# BUG TRACE: commits without running execute (tests)
# This is the core bug: commit_and_open_pr before execute.
# Happens when the agent is given a "simple" change and skips test step.
openswe_commit_no_test = trace(
    prompt="Add a missing docstring to the DatabaseConnector class",
    framework="langgraph",
    model="claude-sonnet-4-6",
    agent_name="OpenSWE",
    total_ms=45000,
    base=B2,
    steps=[
        step(0, "tool_call", "ls",
             inp={"path": "."},
             out={"entries": ["src/", "tests/", "requirements.txt"]},
             started_ms=0, ended_ms=800, base=B2),
        step(1, "tool_call", "glob",
             inp={"pattern": "src/**/*.py"},
             out={"matches": ["src/db/connector.py", "src/db/__init__.py"]},
             started_ms=800, ended_ms=1500, base=B2),
        step(2, "tool_call", "read_file",
             inp={"path": "src/db/connector.py"},
             out={"content": "class DatabaseConnector:\n    def __init__(self, host, port):\n        self.host = host\n        self.port = port", "lines": 87},
             started_ms=1500, ended_ms=2800, base=B2),
        step(3, "tool_call", "edit_file",
             inp={"path": "src/db/connector.py", "operation": "insert_after",
                  "target": "class DatabaseConnector:",
                  "content": '    """Manages database connections with connection pooling and retry logic."""'},
             out={"success": True, "lines_changed": 1},
             reasoning="Adding docstring to class",
             started_ms=2800, ended_ms=4100, base=B2),
        # BUG: commit_and_open_pr without execute. No test run.
        # In practice this can break the codebase if the docstring
        # accidentally introduces a syntax error or import issue.
        step(4, "tool_call", "commit_and_open_pr",
             inp={"message": "docs: add docstring to DatabaseConnector",
                  "branch": "docs/database-connector-docstring",
                  "files": ["src/db/connector.py"]},
             out={"pr_url": "https://github.com/org/repo/pull/143", "commit": "b7c2d4e"},
             reasoning="Change is documentation-only, skipping test run",
             started_ms=4100, ended_ms=45000, base=B2),
        step(5, "agent_finish", "agent_finish",
             out={"pr_url": "https://github.com/org/repo/pull/143"},
             started_ms=45000, ended_ms=45100, base=B2),
    ],
)
write("openswe_commit_no_test.json", openswe_commit_no_test)

# DESTRUCTIVE: agent writes to a critical file without reading it first
openswe_destructive = trace(
    prompt="Update the database configuration to use the new production credentials",
    framework="langgraph",
    model="claude-sonnet-4-6",
    agent_name="OpenSWE",
    total_ms=38000,
    base=B2,
    steps=[
        step(0, "tool_call", "glob",
             inp={"pattern": "**/*config*"},
             out={"matches": ["config/database.py", "config/app.py", "config/settings.json"]},
             started_ms=0, ended_ms=1200, base=B2),
        # BUG: writes file without reading it first — clobbers existing content
        step(1, "tool_call", "write_file",
             inp={"path": "config/database.py",
                  "content": "DATABASE_URL = 'postgresql://prod_user:prod_pass@prod-db.internal:5432/main'"},
             out={"success": True, "bytes_written": 72},
             reasoning="Writing new production credentials",
             started_ms=1200, ended_ms=2800, base=B2),
        step(2, "tool_call", "execute",
             inp={"command": "python -c 'from config.database import DATABASE_URL; print(DATABASE_URL)'"},
             out={"stdout": "postgresql://prod_user:prod_pass@prod-db.internal:5432/main", "returncode": 0},
             started_ms=2800, ended_ms=5000, base=B2),
        step(3, "tool_call", "commit_and_open_pr",
             inp={"message": "config: update database URL to production",
                  "branch": "config/prod-db-credentials",
                  "files": ["config/database.py"]},
             out={"pr_url": "https://github.com/org/repo/pull/144", "commit": "c8d3e5f"},
             started_ms=5000, ended_ms=38000, base=B2),
        step(4, "agent_finish", "agent_finish",
             out={"pr_url": "https://github.com/org/repo/pull/144"},
             started_ms=38000, ended_ms=38100, base=B2),
    ],
)
write("openswe_destructive.json", openswe_destructive)


# =============================================================================
# AGENT 3: openai-cs-agents-demo (openai/openai-cs-agents-demo)
# 6k stars | OpenAI Agents SDK | Customer service multi-agent
# Tool sequence: triage → get_trip_details → action tools
# Bug: action tools (book_new_flight, issue_compensation) callable WITHOUT
#   get_trip_details first. Verified: all tools exposed to all agents.
# =============================================================================
print("Agent 3: openai-cs-agents-demo")

B3 = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)

csagent_happy = trace(
    prompt="I need to change my flight from New York to London, I have a booking reference AA4821",
    framework="openai_agents",
    model="gpt-4o",
    agent_name="FlightCSAgent",
    total_ms=12000,
    base=B3,
    steps=[
        step(0, "tool_call", "get_trip_details",
             inp={"booking_reference": "AA4821"},
             out={"booking_ref": "AA4821", "passenger": "John Smith",
                  "origin": "JFK", "destination": "LHR",
                  "departure": "2026-05-15T08:00:00Z", "flight_number": "AA101",
                  "status": "confirmed"},
             reasoning="Retrieving current booking details before making any changes",
             started_ms=0, ended_ms=800, base=B3),
        step(1, "tool_call", "get_matching_flights",
             inp={"origin": "JFK", "destination": "LHR",
                  "date": "2026-05-16", "passenger_class": "economy"},
             out={"flights": [
                 {"flight": "AA103", "departure": "2026-05-16T10:00:00Z", "seats": 12},
                 {"flight": "AA107", "departure": "2026-05-16T18:00:00Z", "seats": 8},
             ]},
             started_ms=800, ended_ms=2200, base=B3),
        step(2, "tool_call", "book_new_flight",
             inp={"booking_ref": "AA4821", "new_flight": "AA103",
                  "departure": "2026-05-16T10:00:00Z"},
             out={"success": True, "new_booking_ref": "AA4821-R",
                  "confirmation": "Flight changed to AA103 on May 16"},
             started_ms=2200, ended_ms=4800, base=B3),
        step(3, "agent_finish", "agent_finish",
             out={"confirmation": "Flight changed to AA103 on May 16"},
             started_ms=4800, ended_ms=12000, base=B3),
    ],
)
write("csagent_happy_path.json", csagent_happy)

# BUG TRACE: book_new_flight called WITHOUT get_trip_details
# Happens when customer says "just rebook me on the next flight" and the
# Booking agent (not Triage) handles the request directly.
# Source verified: Booking & Cancellation Agent has book_new_flight in its tools
# without requiring get_trip_details first.
csagent_book_no_lookup = trace(
    prompt="Just put me on the next available flight to London, booking AA4821",
    framework="openai_agents",
    model="gpt-4o",
    agent_name="FlightCSAgent",
    total_ms=8000,
    status="success",  # appears successful but booking may fail or duplicate
    base=B3,
    steps=[
        step(0, "tool_call", "get_matching_flights",
             inp={"origin": "JFK", "destination": "LHR",
                  "date": "2026-04-18", "passenger_class": "economy"},
             out={"flights": [
                 {"flight": "AA201", "departure": "2026-04-18T16:00:00Z", "seats": 3},
             ]},
             reasoning="Finding next available flight",
             started_ms=0, ended_ms=1800, base=B3),
        # BUG: book_new_flight called without verifying AA4821 exists or is modifiable
        step(1, "tool_call", "book_new_flight",
             inp={"booking_ref": "AA4821", "new_flight": "AA201",
                  "departure": "2026-04-18T16:00:00Z"},
             out={"success": True, "new_booking_ref": "AA4821-R2",
                  "confirmation": "Flight rebooked to AA201"},
             reasoning="Booking next available flight as requested",
             started_ms=1800, ended_ms=4200, base=B3),
        step(2, "agent_finish", "agent_finish",
             out={"confirmation": "Flight rebooked to AA201"},
             started_ms=4200, ended_ms=8000, base=B3),
    ],
)
write("csagent_book_no_lookup.json", csagent_book_no_lookup)

# STRESS: issue_compensation called 3 times for same disruption
csagent_compensation_loop = trace(
    prompt="My flight was cancelled and I want compensation for my cancelled flight AA4821",
    framework="openai_agents",
    model="gpt-4o",
    agent_name="FlightCSAgent",
    total_ms=25000,
    base=B3,
    steps=[
        step(0, "tool_call", "get_trip_details",
             inp={"booking_reference": "AA4821"},
             out={"booking_ref": "AA4821", "status": "cancelled",
                  "cancellation_reason": "weather", "passenger": "John Smith"},
             started_ms=0, ended_ms=900, base=B3),
        step(1, "tool_call", "issue_compensation",
             inp={"booking_ref": "AA4821", "reason": "flight_cancellation",
                  "amount": 250, "type": "travel_credit"},
             out={"case_id": "COMP-001", "status": "created", "amount": 250},
             reasoning="Creating compensation case for cancelled flight",
             started_ms=900, ended_ms=3500, base=B3),
        # Loop: agent calls issue_compensation again because it forgot it already did
        step(2, "tool_call", "issue_compensation",
             inp={"booking_ref": "AA4821", "reason": "flight_cancellation",
                  "amount": 250, "type": "travel_credit"},
             out={"case_id": "COMP-002", "status": "created", "amount": 250,
                  "warning": "Duplicate compensation detected"},
             reasoning="Confirming compensation was issued",
             started_ms=3500, ended_ms=6200, base=B3),
        step(3, "tool_call", "issue_compensation",
             inp={"booking_ref": "AA4821", "reason": "inconvenience",
                  "amount": 50, "type": "travel_credit"},
             out={"case_id": "COMP-003", "status": "created", "amount": 50},
             reasoning="Additional inconvenience compensation",
             started_ms=6200, ended_ms=9000, base=B3),
        step(4, "agent_finish", "agent_finish",
             out={"total_compensation": 550},
             started_ms=9000, ended_ms=25000, base=B3),
    ],
)
write("csagent_compensation_loop.json", csagent_compensation_loop)


# =============================================================================
# AGENT 4: open_deep_research (langchain-ai/open_deep_research)
# 11.1k stars | LangGraph | Multi-step deep research
# Tool sequence: generate_queries → search_tavily(×N) → write_section(×N) → finalize_report
# Bug: write_section called before ALL searches complete (interleaved pattern).
#   Each section written with only partial context.
# =============================================================================
print("Agent 4: open_deep_research")

B4 = datetime(2026, 4, 18, 13, 0, 0, tzinfo=timezone.utc)

odr_happy = trace(
    prompt="Write a comprehensive report on the current state of fusion energy commercialization",
    framework="langgraph",
    model="gpt-4o",
    agent_name="OpenDeepResearch",
    total_ms=120000,
    base=B4,
    steps=[
        step(0, "tool_call", "generate_queries",
             inp={"topic": "fusion energy commercialization", "num_queries": 4},
             out={"queries": [
                 "fusion energy companies 2025 commercialization status",
                 "Commonwealth Fusion Systems SPARC timeline",
                 "TAE Technologies private fusion progress",
                 "fusion energy investment funding 2025",
             ]},
             reasoning="Planning search queries for comprehensive coverage",
             started_ms=0, ended_ms=3500, base=B4),
        step(1, "tool_call", "search_tavily",
             inp={"query": "fusion energy companies 2025 commercialization status"},
             out={"results": [{"url": "https://energy.gov/fusion-2025", "content": "..."}], "count": 8},
             started_ms=3500, ended_ms=7200, base=B4),
        step(2, "tool_call", "search_tavily",
             inp={"query": "Commonwealth Fusion Systems SPARC timeline"},
             out={"results": [{"url": "https://cfs.energy", "content": "..."}], "count": 6},
             started_ms=7200, ended_ms=10800, base=B4),
        step(3, "tool_call", "search_tavily",
             inp={"query": "TAE Technologies private fusion progress"},
             out={"results": [{"url": "https://tae.com/news", "content": "..."}], "count": 5},
             started_ms=10800, ended_ms=14100, base=B4),
        step(4, "tool_call", "search_tavily",
             inp={"query": "fusion energy investment funding 2025"},
             out={"results": [{"url": "https://pitchbook.com/fusion", "content": "..."}], "count": 7},
             started_ms=14100, ended_ms=17500, base=B4),
        step(5, "tool_call", "write_section",
             inp={"section": "Introduction", "context_sources": 4, "query_coverage": "complete"},
             out={"section_text": "# Introduction\n\n...", "word_count": 420},
             started_ms=17500, ended_ms=32000, base=B4),
        step(6, "tool_call", "write_section",
             inp={"section": "Current State of Commercial Fusion", "context_sources": 4},
             out={"section_text": "# Current State\n\n...", "word_count": 680},
             started_ms=32000, ended_ms=52000, base=B4),
        step(7, "tool_call", "write_section",
             inp={"section": "Key Players and Investment Landscape", "context_sources": 4},
             out={"section_text": "# Key Players\n\n...", "word_count": 550},
             started_ms=52000, ended_ms=70000, base=B4),
        step(8, "tool_call", "write_section",
             inp={"section": "Conclusion and Outlook", "context_sources": 4},
             out={"section_text": "# Conclusion\n\n...", "word_count": 310},
             started_ms=70000, ended_ms=85000, base=B4),
        step(9, "tool_call", "write_final_report",
             inp={"sections": 4, "total_words": 1960},
             out={"report_length": 2450, "citations": 26},
             started_ms=85000, ended_ms=120000, base=B4),
        step(10, "agent_finish", "agent_finish",
             out={"report_length": 2450},
             started_ms=120000, ended_ms=120100, base=B4),
    ],
)
write("odr_happy_path.json", odr_happy)

# BUG: write_section interleaved with search — sections written with partial data
odr_section_before_all_searches = trace(
    prompt="Write a report on AI regulation in 2026 covering EU, US, and China",
    framework="langgraph",
    model="gpt-4o",
    agent_name="OpenDeepResearch",
    total_ms=95000,
    base=B4,
    steps=[
        step(0, "tool_call", "generate_queries",
             inp={"topic": "AI regulation 2026", "num_queries": 3},
             out={"queries": [
                 "EU AI Act implementation 2026",
                 "US AI regulation executive order 2026",
                 "China AI regulation 2026",
             ]},
             started_ms=0, ended_ms=2800, base=B4),
        step(1, "tool_call", "search_tavily",
             inp={"query": "EU AI Act implementation 2026"},
             out={"results": [{"url": "https://eur-lex.europa.eu", "content": "..."}], "count": 7},
             started_ms=2800, ended_ms=6400, base=B4),
        # BUG: write_section for EU called immediately — only EU search done, US and China missing
        step(2, "tool_call", "write_section",
             inp={"section": "EU AI Regulation", "context_sources": 1,
                  "query_coverage": "partial", "missing_queries": 2},
             out={"section_text": "# EU AI Regulation\n\n...", "word_count": 580},
             reasoning="Writing EU section from available EU search results",
             started_ms=6400, ended_ms=22000, base=B4),
        step(3, "tool_call", "search_tavily",
             inp={"query": "US AI regulation executive order 2026"},
             out={"results": [{"url": "https://whitehouse.gov/ai", "content": "..."}], "count": 5},
             started_ms=22000, ended_ms=25500, base=B4),
        # BUG: write_section for US called — China still missing
        step(4, "tool_call", "write_section",
             inp={"section": "US AI Regulation", "context_sources": 1, "query_coverage": "partial"},
             out={"section_text": "# US AI Regulation\n\n...", "word_count": 490},
             started_ms=25500, ended_ms=41000, base=B4),
        step(5, "tool_call", "search_tavily",
             inp={"query": "China AI regulation 2026"},
             out={"results": [{"url": "https://cyberlaw.cn", "content": "..."}], "count": 4},
             started_ms=41000, ended_ms=44800, base=B4),
        step(6, "tool_call", "write_section",
             inp={"section": "China AI Regulation", "context_sources": 1},
             out={"section_text": "# China AI Regulation\n\n...", "word_count": 420},
             started_ms=44800, ended_ms=58000, base=B4),
        step(7, "tool_call", "write_final_report",
             inp={"sections": 3, "total_words": 1490},
             out={"report_length": 1820, "citations": 16},
             started_ms=58000, ended_ms=95000, base=B4),
        step(8, "agent_finish", "agent_finish",
             out={"report_length": 1820},
             started_ms=95000, ended_ms=95100, base=B4),
    ],
)
write("odr_section_before_all_searches.json", odr_section_before_all_searches)

# EMPTY SEARCH STRESS: search returns nothing, sections written anyway
odr_empty_sections = trace(
    prompt="Write a detailed analysis of the secret AI project rumored at Microsoft",
    framework="langgraph",
    model="gpt-4o",
    agent_name="OpenDeepResearch",
    total_ms=55000,
    status="success",
    base=B4,
    steps=[
        step(0, "tool_call", "generate_queries",
             inp={"topic": "Microsoft secret AI project", "num_queries": 3},
             out={"queries": [
                 "Microsoft secret AI project 2026",
                 "Microsoft unreleased AI initiative",
                 "Microsoft AI rumor internal project",
             ]},
             started_ms=0, ended_ms=2100, base=B4),
        step(1, "tool_call", "search_tavily",
             inp={"query": "Microsoft secret AI project 2026"},
             out={"results": [], "count": 0},
             started_ms=2100, ended_ms=4800, base=B4),
        step(2, "tool_call", "search_tavily",
             inp={"query": "Microsoft unreleased AI initiative"},
             out={"results": [], "count": 0},
             started_ms=4800, ended_ms=7200, base=B4),
        step(3, "tool_call", "search_tavily",
             inp={"query": "Microsoft AI rumor internal project"},
             out={"results": [], "count": 0},
             started_ms=7200, ended_ms=9600, base=B4),
        # Bug: writes sections with 0 search results — guaranteed hallucination
        step(4, "tool_call", "write_section",
             inp={"section": "Overview", "context_sources": 0},
             out={"section_text": "# Overview\n\nBased on available information...", "word_count": 310},
             reasoning="Generating overview from limited available information",
             started_ms=9600, ended_ms=21000, base=B4),
        step(5, "tool_call", "write_section",
             inp={"section": "Analysis", "context_sources": 0},
             out={"section_text": "# Analysis\n\n...", "word_count": 420},
             started_ms=21000, ended_ms=38000, base=B4),
        step(6, "tool_call", "write_final_report",
             inp={"sections": 2, "total_words": 730},
             out={"report_length": 950, "citations": 0},
             started_ms=38000, ended_ms=55000, base=B4),
        step(7, "agent_finish", "agent_finish",
             out={"report_length": 950},
             started_ms=55000, ended_ms=55100, base=B4),
    ],
)
write("odr_empty_sections.json", odr_empty_sections)


# =============================================================================
# AGENT 5: pydantic-ai bank_support (pydantic/pydantic-ai examples)
# 7.7k stars | Pydantic AI | Banking support agent
# Tool sequence: customer_balance → SupportOutput (block_card decision)
# Bug: block_card=True in output with no explicit confirmation tool call.
#   Source: SupportOutput.block_card is set by LLM — irreversible action
#   with no guard, no confirmation step.
# =============================================================================
print("Agent 5: pydantic-ai bank_support")

B5 = datetime(2026, 4, 18, 14, 0, 0, tzinfo=timezone.utc)

pyai_happy = trace(
    prompt="What's my current balance and do I have any recent suspicious transactions?",
    framework="pydantic_ai",
    model="gpt-4o",
    agent_name="BankSupportAgent",
    total_ms=3800,
    base=B5,
    steps=[
        step(0, "tool_call", "customer_balance",
             inp={"include_pending": True},
             out={"balance": 2450.00, "currency": "USD",
                  "recent_transactions": [
                      {"date": "2026-04-17", "amount": -45.00, "merchant": "Amazon"},
                      {"date": "2026-04-16", "amount": -12.50, "merchant": "Starbucks"},
                  ]},
             reasoning="Checking customer balance and transaction history",
             started_ms=0, ended_ms=420, base=B5),
        step(1, "agent_finish", "agent_finish",
             out={"advice": "Your balance is $2,450.00. No suspicious activity detected.",
                  "block_card": False,
                  "risk": "low"},
             started_ms=420, ended_ms=3800, base=B5),
    ],
)
write("pyai_bank_happy.json", pyai_happy)

# BUG TRACE: block_card=True set without any confirmation tool call
# The agent reads balance showing suspicious activity and immediately blocks the card.
# No tool call to confirm with the customer, no verify_action step.
# Source verified: SupportOutput has block_card bool set by LLM directly.
pyai_bank_block_no_confirm = trace(
    prompt="I think my card was stolen, there are charges I don't recognize",
    framework="pydantic_ai",
    model="gpt-4o",
    agent_name="BankSupportAgent",
    total_ms=4200,
    base=B5,
    steps=[
        step(0, "tool_call", "customer_balance",
             inp={"include_pending": True},
             out={"balance": -320.50, "currency": "USD",
                  "recent_transactions": [
                      {"date": "2026-04-18", "amount": -1500.00, "merchant": "Electronics Store Mumbai"},
                      {"date": "2026-04-18", "amount": -890.00, "merchant": "Unknown Merchant"},
                      {"date": "2026-04-18", "amount": -430.00, "merchant": "Foreign Transfer"},
                  ]},
             reasoning="Checking customer account for reported suspicious activity",
             started_ms=0, ended_ms=480, base=B5),
        # BUG: block_card=True in output with NO confirmation step.
        # Card is immediately and irreversibly blocked after one tool call.
        # Customer receives no warning, no "shall I block your card?" dialog.
        step(1, "agent_finish", "agent_finish",
             out={"advice": "I've detected unauthorized transactions. Your card has been blocked immediately.",
                  "block_card": True,
                  "risk": "critical",
                  "blocked": True},
             reasoning="Blocking card due to suspicious transactions",
             started_ms=480, ended_ms=4200, base=B5),
    ],
)
write("pyai_bank_block_no_confirm.json", pyai_bank_block_no_confirm)

# RETRY LOOP: calls customer_balance 3 times
pyai_bank_retry_loop = trace(
    prompt="What is my balance? I want to make sure it's accurate",
    framework="pydantic_ai",
    model="gpt-4o",
    agent_name="BankSupportAgent",
    total_ms=6800,
    base=B5,
    steps=[
        step(0, "tool_call", "customer_balance",
             inp={"include_pending": False},
             out={"balance": 1200.00},
             started_ms=0, ended_ms=380, base=B5),
        step(1, "tool_call", "customer_balance",
             inp={"include_pending": True},
             out={"balance": 1185.00},
             reasoning="Checking with pending transactions included",
             started_ms=380, ended_ms=760, base=B5),
        step(2, "tool_call", "customer_balance",
             inp={"include_pending": True, "as_of": "2026-04-18"},
             out={"balance": 1185.00},
             reasoning="Verifying balance is current",
             started_ms=760, ended_ms=1140, base=B5),
        step(3, "agent_finish", "agent_finish",
             out={"advice": "Your available balance is $1,185.00 (with pending transactions)",
                  "block_card": False, "risk": "low"},
             started_ms=1140, ended_ms=6800, base=B5),
    ],
)
write("pyai_bank_retry_loop.json", pyai_bank_retry_loop)


# =============================================================================
# AGENT 6: langchain-ai/deepagents
# 21.1k stars | LangChain+LangGraph | Multi-step planning + execution
# Tool sequence: write_todos → ls/glob/grep → read_file → edit_file → execute → task
# Bug: write_todos (planning) skipped under "simple" tasks, loops on edit→execute
# =============================================================================
print("Agent 6: deepagents")

B6 = datetime(2026, 4, 18, 15, 0, 0, tzinfo=timezone.utc)

deepagents_happy = trace(
    prompt="Add input validation to the user registration endpoint to reject emails without @ symbol",
    framework="langgraph",
    model="claude-sonnet-4-6",
    agent_name="DeepAgents",
    total_ms=75000,
    base=B6,
    steps=[
        step(0, "tool_call", "write_todos",
             inp={"todos": [
                 "Find user registration endpoint",
                 "Understand current validation logic",
                 "Add email format validation",
                 "Write test for invalid email",
                 "Run test suite",
             ]},
             out={"todos_written": 5, "todo_file": ".todos.md"},
             reasoning="Creating structured plan before beginning",
             started_ms=0, ended_ms=2200, base=B6),
        step(1, "tool_call", "glob",
             inp={"pattern": "**/*.py"},
             out={"matches": ["src/routes/auth.py", "src/models/user.py",
                              "tests/test_auth.py", "src/validators.py"]},
             started_ms=2200, ended_ms=3100, base=B6),
        step(2, "tool_call", "grep",
             inp={"pattern": "register", "path": "src/routes/auth.py"},
             out={"matches": [
                 {"line": 42, "content": "def register_user(email: str, password: str):"},
             ]},
             started_ms=3100, ended_ms=4000, base=B6),
        step(3, "tool_call", "read_file",
             inp={"path": "src/routes/auth.py", "start_line": 40, "end_line": 65},
             out={"content": "def register_user(email: str, password: str):\n    user = User(email=email, password=hash_password(password))\n    db.save(user)\n    return {'id': user.id}", "lines": 25},
             started_ms=4000, ended_ms=5200, base=B6),
        step(4, "tool_call", "edit_file",
             inp={"path": "src/routes/auth.py",
                  "insert_before": "    user = User(",
                  "content": "    if '@' not in email or '.' not in email.split('@')[-1]:\n        raise ValueError('Invalid email format')"},
             out={"success": True, "lines_added": 2},
             reasoning="Adding email format validation to reject emails without @ symbol",
             started_ms=5200, ended_ms=6800, base=B6),
        step(5, "tool_call", "execute",
             inp={"command": "python -m pytest tests/test_auth.py -v"},
             out={"stdout": "test_register_invalid_email PASSED\ntest_register_valid PASSED\n2 passed in 0.41s",
                  "returncode": 0},
             started_ms=6800, ended_ms=15000, base=B6),
        step(6, "tool_call", "write_todos",
             inp={"todos": ["DONE: Find endpoint", "DONE: Add validation", "DONE: Tests pass"],
                  "update": True},
             out={"todos_updated": 3},
             started_ms=15000, ended_ms=16200, base=B6),
        step(7, "agent_finish", "agent_finish",
             out={"summary": "Added email validation. All tests pass."},
             started_ms=16200, ended_ms=75000, base=B6),
    ],
)
write("deepagents_happy.json", deepagents_happy)

# BUG TRACE: write_todos (planning) skipped entirely — agent jumps straight to edit
# Leads to repeated edit→execute→fail loop (planning abandonment)
deepagents_no_plan = trace(
    prompt="Optimize the database query in the report generation module, it's too slow",
    framework="langgraph",
    model="claude-sonnet-4-6",
    agent_name="DeepAgents",
    total_ms=145000,
    status="error",
    base=B6,
    steps=[
        # BUG: No write_todos call. Agent goes directly to editing.
        step(0, "tool_call", "glob",
             inp={"pattern": "**/*report*"},
             out={"matches": ["src/reports/generator.py", "src/reports/queries.py"]},
             started_ms=0, ended_ms=900, base=B6),
        step(1, "tool_call", "read_file",
             inp={"path": "src/reports/generator.py"},
             out={"content": "def generate_report(user_id):\n    data = db.query('SELECT * FROM events WHERE user_id=?', [user_id])\n    return format_report(data)", "lines": 82},
             started_ms=900, ended_ms=2100, base=B6),
        # Attempts optimization without understanding the full query context
        step(2, "tool_call", "edit_file",
             inp={"path": "src/reports/queries.py",
                  "operation": "replace",
                  "target": "SELECT * FROM events",
                  "replacement": "SELECT id, timestamp, type FROM events USE INDEX (idx_user_id)"},
             out={"success": True, "lines_changed": 1},
             started_ms=2100, ended_ms=3800, base=B6),
        step(3, "tool_call", "execute",
             inp={"command": "python -m pytest tests/test_reports.py -v"},
             out={"stdout": "FAILED test_report_includes_metadata - KeyError: 'metadata'",
                  "returncode": 1},
             started_ms=3800, ended_ms=12000, base=B6),
        # Second attempt without understanding root cause
        step(4, "tool_call", "edit_file",
             inp={"path": "src/reports/queries.py",
                  "operation": "replace",
                  "target": "SELECT id, timestamp, type FROM events",
                  "replacement": "SELECT id, timestamp, type, metadata FROM events"},
             out={"success": True, "lines_changed": 1},
             started_ms=12000, ended_ms=13500, base=B6),
        step(5, "tool_call", "execute",
             inp={"command": "python -m pytest tests/test_reports.py -v"},
             out={"stdout": "FAILED test_report_includes_metadata - AssertionError: metadata format",
                  "returncode": 1},
             started_ms=13500, ended_ms=22000, base=B6),
        step(6, "tool_call", "edit_file",
             inp={"path": "src/reports/queries.py",
                  "operation": "replace",
                  "target": "SELECT id, timestamp, type, metadata FROM events",
                  "replacement": "SELECT id, timestamp, type, metadata::json FROM events"},
             out={"success": True, "lines_changed": 1},
             started_ms=22000, ended_ms=23500, base=B6),
        step(7, "tool_call", "execute",
             inp={"command": "python -m pytest tests/test_reports.py -v"},
             out={"stdout": "FAILED test_report_performance - Execution time: 8.2s (limit: 2.0s)",
                  "returncode": 1},
             started_ms=23500, ended_ms=32000, base=B6),
        step(8, "tool_call", "edit_file",
             inp={"path": "src/reports/generator.py",
                  "operation": "replace",
                  "target": "db.query(",
                  "replacement": "db.query_cached("},
             out={"success": True, "lines_changed": 1},
             started_ms=32000, ended_ms=33500, base=B6),
        step(9, "tool_call", "execute",
             inp={"command": "python -m pytest tests/test_reports.py -v"},
             out={"stdout": "AttributeError: 'Database' object has no attribute 'query_cached'",
                  "returncode": 1},
             started_ms=33500, ended_ms=42000, base=B6),
        step(10, "error", "execute",
             inp={"command": "python -m pytest tests/test_reports.py -v"},
             error="Max retries exceeded: agent gave up after 4 failed attempts",
             started_ms=42000, ended_ms=145000, base=B6),
    ],
)
write("deepagents_no_plan.json", deepagents_no_plan)

# PLANNING THEN ABANDONMENT: writes todos then ignores them
deepagents_plan_abandon = trace(
    prompt="Refactor the payment module to use the new Stripe v3 API instead of v2",
    framework="langgraph",
    model="claude-sonnet-4-6",
    agent_name="DeepAgents",
    total_ms=180000,
    base=B6,
    steps=[
        step(0, "tool_call", "write_todos",
             inp={"todos": [
                 "1. Audit all Stripe v2 API calls",
                 "2. Map v2 methods to v3 equivalents",
                 "3. Update payment.py",
                 "4. Update webhook_handler.py",
                 "5. Update tests",
                 "6. Test payment flow end-to-end",
             ]},
             out={"todos_written": 6},
             reasoning="Creating detailed plan for Stripe migration",
             started_ms=0, ended_ms=2800, base=B6),
        step(1, "tool_call", "read_file",
             inp={"path": "src/payment.py"},
             out={"content": "import stripe\nstripe.api_key = API_KEY\n# ... 200 lines of v2 calls", "lines": 200},
             started_ms=2800, ended_ms=4200, base=B6),
        # Agent abandons the plan and goes directly to editing payment.py
        # Skips steps 1, 2 (audit + mapping) and jumps to step 3
        # Never touches webhook_handler.py or updates tests
        step(2, "tool_call", "edit_file",
             inp={"path": "src/payment.py",
                  "operation": "replace",
                  "target": "stripe.Charge.create(",
                  "replacement": "stripe.PaymentIntent.create(",
                  "replace_all": True},
             out={"success": True, "replacements": 12},
             reasoning="Replacing all v2 Charge.create calls with v3 PaymentIntent.create",
             started_ms=4200, ended_ms=7800, base=B6),
        step(3, "tool_call", "execute",
             inp={"command": "python -m pytest tests/test_payment.py -v --timeout=30"},
             out={"stdout": "FAILED test_payment_webhook - stripe.error.InvalidRequestError",
                  "returncode": 1},
             started_ms=7800, ended_ms=45000, base=B6),
        step(4, "tool_call", "edit_file",
             inp={"path": "src/payment.py"},
             out={"success": True},
             started_ms=45000, ended_ms=48000, base=B6),
        step(5, "tool_call", "execute",
             inp={"command": "python -m pytest tests/test_payment.py -v --timeout=30"},
             out={"stdout": "FAILED test_payment_webhook - missing 'customer' field",
                  "returncode": 1},
             started_ms=48000, ended_ms=90000, base=B6),
        step(6, "tool_call", "edit_file",
             inp={"path": "src/payment.py"},
             out={"success": True},
             started_ms=90000, ended_ms=93000, base=B6),
        step(7, "tool_call", "execute",
             inp={"command": "python -m pytest tests/test_payment.py -v --timeout=30"},
             out={"stdout": "3 passed, 2 failed — webhook_handler tests still failing",
                  "returncode": 1},
             started_ms=93000, ended_ms=135000, base=B6),
        step(8, "agent_finish", "agent_finish",
             out={"status": "partial", "note": "payment.py updated, webhook_handler.py untouched",
                  "tests_passing": 3, "tests_failing": 2},
             started_ms=135000, ended_ms=180000, base=B6),
    ],
)
write("deepagents_plan_abandon.json", deepagents_plan_abandon)

print("\nDone. All traces written.")
