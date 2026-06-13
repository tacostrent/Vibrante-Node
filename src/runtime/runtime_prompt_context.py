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
        Full operational system prompt - inject into LLM system message on connect.

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

    get_scene_planning_block() -> str
        Semantic scene assembly guidance rules (Tier 2 - for LLM context injection).

    get_scene_realization_block() -> str
        Scene realization guidance rules (Tier 3 - for LLM context injection).

    get_cinematic_scene_layer_block() -> str
        Cinematic scene layer guidance rules (Tier 4 - lighting, camera, atmosphere, review).

    get_production_knowledge_block() -> str
        Production Knowledge System rules (Tier 5 - memory, patterns, recommendations).

    get_environment_construction_block() -> str
        Environment construction rules (Tier 9 - §29 Semantic Asset Assembly).

    get_workflow_pack_block() -> str
        Workflow Pack rules (Tier 10 - §30 Workflow Packs & Production Blueprints).

    get_asset_ecosystem_block() -> str
        Asset Ecosystem rules (Tier 12 - §32 Asset Ecosystem Expansion).

    get_asset_realization_block() -> str
        Asset Realization & DCC Integration rules (Tier 13 - §33).

    get_lookdev_intelligence_block() -> str
        Lookdev & Material Intelligence rules (Tier 14 - §34).

    get_semantic_catalog_block() -> str
        Semantic Asset Catalog rules (Tier 12.7 - §35).

    get_semantic_retrieval_block() -> str
        Semantic Vector Search & Asset Retrieval rules (Tier 12.8 - §36).

    get_online_acquisition_block() -> str
        Online Asset Acquisition & Intelligent Asset Fetching rules (Tier 12.9 - §37).
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
# Cinematic orchestration guidance
# ---------------------------------------------------------------------------

_CINEMATIC_RULES = [
    "Decompose large cinematic goals into ordered stage sequences before executing.",
    "Never execute a cinematic workflow as a single operation - always use staged execution.",
    "Use plan_scene to decompose 'create explosion scene' into specific ordered workflow stages.",
    "Stage dependencies are real - terrain_prep MUST precede pyro_source; lighting MUST precede render.",
    "Artistic constraints are non-negotiable - motion blur, EXR output, emission AOV are required for cinematic work.",
    "After cinematic execution, always call review_execution - 'Execution successful' is NOT an acceptable review.",
    "Production-ready means: specific stages passed, specific criteria met - not just 'no errors'.",
]

_CINEMATIC_GOOD_PATTERNS = """\
GOOD - Decomposed cinematic execution:
  plan_scene("create cinematic explosion")
    → matched: cinematic_explosion, dust_wave, debris_field, arnold_cinematic_lighting,
               cinematic_push_in, arnold_render_ready
    → 34 ordered stages queued
    → review: "9/9 stages passed. Emission AOV confirmed. Cryptomatte configured."

GOOD - Specific review feedback:
  review_execution(result)
    → [Review] Stage [smoke_evolution] ⚠ - smoke breakup lacks variation.
    → [Review] Stage [camera_framing] ✓ - 24-frame anticipation hold present.
    → Production-ready: advisory notes only.
"""

_CINEMATIC_BAD_PATTERNS = """\
BAD - Single-shot execution (produces random non-cinematic output):
  execute_workflow_transaction(intent="create explosion scene")
    → ✗ Missing stage ordering
    → ✗ No terrain interaction setup
    → ✗ No lighting before render
    → ✗ No camera setup

BAD - Lights only, no geometry (incomplete scene - the most common failure):
  intent="build western old room"
    → Creates 3 lights in /stage
    → Says "Next step: add your saloon assets manually"
    → ✗ WRONG - the agent must import the geometry, not delegate it back to the user
    → ✗ A scene with lights but no geometry is NOT a scene - it is an empty lit void
    → Correct: call hou_mcp_build_scene_from_intent FIRST, then add lighting

BAD - Primitive geometry fallback (never acceptable for real-world objects):
  bridge.create_node("/obj", "box", "barrel")     ← a barrel is NOT a box
  bridge.create_node("/obj", "tube", "column")    ← a column is NOT a tube
  bridge.create_node("/obj", "grid", "floor")     ← a floor is NOT a grid
    → These are placeholder shapes, not production assets
    → Always import real Megascans assets via hou_mcp_import_asset or hou_mcp_build_scene_from_intent

BAD - Generic success response (no artistic critique):
  review_execution(result)
    → "Execution completed successfully."  ← WRONG - this tells nothing
    → Should say: "Smoke breakup lacks variation - add turbulence layers."
"""

