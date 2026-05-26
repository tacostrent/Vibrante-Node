"""
Houdini Runtime
===============
Semantic layer on top of `src.utils.hou_bridge`. Provides:

  • scene_context(...) — single structured snapshot of scene + selection +
    networks + assets + render nodes, cached for fast repeated reads.
  • build_node_chain(spec) — declarative creation of a Houdini network from
    a JSON spec: validate → create → param → connect → layout → cook.

Both functions are async to fit Vibrante's node `execute()` contract. The
runtime is the seam between graph nodes and the raw RPC bridge — nodes
should never call `get_bridge()` directly for context aggregation or
multi-step composition, because the runtime layer:

  1. caches reads (avoids duplicate bridge round-trips per execution)
  2. validates inputs before mutating Houdini
  3. returns shape-stable JSON-serialisable data (LLM-friendly)
  4. is the future hook point for transactions / rollback (Tier 3)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional

from src.runtime.scene_cache import get_scene_cache

# Bridge imports kept lazy so unit tests can monkey-patch without a live
# Houdini process. We import the module, not the names, so attribute access
# (`_bridge_module.get_bridge()`) resolves through any test patch.
from src.utils import hou_bridge as _bridge_module


# ---------------------------------------------------------------------------
# Bridge helpers
# ---------------------------------------------------------------------------

def _bridge():
    return _bridge_module.get_bridge()


async def _to_thread(fn, *args, **kwargs):
    """Run a blocking bridge call off the event loop without leaking exceptions."""
    return await asyncio.to_thread(fn, *args, **kwargs)


# ---------------------------------------------------------------------------
# Scene context
# ---------------------------------------------------------------------------

_NETWORKS = ("obj", "mat", "out", "stage", "tasks", "shop", "vex", "ch")
_CORE_NETWORKS = ("obj", "mat", "out")
_OPTIONAL_NETWORKS = ("stage", "tasks", "shop", "vex", "ch")


async def scene_context(
    include_selection: bool = True,
    include_assets: bool = True,
    include_render: bool = True,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Return a structured snapshot of the current Houdini scene state.

    Shape is stable across calls — empty sections appear as empty lists/dicts
    instead of being omitted, so downstream LLM prompts can rely on the keys.
    """
    cache = get_scene_cache()

    if force_refresh:
        cache.invalidate("scene_context::")

    # Each section cached independently so a partial refresh is possible later.
    scene = await _section(cache, "scene_context::scene", _fetch_scene_info)
    networks = await _section(cache, "scene_context::networks", _fetch_networks)
    selection = (
        await _section(cache, "scene_context::selection", _fetch_selection)
        if include_selection else []
    )
    assets = (
        await _section(cache, "scene_context::assets", _fetch_assets)
        if include_assets else {"hda_files": [], "definitions": []}
    )
    render = (
        await _section(cache, "scene_context::render", _fetch_render, networks)
        if include_render else {"render_nodes": []}
    )

    return {
        "scene": scene,
        "selection": selection,
        "networks": networks,
        "assets": assets,
        "render": render,
    }


async def _section(cache, key: str, fetcher, *fetcher_args) -> Any:
    cached = cache.get(key)
    if cached is not None:
        return cached
    value = await fetcher(*fetcher_args)
    cache.set(key, value, ttl_sec=5.0)
    return value


async def _fetch_scene_info() -> Dict[str, Any]:
    try:
        info = await _to_thread(_bridge().scene_info) or {}
    except Exception as exc:
        return {"error": str(exc)}
    return {
        "hip_file": info.get("hip_file", ""),
        "hip_name": info.get("hip_name", ""),
        "houdini_version": info.get("houdini_version", ""),
        "fps": info.get("fps", 24),
        "frame": info.get("frame", 1),
        "frame_range": list(info.get("frame_range") or [1, 240]),
    }


async def _fetch_networks() -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    bridge = _bridge()

    for net in _CORE_NETWORKS:
        out[net] = await _safe_network_summary(bridge, f"/{net}")

    for net in _OPTIONAL_NETWORKS:
        path = f"/{net}"
        try:
            exists = await _to_thread(bridge.node_exists, path)
            if not (isinstance(exists, dict) and exists.get("exists")):
                continue
        except Exception:
            continue
        out[net] = await _safe_network_summary(bridge, path)
    return out


