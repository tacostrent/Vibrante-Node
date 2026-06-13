"""
Asset Cache (Tier 8 — Asset Intelligence Runtime)
===================================================
SQLite-backed TTL cache for asset queries, normalized assets, and rankings.

Tables:
    query_cache   — cached provider query results keyed by (provider, category, tags_hash)
    asset_cache   — cached normalized AssetDescriptor objects keyed by (provider, asset_id)
    ranking_cache — cached ranking results keyed by (intent_id, plan_id, category)

Design:
    - WAL-mode SQLite for concurrent reads.
    - TTL enforced at read time (expired entries are treated as misses).
    - Thread-safe via threading.Lock.
    - Lazy initialization — DB opened on first access.
    - Path from VIBRANTE_ASSET_CACHE_PATH env var or constructor argument.
      When path is None, an in-memory store is used (tests / ephemeral use).

Public API:
    AssetCache
    get_asset_cache()
    reset_asset_cache_for_tests()
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.assets.schema import AssetDescriptor

_DEFAULT_TTL_SECONDS = 86400  # 24 hours

_DDL = """
CREATE TABLE IF NOT EXISTS query_cache (
    cache_key   TEXT    NOT NULL,
    provider    TEXT    NOT NULL,
    data_json   TEXT    NOT NULL,
    created_at  REAL    NOT NULL DEFAULT 0,
    ttl_sec     REAL    NOT NULL DEFAULT 86400,
    PRIMARY KEY (cache_key, provider)
);
CREATE TABLE IF NOT EXISTS asset_cache (
    cache_key   TEXT    PRIMARY KEY,
    data_json   TEXT    NOT NULL,
    created_at  REAL    NOT NULL DEFAULT 0,
    ttl_sec     REAL    NOT NULL DEFAULT 86400
);
CREATE TABLE IF NOT EXISTS ranking_cache (
    cache_key   TEXT    PRIMARY KEY,
    data_json   TEXT    NOT NULL,
    created_at  REAL    NOT NULL DEFAULT 0,
    ttl_sec     REAL    NOT NULL DEFAULT 86400
);
"""


def _make_key(*parts: Any) -> str:
    """Build a deterministic cache key from arbitrary parts."""
    combined = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


class AssetCache:
    """Thread-safe SQLite TTL cache for the Asset Intelligence layer."""

    def __init__(
        self,
        path: Optional[str] = None,
        default_ttl: float = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._path = path or os.environ.get("VIBRANTE_ASSET_CACHE_PATH")
        self._default_ttl = default_ttl
        self._lock: threading.Lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._hits = 0
        self._misses = 0
        self._writes = 0
        # In-memory fallback when no path configured
        self._memory: Dict[Tuple[str, str], Tuple[str, float, float]] = {}

    # ------------------------------------------------------------------
    # Query cache
    # ------------------------------------------------------------------

    def get_query(
        self,
        provider: str,
        category: str,
        tags: List[str],
    ) -> Optional[List[Dict[str, Any]]]:
        """Return cached provider results, or None on miss/expiry."""
        key = _make_key(category, sorted(tags))
        now = time.time()
        if self._path:
            row = self._db_get("query_cache", key, provider)
            if row and now - row[1] < row[2]:
                self._hits += 1
                return json.loads(row[0])
        else:
            mem_key = ("query", f"{key}:{provider}")
            entry = self._memory.get(mem_key)
            if entry and now - entry[1] < entry[2]:
                self._hits += 1
                return json.loads(entry[0])
        self._misses += 1
        return None

    def set_query(
        self,
        provider: str,
        category: str,
        tags: List[str],
        data: List[Dict[str, Any]],
        ttl: Optional[float] = None,
    ) -> None:
        key = _make_key(category, sorted(tags))
        payload = json.dumps(data, sort_keys=True, default=str)
        ttl_val = ttl if ttl is not None else self._default_ttl
        now = time.time()
        if self._path:
            with self._lock:
                conn = self._get_conn()
                conn.execute(
                    "INSERT OR REPLACE INTO query_cache "
                    "(cache_key, provider, data_json, created_at, ttl_sec) VALUES (?,?,?,?,?)",
                    (key, provider, payload, now, ttl_val),
                )
                conn.commit()
        else:
            self._memory[("query", f"{key}:{provider}")] = (payload, now, ttl_val)
        self._writes += 1

    # ------------------------------------------------------------------
    # Asset cache
    # ------------------------------------------------------------------

    def get_asset(self, provider: str, asset_id: str) -> Optional[AssetDescriptor]:
        """Return a cached AssetDescriptor, or None."""
        key = _make_key(provider, asset_id)
        now = time.time()
        raw: Optional[str] = None
        if self._path:
            row = self._db_get("asset_cache", key, None)
            if row and now - row[1] < row[2]:
                raw = row[0]
        else:
            entry = self._memory.get(("asset", key))
            if entry and now - entry[1] < entry[2]:
                raw = entry[0]
        if raw:
            self._hits += 1
            return AssetDescriptor.from_json(raw)
        self._misses += 1
        return None

    def set_asset(
        self,
        asset: AssetDescriptor,
        ttl: Optional[float] = None,
    ) -> None:
        key = _make_key(asset.provider, asset.asset_id)
        payload = asset.to_json()
        ttl_val = ttl if ttl is not None else self._default_ttl
        now = time.time()
        if self._path:
            with self._lock:
                conn = self._get_conn()
                conn.execute(
                    "INSERT OR REPLACE INTO asset_cache "
                    "(cache_key, data_json, created_at, ttl_sec) VALUES (?,?,?,?)",
                    (key, payload, now, ttl_val),
                )
                conn.commit()
        else:
            self._memory[("asset", key)] = (payload, now, ttl_val)
        self._writes += 1

    # ------------------------------------------------------------------
    # Ranking cache
    # ------------------------------------------------------------------

    def get_ranking(
        self,
        intent_id: str,
        plan_id: str,
        category: str,
    ) -> Optional[List[Dict[str, Any]]]:
        key = _make_key(intent_id, plan_id, category)
        now = time.time()
        if self._path:
            row = self._db_get("ranking_cache", key, None)
            if row and now - row[1] < row[2]:
                self._hits += 1
                return json.loads(row[0])
        else:
            entry = self._memory.get(("ranking", key))
            if entry and now - entry[1] < entry[2]:
                self._hits += 1
                return json.loads(entry[0])
        self._misses += 1
        return None

    def set_ranking(
        self,
        intent_id: str,
        plan_id: str,
        category: str,
        data: List[Dict[str, Any]],
        ttl: Optional[float] = None,
    ) -> None:
        key = _make_key(intent_id, plan_id, category)
        payload = json.dumps(data, sort_keys=True, default=str)
        ttl_val = ttl if ttl is not None else self._default_ttl
        now = time.time()
        if self._path:
            with self._lock:
                conn = self._get_conn()
                conn.execute(
                    "INSERT OR REPLACE INTO ranking_cache "
                    "(cache_key, data_json, created_at, ttl_sec) VALUES (?,?,?,?)",
                    (key, payload, now, ttl_val),
                )
                conn.commit()
        else:
            self._memory[("ranking", key)] = (payload, now, ttl_val)
        self._writes += 1

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def invalidate_all(self) -> None:
        """Clear all cache entries."""
        if self._path:
            with self._lock:
                conn = self._get_conn()
                for tbl in ("query_cache", "asset_cache", "ranking_cache"):
                    conn.execute(f"DELETE FROM {tbl}")
                conn.commit()
        else:
            self._memory.clear()

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "hits":       self._hits,
            "misses":     self._misses,
            "writes":     self._writes,
            "hit_rate":   round(self._hits / total, 3) if total else 0.0,
            "persistent": self._path is not None,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            try:
                self._conn = self._open()
            except sqlite3.DatabaseError:
                if self._path and Path(self._path).exists():
                    Path(self._path).unlink(missing_ok=True)
                self._conn = self._open()
        return self._conn

    def _open(self) -> sqlite3.Connection:
        if not self._path:
            conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(_DDL)
        conn.commit()
        return conn

    def _db_get(
        self,
        table: str,
        key: str,
        provider: Optional[str],
    ) -> Optional[Tuple[str, float, float]]:
        with self._lock:
            conn = self._get_conn()
            if provider is not None and table == "query_cache":
                row = conn.execute(
                    f"SELECT data_json, created_at, ttl_sec FROM {table} "
                    "WHERE cache_key=? AND provider=?",
                    (key, provider),
                ).fetchone()
            else:
                row = conn.execute(
                    f"SELECT data_json, created_at, ttl_sec FROM {table} "
                    "WHERE cache_key=?",
                    (key,),
                ).fetchone()
        return row  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetCache] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_cache() -> AssetCache:
    """Return the module-level singleton AssetCache."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetCache()
    return _INSTANCE


def reset_asset_cache_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
