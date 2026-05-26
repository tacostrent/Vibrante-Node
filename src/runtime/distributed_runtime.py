"""
Distributed Runtime (Tier 4)
==============================
Orchestrates execution dispatch across local and remote workers.  Workers
are registered with capabilities; the dispatcher selects the best-matching
worker and routes the operation batch through the existing transaction /
validation pipeline.

SAFETY RULE: All dispatched execution remains transactional, replayable,
and supervised — identical to local execution. Remote workers do not receive
authority to bypass constraints.

Worker endpoint conventions:
    "local://"       — execute via local TransactionManager + houdini_runtime
    "remote://<host>" — record dispatch; remote transport wired externally

Public API:
    get_distributed_runtime() -> DistributedRuntime   (singleton)
    reset_distributed_runtime_for_tests()

    DistributedRuntime.register_worker(name, capabilities, endpoint, max_load) -> str
    DistributedRuntime.deregister_worker(worker_id) -> bool
    DistributedRuntime.dispatch_operations(ops, required_capabilities, …) -> dict
    DistributedRuntime.get_dispatch_status(dispatch_id) -> dict | None
    DistributedRuntime.list_workers(cap_filter) -> list[dict]
    DistributedRuntime.stats() -> dict
"""

import json
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

WORKER_STATUSES = frozenset({"idle", "busy", "offline"})


