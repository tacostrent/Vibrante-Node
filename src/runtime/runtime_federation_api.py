"""
Runtime Federation API (Tier 4)
=================================
Provides runtime-to-runtime communication: peer discovery, capability
exchange, and coordinated execution routing between runtimes.

A "runtime" in this context is any Vibrante-Node instance (local, remote,
farm node, cloud worker) participating in a federated orchestration network.
The API manages peer registration, capability exchange, and dispatches
execution requests to peers via the distributed runtime layer.

Runtime types:
    "local"  — the current process
    "remote" — another host reachable via external transport
    "farm"   — a render farm / task queue node
    "cloud"  — a cloud-hosted runtime

SAFETY RULE: Execution requests forwarded to peer runtimes are always
wrapped in the distributed runtime dispatch layer — never raw bridge calls.

Public API:
    get_runtime_federation_api() -> RuntimeFederationApi   (singleton)
    reset_runtime_federation_api_for_tests()

    RuntimeFederationApi.register_runtime(name, endpoint, capabilities, runtime_type) -> str
    RuntimeFederationApi.deregister_runtime(runtime_id) -> bool
    RuntimeFederationApi.discover_capabilities(runtime_id) -> list[dict]
    RuntimeFederationApi.exchange_capabilities(runtime_id, our_capabilities) -> dict
    RuntimeFederationApi.request_execution(runtime_id, operations, transaction_id) -> dict (async)
    RuntimeFederationApi.update_runtime_heartbeat(runtime_id) -> bool
    RuntimeFederationApi.list_runtimes(runtime_type) -> list[dict]
    RuntimeFederationApi.get_runtime_status(runtime_id) -> dict | None
    RuntimeFederationApi.stats() -> dict
"""

import json
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

RUNTIME_TYPES = frozenset({"local", "remote", "farm", "cloud"})


