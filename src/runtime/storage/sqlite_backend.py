"""
SQLite Backend (Tier 5 — Storage Architecture)
===============================================
WAL-mode SQLite persistence backend for Tier 5 production knowledge modules.

Fully implements ``ProductionMemoryBackend`` so it is a drop-in replacement
for ``JSONLBackend`` or ``InMemoryBackend``.

Features:
    - Named per-entity tables (scenes, reviews, patterns, failures, recommendations)
    - WAL journal mode — concurrent reads, serialised writes
    - ACID transactions — every insert is committed immediately
    - Thread-safe — single connection guarded by threading.Lock
    - Lazy loading — DB file opened only on the first operation
    - JSONL migration — if the target file exists but is NOT a valid SQLite
      database (e.g. a prior JSONL deployment), all valid records are read and
      re-inserted into the correct table; corrupt lines are skipped silently
    - Corruption recovery — if ``sqlite3.DatabaseError`` is raised on open,
      the file is deleted and a fresh database is created
    - Human-readable storage — each row carries ``data_json`` so records can be
      inspected with any SQLite browser

Schema (one table per entity type):
    scenes          — record_type "scene"
    reviews         — record_type "review"
    patterns        — record_type "pattern_usage"
    failures        — record_type "failure"
    recommendations — record_type "recommendation"  (reserved for future use)

    Each table:
        id         INTEGER PRIMARY KEY AUTOINCREMENT
        record_id  TEXT    NOT NULL DEFAULT ''
        data_json  TEXT    NOT NULL
        timestamp  REAL    NOT NULL DEFAULT 0

Public API (mirrors ProductionMemoryBackend exactly):
    SQLiteBackend(path)
        .insert(record_type, record) -> None
        .query(record_type, filters, order_desc, limit) -> list
        .count(record_type, filters) -> int
        .all_records(record_type) -> list
        .clear() -> None
        .record_count() -> int
        .write_count() -> int
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from src.runtime.storage.memory_backend import ProductionMemoryBackend
from src.runtime.storage.serialization import deserialize_record, serialize_record

# ---------------------------------------------------------------------------
# Record-type → table name mapping
# ---------------------------------------------------------------------------

_TABLE_MAP: Dict[str, str] = {
    "scene":          "scenes",
    "review":         "reviews",
    "pattern_usage":  "patterns",
    "failure":        "failures",
    "recommendation": "recommendations",
}

# ---------------------------------------------------------------------------
# DDL — one CREATE TABLE / INDEX per entity type
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS scenes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id  TEXT    NOT NULL DEFAULT '',
    data_json  TEXT    NOT NULL,
    timestamp  REAL    NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_scenes_ts ON scenes (timestamp);

CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id  TEXT    NOT NULL DEFAULT '',
    data_json  TEXT    NOT NULL,
    timestamp  REAL    NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_reviews_ts ON reviews (timestamp);

CREATE TABLE IF NOT EXISTS patterns (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id  TEXT    NOT NULL DEFAULT '',
    data_json  TEXT    NOT NULL,
    timestamp  REAL    NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_patterns_ts ON patterns (timestamp);

CREATE TABLE IF NOT EXISTS failures (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id  TEXT    NOT NULL DEFAULT '',
    data_json  TEXT    NOT NULL,
    timestamp  REAL    NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_failures_ts ON failures (timestamp);

CREATE TABLE IF NOT EXISTS recommendations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id  TEXT    NOT NULL DEFAULT '',
    data_json  TEXT    NOT NULL,
    timestamp  REAL    NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_recommendations_ts ON recommendations (timestamp);
"""


