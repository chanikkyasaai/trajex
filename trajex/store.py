from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from uuid import uuid4


class TraceStore:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = os.environ.get("TRAJEX_DB")
        if db_path is None:
            home = os.path.expanduser("~")
            trajex_dir = os.path.join(home, ".trajex")
            os.makedirs(trajex_dir, exist_ok=True)
            db_path = os.path.join(trajex_dir, "baselines.db")
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS baselines (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    trace_count INTEGER NOT NULL,
                    agent_name  TEXT,
                    description TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS baseline_patterns (
                    id           TEXT PRIMARY KEY,
                    baseline_id  TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    tool_name    TEXT,
                    value_json   TEXT NOT NULL,
                    FOREIGN KEY (baseline_id) REFERENCES baselines(id)
                )
            """)

    def save_baseline(self, baseline) -> str:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO baselines "
                "(id, name, created_at, trace_count, agent_name, description) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    baseline.id,
                    baseline.name,
                    baseline.created_at.isoformat(),
                    baseline.trace_count,
                    baseline.agent_name,
                    baseline.description,
                ),
            )
            conn.execute(
                "DELETE FROM baseline_patterns WHERE baseline_id = ?",
                (baseline.id,),
            )
            for pattern_type, pattern_data in baseline.patterns.items():
                if pattern_type in ("tool_frequency", "duration_range"):
                    for tool_name, stats in pattern_data.items():
                        conn.execute(
                            "INSERT INTO baseline_patterns "
                            "(id, baseline_id, pattern_type, tool_name, value_json) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (str(uuid4()), baseline.id, pattern_type, tool_name,
                             json.dumps(stats)),
                        )
                else:
                    conn.execute(
                        "INSERT INTO baseline_patterns "
                        "(id, baseline_id, pattern_type, tool_name, value_json) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (str(uuid4()), baseline.id, pattern_type, None,
                         json.dumps(pattern_data)),
                    )
        return baseline.id

    def load_baseline(self, baseline_id: str):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM baselines WHERE id = ?", (baseline_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Baseline not found: {baseline_id}")
            pattern_rows = conn.execute(
                "SELECT * FROM baseline_patterns WHERE baseline_id = ?",
                (baseline_id,),
            ).fetchall()

        patterns: dict = {}
        for pr in pattern_rows:
            ptype = pr["pattern_type"]
            tool_name = pr["tool_name"]
            value = json.loads(pr["value_json"])
            if ptype in ("tool_frequency", "duration_range"):
                if ptype not in patterns:
                    patterns[ptype] = {}
                patterns[ptype][tool_name] = value
            else:
                patterns[ptype] = value

        from trajex.baseline import BaselineModel
        return BaselineModel(
            id=row["id"],
            name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            trace_count=row["trace_count"],
            agent_name=row["agent_name"],
            description=row["description"] or "",
            patterns=patterns,
        )

    def list_baselines(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, created_at, trace_count, agent_name "
                "FROM baselines ORDER BY created_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_baseline(self, baseline_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM baseline_patterns WHERE baseline_id = ?",
                (baseline_id,),
            )
            conn.execute("DELETE FROM baselines WHERE id = ?", (baseline_id,))

    def find_baseline(self, name: str):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM baselines WHERE name = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (name,),
            ).fetchone()
        if row is None:
            return None
        return self.load_baseline(row["id"])