# ---------------------------------------------------------------------------
# Semantic scene planning guidance (Tier 2)
# ---------------------------------------------------------------------------

_SCENE_PLANNING_RULES = [
    # Asset-first - NEVER primitives for real-world objects
    "CRITICAL: NEVER use Houdini primitive nodes (box, tube, sphere, grid, line, circle) to represent real-world scene objects. A barrel is a Megascans asset, not a tube SOP. A wooden floor is a Megascans surface, not a grid SOP. A wall is a surface asset, not a box SOP. Primitives are ONLY for abstract math geometry.",
    "CRITICAL: Always query the asset library BEFORE building any scene. The mandatory sequence is: (1) hou_mcp_build_scene_from_intent → geometry + assets, (2) atmosphere, (3) camera, (4) lights. Never skip straight to lighting - lights on empty geometry = failure.",
    "CRITICAL: Geometry ALWAYS comes before lighting. A scene description like 'western old room' means: floor, walls, furniture, barrels, and props FIRST. Then lights. Reporting a scene as done after only creating lights is incorrect and incomplete.",
    "If the semantic catalog is empty or returns no results, call hou_mcp_catalog_sync first to import available local Megascans assets. Never fall back to primitives when the catalog is empty - sync first.",
    "If hou_mcp_build_scene_from_intent returns 0 assets, report the reason clearly (catalog empty / Megascans credentials missing) and guide the user to fix it. Do NOT proceed to lights.",
    "Unknown environments (western, medieval, jungle, desert, etc.) are handled by keyword extraction - pass the full intent text to hou_mcp_asset_retrieval and let the hybrid ranking engine find matching assets by tags and description.",
    # Layout and composition
    "Always construct scenes through semantic layout planning - never place assets at random positions.",
    "Prefer cinematic composition over dense asset placement; a clear hero focus beats a crowded scene.",
    "Maintain clear hero focus: hero_area should hold 1-3 primary assets; more dilutes narrative clarity.",
    "Preserve scene readability: populate at least midground AND background to create depth.",
    "Avoid random environment assembly - use environment rules and scene templates to guide asset placement.",
    "Use SceneLayoutPlanner to generate zone assignments before staging; zones drive import order.",
    "Validate asset compatibility before staging: conflicting style pairs (vegetation+tech_panel, creature+robot) must be resolved.",
    "Prefer AssetStagingManager.build_staging_plan for import orchestration - it validates coherence automatically.",
    "Use SemanticSceneTemplates to select a production blueprint before assembling a scene from scratch.",
]

# ---------------------------------------------------------------------------
# Scene realization guidance (Tier 3)
# ---------------------------------------------------------------------------

_SCENE_REALIZATION_RULES = [
    "Always realize scenes through deterministic semantic assembly - never place assets at arbitrary positions.",
    "Use hou_mcp_layout_preview to inspect the full operation list and complexity before committing to execution.",
    "All scene mutations go through the transaction system - hou_mcp_scene_realize handles this automatically.",
    "Rollback is automatic on failure - a partially-realized scene is always recoverable.",
    "After realization, always call hou_mcp_scene_review - a score and specific findings are required for production sign-off.",
    "Scene hierarchy is canonical: /obj/hero_assets, /obj/background, /obj/lighting, /obj/camera must be present.",
    "Transforms are deterministic: same layout_plan + staging_plan always produce the same scene layout.",
    "Import order is back-to-front (background first, hero last) - this is enforced by the staging plan.",
    "Prefer cinematic composition over dense placement - a clear hero focus beats a crowded scene.",
    "Avoid uncontrolled importing - always validate asset compatibility before staging.",
]


# ---------------------------------------------------------------------------
# Cinematic Scene Layer guidance (Tier 4 - §23)
# ---------------------------------------------------------------------------

