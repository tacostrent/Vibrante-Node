"""
MCP Server Runtime (Tier 4)
============================
Exposes the Vibrante semantic runtime as an MCP server so that external
agents (Claude, Cursor, GPT, IDEs) can call structured runtime tools via
the Model Context Protocol.

SAFETY RULE: No tool may expose arbitrary Python execution, raw Houdini
mutations, or bypass the validation / approval / transaction pipeline.
All requests are routed through the existing Tier 1–3 pipeline.

Exposed tools:
    vibrante_plan_workflow        — intent → validated execution plan
    vibrante_preview_plan         — validate a plan without executing
    vibrante_list_capabilities    — query the capability registry
    vibrante_list_templates       — list available workflow templates
    vibrante_query_audit          — query recent audit records
    vibrante_get_scene_status     — scene cache dirty state / lineage

Public API:
    get_mcp_server_runtime() -> McpServerRuntime   (singleton)
    reset_mcp_server_runtime_for_tests()

    McpServerRuntime.list_tools() -> list[dict]
    McpServerRuntime.handle_request(tool_name, arguments) -> dict   (async)
    McpServerRuntime.register_tool(name, description, schema, handler)
"""

import json
import threading
from typing import Any, Callable, Coroutine, Dict, List, Optional

# ---------------------------------------------------------------------------
# Built-in tool schemas (MCP-format inputSchema)
# ---------------------------------------------------------------------------

_BUILTIN_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "vibrante_plan_workflow": {
        "type": "object",
        "properties": {
            "prompt":     {"type": "string", "description": "Natural language description of intent"},
            "context":    {"type": "object", "description": "Optional planning context (parent, name, style …)"},
        },
        "required": ["prompt"],
    },
    "vibrante_preview_plan": {
        "type": "object",
        "properties": {
            "plan":            {"type": "object", "description": "Plan dict from vibrante_plan_workflow"},
            "max_cook_cost":   {"type": "number", "description": "Cook cost threshold (default 1.5)"},
            "max_op_count":    {"type": "integer", "description": "Op count threshold (default 150)"},
        },
        "required": ["plan"],
    },
    "vibrante_list_capabilities": {
        "type": "object",
        "properties": {
            "cap_type": {"type": "string", "description": "Filter by capability type (optional)"},
        },
    },
    "vibrante_list_templates": {
        "type": "object",
        "properties": {
            "tag":    {"type": "string", "description": "Filter templates by tag (optional)"},
            "apply":  {"type": "string", "description": "Template id to resolve to ops (optional)"},
            "params": {"type": "object", "description": "Parameters for template resolution"},
        },
    },
    "vibrante_query_audit": {
        "type": "object",
        "properties": {
            "limit":  {"type": "integer", "description": "Max records to return (default 10)"},
            "status": {"type": "string",  "description": "Filter by status (optional)"},
        },
    },
    "vibrante_get_scene_status": {
        "type": "object",
        "properties": {},
    },
}

_BUILTIN_DESCRIPTIONS: Dict[str, str] = {
    "vibrante_plan_workflow":     "Parse a natural language prompt to a structured execution plan. Never executes.",
    "vibrante_preview_plan":      "Validate a plan dict and return risk level, errors, and capability gaps. Never executes.",
    "vibrante_list_capabilities": "List runtime capabilities (optionally filtered by type).",
    "vibrante_list_templates":    "List workflow templates and optionally resolve one to concrete operations.",
    "vibrante_query_audit":       "Query the audit store for recent transaction records.",
    "vibrante_get_scene_status":  "Return the current scene cache dirty state and semantic lineage.",
}


# ---------------------------------------------------------------------------
# Built-in handlers
# ---------------------------------------------------------------------------

