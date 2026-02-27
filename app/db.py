from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from datetime import date
from typing import Optional

DB_PATH = Path(os.getenv("HEALTH_DB_PATH", "/data/health.sqlite3"))

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS weight_entries (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  entry_ts    TEXT NOT NULL,              -- ISO8601 timestamp (with offset if you want later)
  entry_date  TEXT NOT NULL,              -- YYYY-MM-DD in America/Chicago
  weight_lbs  REAL NOT NULL,
  notes       TEXT,
  deleted_at  TEXT,                       -- ISO8601 timestamp when soft-deleted
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_weight_entries_entry_date
  ON weight_entries(entry_date);

CREATE INDEX IF NOT EXISTS idx_weight_entries_entry_ts
  ON weight_entries(entry_ts);

CREATE TABLE IF NOT EXISTS day_flags (
  entry_date   TEXT PRIMARY KEY,          -- YYYY-MM-DD
  did_workout  INTEGER NOT NULL DEFAULT 0,
  did_walk     INTEGER NOT NULL DEFAULT 0,
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH.as_posix(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def insert_weight_entry(
    *,
    entry_ts: str,
    entry_date: str,
    weight_lbs: float,
    notes: Optional[str],
) -> int:
    conn = connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO weight_entries (entry_ts, entry_date, weight_lbs, notes)
            VALUES (?, ?, ?, ?)
            """,
            (entry_ts, entry_date, weight_lbs, notes),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_weight_entries(*, range_key: str, limit: int = 200) -> list[sqlite3.Row]:
    # range_key: 7d/14d/30d/90d/all
    days_map = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}

    where = "deleted_at IS NULL"
    params: list[object] = []

    if range_key in days_map:
        # entry_date stored as YYYY-MM-DD, so lexicographic compare works
        cutoff = date.today().toordinal() - days_map[range_key] + 1
        cutoff_date = date.fromordinal(cutoff).isoformat()
        where += " AND entry_date >= ?"
        params.append(cutoff_date)

    conn = connect()
    try:
        cur = conn.execute(
            f"""
            SELECT id, entry_ts, entry_date, weight_lbs, notes, deleted_at
            FROM weight_entries
            WHERE {where}
            ORDER BY entry_ts DESC
            LIMIT ?
            """,
            (*params, limit),
        )
        return list(cur.fetchall())
    finally:
        conn.close()