_CINEMATIC_SCENE_LAYER_RULES = [
    "Use hou_mcp_cinematic_lighting before any render pass - cinematic scenes require planned key/rim/fill/volumetric setups.",
    "Use hou_mcp_camera_orchestrator to select a camera mode (cinematic_push_in, orbital_reveal, hero_focus, atmospheric_tracking, handheld_subtle) before staging cameras.",
    "Use hou_mcp_atmosphere_builder to establish depth-supporting fog and particles - flat scenes lack cinematic depth.",
    "Run hou_mcp_cinematic_review after assembly - 'Execution successful' is NEVER acceptable; every review must return specific per-dimension findings.",
    "Canonical cinematic pipeline order: lighting plan → camera plan → atmosphere plan → hierarchy review → cinematic review.",
    "Lighting must target hero_area - a rim light without a key on the hero fails the 'hero_locked' focus criterion.",
    "Camera readability score must reach 0.5+ - high shake intensity (>0.5) is a blocking readability issue.",
    "Atmosphere density above 0.06 is cinema-invalid - background assets become obscured and fail depth criteria.",
    "A production-ready cinematic review requires overall_score ≥ 0.7 with no critical findings (absent hero, flat lighting, undefined camera).",
    "Visual hierarchy must have at minimum hero_area + midground populated - an empty background zone is an advisory warning, an empty midground is a depth failure.",
]


# ---------------------------------------------------------------------------
# Production Knowledge System rules (Tier 5 - §24)
# ---------------------------------------------------------------------------

_PRODUCTION_KNOWLEDGE_RULES = [
    "Prefer production-proven patterns - always check hou_mcp_scene_recommendation before choosing lighting, camera, or atmosphere styles.",
    "Reuse successful scene structures - if production_memory has successful scenes of the same type, use their configuration.",
    "Avoid previously failed configurations - check hou_mcp_production_memory for failure patterns before assembling a scene.",
    "Favor high-scoring recommendations - recommendations with confidence >= 0.8 (from production_memory) should take priority over pattern or default recommendations.",
    "Preserve cinematic consistency - do not mix lighting/camera/atmosphere styles from different environments without a deliberate reason.",
    "After scene execution, record the result in production memory - call hou_mcp_production_memory with action='record_scene' to accumulate knowledge.",
    "Use hou_mcp_production_score to evaluate quality before deciding whether to record a scene as 'success' or 'failure'.",
    "Patterns with _success_count > 0 are empirically proven - prefer them over built-in defaults when available.",
]

# ---------------------------------------------------------------------------
# Environment construction guidance (Tier 9 - §29)
# ---------------------------------------------------------------------------

_ENVIRONMENT_CONSTRUCTION_RULES = [
    "Build environments through semantic zones - never place assets at random or arbitrary positions.",
    "Preserve hero readability: hero_zone must hold 1-3 primary assets; more dilutes the narrative focal point.",
    "Maintain visual hierarchy: hero (primary) → support → detail → atmosphere, in that priority order.",
    "Prefer deterministic placement - use hou_mcp_asset_placement which derives positions from PlacementTemplates.",
    "Avoid procedural clutter - detail and atmosphere assets should never dominate the population balance.",
    "Preserve cinematic composition - run hou_mcp_environment_review before realizing a scene.",
    "Respect production patterns - hou_mcp_scene_recommendation provides environment-specific proven configurations.",
    "Use hou_mcp_storytelling_layout to define the visual flow and viewer path before executing placement.",
    "Scene population must be balanced: hero_assets populated, detail_assets below 60% of total.",
    "Environment review must return specific findings - 'Execution successful' is never acceptable output.",
]

# ---------------------------------------------------------------------------
# Workflow Pack rules (Tier 10 - §30)
# ---------------------------------------------------------------------------

_WORKFLOW_PACK_RULES = [
    "Prefer workflow packs over ad-hoc orchestration - packs encapsulate proven production strategies.",
    "Use hou_mcp_workflow_recommend to select the best pack from a semantic intent before executing.",
    "Always validate a pack before execution - hou_mcp_workflow_pack retrieves the full strategy configuration.",
    "Reuse proven production blueprints - packs encode lighting, camera, atmosphere, and review thresholds.",
    "Use dry_run=True in hou_mcp_workflow_execute to preview operations before committing to scene mutation.",
    "All workflow mutations go through the transaction system - rollback is automatic on failure.",
    "After execution, always call hou_mcp_workflow_review - 'Execution successful' is never an acceptable review.",
    "Respect review thresholds - production_ready requires meeting the pack's stated production_threshold.",
    "Favor high-scoring workflow packs - check hou_mcp_workflow_statistics for success_rate before reusing a pack.",
    "Preserve production consistency - do not mix strategies from different packs without a deliberate reason.",
]

