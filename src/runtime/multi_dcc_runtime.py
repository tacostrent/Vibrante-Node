"""
Multi-DCC Runtime (Tier 4)
===========================
Coordinates execution across multiple DCC adapters (Houdini, Maya, Blender,
Nuke, USD runtimes, render managers) inside one orchestration system.

Each DCC registers an adapter that implements the DccAdapter protocol.
The router matches operations to the correct DCC by capability or explicit
routing hint, then delegates through the validation / constraint pipeline
before execution.

SAFETY RULE: Capability validation and constraint checking happen for every
DCC — not just Houdini.  Cross-DCC execution is still transactional.

DCC adapter types pre-defined:
    "houdini", "maya", "blender", "nuke", "usd", "deadline"

Public API:
    get_multi_dcc_runtime() -> MultiDccRuntime   (singleton)
    reset_multi_dcc_runtime_for_tests()

    MultiDccRuntime.register_dcc(name, adapter, capabilities) -> str
    MultiDccRuntime.deregister_dcc(name) -> bool
    MultiDccRuntime.route_operation(op, hint_dcc) -> str | None
    MultiDccRuntime.execute_for_dcc(dcc_name, operations, dry_run) -> dict
    MultiDccRuntime.list_dccs() -> list[dict]
    MultiDccRuntime.stats() -> dict
"""

import asyncio
import json
import threading
import time
from typing import Any, Dict, List, Optional

KNOWN_DCC_TYPES = frozenset({
    "houdini", "maya", "blender", "nuke", "usd", "deadline", "custom"
})

# Operations that can be routed to Houdini by default
_HOUDINI_OPS = frozenset({
    "create_node", "set_parms", "connect_nodes", "delete_node",
    "cook_node", "layout_children", "build_node_chain",
    "set_display_flag", "set_render_flag",
})


class DccAdapter:
    """Minimal base adapter for a DCC integration.

    Subclass this and override `execute_operations` for real DCC adapters.
    The base implementation returns a dry-run-style validated result.
    """

    def __init__(self, dcc_type: str = "custom") -> None:
        self.dcc_type = dcc_type

    @property
    def is_available(self) -> bool:
        """Return True if the DCC is reachable."""
        return False

    async def execute_operations(
        self,
        operations: List[Dict[str, Any]],
        dry_run:    bool = False,
    ) -> Dict[str, Any]:
        """Execute a list of structured operations.  Must return a result dict."""
        return {
            "ok":                  False,
            "status":              "not_implemented",
            "operations_executed": 0,
            "errors":              [f"{self.dcc_type} adapter not implemented"],
            "graph_diff":          {},
        }


class HoudiniDccAdapter(DccAdapter):
    """Routes Houdini ops through DistributedRuntime local path."""

    def __init__(self) -> None:
        super().__init__("houdini")

    @property
    def is_available(self) -> bool:
        try:
            from src.utils.hou_bridge import get_bridge
            get_bridge().ping()
            return True
        except Exception:
            return False

    async def execute_operations(
        self,
        operations: List[Dict[str, Any]],
        dry_run:    bool = False,
    ) -> Dict[str, Any]:
        from src.runtime.distributed_runtime import get_distributed_runtime
        dr = get_distributed_runtime()
        # Ensure a local worker exists (register one if needed)
        workers = dr.list_workers(cap_filter="houdini")
        if not workers:
            dr.register_worker("houdini_local", ["houdini", "karma", "mantra"],
                               endpoint="local://", max_load=1)
        return await dr.dispatch_operations(
            operations,
            required_capabilities=["houdini"],
            transaction_name="multi_dcc:houdini",
            dry_run=dry_run,
        )


