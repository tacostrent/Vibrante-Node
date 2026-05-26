"""
Transaction Manager
===================
Runtime service that wraps a sequence of structured operations into a
transaction with begin / commit / rollback semantics. Sits between AI-generated
plans and the actual DCC mutations:

    AI Plan → Transaction → Validation → Execution → Commit / Rollback

The manager itself is **DCC-agnostic**. It stores operations + snapshots as
opaque dicts, exposes a lifecycle API, and dispatches rollback to per-op-type
handlers registered by DCC runtime modules (`houdini_runtime` registers
Houdini handlers at import time; future `maya_runtime` / `blender_runtime`
modules can register their own).

This module:
  • never imports any DCC bridge directly
  • never executes anything itself — it records what callers tell it
  • is async-safe (one asyncio.Lock guards the registry)
  • holds bounded execution history (default cap = 200 entries)
  • is rollback-tolerant — failed rollbacks are logged but never raised

Public API:
    get_transaction_manager() -> TransactionManager        (singleton)

    await mgr.begin_transaction(name, metadata=None) -> txn_id
    await mgr.record_operation(txn_id, operation)          # post-execution recording
    await mgr.commit_transaction(txn_id) -> dict
    await mgr.rollback_transaction(txn_id) -> dict
    await mgr.get_transaction(txn_id) -> dict | None
    await mgr.list_transactions() -> list
    await mgr.clear_finished_transactions() -> int

    # Registration (called by DCC runtime modules at import time)
    register_rollback_handler(op_type, handler)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional


# Recorded-operation shape (the "operation" arg passed to record_operation):
#   {
#       "op":        str,               # e.g. "create_node", "set_parms"
#       "params":    dict,              # the original op params
#       "result":    Any,               # what executor returned
#       "snapshot":  dict,              # pre-state for rollback (op-specific)
#       "status":    "ok" | "failed",   # default "ok" if omitted
#       "error":     str (optional),
#       "dirty":     list[str] (optional),  # paths this op mutated
#       "timestamp": float (optional),  # set by record_operation if missing
#   }

RollbackHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]

_ROLLBACK_HANDLERS: Dict[str, RollbackHandler] = {}


def register_rollback_handler(op_type: str, handler: RollbackHandler) -> None:
    """Register an async rollback function for an operation type.

    The handler receives the recorded operation dict (with `params`, `result`,
    and `snapshot` keys) and must return a dict describing the rollback
    outcome (at minimum `{"ok": bool, "error"?: str}`). Handlers MUST NOT
    raise — catch internal errors and report them via the return dict.

    DCC runtime modules register their handlers at import time.
    """
    if not op_type:
        raise ValueError("op_type is required")
    if not callable(handler):
        raise TypeError("handler must be callable (async)")
    _ROLLBACK_HANDLERS[op_type] = handler


def list_rollback_handlers() -> List[str]:
    """Diagnostic helper: which op types have a registered rollback handler."""
    return sorted(_ROLLBACK_HANDLERS.keys())


_VALID_STATUSES = {"pending", "committed", "rolled_back", "failed"}


def _new_transaction(name: str, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "created_at": time.time(),
        "status": "pending",
        "operations": [],
        "snapshots": [],         # alias view onto operations[*]["snapshot"]
        "metadata": dict(metadata or {}),
        "dirty_nodes": [],
        "errors": [],
        "committed_at": None,
        "rolled_back_at": None,
    }


class TransactionManager:
    """In-memory transaction registry + bounded execution history."""

    HISTORY_CAP = 200

    def __init__(self):
        self._transactions: Dict[str, Dict[str, Any]] = {}
        self._history: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def begin_transaction(
        self, name: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        if not name:
            raise ValueError("transaction name is required")
        txn = _new_transaction(name, metadata)
        async with self._lock:
            self._transactions[txn["id"]] = txn
            self._append_history(txn["id"], "begin", "ok", {"name": name})
        return txn["id"]

    async def record_operation(self, transaction_id: str, operation: Dict[str, Any]) -> None:
        if not isinstance(operation, dict):
            raise TypeError("operation must be a dict")
        if "op" not in operation:
            raise ValueError("operation requires an 'op' field")
        async with self._lock:
            txn = self._transactions.get(transaction_id)
            if txn is None:
                raise KeyError(f"unknown transaction: {transaction_id}")
            if txn["status"] != "pending":
                raise RuntimeError(
                    f"cannot record into a {txn['status']} transaction: {transaction_id}"
                )
            normalized = dict(operation)
            normalized.setdefault("timestamp", time.time())
            normalized.setdefault("status", "ok")
            normalized.setdefault("snapshot", {})
            normalized.setdefault("params", {})
            normalized.setdefault("result", None)
            txn["operations"].append(normalized)
            txn["snapshots"].append(normalized["snapshot"])
            for path in normalized.get("dirty") or []:
                if path and path not in txn["dirty_nodes"]:
                    txn["dirty_nodes"].append(path)
            if normalized.get("status") == "failed":
                err = normalized.get("error") or "unknown error"
                txn["errors"].append({"op": normalized["op"], "error": err})
            self._append_history(
                transaction_id, "record", normalized["status"],
                {"op": normalized["op"]},
            )

    async def commit_transaction(self, transaction_id: str) -> Dict[str, Any]:
        async with self._lock:
            txn = self._transactions.get(transaction_id)
            if txn is None:
                raise KeyError(f"unknown transaction: {transaction_id}")
            if txn["status"] != "pending":
                raise RuntimeError(
                    f"cannot commit a {txn['status']} transaction: {transaction_id}"
                )
            txn["status"] = "committed"
            txn["committed_at"] = time.time()
            self._append_history(transaction_id, "commit", "ok", {
                "operations": len(txn["operations"]),
            })
            return self._public_view(txn)

    async def rollback_transaction(self, transaction_id: str) -> Dict[str, Any]:
        async with self._lock:
            txn = self._transactions.get(transaction_id)
            if txn is None:
                raise KeyError(f"unknown transaction: {transaction_id}")
            if txn["status"] not in ("pending", "failed"):
                raise RuntimeError(
                    f"cannot rollback a {txn['status']} transaction: {transaction_id}"
                )
            # Snapshot the operations list so we release the lock during
            # rollback handler calls (handlers may await on the bridge).
            operations = list(txn["operations"])

        rollback_results: List[Dict[str, Any]] = []
        rollback_errors: List[Dict[str, Any]] = []

        # Reverse order so a graph "create A → create B → connect A→B" is
        # undone as "disconnect → delete B → delete A".
        for recorded in reversed(operations):
            op_type = recorded.get("op", "")
            handler = _ROLLBACK_HANDLERS.get(op_type)
            if handler is None:
                rollback_errors.append({
                    "op": op_type,
                    "error": f"no rollback handler registered for op '{op_type}'",
                })
                continue
            try:
                outcome = await handler(recorded)
                if not isinstance(outcome, dict):
                    outcome = {"ok": True, "result": outcome}
                rollback_results.append({"op": op_type, "outcome": outcome})
                if not outcome.get("ok", True):
                    rollback_errors.append({
                        "op": op_type,
                        "error": outcome.get("error", "rollback returned ok=False"),
                    })
            except Exception as exc:  # noqa: BLE001
                # Rollback must never crash the runtime — capture and continue.
                rollback_errors.append({"op": op_type, "error": f"{type(exc).__name__}: {exc}"})

        async with self._lock:
            txn = self._transactions.get(transaction_id)
            if txn is None:
                # Extremely unlikely, but handle the race where a concurrent
                # clear removed the txn between our two lock windows.
                return {
                    "id": transaction_id,
                    "status": "rolled_back",
                    "rollback_results": rollback_results,
                    "rollback_errors": rollback_errors,
                }
            txn["status"] = "rolled_back"
            txn["rolled_back_at"] = time.time()
            txn["errors"].extend(rollback_errors)
            self._append_history(transaction_id, "rollback", "ok" if not rollback_errors else "partial", {
                "rolled_back": len(rollback_results),
                "errors": len(rollback_errors),
            })
            view = self._public_view(txn)
            view["rollback_results"] = rollback_results
            view["rollback_errors"] = rollback_errors
            return view

    async def mark_failed(self, transaction_id: str, error: str) -> None:
        """Mark a still-pending transaction as failed without rolling back."""
        async with self._lock:
            txn = self._transactions.get(transaction_id)
            if txn is None:
                raise KeyError(f"unknown transaction: {transaction_id}")
            if txn["status"] == "pending":
                txn["status"] = "failed"
                txn["errors"].append({"op": "<transaction>", "error": error})
                self._append_history(transaction_id, "failed", "ok", {"error": error})

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    async def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            txn = self._transactions.get(transaction_id)
            return self._public_view(txn) if txn is not None else None

    async def list_transactions(self) -> List[Dict[str, Any]]:
        async with self._lock:
            return [self._public_view(t) for t in self._transactions.values()]

    async def clear_finished_transactions(self) -> int:
        async with self._lock:
            removed = 0
            for txn_id in list(self._transactions.keys()):
                if self._transactions[txn_id]["status"] in ("committed", "rolled_back", "failed"):
                    del self._transactions[txn_id]
                    removed += 1
            return removed

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Synchronous accessor for the bounded execution history."""
        return list(self._history[-limit:])

    def clear_history(self) -> None:
        self._history.clear()

    def get_graph_visualization_data(self) -> Dict[str, Any]:
        """Return structured data for graph-state visualization (no UI rendering).

        Shape:
            {
                "pending_count": int,
                "committed_count": int,
                "rolled_back_count": int,
                "failed_count": int,
                "rollback_states": {txn_id: status, ...},
                "recent_names": [name, ...]   # last 5 transaction names
            }
        """
        txns = list(self._transactions.values())
        rollback_states = {t["id"]: t["status"] for t in txns}
        counts: Dict[str, int] = {"pending": 0, "committed": 0, "rolled_back": 0, "failed": 0}
        for t in txns:
            status = t.get("status", "pending")
            if status in counts:
                counts[status] += 1
        recent = [t["name"] for t in sorted(txns, key=lambda t: t["created_at"], reverse=True)[:5]]
        return {
            "pending_count": counts["pending"],
            "committed_count": counts["committed"],
            "rolled_back_count": counts["rolled_back"],
            "failed_count": counts["failed"],
            "rollback_states": rollback_states,
            "recent_names": recent,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append_history(
        self, transaction_id: str, action: str, status: str, details: Dict[str, Any]
    ) -> None:
        # Caller already holds self._lock — never await here.
        entry = {
            "timestamp": time.time(),
            "transaction_id": transaction_id,
            "action": action,
            "status": status,
            "details": dict(details or {}),
        }
        self._history.append(entry)
        if len(self._history) > self.HISTORY_CAP:
            self._history = self._history[-self.HISTORY_CAP:]

    @staticmethod
    def _public_view(txn: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": txn["id"],
            "name": txn["name"],
            "created_at": txn["created_at"],
            "committed_at": txn.get("committed_at"),
            "rolled_back_at": txn.get("rolled_back_at"),
            "status": txn["status"],
            "operations": list(txn["operations"]),
            "snapshots": list(txn["snapshots"]),
            "metadata": dict(txn["metadata"]),
            "dirty_nodes": list(txn["dirty_nodes"]),
            "errors": list(txn["errors"]),
        }


_MANAGER: Optional[TransactionManager] = None


def get_transaction_manager() -> TransactionManager:
    """Return the process-wide TransactionManager singleton."""
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = TransactionManager()
    return _MANAGER


def reset_transaction_manager_for_tests() -> None:
    """Drop the singleton — for test isolation only.

    Production code must never call this. Tests use it via fixtures to ensure
    a clean manager + clean handler registry between cases.
    """
    global _MANAGER
    _MANAGER = None