# ---------------------------------------------------------------------------
# Studio Knowledge rules (Tier 11 - §31)
# ---------------------------------------------------------------------------

_STUDIO_KNOWLEDGE_RULES = [
    "Prefer studio-approved standards - use hou_mcp_studio_standards to verify that lighting, camera, atmosphere, and workflow choices are approved before executing.",
    "Reuse successful cross-project patterns - call hou_mcp_cross_project_learning to identify the best_workflow and best_lighting before starting a new scene.",
    "Avoid historically poor-performing configurations - check hou_mcp_studio_knowledge for failure records before assembling a scene.",
    "Follow benchmark-proven production strategies - use hou_mcp_knowledge_recommendation which applies the priority chain: Standards → Cross-Project → Memory → Patterns → Defaults.",
    "Favour long-term production consistency - do not deviate from studio-approved styles without a documented reason.",
    "Use studio knowledge before generic reasoning - hou_mcp_knowledge_recommendation outranks any heuristic default when studio knowledge is available.",
    "After execution, record outcomes in studio knowledge - call hou_mcp_studio_knowledge with action='record_success' or 'record_failure' to accumulate cross-project intelligence.",
    "Benchmark new projects against historical performance - call hou_mcp_production_benchmark to classify performance and receive specific improvement recommendations.",
    "Analyse review trends with hou_mcp_review_analytics - identify recurring failures before they become studio-wide patterns.",
    "Studio standards are the highest-priority constraint - a workflow not in approved_workflows or a lighting style not in approved_lighting_styles must be justified explicitly.",
]


# ---------------------------------------------------------------------------
# Asset Ecosystem rules (Tier 12 - §32)
# ---------------------------------------------------------------------------

_ASSET_ECOSYSTEM_RULES = [
    "Prefer local assets before remote downloads - check AssetStorage before queuing downloads.",
    "Cache acquired assets - register downloaded assets in AssetStorage for reuse.",
    "Preserve asset provenance - always record_source when discovering assets from providers.",
    "Normalize all provider metadata - use ProviderNormalizer before passing assets downstream.",
    "Maintain deterministic asset selection - same query always produces the same ranked result.",
    "Avoid duplicate asset acquisition - check asset_exists() before queuing a download.",
    "Use semantic asset profiles for recommendations - enrich assets before ranking.",
    "Respect provider availability - check is_available() before querying a provider.",
    "Route all downloads through AssetDownloadManager - never bypass download tracking.",
    "Sync libraries periodically - use AssetSync to keep local storage up to date.",
]


# ---------------------------------------------------------------------------
# Asset Realization rules (Tier 13 - §33)
# ---------------------------------------------------------------------------

_ASSET_REALIZATION_RULES = [
    "Preserve provenance - always record asset source, provider, and download chain.",
    "Preserve metadata - normalization must never discard original asset metadata.",
    "Normalize assets before realization - scale, orientation, and units must be consistent.",
    "Resolve dependencies before instancing - missing textures and materials must be identified first.",
    "Use USD-friendly representations - prefer USD-compatible formats for all realizations.",
    "Generate transaction-safe realization plans - never mutate Houdini state directly.",
    "Avoid direct DCC mutations - all scene changes must go through the transaction system.",
    "Validate the full pipeline before committing - use AssetValidationPipeline before execution.",
    "Review realization quality after completion - use AssetRealizationReview for production sign-off.",
    "Prefer AssetMaterialMapper for renderer-specific material descriptions - never hardcode shader parameters.",
]


# ---------------------------------------------------------------------------
# Lookdev & Material Intelligence rules (Tier 14 - §34)
# ---------------------------------------------------------------------------

