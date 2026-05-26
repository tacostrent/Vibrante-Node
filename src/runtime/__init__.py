"""
Vibrante-Node Runtime Layer
===========================
Orchestration seam between graph nodes and the underlying DCC bridges /
external services. Modules:

    mcp_runtime              — long-lived MCP client session registry (Tier 1)
    scene_cache              — per-run TTL cache + dirty scene tracking (Tier 1/2)
    houdini_runtime          — semantic Houdini ops + per-op rollback handlers (Tier 1/2)
    transaction_manager      — DCC-agnostic transaction lifecycle + history (Tier 2)
    dependency_graph         — inter-node dependency tracking (Tier 2.5)
    validation_engine        — pre-execution op validation (Tier 2.5)
    audit_store              — persistent JSONL transaction audit trail (Tier 2.5)
    execution_scheduler      — serialised mutation queue (Tier 2.5/5)
    capability_registry      — dynamic capability tracking (Tier 2.75)
    resource_estimator       — heuristic cost estimation (Tier 2.75)
    runtime_constraints      — protected paths + forbidden ops (Tier 2.75)
    workflow_templates       — parameterised workflow blueprints (Tier 2.75)
    semantic_registry        — named semantic operation handlers (Tier 2.75)
    semantic_execution       — deterministic intent → plan → execute (Tier 2.75)
    llm_provider             — optional LLM provider abstraction (Tier 3)
    planning_memory          — structured planning event store (Tier 3)
    intent_parser            — deterministic NL→intent parser + LLM enhancement (Tier 3)
    contextual_reasoning     — pre-planning scene analysis (Tier 3)
    ai_planner               — AI plan generation from parsed intent (Tier 3)
    plan_validator           — multi-layer pre-execution plan validation (Tier 3)
    execution_explainer      — human-readable explanation generator (Tier 3)
    execution_review         — post-execution structured review (Tier 3)
    approval_pipeline        — human approval gate (Tier 3)
    mcp_server_runtime       — MCP server mode: Vibrante as an MCP server (Tier 4)
    distributed_runtime      — distributed execution + worker routing (Tier 4)
    agent_runtime            — runtime-supervised agent system (Tier 4)
    multi_dcc_runtime        — multi-DCC routing + adapter protocol (Tier 4)
    knowledge_graph          — in-memory semantic entity/relationship graph (Tier 4)
    semantic_memory          — persistent structured orchestration patterns (Tier 4)
    worker_runtime           — worker pool accounting for distributed work (Tier 4)
    workflow_federation      — cross-DCC federated workflow execution (Tier 4)
    runtime_federation_api   — runtime-to-runtime capability exchange (Tier 4)
    workflow_optimizer       — advisory execution path optimizer (Tier 5)
    runtime_analytics        — execution performance data collector (Tier 5)
    predictive_execution     — heuristic failure prediction engine (Tier 5)
    orchestration_heuristics — reusable execution ordering heuristics (Tier 5)
    recommendation_engine    — advisory workflow recommendation engine (Tier 5)
    resource_optimizer       — advisory resource allocation optimizer (Tier 5)
    failure_intelligence     — failure pattern detector and analyzer (Tier 5)
    execution_quality        — orchestration quality evaluator (Tier 5)
    studio_knowledge         — studio pipeline pattern knowledge store (Tier 5)
    runtime_identity         — operational identity constants for LLMs (§19)
    runtime_bootstrap        — runtime warm-up + bootstrap payload (§19)
    runtime_prompt_context   — operational system-prompt generator (§19)
    mcp_session              — connected LLM session lifecycle (§19)
    mcp_tool_registry        — semantic tool registry + 11 MCP handlers (§19)
    mcp_transport            — stdio MCP transport wrapping the mcp SDK (§19)

Import order note (Tier 2 constraint):
    houdini_runtime registers rollback handlers with transaction_manager at
    import time. houdini_runtime.py imports transaction_manager directly at
    its top level, so the registration order is self-contained — no special
    ordering is required here.

All modules use lazy imports: nothing is loaded until first accessed.
Callers import the submodule they need directly:

    from src.runtime import mcp_runtime, houdini_runtime, transaction_manager
    from src.runtime import dependency_graph, validation_engine
    from src.runtime import semantic_registry, semantic_execution
    from src.runtime import ai_planner, intent_parser, approval_pipeline
    from src.runtime import mcp_server_runtime, distributed_runtime, agent_runtime
    from src.runtime import multi_dcc_runtime, knowledge_graph, semantic_memory
    from src.runtime import worker_runtime, workflow_federation, runtime_federation_api
    from src.runtime import workflow_optimizer, runtime_analytics, predictive_execution
    from src.runtime import orchestration_heuristics, recommendation_engine
    from src.runtime import resource_optimizer, failure_intelligence, execution_quality
    from src.runtime import studio_knowledge
    from src.runtime.scene_cache import get_scene_cache
"""

import importlib as _importlib

__all__ = [
    "mcp_runtime",
    "houdini_runtime",
    "scene_cache",
    "transaction_manager",
    "dependency_graph",
    "validation_engine",
    "audit_store",
    "execution_scheduler",
    "capability_registry",
    "resource_estimator",
    "runtime_constraints",
    "workflow_templates",
    "semantic_registry",
    "semantic_execution",
    "llm_provider",
    "planning_memory",
    "intent_parser",
    "contextual_reasoning",
    "ai_planner",
    "plan_validator",
    "execution_explainer",
    "execution_review",
    "approval_pipeline",
    "mcp_server_runtime",
    "distributed_runtime",
    "agent_runtime",
    "multi_dcc_runtime",
    "knowledge_graph",
    "semantic_memory",
    "worker_runtime",
    "workflow_federation",
    "runtime_federation_api",
    "workflow_optimizer",
    "runtime_analytics",
    "predictive_execution",
    "orchestration_heuristics",
    "recommendation_engine",
    "resource_optimizer",
    "failure_intelligence",
    "execution_quality",
    "studio_knowledge",
    # MCP Operational Layer (§19)
    "runtime_identity",
    "runtime_bootstrap",
    "runtime_prompt_context",
    "mcp_session",
    "mcp_tool_registry",
    "mcp_transport",
]


def __getattr__(name: str):
    if name in __all__:
        mod = _importlib.import_module(f"src.runtime.{name}")
        globals()[name] = mod
        return mod
    raise AttributeError(f"module 'src.runtime' has no attribute {name!r}")
