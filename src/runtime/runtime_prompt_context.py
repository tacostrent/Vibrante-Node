"""
Runtime Prompt Context
======================
Generates operational runtime context strings for LLMs.

This is NOT creative prompting.
This is runtime operational specification injected at session start so that
Claude, Codex, and GPT agents understand the Vibrante environment before
issuing any commands.

Public API:
    get_system_prompt() -> str
        Full operational system prompt — inject into LLM system message on connect.

    get_execution_rules_block() -> str
        Execution rules section only (for refreshes / brief summaries).

    get_recommended_flow_block() -> str
        Recommended 8-step execution flow section.

    get_tool_guide() -> str
        One-line-per-tool reference of available MCP tools.

    get_scene_context_block(scene_context) -> str
        Formats a scene_context dict into a human-readable block for mid-session
        context injection.

    get_contextual_prompt(scene_context=None) -> str
        Shorter mid-session refresh prompt (rules + optional scene context).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.runtime.runtime_identity import (
    EXECUTION_RULES,
    RECOMMENDED_EXECUTION_FLOW,
    RUNTIME_NAME,
    RUNTIME_TYPE,
)


# ---------------------------------------------------------------------------
# Block generators
# ---------------------------------------------------------------------------

def get_execution_rules_block() -> str:
    rules = "\n".join(f"- {r}" for r in EXECUTION_RULES)
    return f"Execution Rules:\n{rules}"


def get_recommended_flow_block() -> str:
    steps = "\n".join(RECOMMENDED_EXECUTION_FLOW)
    return f"Preferred Execution Flow:\n{steps}"


def get_tool_guide() -> str:
    return """\
Available MCP Tools:

RUNTIME:
  initialize_runtime_context   — read current scene + runtime state (call first)
  query_runtime_state          — live runtime metrics and status
  query_scene_context          — structured Houdini scene snapshot

KNOWLEDGE:
  query_capabilities           — enumerate what the runtime can do
  query_workflow_templates     — browse available workflow templates
  query_examples               — get execution examples for an intent
  query_node_parameters        — list parameter names + values for a Houdini node

PLANNING:
  plan_scene                   — parse a natural-language intent → execution plan
  preview_execution            — inspect operations + risk without executing
  validate_execution_plan      — structural + constraint validation pass

EXECUTION:
  execute_workflow_transaction — run a validated plan via the transaction system
  review_execution             — post-execution intent-match review"""


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def get_system_prompt() -> str:
    """Full operational system prompt.

    Inject this into the LLM system message on session start to establish
    Vibrante Runtime awareness.  Idempotent — safe to call multiple times.
    """
    return f"""\
You are operating inside {RUNTIME_NAME}.

{RUNTIME_NAME} is an {RUNTIME_TYPE}.

{get_execution_rules_block()}

{get_recommended_flow_block()}

{get_tool_guide()}

IMPORTANT:
- Always call initialize_runtime_context before issuing any execution commands.
- Always call preview_execution before execute_workflow_transaction.
- Never attempt raw Houdini API calls — they are not exposed.
- Never skip validation — the runtime enforces it automatically.
- After execution, always call review_execution to verify the intent was achieved.
"""


# ---------------------------------------------------------------------------
# Scene context formatter
# ---------------------------------------------------------------------------

def get_scene_context_block(scene_context: Optional[Dict[str, Any]]) -> str:
    """Format a scene_context dict into a concise human-readable block."""
    if not scene_context:
        return "Scene Context: not available"

    lines: List[str] = ["Current Scene Context:"]

    scene = scene_context.get("scene", {})
    if scene:
        lines.append(f"  hip_file:         {scene.get('hip_file', 'untitled')}")
        lines.append(f"  houdini_version:  {scene.get('houdini_version', 'unknown')}")
        fr = scene.get("frame_range", [1, 240])
        lines.append(f"  frame:            {scene.get('frame', 1)}  range {fr[0]}–{fr[1]}")

    networks = scene_context.get("networks", {})
    for net_name, nodes in networks.items():
        if nodes:
            names = [n.get("name", "?") for n in nodes[:5]]
            suffix = f" (+{len(nodes) - 5} more)" if len(nodes) > 5 else ""
            lines.append(f"  {net_name}: {', '.join(names)}{suffix}")

    selection = scene_context.get("selection", [])
    if selection:
        paths = [n.get("path", "?") for n in selection[:3]]
        lines.append(f"  selection: {', '.join(paths)}")

    assets = scene_context.get("assets", {})
    hdas = assets.get("hda_files", [])
    if hdas:
        lines.append(f"  hda_files: {len(hdas)} loaded")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Contextual / mid-session prompt
# ---------------------------------------------------------------------------

def get_contextual_prompt(scene_context: Optional[Dict[str, Any]] = None) -> str:
    """Shorter mid-session context refresh — rules + optional current scene."""
    blocks = [get_execution_rules_block()]
    if scene_context:
        blocks.append(get_scene_context_block(scene_context))
    return "\n\n".join(blocks)