_LOOKDEV_INTELLIGENCE_RULES = [
    "Prefer production-proven lookdev patterns - always call hou_mcp_lookdev_patterns before selecting materials.",
    "Match materials to environment - industrial_hangar uses weathered_concrete + industrial_metal, not polished_steel.",
    "Use renderer-aware profiles - call hou_mcp_renderer_profile to get correct material class before building any shader plan.",
    "Maintain environment consistency - all assets in a scene should share a lookdev pattern, not mix arbitrary materials.",
    "Preserve visual coherence - avoid conflicting material categories (e.g., polished_steel with weathered_concrete in the same hero zone).",
    "Generate assignment plans only - hou_mcp_material_assign produces transaction ops, never direct Houdini mutations.",
    "Use material recommendations before defaults - hou_mcp_material_recommend outranks any hardcoded material guess.",
    "Favor studio-approved lookdev standards - a lookdev pattern not in LookdevPatterns must be explicitly justified.",
    "Run lookdev review before scene realization - call hou_mcp_lookdev_review after planning materials, not after rendering.",
    "Review must be specific - 'material assigned' is NOT acceptable; review must state which materials were chosen and why.",
]


# ---------------------------------------------------------------------------
# Semantic Asset Catalog rules (Tier 12.7 - §35)
# ---------------------------------------------------------------------------

_SEMANTIC_CATALOG_RULES = [
    "Prefer semantic reasoning over raw tags - query by environment intent, not filename.",
    "Prefer local metadata before API calls - check manifest files and catalog before querying Megascans.",
    "Understand environment suitability - industrial_hangar assets are not interchangeable with sci_fi_corridor assets.",
    "Understand storytelling purpose - hero_object assets need cinematic placement; atmosphere_builder assets fill depth layers.",
    "Understand cinematic usage - depth_layer assets support visual depth; hero_focus assets must occupy the primary focal zone.",
    "Maintain deterministic ranking - same environment intent always returns the same ranked asset list.",
    "Preserve semantic relationships - use the knowledge graph to discover commonly_used_with and same_environment assets.",
    "Cache Megascans metadata aggressively - never re-fetch if catalog entry exists.",
    "Use query_intent() for natural language queries - 'Industrial Hangar Hero Machinery' resolves to environment + role + category filters.",
    "Review catalog quality before production - call hou_mcp_catalog_review after sync; production_ready requires score >= 0.7.",
]


# ---------------------------------------------------------------------------
# Semantic Vector Search & Asset Retrieval rules (Tier 12.8 - §36)
# ---------------------------------------------------------------------------

_SEMANTIC_RETRIEVAL_RULES = [
    "Prefer semantic meaning over keyword matching - use hou_mcp_asset_retrieval with intent text, not raw filenames.",
    "Prefer environment fit over raw similarity - an asset scoring 0.9 in wrong environment beats a 0.7 in the right one.",
    "Consider storytelling purpose - hero_object assets need cinematic placement; atmosphere_builder assets fill depth layers.",
    "Consider cinematic usage - depth_layer assets need background zones; hero_focus assets must be in the primary focal zone.",
    "Consider production memory - importance=primary assets rank higher than ambient; factor this into placement decisions.",
    "Preserve deterministic ranking - same intent text always returns same ranked asset list given same catalog state.",
    "Build the vector index before retrieval - call hou_mcp_vector_index (build_full) after catalog sync.",
    "Use hybrid ranking, not pure vector search - hou_mcp_hybrid_ranking combines 6 signals for production-aware results.",
    "Review retrieval quality - call hou_mcp_retrieval_review after building the index; production_ready requires score >= 0.7.",
    "Fall back gracefully - retrieval_pipeline falls back to catalog search when vector store is empty; never fails silently.",
]


# ---------------------------------------------------------------------------
# Online Asset Acquisition rules (Tier 12.9 - §37)
# ---------------------------------------------------------------------------

