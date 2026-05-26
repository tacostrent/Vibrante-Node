"""
Audit Store
===========
Optional persistent storage for transaction records and operation histories.
Provides a durable audit trail for AI-driven operations — useful for debugging,
replay, and compliance.

Storage is **advisory** — if the store is unavailable or writes fail, runtime
operations proceed unaffected. Failures are silently swallowed (printed to
stderr at DEBUG level only).

Backend: JSONL (one JSON object per line). Human-readable and grep-friendly.
A future sqlite backend is reserved for Tier 4 when richer queries are needed.

File location:
  Default: ~/.vibrante_node_audit.jsonl
  Override: VIBRANTE_AUDIT_PATH env var, or pass `path=` to the constructor
  In-memory only: pass `path=None` explicitly — useful for tests

Retention:
  Records older than `max_age_days` OR beyond `max_records` are pruned at
  `compact()` time. `compact()` is called automatically when the in-memory
  buffer exceeds 2× `max_records`.

Public API:
    get_audit_store() -> AuditStore   (singleton)
    reset_audit_store_for_tests()     (test isolation only)

    await store.log_transaction(data: dict) -> str      (returns audit_id)
    await store.get_transaction(txn_id: str) -> dict | None
    await store.query_transactions(limit=100, status=None) -> list[dict]
    await store.compact() -> int                        (returns pruned count)
    store.stats() -> dict
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

_DEFAULT_PATH: Optional[Path] = None  # resolved lazily so env var can be set after import
_MAX_RECORDS_DEFAULT = 10_000
_MAX_AGE_DAYS_DEFAULT = 30.0


def _resolve_default_path() -> Path:
    env = os.environ.get("VIBRANTE_AUDIT_PATH", "")
    if env:
        return Path(env)
    return Path.home() / ".vibrante_node_audit.jsonl"


class AuditStore:
    """JSONL-backed persistent audit store.

    Records are kept in memory as a plain list; disk is the durable copy.
    Initial load from disk is lazy (on first write or read).
    """

    def __init__(
        self,
        path: Optional[Union[str, Path]] = ...,   # type: ignore[assignment]
        max_records: int = _MAX_RECORDS_DEFAULT,
        max_age_days: float = _MAX_AGE_DAYS_DEFAULT,
    ):
        # Sentinel: path=... (default) means "use env var / home dir"
        # path=None means "in-memory only"
        if path is ...:  # type: ignore[comparison-overlap]
            self._path: Optional[Path] = _resolve_default_path()
        elif path is None:
            self._path = None
        else:
            self._path = Path(path)

        self._max_records = max_records
        self._max_age_days = max_age_days
        self._lock = asyncio.Lock()
        self._memory: List[Dict[str, Any]] = []
        self._loaded = False
        self._write_count = 0

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def log_transaction(self, data: Dict[str, Any]) -> str:
        """Persist a transaction record and return its `audit_id`."""
        record = dict(data)
        if "audit_id" not in record:
            record["audit_id"] = str(uuid.uuid4())
        if "audit_ts" not in record:
            record["audit_ts"] = time.time()

        async with self._lock:
            await self._ensure_loaded()
            self._memory.append(record)
            await self._append_to_disk(record)
            self._write_count += 1
            if len(self._memory) > self._max_records * 2:
                await self._compact_unlocked()

        return record["audit_id"]

    async def get_transaction(self, txn_id: str) -> Optional[Dict[str, Any]]:
        """Look up by `transaction_id`, `id`, or `audit_id`. Returns most recent match."""
        async with self._lock:
            await self._ensure_loaded()
            for r in reversed(self._memory):
                if (
                    r.get("id") == txn_id
                    or r.get("transaction_id") == txn_id
                    or r.get("audit_id") == txn_id
                ):
                    return dict(r)
        return None

    async def query_transactions(
        self, limit: int = 100, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return the most recent `limit` records, newest first.

        Optionally filter by `status` field value (committed, rolled_back, …).
        """
        async with self._lock:
            await self._ensure_loaded()
            records = list(reversed(self._memory))

        if status:
            records = [r for r in records if r.get("status") == status]
        return records[:limit]

    async def compact(self) -> int:
        """Prune records exceeding retention limits. Returns count pruned."""
        async with self._lock:
            return await self._compact_unlocked()

    def stats(self) -> Dict[str, Any]:
        return {
            "path": str(self._path) if self._path else "(memory only)",
            "records_in_memory": len(self._memory),
            "max_records": self._max_records,
            "max_age_days": self._max_age_days,
            "write_count": self._write_count,
            "loaded": self._loaded,
        }

    # ------------------------------------------------------------------
    # Internal helpers (always call with self._lock held)
    # ------------------------------------------------------------------

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._memory = await asyncio.to_thread(self._load_from_disk)
        self._loaded = True

    def _load_from_disk(self) -> List[Dict[str, Any]]:
        if self._path is None or not self._path.exists():
            return []
        records: List[Dict[str, Any]] = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass  # skip corrupt lines
        except OSError:
            pass
        return records

    async def _append_to_disk(self, record: Dict[str, Any]) -> None:
        if self._path is None:
            return
        try:
            await asyncio.to_thread(self._sync_append, record)
        except Exception:  # noqa: BLE001
            pass  # audit failure must never block the runtime

    def _sync_append(self, record: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
        with open(self._path, "a", encoding="utf-8") as f:  # type: ignore[arg-type]
            f.write(json.dumps(record, default=str) + "\n")

    async def _compact_unlocked(self) -> int:
        cutoff = time.time() - self._max_age_days * 86400
        before = len(self._memory)
        self._memory = [r for r in self._memory if r.get("audit_ts", 0) >= cutoff]
        if len(self._memory) > self._max_records:
            self._memory = self._memory[-self._max_records:]
        pruned = before - len(self._memory)
        if pruned > 0 and self._path is not None:
            await asyncio.to_thread(self._rewrite_disk)
        return pruned

    def _rewrite_disk(self) -> None:
        if self._path is None:
            return
        try:
            tmp = self._path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                for r in self._memory:
                    f.write(json.dumps(r, default=str) + "\n")
            tmp.replace(self._path)
        except OSError:
            pass


_STORE: Optional[AuditStore] = None


def get_audit_store() -> AuditStore:
    """Return the process-wide AuditStore singleton (default path)."""
    global _STORE
    if _STORE is None:
        _STORE = AuditStore()
    return _STORE


def reset_audit_store_for_tests() -> None:
    """Drop the singleton — for test isolation only."""
    global _STORE
    _STORE = None