async def _safe_network_summary(bridge, path: str) -> List[Dict[str, Any]]:
    summarizer = getattr(bridge, "network_summary", None)
    try:
        if summarizer is not None:
            data = await _to_thread(summarizer, path)
        else:
            data = await _to_thread(bridge.children, path)
    except Exception:
        return []
    return list(data or [])


async def _fetch_selection() -> List[Dict[str, Any]]:
    bridge = _bridge()
    selection_fn = getattr(bridge, "get_selection", None)
    if selection_fn is None:
        return []
    try:
        paths = await _to_thread(selection_fn) or []
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for entry in paths:
        if isinstance(entry, dict):
            out.append({
                "path": entry.get("path", ""),
                "type": entry.get("type", ""),
                "category": entry.get("category", ""),
            })
        else:
            path_str = str(entry)
            info = await _safe_node_info(bridge, path_str)
            out.append({
                "path": path_str,
                "type": info.get("type", ""),
                "category": info.get("category", ""),
            })
    return out


async def _safe_node_info(bridge, path: str) -> Dict[str, Any]:
    try:
        return await _to_thread(bridge.node_info, path) or {}
    except Exception:
        return {}


async def _fetch_assets() -> Dict[str, Any]:
    bridge = _bridge()
    try:
        result = await _to_thread(
            bridge.run_code,
            (
                "import hou\n"
                "result = {\n"
                "    'files': list(hou.hda.loadedFiles()),\n"
                "    'defs': [\n"
                "        {\n"
                "            'name': d.nodeTypeName(),\n"
                "            'label': d.description(),\n"
                "            'file': d.libraryFilePath(),\n"
                "            'category': d.nodeTypeCategory().name(),\n"
                "        }\n"
                "        for f in hou.hda.loadedFiles() for d in hou.hda.definitionsInFile(f)\n"
                "    ]\n"
                "}\n"
            ),
        )
    except Exception:
        return {"hda_files": [], "definitions": []}
    payload = (result or {}).get("result") or {}
    return {
        "hda_files": list(payload.get("files") or []),
        "definitions": list(payload.get("defs") or []),
    }


