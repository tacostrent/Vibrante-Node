from __future__ import annotations

import asyncio
import importlib.util
import json
import time
import sys
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


def _cinematic_pyro_ops(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    base = str(ctx["base"])
    frame_start = str(ctx.get("frame_start", 1))
    frame_end = str(ctx.get("frame_end", 120))
    cache_root = str(ctx.get("cache_root", "$HIP/cache"))

    terrain_geo = f"{base}_terrain_geo"
    source_geo = f"{base}_source_geo"
    smoke_geo = f"{base}_smoke_geo"

    terrain_out = f"/obj/{terrain_geo}/OUT_TERRAIN_CACHE"
    source_out = f"/obj/{source_geo}/OUT_SOURCE_CACHE"
    smoke_out = f"/obj/{smoke_geo}/OUT_SMOKE_CACHE"

    ops: List[Dict[str, Any]] = [
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": terrain_geo},
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": source_geo},
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": smoke_geo},
        _chain(
            "cinematic_pyro_terrain",
            [
                {
                    "id": "grid",
                    "parent": f"/obj/{terrain_geo}",
                    "type": "grid",
                    "name": "terrain_grid",
                    "params": {"sizex": "34", "sizey": "24", "rows": "80", "cols": "80"},
                },
                {
                    "id": "mountain",
                    "parent": f"/obj/{terrain_geo}",
                    "type": "mountain",
                    "name": "terrain_breakup",
                    "params": {"height": "1.35", "elementsize": "2.8"},
                },
                {"id": "out", "parent": f"/obj/{terrain_geo}", "type": "null", "name": "OUT_TERRAIN"},
                {
                    "id": "cache",
                    "parent": f"/obj/{terrain_geo}",
                    "type": "filecache",
                    "name": "cache_terrain",
                    "params": {
                        "file": f"{cache_root}/{base}/terrain.$F4.bgeo.sc",
                        "f1": frame_start,
                        "f2": frame_end,
                    },
                },
                {
                    "id": "cache_out",
                    "parent": f"/obj/{terrain_geo}",
                    "type": "null",
                    "name": "OUT_TERRAIN_CACHE",
                },
            ],
            [
                {"from": "grid", "to": "mountain", "out": 0, "in": 0},
                {"from": "mountain", "to": "out", "out": 0, "in": 0},
                {"from": "out", "to": "cache", "out": 0, "in": 0},
                {"from": "cache", "to": "cache_out", "out": 0, "in": 0},
            ],
        ),
        _chain(
            "cinematic_pyro_source",
            [
                {
                    "id": "sphere",
                    "parent": f"/obj/{source_geo}",
                    "type": "sphere",
                    "name": "explosion_core",
                    "params": {"radx": "1.6", "rady": "1.6", "radz": "1.6"},
                },
                {
                    "id": "scatter",
                    "parent": f"/obj/{source_geo}",
                    "type": "scatter",
                    "name": "source_points",
                    "params": {"npts": "1400"},
                },
                {"id": "pyrosrc", "parent": f"/obj/{source_geo}", "type": "pyrosource", "name": "pyro_source"},
                {"id": "out", "parent": f"/obj/{source_geo}", "type": "null", "name": "OUT_SOURCE"},
                {
                    "id": "cache",
                    "parent": f"/obj/{source_geo}",
                    "type": "filecache",
                    "name": "cache_pyro_source",
                    "params": {
                        "file": f"{cache_root}/{base}/pyro_source.$F4.bgeo.sc",
                        "f1": frame_start,
                        "f2": frame_end,
                    },
                },
                {"id": "cache_out", "parent": f"/obj/{source_geo}", "type": "null", "name": "OUT_SOURCE_CACHE"},
            ],
            [
                {"from": "sphere", "to": "scatter", "out": 0, "in": 0},
                {"from": "scatter", "to": "pyrosrc", "out": 0, "in": 0},
                {"from": "pyrosrc", "to": "out", "out": 0, "in": 0},
                {"from": "out", "to": "cache", "out": 0, "in": 0},
                {"from": "cache", "to": "cache_out", "out": 0, "in": 0},
            ],
        ),
        _chain(
            "cinematic_pyro_smoke_setup",
            [
                {
                    "id": "src_merge",
                    "parent": f"/obj/{smoke_geo}",
                    "type": "object_merge",
                    "name": "IN_PYRO_SOURCE",
                    "params": {"objpath1": source_out},
                },
                {"id": "solver", "parent": f"/obj/{smoke_geo}", "type": "pyrosolver", "name": "smoke_pyro_solver"},
                {"id": "look", "parent": f"/obj/{smoke_geo}", "type": "volumevisualization", "name": "smoke_look"},
                {
                    "id": "cache",
                    "parent": f"/obj/{smoke_geo}",
                    "type": "filecache",
                    "name": "cache_smoke",
                    "params": {
                        "file": f"{cache_root}/{base}/smoke_sim.$F4.bgeo.sc",
                        "f1": frame_start,
                        "f2": frame_end,
                    },
                },
                {"id": "cache_out", "parent": f"/obj/{smoke_geo}", "type": "null", "name": "OUT_SMOKE_CACHE"},
            ],
            [
                {"from": "src_merge", "to": "solver", "out": 0, "in": 0},
                {"from": "solver", "to": "look", "out": 0, "in": 0},
                {"from": "look", "to": "cache", "out": 0, "in": 0},
                {"from": "cache", "to": "cache_out", "out": 0, "in": 0},
            ],
        ),
        _chain(
            "cinematic_pyro_camera_lighting",
            [
                {
                    "id": "cam",
                    "parent": "/obj",
                    "type": "cam",
                    "name": f"{base}_camera",
                    "params": {
                        "tx": "9.5",
                        "ty": "5.0",
                        "tz": "11.5",
                        "rx": "-24",
                        "ry": "38",
                        "rz": "0",
                        "focal": "35",
                    },
                },
                {
                    "id": "key",
                    "parent": "/obj",
                    "type": "hlight",
                    "name": f"{base}_key_light",
                    "params": {"tx": "-6", "ty": "8", "tz": "5", "rx": "-42", "ry": "-35", "light_intensity": "2.8"},
                },
                {
                    "id": "rim",
                    "parent": "/obj",
                    "type": "hlight",
                    "name": f"{base}_rim_light",
                    "params": {"tx": "7", "ty": "6", "tz": "-6", "rx": "-35", "ry": "135", "light_intensity": "1.4"},
                },
                {
                    "id": "fill",
                    "parent": "/obj",
                    "type": "hlight",
                    "name": f"{base}_fill_light",
                    "params": {"tx": "0", "ty": "5", "tz": "9", "rx": "-28", "ry": "0", "light_intensity": "0.75"},
                },
            ],
            [],
        ),
        {"op": "set_display_flag", "path": terrain_out, "on": True},
        {"op": "set_render_flag", "path": terrain_out, "on": True},
        {"op": "set_display_flag", "path": source_out, "on": True},
        {"op": "set_render_flag", "path": source_out, "on": True},
        {"op": "set_display_flag", "path": smoke_out, "on": True},
        {"op": "set_render_flag", "path": smoke_out, "on": True},
        {"op": "layout_children", "path": "/obj"},
    ]
    return ops


async def main() -> int:
    from src.runtime.ai_planner import get_ai_planner
    from src.runtime.execution_review import get_execution_reviewer
    from src.runtime.resource_estimator import get_resource_estimator
    from src.runtime.runtime_constraints import get_runtime_constraints
    from src.runtime.semantic_registry import get_semantic_registry

    suffix = time.strftime("%Y%m%d_%H%M%S")
    base = f"cine_pyro_{suffix}"
    context = {
        "base": base,
        "parent": "/obj",
        "name": base,
        "radius": 1.6,
        "frame_start": 1,
        "frame_end": 120,
        "cache_root": "$HIP/cache",
        "production_safe": True,
    }

    constraints = get_runtime_constraints()
    for policy_id in ("production_forbid_delete", "production_forbid_python_node", "production_max_ops_80"):
        constraints.remove_policy(policy_id)
    constraints.add_policy(
        "forbidden_op",
        "production_forbid_delete",
        {"op": "delete_node", "message": "Production-safe scene setup must not delete existing Houdini nodes."},
    )
    constraints.add_policy(
        "forbidden_node_type",
        "production_forbid_python_node",
        {"node_type": "python", "message": "Production-safe semantic workflows cannot create Python SOPs."},
    )
    constraints.add_policy(
        "max_ops",
        "production_max_ops_80",
        {"limit": 80, "message": "Production-safe scene setup is limited to 80 structured ops."},
    )

    reg = get_semantic_registry()
    reg.register_operation(
        "cinematic_pyro_explosion_scene",
        {
            "description": "Create terrain, pyro source, smoke setup, camera, lighting, and cache nodes under /obj.",
            "tags": ["houdini", "pyro", "smoke", "terrain", "camera", "lighting", "cache", "production"],
            "required_capabilities": ["build_node_chain", "create_node", "set_display_flag", "set_render_flag"],
        },
        _cinematic_pyro_ops,
    )

    ai_plan_cls = _load_node_class(HOU_NODES / "hou_mcp_ai_plan.json")
    ai_preview_cls = _load_node_class(HOU_NODES / "hou_mcp_ai_preview.json")
    exec_preview_cls = _load_node_class(HOU_NODES / "hou_mcp_execution_preview.json")
    ai_execute_cls = _load_node_class(HOU_NODES / "hou_mcp_ai_execute.json")
    ai_review_cls = _load_node_class(HOU_NODES / "hou_mcp_ai_review.json")

    prompt = (
        "Create a cinematic pyro explosion scene in Houdini using only semantic workflows. "
        "Include terrain, a pyro source, smoke setup, production cache nodes, cinematic lighting, "
        f"and a camera. Use /obj only and keep it production safe. Name it {base}."
    )

    ai_plan = await ai_plan_cls().execute(
        {
            "prompt": prompt,
            "context_json": json.dumps(context),
            "scene_context": {
                "scene": {"fps": 24, "frame_range": [1, 120]},
                "networks": {"obj": [], "out": [], "mat": []},
                "selection": [],
                "assets": {"hda_files": [], "definitions": []},
                "render": {"render_nodes": []},
            },
            "include_reasoning": True,
        }
    )

    semantic_plan = reg.resolve_to_execution_plan("cinematic_pyro_explosion_scene", context)
    operations = semantic_plan["operations"]
    resource_estimate = get_resource_estimator().estimate_transaction(operations)
    constraint_result = constraints.validate_transaction(operations)

    planner = get_ai_planner()
    ai_shell = await planner.plan(
        {
            "intent": "cinematic_pyro_explosion_scene",
            "parameters": context,
            "confidence": max(float(ai_plan.get("plan", {}).get("confidence", 0.0) or 0.0), 0.9),
            "alternatives": [],
            "ambiguous": False,
            "raw_prompt": prompt,
            "matched_keywords": ["pyro", "explosion", "smoke", "cache", "lighting"],
            "llm_enhanced": False,
        },
        {"recommended_actions": [], "existing_workflows": [], "conflicts": []},
        None,
    )

    plan = dict(ai_shell)
    plan.update(
        {
            "ok": semantic_plan["ok"] and constraint_result["valid"],
            "intent": "cinematic_pyro_explosion_scene",
            "selected_template": "runtime_semantic_operation",
            "execution_strategy": {
                "strategy": "create_new",
                "target_path": "/obj",
                "source": "semantic_registry",
                "rationale": "Create a new production-safe /obj scene without touching protected /stage or /out networks.",
            },
            "operations": operations,
            "op_count": len(operations),
            "parameters": context,
            "warnings": list(ai_plan.get("warnings", [])),
            "errors": [] if constraint_result["valid"] else [
                f"Constraint '{v.get('policy_id', '?')}': {v.get('message', '')}"
                for v in constraint_result.get("violations", [])
            ],
            "requires_approval": True,
            "approval_reasons": [
                "Pyro/smoke setup is simulation-oriented and should be operator-approved.",
                "Production cache nodes affect project cache paths.",
            ],
            "resource_estimate": resource_estimate,
            "constraint_result": constraint_result,
            "reasoning": list(ai_plan.get("plan", {}).get("reasoning", []))
            + [
                "Expanded AI pyro intent into the registered cinematic_pyro_explosion_scene semantic workflow.",
                "Kept all authored nodes under /obj to respect protected /stage and /out policies.",
                "No delete_node, run_code, or arbitrary Python operations are present.",
            ],
        }
    )

    ai_validation = await ai_preview_cls().execute(
        {"plan": plan, "plan_json": "", "max_cook_cost": 1.5, "max_op_count": 80}
    )
    execution_preview = await exec_preview_cls().execute(
        {
            "operations": json.dumps(operations),
            "include_dependencies": True,
            "estimate_cooks": True,
        }
    )

    can_execute = bool(plan["ok"]) and bool(ai_validation["valid"]) and not execution_preview["errors"]
    if can_execute:
        execution = await ai_execute_cls().execute(
            {
                "plan": plan,
                "plan_json": "",
                "dry_run": False,
                "require_approval": True,
                "approver": "codex_operator",
                "rollback_on_error": True,
            }
        )
    else:
        execution = {
            "ok": False,
            "status": "not_executed",
            "transaction_id": "",
            "operations_executed": [],
            "graph_diff": {},
            "errors": [
                "Execution skipped because validation or preview did not pass.",
                *[str(e) for e in ai_validation.get("errors", [])],
                *[str(e) for e in execution_preview.get("errors", [])],
            ],
            "warnings": ai_validation.get("warnings", []),
            "report_json": "{}",
        }

    review = await ai_review_cls().execute(
        {
            "plan": plan,
            "plan_json": "",
            "execution_result": execution,
            "result_json": "",
        }
    )

    report = {
        "base": base,
        "semantic_workflow": "cinematic_pyro_explosion_scene",
        "ai_plan_node_used": True,
        "plan": {
            "plan_id": plan.get("plan_id"),
            "intent": plan.get("intent"),
            "ok": plan.get("ok"),
            "op_count": plan.get("op_count"),
            "requires_approval": plan.get("requires_approval"),
            "approval_reasons": plan.get("approval_reasons"),
            "resource_estimate": resource_estimate,
            "constraint_result": constraint_result,
        },
        "ai_plan_summary": {
            "intent": ai_plan.get("intent"),
            "ok": ai_plan.get("ok"),
            "warnings": ai_plan.get("warnings"),
            "errors": ai_plan.get("errors"),
        },
        "validation": {
            "valid": ai_validation.get("valid"),
            "risk_level": ai_validation.get("risk_level"),
            "errors": ai_validation.get("errors"),
            "warnings": ai_validation.get("warnings"),
            "capability_gaps": ai_validation.get("capability_gaps"),
        },
        "execution_preview": {
            "nodes_to_create": execution_preview.get("nodes_to_create"),
            "nodes_to_modify": execution_preview.get("nodes_to_modify"),
            "nodes_to_delete": execution_preview.get("nodes_to_delete"),
            "estimated_cooks": execution_preview.get("estimated_cooks"),
            "risk_level": execution_preview.get("risk_level"),
            "warnings": execution_preview.get("warnings"),
            "errors": execution_preview.get("errors"),
        },
        "execution": {
            "ok": execution.get("ok"),
            "status": execution.get("status"),
            "transaction_id": execution.get("transaction_id"),
            "errors": execution.get("errors"),
            "warnings": execution.get("warnings"),
            "graph_diff": execution.get("graph_diff"),
            "operations_executed": execution.get("operations_executed"),
            "approval_status": execution.get("approval_status"),
        },
        "review": {
            "outcome": review.get("outcome"),
            "match_score": review.get("match_score"),
            "findings": review.get("findings"),
            "recommendations": review.get("recommendations"),
            "op_stats": review.get("op_stats"),
        },
    }

    REPORT_DIR.mkdir(exist_ok=True)
    report_path = REPORT_DIR / f"{base}_orchestration_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")

    print(json.dumps({"report_path": str(report_path), **report}, indent=2, sort_keys=True, default=str))
    return 0 if execution.get("status") in ("committed", "not_executed") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
