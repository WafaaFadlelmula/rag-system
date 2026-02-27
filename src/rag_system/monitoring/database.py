"""
Query Monitoring Database
==========================
SQLite-backed log of every RAG query.

Schema — query_logs:
    id                  auto-increment primary key
    timestamp           ISO-8601 UTC string
    question            user question text
    answer              generated answer text
    sources_cited       JSON list of source_file names
    cost_usd            LLM cost (None for streaming queries)
    latency_ms          wall-clock ms from request receipt to response ready
    top_reranker_score  rerank_score of the first (top) source chunk
    prompt_tokens       input tokens (None for streaming)
    completion_tokens   output tokens (None for streaming)
    flagged             0/1 review flag set by the monitoring UI
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# The DB path can be overridden with MONITORING_DB_PATH.
# On cloud deployments set this env var to a persistent volume path.
# Default: <project-root>/data/monitoring/queries.db (works for local dev)
_DEFAULT_DB = Path(__file__).parent.parent.parent.parent / "data" / "monitoring" / "queries.db"
DB_PATH = Path(os.environ.get("MONITORING_DB_PATH", str(_DEFAULT_DB)))


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables if they do not already exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_logs (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp           TEXT    NOT NULL,
                question            TEXT    NOT NULL,
                answer              TEXT    NOT NULL,
                sources_cited       TEXT,
                cost_usd            REAL,
                latency_ms          REAL,
                top_reranker_score  REAL,
                prompt_tokens       INTEGER,
                completion_tokens   INTEGER,
                flagged             INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

@contextmanager
def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def log_query(
    *,
    question: str,
    answer: str,
    sources: list[dict],
    cost_usd: Optional[float],
    latency_ms: float,
    top_reranker_score: Optional[float],
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
) -> int:
    """Insert one query log row and return its new id."""
    sources_cited = json.dumps([s.get("source_file", "") for s in sources])
    ts = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO query_logs
                (timestamp, question, answer, sources_cited,
                 cost_usd, latency_ms, top_reranker_score,
                 prompt_tokens, completion_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts, question, answer, sources_cited,
                cost_usd, latency_ms, top_reranker_score,
                prompt_tokens, completion_tokens,
            ),
        )
        conn.commit()
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_all_queries() -> list[dict]:
    """Return all rows, newest first."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM query_logs ORDER BY timestamp DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def flag_query(query_id: int, flagged: bool) -> None:
    """Set or clear the review flag on a single row."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE query_logs SET flagged = ? WHERE id = ?",
            (int(flagged), query_id),
        )
        conn.commit()