async def _fetch_render(networks: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    out_nodes = networks.get("out") or []
    render_types = {
        "karma", "ifd", "mantra", "opengl", "ris", "arnold", "redshift_rop",
        "vray_renderer", "usdrender_rop", "lop_render"
    }
    render_nodes = [
        {"path": n.get("path", ""), "type": n.get("type", "")}
        for n in out_nodes
        if n.get("type", "") in render_types
    ]
    return {"render_nodes": render_nodes}


# ---------------------------------------------------------------------------
# Build node chain
# ---------------------------------------------------------------------------

def _expected_path(n: dict) -> str:
    """Return the path we expect Houdini to create for spec node `n`.

    Returns an empty string when `n` has no explicit name (Houdini will pick
    one, so we can't predict the path before the create call).
    """
    name = n.get("name") or ""
    if not name:
        return ""
    return n["parent"].rstrip("/") + "/" + name


def _topo_sort_nodes(nodes_spec: List[dict]) -> List[dict]:
    """Return nodes in creation order: parent-creators before their children.

    If node A's expected created path matches node B's `parent`, B must come
    after A.  Uses Kahn's algorithm; falls back to the original order if a
    cycle is detected (which the spec validator should have rejected already).
    """
    # expected_path → index for nodes that have an explicit name
    by_expected: Dict[str, int] = {}
    for i, n in enumerate(nodes_spec):
        ep = _expected_path(n)
        if ep:
            by_expected[ep] = i

    # deps[i] = indices that i depends on (i must come after them)
    dependents: Dict[int, List[int]] = {i: [] for i in range(len(nodes_spec))}
    in_degree = [0] * len(nodes_spec)
    for i, n in enumerate(nodes_spec):
        parent = n["parent"]
        if parent in by_expected and by_expected[parent] != i:
            dep = by_expected[parent]
            dependents[dep].append(i)
            in_degree[i] += 1

    from collections import deque
    queue: deque[int] = deque(i for i in range(len(nodes_spec)) if in_degree[i] == 0)
    ordered: List[int] = []
    while queue:
        idx = queue.popleft()
        ordered.append(idx)
        for child in dependents[idx]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(ordered) != len(nodes_spec):
        return nodes_spec  # cycle — fall back to original order
    return [nodes_spec[i] for i in ordered]


async def build_node_chain(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Build a Houdini node network from a structured spec.

    Spec shape:
        {
            "intent": "string (free-form label for logs)",
            "nodes": [
                {"id": "n1", "parent": "/obj/geo1", "type": "sphere",
                 "name": "src", "params": {"radx": 2.0}},
                ...
            ],
            "connections": [
                {"from": "n1", "to": "n2", "out": 0, "in": 0},
                ...
            ],
            "layout": true,
            "cook": false
        }

    Returns:
        {"ok": bool, "intent": str, "created_paths": [...],
         "id_to_path": {...}, "error": "..." (only if ok=false)}
    """
    intent = str(spec.get("intent") or "")
    nodes_spec = list(spec.get("nodes") or [])
    connections_spec = list(spec.get("connections") or [])
    do_layout = bool(spec.get("layout", True))
    do_cook = bool(spec.get("cook", False))

    error = _validate_spec(nodes_spec, connections_spec)
    if error:
        return {
            "ok": False,
            "intent": intent,
            "created_paths": [],
            "id_to_path": {},
            "error": error,
        }

    # Sort so parent-creating nodes always precede their children.
    sorted_nodes = _topo_sort_nodes(nodes_spec)

    # Paths that will be created by nodes in this spec — skip the pre-flight
    # node_exists check for these (they don't exist yet, by design).
    will_create: set[str] = {_expected_path(n) for n in sorted_nodes if _expected_path(n)}

    bridge = _bridge()

    # Pre-flight: verify that external parents (not created in this spec) exist.
    for n in sorted_nodes:
        parent = n["parent"]
        if parent in will_create:
            continue  # will be satisfied by a preceding node in sorted_nodes
        try:
            exists = await _to_thread(bridge.node_exists, parent)
        except Exception as exc:
            return _failure(intent, [], {}, f"node_exists check failed for {parent}: {exc}")
        if not (isinstance(exists, dict) and exists.get("exists")):
            return _failure(intent, [], {}, f"parent node does not exist: {parent}")

    id_to_path: Dict[str, str] = {}
    created_paths: List[str] = []
    parents_seen: List[str] = []
    # Maps expected_path → actual_path so we can fix parent refs when Houdini
    # assigns a numbered suffix (e.g. pyro_src_geo1 instead of pyro_src_geo).
    actual_by_expected: Dict[str, str] = {}

    for n in sorted_nodes:
        node_id = n["id"]
        # Patch parent if a preceding node in this spec was created with a
        # different actual path than we predicted (Houdini name collision).
        parent = actual_by_expected.get(n["parent"], n["parent"])
        try:
            result = await _to_thread(
                bridge.create_node,
                parent, n["type"], n.get("name", ""),
            )
        except Exception as exc:
            return _failure(intent, created_paths, id_to_path, f"create_node failed for '{node_id}': {exc}")
        path = (result or {}).get("path") or ""
        if not path:
            return _failure(intent, created_paths, id_to_path, f"create_node returned no path for '{node_id}'")
        id_to_path[node_id] = path
        created_paths.append(path)
        if parent not in parents_seen:
            parents_seen.append(parent)

        # Record mapping so children of this node use the real path.
        ep = _expected_path(n)
        if ep and ep != path:
            actual_by_expected[ep] = path

        params = n.get("params") or {}
        if params:
            try:
                await _to_thread(bridge.set_parms, path, params)
            except Exception as exc:
                return _failure(intent, created_paths, id_to_path, f"set_parms failed for '{node_id}' ({path}): {exc}")

    for c in connections_spec:
        from_path = id_to_path[c["from"]]
        to_path = id_to_path[c["to"]]
        try:
            await _to_thread(
                bridge.connect_nodes,
                from_path, to_path,
                int(c.get("out", 0)), int(c.get("in", 0)),
            )
        except Exception as exc:
            return _failure(intent, created_paths, id_to_path, f"connect_nodes failed for {c['from']}→{c['to']}: {exc}")

    if do_layout:
        for parent in parents_seen:
            try:
                await _to_thread(bridge.layout_children, parent)
            except Exception:
                pass  # layout is decorative — never fail the build for this

    if do_cook and created_paths:
        last = created_paths[-1]
        try:
            await _to_thread(bridge.cook_node, last, False)
        except Exception as exc:
            return _failure(intent, created_paths, id_to_path, f"cook_node failed for {last}: {exc}")

    # Mutating op — bump cache so subsequent scene_context() reflects reality.
    get_scene_cache().invalidate("scene_context::")

    return {
        "ok": True,
        "intent": intent,
        "created_paths": created_paths,
        "id_to_path": dict(id_to_path),
    }


def _validate_spec(nodes_spec: List[dict], connections_spec: List[dict]) -> Optional[str]:
    if not nodes_spec:
        return "spec.nodes must contain at least one node"

    seen_ids: set[str] = set()
    for i, n in enumerate(nodes_spec):
        if not isinstance(n, dict):
            return f"spec.nodes[{i}] must be a dict, got {type(n).__name__}"
        for key in ("id", "parent", "type"):
            if not n.get(key):
                return f"spec.nodes[{i}] missing required field '{key}'"
        nid = n["id"]
        if nid in seen_ids:
            return f"duplicate node id: '{nid}'"
        seen_ids.add(nid)

    for i, c in enumerate(connections_spec):
        if not isinstance(c, dict):
            return f"spec.connections[{i}] must be a dict, got {type(c).__name__}"
        for key in ("from", "to"):
            if not c.get(key):
                return f"spec.connections[{i}] missing required field '{key}'"
        if c["from"] not in seen_ids:
            return f"connection {i} references unknown node id '{c['from']}'"
        if c["to"] not in seen_ids:
            return f"connection {i} references unknown node id '{c['to']}'"
    return None


def _failure(intent: str, created: List[str], id_to_path: Dict[str, str], message: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "intent": intent,
        "created_paths": list(created),
        "id_to_path": dict(id_to_path),
        "error": message,
    }


# ---------------------------------------------------------------------------
# Convenience: scene_context serialised for LLM prompts
# ---------------------------------------------------------------------------

def context_to_prompt(context: Dict[str, Any]) -> str:
    """Pre-serialise a scene_context dict to a compact JSON string."""
    return json.dumps(context, indent=2, sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# Semantic operation execution (Tier 2)
# ---------------------------------------------------------------------------
#
# Each supported operation is a structured dict with an "op" discriminator
# plus type-specific params. The transaction system feeds these in one at a
# time; this module is responsible for:
#   1. validating each op shape
#   2. capturing a rollback snapshot BEFORE mutating
#   3. executing via the bridge
#   4. marking the appropriate dirty-state entries
#   5. exposing a paired rollback handler for the transaction manager
#
# The same op vocabulary is also used by `build_node_chain` internally.
# Adding a new op type means:
#   • add an entry to _OP_EXECUTORS
#   • add a paired entry to _OP_ROLLBACKERS
#   • register the rollback in `_register_rollback_handlers()` (called at
#     module import time)
#
# We DELIBERATELY do not expose a "run_python" or "execute_code" op.
# Arbitrary Python execution would break the AI-Plan → Transaction guarantee
# that operations are structured, validated, and deterministic.

SUPPORTED_OPS = (
    "create_node",
    "set_parms",
    "connect_nodes",
    "delete_node",
    "set_display_flag",
    "set_render_flag",
    "set_keyframe",
    "cook_node",
    "layout_children",
    "build_node_chain",
)


def _validate_operation(op: Dict[str, Any]) -> Optional[str]:
    """Return None if the op is well-formed, else an error string."""
    if not isinstance(op, dict):
        return f"operation must be a dict, got {type(op).__name__}"
    op_type = op.get("op")
    if op_type not in SUPPORTED_OPS:
        return f"unsupported op '{op_type}'. Supported: {sorted(SUPPORTED_OPS)}"

    required: Dict[str, tuple] = {
        "create_node":      ("parent", "type"),
        "set_parms":        ("node", "parms"),
        "connect_nodes":    ("from", "to"),
        "delete_node":      ("path",),
        "set_display_flag": ("path",),
        "set_render_flag":  ("path",),
        "set_keyframe":     ("node", "parm", "frame", "value"),
        "cook_node":        ("path",),
        "layout_children":  ("path",),
        "build_node_chain": ("spec",),
    }
    for field in required.get(op_type, ()):
        if op.get(field) is None or op.get(field) == "":
            return f"op '{op_type}' missing required field '{field}'"

    if op_type == "set_parms" and not isinstance(op.get("parms"), dict):
        return "op 'set_parms' requires 'parms' to be a dict"
    if op_type == "build_node_chain" and not isinstance(op.get("spec"), dict):
        return "op 'build_node_chain' requires 'spec' to be a dict"
    return None


async def execute_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a single structured operation against Houdini.

    Returns a dict suitable for `TransactionManager.record_operation`:
        {"op", "params", "result", "snapshot", "status", "dirty", "error"?}

    Never raises — failures are returned with status="failed" and an "error".
    """
    error = _validate_operation(op)
    if error is not None:
        return {
            "op": op.get("op", "<invalid>"),
            "params": dict(op),
            "result": None,
            "snapshot": {},
            "status": "failed",
            "error": error,
            "dirty": [],
        }

    op_type = op["op"]
    executor = _OP_EXECUTORS[op_type]
    try:
        return await executor(op)
    except Exception as exc:  # noqa: BLE001
        return {
            "op": op_type,
            "params": dict(op),
            "result": None,
            "snapshot": {},
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "dirty": [],
        }


# ----- Executors -----------------------------------------------------------

async def _exec_create_node(op: Dict[str, Any]) -> Dict[str, Any]:
    bridge = _bridge()
    parent = op["parent"]
    node_type = op["type"]
    name = op.get("name", "")
    result = await _to_thread(bridge.create_node, parent, node_type, name) or {}
    path = result.get("path") or ""
    cache = get_scene_cache()
    if path:
        cache.mark_node_created(path)
    cache.invalidate("scene_context::")
    return {
        "op": "create_node",
        "params": {"parent": parent, "type": node_type, "name": name},
        "result": {"path": path, "name": result.get("name", name), "type": result.get("type", node_type)},
        "snapshot": {"created_path": path},
        "status": "ok" if path else "failed",
        "dirty": [path] if path else [],
        "error": "" if path else "create_node returned empty path",
    }


async def _exec_set_parms(op: Dict[str, Any]) -> Dict[str, Any]:
    bridge = _bridge()
    node = op["node"]
    new_parms = dict(op["parms"])
    prev: Dict[str, Any] = {}
    for key in new_parms:
        try:
            r = await _to_thread(bridge.get_parm, node, key)
            prev[key] = r.get("value") if isinstance(r, dict) else r
        except Exception:
            prev[key] = None
    await _to_thread(bridge.set_parms, node, new_parms)
    cache = get_scene_cache()
    cache.mark_node_dirty(node)
    cache.invalidate("scene_context::")
    return {
        "op": "set_parms",
        "params": {"node": node, "parms": new_parms},
        "result": {"node": node, "parm_count": len(new_parms)},
        "snapshot": {"node": node, "prev": prev},
        "status": "ok",
        "dirty": [node],
    }


async def _exec_connect_nodes(op: Dict[str, Any]) -> Dict[str, Any]:
    bridge = _bridge()
    from_path = op["from"]
    to_path = op["to"]
    out_idx = int(op.get("out", 0))
    in_idx = int(op.get("in", 0))

    # Snapshot previous input on the target so we can restore it on rollback.
    prev_from = await _read_input_source(bridge, to_path, in_idx)

    await _to_thread(bridge.connect_nodes, from_path, to_path, out_idx, in_idx)
    cache = get_scene_cache()
    cache.mark_connection_changed(from_path, to_path, in_idx)
    cache.invalidate("scene_context::")
    return {
        "op": "connect_nodes",
        "params": {"from": from_path, "to": to_path, "out": out_idx, "in": in_idx},
        "result": {"from": from_path, "to": to_path, "in": in_idx},
        "snapshot": {"to": to_path, "in": in_idx, "prev_from": prev_from},
        "status": "ok",
        "dirty": [to_path],
    }


async def _exec_delete_node(op: Dict[str, Any]) -> Dict[str, Any]:
    bridge = _bridge()
    path = op["path"]
    # Capture a thin snapshot for diagnostics (rollback cannot reconstruct
    # the node — see docs in _rollback_delete_node).
    try:
        info = await _to_thread(bridge.node_info, path)
    except Exception:
        info = {}
    await _to_thread(bridge.delete_node, path)
    cache = get_scene_cache()
    cache.mark_node_deleted(path)
    cache.invalidate("scene_context::")
    return {
        "op": "delete_node",
        "params": {"path": path},
        "result": {"path": path},
        "snapshot": {"path": path, "info": info, "restorable": False},
        "status": "ok",
        "dirty": [path],
    }


async def _exec_set_display_flag(op: Dict[str, Any]) -> Dict[str, Any]:
    return await _exec_set_flag(op, kind="display")


async def _exec_set_render_flag(op: Dict[str, Any]) -> Dict[str, Any]:
    return await _exec_set_flag(op, kind="render")


async def _exec_set_keyframe(op: Dict[str, Any]) -> Dict[str, Any]:
    bridge = _bridge()
    node = op["node"]
    parm = op["parm"]
    frame = float(op["frame"])
    value = op["value"]
    try:
        r = await _to_thread(bridge.get_parm, node, parm)
        prev = r.get("value") if isinstance(r, dict) else r
    except Exception:
        prev = None
    await _to_thread(bridge.set_keyframe, node, parm, frame, value)
    cache = get_scene_cache()
    cache.mark_node_dirty(node)
    cache.invalidate("scene_context::")
    return {
        "op": "set_keyframe",
        "params": {"node": node, "parm": parm, "frame": frame, "value": value},
        "result": {"node": node, "parm": parm, "frame": frame, "value": value},
        "snapshot": {"node": node, "parm": parm, "prev": prev},
        "status": "ok",
        "dirty": [node],
    }


async def _exec_set_flag(op: Dict[str, Any], kind: str) -> Dict[str, Any]:
    bridge = _bridge()
    path = op["path"]
    on = bool(op.get("on", True))
    prev = await _read_flag(bridge, path, kind)
    setter = bridge.set_display_flag if kind == "display" else bridge.set_render_flag
    await _to_thread(setter, path, on)
    cache = get_scene_cache()
    cache.mark_flag_changed(path)
    cache.invalidate("scene_context::")
    return {
        "op": f"set_{kind}_flag",
        "params": {"path": path, "on": on},
        "result": {"path": path, "on": on},
        "snapshot": {"path": path, "kind": kind, "prev": prev},
        "status": "ok",
        "dirty": [path],
    }


async def _exec_cook_node(op: Dict[str, Any]) -> Dict[str, Any]:
    bridge = _bridge()
    path = op["path"]
    force = bool(op.get("force", False))
    await _to_thread(bridge.cook_node, path, force)
    get_scene_cache().mark_node_cooked(path)
    return {
        "op": "cook_node",
        "params": {"path": path, "force": force},
        "result": {"path": path, "cooked": True},
        "snapshot": {"path": path},  # cook has no inverse
        "status": "ok",
        "dirty": [path],
    }


async def _exec_layout_children(op: Dict[str, Any]) -> Dict[str, Any]:
    bridge = _bridge()
    path = op["path"]
    await _to_thread(bridge.layout_children, path)
    return {
        "op": "layout_children",
        "params": {"path": path},
        "result": {"path": path},
        "snapshot": {"path": path},  # layout has no meaningful inverse
        "status": "ok",
        "dirty": [],
    }


async def _exec_build_node_chain(op: Dict[str, Any]) -> Dict[str, Any]:
    spec = op["spec"]
    result = await build_node_chain(spec)
    created = list(result.get("created_paths") or [])
    return {
        "op": "build_node_chain",
        "params": {"spec": spec},
        "result": result,
        "snapshot": {"created_paths": created},
        "status": "ok" if result.get("ok") else "failed",
        "dirty": list(created),
        "error": result.get("error", "") or "",
    }


_OP_EXECUTORS: Dict[str, Callable[[Dict[str, Any]], Any]] = {
    "create_node":      _exec_create_node,
    "set_parms":        _exec_set_parms,
    "connect_nodes":    _exec_connect_nodes,
    "delete_node":      _exec_delete_node,
    "set_display_flag": _exec_set_display_flag,
    "set_render_flag":  _exec_set_render_flag,
    "set_keyframe":     _exec_set_keyframe,
    "cook_node":        _exec_cook_node,
    "layout_children":  _exec_layout_children,
    "build_node_chain": _exec_build_node_chain,
}


# ----- Rollback handlers ---------------------------------------------------
#
# Each handler receives the FULL recorded operation dict (params + result +
# snapshot). MUST NOT raise; returns {"ok": bool, "error"?: str, ...}.

async def _rollback_create_node(recorded: Dict[str, Any]) -> Dict[str, Any]:
    path = (recorded.get("snapshot") or {}).get("created_path", "")
    if not path:
        return {"ok": True, "note": "nothing to undo (no path captured)"}
    try:
        await _to_thread(_bridge().delete_node, path)
        get_scene_cache().mark_node_deleted(path)
        return {"ok": True, "undone": path}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"delete failed: {type(exc).__name__}: {exc}"}


async def _rollback_set_parms(recorded: Dict[str, Any]) -> Dict[str, Any]:
    snap = recorded.get("snapshot") or {}
    node = snap.get("node", "")
    prev = snap.get("prev") or {}
    if not node:
        return {"ok": True, "note": "nothing to undo"}
    restored: Dict[str, Any] = {}
    errors: List[str] = []
    bridge = _bridge()
    for key, value in prev.items():
        if value is None:
            errors.append(f"no prev for '{key}' — skipped")
            continue
        try:
            await _to_thread(bridge.set_parm, node, key, value)
            restored[key] = value
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{key}: {type(exc).__name__}: {exc}")
    get_scene_cache().mark_node_dirty(node)
    return {"ok": not errors, "restored": restored, "error": "; ".join(errors) if errors else ""}


async def _rollback_set_keyframe(recorded: Dict[str, Any]) -> Dict[str, Any]:
    snap = recorded.get("snapshot") or {}
    node = snap.get("node", "")
    parm = snap.get("parm", "")
    prev = snap.get("prev")
    if not node or not parm:
        return {"ok": True, "note": "nothing to undo"}
    if prev is None:
        return {"ok": True, "note": f"no previous value captured for '{node}.{parm}'"}
    try:
        await _to_thread(_bridge().set_parm, node, parm, prev)
        get_scene_cache().mark_node_dirty(node)
        return {"ok": True, "restored": {parm: prev}}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _rollback_connect_nodes(recorded: Dict[str, Any]) -> Dict[str, Any]:
    snap = recorded.get("snapshot") or {}
    to_path = snap.get("to", "")
    in_idx = int(snap.get("in", 0))
    prev_from = snap.get("prev_from")
    if not to_path:
        return {"ok": True, "note": "nothing to undo"}
    try:
        if prev_from:
            # Restore prior connection
            await _to_thread(_bridge().connect_nodes, prev_from, to_path, 0, in_idx)
            return {"ok": True, "restored_from": prev_from}
        else:
            await _disconnect_input(_bridge(), to_path, in_idx)
            return {"ok": True, "disconnected": to_path}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _rollback_delete_node(recorded: Dict[str, Any]) -> Dict[str, Any]:
    # Tier 2 limitation — deleting a node is unrecoverable without a full
    # HIP snapshot. Report the limitation explicitly so audit logs are honest.
    path = (recorded.get("snapshot") or {}).get("path", "")
    return {
        "ok": False,
        "error": (
            f"cannot restore deleted node '{path}' in Tier 2 "
            "(no HIP snapshot system yet)."
        ),
    }


async def _rollback_set_flag(recorded: Dict[str, Any]) -> Dict[str, Any]:
    snap = recorded.get("snapshot") or {}
    path = snap.get("path", "")
    kind = snap.get("kind", "")
    prev = snap.get("prev")
    if not path or kind not in ("display", "render"):
        return {"ok": True, "note": "nothing to undo"}
    if prev is None:
        return {
            "ok": False,
            "error": f"no prev {kind} flag state captured for '{path}'",
        }
    try:
        setter = _bridge().set_display_flag if kind == "display" else _bridge().set_render_flag
        await _to_thread(setter, path, bool(prev))
        get_scene_cache().mark_flag_changed(path)
        return {"ok": True, "restored": bool(prev)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _rollback_noop(recorded: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "note": f"op '{recorded.get('op')}' has no inverse"}


async def _rollback_build_node_chain(recorded: Dict[str, Any]) -> Dict[str, Any]:
    created = list((recorded.get("snapshot") or {}).get("created_paths") or [])
    if not created:
        return {"ok": True, "note": "no nodes created"}
    bridge = _bridge()
    errors: List[str] = []
    deleted: List[str] = []
    for path in reversed(created):
        try:
            await _to_thread(bridge.delete_node, path)
            deleted.append(path)
            get_scene_cache().mark_node_deleted(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}: {type(exc).__name__}: {exc}")
    return {"ok": not errors, "deleted": deleted, "error": "; ".join(errors) if errors else ""}


_OP_ROLLBACKERS: Dict[str, Any] = {
    "create_node":      _rollback_create_node,
    "set_parms":        _rollback_set_parms,
    "connect_nodes":    _rollback_connect_nodes,
    "delete_node":      _rollback_delete_node,
    "set_display_flag": _rollback_set_flag,
    "set_render_flag":  _rollback_set_flag,
    "set_keyframe":     _rollback_set_keyframe,
    "cook_node":        _rollback_noop,
    "layout_children":  _rollback_noop,
    "build_node_chain": _rollback_build_node_chain,
}


# ----- Bridge helpers used by execute / rollback ---------------------------

async def _read_flag(bridge, path: str, kind: str) -> Optional[bool]:
    """Read display or render flag via run_code (no dedicated bridge method)."""
    attr = "isDisplayFlagSet" if kind == "display" else "isRenderFlagSet"
    code = (
        f"_n = hou.node('{path}')\n"
        f"if _n is not None and hasattr(_n, '{attr}'):\n"
        f"    result = bool(_n.{attr}())\n"
        f"else:\n"
        f"    result = None\n"
    )
    try:
        r = await _to_thread(bridge.run_code, code)
        return r.get("result") if isinstance(r, dict) else None
    except Exception:
        return None


async def _read_input_source(bridge, target_path: str, in_idx: int) -> Optional[str]:
    """Return the path of the node currently feeding input `in_idx` of target."""
    code = (
        f"_n = hou.node('{target_path}')\n"
        f"if _n is None:\n"
        f"    result = None\n"
        f"else:\n"
        f"    _inputs = list(_n.inputs())\n"
        f"    if {in_idx} < len(_inputs) and _inputs[{in_idx}] is not None:\n"
        f"        result = _inputs[{in_idx}].path()\n"
        f"    else:\n"
        f"        result = None\n"
    )
    try:
        r = await _to_thread(bridge.run_code, code)
        return r.get("result") if isinstance(r, dict) else None
    except Exception:
        return None


async def _disconnect_input(bridge, target_path: str, in_idx: int) -> None:
    code = (
        f"_n = hou.node('{target_path}')\n"
        f"if _n is not None and {in_idx} < len(_n.inputs()):\n"
        f"    _n.setInput({in_idx}, None)\n"
    )
    await _to_thread(bridge.run_code, code)


# ----- Handler registration ------------------------------------------------

def _register_rollback_handlers() -> None:
    """Register Houdini rollback handlers with the transaction manager.

    Called at module import time so any code path that imports
    `src.runtime.houdini_runtime` (which is everything that mutates Houdini)
    transparently gets the rollback contract.
    """
    from src.runtime import transaction_manager as _tm
    for op_type, handler in _OP_ROLLBACKERS.items():
        _tm.register_rollback_handler(op_type, handler)


_register_rollback_handlers()
