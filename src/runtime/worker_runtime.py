"""
Worker Runtime (Tier 4)
========================
Worker pool management for distributed orchestration.  Workers register
with capabilities and a heartbeat mechanism; the pool matches tasks to
workers by capability and load.

Workers are logical units — they may represent local processes, remote
machines, farm slots, or cloud workers.  The WorkerRuntime does not
manage actual network connections; it provides the pool accounting layer
that DistributedRuntime and WorkflowFederation consume.

Worker lifecycle:
    registered → idle ↔ busy → offline

Stale detection:
    Workers that have not sent a heartbeat within `timeout_sec` (default 60s)
    are marked "stale". check_stale_workers() returns their ids.

Public API:
    get_worker_runtime() -> WorkerRuntime   (singleton)
    reset_worker_runtime_for_tests()

    WorkerRuntime.register_worker(name, capabilities, endpoint, max_load) -> str
    WorkerRuntime.deregister_worker(worker_id) -> bool
    WorkerRuntime.update_heartbeat(worker_id) -> bool
    WorkerRuntime.acquire_worker(required_capabilities) -> str | None
    WorkerRuntime.release_worker(worker_id) -> bool
    WorkerRuntime.find_workers_for(required_capabilities) -> list[str]
    WorkerRuntime.check_stale_workers(timeout_sec) -> list[str]
    WorkerRuntime.get_worker(worker_id) -> dict | None
    WorkerRuntime.list_workers(status) -> list[dict]
    WorkerRuntime.stats() -> dict
"""

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

WORKER_STATUSES = frozenset({"idle", "busy", "offline"})

_DEFAULT_HEARTBEAT_TIMEOUT = 60.0


class WorkerRuntime:
    """Worker pool accounting layer for distributed orchestration."""

    def __init__(self) -> None:
        self._lock    = threading.Lock()
        self._workers: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_worker(
        self,
        name:         str,
        capabilities: Optional[List[str]] = None,
        endpoint:     str = "local://",
        max_load:     int = 4,
    ) -> str:
        """Register a worker and return its worker_id."""
        if not name:
            raise ValueError("Worker name must be non-empty")
        now       = time.time()
        worker_id = str(uuid.uuid4())
        with self._lock:
            self._workers[worker_id] = {
                "id":             worker_id,
                "name":           name,
                "capabilities":   list(capabilities or []),
                "endpoint":       endpoint,
                "max_load":       max(1, int(max_load)),
                "current_load":   0,
                "status":         "idle",
                "registered_at":  now,
                "last_heartbeat": now,
            }
        return worker_id

    def deregister_worker(self, worker_id: str) -> bool:
        with self._lock:
            if worker_id in self._workers:
                del self._workers[worker_id]
                return True
        return False

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def update_heartbeat(self, worker_id: str) -> bool:
        """Refresh the heartbeat timestamp.  Returns True if worker exists."""
        with self._lock:
            w = self._workers.get(worker_id)
            if w is None:
                return False
            w["last_heartbeat"] = time.time()
            if w["status"] == "offline":
                w["status"] = "idle" if w["current_load"] == 0 else "busy"
            return True

    # ------------------------------------------------------------------
    # Acquire / release
    # ------------------------------------------------------------------

    def acquire_worker(
        self,
        required_capabilities: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Atomically acquire the least-loaded matching worker.

        Returns worker_id on success, or None if none available.
        """
        required = list(required_capabilities or [])
        with self._lock:
            candidates = [
                w for w in self._workers.values()
                if w["status"] != "offline"
                and w["current_load"] < w["max_load"]
                and all(c in w["capabilities"] for c in required)
            ]
            if not candidates:
                return None
            best = min(candidates,
                       key=lambda w: w["current_load"] / max(1, w["max_load"]))
            best["current_load"] += 1
            best["status"] = "busy" if best["current_load"] >= best["max_load"] else "idle"
            # Partial load → still idle but reserved slot counted
            best["status"] = "busy"
            return best["id"]

    def release_worker(self, worker_id: str) -> bool:
        """Decrement load for a worker.  Returns True if found."""
        with self._lock:
            w = self._workers.get(worker_id)
            if w is None:
                return False
            w["current_load"] = max(0, w["current_load"] - 1)
            w["status"] = "idle" if w["current_load"] == 0 else "busy"
            return True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def find_workers_for(
        self,
        required_capabilities: Optional[List[str]] = None,
        status_filter:         Optional[str] = None,
    ) -> List[str]:
        """Return worker_ids matching capability requirements."""
        required = list(required_capabilities or [])
        with self._lock:
            workers = list(self._workers.values())
        results = []
        for w in workers:
            if status_filter and w["status"] != status_filter:
                continue
            if all(c in w["capabilities"] for c in required):
                results.append(w["id"])
        return sorted(results)

    def check_stale_workers(
        self,
        timeout_sec: float = _DEFAULT_HEARTBEAT_TIMEOUT,
    ) -> List[str]:
        """Return worker_ids whose last heartbeat is older than timeout_sec.

        Also marks them as offline internally.
        """
        cutoff = time.time() - timeout_sec
        stale: List[str] = []
        with self._lock:
            for worker_id, w in self._workers.items():
                if w["last_heartbeat"] < cutoff and w["status"] != "offline":
                    w["status"] = "offline"
                    stale.append(worker_id)
        return sorted(stale)

    def get_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            w = self._workers.get(worker_id)
            return dict(w) if w else None

    def list_workers(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            workers = list(self._workers.values())
        if status:
            workers = [w for w in workers if w["status"] == status]
        return [dict(w) for w in sorted(workers, key=lambda w: w["registered_at"])]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_status: Dict[str, int] = {}
            total_load = 0
            total_cap  = 0
            for w in self._workers.values():
                s = w["status"]
                by_status[s] = by_status.get(s, 0) + 1
                total_load += w["current_load"]
                total_cap  += w["max_load"]
            return {
                "total_workers":   len(self._workers),
                "by_status":       by_status,
                "total_load":      total_load,
                "total_capacity":  total_cap,
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[WorkerRuntime] = None
_LOCK = threading.Lock()


def get_worker_runtime() -> WorkerRuntime:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = WorkerRuntime()
        return _INSTANCE


def reset_worker_runtime_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