_ONLINE_ACQUISITION_RULES = [
    "Download only assets selected by semantic intelligence layers - never download blindly or in bulk.",
    "Prefer cache before acquisition - call hou_mcp_asset_fetch (ensure_available) to check cache before triggering any download.",
    "Prefer highest-ranked assets - acquisition pipeline calls vector retrieval first; only top-k results are fetched.",
    "Preserve provenance - every acquired asset must have a ProvenanceRecord with provider, checksum, local_path, and download_time.",
    "Validate integrity - always verify SHA-256 checksum after download; reject assets with mismatched checksums.",
    "Never duplicate assets - the cache manager deduplicates by (provider, asset_id); re-acquiring the same asset returns the cached path.",
    "Build project-local caches - use hou_mcp_asset_staging to copy acquired assets into the project staging directory.",
    "Use the download queue for bulk operations - enqueue via hou_mcp_download_queue, process via DownloadScheduler.",
    "Review acquisition quality - call hou_mcp_download_review after pipeline runs; production_ready requires score >= 0.70.",
    "Handle offline mode gracefully - all acquisition modules return safe defaults when VIBRANTE_MEGASCANS_TOKEN is unset.",
    "Canonical acquisition workflow: hou_mcp_asset_retrieval → hou_mcp_asset_fetch → hou_mcp_asset_staging → hou_mcp_download_review.",
    "CREDENTIAL CONFIGURATION — MANDATORY: When any acquisition tool returns configuration_required=True or how_to_fix, "
    "relay the how_to_fix text verbatim. NEVER substitute shell $env: commands. "
    "Credentials live in the 'env' array of ~/Documents/houdiniXX.Y/packages/vibrante_node.json — "
    "that is the ONLY correct location to tell the user to edit. "
    "The runtime reads this file automatically from the live Houdini session on every acquisition call.",
]


# ---------------------------------------------------------------------------
# Lighting Intelligence rules (Tier 15 - §38)
# ---------------------------------------------------------------------------

_LIGHTING_INTELLIGENCE_RULES = [
    "Lighting exists to support story - every light must have a narrative justification.",
    "Readability is more important than complexity - a readable scene beats a technically impressive one.",
    "Mood drives illumination decisions - infer mood from intent before building any lighting plan.",
    "Visual hierarchy must be preserved - hero subjects receive maximum rim and dedicated key targeting.",
    "Use production memory when available - pattern library captures proven setups; prefer it over generic defaults.",
    "Prefer deterministic planning - same intent always produces the same lighting plan.",
    "Generate plans, not renderer nodes - all lighting outputs are renderer-agnostic plan dicts.",
    "Never create Houdini lights directly - lighting nodes produce plans for downstream realization.",
    "Always review lighting quality - call hou_mcp_lighting_review after plan generation; production_ready requires score >= 0.70.",
    "Color temperature tells a story - warm keys suggest safety; cool keys suggest threat or technology.",
    "Contrast ratio controls emotional weight - high contrast for drama/danger; low contrast for clinical/hopeful.",
    "Volumetrics add narrative depth - use only when environment warrants it (hangar, corridor, abandoned, night exterior).",
    "Canonical lighting workflow: hou_mcp_lighting_strategy → hou_mcp_lighting_plan → hou_mcp_lighting_review.",
]


# ---------------------------------------------------------------------------
# Block generators
# ---------------------------------------------------------------------------

def get_execution_rules_block() -> str:
    rules = "\n".join(f"- {r}" for r in EXECUTION_RULES)
    return f"Execution Rules:\n{rules}"


def get_recommended_flow_block() -> str:
    steps = "\n".join(RECOMMENDED_EXECUTION_FLOW)
    return f"Preferred Execution Flow:\n{steps}"


def get_cinematic_orchestration_block() -> str:
    """Cinematic-specific orchestration guidance block."""
    rules = "\n".join(f"- {r}" for r in _CINEMATIC_RULES)
    return f"""\
Cinematic Orchestration Rules:
{rules}

{_CINEMATIC_GOOD_PATTERNS}
{_CINEMATIC_BAD_PATTERNS}"""


def get_scene_planning_block() -> str:
    """Semantic scene assembly guidance block (Tier 2)."""
    rules = "\n".join(f"- {r}" for r in _SCENE_PLANNING_RULES)
    return f"Semantic Scene Planning Rules:\n{rules}"


def get_scene_realization_block() -> str:
    """Deterministic scene realization guidance block (Tier 3)."""
    rules = "\n".join(f"- {r}" for r in _SCENE_REALIZATION_RULES)
    return f"Scene Realization Rules:\n{rules}"


def get_cinematic_scene_layer_block() -> str:
    """Cinematic Scene Layer guidance block (Tier 4 - §23)."""
    rules = "\n".join(f"- {r}" for r in _CINEMATIC_SCENE_LAYER_RULES)
    return f"Cinematic Scene Layer Rules (lighting, camera, atmosphere, review):\n{rules}"


