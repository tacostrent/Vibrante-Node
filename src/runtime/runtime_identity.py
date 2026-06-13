"""
Runtime Identity
================
Defines the Vibrante Runtime's operational identity — the structured
representation exposed to connected LLMs so they understand what environment
they are operating inside.

This is NOT creative prompting. It is a runtime operational specification.
Every constant here is consumed by runtime_bootstrap.py and
runtime_prompt_context.py to produce the system prompt injected into
Claude / Codex / GPT sessions at connection time.
"""

from __future__ import annotations

RUNTIME_NAME    = "Vibrante Runtime"
RUNTIME_VERSION = "2.5.0"
RUNTIME_TYPE    = "AI-native procedural orchestration runtime"
EXECUTION_MODEL = "semantic_transactional_execution"

EXECUTION_RULES: list[str] = [
    "semantic workflows only — no raw Houdini API calls",
    "all mutations require a transaction",
    "preview before execution — inspect risk before committing",
    "validation required — RuntimeConstraints enforced on every plan",
    "review after execution — post-execution review confirms intent match",
    "no direct Houdini mutation — all ops route through houdini_runtime",
    "no arbitrary Python execution via MCP tools",
]

RECOMMENDED_EXECUTION_FLOW: list[str] = [
    "1. initialize_runtime_context       — read scene and runtime state (call first)",
    "2. query_capabilities               — know what the runtime can do",
    "3. query_workflow_templates         — find applicable templates",
    "4. plan_scene                       — parse intent → validated execution plan",
    "5. preview_execution                — inspect operations and risk",
    "6. validate_execution_plan          — structural + constraint pass",
    "7. hou_mcp_build_scene_from_intent  — FOR SCENE INTENTS: import real assets into Houdini FIRST (geometry before lights)",
    "8. execute_workflow_transaction     — run remaining workflow via transaction system",
    "9. review_execution                 — verify intent was achieved (geometry + lighting + composition, not just 'no errors')",
]

MCP_TOOL_NAMES: list[str] = [
    # Runtime
    "initialize_runtime_context",
    "query_runtime_state",
    "query_scene_context",
    # Knowledge
    "query_capabilities",
    "query_workflow_templates",
    "query_examples",
    "query_node_parameters",
    # Planning
    "plan_scene",
    "preview_execution",
    "validate_execution_plan",
    # Execution
    "execute_workflow_transaction",
    "review_execution",
]

RUNTIME_IDENTITY: dict = {
    "name":                      RUNTIME_NAME,
    "version":                   RUNTIME_VERSION,
    "type":                      RUNTIME_TYPE,
    "execution_model":           EXECUTION_MODEL,
    "rules":                     EXECUTION_RULES,
    "recommended_execution_flow": RECOMMENDED_EXECUTION_FLOW,
    "mcp_tools":                 MCP_TOOL_NAMES,
}