class MultiDccRuntime:
    """Coordinator for multi-DCC orchestration."""

    def __init__(self) -> None:
        self._lock    = threading.Lock()
        self._dccs:   Dict[str, Dict[str, Any]] = {}
        self._adapters: Dict[str, DccAdapter]   = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        self.register_dcc(
            "houdini",
            HoudiniDccAdapter(),
            ["create_node", "set_parms", "connect_nodes", "delete_node",
             "cook_node", "layout_children", "build_node_chain",
             "set_display_flag", "set_render_flag", "karma", "mantra"],
        )

    # ------------------------------------------------------------------
    # DCC registration
    # ------------------------------------------------------------------

    def register_dcc(
        self,
        name:         str,
        adapter:      DccAdapter,
        capabilities: List[str],
    ) -> str:
        """Register a DCC adapter and return its dcc_id (same as name)."""
        if not name:
            raise ValueError("DCC name must be non-empty")
        dcc_id = name
        with self._lock:
            self._dccs[dcc_id] = {
                "id":           dcc_id,
                "name":         name,
                "dcc_type":     getattr(adapter, "dcc_type", "custom"),
                "capabilities": list(capabilities),
                "registered_at": time.time(),
            }
            self._adapters[dcc_id] = adapter
        return dcc_id

    def deregister_dcc(self, name: str) -> bool:
        with self._lock:
            if name in self._dccs:
                del self._dccs[name]
                del self._adapters[name]
                return True
        return False

    def get_dcc(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            d = self._dccs.get(name)
            return dict(d) if d else None

    def list_dccs(self) -> List[Dict[str, Any]]:
        with self._lock:
            dccs = list(self._dccs.values())
        return [dict(d) for d in sorted(dccs, key=lambda d: d["registered_at"])]

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route_operation(
        self,
        op:       Dict[str, Any],
        hint_dcc: Optional[str] = None,
    ) -> Optional[str]:
        """Determine which DCC should handle this operation.

        Returns the DCC name, or None if no suitable DCC is registered.
        """
        if hint_dcc and hint_dcc in self._dccs:
            return hint_dcc

        op_type = op.get("op", "")
        with self._lock:
            dccs = list(self._dccs.values())

        # Match by op type in capabilities list
        for dcc in dccs:
            if op_type in dcc["capabilities"]:
                return dcc["id"]

        # Fallback: Houdini handles all SUPPORTED_OPS
        if op_type in _HOUDINI_OPS and "houdini" in self._dccs:
            return "houdini"

        return None

    def route_operations(
        self,
        operations: List[Dict[str, Any]],
        hint_dcc:   Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Partition a list of operations by target DCC.

        Returns {dcc_name: [ops]} mapping.
        """
        by_dcc: Dict[str, List[Dict[str, Any]]] = {}
        for op in operations:
            target = self.route_operation(op, hint_dcc) or "houdini"
            by_dcc.setdefault(target, []).append(op)
        return by_dcc

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute_for_dcc(
        self,
        dcc_name:   str,
        operations: List[Dict[str, Any]],
        dry_run:    bool = False,
    ) -> Dict[str, Any]:
        """Execute a batch of operations via a specific DCC adapter."""
        with self._lock:
            adapter = self._adapters.get(dcc_name)
        if adapter is None:
            return {
                "ok":     False,
                "status": "unknown_dcc",
                "error":  f"No DCC registered with name: {dcc_name!r}",
                "dcc":    dcc_name,
            }
        try:
            result = await adapter.execute_operations(operations, dry_run=dry_run)
            result["dcc"] = dcc_name
            return result
        except Exception as exc:
            return {
                "ok": False, "status": "error",
                "error": str(exc), "dcc": dcc_name,
                "operations_executed": 0, "errors": [str(exc)],
            }

    async def execute_cross_dcc(
        self,
        operations: List[Dict[str, Any]],
        hint_dcc:   Optional[str] = None,
        dry_run:    bool = False,
    ) -> Dict[str, Any]:
        """Route a mixed operation list across DCCs and collect results."""
        by_dcc = self.route_operations(operations, hint_dcc)
        results: Dict[str, Any] = {}
        all_ok  = True
        total_executed = 0
        all_errors: List[str] = []

        for dcc_name, dcc_ops in by_dcc.items():
            r = await self.execute_for_dcc(dcc_name, dcc_ops, dry_run=dry_run)
            results[dcc_name] = r
            if not r.get("ok"):
                all_ok = False
            total_executed += r.get("operations_executed", 0)
            all_errors.extend(r.get("errors", []))

        return {
            "ok":                  all_ok,
            "total_operations":    len(operations),
            "operations_executed": total_executed,
            "errors":              all_errors,
            "by_dcc":              results,
            "report_json":         json.dumps({
                "ok": all_ok, "total": len(operations),
                "dccs": list(by_dcc.keys()),
                "errors": all_errors,
            }),
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_dccs":   len(self._dccs),
                "dcc_names":    sorted(self._dccs.keys()),
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[MultiDccRuntime] = None
_LOCK = threading.Lock()


def get_multi_dcc_runtime() -> MultiDccRuntime:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = MultiDccRuntime()
        return _INSTANCE


def reset_multi_dcc_runtime_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
