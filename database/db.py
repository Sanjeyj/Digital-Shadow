"""
database/db.py
SQLite persistence layer using only the standard library (sqlite3).
Stores a minimal report summary — never the user's raw personal input.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: str) -> None:
    """Create tables if they do not already exist."""
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reports (
                report_id       TEXT PRIMARY KEY,
                created_at      TEXT NOT NULL,
                risk_score      INTEGER NOT NULL,
                risk_category   TEXT NOT NULL,
                total_findings  INTEGER NOT NULL,
                low_count       INTEGER NOT NULL DEFAULT 0,
                medium_count    INTEGER NOT NULL DEFAULT 0,
                high_count      INTEGER NOT NULL DEFAULT 0,
                critical_count  INTEGER NOT NULL DEFAULT 0,
                score_breakdown TEXT,          -- JSON array
                disclaimer      TEXT
            );
            """
        )


def save_report(db_path: str, report: dict) -> str:
    """
    Persist a minimal report summary to the database.
    Returns the report_id.
    """
    report_id = report.get("report_id") or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    scoring = report.get("scoring", {})
    findings = report.get("findings", [])

    severity_counts = _count_severities(findings)

    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO reports
                (report_id, created_at, risk_score, risk_category,
                 total_findings, low_count, medium_count, high_count,
                 critical_count, score_breakdown, disclaimer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                now,
                scoring.get("total_score", 0),
                scoring.get("risk_category", "Unknown"),
                len(findings),
                severity_counts["low"],
                severity_counts["medium"],
                severity_counts["high"],
                severity_counts["critical"],
                json.dumps(scoring.get("score_breakdown", [])),
                scoring.get("disclaimer", ""),
            ),
        )
    return report_id


def get_report(db_path: str, report_id: str) -> Optional[dict]:
    """Return the stored report summary or None."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM reports WHERE report_id = ?", (report_id,)
        ).fetchone()
    if row is None:
        return None

    result = dict(row)
    try:
        result["score_breakdown"] = json.loads(result.get("score_breakdown") or "[]")
    except Exception:
        result["score_breakdown"] = []
    return result


def delete_report(db_path: str, report_id: str) -> bool:
    """Delete a report. Returns True if a row was deleted."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM reports WHERE report_id = ?", (report_id,)
        )
    return cursor.rowcount > 0


def list_reports(db_path: str, limit: int = 50) -> list[dict]:
    """Return a summary list of stored reports, newest first."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT report_id, created_at, risk_score, risk_category, total_findings "
            "FROM reports ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _count_severities(findings: list[dict]) -> dict:
    counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for f in findings:
        s = (f.get("severity") or "low").lower()
        if s in counts:
            counts[s] += 1
    return counts
