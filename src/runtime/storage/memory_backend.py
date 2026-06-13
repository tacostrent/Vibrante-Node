"""
Storage Backend Abstraction — Production Memory (Tier 5)
=========================================================
Provides the abstract interface and concrete implementations for
Tier 5 persistence backends.

Classes:
    ProductionMemoryBackend  — abstract base class (the interface contract)
    InMemoryBackend          — no-persistence in-memory implementation (tests / ephemeral)
    JSONLBackend             — append-only JSONL file implementation (existing behaviour)

All three implement the same interface so callers in production_memory.py
remain unchanged regardless of which backend is selected.

Public API:
    ProductionMemoryBackend   — import for type annotations
    InMemoryBackend           — used when path=None
    JSONLBackend              — used when path is a file path
    MemoryBackend             — alias for InMemoryBackend (backward compat)
"""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.runtime.storage.serialization import deserialize_record, serialize_record


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class ProductionMemoryBackend(ABC):
    """Contract that every storage backend must fulfil.

    All methods are thread-safe in concrete implementations.
    """

    @abstractmethod
    def insert(self, record_type: str, record: Dict[str, Any]) -> None:
        """Persist one record.  record must contain a record_type key."""

    @abstractmethod
    def query(
        self,
        record_type: str,
        filters: Optional[Dict[str, Any]] = None,
        order_desc: bool = True,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return records of *record_type* matching all *filters* key=value pairs.

        Ordered newest-first by ``timestamp`` when *order_desc* is True.
        """

    @abstractmethod
    def count(
        self,
        record_type: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Count records of *record_type* matching all *filters*."""

    @abstractmethod
    def all_records(self, record_type: str) -> List[Dict[str, Any]]:
        """Return every record of *record_type* (no limit)."""

    @abstractmethod
    def clear(self) -> None:
        """Delete all records and reset counters."""

    @abstractmethod
    def record_count(self) -> int:
        """Total number of records across all types."""

    @abstractmethod
    def write_count(self) -> int:
        """Number of successful inserts since construction."""

    # ------------------------------------------------------------------
    # Shared helper — all concrete classes use this
    # ------------------------------------------------------------------

    @staticmethod
    def _matches(record: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        return all(record.get(k) == v for k, v in filters.items())


# ---------------------------------------------------------------------------
# In-memory backend  (used when path=None)
# ---------------------------------------------------------------------------

class InMemoryBackend(ProductionMemoryBackend):
    """Thread-safe in-memory record store.  No persistence whatsoever."""

    def __init__(self) -> None:
        self._lock    = threading.Lock()
        self._records: List[Dict[str, Any]] = []
        self._writes  = 0

    def insert(self, record_type: str, record: Dict[str, Any]) -> None:
        with self._lock:
            self._records.append(dict(record))
            self._writes += 1

    def query(
        self,
        record_type: str,
        filters: Optional[Dict[str, Any]] = None,
        order_desc: bool = True,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            results = [
                dict(r) for r in self._records
                if r.get("record_type") == record_type
                and self._matches(r, filters or {})
            ]
        if order_desc:
            results.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
        return results[:limit]

    def count(
        self,
        record_type: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        with self._lock:
            return sum(
                1 for r in self._records
                if r.get("record_type") == record_type
                and self._matches(r, filters or {})
            )

    def all_records(self, record_type: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._records if r.get("record_type") == record_type]

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._writes = 0

    def record_count(self) -> int:
        with self._lock:
            return len(self._records)

    def write_count(self) -> int:
        with self._lock:
            return self._writes


# ---------------------------------------------------------------------------
# JSONL backend  (used when path is a file path — preserves existing behaviour)
# ---------------------------------------------------------------------------

class JSONLBackend(ProductionMemoryBackend):
    """Append-only JSONL file backend.

    Behaviour is identical to the original ProductionMemory JSONL logic:
    - Lazy loads from file on first read
    - Each insert appends a JSON line to the file (silent on write failure)
    - Corrupt lines are skipped during load
    - In-memory cache is maintained for fast queries after load
    """

    _MAX_RECORDS = 5_000

    def __init__(self, path: str) -> None:
        self._path   = path
        self._lock   = threading.Lock()
        self._cache: List[Dict[str, Any]] = []
        self._loaded = False
        self._writes = 0

    # ------------------------------------------------------------------
    # ProductionMemoryBackend interface
    # ------------------------------------------------------------------

    def insert(self, record_type: str, record: Dict[str, Any]) -> None:
        with self._lock:
            self._ensure_loaded_locked()
            self._cache.append(dict(record))
            self._writes += 1
            # Auto-prune in memory
            if len(self._cache) > self._MAX_RECORDS * 2:
                self._cache = self._cache[-self._MAX_RECORDS:]

        # Append to file outside the cache lock to avoid holding it during I/O
        if self._path:
            try:
                with open(self._path, "a", encoding="utf-8") as fh:
                    fh.write(serialize_record(record) + "\n")
            except Exception:
                pass  # write failures never block execution

    def query(
        self,
        record_type: str,
        filters: Optional[Dict[str, Any]] = None,
        order_desc: bool = True,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        with self._lock:
            results = [
                dict(r) for r in self._cache
                if r.get("record_type") == record_type
                and self._matches(r, filters or {})
            ]
        if order_desc:
            results.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
        return results[:limit]

    def count(
        self,
        record_type: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        self._ensure_loaded()
        with self._lock:
            return sum(
                1 for r in self._cache
                if r.get("record_type") == record_type
                and self._matches(r, filters or {})
            )

    def all_records(self, record_type: str) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        with self._lock:
            return [dict(r) for r in self._cache if r.get("record_type") == record_type]

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._writes = 0
        if self._path and os.path.exists(self._path):
            try:
                open(self._path, "w").close()  # truncate
            except Exception:
                pass

    def record_count(self) -> int:
        self._ensure_loaded()
        with self._lock:
            return len(self._cache)

    def write_count(self) -> int:
        with self._lock:
            return self._writes

    # ------------------------------------------------------------------
    # Lazy load
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        with self._lock:
            self._ensure_loaded_locked()

    def _ensure_loaded_locked(self) -> None:
        """Must be called under self._lock."""
        if self._loaded:
            return
        self._loaded = True
        if not self._path:
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    record = deserialize_record(line)
                    if record:  # empty dict signals a parse error or non-dict JSON
                        self._cache.append(record)
        except FileNotFoundError:
            pass
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Backward-compat alias
# ---------------------------------------------------------------------------

# Tests and older code that imported MemoryBackend directly continue to work.
MemoryBackend = InMemoryBackend