class SQLiteBackend(ProductionMemoryBackend):
    """Thread-safe SQLite-backed record store with JSONL migration support.

    Inherits from ``ProductionMemoryBackend`` — fully substitutable for
    ``InMemoryBackend`` and ``JSONLBackend``.
    """

    def __init__(self, path: str) -> None:
        self._path   = path
        self._lock   = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._writes = 0

    # ------------------------------------------------------------------
    # ProductionMemoryBackend interface
    # ------------------------------------------------------------------

    def insert(self, record_type: str, record: Dict[str, Any]) -> None:
        """Insert *record* into the table for *record_type*.

        Raises ``ValueError`` for unknown record types.
        """
        table = self._table_for(record_type)
        record_id = self._extract_record_id(record)
        ts        = float(record.get("timestamp", 0))
        data_json = serialize_record(record)
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                f"INSERT INTO {table} (record_id, data_json, timestamp) "
                f"VALUES (?, ?, ?)",
                (record_id, data_json, ts),
            )
            conn.commit()
            self._writes += 1

    def query(
        self,
        record_type: str,
        filters:    Optional[Dict[str, Any]] = None,
        order_desc: bool = True,
        limit:      int  = 50,
    ) -> List[Dict[str, Any]]:
        """Return records from *record_type*'s table matching *filters*.

        Ordered newest-first by timestamp when *order_desc* is True.
        """
        table   = self._table_for(record_type)
        filters = filters or {}
        order   = "DESC" if order_desc else "ASC"

        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                f"SELECT data_json FROM {table} "
                f"ORDER BY timestamp {order}, id {order}"
            ).fetchall()

        results: List[Dict[str, Any]] = []
        for (data_json,) in rows:
            rec = deserialize_record(data_json)
            if rec and self._matches(rec, filters):
                results.append(rec)
                if len(results) >= limit:
                    break
        return results

    def count(
        self,
        record_type: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Count records in *record_type*'s table matching *filters*."""
        table   = self._table_for(record_type)
        filters = filters or {}

        if not filters:
            with self._lock:
                conn = self._get_conn()
                row = conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()
            return row[0] if row else 0

        # Filters require Python-side evaluation
        return len(self.query(record_type, filters, order_desc=False, limit=10_000))

    def all_records(self, record_type: str) -> List[Dict[str, Any]]:
        """Return all records in *record_type*'s table (no limit)."""
        return self.query(record_type, limit=10_000, order_desc=True)

    def clear(self) -> None:
        """Delete all records from every table and reset the write counter."""
        with self._lock:
            conn = self._get_conn()
            for table in _TABLE_MAP.values():
                conn.execute(f"DELETE FROM {table}")
            conn.commit()
            self._writes = 0

    def record_count(self) -> int:
        """Total number of rows across all entity tables."""
        with self._lock:
            conn = self._get_conn()
            total = 0
            for table in _TABLE_MAP.values():
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                total += row[0] if row else 0
        return total

    def write_count(self) -> int:
        """Number of successful ``insert`` calls since construction."""
        with self._lock:
            return self._writes

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Return (or lazily open) the SQLite connection.

        Must be called under ``self._lock``.
        Handles corruption by deleting the file and starting fresh.
        """
        if self._conn is None:
            try:
                self._conn = self._open()
            except sqlite3.DatabaseError:
                # Corrupt database — wipe and start fresh
                self._delete_file_safely()
                self._conn = self._open()
        return self._conn

    def _open(self) -> sqlite3.Connection:
        """Open (or create) the SQLite database, migrating a JSONL file if present."""
        path = self._path

        # If the file exists but is not a valid SQLite database, treat it as JSONL
        jsonl_records: List[Dict[str, Any]] = []
        if os.path.exists(path) and os.path.getsize(path) > 0:
            if not _is_sqlite_db(path):
                jsonl_records = _read_jsonl(path)
                try:
                    os.truncate(path, 0)
                except OSError:
                    os.unlink(path)

        conn = sqlite3.connect(path, check_same_thread=False)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(_DDL)
            conn.commit()
        except sqlite3.DatabaseError:
            conn.close()  # release the file handle so _delete_file_safely can unlink it
            raise

        # JSONL migration: re-insert migrated records into the correct tables
        if jsonl_records:
            for record in jsonl_records:
                rt    = record.get("record_type", "")
                table = _TABLE_MAP.get(rt)
                if not table:
                    continue  # unknown type — skip silently
                ts        = float(record.get("timestamp", 0))
                record_id = self._extract_record_id(record)
                conn.execute(
                    f"INSERT INTO {table} (record_id, data_json, timestamp) "
                    f"VALUES (?, ?, ?)",
                    (record_id, serialize_record(record), ts),
                )
                self._writes += 1
            conn.commit()

        return conn

    def _delete_file_safely(self) -> None:
        # Also remove WAL and SHM sidecars — if they survive, the next
        # sqlite3.connect() may fail trying to reconcile them with a new DB.
        for suffix in ("", "-wal", "-shm"):
            candidate = self._path + suffix
            if os.path.exists(candidate):
                try:
                    os.unlink(candidate)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _table_for(record_type: str) -> str:
        """Return the table name for *record_type*.

        Raises ``ValueError`` for unknown types so callers fail loudly.
        """
        table = _TABLE_MAP.get(record_type)
        if table is None:
            raise ValueError(
                f"Unknown record_type {record_type!r}. "
                f"Known types: {sorted(_TABLE_MAP)}"
            )
        return table

    @staticmethod
    def _extract_record_id(record: Dict[str, Any]) -> str:
        """Pull the best available ID field from a record dict."""
        return str(record.get(
            "scene_id", record.get(
                "record_id", record.get(
                    "failure_id", record.get("pattern_id", "")
                )
            )
        ))


# ---------------------------------------------------------------------------
# File-level helpers (module private)
# ---------------------------------------------------------------------------

def _is_sqlite_db(path: str) -> bool:
    """Return True if *path* begins with the SQLite3 magic header."""
    try:
        with open(path, "rb") as fh:
            return fh.read(6) == b"SQLite"
    except (OSError, IOError):
        return False


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    """Read a JSONL file, skipping corrupt or non-dict lines."""
    records: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        records.append(obj)
                except (json.JSONDecodeError, ValueError):
                    pass
    except (OSError, IOError):
        pass
    return records
