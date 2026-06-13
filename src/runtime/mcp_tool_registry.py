"""
MCP Tool Registry
=================
Bridges the semantic runtime, orchestration runtime, workflow templates,
AI planning tools, and review systems to the MCP protocol's tool surface.

ONLY semantic orchestration tools are registered.
Raw Houdini mutation APIs (create_node, set_parm, run_python …) are NEVER
exposed here.  The semantic layer is the mandatory choke point.

Registered tools
----------------

  RUNTIME:
    initialize_runtime_context   warm up runtime; return bootstrap data
    query_runtime_state          live runtime metrics and status
    query_scene_context          structured Houdini scene snapshot

  KNOWLEDGE:
    query_capabilities           enumerate available capabilities
    query_workflow_templates     browse workflow templates
    query_examples               execution examples for an intent

  PLANNING:
    plan_scene                   NL intent → execution plan
    preview_execution            inspect ops + risk without executing
    validate_execution_plan      structural + constraint validation

  SCENE BUILDING:
    build_scene_from_assets      REQUIRED FIRST STEP for scene intents — real assets, never primitives

  EXECUTION:
    execute_workflow_transaction run via the transaction system
    review_execution             post-execution intent-match review

Public API:
    register_all_tools(transport=None) -> MCPToolRegistry
    get_mcp_tool_registry() -> MCPToolRegistry   (singleton)
    reset_mcp_tool_registry_for_tests()
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Scene-building intent detection
# ---------------------------------------------------------------------------

_SCENE_BUILDING_VERBS = frozenset({
    "build", "create", "make", "construct", "generate", "assemble",
    "design", "set up", "setup", "populate", "fill",
})

_SCENE_ENVIRONMENT_KEYWORDS = frozenset({
    "room", "scene", "environment", "interior", "exterior", "set",
    "hangar", "corridor", "hallway", "tavern", "saloon", "office",
    "dungeon", "castle", "building", "hall", "warehouse", "factory",
    "lab", "laboratory", "kitchen", "bedroom", "bathroom", "cellar",
    "western", "medieval", "sci-fi", "cyberpunk", "fantasy", "desert",
    "apartment", "house", "hotel", "bar", "restaurant", "cafe",
    "village", "town", "alley", "street", "courtyard", "arena",
})

_PRIMITIVE_NODE_TYPES = frozenset({
    "box", "tube", "sphere", "grid", "line", "circle", "torus",
    "platonic", "rubber_toy", "metaball",
})


def _is_scene_building_intent(intent: str) -> bool:
    """Return True if the intent is for building a scene/environment."""
    low   = intent.lower()
    words = set(low.split())
    has_verb = any(v in low for v in _SCENE_BUILDING_VERBS)
    has_env  = any(kw in low for kw in _SCENE_ENVIRONMENT_KEYWORDS)
    return has_verb and has_env


def _plan_is_primitive_only(operations: List[Dict[str, Any]]) -> bool:
    """Return True if the plan is mostly create_node calls with primitive types."""
    if not operations:
        return False
    prim_count = sum(
        1 for op in operations
        if str(op.get("node_type", op.get("params", {}).get("node_type", ""))).lower()
        in _PRIMITIVE_NODE_TYPES
    )
    return prim_count / max(len(operations), 1) >= 0.4

# ---------------------------------------------------------------------------
# ToolDefinition
# ---------------------------------------------------------------------------

@dataclass
class ToolDefinition:
    name:        str
    description: str
    inputSchema: Dict[str, Any]
    handler:     Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]
    category:    str = "general"


# ---------------------------------------------------------------------------
# MCPToolRegistry
# ---------------------------------------------------------------------------

class MCPToolRegistry:
    """In-process registry of MCP-exposed semantic tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._lock  = threading.Lock()

    def register_tool(self, defn: ToolDefinition) -> None:
        with self._lock:
            self._tools[defn.name] = defn

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        with self._lock:
            return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "name":        d.name,
                    "description": d.description,
                    "inputSchema": d.inputSchema,
                    "category":    d.category,
                }
                for d in self._tools.values()
            ]

    async def dispatch_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        tool = self.get_tool(name)
        if tool is None:
            return {"ok": False, "error": f"Unknown tool: {name!r}"}
        try:
            result = await tool.handler(arguments)
            if not isinstance(result, dict):
                result = {"result": result}
            return result
        except Exception as exc:
            return {"ok": False, "error": str(exc), "tool": name}

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_cat: Dict[str, int] = {}
            for d in self._tools.values():
                by_cat[d.category] = by_cat.get(d.category, 0) + 1
            return {
                "tool_count":   len(self._tools),
                "by_category":  by_cat,
                "tools":        sorted(self._tools.keys()),
            }


# ---------------------------------------------------------------------------
# Handlers — RUNTIME group
# ---------------------------------------------------------------------------

async def _handle_initialize_runtime_context(args: Dict[str, Any]) -> Dict[str, Any]:
    import os
    from src.runtime.runtime_bootstrap import initialize_runtime, get_bootstrap_data
    from src.utils.vibrante_config import apply_vibrante_config

    # Read the packages file and push its values into the live Houdini session
    # so the session always reflects what vibrante_node.json says, even when
    # Houdini loaded an old state at startup (packages are not hot-reloaded).
    from src.utils.vibrante_config import read_vibrante_config
    try:
        from src.utils.hou_bridge import get_bridge
        file_vals = read_vibrante_config()
        bridge = get_bridge()
        for key, value in file_vals.items():
            if value and not (value.startswith("<") and value.endswith(">")):
                bridge.run_code(
                    f"import os\nos.environ[{key!r}] = {value!r}"
                )
    except Exception:
        pass  # bridge not available — fall back to file-only path
    apply_vibrante_config(force=True)

    client_id   = str(args.get("client_id", ""))
    init_status = initialize_runtime()
    bootstrap   = get_bootstrap_data()

    # Include resolved asset paths so the agent never guesses or checks stale locations.
    asset_paths = {
        "megascans_library": os.environ.get("VIBRANTE_MEGASCANS_LIBRARY", "(not set)"),
        "asset_cache":       os.environ.get("VIBRANTE_ASSET_CACHE",       "(not set)"),
        "fab_library":       os.environ.get("VIBRANTE_FAB_LIBRARY",       "(not set)"),
        "project_staging":   os.environ.get("VIBRANTE_PROJECT_STAGING",   "(not set)"),
    }

    # Start the Fab Plugin socket receiver in the background so the user can
    # push assets from the Fab desktop app / Unreal Engine without restarting.
    fab_receiver_info: Dict[str, Any] = {}
    try:
        from src.runtime.assets.acquisition_online.fab_socket_receiver import (
            get_fab_socket_receiver,
        )
        receiver = get_fab_socket_receiver()
        if not receiver.is_running():
            receiver.start()
        fab_receiver_info = {
            "running": receiver.is_running(),
            "port":    receiver.port,
            "message": (
                f"Fab socket receiver listening on port {receiver.port}. "
                "Export assets from the Fab desktop app / Unreal Engine → "
                "they will be automatically picked up on the next build_scene_from_assets call."
            ) if receiver.is_running() else (
                f"Fab socket receiver could not start on port {receiver.port} "
                "(port may be in use). Manual download or local library scan still works."
            ),
        }
    except Exception as _fab_exc:
        fab_receiver_info = {"running": False, "error": str(_fab_exc)}

    return {
        "ok":         True,
        "status":     init_status,
        "bootstrap":  bootstrap,
        "asset_paths": asset_paths,
        "fab_socket_receiver": fab_receiver_info,
        "message": (
            "Vibrante Runtime initialized. "
            f"Megascans library: {asset_paths['megascans_library']}. "
            "Review runtime_rules and recommended_execution_flow before issuing commands."
        ),
    }


async def _handle_query_runtime_state(args: Dict[str, Any]) -> Dict[str, Any]:
    state: Dict[str, Any] = {"ok": True}
    try:
        from src.runtime.transaction_manager import get_transaction_manager
        viz = get_transaction_manager().get_graph_visualization_data()
        state["transaction_manager"] = viz
    except Exception as exc:
        state["transaction_manager_error"] = str(exc)
    try:
        from src.runtime.scene_cache import get_scene_cache
        state["scene_cache"] = get_scene_cache().stats()
    except Exception as exc:
        state["scene_cache_error"] = str(exc)
    try:
        from src.runtime.execution_scheduler import get_execution_scheduler
        sched = get_execution_scheduler()
        state["scheduler"] = sched.stats()
    except Exception as exc:
        state["scheduler_error"] = str(exc)
    try:
        from src.runtime.audit_store import get_audit_store
        state["audit_store"] = get_audit_store().stats()
    except Exception as exc:
        state["audit_store_error"] = str(exc)
    return state


async def _handle_query_scene_context(args: Dict[str, Any]) -> Dict[str, Any]:
    force_refresh = bool(args.get("force_refresh", False))
    try:
        from src.runtime import houdini_runtime
        context = await houdini_runtime.scene_context(force_refresh=force_refresh)
        return {"ok": True, "scene_context": context}
    except Exception as exc:
        return {
            "ok":           False,
            "error":        str(exc),
            "scene_context": None,
            "message": (
                "Houdini bridge not available. "
                "Ensure Houdini is running with the Vibrante-Node plugin loaded."
            ),
        }


# ---------------------------------------------------------------------------
# Handlers — KNOWLEDGE group
# ---------------------------------------------------------------------------