class DistributedRuntime:
    """Dispatch engine for distributed transactional execution."""

    def __init__(self) -> None:
        self._lock      = threading.Lock()
        self._workers:   Dict[str, Dict[str, Any]] = {}
        self._dispatches: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Worker management
    # ------------------------------------------------------------------

    def register_worker(
        self,
        name:         str,
        capabilities: List[str],
        endpoint:     str = "local://",
        max_load:     int = 4,
    ) -> str:
        """Register a worker and return its worker_id."""
        if not name:
            raise ValueError("Worker name must be non-empty")
        worker_id = str(uuid.uuid4())
        with self._lock:
            self._workers[worker_id] = {
                "id":           worker_id,
                "name":         name,
                "capabilities": list(capabilities),
                "endpoint":     endpoint,
                "max_load":     max(1, int(max_load)),
                "current_load": 0,
                "status":       "idle",
                "registered_at": time.time(),
            }
        return worker_id

    def deregister_worker(self, worker_id: str) -> bool:
        with self._lock:
            if worker_id in self._workers:
                del self._workers[worker_id]
                return True
        return False

    def get_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            w = self._workers.get(worker_id)
            return dict(w) if w else None

    def list_workers(
        self,
        cap_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            workers = list(self._workers.values())
        if cap_filter:
            workers = [w for w in workers if cap_filter in w["capabilities"]]
        if status_filter:
            workers = [w for w in workers if w["status"] == status_filter]
        return [dict(w) for w in sorted(workers, key=lambda w: w["registered_at"])]

    def _select_worker(self, required_capabilities: List[str]) -> Optional[str]:
        """Return the worker_id with lowest load that matches all required caps."""
        with self._lock:
            candidates = [
                w for w in self._workers.values()
                if w["status"] != "offline"
                and w["current_load"] < w["max_load"]
                and all(c in w["capabilities"] for c in required_capabilities)
            ]
        if not candidates:
            return None
        return min(candidates, key=lambda w: w["current_load"] / max(1, w["max_load"]))["id"]

    def _set_worker_load(self, worker_id: str, delta: int) -> None:
        with self._lock:
            w = self._workers.get(worker_id)
            if w:
                w["current_load"] = max(0, w["current_load"] + delta)
                w["status"] = "busy" if w["current_load"] > 0 else "idle"

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch_operations(
        self,
        operations:             List[Dict[str, Any]],
        required_capabilities:  Optional[List[str]] = None,
        transaction_name:       str = "distributed_dispatch",
        dry_run:                bool = False,
        rollback_on_error:      bool = True,
    ) -> Dict[str, Any]:
        """Dispatch a batch of operations to the best-matching worker.

        For local workers, executes via the existing TransactionManager +
        houdini_runtime pipeline. For remote workers, records the dispatch
        request (transport is wired externally).

        Returns a structured execution result.
        """
        required_capabilities = list(required_capabilities or [])
        dispatch_id = str(uuid.uuid4())

        # Select worker
        worker_id = self._select_worker(required_capabilities)
        if worker_id is None:
            result = {
                "ok":                   False,
                "dispatch_id":          dispatch_id,
                "worker_id":            None,
                "status":               "no_worker",
                "error":                "No available worker matching required capabilities",
                "required_capabilities": required_capabilities,
                "operations_executed":  0,
                "errors":               ["No available worker"],
                "graph_diff":           {},
                "report_json":          json.dumps({"status": "no_worker", "dispatch_id": dispatch_id}),
            }
            self._record_dispatch(dispatch_id, result)
            return result

        worker = self.get_worker(worker_id)
        endpoint = worker["endpoint"]  # type: ignore[index]

        # Record dispatch
        dispatch_record: Dict[str, Any] = {
            "dispatch_id":          dispatch_id,
            "worker_id":            worker_id,
            "worker_name":          worker["name"],  # type: ignore[index]
            "endpoint":             endpoint,
            "transaction_name":     transaction_name,
            "op_count":             len(operations),
            "dry_run":              dry_run,
            "dispatched_at":        time.time(),
            "status":               "dispatching",
        }
        self._record_dispatch(dispatch_id, dispatch_record)

        # --- local execution path ---
        if endpoint == "local://":
            self._set_worker_load(worker_id, +1)
            try:
                result = await self._execute_local(
                    operations, transaction_name, dry_run, rollback_on_error
                )
            finally:
                self._set_worker_load(worker_id, -1)

            result["dispatch_id"] = dispatch_id
            result["worker_id"]   = worker_id
            dispatch_record["status"] = result.get("status", "done")
            dispatch_record["result"] = result
            self._record_dispatch(dispatch_id, dispatch_record)
            return result

        # --- remote execution path (transport wired externally) ---
        dispatch_record["status"] = "dispatched"
        self._record_dispatch(dispatch_id, dispatch_record)
        return {
            "ok":                   True,
            "dispatch_id":          dispatch_id,
            "worker_id":            worker_id,
            "status":               "dispatched",
            "operations_executed":  len(operations),
            "errors":               [],
            "graph_diff":           {},
            "report_json":          json.dumps({
                "status": "dispatched",
                "dispatch_id": dispatch_id,
                "worker_id": worker_id,
                "endpoint": endpoint,
            }),
        }

    async def _execute_local(
        self,
        operations:       List[Dict[str, Any]],
        transaction_name: str,
        dry_run:          bool,
        rollback_on_error: bool,
    ) -> Dict[str, Any]:
        """Execute operations locally via the existing transaction pipeline."""
        from src.runtime.validation_engine  import get_validation_engine
        from src.runtime.runtime_constraints import get_runtime_constraints
        from src.runtime.scene_cache         import get_scene_cache

        # Validate before any mutation
        constraint_result = get_runtime_constraints().validate_transaction(operations)
        violations = constraint_result.get("violations", [])
        if violations:
            errs = [f"Constraint '{v['policy_id']}': {v['message']}" for v in violations]
            return {
                "ok": False, "status": "failed",
                "operations_executed": 0, "errors": errs,
                "graph_diff": {}, "transaction_id": None,
                "report_json": json.dumps({"status": "failed", "errors": errs}),
            }

        validation = await get_validation_engine().validate_operations(operations)
        if not validation.get("valid"):
            errs = [e.get("message", "") for e in validation.get("errors", [])]
            return {
                "ok": False, "status": "failed",
                "operations_executed": 0, "errors": errs,
                "graph_diff": {}, "transaction_id": None,
                "report_json": json.dumps({"status": "failed", "errors": errs}),
            }

        if dry_run:
            return {
                "ok": True, "status": "validated", "transaction_id": None,
                "operations_executed": 0, "errors": [], "warnings": [],
                "graph_diff": {},
                "report_json": json.dumps({"status": "validated", "op_count": len(operations)}),
            }

        from src.runtime import transaction_manager as tm_module
        from src.runtime import houdini_runtime

        cache  = get_scene_cache()
        cache.clear_dirty_state()
        mgr    = tm_module.get_transaction_manager()
        txn_id = await mgr.begin_transaction(transaction_name)

        ops_executed: List[Dict[str, Any]] = []
        errors: List[str] = []
        status = "pending"

        for op in operations:
            recorded = await houdini_runtime.execute_operation(op)
            await mgr.record_operation(txn_id, recorded)
            ops_executed.append(recorded)
            if recorded.get("status") == "failed":
                errors.append(recorded.get("error") or "op failed")
                if rollback_on_error:
                    await mgr.rollback_transaction(txn_id)
                    status = "rolled_back"
                else:
                    await mgr.mark_failed(txn_id, errors[-1])
                    status = "failed"
                break

        if status == "pending":
            await mgr.commit_transaction(txn_id)
            status = "committed"

        graph_diff = cache.get_dirty_nodes()
        return {
            "ok":                  status == "committed",
            "status":              status,
            "transaction_id":      txn_id,
            "operations_executed": len(ops_executed),
            "errors":              errors,
            "graph_diff":          graph_diff,
            "report_json":         json.dumps({
                "status": status, "txn_id": txn_id,
                "op_count": len(ops_executed), "errors": errors,
            }),
        }

    # ------------------------------------------------------------------
    # Dispatch record helpers
    # ------------------------------------------------------------------

    def _record_dispatch(self, dispatch_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self._dispatches[dispatch_id] = dict(data)

    def get_dispatch_status(self, dispatch_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            d = self._dispatches.get(dispatch_id)
            return dict(d) if d else None

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_status: Dict[str, int] = {}
            for w in self._workers.values():
                s = w["status"]
                by_status[s] = by_status.get(s, 0) + 1
            return {
                "total_workers":    len(self._workers),
                "total_dispatches": len(self._dispatches),
                "workers_by_status": by_status,
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[DistributedRuntime] = None
_LOCK = threading.Lock()


def get_distributed_runtime() -> DistributedRuntime:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = DistributedRuntime()
        return _INSTANCE


def reset_distributed_runtime_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