class RuntimeFederationApi:
    """Runtime-to-runtime communication protocol for federated orchestration."""

    def __init__(self) -> None:
        self._lock      = threading.Lock()
        self._runtimes: Dict[str, Dict[str, Any]] = {}
        self._exchanges: List[Dict[str, Any]]      = []
        self._register_local()

    def _register_local(self) -> None:
        """Auto-register the local runtime on init."""
        local_id = "local"
        with self._lock:
            self._runtimes[local_id] = {
                "id":              local_id,
                "name":            "local",
                "endpoint":        "local://",
                "capabilities":    self._get_local_capabilities(),
                "runtime_type":    "local",
                "status":          "online",
                "registered_at":   time.time(),
                "last_heartbeat":  time.time(),
            }

    def _get_local_capabilities(self) -> List[str]:
        """Return a list of capability ids from the local CapabilityRegistry."""
        try:
            from src.runtime.capability_registry import get_capability_registry
            return [c["id"] for c in get_capability_registry().query_capabilities()]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Runtime registration
    # ------------------------------------------------------------------

    def register_runtime(
        self,
        name:         str,
        endpoint:     str,
        capabilities: Optional[List[str]] = None,
        runtime_type: str = "remote",
    ) -> str:
        """Register a peer runtime.  Returns runtime_id."""
        if not name:
            raise ValueError("Runtime name must be non-empty")
        if runtime_type not in RUNTIME_TYPES:
            raise ValueError(
                f"Invalid runtime_type {runtime_type!r}. Valid: {sorted(RUNTIME_TYPES)}"
            )
        runtime_id = str(uuid.uuid4())
        with self._lock:
            self._runtimes[runtime_id] = {
                "id":             runtime_id,
                "name":           name,
                "endpoint":       endpoint,
                "capabilities":   list(capabilities or []),
                "runtime_type":   runtime_type,
                "status":         "online",
                "registered_at":  time.time(),
                "last_heartbeat": time.time(),
            }
        return runtime_id

    def deregister_runtime(self, runtime_id: str) -> bool:
        if runtime_id == "local":
            raise ValueError("Cannot deregister the local runtime")
        with self._lock:
            if runtime_id in self._runtimes:
                del self._runtimes[runtime_id]
                return True
        return False

    # ------------------------------------------------------------------
    # Capability exchange
    # ------------------------------------------------------------------

    def discover_capabilities(self, runtime_id: str) -> List[Dict[str, Any]]:
        """Return the capabilities of a registered peer runtime.

        For the local runtime, queries the live CapabilityRegistry.
        For remote runtimes, returns what was registered at registration time.
        """
        with self._lock:
            rt = self._runtimes.get(runtime_id)
        if rt is None:
            return []
        if rt["runtime_type"] == "local":
            return self._get_local_capabilities_dicts()
        return [{"id": c} for c in rt.get("capabilities", [])]

    def _get_local_capabilities_dicts(self) -> List[Dict[str, Any]]:
        try:
            from src.runtime.capability_registry import get_capability_registry
            return get_capability_registry().query_capabilities()
        except Exception:
            return []

    def exchange_capabilities(
        self,
        runtime_id:      str,
        our_capabilities: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Perform a capability exchange with a peer runtime.

        Updates the peer's capability list in our registry, and returns
        both what we received and what we sent.

        Returns:
            {"received": list[str], "sent": list[str], "ok": bool}
        """
        our_caps = list(our_capabilities or self._get_local_capabilities())
        received = [c["id"] if isinstance(c, dict) else c
                    for c in self.discover_capabilities(runtime_id)]

        # Update peer capabilities in registry
        with self._lock:
            rt = self._runtimes.get(runtime_id)
            if rt is not None and our_capabilities is not None:
                rt["capabilities"] = list(our_capabilities)
                rt["last_heartbeat"] = time.time()

        exchange = {
            "runtime_id":  runtime_id,
            "sent":        our_caps,
            "received":    received,
            "timestamp":   time.time(),
        }
        with self._lock:
            self._exchanges.append(exchange)

        return {"ok": rt is not None, "received": received, "sent": our_caps}

    # ------------------------------------------------------------------
    # Execution routing
    # ------------------------------------------------------------------

    async def request_execution(
        self,
        runtime_id:     str,
        operations:     List[Dict[str, Any]],
        transaction_id: Optional[str] = None,
        dry_run:        bool = False,
    ) -> Dict[str, Any]:
        """Forward an execution request to a peer runtime.

        For local runtimes, dispatches via DistributedRuntime.
        For remote runtimes, records as a federated dispatch (transport
        wired externally by the caller).
        """
        with self._lock:
            rt = self._runtimes.get(runtime_id)
        if rt is None:
            return {
                "ok":    False,
                "error": f"Unknown runtime: {runtime_id!r}",
            }

        if rt["runtime_type"] == "local" or rt["endpoint"] == "local://":
            from src.runtime.distributed_runtime import get_distributed_runtime
            return await get_distributed_runtime().dispatch_operations(
                operations,
                transaction_name=transaction_id or "federation_exec",
                dry_run=dry_run,
            )

        # Remote dispatch record
        dispatch_id = str(uuid.uuid4())
        return {
            "ok":            True,
            "status":        "federated_dispatch",
            "dispatch_id":   dispatch_id,
            "runtime_id":    runtime_id,
            "endpoint":      rt["endpoint"],
            "operation_count": len(operations),
            "dry_run":       dry_run,
            "report_json":   json.dumps({
                "status":      "federated_dispatch",
                "dispatch_id": dispatch_id,
                "runtime_id":  runtime_id,
                "endpoint":    rt["endpoint"],
            }),
        }

    # ------------------------------------------------------------------
    # Heartbeat / status
    # ------------------------------------------------------------------

    def update_runtime_heartbeat(self, runtime_id: str) -> bool:
        with self._lock:
            rt = self._runtimes.get(runtime_id)
            if rt is None:
                return False
            rt["last_heartbeat"] = time.time()
            rt["status"]         = "online"
            return True

    def get_runtime_status(self, runtime_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            rt = self._runtimes.get(runtime_id)
            return dict(rt) if rt else None

    def list_runtimes(
        self,
        runtime_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            rts = list(self._runtimes.values())
        if runtime_type:
            rts = [r for r in rts if r["runtime_type"] == runtime_type]
        return [dict(r) for r in sorted(rts, key=lambda r: r["registered_at"])]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_type: Dict[str, int] = {}
            by_status: Dict[str, int] = {}
            for rt in self._runtimes.values():
                t  = rt["runtime_type"]
                s  = rt["status"]
                by_type[t]   = by_type.get(t, 0) + 1
                by_status[s] = by_status.get(s, 0) + 1
            return {
                "total_runtimes":   len(self._runtimes),
                "by_type":          by_type,
                "by_status":        by_status,
                "total_exchanges":  len(self._exchanges),
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[RuntimeFederationApi] = None
_LOCK = threading.Lock()


def get_runtime_federation_api() -> RuntimeFederationApi:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = RuntimeFederationApi()
        return _INSTANCE


def reset_runtime_federation_api_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
