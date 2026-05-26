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
    from src.runtime.runtime_bootstrap import initialize_runtime, get_bootstrap_data
    client_id = str(args.get("client_id", ""))
    init_status = initialize_runtime()
    bootstrap   = get_bootstrap_data()
    return {
        "ok":        True,
        "status":    init_status,
        "bootstrap": bootstrap,
        "message": (
            "Vibrante Runtime initialized. "
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
    try:
        from src.runtime.workflow_templates import get_workflow_templates
        wt = get_workflow_templates()
        for tmpl in wt.list_templates():
            tid  = tmpl.get("template_id", "")
            desc = tmpl.get("description", "")
            if intent.lower() in tid.lower() or intent.lower() in desc.lower():
                results["template_example"] = {
                    "template_id": tid,
                    "description": desc,
                    "variables":   tmpl.get("variables", {}),
                    "usage": (
                        f"Use query_workflow_templates and then pass the resolved ops "
                        f"to execute_workflow_transaction."
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

async def _handle_plan_scene(args: Dict[str, Any]) -> Dict[str, Any]:
    prompt = str(args.get("prompt", "")).strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    try:
        from src.runtime.intent_parser      import get_intent_parser
        from src.runtime.contextual_reasoning import get_contextual_reasoner
        from src.runtime.ai_planner         import get_ai_planner
        parsed   = await get_intent_parser().parse(prompt)
        analysis = get_contextual_reasoner().analyze(
            parsed.get("intent", ""),
            parsed.get("parameters", {}),
        )
        plan = await get_ai_planner().plan(parsed, analysis)
        return {
            "ok":              plan.get("ok", False),
            "plan":            plan,
            "parsed_intent":   parsed,
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
