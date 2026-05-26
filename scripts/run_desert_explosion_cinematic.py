from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
HOU_NODES = ROOT / "plugins" / "houdini" / "v_nodes_houdini"
REPORT_DIR = ROOT / "tmp"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_node_class(node_json: Path):
    data = json.loads(node_json.read_text(encoding="utf-8"))
    module_name = f"_vibrante_{data['node_id']}_{int(time.time() * 1000)}"
    spec = importlib.util.spec_from_loader(module_name, loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(data["python_code"], module.__dict__)
    return module.register_node()


def _chain(intent: str, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]):
    return {
        "op": "build_node_chain",
        "spec": {
            "intent": intent,
            "nodes": nodes,
            "connections": connections,
            "layout": True,
            "cook": False,
        },
    }


def _template_ops(template_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    from src.runtime.workflow_templates import get_workflow_templates

    return get_workflow_templates().apply_template(template_id, context)


def _strip_build_params(ops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sanitized = json.loads(json.dumps(ops))
    for op in sanitized:
        if op.get("op") != "build_node_chain":
            continue
        for node in (op.get("spec") or {}).get("nodes") or []:
            node.pop("params", None)
    return sanitized


def _create_ops_only(ops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [op for op in json.loads(json.dumps(ops)) if op.get("op") != "set_parms"]


def _desert_explosion_ops(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    base = str(ctx["base"])
    frame_start = str(ctx.get("frame_start", 1))
    frame_mid = str(ctx.get("frame_mid", 56))
    frame_end = str(ctx.get("frame_end", 144))
    cache_root = str(ctx.get("cache_root", "$HIP/cache"))
    render_root = str(ctx.get("render_root", "$HIP/render"))
    usd_root = str(ctx.get("usd_root", "$HIP/usd"))

    terrain_geo = f"{base}_desert_terrain_geo"
    debris_geo = f"{base}_ground_debris_geo"
    source_geo = f"{base}_pyro_source_geo"
    smoke_geo = f"{base}_pyro_smoke_geo"
    camera_name = f"{base}_camera"

    terrain_out = f"/obj/{terrain_geo}/OUT_TERRAIN_CACHE"
    debris_out = f"/obj/{debris_geo}/OUT_DEBRIS_CACHE"
    source_out = f"/obj/{source_geo}/OUT_SOURCE_CACHE"
    smoke_out = f"/obj/{smoke_geo}/OUT_SMOKE_CACHE"

    ops: List[Dict[str, Any]] = [
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": terrain_geo},
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": debris_geo},
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": source_geo},
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": smoke_geo},
        _chain(
            "desert_terrain_cache",
            [
                {"id": "grid", "parent": f"/obj/{terrain_geo}", "type": "grid", "name": "desert_plane",
                 "params": {"sizex": "72", "sizey": "42", "rows": "110", "cols": "110"}},
                {"id": "dunes", "parent": f"/obj/{terrain_geo}", "type": "mountain", "name": "dune_noise",
                 "params": {"height": "0.9", "elementsize": "7.5"}},
                {"id": "out", "parent": f"/obj/{terrain_geo}", "type": "null", "name": "OUT_TERRAIN"},
                {"id": "cache", "parent": f"/obj/{terrain_geo}", "type": "filecache", "name": "cache_desert_terrain",
                 "params": {"file": f"{cache_root}/{base}/terrain.$F4.bgeo.sc", "f1": frame_start, "f2": frame_end}},
                {"id": "cache_out", "parent": f"/obj/{terrain_geo}", "type": "null", "name": "OUT_TERRAIN_CACHE"},
            ],
            [
                {"from": "grid", "to": "dunes", "out": 0, "in": 0},
                {"from": "dunes", "to": "out", "out": 0, "in": 0},
                {"from": "out", "to": "cache", "out": 0, "in": 0},
                {"from": "cache", "to": "cache_out", "out": 0, "in": 0},
            ],
        ),
        _chain(
            "ground_debris_cache",
            [
                {"id": "debris_area", "parent": f"/obj/{debris_geo}", "type": "grid", "name": "debris_scatter_area",
                 "params": {"sizex": "18", "sizey": "12", "rows": "24", "cols": "24"}},
                {"id": "scatter", "parent": f"/obj/{debris_geo}", "type": "scatter", "name": "debris_points",
                 "params": {"npts": "360"}},
                {"id": "chunk", "parent": f"/obj/{debris_geo}", "type": "box", "name": "hero_debris_chunk",
                 "params": {"sizex": "0.28", "sizey": "0.18", "sizez": "0.16"}},
                {"id": "debris_out", "parent": f"/obj/{debris_geo}", "type": "null", "name": "OUT_DEBRIS"},
                {"id": "cache", "parent": f"/obj/{debris_geo}", "type": "filecache", "name": "cache_ground_debris",
                 "params": {"file": f"{cache_root}/{base}/ground_debris.$F4.bgeo.sc", "f1": frame_start, "f2": frame_end}},
                {"id": "cache_out", "parent": f"/obj/{debris_geo}", "type": "null", "name": "OUT_DEBRIS_CACHE"},
            ],
            [
                {"from": "debris_area", "to": "scatter", "out": 0, "in": 0},
                {"from": "scatter", "to": "debris_out", "out": 0, "in": 0},
                {"from": "debris_out", "to": "cache", "out": 0, "in": 0},
                {"from": "cache", "to": "cache_out", "out": 0, "in": 0},
            ],
        ),
        _chain(
            "pyro_explosion_source_cache",
            [
                {"id": "sphere", "parent": f"/obj/{source_geo}", "type": "sphere", "name": "blast_core",
                 "params": {"radx": "2.15", "rady": "1.45", "radz": "2.15"}},
                {"id": "points", "parent": f"/obj/{source_geo}", "type": "scatter", "name": "ignition_points",
                 "params": {"npts": "1900"}},
                {"id": "pyro", "parent": f"/obj/{source_geo}", "type": "pyrosource", "name": "pyro_source"},
                {"id": "out", "parent": f"/obj/{source_geo}", "type": "null", "name": "OUT_SOURCE"},
                {"id": "cache", "parent": f"/obj/{source_geo}", "type": "filecache", "name": "cache_pyro_source",
                 "params": {"file": f"{cache_root}/{base}/pyro_source.$F4.bgeo.sc", "f1": frame_start, "f2": frame_end}},
                {"id": "cache_out", "parent": f"/obj/{source_geo}", "type": "null", "name": "OUT_SOURCE_CACHE"},
            ],
            [
                {"from": "sphere", "to": "points", "out": 0, "in": 0},
                {"from": "points", "to": "pyro", "out": 0, "in": 0},
                {"from": "pyro", "to": "out", "out": 0, "in": 0},
                {"from": "out", "to": "cache", "out": 0, "in": 0},
                {"from": "cache", "to": "cache_out", "out": 0, "in": 0},
            ],
        ),
        _chain(
            "pyro_smoke_sim_cache",
            [
                {"id": "src", "parent": f"/obj/{smoke_geo}", "type": "object_merge", "name": "IN_PYRO_SOURCE",
                 "params": {"objpath1": source_out}},
                {"id": "solver", "parent": f"/obj/{smoke_geo}", "type": "pyrosolver", "name": "desert_explosion_solver"},
                {"id": "look", "parent": f"/obj/{smoke_geo}", "type": "volumevisualization", "name": "smoke_fire_look"},
                {"id": "cache", "parent": f"/obj/{smoke_geo}", "type": "filecache", "name": "cache_pyro_smoke",
                 "params": {"file": f"{cache_root}/{base}/pyro_smoke.$F4.bgeo.sc", "f1": frame_start, "f2": frame_end}},
                {"id": "cache_out", "parent": f"/obj/{smoke_geo}", "type": "null", "name": "OUT_SMOKE_CACHE"},
            ],
            [
                {"from": "src", "to": "solver", "out": 0, "in": 0},
                {"from": "solver", "to": "look", "out": 0, "in": 0},
                {"from": "look", "to": "cache", "out": 0, "in": 0},
                {"from": "cache", "to": "cache_out", "out": 0, "in": 0},
            ],
        ),
        _chain(
            "camera_and_environment_light",
            [
                {"id": "cam", "parent": "/obj", "type": "cam", "name": camera_name,
                 "params": {"tx": "13.0", "ty": "4.2", "tz": "15.0", "rx": "-18", "ry": "39", "rz": "0", "focal": "38"}},
                {"id": "sun", "parent": "/obj", "type": "hlight", "name": f"{base}_desert_sun",
                 "params": {"tx": "-9", "ty": "12", "tz": "7", "rx": "-48", "ry": "-38", "light_intensity": "3.4"}},
                {"id": "rim", "parent": "/obj", "type": "hlight", "name": f"{base}_heat_rim",
                 "params": {"tx": "8", "ty": "5", "tz": "-8", "rx": "-25", "ry": "140", "light_intensity": "1.3"}},
            ],
            [],
        ),
    ]

    ops.extend([
        {"op": "set_display_flag", "path": terrain_out, "on": True},
        {"op": "set_render_flag", "path": terrain_out, "on": True},
        {"op": "set_display_flag", "path": debris_out, "on": True},
        {"op": "set_render_flag", "path": debris_out, "on": True},
        {"op": "set_display_flag", "path": source_out, "on": True},
        {"op": "set_render_flag", "path": source_out, "on": True},
        {"op": "set_display_flag", "path": smoke_out, "on": True},
        {"op": "set_render_flag", "path": smoke_out, "on": True},
        {"op": "set_keyframe", "node": f"/obj/{camera_name}", "parm": "tx", "frame": frame_start, "value": 13.0},
        {"op": "set_keyframe", "node": f"/obj/{camera_name}", "parm": "ty", "frame": frame_start, "value": 4.2},
        {"op": "set_keyframe", "node": f"/obj/{camera_name}", "parm": "tz", "frame": frame_start, "value": 15.0},
        {"op": "set_keyframe", "node": f"/obj/{camera_name}", "parm": "tx", "frame": frame_mid, "value": 7.5},
        {"op": "set_keyframe", "node": f"/obj/{camera_name}", "parm": "ty", "frame": frame_mid, "value": 3.5},
        {"op": "set_keyframe", "node": f"/obj/{camera_name}", "parm": "tz", "frame": frame_mid, "value": 8.8},
        {"op": "set_keyframe", "node": f"/obj/{camera_name}", "parm": "tx", "frame": frame_end, "value": 4.0},
        {"op": "set_keyframe", "node": f"/obj/{camera_name}", "parm": "ty", "frame": frame_end, "value": 4.9},
        {"op": "set_keyframe", "node": f"/obj/{camera_name}", "parm": "tz", "frame": frame_end, "value": 6.5},
    ])

    # Workflow templates: reusable Solaris lighting, Karma render, and USD export.
    ops.extend(_strip_build_params(
        _template_ops("solaris_lighting_setup", {"stage_path": "/stage", "name": f"{base}_solaris"})
    ))
    ops.append(_chain(
        "solaris_environment_and_usd_import_scaffold",
        [
            {"id": "terrain_import", "parent": "/stage", "type": "sopimport", "name": f"{base}_terrain_usd"},
            {"id": "debris_import", "parent": "/stage", "type": "sopimport", "name": f"{base}_debris_usd"},
            {"id": "smoke_import", "parent": "/stage", "type": "sopimport", "name": f"{base}_smoke_usd"},
            {"id": "env", "parent": "/stage", "type": "domelight", "name": f"{base}_desert_env_light"},
            {"id": "merge", "parent": "/stage", "type": "merge", "name": f"{base}_usd_scene"},
        ],
        [
            {"from": "terrain_import", "to": "merge", "out": 0, "in": 0},
            {"from": "debris_import", "to": "merge", "out": 0, "in": 1},
            {"from": "smoke_import", "to": "merge", "out": 0, "in": 2},
            {"from": "env", "to": "merge", "out": 0, "in": 3},
        ],
    ))
    ops.extend([
        {"op": "set_parms", "node": f"/stage/{base}_terrain_usd", "parms": {"soppath": terrain_out, "primpath": "/World/desert/terrain"}},
        {"op": "set_parms", "node": f"/stage/{base}_debris_usd", "parms": {"soppath": debris_out, "primpath": "/World/desert/debris"}},
        {"op": "set_parms", "node": f"/stage/{base}_smoke_usd", "parms": {"soppath": smoke_out, "primpath": "/World/fx/explosion_smoke"}},
    ])
    ops.extend(_create_ops_only(_template_ops(
        "karma_render",
        {
            "name": base,
            "stage_path": "/stage",
            "output_path": f"{render_root}/{base}/{base}.$F4.exr",
            "res_x": 2048,
            "res_y": 858,
        },
    )))
    ops.append({
        "op": "set_parms",
        "node": f"/out/{base}_karma",
        "parms": {
            "picture": f"{render_root}/{base}/{base}.$F4.exr",
            "camera": f"/obj/{camera_name}",
            "f1": frame_start,
            "f2": frame_end,
            "resolutionx": "2048",
            "resolutiony": "858",
        },
    })
    ops.extend(_create_ops_only(_template_ops(
        "usd_export",
        {
            "name": base,
            "output_path": f"{usd_root}/{base}/{base}.usd",
            "frame_start": frame_start,
            "frame_end": frame_end,
        },
    )))
    ops.append({
        "op": "set_parms",
        "node": f"/out/{base}_usd_out",
        "parms": {
            "lopoutput": f"{usd_root}/{base}/{base}.usd",
            "loppath": "/stage",
            "f1": frame_start,
            "f2": frame_end,
        },
    })
    ops.extend([
        {"op": "layout_children", "path": "/obj"},
        {"op": "layout_children", "path": "/stage"},
        {"op": "layout_children", "path": "/out"},
    ])
    return ops


async def main() -> int:
    from src.runtime.execution_review import get_execution_reviewer
    from src.runtime.resource_estimator import get_resource_estimator
    from src.runtime.semantic_registry import get_semantic_registry

    suffix = time.strftime("%Y%m%d_%H%M%S")
    base = f"desert_explosion_{suffix}"
    context = {
        "base": base,
        "frame_start": 1,
        "frame_mid": 56,
        "frame_end": 144,
        "cache_root": "$HIP/cache",
        "render_root": "$HIP/render",
        "usd_root": "$HIP/usd",
    }

    reg = get_semantic_registry()
    reg.register_operation(
        "desert_explosion_cinematic_setup",
        {
            "description": "Desert pyro explosion cinematic with USD/Solaris/Karma scaffold.",
            "tags": ["desert", "pyro", "solaris", "karma", "usd", "camera", "debris"],
            "required_capabilities": ["build_node_chain", "set_keyframe", "create_node"],
        },
        _desert_explosion_ops,
    )

    semantic_plan = reg.resolve_to_execution_plan("desert_explosion_cinematic_setup", context)
    operations = semantic_plan["operations"]
    no_destructive = all(op.get("op") != "delete_node" for op in operations)
    destructive_errors = [] if no_destructive else ["Plan contains delete_node; refusing execution."]
    safety_result = {
        "valid": no_destructive and len(operations) <= 90,
        "op_count": len(operations),
        "violations": destructive_errors + (
            [f"Operation count {len(operations)} exceeds 90."] if len(operations) > 90 else []
        ),
        "rules": ["no delete_node", "max 90 structured operations"],
    }

    exec_preview_cls = _load_node_class(HOU_NODES / "hou_mcp_execution_preview.json")
    txn_cls = _load_node_class(HOU_NODES / "hou_mcp_transaction.json")

    resource_estimate = get_resource_estimator().estimate_transaction(operations)
    execution_preview = await exec_preview_cls().execute({
        "operations": json.dumps(operations),
        "include_dependencies": True,
        "estimate_cooks": True,
    })
    dry_run = await txn_cls().execute({
        "transaction_name": f"dryrun:{base}",
        "operations": json.dumps(operations),
        "dry_run": True,
        "auto_commit": False,
        "rollback_on_error": True,
    })

    preview_errors = (
        list(execution_preview.get("errors") or [])
        + list(dry_run.get("errors") or [])
        + list(safety_result["violations"])
    )
    if preview_errors:
        execution = {
            "ok": False,
            "status": "not_executed",
            "transaction_id": "",
            "operations_executed": [],
            "graph_diff": {},
            "errors": preview_errors,
            "warnings": execution_preview.get("warnings", []),
        }
    else:
        execution = await txn_cls().execute({
            "transaction_name": f"semantic:desert_explosion_cinematic_setup:{base}",
            "operations": json.dumps(operations),
            "dry_run": False,
            "auto_commit": True,
            "rollback_on_error": True,
        })

    plan = {
        "ok": semantic_plan["ok"] and safety_result["valid"],
        "intent": "desert_explosion_cinematic_setup",
        "operations": operations,
        "op_count": len(operations),
        "requires_approval": True,
        "warnings": [],
        "errors": destructive_errors,
        "template_ids_used": ["solaris_lighting_setup", "karma_render", "usd_export"],
        "resource_estimate": resource_estimate,
    }
    exec_result = {
        "status": execution.get("status"),
        "intent": plan["intent"],
        "operations_executed": execution.get("operations_executed", []),
        "graph_diff": execution.get("graph_diff", {}),
        "errors": execution.get("errors", []),
        "warnings": execution.get("warnings", []),
        "transaction_id": execution.get("transaction_id", ""),
    }
    review = get_execution_reviewer().review(plan, exec_result)

    report = {
        "base": base,
        "semantic_workflow": "desert_explosion_cinematic_setup",
        "workflow_templates_used": plan["template_ids_used"],
        "non_destructive": no_destructive,
        "plan": {
            "ok": plan["ok"],
            "op_count": len(operations),
            "resource_estimate": resource_estimate,
            "safety_result": safety_result,
        },
        "preview": {
            "dry_run_status": dry_run.get("status"),
            "nodes_to_create": execution_preview.get("nodes_to_create"),
            "nodes_to_modify": execution_preview.get("nodes_to_modify"),
            "nodes_to_delete": execution_preview.get("nodes_to_delete"),
            "estimated_cooks": execution_preview.get("estimated_cooks"),
            "risk_level": execution_preview.get("risk_level"),
            "errors": execution_preview.get("errors"),
            "warnings": execution_preview.get("warnings"),
        },
        "execution": {
            "status": execution.get("status"),
            "transaction_id": execution.get("transaction_id"),
            "errors": execution.get("errors"),
            "rollback_performed": execution.get("rollback_performed", False),
            "graph_diff": execution.get("graph_diff"),
            "operations_executed": execution.get("operations_executed"),
        },
        "review": review,
    }

    REPORT_DIR.mkdir(exist_ok=True)
    report_path = REPORT_DIR / f"{base}_orchestration_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps({"report_path": str(report_path), **report}, indent=2, sort_keys=True, default=str))
    return 0 if execution.get("status") == "committed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
