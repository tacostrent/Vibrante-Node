"""
Runtime Bootstrap Protocol
==========================
Provides the runtime identity and orchestration rules to connected LLMs
immediately after connection. This is the step that makes Claude, Codex,
and GPT-based agents understand the Vibrante environment before issuing any
commands.

Public API:
    initialize_runtime() -> dict        — warm up all runtime singletons; returns status
    get_bootstrap_data() -> dict        — structured payload for LLMs on first connect
    get_runtime_capabilities() -> list  — live capability list from registry
    get_available_templates() -> list   — live template ids from workflow_templates
    get_available_operations() -> list  — live operation ids from semantic_registry
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

from src.runtime.runtime_identity import RUNTIME_IDENTITY


# ---------------------------------------------------------------------------
# Runtime initialisation
# ---------------------------------------------------------------------------

def initialize_runtime() -> Dict[str, Any]:
    """Touch all runtime singletons to warm caches before accepting connections.

    Returns a status dict with keys:
        ok          — True always (individual errors captured per-module)
        modules     — list of successfully loaded module names
        initialized_at — float timestamp
        <module>_error — present only when that module failed to import/init
    """
    status: Dict[str, Any] = {"initialized_at": time.time(), "modules": []}

    _warm(status, "capability_registry",
          lambda: __import__("src.runtime.capability_registry", fromlist=["get_capability_registry"])
                  .get_capability_registry())
    _warm(status, "workflow_templates",
          lambda: __import__("src.runtime.workflow_templates", fromlist=["get_workflow_templates"])
                  .get_workflow_templates())
    _warm(status, "semantic_registry",
          lambda: __import__("src.runtime.semantic_registry", fromlist=["get_semantic_registry"])
                  .get_semantic_registry())
    _warm(status, "transaction_manager",
          lambda: __import__("src.runtime.transaction_manager", fromlist=["get_transaction_manager"])
                  .get_transaction_manager())
    _warm(status, "validation_engine",
          lambda: __import__("src.runtime.validation_engine", fromlist=["get_validation_engine"])
                  .get_validation_engine())
    _warm(status, "runtime_constraints",
          lambda: __import__("src.runtime.runtime_constraints", fromlist=["get_runtime_constraints"])
                  .get_runtime_constraints())
    _warm(status, "ai_planner",
          lambda: __import__("src.runtime.ai_planner", fromlist=["get_ai_planner"])
                  .get_ai_planner())
    _warm(status, "semantic_execution",
          lambda: __import__("src.runtime.semantic_execution", fromlist=["get_semantic_executor"])
                  .get_semantic_executor())
    _warm(status, "execution_scheduler",
          lambda: __import__("src.runtime.execution_scheduler", fromlist=["get_execution_scheduler"])
                  .get_execution_scheduler())

    status["ok"] = True
    return status


def _warm(status: Dict[str, Any], module_name: str, loader) -> None:
    try:
        loader()
        status["modules"].append(module_name)
    except Exception as exc:
        status[f"{module_name}_error"] = str(exc)


# ---------------------------------------------------------------------------
# Live queries
# ---------------------------------------------------------------------------

def get_runtime_capabilities() -> List[Dict[str, Any]]:
    """Return the live capability list (type, id, metadata) from the registry."""
    try:
        from src.runtime.capability_registry import get_capability_registry
        return get_capability_registry().query_capabilities()
    except Exception:
        return []


def get_available_templates() -> List[str]:
    """Return available workflow template ids."""
    try:
        from src.runtime.workflow_templates import get_workflow_templates
        return [t["template_id"] for t in get_workflow_templates().list_templates()]
    except Exception:
        return []


def get_available_operations() -> List[str]:
    """Return available semantic operation ids from the semantic registry."""
    try:
        from src.runtime.semantic_registry import get_semantic_registry
        return [op["operation_id"] for op in get_semantic_registry().list_operations()]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Bootstrap payload
# ---------------------------------------------------------------------------

def get_bootstrap_data() -> Dict[str, Any]:
    """Structured bootstrap payload sent to LLMs right after connection.

    This establishes Vibrante Runtime awareness before any commands are
    issued.  The payload is designed to be injected as structured context so
    the LLM understands:
      - what this environment is
      - what rules it must follow
      - what tools are available
      - what the recommended execution flow is
    """
    return {
        "runtime_name":              RUNTIME_IDENTITY["name"],
        "runtime_version":           RUNTIME_IDENTITY["version"],
        "runtime_type":              RUNTIME_IDENTITY["type"],
        "execution_model":           RUNTIME_IDENTITY["execution_model"],
        "runtime_rules":             RUNTIME_IDENTITY["rules"],
        "available_capabilities":    get_runtime_capabilities(),
        "workflow_templates":        get_available_templates(),
        "available_operations":      get_available_operations(),
        "recommended_execution_flow": RUNTIME_IDENTITY["recommended_execution_flow"],
        "mcp_tools":                 RUNTIME_IDENTITY["mcp_tools"],
    }
