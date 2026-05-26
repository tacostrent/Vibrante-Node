"""
Capability Registry (Tier 2.75)
================================
Dynamic tracking of what the runtime can currently do. Capabilities are
registered at module import time from known sources (houdini_runtime ops,
known runtime services) and updated at runtime as MCP servers connect or
new DCC integrations activate.

This is foundational for future AI planners / tool-discovery flows: any
component that needs to emit an intent can first check whether the required
capability exists before constructing an execution plan.

Capability types (string constants):
    "houdini_op"         — a named op type in houdini_runtime.SUPPORTED_OPS
    "runtime_service"    — an active src/runtime service (transaction_manager, etc.)
    "semantic_operation" — a named semantic operation registered in semantic_registry
    "mcp_server"         — a connected MCP server registered in mcp_runtime
    "dcc_integration"    — an active DCC bridge (houdini, maya, blender)
    "renderer"           — a known renderer type (karma, mantra, arnold, etc.)

Public API:
    get_capability_registry() -> CapabilityRegistry   (singleton)
    reset_capability_registry_for_tests()

    CapabilityRegistry.register_capability(type, id, metadata)
    CapabilityRegistry.deregister_capability(id)
    CapabilityRegistry.query_capabilities(type=None) -> list[dict]
    CapabilityRegistry.supports(capability_id) -> bool
    CapabilityRegistry.stats() -> dict
"""

import threading
from typing import Any, Dict, List, Optional

CAPABILITY_TYPES = frozenset({
    "houdini_op",
    "runtime_service",
    "semantic_operation",
    "mcp_server",
    "dcc_integration",
    "renderer",
    # Tier 4 additions
    "remote_capability",   # capability from a remote/federated runtime
    "mcp_tool",            # an MCP tool exposed by the server runtime
})

_BUILTIN_CAPABILITIES: List[Dict[str, Any]] = [
    # Houdini bridge ops -------------------------------------------------------
    {"type": "houdini_op", "id": "create_node",       "metadata": {"description": "Create a Houdini node"}},
    {"type": "houdini_op", "id": "set_parms",         "metadata": {"description": "Set multiple parameters"}},
    {"type": "houdini_op", "id": "connect_nodes",     "metadata": {"description": "Wire two nodes"}},
    {"type": "houdini_op", "id": "delete_node",       "metadata": {"description": "Delete a node (irreversible in Tier 2)"}},
    {"type": "houdini_op", "id": "set_display_flag",  "metadata": {"description": "Toggle display flag"}},
    {"type": "houdini_op", "id": "set_render_flag",   "metadata": {"description": "Toggle render flag"}},
    {"type": "houdini_op", "id": "cook_node",         "metadata": {"description": "Force-cook a node"}},
    {"type": "houdini_op", "id": "layout_children",   "metadata": {"description": "Auto-layout child nodes"}},
    {"type": "houdini_op", "id": "build_node_chain",  "metadata": {"description": "Create a multi-node network from spec"}},
    # Runtime services ---------------------------------------------------------
    {"type": "runtime_service", "id": "transaction_manager", "metadata": {"description": "Transactional execution with rollback"}},
    {"type": "runtime_service", "id": "scene_cache",         "metadata": {"description": "TTL cache + dirty tracking"}},
    {"type": "runtime_service", "id": "dependency_graph",    "metadata": {"description": "Inter-node dependency BFS graph"}},
    {"type": "runtime_service", "id": "validation_engine",   "metadata": {"description": "Pre-execution op validation"}},
    {"type": "runtime_service", "id": "audit_store",         "metadata": {"description": "JSONL audit trail"}},
    {"type": "runtime_service", "id": "execution_scheduler", "metadata": {"description": "Serialised FIFO mutation queue"}},
    {"type": "runtime_service", "id": "mcp_runtime",         "metadata": {"description": "Long-lived MCP client session registry"}},
    # DCC integration ----------------------------------------------------------
    {"type": "dcc_integration", "id": "houdini", "metadata": {"description": "Houdini TCP bridge (hou_bridge.py)"}},
    # Known renderers ----------------------------------------------------------
    {"type": "renderer", "id": "karma",           "metadata": {"rop_type": "karma"}},
    {"type": "renderer", "id": "mantra",          "metadata": {"rop_type": "ifd"}},
    {"type": "renderer", "id": "arnold",          "metadata": {"rop_type": "arnold"}},
    {"type": "renderer", "id": "redshift",        "metadata": {"rop_type": "redshift_rop"}},
    {"type": "renderer", "id": "vray",            "metadata": {"rop_type": "vray_renderer"}},
    {"type": "renderer", "id": "opengl",          "metadata": {"rop_type": "opengl"}},
    {"type": "renderer", "id": "usd_render",      "metadata": {"rop_type": "usdrender_rop"}},
]


class CapabilityRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        # id → {"type": str, "id": str, "metadata": dict}
        self._caps: Dict[str, Dict[str, Any]] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        for cap in _BUILTIN_CAPABILITIES:
            self._caps[cap["id"]] = {
                "type": cap["type"],
                "id":   cap["id"],
                "metadata": dict(cap.get("metadata", {})),
            }

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_capability(self, cap_type: str, cap_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Register or update a capability.

        Args:
            cap_type: One of the CAPABILITY_TYPES strings.
            cap_id:   Unique string identifier (e.g. "karma", "create_node").
            metadata: Arbitrary dict of extra information.

        Raises:
            ValueError: If cap_type is not a known capability type.
        """
        if cap_type not in CAPABILITY_TYPES:
            raise ValueError(f"Unknown capability type: {cap_type!r}. Valid types: {sorted(CAPABILITY_TYPES)}")
        if not cap_id:
            raise ValueError("cap_id must be a non-empty string")
        with self._lock:
            self._caps[cap_id] = {
                "type":     cap_type,
                "id":       cap_id,
                "metadata": dict(metadata or {}),
            }

    def deregister_capability(self, cap_id: str) -> bool:
        """Remove a capability by id. Returns True if found and removed."""
        with self._lock:
            if cap_id in self._caps:
                del self._caps[cap_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query_capabilities(self, cap_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all capabilities, optionally filtered by type.

        Returns a list of dicts sorted by (type, id) for deterministic output.
        """
        with self._lock:
            caps = list(self._caps.values())
        if cap_type is not None:
            caps = [c for c in caps if c["type"] == cap_type]
        return sorted(caps, key=lambda c: (c["type"], c["id"]))

    def supports(self, capability_id: str) -> bool:
        """Return True if the given capability id is registered."""
        with self._lock:
            return capability_id in self._caps

    def get(self, capability_id: str) -> Optional[Dict[str, Any]]:
        """Return the capability dict for the given id, or None."""
        with self._lock:
            cap = self._caps.get(capability_id)
            return dict(cap) if cap else None

    # ------------------------------------------------------------------
    # Tier 4 — MCP tool exposure
    # ------------------------------------------------------------------

    def expose_via_mcp(self, cap_id: str, tool_schema: Optional[Dict[str, Any]] = None) -> None:
        """Mark a capability as exposed via the MCP server runtime.

        Registers an ``mcp_tool`` capability whose metadata contains the
        inputSchema used by the MCP server.  The cap_id must already exist
        in the registry.
        """
        tool_schema = dict(tool_schema or {})
        existing    = self.get(cap_id)
        description = existing.get("metadata", {}).get("description", cap_id) if existing else cap_id
        with self._lock:
            self._caps[f"mcp:{cap_id}"] = {
                "type":     "mcp_tool",
                "id":       f"mcp:{cap_id}",
                "metadata": {
                    "tool_name":   cap_id,
                    "description": description,
                    "inputSchema": tool_schema,
                },
            }

    def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """Return all MCP-exposed tools in MCP tool-list format."""
        with self._lock:
            tools = [c for c in self._caps.values() if c["type"] == "mcp_tool"]
        return sorted(
            [
                {
                    "name":        t["metadata"].get("tool_name", t["id"]),
                    "description": t["metadata"].get("description", ""),
                    "inputSchema": t["metadata"].get("inputSchema", {}),
                }
                for t in tools
            ],
            key=lambda t: t["name"],
        )

    # ------------------------------------------------------------------
    # Tier 4 — Remote / federated capability registration
    # ------------------------------------------------------------------

    def register_remote_capability(
        self,
        runtime_id: str,
        cap_type:   str,
        cap_id:     str,
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a capability from a remote federated runtime.

        The cap_id is namespaced as ``<runtime_id>:<cap_id>`` to avoid
        collisions with local capabilities.

        Raises:
            ValueError: If cap_type is not a valid CAPABILITY_TYPES entry.
        """
        namespaced_id = f"{runtime_id}:{cap_id}"
        meta = dict(metadata or {})
        meta["runtime_id"] = runtime_id
        meta["remote"]     = True
        self.register_capability("remote_capability", namespaced_id, meta)

    def get_remote_capabilities(self, runtime_id: str) -> List[Dict[str, Any]]:
        """Return all capabilities registered from a specific remote runtime."""
        with self._lock:
            return [
                dict(c) for c in self._caps.values()
                if c["type"] == "remote_capability"
                and c.get("metadata", {}).get("runtime_id") == runtime_id
            ]

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_type: Dict[str, int] = {}
            for cap in self._caps.values():
                by_type[cap["type"]] = by_type.get(cap["type"], 0) + 1
            return {
                "total": len(self._caps),
                "by_type": by_type,
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_REGISTRY: Optional[CapabilityRegistry] = None
_REGISTRY_LOCK = threading.Lock()


def get_capability_registry() -> CapabilityRegistry:
    global _REGISTRY
    with _REGISTRY_LOCK:
        if _REGISTRY is None:
            _REGISTRY = CapabilityRegistry()
        return _REGISTRY


def reset_capability_registry_for_tests() -> None:
    global _REGISTRY
    with _REGISTRY_LOCK:
        _REGISTRY = None
