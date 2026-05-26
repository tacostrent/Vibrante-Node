"""
Semantic Registry (Tier 2.75)
================================
Registry of named semantic operations that translate high-level intents
into concrete, structured op lists.

A semantic operation is a Python callable:
    handler(context: dict) -> list[dict]

The handler receives a context dict (parameters supplied by the caller)
and returns a list of raw op dicts that the transaction system can execute.
Handlers MUST be deterministic — no LLM calls, no bridge reads, no I/O.
They may read from the context dict only.

Built-in operations cover the most common scaffolding patterns. Users can
register custom operations at runtime.

Public API:
    get_semantic_registry() -> SemanticRegistry   (singleton)
    reset_semantic_registry_for_tests()

    SemanticRegistry.register_operation(operation_id, metadata, handler)
    SemanticRegistry.deregister_operation(operation_id) -> bool
    SemanticRegistry.get_operation(operation_id) -> dict | None
    SemanticRegistry.list_operations() -> list[dict]
    SemanticRegistry.resolve_to_execution_plan(operation_id, context) -> dict
"""

import threading
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Built-in operation handlers
# ---------------------------------------------------------------------------

def _create_geo_container(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Create an /obj-level geo container with an optional inner null."""
    parent   = str(ctx.get("parent", "/obj"))
    name     = str(ctx.get("name",   "geo1"))
    return [{"op": "create_node", "parent": parent, "type": "geo", "name": name}]


def _build_pyro_source(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    parent = str(ctx.get("parent",  "/obj"))
    name   = str(ctx.get("name",    "pyro_source"))
    radius = str(ctx.get("radius",  "1.0"))
    geo_name = f"{name}_geo"
    return [
        {
            "op": "build_node_chain",
            "spec": {
                "intent": "build_pyro_source",
                "nodes": [
                    {"id": "geo",     "parent": parent,                   "type": "geo",         "name": geo_name},
                    {"id": "sphere",  "parent": f"{parent}/{geo_name}",   "type": "sphere",      "name": "src_sphere",
                     "params": {"radx": radius, "rady": radius, "radz": radius}},
                    {"id": "scatter", "parent": f"{parent}/{geo_name}",   "type": "scatter",     "name": "src_scatter",
                     "params": {"npts": str(ctx.get("scatter_count", 1000))}},
                    {"id": "psource", "parent": f"{parent}/{geo_name}",   "type": "pyro_source", "name": "pyro_source1"},
                ],
                "connections": [
                    {"from": "sphere",  "to": "scatter",  "out": 0, "in": 0},
                    {"from": "scatter", "to": "psource",  "out": 0, "in": 0},
                ],
                "layout": True,
                "cook":   False,
            },
        }
    ]


def _setup_karma_renderer(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    name        = str(ctx.get("name",        "karma1"))
    stage_path  = str(ctx.get("stage_path",  "/stage"))
    output_path = str(ctx.get("output_path", "$HIP/render/$HIPNAME.$F4.exr"))
    res_x       = str(ctx.get("res_x",       1920))
    res_y       = str(ctx.get("res_y",       1080))
    return [
        {"op": "create_node", "parent": "/out", "type": "karma", "name": name},
        {"op": "set_parms", "node": f"/out/{name}",
         "parms": {"loppath": stage_path, "picture": output_path, "xres": res_x, "yres": res_y}},
    ]


def _export_to_usd(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    name        = str(ctx.get("name",        "usd_export"))
    output_path = str(ctx.get("output_path", "$HIP/$HIPNAME.usd"))
    frame_start = str(ctx.get("frame_start", 1))
    frame_end   = str(ctx.get("frame_end",   240))
    return [
        {"op": "create_node", "parent": "/out", "type": "usd", "name": name},
        {"op": "set_parms", "node": f"/out/{name}",
         "parms": {"lopoutput": output_path, "trange": "1",
                   "f1": frame_start, "f2": frame_end}},
    ]


def _cache_geometry(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    geo_path    = str(ctx.get("geo_path",    "/obj/geo1"))
    source_path = str(ctx.get("source_path", ""))
    name        = str(ctx.get("name",        "filecache1"))
    cache_path  = str(ctx.get("cache_path",  "$HIP/cache/$HIPNAME.$F4.bgeo.sc"))
    frame_start = str(ctx.get("frame_start", 1))
    frame_end   = str(ctx.get("frame_end",   240))
    ops = [
        {"op": "create_node", "parent": geo_path, "type": "filecache", "name": name},
        {"op": "set_parms", "node": f"{geo_path}/{name}",
         "parms": {"file": cache_path, "f1": frame_start, "f2": frame_end}},
    ]
    if source_path:
        ops.insert(1, {
            "op": "connect_nodes",
            "from_node": source_path,
            "to_node":   f"{geo_path}/{name}",
            "output":    0,
            "input_idx": 0,
        })
    return ops


def _asset_publish_scaffold(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    parent     = str(ctx.get("parent",     "/obj"))
    asset_name = str(ctx.get("asset_name", "asset1"))
    return [
        {
            "op": "build_node_chain",
            "spec": {
                "intent": "asset_publish",
                "nodes": [
                    {"id": "geo",    "parent": parent,                   "type": "geo",  "name": asset_name},
                    {"id": "input",  "parent": f"{parent}/{asset_name}", "type": "null", "name": "INPUT"},
                    {"id": "output", "parent": f"{parent}/{asset_name}", "type": "null", "name": "OUTPUT"},
                ],
                "connections": [{"from": "input", "to": "output", "out": 0, "in": 0}],
                "layout": True,
                "cook":   False,
            },
        }
    ]


def _solaris_lighting_setup(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    stage_path = str(ctx.get("stage_path", "/stage"))
    name       = str(ctx.get("name",       "lighting"))
    return [
        {
            "op": "build_node_chain",
            "spec": {
                "intent": "solaris_lighting_setup",
                "nodes": [
                    {"id": "key",  "parent": stage_path, "type": "distantlight", "name": f"{name}_key",
                     "params": {"intensity": str(ctx.get("key_intensity", 5.0)), "angle": "45"}},
                    {"id": "fill", "parent": stage_path, "type": "distantlight", "name": f"{name}_fill",
                     "params": {"intensity": str(ctx.get("fill_intensity", 2.0)), "angle": "-45"}},
                    {"id": "rim",  "parent": stage_path, "type": "distantlight", "name": f"{name}_rim",
                     "params": {"intensity": str(ctx.get("rim_intensity", 3.0)), "angle": "180"}},
                ],
                "connections": [],
                "layout": True,
                "cook":   False,
            },
        }
    ]


_BUILTIN_OPERATIONS: List[Dict[str, Any]] = [
    {
        "operation_id":          "create_geo_container",
        "description":           "Create an Object-level geo container.",
        "required_context_keys": ["parent", "name"],
        "tags":                  ["geometry", "scaffold"],
        "handler":               _create_geo_container,
    },
    {
        "operation_id":          "build_pyro_source",
        "description":           "Build a pyro source network (sphere → scatter → pyro_source).",
        "required_context_keys": ["parent", "name"],
        "tags":                  ["vfx", "pyro", "simulation"],
        "handler":               _build_pyro_source,
    },
    {
        "operation_id":          "setup_karma_renderer",
        "description":           "Add a Karma render node and configure output path + resolution.",
        "required_context_keys": ["name", "output_path"],
        "tags":                  ["render", "karma", "solaris"],
        "handler":               _setup_karma_renderer,
    },
    {
        "operation_id":          "export_to_usd",
        "description":           "Create a USD export ROP with frame range.",
        "required_context_keys": ["name", "output_path"],
        "tags":                  ["usd", "export", "pipeline"],
        "handler":               _export_to_usd,
    },
    {
        "operation_id":          "cache_geometry",
        "description":           "Write geometry to a file cache.",
        "required_context_keys": ["geo_path", "name", "cache_path"],
        "tags":                  ["cache", "geometry", "pipeline"],
        "handler":               _cache_geometry,
    },
    {
        "operation_id":          "asset_publish_scaffold",
        "description":           "Create an asset geo container with INPUT/OUTPUT null nodes.",
        "required_context_keys": ["parent", "asset_name"],
        "tags":                  ["asset", "pipeline"],
        "handler":               _asset_publish_scaffold,
    },
    {
        "operation_id":          "solaris_lighting_setup",
        "description":           "Add a three-point distant-light rig to a Solaris stage.",
        "required_context_keys": ["stage_path", "name"],
        "tags":                  ["solaris", "usd", "lighting"],
        "handler":               _solaris_lighting_setup,
    },
]


# ---------------------------------------------------------------------------
# Registry class
# ---------------------------------------------------------------------------

class SemanticRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        # operation_id → {operation_id, description, required_context_keys, tags, handler}
        self._ops: Dict[str, Dict[str, Any]] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        for op in _BUILTIN_OPERATIONS:
            self._ops[op["operation_id"]] = dict(op)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_operation(
        self,
        operation_id: str,
        metadata:     Optional[Dict[str, Any]],
        handler:      Callable[[Dict[str, Any]], List[Dict[str, Any]]],
    ) -> None:
        """Register or replace a semantic operation.

        Args:
            operation_id: Unique string identifier.
            metadata:     Dict of descriptive info (description, tags, etc.).
            handler:      Pure function: context dict → list of op dicts.
                          Must be deterministic and side-effect-free.
        """
        if not operation_id:
            raise ValueError("operation_id must be non-empty")
        if not callable(handler):
            raise ValueError("handler must be callable")
        record: Dict[str, Any] = {
            "operation_id": operation_id,
            "handler":      handler,
        }
        record.update(metadata or {})
        with self._lock:
            self._ops[operation_id] = record

    def deregister_operation(self, operation_id: str) -> bool:
        """Remove an operation. Returns True if found."""
        with self._lock:
            if operation_id in self._ops:
                del self._ops[operation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_operation(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Return operation metadata (without handler callable), or None."""
        with self._lock:
            op = self._ops.get(operation_id)
            if op is None:
                return None
            return {k: v for k, v in op.items() if k != "handler"}

    def list_operations(self, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all operation metadata dicts (no handler), sorted by operation_id."""
        with self._lock:
            ops = [{k: v for k, v in op.items() if k != "handler"} for op in self._ops.values()]
        if tag is not None:
            ops = [op for op in ops if tag in op.get("tags", [])]
        return sorted(ops, key=lambda o: o["operation_id"])

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve_to_execution_plan(
        self,
        operation_id: str,
        context:      Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Resolve a semantic operation to a concrete execution plan.

        The handler is called with the provided context and returns a list
        of raw op dicts. No validation is performed here — run the result
        through ValidationEngine / RuntimeConstraints before executing.

        Returns:
            {
                "ok":            bool,
                "operation_id":  str,
                "operations":    list[dict],
                "op_count":      int,
                "error":         str  (only when ok=False),
                "metadata":      dict (operation metadata),
            }
        """
        context = dict(context or {})

        with self._lock:
            record = self._ops.get(operation_id)

        if record is None:
            return {
                "ok":           False,
                "operation_id": operation_id,
                "operations":   [],
                "op_count":     0,
                "error":        f"Unknown semantic operation: {operation_id!r}",
                "metadata":     {},
            }

        handler  = record["handler"]
        metadata = {k: v for k, v in record.items() if k not in ("handler",)}

        try:
            ops = handler(context)
        except Exception as exc:
            return {
                "ok":           False,
                "operation_id": operation_id,
                "operations":   [],
                "op_count":     0,
                "error":        f"Handler for '{operation_id}' raised: {exc}",
                "metadata":     metadata,
            }

        if not isinstance(ops, list):
            return {
                "ok":           False,
                "operation_id": operation_id,
                "operations":   [],
                "op_count":     0,
                "error":        f"Handler for '{operation_id}' must return list, got {type(ops).__name__}",
                "metadata":     metadata,
            }

        return {
            "ok":           True,
            "operation_id": operation_id,
            "operations":   ops,
            "op_count":     len(ops),
            "error":        "",
            "metadata":     metadata,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_REGISTRY: Optional[SemanticRegistry] = None
_LOCK = threading.Lock()


def get_semantic_registry() -> SemanticRegistry:
    global _REGISTRY
    with _LOCK:
        if _REGISTRY is None:
            _REGISTRY = SemanticRegistry()
        return _REGISTRY


def reset_semantic_registry_for_tests() -> None:
    global _REGISTRY
    with _LOCK:
        _REGISTRY = None