async def _handle_query_capabilities(args: Dict[str, Any]) -> Dict[str, Any]:
    cap_type: Optional[str] = args.get("cap_type") or None
    try:
        from src.runtime.capability_registry import get_capability_registry
        reg  = get_capability_registry()
        caps = reg.query_capabilities(cap_type=cap_type) if cap_type else reg.query_capabilities()
        return {"ok": True, "capabilities": caps, "count": len(caps)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def _handle_query_workflow_templates(args: Dict[str, Any]) -> Dict[str, Any]:
    tag: Optional[str] = args.get("tag") or None
    try:
        from src.runtime.workflow_templates import get_workflow_templates
        wt        = get_workflow_templates()
        templates = wt.list_templates(tag=tag) if tag else wt.list_templates()
        return {"ok": True, "templates": templates, "count": len(templates)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def _handle_query_examples(args: Dict[str, Any]) -> Dict[str, Any]:
    intent = str(args.get("intent", "")).strip()
    if not intent:
        return {"ok": False, "error": "intent is required"}
    results: Dict[str, Any] = {"ok": True, "intent": intent}

    # ── Scene-building / environment example ──────────────────────────────────
    # build_scene_from_assets handles the full intent-to-scene pipeline.
    # Return a concrete usage example so callers know the correct tool sequence.
    if _is_scene_building_intent(intent):
        t128 = _parse_intent_tier128(intent)
        results["scene_building_example"] = {
            "tool": "build_scene_from_assets",
            "description": (
                "Full intent-to-scene pipeline: intent → semantic keywords → "
                "local catalog search → Megascans import → structural routing → "
                "semantic layout → layout realization → Houdini transforms."
            ),
            "sample_call": {
                "intent":          intent,
                "top_k":           10,
                "parent":          "/obj",
                "environment":     t128.get("environment", "(auto-detected from intent)"),
                "room_half_width": 5.0,
            },
            "pipeline_stages": [
                "Phase 1:   Intent parsing (Tier 12.8) — environment, keywords, role",
                "Phase 1.5: Structural routing (Tier 10.3.5) — split structural vs furniture",
                "Phase 2:   SemanticLayout furniture only (Tier 9.8) — clusters, surfaces, walls",
                "Phase 3:   LayoutRealization (Tier 9.9) — world-space transforms",
                "Phase 4:   Collision resolution (Tier 9.4)",
                "Phase 5:   Scene constraint solving",
                "Phase 6:   Apply furniture transforms to Houdini",
                "Phase 6b:  Apply structural transforms (beam/door/column placement)",
            ],
            "expected_output_fields": [
                "ok", "asset_count", "environment", "source",
                "layout_pipeline_report.routing_ok",
                "layout_pipeline_report.structural_assets_routed",
                "layout_pipeline_report.furniture_assets_to_layout",
                "layout_pipeline_report.collision_count_after",
                "layout_pipeline_report.production_ready",
                "END_TO_END_LAYOUT_STATUS",
            ],
            "usage": (
                "Call build_scene_from_assets directly with the intent string. "
                "Do NOT use plan_scene + execute_workflow_transaction for scene building — "
                "those tools handle primitive geometry only."
            ),
        }
        return results

    # ── Semantic registry lookup ───────────────────────────────────────────────
    try:
        from src.runtime.semantic_registry import get_semantic_registry
        reg  = get_semantic_registry()
        plan = reg.resolve_to_execution_plan(intent, {"parent": "/obj"})
        if plan.get("ok"):
            results["semantic_operation"] = {
                "operation_id":      plan.get("operation_id"),
                "sample_operations": plan.get("operations", [])[:3],
                "usage": (
                    f"Use plan_scene with prompt containing '{intent}' "
                    "to generate a full plan automatically."
                ),
            }
    except Exception:
        pass

    # ── Workflow template lookup ───────────────────────────────────────────────
    try:
        from src.runtime.workflow_templates import get_workflow_templates
        wt = get_workflow_templates()
        for tmpl in wt.list_templates():
            tid  = tmpl.get("template_id", "")
            desc = tmpl.get("description", "")
            tags = " ".join(tmpl.get("tags", []))
            low  = intent.lower()
            if low in tid.lower() or low in desc.lower() or low in tags.lower():
                results["template_example"] = {
                    "template_id": tid,
                    "description": desc,
                    "variables":   tmpl.get("variables", {}),
                    "usage": (
                        "Use query_workflow_templates and then pass the resolved ops "
                        "to execute_workflow_transaction."
                    ),
                }
                break
    except Exception:
        pass

    if len(results) == 2:   # only ok + intent — nothing found
        results["ok"]    = False
        results["error"] = f"No examples found for intent: {intent!r}"
    return results


async def _handle_query_node_parameters(args: Dict[str, Any]) -> Dict[str, Any]:
    node_path = str(args.get("node_path", "")).strip()
    if not node_path:
        return {"ok": False, "error": "node_path is required"}
    try:
        from src.utils.hou_bridge import get_bridge
        bridge = get_bridge()
        parms  = bridge.get_parms(node_path)
        names  = sorted(parms.keys())
        return {
            "ok":          True,
            "node_path":   node_path,
            "parameters":  parms,
            "param_names": names,
            "count":       len(names),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Handlers — PLANNING group
# ---------------------------------------------------------------------------

def _parse_intent_tier128(prompt: str) -> Dict[str, Any]:
    """
    Run the Tier 12.8 semantic intent parser on a prompt.
    Returns a dict with environment, keywords, role, storytelling, lookdev, etc.
    Never raises — returns {} on any import or parse error.
    """
    try:
        from src.runtime.assets.vector_search.intent_parser import (
            get_intent_parser as _vec_get)
        _p = _vec_get().parse(prompt)
        return _p.to_dict() if hasattr(_p, "to_dict") else {}
    except Exception:
        return {}


async def _handle_plan_scene(args: Dict[str, Any]) -> Dict[str, Any]:
    prompt = str(args.get("prompt", "")).strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}

    # ── Always run the Tier 12.8 semantic intent parser first ────────────────
    # This gives structured environment / keywords / role even for scene-building
    # intents that will be redirected, and serves as a fallback for lighting /
    # structural prompts the legacy parser cannot handle.
    t128 = _parse_intent_tier128(prompt)

    # ── Intercept scene-building intents ─────────────────────────────────────
    # Scene / environment assembly must go through build_scene_from_assets
    # which imports real Megascans assets instead of primitive geometry.
    # Return ok=True with the parsed intent so callers can inspect it and
    # then call build_scene_from_assets directly.
    if _is_scene_building_intent(prompt):
        return {
            "ok":            True,
            "redirect":      "build_scene_from_assets",
            "parsed_intent": t128,
            "environment":   t128.get("environment", ""),
            "keywords":      t128.get("keywords", []),
            "role":          t128.get("role", ""),
            "storytelling":  t128.get("storytelling", ""),
            # Synthetic plan — allows review_execution to score this intent
            "plan": {
                "ok":              True,
                "intent":          prompt,
                "environment":     t128.get("environment", ""),
                "keywords":        t128.get("keywords", []),
                "operations":      [],
                "requires_approval": False,
                "notes":           "Scene-building intent — execute via build_scene_from_assets.",
            },
            "message": (
                f"Scene-building intent detected and parsed. "
                f"Call build_scene_from_assets(intent={prompt!r}, top_k=10, parent='/obj') "
                f"to import real Megascans assets and run the full layout pipeline."
            ),
            "action_required": (
                f"build_scene_from_assets(intent={prompt!r}, top_k=10, parent='/obj')"
            ),
        }
    # ─────────────────────────────────────────────────────────────────────────

    try:
        from src.runtime.intent_parser        import get_intent_parser
        from src.runtime.contextual_reasoning import get_contextual_reasoner
        from src.runtime.ai_planner           import get_ai_planner
        parsed = await get_intent_parser().parse(prompt)

        # If the legacy parser returns a null/empty intent (e.g. for lighting or
        # structural asset prompts it doesn't understand), enrich it with the
        # Tier 12.8 result so the planner has something meaningful to work with.
        if not parsed.get("intent") and t128:
            parsed = dict(parsed)
            parsed["intent"]      = prompt
            parsed["environment"] = t128.get("environment", parsed.get("environment", ""))
            parsed["keywords"]    = t128.get("keywords", parsed.get("keywords", []))
            parsed["role"]        = t128.get("role", "")
            parsed["storytelling"]= t128.get("storytelling", "")
            parsed["lookdev"]     = t128.get("lookdev", "")
            parsed["t128_parsed"] = t128

        analysis = get_contextual_reasoner().analyze(
            parsed.get("intent", prompt),
            parsed.get("parameters", {}),
        )
        plan = await get_ai_planner().plan(parsed, analysis)
        return {
            "ok":               plan.get("ok", False),
            "plan":             plan,
            "parsed_intent":    parsed,
            "context_analysis": analysis,
            "message": (
                "Plan generated. Review plan.operations and plan.requires_approval "
                "before calling execute_workflow_transaction."
            ),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def _handle_preview_execution(args: Dict[str, Any]) -> Dict[str, Any]:
    plan_json = str(args.get("plan_json", "")).strip()
    ops_json  = str(args.get("operations_json", "")).strip()
    operations: List[Dict[str, Any]] = []
    try:
        if plan_json:
            plan       = json.loads(plan_json)
            operations = plan.get("operations", [])
        elif ops_json:
            operations = json.loads(ops_json)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Invalid JSON: {exc}"}
    if not operations:
        return {"ok": False, "error": "No operations to preview (provide plan_json or operations_json)"}
    try:
        from src.runtime.validation_engine    import get_validation_engine
        from src.runtime.resource_estimator   import get_resource_estimator
        from src.runtime.workflow_optimizer   import get_workflow_optimizer
        from src.runtime.predictive_execution import get_predictive_engine
        from src.runtime.execution_explainer  import get_execution_explainer
        validation   = await get_validation_engine().validate_operations(operations)
        estimate     = get_resource_estimator().estimate_transaction(operations)
        optimizer    = get_workflow_optimizer().analyze_plan(operations)
        prediction   = get_predictive_engine().predict(operations)
        explanation  = get_execution_explainer().explain_validation(validation)
        safe = (
            validation.get("valid", False)
            and prediction.get("predicted_risk") in ("low", "medium")
        )
        return {
            "ok":              True,
            "validation":      validation,
            "resource_estimate": estimate,
            "optimization":    optimizer,
            "prediction":      prediction,
            "explanation":     explanation,
            "op_count":        len(operations),
            "safe_to_execute": safe,
            "message": (
                "Preview complete. Check safe_to_execute and validation.warnings "
                "before calling execute_workflow_transaction."
            ),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def _handle_validate_execution_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    ops_json = str(args.get("operations_json", "")).strip()
    if not ops_json:
        return {"ok": False, "error": "operations_json is required"}
    try:
        operations = json.loads(ops_json)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Invalid JSON: {exc}"}
    try:
        from src.runtime.validation_engine import get_validation_engine
        from src.runtime.plan_validator    import get_plan_validator
        validation   = await get_validation_engine().validate_operations(operations)
        plan_result  = await get_plan_validator().validate(
            {"operations": operations, "ok": validation.get("valid", False)}
        )
        return {
            "ok":              True,
            "validation":      validation,
            "plan_validation": plan_result,
            "valid":           validation.get("valid") and plan_result.get("valid"),
            "errors":          (validation.get("errors", []) + plan_result.get("errors", [])),
            "warnings":        (validation.get("warnings", []) + plan_result.get("warnings", [])),
            "risk_level":      plan_result.get("risk_level", validation.get("risk_level", "low")),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Handlers — EXECUTION group
# ---------------------------------------------------------------------------

async def _handle_execute_workflow_transaction(args: Dict[str, Any]) -> Dict[str, Any]:
    plan_json      = str(args.get("plan_json", "")).strip()
    intent         = str(args.get("intent", "")).strip()
    params_json    = str(args.get("parameters_json", "{}")).strip()
    dry_run        = bool(args.get("dry_run", False))
    approver       = str(args.get("approver", "")).strip()

    # --- Named-intent path via SemanticExecutor ---
    if intent and not plan_json:
        # ── Intercept: redirect scene-building intents to build_scene_from_assets
        if _is_scene_building_intent(intent):
            return await _handle_build_scene_from_assets({
                "intent": intent, "top_k": 10, "parent": "/obj",
                "quality": "medium", "spacing": 3.0, "my_assets_only": False,
                "allow_download": True,
            })
        # ─────────────────────────────────────────────────────────────────────
        try:
            parameters = json.loads(params_json) if params_json else {}
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"Invalid parameters_json: {exc}"}
        try:
            from src.runtime.semantic_execution import get_semantic_executor
            result = await get_semantic_executor().execute(
                intent, parameters,
                dry_run=dry_run, auto_commit=True, rollback_on_error=True,
            )
            return {
                "ok":               result.get("ok", False),
                "execution_result": result,
                "message": "Execution complete. Call review_execution to verify.",
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # --- Plan-dict path ---
    try:
        plan       = json.loads(plan_json) if plan_json else {}
        operations = plan.get("operations", [])
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Invalid plan_json: {exc}"}

    if not operations:
        return {"ok": False, "error": "No operations to execute (provide plan_json or intent)"}

    # ── Intercept: reject primitive-only scene plans ─────────────────────────
    plan_intent = str(plan.get("intent", intent or "")).strip()
    if _is_scene_building_intent(plan_intent) and _plan_is_primitive_only(operations):
        return await _handle_build_scene_from_assets({
            "intent": plan_intent, "top_k": 10, "parent": "/obj",
            "quality": "medium", "spacing": 3.0, "my_assets_only": False,
            "allow_download": True,
        })
    # ─────────────────────────────────────────────────────────────────────────

    if not plan.get("ok", True):
        return {
            "ok":          False,
            "error":       "Plan has ok=False — fix plan errors before executing",
            "plan_errors": plan.get("errors", []),
        }

    if plan.get("requires_approval") and not approver:
        return {
            "ok":               False,
            "status":           "pending_approval",
            "error":            "Plan requires approval. Provide an 'approver' name to authorize.",
            "requires_approval": True,
            "approval_reasons": plan.get("approval_reasons", []),
        }

    # Execute through the transaction system
    try:
        from src.runtime.transaction_manager import get_transaction_manager
        from src.runtime import houdini_runtime

        txn_name = plan.get("intent", intent or "mcp_execution")
        txn_id   = await get_transaction_manager().begin_transaction(
            txn_name, metadata={"via": "mcp", "approver": approver or None}
        )

        if dry_run:
            from src.runtime.validation_engine import get_validation_engine
            validation = await get_validation_engine().validate_operations(operations)
            await get_transaction_manager().mark_failed(txn_id, "dry_run — no execution")
            return {
                "ok":        True,
                "status":    "dry_run",
                "validation": validation,
                "op_count":  len(operations),
            }

        created_paths:     List[str] = []
        errors:            List[str] = []
        operations_executed: List[Dict[str, Any]] = []

        for op in operations:
            op_result = await houdini_runtime.execute_operation(op)
            operations_executed.append(op_result)
            await get_transaction_manager().record_operation(txn_id, op_result)
            if op_result.get("status") == "failed":
                errors.append(op_result.get("error", "unknown"))
                await get_transaction_manager().rollback_transaction(txn_id)
                return {
                    "ok":                 False,
                    "status":             "rolled_back",
                    "errors":             errors,
                    "created_paths":      created_paths,
                    "transaction_id":     txn_id,
                    "operations_executed": operations_executed,
                }
            path = (op_result.get("result") or {}).get("path")
            if path:
                created_paths.append(path)

        await get_transaction_manager().commit_transaction(txn_id)
        return {
            "ok":                 True,
            "status":             "committed",
            "transaction_id":     txn_id,
            "created_paths":      created_paths,
            "op_count":           len(operations),
            "operations_executed": operations_executed,
            "message":            "Execution committed. Call review_execution to verify the result.",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def _handle_check_vibrante_config(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Report the current Vibrante credential / path configuration and tell the
    user exactly which file to edit when something is missing.

    Priority order for reading credentials:
      1. Live Houdini session (bridge.run_code) — checked first, always
      2. vibrante_node.json file sources (packages dir → local.json → source copy)

    This tool should be called BEFORE any acquisition tool when the agent
    suspects credentials may be missing.
    """
    import os
    from pathlib import Path
    from src.utils.vibrante_config import (
        apply_vibrante_config,
        read_from_houdini_session,
        find_vibrante_node_json, read_vibrante_config, _houdini_pkg_dirs,
        _VIBRANTE_ENV_VARS,
    )

    # Step 1: read from live Houdini session first, then file fallback
    apply_vibrante_config(force=True)

    # Report whether Houdini session was reachable
    houdini_values = read_from_houdini_session()
    houdini_reachable = bool(houdini_values)

    # Locate the config file being used as fallback
    config_file = find_vibrante_node_json()

    # Discover Houdini packages paths
    houdini_pkg_paths: List[Path] = []
    _houdini_pkg_dirs(houdini_pkg_paths)
    installed_pkg = next((p for p in houdini_pkg_paths if p.exists()), None)
    canonical_pkg = houdini_pkg_paths[0] if houdini_pkg_paths else None

    # File values (for reporting what the file contains)
    file_values = read_vibrante_config(config_file) if config_file else {}

    # Build status after apply_vibrante_config has already run
    var_status: Dict[str, str] = {}
    for var in _VIBRANTE_ENV_VARS:
        if os.environ.get(var, "").strip():
            # Determine which source provided it
            if houdini_values.get(var, "").strip():
                var_status[var] = "set_from_houdini_session"
            else:
                var_status[var] = "set_in_env"
        elif file_values.get(var, "").strip() and not file_values[var].startswith("<"):
            var_status[var] = "set_in_file"
        else:
            var_status[var] = "missing"

    missing = [v for v, s in var_status.items() if s == "missing"]
    acquisition_vars = [
        "VIBRANTE_MEGASCANS_LIBRARY",
        "VIBRANTE_MEGASCANS_TOKEN",
        "VIBRANTE_ASSET_CACHE",
    ]
    missing_critical = [v for v in acquisition_vars if var_status.get(v) == "missing"]

    # Build the actionable edit instruction
    edit_target = installed_pkg or config_file or canonical_pkg
    if missing_critical:
        example_lines = "\n".join(
            f'  {{"{v}": "your_value_here"}}' for v in missing_critical
        )
        if houdini_reachable:
            how_to_fix = (
                "Houdini is running but these vars are not set in its environment. "
                f"Open this file in Houdini's packages directory:\n  {edit_target}\n\n"
                f"Add or fill in these entries in the 'env' array:\n{example_lines}\n\n"
                "Restart Houdini after editing so the package reloads. "
                "The Vibrante runtime will then read them from the live session automatically.\n\n"
                "IMPORTANT: Do NOT use $env: or SetEnvironmentVariable."
            )
        else:
            how_to_fix = (
                "Houdini session is not reachable. Editing the config file directly:\n\n"
                f"Open this file in your editor:\n  {edit_target}\n\n"
                f"Add or fill in these entries in the 'env' array:\n{example_lines}\n\n"
                "Save the file. The next acquisition call reads it automatically — "
                "no restart, no shell commands needed.\n\n"
                "IMPORTANT: Do NOT use $env: or SetEnvironmentVariable — "
                "edit vibrante_node.json directly."
            )
        if installed_pkg is None and canonical_pkg:
            how_to_fix += (
                f"\n\nNOTE: {canonical_pkg} does not exist yet. "
                "Copy plugins/houdini/vibrante_node.json there and fill in your values "
                f"(or edit the file currently in use: {config_file})."
            )
    else:
        src = "Houdini session" if houdini_reachable else "config file"
        how_to_fix = f"All acquisition credentials are configured (read from {src}). No action needed."

    # Build bridge status message separately so it's always present
    if houdini_reachable:
        bridge_status = "Connected (port 18811)."
    else:
        pkg_note = (
            f"Package already at: {installed_pkg}"
            if installed_pkg
            else (
                f"Package not yet installed -- copy "
                f"plugins/houdini/vibrante_node.json to "
                f"{canonical_pkg or '~/Documents/houdiniXX.Y/packages/vibrante_node.json'} "
                f"and restart Houdini first."
            )
        )
        bridge_status = (
            "NOT connected (port 18811 refused). "
            "In Houdini: open the Vibrante-Node menu -> Launch Vibrante. "
            "That starts the bridge server so credentials are read directly from the Houdini session. "
            f"{pkg_note}"
        )

    return {
        "ok":                       True,
        "houdini_session_reachable": houdini_reachable,
        "bridge_status":            bridge_status,
        "houdini_session_vars":     sorted(houdini_values.keys()),
        "config_file_used":         str(config_file) if config_file else None,
        "canonical_pkg_path":       str(canonical_pkg) if canonical_pkg else None,
        "installed_in_houdini_packages": installed_pkg is not None,
        "var_status":               var_status,
        "missing_critical":         missing_critical,
        "all_configured":           len(missing_critical) == 0,
        "how_to_fix":               how_to_fix,
    }


def _compute_structural_transform(
    role:            str,
    room_half_width: float,
    ceiling_y:       float,
    ground_ty:       float,
) -> tuple:
    """
    Returns (tx, ty, tz, ry) for a structural asset placed per its classified role.
    ground_ty  — half-height of the asset (makes bottom flush with y=0 when ty=ground_ty).
    ceiling_y  — estimated room ceiling height in metres.
    """
    rh = room_half_width
    if role in ("beam", "support_beam"):
        return 0.0, max(ceiling_y - ground_ty, 1.5), 0.0, 0.0
    if role == "column":
        return rh - 0.5, ceiling_y / 2.0, rh - 0.5, 0.0
    if role == "floor_piece":
        return 0.0, ground_ty, 0.0, 0.0
    if role == "ceiling_piece":
        return 0.0, ceiling_y - ground_ty, 0.0, 0.0
    if role in ("doorway", "door_frame"):
        return 0.0, ground_ty, -(rh - 0.05), 0.0
    if role in ("window", "window_frame"):
        return rh - 0.05, max(1.2, ground_ty), 0.0, 90.0
    if role == "archway":
        return 0.0, ground_ty, -(rh - 0.05), 0.0
    if role in ("wall", "wall_segment"):
        return 0.0, ground_ty, -(rh - 0.1), 0.0
    if role == "fireplace":
        return 0.0, ground_ty, rh - 0.3, 180.0
    if role in ("stair", "railing"):
        return -(rh - 1.0), ground_ty, rh - 1.0, 0.0
    # architectural_module / structural_unknown — south perimeter
    return 0.0, ground_ty, -(rh - 0.2), 0.0


async def _handle_build_scene_from_assets(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full intent-to-scene pipeline as an MCP tool.

    Step 1 — Parse the intent into keywords (+ environment detection).
    Step 2 — Search the local semantic catalog for matching Megascans assets.
    Step 3 — If catalog is empty, search the user's Megascans library via the
             official API (view=myscans), then download + extract + mirror to
             VIBRANTE_MEGASCANS_LIBRARY automatically.
    Step 4 — Import each asset into Houdini via the bridge (geo node + SOP).
    Step 5 — Build AssetMetrics for every imported asset (PHASE 1).
    Step 5.5 — Structural routing: split assets into structural/furniture (PHASE 1.5).
    Step 6 — Semantic layout via SemanticLayoutEngine (furniture only, PHASE 2).
    Step 7 — Layout realization with bbox_half injection (PHASE 3).
    Step 8 — Collision resolution using real geometry (PHASE 4).
    Step 9 — Scene constraint solving (PHASE 5).
    Step 10 — Apply final transforms to Houdini (PHASE 6).
    Step 10.5 — Apply structural placement transforms (PHASE 6b).
    Step 11 — Emit validation report (PHASE 7).

    NEVER creates box / tube / sphere / grid primitives to represent real-world
    objects. If no assets can be found or downloaded the tool returns ok=False
    with a clear advisory — it does NOT fall back to primitives.
    """
    intent          = str(args.get("intent", "")).strip()
    top_k           = int(args.get("top_k", 10))
    parent          = str(args.get("parent", "/obj")).strip() or "/obj"
    quality         = str(args.get("quality", "medium")).strip()
    spacing         = float(args.get("spacing", 3.0))
    my_assets_only  = bool(args.get("my_assets_only", False))
    allow_download  = bool(args.get("allow_download", True))
    force_online    = bool(args.get("force_online", False))
    environment     = str(args.get("environment", "")).strip()
    room_half_width = float(args.get("room_half_width", 5.0))

    if not intent:
        return {"ok": False, "error": "intent is required"}

    import os
    keywords: List[str] = []
    assets:   List[Dict[str, Any]] = []
    source    = ""

    # ── Step 1: keyword extraction + environment detection ──────────────────
    try:
        from src.runtime.assets.vector_search.intent_parser import get_intent_parser
        parsed   = get_intent_parser().parse(intent)
        keywords = list(parsed.keywords or [])
        if not environment:
            environment = str(parsed.environment or "").strip()
    except Exception:
        keywords = [w for w in intent.lower().split() if len(w) > 3]

    # ── Step 2: local catalog search ────────────────────────────────────────
    try:
        from src.runtime.assets.vector_search import get_retrieval_pipeline
        result = get_retrieval_pipeline().retrieve(intent, top_k=top_k)
        assets = [a for a in (result.assets or [])
                  if isinstance(a, dict) and a.get("asset_id")]
        if assets:
            source = "catalog"
    except Exception:
        pass

    # ── Step 2.5: direct assetsData.json scan (local Megascans library) ────────
    if not assets:
        try:
            import glob as _glob
            _ms_lib = os.environ.get("VIBRANTE_MEGASCANS_LIBRARY", "").strip()
            _ads_path = os.path.join(_ms_lib, "assetsData.json") if _ms_lib else ""
            if _ads_path and os.path.isfile(_ads_path):
                with open(_ads_path, "r", encoding="utf-8", errors="replace") as _f:
                    _catalog = json.load(_f)
                _query_words = set(
                    w.lower() for kw in (keywords or intent.lower().split())
                    for w in kw.lower().split() if len(w) > 2
                )
                _scored: list = []
                for _entry in (_catalog if isinstance(_catalog, list) else []):
                    _ss = str(_entry.get("searchStr", "")).lower()
                    _name = str(_entry.get("semanticTags", {}).get("name", "")).lower()
                    _tags = " ".join(str(t) for t in _entry.get("tags", [])).lower()
                    _cats = " ".join(str(c) for c in _entry.get("categories", [])).lower()
                    _haystack = f"{_ss} {_name} {_tags} {_cats}"
                    _score = sum(1 for w in _query_words if w in _haystack)
                    if _score > 0:
                        _aid = str(_entry.get("id") or _entry.get("asset") or "")
                        _jp  = _entry.get("jsonPath", [])
                        _folder = os.path.join(_ms_lib, *_jp[:-1]) if len(_jp) >= 2 else ""
                        _fbx_files = sorted(
                            _glob.glob(os.path.join(_folder, "*_LOD3.fbx"))
                            + _glob.glob(os.path.join(_folder, "*_lod3.fbx"))
                        ) if _folder else []
                        _fbx = _fbx_files[0] if _fbx_files else ""
                        if _aid and _fbx and os.path.isfile(_fbx):
                            _scored.append((_score, {
                                "asset_id":   _aid,
                                "name":       str(_entry.get("semanticTags", {}).get("name", _aid)),
                                "local_path": _fbx,
                                "provider":   "megascans",
                                "source":     "local_library",
                            }))
                _scored.sort(key=lambda x: x[0], reverse=True)
                assets = [a for _, a in _scored[:top_k]]
                if assets:
                    source = "local_library"
        except Exception:
            pass

    # ── Step 3a: Quixel Bridge (localhost:28241) — no auth needed ───────────
    # Run if: no local assets yet, or force_online, or local count < top_k and allow_download.
    _needs_online = not assets or force_online or (allow_download and len(assets) < top_k)
    if _needs_online:
        try:
            from src.runtime.assets.acquisition_online.quixel_bridge_client import (
                get_quixel_bridge_client)
            bridge_client = get_quixel_bridge_client()
            if bridge_client.is_bridge_running():
                query        = " ".join(keywords[:6]) if keywords else intent
                _existing_ids = {a.get("asset_id") for a in assets}
                records      = bridge_client.search_assets(query, limit=top_k)
                new_records  = [r for r in records
                                if (r.get("id") or r.get("asset_id"))
                                and r.get("asset_id") not in _existing_ids]
                if new_records:
                    assets = (assets + new_records)[: top_k]
                    source = source or "quixel_bridge"
        except Exception:
            pass

    # ── Step 3b: Fab public search API (no auth required) ────────────────────
    # After the Quixel → Fab migration (2024) the old megascans.se/v1 REST API
    # and accounts.quixel.se credential exchange were shut down.
    # The Fab public search (www.fab.com/i/listings/search) works WITHOUT auth.
    # Auth is now only needed for actual asset DOWNLOADS.
    _needs_online = not assets or force_online or (allow_download and len(assets) < top_k)
    if _needs_online:
        try:
            from src.runtime.assets.acquisition_online import get_megascans_search
            query         = " ".join(keywords[:8]) if keywords else intent
            searcher      = get_megascans_search()
            _existing_ids = {a.get("asset_id") for a in assets}
            records       = searcher.search_assets(query, limit=top_k)
            new_api = [r.to_dict() for r in records
                       if r.asset_id and r.asset_id not in _existing_ids]
            if new_api:
                assets = (assets + new_api)[: top_k]
                source = source or "fab_api"
        except Exception:
            pass   # Fab search failure is non-fatal — proceed with local assets

    if not assets:
        _lib_path = os.environ.get('VIBRANTE_MEGASCANS_LIBRARY', 'not set')
        _fab_receiver_port = 31337
        try:
            from src.runtime.assets.acquisition_online.fab_socket_receiver import _read_socket_export_port
            _fab_receiver_port = _read_socket_export_port()
        except Exception:
            pass
        config_status = await _handle_check_vibrante_config({})
        return {
            "ok":    False,
            "error": f"No assets found for environment '{environment or intent}'.",
            "configuration_required": True,
            "how_to_fix": (
                "No assets are in the local library. There are three ways to get assets:\n\n"
                "OPTION 1 — Fab socket push (recommended, works instantly):\n"
                "  1. Start the Vibrante MCP server (it listens on port "
                f"{_fab_receiver_port} for Fab push).\n"
                "  2. Open Unreal Engine (with the built-in Fab panel) or the Fab desktop app.\n"
                "  3. Go to My Library → find the asset → click Export / Send to DCC.\n"
                "  4. Choose format: 'houdini', 'fbx', or 'obj'.\n"
                "  5. Call build_scene_from_assets again — Vibrante will pick up the pushed asset.\n\n"
                "OPTION 2 — Manual download:\n"
                "  1. Log in to fab.com → My Library → download asset as FBX/OBJ.\n"
                f"  2. Copy the downloaded folder to: {_lib_path}\n"
                "  3. Call build_scene_from_assets again — local scanner picks it up.\n\n"
                "OPTION 3 — Fab browser token (for asset metadata / download URLs):\n"
                "  1. Open fab.com in browser while logged in.\n"
                "  2. Press F12 → Network tab → filter by XHR → navigate to any page.\n"
                "  3. Find a request to fab.com → copy the 'Authorization: Bearer …' value.\n"
                '  4. Set it in vibrante_node.json: {"VIBRANTE_MEGASCANS_TOKEN": "eyJ..."}\n\n'
                "NOTE: The old Quixel Bridge / megascans.se API was shut down in 2024 "
                "after the Fab migration. App-credential exchange no longer works."
            ),
            "sources_tried":  ["local_catalog", "fab_library_scan", "quixel_bridge", "fab_api"],
            "fab_receiver_port": _fab_receiver_port,
            "library_path":   _lib_path,
            "keywords":       keywords,
            "config_status":  config_status,
        }

    # ── Step 4: fetch (cache-first → API download) ──────────────────────────
    # Assets from local_library source already have a resolved local_path — skip fetcher.
    try:
        if source == "local_library" and all(a.get("local_path") for a in assets):
            from src.runtime.assets.acquisition_online.asset_fetcher import FetchResult
            fetch_results = [
                FetchResult(ok=True, asset_id=a["asset_id"], provider="megascans",
                            local_path=a["local_path"], source="local_library")
                for a in assets
            ]
        else:
            from src.runtime.assets.acquisition_online import get_asset_fetcher
            fetch_results = get_asset_fetcher().fetch_assets(assets, quality=quality)
    except Exception as exc:
        return {"ok": False, "error": f"Asset fetch failed: {exc}"}

    # ── Step 5: import into Houdini ─────────────────────────────────────────
    try:
        from src.utils.hou_bridge import get_bridge
        bridge = get_bridge()
    except Exception as exc:
        return {"ok": False, "error": f"Houdini bridge not available: {exc}"}

    def _sop_info(lp: str):
        ext = lp.rsplit(".", 1)[-1].lower()
        if ext in ("usd", "usda", "usdc", "usdz"):
            return "usdimport", "filepath"
        if ext == "abc":
            return "alembic", "fileName"
        return "file", "file"

    def _get_bbox(sop_path: str) -> Dict[str, Any]:
        """Return bounding box of a cooked SOP. Returns {} if not available."""
        try:
            r = bridge.run_code(
                "import hou\n"
                f"_n = hou.node({sop_path!r})\n"
                "_g = _n.geometry() if _n else None\n"
                "_bb = _g.boundingBox() if (_g and len(_g.points()) > 0) else None\n"
                "result = ({'size': list(_bb.sizevec()), 'center': list(_bb.center()), "
                "'min': list(_bb.minvec())} if _bb else None)"
            )
            return r.get("result") or {}
        except Exception:
            return {}

    def _import_scale(info: Dict[str, Any], bbox: Dict[str, Any]) -> float:
        """
        Return the correct uniform import scale (sx = sy = sz) for this asset.

        Megascans FBX are exported in centimeters → scale = 0.01 (preserves
        real-world dimensions without any size normalisation).

        This function NEVER normalises assets to a target height.  A chair that
        is 84 cm tall in real life must arrive as 0.84 m in Houdini.
        """
        try:
            from src.runtime.assets.real_world_scale import get_real_world_scale_resolver
            return get_real_world_scale_resolver().resolve_import_scale(info)
        except Exception:
            # Heuristic fallback: large Houdini-unit bbox → assume cm-space
            size = bbox.get("size") or []
            if size and len(size) >= 3 and max(size) > 10.0:
                return 0.01
            return 0.01  # default: Megascans cm-space

    def _ground_offset(bbox: Dict[str, Any], scale: float) -> float:
        """Return ty so the object bottom sits at y=0."""
        mn = bbox.get("min") or []
        if not mn or len(mn) < 3:
            return 0.0
        return round(-mn[1] * scale, 6)

    imported:      List[str]            = []
    failed:        List[str]            = []
    scene_assets:  List[Dict[str, Any]] = []
    node_path_map: Dict[str, str]       = {}   # asset_id → geo_path
    metrics_map:   Dict[str, Any]       = {}   # asset_id → AssetMetrics
    ty_map:        Dict[str, float]     = {}   # asset_id → ground_offset (raises bottom to y=0)
    cursor_x = 0.0   # running X cursor for temporary staging layout

    for i, (info, fr) in enumerate(zip(assets, fetch_results)):
        aid = str(info.get("asset_id", f"asset_{i}"))
        if not fr.ok or not fr.local_path or not os.path.exists(fr.local_path):
            failed.append(f"{aid}: {fr.error or 'not available'}")
            continue
        lp        = fr.local_path
        sop_t, pn = _sop_info(lp)
        safe      = "".join(c if c.isalnum() or c == "_" else "_" for c in aid)[:28] or f"asset_{i}"
        try:
            geo_r = bridge.create_node(parent, "geo", safe)
            geo_p = geo_r["path"]
            for child in bridge.children(geo_p):
                bridge.delete_node(child["path"])
            sop_r = bridge.create_node(geo_p, sop_t, "load")
            sop_p = sop_r["path"]
            bridge.set_parm(sop_p, pn, lp)
            bridge.set_display_flag(sop_p, True)
            bridge.set_render_flag(sop_p, True)
            bridge.cook_node(sop_p)

            # Measure imported geometry; preserve real-world dimensions (no normalisation)
            bbox_  = _get_bbox(sop_p)
            scale  = _import_scale(info, bbox_)
            ty     = _ground_offset(bbox_, scale)

            # Derive real-world world-space dimensions and store on the asset dict
            # so downstream systems (layout, collision) receive actual measurements.
            try:
                from src.runtime.assets.geometry.bounding_box_extractor import (
                    get_geometry_bbox_extractor)
                wbbox = get_geometry_bbox_extractor().from_houdini_bbox(bbox_, scale)
                info["width_m"]     = wbbox["width_m"]
                info["height_m"]    = wbbox["height_m"]
                info["depth_m"]     = wbbox["depth_m"]
                info["bbox_min"]    = wbbox["bbox_min"]
                info["bbox_max"]    = wbbox["bbox_max"]
                info["source_unit"] = "meters"
            except Exception:
                pass

            # ── PHASE 1: Build AssetMetrics from cooked geometry ─────────────
            try:
                from src.runtime.assets.geometry.asset_metrics import (
                    get_asset_metrics_builder)
                metrics = get_asset_metrics_builder().build(info)
                metrics_map[aid] = metrics
                # Propagate classification back into info for layout engine type inference
                if not info.get("placement_type") and metrics.placement_type:
                    info["placement_type"] = metrics.placement_type
                if not info.get("category") and metrics.category:
                    info["category"] = metrics.category
                info["scale_class"] = metrics.scale_class
                info["role"]        = metrics.role
            except Exception:
                pass

            size_x = (bbox_.get("size") or [spacing, 0, 0])[0] * scale

            # Temporary staging: linear placement along X (overridden by layout pipeline)
            bridge.set_parms(geo_p, {
                "tx": round(cursor_x + size_x / 2.0, 4),
                "ty": round(ty, 6),
                "tz": 0.0,
                "sx": scale, "sy": scale, "sz": scale,
            })
            cursor_x += size_x + spacing
            imported.append(geo_p)
            node_path_map[aid] = geo_p
            ty_map[aid]        = ty

            scene_asset = dict(info)
            scene_asset["asset_id"] = aid
            scene_assets.append(scene_asset)

        except Exception as exc:
            failed.append(f"{safe}: {exc}")

    if imported:
        try:
            bridge.layout_children(parent)
        except Exception:
            pass

    # ── Layout pipeline metrics ──────────────────────────────────────────────
    layout_ok             = False
    realize_ok            = False
    collision_before      = 0
    collision_after       = 0
    constraint_violations = 0
    transforms_applied    = 0
    assets_in_clusters    = 0
    assets_on_surfaces    = 0
    assets_on_walls       = 0
    pipeline_errors:  List[str] = []
    layout            = None
    final_score       = None
    routing_ok        = True
    structural_count  = 0
    furniture_count   = len(scene_assets)
    shell_ready         = True            # default: non-blocking if shell module unavailable
    shell_report:  Dict[str, Any] = {}
    shell_geometry_created = False
    shell_geo_nodes: Dict[str, str] = {}   # label → geo node path in Houdini
    shell_geo_prims: Dict[str, int] = {}   # label → primitive count after cook
    shell_geo_status = "SKIP"              # PASS | FAIL | SKIP

    # ── Phase 0: Environment Shell Construction (Tier 10.4) ──────────────────
    # Build the room shell (floor + walls + ceiling + anchors) before ANY asset
    # placement.  environment_ready = False → BLOCKING gate; furniture layout,
    # surface placement, and decoration are all skipped.
    _shell_env    = environment or "western_room"
    _shell_result = None
    _shell_bp:    Dict[str, Any] = {}
    try:
        from src.runtime.environment_shell import get_environment_shell_builder
        _shell_result = get_environment_shell_builder().build(_shell_env)
        _sh           = _shell_result.shell
        _shell_bp     = _shell_result.blueprint or {}
        shell_ready   = bool(_sh and _sh.environment_ready)
        shell_report  = {
            "environment_ready":   shell_ready,
            "floor_exists":        _sh.floor_exists        if _sh else False,
            "wall_count":          _sh.wall_count          if _sh else 0,
            "ceiling_exists":      _sh.ceiling_exists      if _sh else False,
            "enclosure_valid":     _sh.enclosure_valid     if _sh else False,
            "door_anchor_count":   _sh.door_anchor_count   if _sh else 0,
            "beam_anchor_count":   _sh.beam_anchor_count   if _sh else 0,
            "gate_status":         _shell_result.gate.gate_status
                                   if _shell_result.gate else "",
            "shell_grade":         _shell_result.review.grade
                                   if _shell_result.review else "F",
            "shell_score":         _shell_result.review.overall_score
                                   if _shell_result.review else 0.0,
            "phase_statuses":      _sh.phase_statuses if _sh else {},
        }
        if not shell_ready:
            _gate_findings = (
                _shell_result.gate.findings if _shell_result.gate else []
            )
            pipeline_errors.append(
                "ENVIRONMENT_NOT_READY — shell gate blocked. "
                f"floor={shell_report['floor_exists']}, "
                f"walls={shell_report['wall_count']}, "
                f"ceiling={shell_report['ceiling_exists']}. "
                + ("; ".join(_gate_findings) if _gate_findings else "")
            )
    except Exception as exc:
        pipeline_errors.append(f"EnvironmentShellBuilder (non-blocking): {exc}")
        # shell_ready stays True — graceful fallback so a missing module does
        # not break existing scenes that predate Tier 10.4.

    # ── Phase 0.75: Shell Geometry Realization (Tier 10.4.2) ─────────────────
    # Create actual Houdini geo nodes (box SOPs) for the validated shell.
    # Nodes: sh_floor / sh_wall_n / sh_wall_s / sh_wall_e / sh_wall_w / sh_ceiling
    # Outdoor environments receive a ground plane only (no walls / ceiling).
    # Furniture layout (Phase 1.5+) is blocked until shell_geo_status == "PASS".
    if shell_ready:
        try:
            _w          = float(_shell_bp.get("room_width",  10.0))
            _l          = float(_shell_bp.get("room_length", 12.0))
            _h          = float(_shell_bp.get("room_height",  4.0))
            _is_outdoor = bool(_shell_bp.get("is_outdoor", False))
            _wall_thick  = 0.3
            _floor_thick = 0.1
            _ceil_thick  = 0.15
            _pfx         = "sh"  # keeps node names short

            def _mk_box(label: str, sx: float, sy: float, sz: float,
                        geo_tx: float = 0.0, geo_ty: float = 0.0,
                        geo_tz: float = 0.0) -> str:
                """Create parent/label geo node with a single box SOP inside."""
                _gr = bridge.create_node(parent, "geo", label)
                _gp = _gr["path"]
                for _ch in bridge.children(_gp):
                    bridge.delete_node(_ch["path"])
                _sr = bridge.create_node(_gp, "box", "shape")
                _sp = _sr["path"]
                bridge.set_parms(_sp, {
                    "sizex": round(sx, 4),
                    "sizey": round(sy, 4),
                    "sizez": round(sz, 4),
                })
                bridge.set_display_flag(_sp, True)
                bridge.set_render_flag(_sp, True)
                bridge.set_parms(_gp, {
                    "tx": round(geo_tx, 4),
                    "ty": round(geo_ty, 4),
                    "tz": round(geo_tz, 4),
                })
                bridge.cook_node(_sp)
                return _gp

            def _prim_count(geo_path: str) -> int:
                try:
                    _ch_list = bridge.children(geo_path)
                    if not _ch_list:
                        return 0
                    _sp_path = _ch_list[0]["path"]
                    _rv = bridge.run_code(
                        f"_n = hou.node({_sp_path!r})\n"
                        "_g = _n.geometry() if _n else None\n"
                        "result = len(_g.prims()) if _g else 0"
                    )
                    return int(_rv.get("result") or 0)
                except Exception:
                    return 0

            # Phase 0.75a — Floor (always present)
            _fg = _mk_box(f"{_pfx}_floor",
                          _w, _floor_thick, _l,
                          0.0, -_floor_thick / 2.0, 0.0)
            shell_geo_nodes["floor"] = _fg
            shell_geo_prims["floor"] = _prim_count(_fg)

            if not _is_outdoor:
                # Phase 0.75b — Perimeter walls
                _wn = _mk_box(f"{_pfx}_wall_n",
                              _w, _h, _wall_thick,
                              0.0, _h / 2.0, -(_l / 2.0))
                shell_geo_nodes["wall_north"] = _wn
                shell_geo_prims["wall_north"] = _prim_count(_wn)

                _ws = _mk_box(f"{_pfx}_wall_s",
                              _w, _h, _wall_thick,
                              0.0, _h / 2.0, _l / 2.0)
                shell_geo_nodes["wall_south"] = _ws
                shell_geo_prims["wall_south"] = _prim_count(_ws)

                _we = _mk_box(f"{_pfx}_wall_e",
                              _wall_thick, _h, _l,
                              _w / 2.0, _h / 2.0, 0.0)
                shell_geo_nodes["wall_east"] = _we
                shell_geo_prims["wall_east"] = _prim_count(_we)

                _ww = _mk_box(f"{_pfx}_wall_w",
                              _wall_thick, _h, _l,
                              -(_w / 2.0), _h / 2.0, 0.0)
                shell_geo_nodes["wall_west"] = _ww
                shell_geo_prims["wall_west"] = _prim_count(_ww)

                # Phase 0.75c — Ceiling
                _cg = _mk_box(f"{_pfx}_ceiling",
                              _w, _ceil_thick, _l,
                              0.0, _h + _ceil_thick / 2.0, 0.0)
                shell_geo_nodes["ceiling"] = _cg
                shell_geo_prims["ceiling"] = _prim_count(_cg)

            shell_geometry_created = bool(shell_geo_nodes)

            # Evaluate geometry status
            _floor_ok   = shell_geo_prims.get("floor", 0) > 0
            _walls_ok   = _is_outdoor or (
                shell_geo_prims.get("wall_north", 0) > 0
                and shell_geo_prims.get("wall_south", 0) > 0
                and shell_geo_prims.get("wall_east",  0) > 0
                and shell_geo_prims.get("wall_west",  0) > 0
            )
            _ceiling_ok = _is_outdoor or shell_geo_prims.get("ceiling", 0) > 0
            shell_geo_status = "PASS" if (_floor_ok and _walls_ok and _ceiling_ok) else "FAIL"

            # Write back into shell_report so callers see the full picture
            shell_report["geometry_nodes"] = dict(shell_geo_nodes)
            shell_report["geometry_prims"] = dict(shell_geo_prims)
            shell_report["geometry_count"] = len(shell_geo_nodes)
            shell_report["anchor_count"]   = sum(
                getattr(_shell_result.shell, k, 0)
                for k in ("door_anchor_count", "window_anchor_count",
                          "beam_anchor_count", "column_anchor_count")
            ) if (_shell_result and _shell_result.shell) else 0

            if shell_geo_status == "FAIL":
                pipeline_errors.append(
                    "SHELL_GEOMETRY_STATUS=FAIL — "
                    f"floor={shell_geo_prims.get('floor', 0)} prims, "
                    f"wall_north={shell_geo_prims.get('wall_north', 0)} prims, "
                    f"ceiling={shell_geo_prims.get('ceiling', 0)} prims"
                )
        except Exception as exc:
            shell_geo_status = "FAIL"
            pipeline_errors.append(f"ShellGeometryRealization: {exc}")

    if scene_assets and shell_ready:
        # ── PHASE 1.5: Structural routing (Tier 10.3.5) ──────────────────────
        # Classify every asset and split into structural (beam/wall/door/column/…)
        # and furniture (chair/table/prop/…).  Only furniture enters SemanticLayoutEngine.
        # Structural assets are placed separately in PHASE 6b.
        furniture_assets:  List[Dict[str, Any]] = list(scene_assets)
        structural_assets: List[Dict[str, Any]] = []
        try:
            from src.runtime.environment_realization.structural_routing_engine import (
                get_structural_routing_engine)
            _routing         = get_structural_routing_engine().route(scene_assets, environment)
            furniture_assets = _routing.furniture_assets
            structural_assets= _routing.structural_assets
            routing_ok       = _routing.production_ready
            structural_count = len(structural_assets)
            furniture_count  = len(furniture_assets)
        except Exception as exc:
            pipeline_errors.append(f"StructuralRoutingEngine: {exc}")

        # ── PHASE 2: Semantic Layout (furniture/props only) ──────────────────
        try:
            from src.runtime.layout.semantic_layout_engine import get_semantic_layout_engine
            layout    = get_semantic_layout_engine().build_layout(furniture_assets, environment)
            layout_ok = layout.ok
            if layout_ok:
                assets_in_clusters = sum(
                    len(c.get("members", [])) for c in (layout.clusters or []))
                assets_on_surfaces = len(layout.surface_placements or [])
                assets_on_walls    = len(layout.wall_attachments or [])
        except Exception as exc:
            pipeline_errors.append(f"SemanticLayoutEngine: {exc}")
            layout    = None
            layout_ok = False

        if layout_ok and layout is not None:
            # ── PHASE 3: Layout Realization ───────────────────────────────────
            try:
                from src.runtime.layout_realization.layout_realization_engine import (
                    get_layout_realization_engine)
                type_hints: Dict[str, str] = {
                    aid_: m.placement_type
                    for aid_, m in metrics_map.items()
                    if m.placement_type
                }
                realized   = get_layout_realization_engine().realize(
                    layout.to_dict(),
                    room_half_width=room_half_width,
                    type_hints=type_hints,
                )
                realize_ok = realized.ok

                if realize_ok and realized.transforms:
                    # Inject real bbox half-extents from cooked geometry into every
                    # transform so that Phase 4 collision uses actual asset footprints.
                    for xf in realized.transforms:
                        m = metrics_map.get(xf.asset_id)
                        if m:
                            xf.bbox_half_x = m.width_m  / 2.0
                            xf.bbox_half_y = m.height_m / 2.0
                            xf.bbox_half_z = m.depth_m  / 2.0

                    # ── PHASE 4: Collision resolution with real geometry ───────
                    from src.runtime.layout_realization.collision_solver import (
                        get_collision_solver)
                    col_result       = get_collision_solver().solve(
                        realized.transforms, room_half_width, type_hints)
                    collision_before = col_result.collisions_found
                    collision_after  = col_result.collisions_remaining

                    # ── PHASE 5: Scene constraint solver ──────────────────────
                    from src.runtime.layout_realization.scene_constraint_solver import (
                        get_scene_constraint_solver)
                    hero_id = ""
                    for ap in (layout.anchor_placements or []):
                        if isinstance(ap, dict) and ap.get("is_hero"):
                            hero_id = str(ap.get("anchor_id", ""))
                            break
                    con_result            = get_scene_constraint_solver().solve_constraints(
                        col_result.transforms, room_half_width, type_hints, hero_id)
                    constraint_violations = con_result.violations_remaining
                    final_transforms      = con_result.transforms

                    # ── PHASE 6: Apply final transforms to Houdini ────────────
                    # ground_ty raises the asset bottom to y=0; xf.ty is the
                    # layout vertical offset (0.0 = floor, 0.75 = table surface, etc.)
                    for xf in final_transforms:
                        geo_p = node_path_map.get(xf.asset_id)
                        if not geo_p:
                            continue
                        ground_ty = ty_map.get(xf.asset_id, 0.0)
                        try:
                            bridge.set_parms(geo_p, {
                                "tx": round(xf.tx,               4),
                                "ty": round(ground_ty + xf.ty,   4),
                                "tz": round(xf.tz,               4),
                                "ry": round(xf.ry,               4),
                            })
                            transforms_applied += 1
                        except Exception as exc:
                            pipeline_errors.append(f"set_parms {geo_p}: {exc}")

                    final_score = (
                        collision_after == 0
                        and constraint_violations == 0
                        and transforms_applied > 0
                    )

            except Exception as exc:
                pipeline_errors.append(f"LayoutRealizationEngine: {exc}")

        # ── PHASE 6b: Structural asset placement ─────────────────────────────
        # Place beams, columns, doorways, walls, etc. per their structural role.
        # These assets bypassed SemanticLayoutEngine intentionally; they are
        # positioned relative to the room shell using role-derived offsets.
        if structural_assets:
            _ceiling_y = max(3.0, room_half_width * 0.65)
            for sa in structural_assets:
                _aid  = sa.get("asset_id", "")
                _gp   = node_path_map.get(_aid)
                if not _gp:
                    continue
                _role     = sa.get("_structural_role", "structural_unknown")
                _ground   = ty_map.get(_aid, 0.0)
                _tx, _ty, _tz, _ry = _compute_structural_transform(
                    _role, room_half_width, _ceiling_y, _ground)
                try:
                    bridge.set_parms(_gp, {
                        "tx": round(_tx, 4),
                        "ty": round(_ty, 4),
                        "tz": round(_tz, 4),
                        "ry": round(_ry, 4),
                    })
                    transforms_applied += 1
                except Exception as exc:
                    pipeline_errors.append(f"structural set_parms {_gp}: {exc}")

    # ── PHASE 7: Validation Report ───────────────────────────────────────────
    pipeline_pass = (
        shell_ready
        and routing_ok
        and layout_ok
        and realize_ok
        and collision_after == 0
        and constraint_violations == 0
        and transforms_applied > 0
    )

    layout_pipeline_report = {
        "imported_assets":              len(imported),
        "assets_with_metrics":          len(metrics_map),
        "structural_assets_routed":     structural_count,
        "furniture_assets_to_layout":   furniture_count,
        "routing_ok":                   routing_ok,
        "assets_in_clusters":           assets_in_clusters,
        "assets_on_surfaces":           assets_on_surfaces,
        "assets_attached_to_walls":     assets_on_walls,
        "assets_resolved":              transforms_applied,
        "collision_count_before":       collision_before,
        "collision_count_after":        collision_after,
        "constraint_violations":        constraint_violations,
        "final_score":                  final_score,
        "production_ready":             pipeline_pass,
        # Shell fields (Tier 10.4 / 10.4.2)
        "shell_ready":                  shell_ready,
        "shell_geo_status":             shell_geo_status,
        "shell_geometry_created":       shell_geometry_created,
        "shell_geo_nodes":              dict(shell_geo_nodes),
        "shell_geo_prims":              dict(shell_geo_prims),
        "shell_geometry_count":         len(shell_geo_nodes),
        "shell_report":                 shell_report,
    }

    ok = len(imported) > 0
    return {
        "ok":                        ok,
        "imported_paths":            imported,
        "asset_count":               len(imported),
        "failed_count":              len(failed),
        "failed":                    failed,
        "keywords":                  keywords,
        "source":                    source,
        "environment":               environment,
        "layout_pipeline_report":    layout_pipeline_report,
        "END_TO_END_LAYOUT_STATUS":  "PASS" if pipeline_pass else "FAIL",
        "SHELL_RUNTIME_STATUS":      "PASS" if shell_ready else "FAIL",
        "SHELL_GEOMETRY_STATUS":     shell_geo_status,
        "pipeline_errors":           pipeline_errors,
        "message": (
            f"Imported {len(imported)} assets into {parent} from {source}. "
            + (f"{len(failed)} failed: {failed[:3]}. " if failed else "")
            + (f"Shell: {'PASS' if shell_ready else 'FAIL (BLOCKING)'} "
               f"Geo: {shell_geo_status} ({len(shell_geo_nodes)} nodes). "
               if shell_report else "")
            + (f"Layout: {'PASS' if pipeline_pass else 'FAIL'} "
               f"({transforms_applied}/{len(imported)} transforms, "
               f"{collision_after} collisions, {constraint_violations} violations). "
               if scene_assets else "")
            + "Next step: add lighting and camera."
        ) if ok else (
            f"No assets imported. Failures: {failed[:5]}"
        ),
    }


async def _handle_review_execution(args: Dict[str, Any]) -> Dict[str, Any]:
    exec_json = str(args.get("execution_result_json", "")).strip()
    plan_json = str(args.get("plan_json", "")).strip()
    if not exec_json:
        return {"ok": False, "error": "execution_result_json is required"}
    try:
        execution_result = json.loads(exec_json)
        plan             = json.loads(plan_json) if plan_json else {}
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Invalid JSON: {exc}"}

    # ── build_scene_from_assets result — metrics-based review ─────────────────
    # That tool bypasses plan_scene and the operation-diff reviewer entirely.
    # Compute a direct score from pipeline report metrics instead.
    if "END_TO_END_LAYOUT_STATUS" in execution_result:
        rpt     = execution_result.get("layout_pipeline_report", {})
        score   = 0.0
        if execution_result.get("ok"):                        score += 0.20
        if execution_result.get("asset_count", 0) > 0:        score += 0.20
        if rpt.get("routing_ok"):                             score += 0.10
        if rpt.get("shell_ready", True):                      score += 0.05
        if rpt.get("shell_geo_status", "SKIP") == "PASS":     score += 0.05
        if rpt.get("collision_count_after", 1) == 0:          score += 0.20
        if rpt.get("constraint_violations", 1) == 0:          score += 0.10
        if rpt.get("production_ready"):                       score += 0.10
        # Master gate: all three PASS flags → ≥ 0.75
        if (execution_result.get("END_TO_END_LAYOUT_STATUS") == "PASS"
                and execution_result.get("SHELL_RUNTIME_STATUS",  "PASS") == "PASS"
                and execution_result.get("SHELL_GEOMETRY_STATUS", "PASS") == "PASS"):
            score = max(score, 0.75)
        score   = min(round(score, 3), 1.0)
        outcome = (
            "success"         if score >= 0.70 else
            "partial_success" if score >= 0.40 else
            "failure"
        )
        review = {
            "intent":             execution_result.get("intent", execution_result.get("environment", "")),
            "outcome":            outcome,
            "intent_match_score": score,
            "findings":           list(execution_result.get("pipeline_errors", [])),
            "asset_count":        execution_result.get("asset_count", 0),
            "routing_ok":         rpt.get("routing_ok", False),
            "structural_routed":  rpt.get("structural_assets_routed", 0),
            "furniture_to_layout":rpt.get("furniture_assets_to_layout", 0),
            "collision_count_after": rpt.get("collision_count_after", 0),
            "constraint_violations": rpt.get("constraint_violations", 0),
            "production_ready":   rpt.get("production_ready", False),
        }
        return {
            "ok":                True,
            "review":            review,
            "explanation": {
                "summary": (
                    f"Scene build review — {outcome}. "
                    f"Score: {score:.0%}. "
                    f"{execution_result.get('asset_count', 0)} assets placed, "
                    f"{rpt.get('collision_count_after', 0)} collisions remaining."
                ),
                "metrics": rpt,
            },
            "outcome":            outcome,
            "intent_match_score": score,
        }

    try:
        from src.runtime.execution_review   import get_execution_reviewer
        from src.runtime.execution_explainer import get_execution_explainer
        review      = get_execution_reviewer().review(plan, execution_result)
        explanation = get_execution_explainer().explain_review(review)
        return {
            "ok":                True,
            "review":            review,
            "explanation":       explanation,
            "outcome":           review.get("outcome"),
            "intent_match_score": review.get("intent_match_score"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_all_tools(transport=None) -> "MCPToolRegistry":
    """Register all 12 semantic orchestration tools.

    If `transport` is supplied (an MCPTransport instance) the tools are also
    forwarded to it via transport.register_tool(). This allows callers to do
    the one-liner:

        register_all_tools(transport)

    without having to manage the registry separately.
    """
    registry = get_mcp_tool_registry()

    _tools: List[ToolDefinition] = [
        # ── RUNTIME ────────────────────────────────────────────────────────
        ToolDefinition(
            name="initialize_runtime_context",
            description=(
                "Initialize the Vibrante Runtime context. "
                "Call this first before any other commands. "
                "Returns runtime identity, capabilities, templates, and execution rules."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "client_id": {
                        "type":        "string",
                        "description": "Optional identifier for this LLM client session.",
                    },
                },
            },
            handler=_handle_initialize_runtime_context,
            category="runtime",
        ),
        ToolDefinition(
            name="query_runtime_state",
            description=(
                "Query live Vibrante Runtime state: transaction manager, "
                "scene cache, execution scheduler, and audit store metrics."
            ),
            inputSchema={"type": "object", "properties": {}},
            handler=_handle_query_runtime_state,
            category="runtime",
        ),
        ToolDefinition(
            name="query_scene_context",
            description=(
                "Get a structured snapshot of the current Houdini scene: "
                "hip file, frame range, node networks, selection, and loaded HDAs. "
                "Requires a live Houdini + Vibrante-Node bridge."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "force_refresh": {
                        "type":        "boolean",
                        "description": "Bypass the 5-second scene cache and re-read from Houdini.",
                        "default":     False,
                    },
                },
            },
            handler=_handle_query_scene_context,
            category="runtime",
        ),
        # ── KNOWLEDGE ──────────────────────────────────────────────────────
        ToolDefinition(
            name="query_capabilities",
            description=(
                "Enumerate what the Vibrante Runtime can do: Houdini ops, "
                "renderers, MCP servers, semantic operations, etc."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "cap_type": {
                        "type":        "string",
                        "description": (
                            "Filter by capability type "
                            "(houdini_op, renderer, mcp_server, semantic_operation, …). "
                            "Omit to return all."
                        ),
                    },
                },
            },
            handler=_handle_query_capabilities,
            category="knowledge",
        ),
        ToolDefinition(
            name="query_workflow_templates",
            description=(
                "Browse available workflow templates (pyro_source, karma_render, "
                "usd_export, asset_publish, etc.). "
                "Templates resolve to concrete op lists safe for execute_workflow_transaction."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tag": {
                        "type":        "string",
                        "description": "Filter templates by tag (e.g. 'vfx', 'render').",
                    },
                },
            },
            handler=_handle_query_workflow_templates,
            category="knowledge",
        ),
        ToolDefinition(
            name="query_examples",
            description=(
                "Get execution examples and usage guidance for a given intent "
                "or semantic operation name."
            ),
            inputSchema={
                "type":     "object",
                "required": ["intent"],
                "properties": {
                    "intent": {
                        "type":        "string",
                        "description": (
                            "Semantic operation name or natural-language description "
                            "(e.g. 'build_pyro_source', 'karma render', 'cache geometry')."
                        ),
                    },
                },
            },
            handler=_handle_query_examples,
            category="knowledge",
        ),
        ToolDefinition(
            name="query_node_parameters",
            description=(
                "List all parameter names and current values for a Houdini node. "
                "Use this to discover the correct parameter name before calling "
                "execute_workflow_transaction with set_parms ops. "
                "Requires a live Houdini + Vibrante-Node bridge."
            ),
            inputSchema={
                "type":     "object",
                "required": ["node_path"],
                "properties": {
                    "node_path": {
                        "type":        "string",
                        "description": (
                            "Full Houdini path of the node to inspect "
                            "(e.g. '/obj/pyro_sim/pyro_dopnet/source_volume1')."
                        ),
                    },
                },
            },
            handler=_handle_query_node_parameters,
            category="knowledge",
        ),
        # ── PLANNING ───────────────────────────────────────────────────────
        ToolDefinition(
            name="plan_scene",
            description=(
                "Parse a natural-language prompt into a structured execution plan "
                "via the AI planning pipeline (intent parser → context analysis → AI planner). "
                "Returns the plan dict with operations, risk, and approval requirements. "
                "Does NOT execute anything."
            ),
            inputSchema={
                "type":     "object",
                "required": ["prompt"],
                "properties": {
                    "prompt": {
                        "type":        "string",
                        "description": "Natural-language description of the scene or workflow to build.",
                    },
                },
            },
            handler=_handle_plan_scene,
            category="planning",
        ),
        ToolDefinition(
            name="preview_execution",
            description=(
                "Inspect a set of operations without executing them. "
                "Returns validation results, resource estimates, risk prediction, "
                "and optimization tips. Always call this before execute_workflow_transaction."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "plan_json": {
                        "type":        "string",
                        "description": "JSON-serialised plan dict returned by plan_scene.",
                    },
                    "operations_json": {
                        "type":        "string",
                        "description": "JSON-serialised list of operation dicts (alternative to plan_json).",
                    },
                },
            },
            handler=_handle_preview_execution,
            category="planning",
        ),
        ToolDefinition(
            name="validate_execution_plan",
            description=(
                "Run structural + constraint validation on an operation list. "
                "Returns errors, warnings, and risk level without executing."
            ),
            inputSchema={
                "type":     "object",
                "required": ["operations_json"],
                "properties": {
                    "operations_json": {
                        "type":        "string",
                        "description": "JSON-serialised list of operation dicts.",
                    },
                },
            },
            handler=_handle_validate_execution_plan,
            category="planning",
        ),
        # ── EXECUTION ──────────────────────────────────────────────────────
        ToolDefinition(
            name="execute_workflow_transaction",
            description=(
                "Execute a validated plan via the Vibrante transaction system. "
                "Provide either plan_json (from plan_scene) or intent + parameters_json. "
                "High-risk plans require an approver name. "
                "Use dry_run=true to validate without committing."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "plan_json": {
                        "type":        "string",
                        "description": "JSON-serialised plan dict from plan_scene.",
                    },
                    "intent": {
                        "type":        "string",
                        "description": "Named semantic operation id (alternative to plan_json).",
                    },
                    "parameters_json": {
                        "type":        "string",
                        "description": "JSON object of parameters for the semantic operation.",
                        "default":     "{}",
                    },
                    "dry_run": {
                        "type":        "boolean",
                        "description": "Validate only — do not commit to Houdini.",
                        "default":     False,
                    },
                    "approver": {
                        "type":        "string",
                        "description": "Approver name required for high-risk plans.",
                    },
                },
            },
            handler=_handle_execute_workflow_transaction,
            category="execution",
        ),
        # ── CONFIGURATION CHECK ────────────────────────────────────────────
        ToolDefinition(
            name="check_vibrante_config",
            description=(
                "Check the current Vibrante credential and path configuration. "
                "Returns which env vars are set, which are missing, the exact "
                "filesystem path of the config file to edit, and a ready-to-use "
                "how_to_fix instruction. "
                "Call this BEFORE any acquisition or scene-build tool if credentials "
                "may be missing — relay how_to_fix verbatim to the user."
            ),
            inputSchema={"type": "object", "properties": {}},
            handler=_handle_check_vibrante_config,
            category="runtime",
        ),
        # ── SCENE BUILDING ─────────────────────────────────────────────────
        ToolDefinition(
            name="build_scene_from_assets",
            description=(
                "REQUIRED FIRST STEP for any scene-building intent "
                "(e.g. 'western old room', 'sci-fi corridor', 'medieval tavern'). "
                "Full pipeline: intent → keyword extraction → local catalog search "
                "→ Megascans API download if catalog empty → Houdini import. "
                "NEVER creates box/tube/sphere/grid primitives. "
                "Works for ANY environment or style. "
                "Call this BEFORE adding lights or camera."
            ),
            inputSchema={
                "type":     "object",
                "required": ["intent"],
                "properties": {
                    "intent": {
                        "type":        "string",
                        "description": (
                            "Natural-language description of the scene to build. "
                            "Examples: 'western old room with barrels and saloon furniture', "
                            "'abandoned factory with rusty machinery', 'desert village at dusk'."
                        ),
                    },
                    "top_k": {
                        "type":        "integer",
                        "description": "Max number of assets to retrieve and import.",
                        "default":     10,
                    },
                    "parent": {
                        "type":        "string",
                        "description": "Houdini parent network path (default: /obj).",
                        "default":     "/obj",
                    },
                    "quality": {
                        "type":        "string",
                        "description": "Download quality: 'low', 'medium', or 'high'.",
                        "default":     "medium",
                    },
                    "spacing": {
                        "type":        "number",
                        "description": "Spacing in metres between imported assets along X axis.",
                        "default":     3.0,
                    },
                    "my_assets_only": {
                        "type":        "boolean",
                        "description": (
                            "If true, search only assets you own on Megascans (view=myscans). "
                            "Default false — searches the full Megascans catalog so missing "
                            "local assets can be found and downloaded automatically."
                        ),
                        "default":     False,
                    },
                    "allow_download": {
                        "type":        "boolean",
                        "description": (
                            "When true (default), the pipeline supplements local results with "
                            "Megascans API downloads whenever fewer than top_k assets are found "
                            "locally. Set to false to restrict to local sources only."
                        ),
                        "default":     True,
                    },
                    "force_online": {
                        "type":        "boolean",
                        "description": (
                            "When true, always queries Quixel Bridge and the Megascans API even "
                            "when the local catalog already returned top_k results. Use this to "
                            "refresh stale local results or to merge online assets into the scene."
                        ),
                        "default":     False,
                    },
                    "environment": {
                        "type":        "string",
                        "description": (
                            "Target environment name for semantic layout "
                            "(e.g. 'western_room', 'industrial_hangar', 'robotics_lab'). "
                            "Auto-detected from intent if omitted."
                        ),
                        "default":     "",
                    },
                    "room_half_width": {
                        "type":        "number",
                        "description": (
                            "Half-width of the room boundary in metres used for "
                            "collision and constraint solving. Default 5.0 (10 m room)."
                        ),
                        "default":     5.0,
                    },
                },
            },
            handler=_handle_build_scene_from_assets,
            category="execution",
        ),
        ToolDefinition(
            name="review_execution",
            description=(
                "Post-execution review: compare the actual execution result against "
                "the original plan, compute intent-match score, and return findings "
                "and recommendations. Always call after execute_workflow_transaction."
            ),
            inputSchema={
                "type":     "object",
                "required": ["execution_result_json"],
                "properties": {
                    "execution_result_json": {
                        "type":        "string",
                        "description": "JSON-serialised result dict from execute_workflow_transaction.",
                    },
                    "plan_json": {
                        "type":        "string",
                        "description": "JSON-serialised plan dict from plan_scene (optional but recommended).",
                    },
                },
            },
            handler=_handle_review_execution,
            category="execution",
        ),
    ]

    for defn in _tools:
        registry.register_tool(defn)
        if transport is not None:
            transport.register_tool(defn)

    return registry


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[MCPToolRegistry] = None
_LOCK = threading.Lock()


def get_mcp_tool_registry() -> MCPToolRegistry:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = MCPToolRegistry()
        return _INSTANCE


def reset_mcp_tool_registry_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
