"""
Scene Cache + Dirty Scene Tracking
==================================
Two responsibilities, deliberately co-located:

  1. **TTL cache** for DCC scene-state reads (the same scene metadata is read
     many times during a single execution — once per node asking for context).
     Used by `houdini_runtime.scene_context()` and friends to dedupe bridge calls.

  2. **Dirty scene tracking** — the runtime layer's lightweight, in-memory
     ledger of what the current workflow has mutated. The transaction system
     and `hou_mcp_graph_diff` node read this ledger to report structured
     changes back to AI agents without re-querying the DCC.

Public API:
    get_scene_cache() -> SceneCache    (singleton)

    # TTL cache
    SceneCache.get(key) -> Any | None
    SceneCache.set(key, value, ttl_sec=5.0)
    SceneCache.invalidate(prefix="")
    SceneCache.stats() -> dict

    # Dirty tracking
    SceneCache.mark_node_dirty(path)
    SceneCache.mark_node_created(path)
    SceneCache.mark_node_deleted(path)
    SceneCache.mark_node_cooked(path)
    SceneCache.mark_connection_changed(from_path, to_path, in_idx=0)
    SceneCache.mark_flag_changed(path)
    SceneCache.get_dirty_nodes() -> dict
    SceneCache.clear_dirty_state()

Dirty tracking is **lightweight by design** — it stores only paths (and tuples
for connections) in plain Python sets, never the full node state. It never
queries the bridge; callers update it explicitly when they perform mutations.
"""

import threading
import time
from typing import Any, Dict, List, Optional, Set


def _new_dirty_state() -> Dict[str, set]:
    return {
        "modified": set(),
        "created": set(),
        "deleted": set(),
        "cooked": set(),
        "connections_changed": set(),
        "flags_changed": set(),
    }