def get_production_knowledge_block() -> str:
    """Production Knowledge System guidance block (Tier 5 - §24)."""
    rules = "\n".join(f"- {r}" for r in _PRODUCTION_KNOWLEDGE_RULES)
    return f"Production Knowledge Rules:\n{rules}"


def get_environment_construction_block() -> str:
    """Environment construction guidance block (Tier 9 - §29)."""
    rules = "\n".join(f"- {r}" for r in _ENVIRONMENT_CONSTRUCTION_RULES)
    return f"Environment Construction Rules:\n{rules}"


def get_workflow_pack_block() -> str:
    """Workflow Pack guidance block (Tier 10 - §30)."""
    rules = "\n".join(f"- {r}" for r in _WORKFLOW_PACK_RULES)
    return f"Workflow Pack Rules:\n{rules}"


def get_studio_knowledge_block() -> str:
    """Studio Knowledge guidance block (Tier 11 - §31)."""
    rules = "\n".join(f"- {r}" for r in _STUDIO_KNOWLEDGE_RULES)
    return f"Studio Knowledge Rules:\n{rules}"


def get_asset_ecosystem_block() -> str:
    """Asset Ecosystem Rules injected into LLM system prompt (Tier 12 - §32)."""
    rules = "\n".join(f"{i}. {r}" for i, r in enumerate(_ASSET_ECOSYSTEM_RULES, 1))
    return f"## Asset Ecosystem Rules\n{rules}"


def get_asset_realization_block() -> str:
    """Asset Realization & DCC Integration rules (Tier 13 - §33)."""
    rules = "\n".join(f"{i}. {r}" for i, r in enumerate(_ASSET_REALIZATION_RULES, 1))
    return f"## Asset Realization Rules\n{rules}"


def get_lookdev_intelligence_block() -> str:
    """Lookdev & Material Intelligence rules (Tier 14 - §34)."""
    rules = "\n".join(f"{i}. {r}" for i, r in enumerate(_LOOKDEV_INTELLIGENCE_RULES, 1))
    return f"## Lookdev Intelligence Rules\n{rules}"


def get_semantic_catalog_block() -> str:
    """Semantic Asset Catalog rules (Tier 12.7 - §35)."""
    rules = "\n".join(f"{i}. {r}" for i, r in enumerate(_SEMANTIC_CATALOG_RULES, 1))
    return f"## Semantic Asset Catalog Rules\n{rules}"


def get_semantic_retrieval_block() -> str:
    """Semantic Vector Search & Asset Retrieval rules (Tier 12.8 - §36)."""
    rules = "\n".join(f"{i}. {r}" for i, r in enumerate(_SEMANTIC_RETRIEVAL_RULES, 1))
    return f"## Semantic Retrieval Rules\n{rules}"


def get_online_acquisition_block() -> str:
    """Online Asset Acquisition & Intelligent Asset Fetching rules (Tier 12.9 - §37)."""
    rules = "\n".join(f"{i}. {r}" for i, r in enumerate(_ONLINE_ACQUISITION_RULES, 1))
    return f"## Online Acquisition Rules\n{rules}"


def get_lighting_intelligence_block() -> str:
    """Lighting Intelligence & Cinematic Illumination rules (Tier 15 - §38)."""
    rules = "\n".join(f"{i}. {r}" for i, r in enumerate(_LIGHTING_INTELLIGENCE_RULES, 1))
    return f"## Lighting Intelligence Rules\n{rules}"