async def _handle_plan_workflow(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from src.runtime.intent_parser        import get_intent_parser
    from src.runtime.contextual_reasoning import get_contextual_reasoner
    from src.runtime.ai_planner           import get_ai_planner
    from src.runtime.execution_explainer  import get_execution_explainer

    prompt  = str(arguments.get("prompt", "")).strip()
    context = dict(arguments.get("context") or {})
    if not prompt:
        return {"ok": False, "errors": ["prompt must not be empty"]}

    parsed       = await get_intent_parser().parse(prompt, context)
    ctx_analysis = get_contextual_reasoner().analyze(
        parsed.get("intent", ""), parsed.get("parameters", {}), None
    )
    plan     = await get_ai_planner().plan(parsed, ctx_analysis, None)
    expl     = get_execution_explainer().explain_plan(plan)

    return {
        "ok":               plan.get("ok", False),
        "intent":           plan.get("intent", ""),
        "plan":             plan,
        "plan_json":        json.dumps(plan, default=str),
        "requires_approval": plan.get("requires_approval", False),
        "explanation":      expl.get("full_text", ""),
    }


async def _handle_preview_plan(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from src.runtime.plan_validator      import get_plan_validator
    from src.runtime.execution_explainer import get_execution_explainer

    plan = arguments.get("plan")
    if not isinstance(plan, dict):
        return {"ok": False, "errors": ["plan must be a dict"]}

    result = await get_plan_validator().validate(
        plan,
        max_cook_cost=float(arguments.get("max_cook_cost", 1.5)),
        max_op_count=int(arguments.get("max_op_count", 150)),
    )
    expl = get_execution_explainer().explain_validation(result)
    return {**result, "explanation": expl.get("full_text", "")}


async def _handle_list_capabilities(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from src.runtime.capability_registry import get_capability_registry
    cap_type = arguments.get("cap_type") or None
    caps = get_capability_registry().query_capabilities(cap_type)
    return {"capabilities": caps, "count": len(caps)}


async def _handle_list_templates(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from src.runtime.workflow_templates import get_workflow_templates
    wt    = get_workflow_templates()
    tag   = arguments.get("tag") or None
    apply = arguments.get("apply") or None
    templates = wt.list_templates(tag=tag)
    result: Dict[str, Any] = {"templates": templates, "count": len(templates)}
    if apply:
        try:
            ops = wt.apply_template(apply, dict(arguments.get("params") or {}))
            result["operations"] = ops
            result["applied"] = apply
        except (KeyError, ValueError) as exc:
            result["apply_error"] = str(exc)
    return result


async def _handle_query_audit(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from src.runtime.audit_store import get_audit_store
    limit  = int(arguments.get("limit", 10))
    status = arguments.get("status") or None
    records = await get_audit_store().query_transactions(limit=limit, status=status)
    return {"records": records, "count": len(records)}


async def _handle_get_scene_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    from src.runtime.scene_cache import get_scene_cache
    cache = get_scene_cache()
    return {
        "dirty_nodes":      cache.get_dirty_nodes(),
        "semantic_lineage": cache.get_semantic_lineage(),
        "cache_stats":      cache.stats(),
    }


_BUILTIN_HANDLERS: Dict[str, Callable[..., Coroutine]] = {
    "vibrante_plan_workflow":     _handle_plan_workflow,
    "vibrante_preview_plan":      _handle_preview_plan,
    "vibrante_list_capabilities": _handle_list_capabilities,
    "vibrante_list_templates":    _handle_list_templates,
    "vibrante_query_audit":       _handle_query_audit,
    "vibrante_get_scene_status":  _handle_get_scene_status,
}


# ---------------------------------------------------------------------------
# McpServerRuntime
# ---------------------------------------------------------------------------

class McpServerRuntime:
    """Virtual MCP server exposing structured Vibrante runtime tools.

    Provides the tool registry and request dispatch layer. Actual transport
    (stdio / SSE) is wired by the caller when connecting to real MCP clients.
    """

    def __init__(self) -> None:
        self._lock    = threading.Lock()
        self._tools:    Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[str, Callable]        = {}
        self._running   = False
        self._register_builtins()

    def _register_builtins(self) -> None:
        for name, handler in _BUILTIN_HANDLERS.items():
            self._tools[name] = {
                "name":        name,
                "description": _BUILTIN_DESCRIPTIONS[name],
                "inputSchema": _BUILTIN_SCHEMAS[name],
            }
            self._handlers[name] = handler

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def register_tool(
        self,
        name:        str,
        description: str,
        schema:      Dict[str, Any],
        handler:     Callable[..., Coroutine],
    ) -> None:
        """Register a custom tool.

        The handler must be an async callable accepting (arguments: dict) → dict.
        It MUST NOT bypass the runtime pipeline (no direct bridge calls,
        no arbitrary Python execution).
        """
        if not name:
            raise ValueError("Tool name must be non-empty")
        with self._lock:
            self._tools[name] = {
                "name":        name,
                "description": description,
                "inputSchema": dict(schema),
            }
            self._handlers[name] = handler

    def deregister_tool(self, name: str) -> bool:
        """Remove a registered tool. Returns True if found and removed."""
        if name in _BUILTIN_HANDLERS:
            raise ValueError(f"Cannot deregister built-in tool: {name!r}")
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                del self._handlers[name]
                return True
        return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return all registered tools in MCP format (sorted by name)."""
        with self._lock:
            return sorted(self._tools.values(), key=lambda t: t["name"])

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """Return a single tool definition, or None."""
        with self._lock:
            t = self._tools.get(name)
            return dict(t) if t else None

    # ------------------------------------------------------------------
    # Request dispatch
    # ------------------------------------------------------------------

    async def handle_request(
        self,
        tool_name:  str,
        arguments:  Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Dispatch an MCP tool call.

        Returns a structured result dict. Never raises — errors are captured
        in the returned dict under the key ``"is_error": True``.
        """
        arguments = dict(arguments or {})
        with self._lock:
            handler = self._handlers.get(tool_name)
        if handler is None:
            return {
                "is_error": True,
                "error":    f"Unknown tool: {tool_name!r}",
                "tool":     tool_name,
            }
        try:
            result = await handler(arguments)
            if not isinstance(result, dict):
                result = {"result": result}
            result["is_error"] = False
            result["tool"]     = tool_name
            return result
        except Exception as exc:
            return {"is_error": True, "error": str(exc), "tool": tool_name}

    # ------------------------------------------------------------------
    # Server lifecycle (stub — transport wired externally)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Mark server as started. Transport connection is managed externally."""
        with self._lock:
            self._running = True

    def stop(self) -> None:
        """Mark server as stopped."""
        with self._lock:
            self._running = False

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "tool_count": len(self._tools),
                "tools":      sorted(self._tools.keys()),
                "running":    self._running,
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[McpServerRuntime] = None
_LOCK = threading.Lock()


def get_mcp_server_runtime() -> McpServerRuntime:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = McpServerRuntime()
        return _INSTANCE


def reset_mcp_server_runtime_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