class SceneCache:
    def __init__(self):
        self._entries: Dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._invalidations = 0

        self._dirty: Dict[str, set] = _new_dirty_state()
        self._dirty_lock = threading.Lock()

        # Graph-state visualization data (Tier 2.5) ----------------------
        # recently_modified: path → timestamp of last mutation
        self._recently_modified: Dict[str, float] = {}
        # transaction_ownership: path → txn_id of last transaction that touched it
        self._transaction_ownership: Dict[str, str] = {}
        # validation_warnings: path → list of warning strings
        self._validation_warnings: Dict[str, List[str]] = {}
        self._viz_lock = threading.Lock()

    # ------------------------------------------------------------------
    # TTL cache
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                del self._entries[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl_sec: float = 5.0) -> None:
        with self._lock:
            self._entries[key] = (time.monotonic() + ttl_sec, value)

    def invalidate(self, prefix: str = "") -> None:
        with self._lock:
            if prefix == "":
                count = len(self._entries)
                self._entries.clear()
            else:
                dead = [k for k in self._entries if k.startswith(prefix)]
                for k in dead:
                    del self._entries[k]
                count = len(dead)
            self._invalidations += count

    def stats(self) -> dict:
        with self._lock:
            cache_stats = {
                "entries": len(self._entries),
                "hits": self._hits,
                "misses": self._misses,
                "invalidations": self._invalidations,
            }
        with self._dirty_lock:
            dirty_stats = {k: len(v) for k, v in self._dirty.items()}
        return {**cache_stats, "dirty": dirty_stats}

    # ------------------------------------------------------------------
    # Dirty scene tracking
    # ------------------------------------------------------------------

    def mark_node_dirty(self, path: str) -> None:
        """Generic parameter / attribute change."""
        if not path:
            return
        with self._dirty_lock:
            self._dirty["modified"].add(path)

    def mark_node_created(self, path: str) -> None:
        if not path:
            return
        with self._dirty_lock:
            self._dirty["created"].add(path)
            # If we previously marked this node as deleted in the same
            # session and it is being re-created, drop the deleted flag.
            self._dirty["deleted"].discard(path)

    def mark_node_deleted(self, path: str) -> None:
        if not path:
            return
        with self._dirty_lock:
            self._dirty["deleted"].add(path)
            # A deleted node is no longer dirty in the other categories.
            self._dirty["created"].discard(path)
            self._dirty["modified"].discard(path)
            self._dirty["cooked"].discard(path)
            self._dirty["flags_changed"].discard(path)

    def mark_node_cooked(self, path: str) -> None:
        if not path:
            return
        with self._dirty_lock:
            self._dirty["cooked"].add(path)

    def mark_connection_changed(self, from_path: str, to_path: str, in_idx: int = 0) -> None:
        """Record a connection that changed. Stored as a tuple to avoid duplicates."""
        if not from_path or not to_path:
            return
        with self._dirty_lock:
            self._dirty["connections_changed"].add((from_path, to_path, int(in_idx)))

    def mark_flag_changed(self, path: str) -> None:
        if not path:
            return
        with self._dirty_lock:
            self._dirty["flags_changed"].add(path)

    def get_dirty_nodes(self) -> Dict[str, List]:
        """Return a JSON-friendly snapshot of the current dirty state.

        Sets are converted to sorted lists so the output is deterministic
        and serialisable for LLM prompts / audit logs.
        """
        with self._dirty_lock:
            out: Dict[str, List] = {}
            for key, value in self._dirty.items():
                if key == "connections_changed":
                    out[key] = sorted(
                        [{"from": f, "to": t, "in": i} for (f, t, i) in value],
                        key=lambda d: (d["to"], d["in"], d["from"]),
                    )
                else:
                    out[key] = sorted(value)
            return out

    def clear_dirty_state(self) -> None:
        with self._dirty_lock:
            self._dirty = _new_dirty_state()

    # ------------------------------------------------------------------
    # Graph-state visualization data (Tier 2.5)
    # ------------------------------------------------------------------

    def record_transaction_ownership(self, paths: List[str], txn_id: str) -> None:
        """Record that `txn_id` is the last transaction to touch each path."""
        if not txn_id:
            return
        now = time.time()
        with self._viz_lock:
            for path in paths:
                if path:
                    self._transaction_ownership[path] = txn_id
                    self._recently_modified[path] = now

    def record_validation_warning(self, path: str, warning: str) -> None:
        """Attach a validation warning to a node path for display/inspection."""
        if not path or not warning:
            return
        with self._viz_lock:
            self._validation_warnings.setdefault(path, []).append(warning)

    def get_graph_visualization_data(self) -> Dict[str, Any]:
        """Return structured visualization metadata (no UI rendering — data only).

        Shape:
            {
                "recently_modified": {path: timestamp, ...},
                "transaction_ownership": {path: txn_id, ...},
                "validation_warnings": {path: [warning, ...], ...},
            }
        """
        with self._viz_lock:
            return {
                "recently_modified": dict(self._recently_modified),
                "transaction_ownership": dict(self._transaction_ownership),
                "validation_warnings": {k: list(v) for k, v in self._validation_warnings.items()},
            }

    def clear_visualization_data(self) -> None:
        """Reset all visualization metadata (e.g. between workflow runs)."""
        with self._viz_lock:
            self._recently_modified.clear()
            self._transaction_ownership.clear()
            self._validation_warnings.clear()

    # ------------------------------------------------------------------
    # Semantic execution lineage (Tier 2.75)
    # ------------------------------------------------------------------

    def record_semantic_execution(self, intent_id: str, txn_id: str, op_count: int) -> None:
        """Append a semantic execution record to the lineage list."""
        if not intent_id:
            return
        with self._viz_lock:
            if not hasattr(self, "_semantic_lineage"):
                self._semantic_lineage: List[Dict[str, Any]] = []
            self._semantic_lineage.append({
                "intent_id": intent_id,
                "txn_id":    txn_id,
                "op_count":  op_count,
                "timestamp": time.time(),
            })

    def get_semantic_lineage(self) -> List[Dict[str, Any]]:
        """Return the list of semantic execution records (newest last)."""
        with self._viz_lock:
            if not hasattr(self, "_semantic_lineage"):
                return []
            return list(self._semantic_lineage)

    def clear_semantic_lineage(self) -> None:
        """Reset semantic execution lineage."""
        with self._viz_lock:
            self._semantic_lineage: List[Dict[str, Any]] = []


_CACHE: Optional[SceneCache] = None


def get_scene_cache() -> SceneCache:
    global _CACHE
    if _CACHE is None:
        _CACHE = SceneCache()
    return _CACHE