def get_tool_guide() -> str:
    return """\
Available MCP Tools:

RUNTIME:
  initialize_runtime_context        - read current scene + runtime state (call first)
  query_runtime_state               - live runtime metrics and status
  query_scene_context               - structured Houdini scene snapshot

KNOWLEDGE:
  query_capabilities                - enumerate what the runtime can do
  query_workflow_templates          - browse available workflow templates
  query_examples                    - get execution examples for an intent
  query_node_parameters             - list parameter names + values for a Houdini node

PLANNING:
  plan_scene                        - parse a natural-language intent → execution plan
  preview_execution                 - inspect operations + risk without executing
  validate_execution_plan           - structural + constraint validation pass

EXECUTION:
  execute_workflow_transaction      - run a validated plan via the transaction system
  review_execution                  - post-execution intent-match review

CONFIGURATION:
  check_vibrante_config             - CALL THIS when credentials or paths may be missing.
                                      Returns the exact file path to edit and how_to_fix text.
                                      Relay how_to_fix verbatim - NEVER substitute $env: commands.

SCENE BUILDING - USE THIS MCP TOOL FOR ANY "BUILD / CREATE / MAKE A ROOM / SCENE" INTENT:
  build_scene_from_assets           - REQUIRED FIRST STEP. This is an MCP tool, call it directly.
                                      Chains: intent → keywords → catalog → Megascans API download
                                      → extract ZIP → find mesh → import into Houdini.
                                      NEVER creates box/tube/sphere/grid primitives.
                                      Works for ANY environment: western, sci-fi, medieval, desert…
                                      Call this BEFORE plan_scene, BEFORE lights, BEFORE camera.

MANDATORY SCENE-BUILDING ORDER:
  1. build_scene_from_assets(intent=...)   ← geometry + real Megascans assets
       └─ Phase 0 (internal): EnvironmentShellBuilder — floor + walls + ceiling + anchors
          SHELL_RUNTIME_STATUS = PASS required before furniture placement proceeds.
          If SHELL_RUNTIME_STATUS = FAIL → ENVIRONMENT_NOT_READY → pipeline aborts layout.
  2. execute_workflow_transaction          ← atmosphere, VFX (if any)
  3. Lighting via execute_workflow_transaction (key, fill, rim)
  4. review_execution                      ← verify geometry + lighting achieved

  Lighting without geometry = INCOMPLETE. Never skip step 1.
  Do NOT use plan_scene for scene-building intents - it generates primitives.
  Do NOT use execute_workflow_transaction alone for geometry - it generates primitives.
  build_scene_from_assets is the ONLY path for environment construction.
  SHELL_RUNTIME_STATUS and END_TO_END_LAYOUT_STATUS are both returned by build_scene_from_assets.
"""


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def get_system_prompt() -> str:
    """Full operational system prompt.

    Inject this into the LLM system message on session start to establish
    Vibrante Runtime awareness.  Idempotent - safe to call multiple times.
    """
    return f"""\
You are operating inside {RUNTIME_NAME}.

{RUNTIME_NAME} is an {RUNTIME_TYPE}.

{get_execution_rules_block()}

{get_recommended_flow_block()}

{get_scene_planning_block()}

{get_scene_realization_block()}

{get_cinematic_scene_layer_block()}

{get_production_knowledge_block()}

{get_environment_construction_block()}

{get_cinematic_orchestration_block()}

{get_workflow_pack_block()}

{get_studio_knowledge_block()}

{get_asset_ecosystem_block()}

{get_asset_realization_block()}

{get_lookdev_intelligence_block()}

{get_semantic_catalog_block()}

{get_semantic_retrieval_block()}

{get_online_acquisition_block()}

{get_lighting_intelligence_block()}

{get_tool_guide()}

IMPORTANT:
- Always call initialize_runtime_context before issuing any execution commands.
- Always call plan_scene to decompose large cinematic goals before executing.
- Always call preview_execution before execute_workflow_transaction.
- Never attempt raw Houdini API calls - they are not exposed.
- Never skip validation - the runtime enforces it automatically.
- After execution, always call review_execution to verify the intent was achieved.
- review_execution must return specific artistic critique, not generic success messages.
- Use hou_mcp_knowledge_recommendation before any scene setup - studio knowledge outranks generic defaults.
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
        lines.append(f"  frame:            {scene.get('frame', 1)}  range {fr[0]}-{fr[1]}")

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

def get_contextual_prompt(
    scene_context: Optional[Dict[str, Any]] = None,
    include_cinematic: bool = False,
) -> str:
    """Shorter mid-session context refresh - rules + optional current scene.

    Args:
        scene_context:     Optional structured scene dict.
        include_cinematic: If True, include cinematic orchestration rules block.
    """
    blocks = [get_execution_rules_block()]
    if include_cinematic:
        blocks.append(get_cinematic_orchestration_block())
    if scene_context:
        blocks.append(get_scene_context_block(scene_context))
    return "\n\n".join(blocks)
