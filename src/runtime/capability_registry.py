"""
Capability Registry (Tier 2.75)
================================
Dynamic tracking of what the runtime can currently do. Capabilities are
registered at module import time from known sources (houdini_runtime ops,
known runtime services) and updated at runtime as MCP servers connect or
new DCC integrations activate.

This is foundational for future AI planners / tool-discovery flows: any
component that needs to emit an intent can first check whether the required
capability exists before constructing an execution plan.

Capability types (string constants):
    "houdini_op"         — a named op type in houdini_runtime.SUPPORTED_OPS
    "runtime_service"    — an active src/runtime service (transaction_manager, etc.)
    "semantic_operation" — a named semantic operation registered in semantic_registry
    "mcp_server"         — a connected MCP server registered in mcp_runtime
    "dcc_integration"    — an active DCC bridge (houdini, maya, blender)
    "renderer"           — a known renderer type (karma, mantra, arnold, etc.)

Public API:
    get_capability_registry() -> CapabilityRegistry   (singleton)
    reset_capability_registry_for_tests()

    CapabilityRegistry.register_capability(type, id, metadata)
    CapabilityRegistry.deregister_capability(id)
    CapabilityRegistry.query_capabilities(type=None) -> list[dict]
    CapabilityRegistry.supports(capability_id) -> bool
    CapabilityRegistry.stats() -> dict
"""

import threading
from typing import Any, Dict, List, Optional

CAPABILITY_TYPES = frozenset({
    "houdini_op",
    "runtime_service",
    "semantic_operation",
    "mcp_server",
    "dcc_integration",
    "renderer",
    # Tier 4 additions
    "remote_capability",   # capability from a remote/federated runtime
    "mcp_tool",            # an MCP tool exposed by the server runtime
})

_BUILTIN_CAPABILITIES: List[Dict[str, Any]] = [
    # Houdini bridge ops -------------------------------------------------------
    {"type": "houdini_op", "id": "create_node",       "metadata": {"description": "Create a Houdini node"}},
    {"type": "houdini_op", "id": "set_parms",         "metadata": {"description": "Set multiple parameters"}},
    {"type": "houdini_op", "id": "connect_nodes",     "metadata": {"description": "Wire two nodes"}},
    {"type": "houdini_op", "id": "delete_node",       "metadata": {"description": "Delete a node (irreversible in Tier 2)"}},
    {"type": "houdini_op", "id": "set_display_flag",  "metadata": {"description": "Toggle display flag"}},
    {"type": "houdini_op", "id": "set_render_flag",   "metadata": {"description": "Toggle render flag"}},
    {"type": "houdini_op", "id": "cook_node",         "metadata": {"description": "Force-cook a node"}},
    {"type": "houdini_op", "id": "layout_children",   "metadata": {"description": "Auto-layout child nodes"}},
    {"type": "houdini_op", "id": "build_node_chain",  "metadata": {"description": "Create a multi-node network from spec"}},
    # Runtime services ---------------------------------------------------------
    {"type": "runtime_service", "id": "transaction_manager", "metadata": {"description": "Transactional execution with rollback"}},
    {"type": "runtime_service", "id": "scene_cache",         "metadata": {"description": "TTL cache + dirty tracking"}},
    {"type": "runtime_service", "id": "dependency_graph",    "metadata": {"description": "Inter-node dependency BFS graph"}},
    {"type": "runtime_service", "id": "validation_engine",   "metadata": {"description": "Pre-execution op validation"}},
    {"type": "runtime_service", "id": "audit_store",         "metadata": {"description": "JSONL audit trail"}},
    {"type": "runtime_service", "id": "execution_scheduler", "metadata": {"description": "Serialised FIFO mutation queue"}},
    {"type": "runtime_service", "id": "mcp_runtime",         "metadata": {"description": "Long-lived MCP client session registry"}},
    # DCC integration ----------------------------------------------------------
    {"type": "dcc_integration", "id": "houdini", "metadata": {"description": "Houdini TCP bridge (hou_bridge.py)"}},
    # Known renderers ----------------------------------------------------------
    {"type": "renderer", "id": "karma",           "metadata": {"rop_type": "karma"}},
    {"type": "renderer", "id": "mantra",          "metadata": {"rop_type": "ifd"}},
    {"type": "renderer", "id": "arnold",          "metadata": {"rop_type": "arnold"}},
    {"type": "renderer", "id": "redshift",        "metadata": {"rop_type": "redshift_rop"}},
    {"type": "renderer", "id": "vray",            "metadata": {"rop_type": "vray_renderer"}},
    {"type": "renderer", "id": "opengl",          "metadata": {"rop_type": "opengl"}},
    {"type": "renderer", "id": "usd_render",      "metadata": {"rop_type": "usdrender_rop"}},
    # Semantic scene assembly (Tier 2) -----------------------------------------
    {
        "type": "semantic_operation",
        "id":   "semantic_scene_planning",
        "metadata": {
            "description": (
                "Generate cinematically coherent scene layout plans from environment "
                "rules and asset lists — planning only, no Houdini mutation."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "cinematic_composition_analysis",
        "metadata": {
            "description": (
                "Analyse visual balance, focus distribution, and scene readability "
                "using deterministic cinematic composition heuristics."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "production_asset_staging",
        "metadata": {
            "description": (
                "Build transaction-safe asset staging plans with import ordering, "
                "compatibility validation, and coherence checks."
            ),
        },
    },
    # Production Knowledge System (§24) ----------------------------------------
    {
        "type": "semantic_operation",
        "id":   "production_memory",
        "metadata": {
            "description": (
                "Append-only store of production experience: successful scenes, "
                "failed scenes, pattern usage, and review outcomes."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "pattern_recommendation",
        "metadata": {
            "description": (
                "Rank and recommend reusable production patterns (lighting, camera, "
                "atmosphere, composition, scene) by success history."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "scene_recommendation",
        "metadata": {
            "description": (
                "Recommend production-proven lighting, camera, atmosphere, and assets "
                "for a given scene type using memory + patterns + knowledge graph."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_knowledge",
        "metadata": {
            "description": (
                "Semantic graph of asset relationships: commonly_used_with, "
                "same_environment, same_style, same_template, successful_pairing."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "production_scoring",
        "metadata": {
            "description": (
                "Deterministic multi-dimension production quality scoring: readability, "
                "composition, lighting, camera, atmosphere — no AI, fully explainable."
            ),
        },
    },
    # Semantic Scene Intent Runtime (§26) ----------------------------------------
    {
        "type": "semantic_operation",
        "id":   "scene_intent_extract",
        "metadata": {
            "description": (
                "Extract a structured SceneIntent from a natural language prompt. "
                "Deterministic keyword extraction with optional LLM enhancement."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "scene_intent_validate",
        "metadata": {
            "description": (
                "Validate and normalize a SceneIntent: checks missing fields, "
                "invalid enum values, and logical contradictions."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "scene_intent_enrich",
        "metadata": {
            "description": (
                "Deterministically enrich a SceneIntent with implied requirements. "
                "Every enrichment records reason, source, and confidence."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "scene_intent_recommend",
        "metadata": {
            "description": (
                "Generate production-proven recommendations for a SceneIntent "
                "from ProductionMemory, PatternLibrary, and AssetKnowledgeGraph."
            ),
        },
    },
    # Scene Planning Runtime (§27) ------------------------------------------
    {
        "type": "semantic_operation",
        "id":   "scene_plan_create",
        "metadata": {
            "description": (
                "Transform a validated SceneIntent into a deterministic ScenePlan: "
                "zones, composition rules, camera targets, and asset queries. "
                "Planning only — no Houdini mutation."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "scene_plan_validate",
        "metadata": {
            "description": (
                "Validate a ScenePlan for structural consistency: zone completeness, "
                "camera targets, composition rules, and asset query validity."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "scene_plan_recommend",
        "metadata": {
            "description": (
                "Enrich a ScenePlan with production-proven recommendations "
                "from ProductionMemory, PatternLibrary, and AssetKnowledgeGraph."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "scene_asset_query_generate",
        "metadata": {
            "description": (
                "Generate structured asset search queries from a ScenePlan or "
                "SceneIntent — category, tags, zone, quantity, priority — "
                "ready for any asset provider without API calls."
            ),
        },
    },
    # Asset Intelligence Runtime (§28) ----------------------------------------
    {
        "type": "semantic_operation",
        "id":   "asset_discover",
        "metadata": {
            "description": (
                "Query registered asset providers (Sketchfab, Polyhaven, local) "
                "for a set of AssetQuery requests.  Returns merged, deduplicated "
                "AssetQueryResults.  No downloads.  No Houdini mutation."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_validate",
        "metadata": {
            "description": (
                "Validate AssetDescriptors for category, format, scale, and style "
                "compatibility before ranking.  Returns valid / rejected sets with "
                "named rejection reasons."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_rank",
        "metadata": {
            "description": (
                "Score and rank validated assets using six deterministic factors: "
                "intent match, plan match, pattern match, knowledge graph, "
                "production history, and provider quality.  Fully explainable."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_recommend",
        "metadata": {
            "description": (
                "Full Asset Intelligence pipeline: Discovery → Validation → Ranking "
                "→ Recommendations.  Priority: Memory 0.95, Patterns 0.80, "
                "Graph 0.65, Provider 0.50.  Provider-agnostic output."
            ),
        },
    },
    # Semantic Asset Assembly (§29) -------------------------------------------
    {
        "type": "semantic_operation",
        "id":   "semantic_environment_construction",
        "metadata": {
            "description": (
                "Build a zone-structured EnvironmentPlan from an environment name "
                "and recommended assets.  Deterministic zone assignment with "
                "category-affinity rules for all 5 canonical environments."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_placement",
        "metadata": {
            "description": (
                "Generate deterministic world-space placement plans: positions, "
                "rotations, and scales for each asset.  Slot data from "
                "PlacementTemplates — no randomness, no noise."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "scene_population",
        "metadata": {
            "description": (
                "Assign assets to semantic population groups (hero, support, detail, "
                "atmosphere, storytelling) and validate production balance."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "storytelling_layout",
        "metadata": {
            "description": (
                "Generate visual storytelling structure: hero beat, support beats, "
                "viewer path, and visual flow direction from environment narrative rules."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "environment_review",
        "metadata": {
            "description": (
                "Evaluate environment quality across layout, population, readability, "
                "and storytelling dimensions.  Returns grade, score, specific findings, "
                "and recommendations.  production_ready requires score >= 0.6."
            ),
        },
    },
    # Workflow Packs & Production Blueprints (§30) ----------------------------
    {
        "type": "semantic_operation",
        "id":   "workflow_pack_execution",
        "metadata": {
            "description": (
                "Execute a reusable WorkflowPack through the transaction system.  "
                "Encapsulates environment, asset, placement, lighting, camera, "
                "atmosphere, and review strategies in one deterministic blueprint."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "workflow_recommendation",
        "metadata": {
            "description": (
                "Recommend a WorkflowPack from a natural language intent using "
                "ProductionMemory (0.95) → PatternLibrary (0.80) → StudioKnowledge "
                "(0.65) → default (0.50) priority chain.  Advisory only."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "workflow_review",
        "metadata": {
            "description": (
                "Evaluate workflow execution quality across environment, cinematic, "
                "production, and execution dimensions.  Returns grade, score, "
                "production_ready, and specific named findings."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "workflow_blueprint",
        "metadata": {
            "description": (
                "Build ordered, phase-resolved workflow execution plans from "
                "WorkflowPack definitions.  Phases: environment, population, "
                "placement, lighting, camera, atmosphere, review."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "workflow_statistics",
        "metadata": {
            "description": (
                "Track and query workflow execution statistics: success rates, "
                "average scores, rollback rates, and top-performing packs."
            ),
        },
    },
    # Cross-Project Learning & Studio Knowledge (§31) -------------------------
    {
        "type": "semantic_operation",
        "id":   "cross_project_learning",
        "metadata": {
            "description": (
                "Extract reusable production intelligence from cross-project records: "
                "best workflows, best lighting/camera/atmosphere, successful patterns, "
                "and recurring failure patterns.  Deterministic — no AI."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "studio_knowledge",
        "metadata": {
            "description": (
                "Aggregate cross-project success/failure/pattern/review records into "
                "studio-wide production knowledge.  JSONL-backed, append-only."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "production_benchmark",
        "metadata": {
            "description": (
                "Compare a project's production score against the studio historical "
                "average.  Returns performance classification, percentile estimate, "
                "and improvement recommendations.  Advisory only."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "review_analytics",
        "metadata": {
            "description": (
                "Analyse review outcomes across projects: common failures, common "
                "successes, pass rate, trend direction, and actionable recommendations."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "knowledge_recommendation",
        "metadata": {
            "description": (
                "Recommend studio-approved production strategies using the studio "
                "knowledge priority chain: Standards (0.90) → Cross-Project (0.85) "
                "→ Memory (0.80) → Patterns (0.70) → Defaults (0.50)."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "studio_standards",
        "metadata": {
            "description": (
                "Manage studio-approved production conventions: approved lighting "
                "styles, camera modes, atmosphere types, workflow packs, hero zone "
                "limits, naming conventions, and review thresholds."
            ),
        },
    },
    # Asset Ecosystem Expansion (§32) -----------------------------------------
    {
        "type": "semantic_operation",
        "id":   "asset_provider_management",
        "metadata": {
            "description": (
                "Query and manage multiple asset providers via the unified ProviderManager. "
                "Supports multi-provider search, result merging, and deduplication."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_download",
        "metadata": {
            "description": (
                "Queue, track, and manage asset downloads with task lifecycle, "
                "simulated completion, and integrity validation."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_storage",
        "metadata": {
            "description": (
                "Register, query, and manage local asset storage and cache. "
                "Tracks provider + asset_id keys in a thread-safe in-memory registry."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_sync",
        "metadata": {
            "description": (
                "Synchronize local and external asset libraries. Compares provider "
                "assets against local storage, registers new assets, returns sync reports."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_metadata_enrichment",
        "metadata": {
            "description": (
                "Enrich asset metadata with deterministically inferred environments, "
                "styles, categories, and usage hints using keyword matching tables."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_provenance_tracking",
        "metadata": {
            "description": (
                "Track asset origin, download history, and usage events across sessions. "
                "Append-only in-memory event log with per-asset provenance reports."
            ),
        },
    },
    # Asset Realization & DCC Integration (§33) --------------------------------
    {
        "type": "semantic_operation",
        "id":   "asset_realization",
        "metadata": {
            "description": (
                "Full asset realization pipeline from AssetDescriptor to transaction "
                "operations: import → convert → normalize → resolve dependencies → "
                "map materials → build USD → instance → generate scene ops."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_import",
        "metadata": {
            "description": (
                "Import assets into the realization pipeline with provenance tracking. "
                "Records source_type, format, provider, and metadata. No file I/O."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_conversion",
        "metadata": {
            "description": (
                "Convert asset formats to USD-compatible representations using the "
                "CONVERSION_MATRIX. No real file conversion — generates ConversionResult "
                "descriptors for downstream realization."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_normalization",
        "metadata": {
            "description": (
                "Normalize asset scale, orientation, units, and pivots to production "
                "standards. Deterministic — same input always produces the same output."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_dependency_resolution",
        "metadata": {
            "description": (
                "Resolve asset textures, materials, and external references from asset "
                "metadata. Identifies missing dependencies before realization."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "usd_asset_generation",
        "metadata": {
            "description": (
                "Generate USD-ready asset hierarchy and metadata representations. "
                "No USD SDK required — produces descriptive data structures for "
                "downstream scene realization and transaction op generation."
            ),
        },
    },
    # Fab / Quixel Asset Acquisition Service (§35) ----------------------------
    {
        "type": "semantic_operation",
        "id":   "fab_library_scan",
        "metadata": {
            "description": (
                "Scan a local Fab asset library directory, extract asset metadata "
                "from JSON manifests, and return AssetDescriptor-compatible records. "
                "No network calls. Reads VIBRANTE_FAB_LIBRARY env var."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "megascans_library_scan",
        "metadata": {
            "description": (
                "Scan a local Megascans / Fab Bridge library, extracting asset "
                "metadata for 3D, surface, decal, imperfection, atlas, and 3dplant "
                "types. No network calls. Reads VIBRANTE_MEGASCANS_LIBRARY env var."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_acquisition",
        "metadata": {
            "description": (
                "Orchestrate local asset acquisition: locate assets in Fab / Megascans "
                "libraries, register discovered assets in the DownloadRegistry and "
                "LibraryIndex, and make them available to the runtime pipeline."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "library_index",
        "metadata": {
            "description": (
                "Build and query a searchable in-memory / persisted index of all "
                "locally acquired Fab and Megascans assets. Supports full-text search "
                "by name, category, tags, and provider."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "library_watch",
        "metadata": {
            "description": (
                "Detect newly downloaded assets by comparing directory snapshots "
                "across watched library paths. Auto-registers new files in the "
                "DownloadRegistry. No real-time OS events — snapshot comparison only."
            ),
        },
    },
    # Semantic Asset Catalog & Megascans Knowledge Layer (§35) ----------------
    {
        "type": "semantic_operation",
        "id":   "semantic_asset_catalog",
        "metadata": {
            "description": (
                "Persistent semantic database of enriched asset records with "
                "environment, role, lookdev, storytelling, and cinematic metadata. "
                "Supports environment-driven and intent-driven asset queries."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "semantic_asset_search",
        "metadata": {
            "description": (
                "Query the semantic catalog by environment, production role, "
                "lookdev style, storytelling role, and cinematic usage — "
                "instead of filename or tag matching."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "megascans_metadata_sync",
        "metadata": {
            "description": (
                "Sync Megascans / Fab asset metadata into the semantic catalog. "
                "Local manifests take priority over API calls. "
                "Offline-safe — operates without a token."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "environment_asset_mapping",
        "metadata": {
            "description": (
                "Map assets to canonical production environments "
                "(industrial_hangar, robotics_lab, control_room, sci_fi_corridor, "
                "abandoned_factory) using deterministic keyword inference."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_storytelling_mapping",
        "metadata": {
            "description": (
                "Classify assets into storytelling roles "
                "(hero_object, context_builder, scale_reference, visual_anchor, "
                "atmosphere_builder) for narrative-aware scene construction."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_knowledge_graph",
        "metadata": {
            "description": (
                "Build and query semantic relationships between catalog assets: "
                "commonly_used_with, same_environment, same_style, same_template, "
                "successful_pairing. Used for knowledge-graph-driven asset expansion."
            ),
        },
    },
    # Semantic Vector Search & Asset Retrieval (§36) -------------------------
    {
        "type": "semantic_operation",
        "id":   "semantic_vector_search",
        "metadata": {
            "description": (
                "Nearest-neighbor asset retrieval using 128-dim deterministic "
                "embeddings (no external ML deps) or sentence-transformers upgrade. "
                "Pure-Python vector store with optional FAISS acceleration."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_retrieval",
        "metadata": {
            "description": (
                "Full semantic retrieval pipeline: intent text → ParsedIntent → "
                "embedding → vector search → hybrid ranking → production-ready "
                "asset list. Falls back to catalog search when vector store is empty."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "intent_embedding",
        "metadata": {
            "description": (
                "Convert structured production intent (environment, role, storytelling, "
                "lookdev, cinematic) into embedding vectors for semantic similarity search."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "hybrid_asset_ranking",
        "metadata": {
            "description": (
                "Combine vector similarity (40%), environment fit (20%), storytelling "
                "match (15%), lookdev match (10%), knowledge graph (10%), and production "
                "memory (5%) into a single deterministic production score."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "vector_index_management",
        "metadata": {
            "description": (
                "Build, update, and rebuild the vector index from the semantic catalog. "
                "Supports incremental updates (new assets only) and full rebuilds."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "retrieval_review",
        "metadata": {
            "description": (
                "Evaluate semantic retrieval quality: precision, semantic relevance, "
                "environment accuracy, and role accuracy. production_ready requires "
                "score >= 0.7."
            ),
        },
    },
    # Lookdev & Material Intelligence (§34) -----------------------------------
    {
        "type": "semantic_operation",
        "id":   "material_intelligence",
        "metadata": {
            "description": (
                "Full lookdev pipeline: semantic material analysis → recommendation → "
                "assignment plan → renderer profile mapping → quality review. "
                "Advisory only — no direct DCC mutations."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "lookdev_patterns",
        "metadata": {
            "description": (
                "Store and retrieve reusable lookdev recipes: environment-matched "
                "material sets proven in production. Ranked by environment and "
                "material affinity — deterministic, no AI."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "material_recommendation",
        "metadata": {
            "description": (
                "Recommend production-proven materials for assets using priority chain: "
                "Lookdev Patterns (0.85) → Material Knowledge (0.70) → Renderer "
                "Default (0.50). Provider-agnostic output."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "material_assignment",
        "metadata": {
            "description": (
                "Generate semantic material assignment plans as transaction ops — "
                "never direct Houdini mutations. Supports per-asset, environment-wide, "
                "and full scene assignment strategies."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "lookdev_review",
        "metadata": {
            "description": (
                "Evaluate lookdev quality across 4 dimensions: material consistency "
                "(30%), environment coherence (25%), renderer compatibility (25%), "
                "visual quality (20%). production_ready requires score >= 0.70."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "renderer_profiles",
        "metadata": {
            "description": (
                "Renderer-aware material class mappings for Arnold (standard_surface), "
                "Karma (mtlxstandard_surface), and USD Preview Surface. "
                "Validates renderer support before mapping."
            ),
        },
    },
    # -----------------------------------------------------------------------
    # Tier 12.9 — Online Asset Acquisition & Intelligent Asset Fetching
    # -----------------------------------------------------------------------
    {
        "type": "semantic_operation",
        "id":   "online_asset_acquisition",
        "metadata": {
            "description": (
                "Full intelligent acquisition pipeline: intent → semantic retrieval → "
                "ranked asset selection → cache-first fetch → project staging. "
                "Never downloads blindly — only acquires assets selected by the semantic layers."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_fetching",
        "metadata": {
            "description": (
                "Cache-first asset fetcher: checks local cache → Tier 12.5 registry → "
                "Megascans API download. Returns local path + provenance record. "
                "Requires VIBRANTE_MEGASCANS_TOKEN for live downloads."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "download_management",
        "metadata": {
            "description": (
                "Persistent download queue + rate-limited scheduler. "
                "Deterministic ordering: priority desc, enqueue_time asc. "
                "Supports pause, resume, cancel, and retry."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_caching",
        "metadata": {
            "description": (
                "Local asset cache with deduplication by SHA-256 checksum and version tracking. "
                "Storage root: VIBRANTE_ASSET_CACHE. "
                "Persistent JSON index survives restarts."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "project_asset_staging",
        "metadata": {
            "description": (
                "Project-local asset sets staged from the central cache. "
                "Layout: {VIBRANTE_PROJECT_STAGING}/{project_id}/assets/{provider}/{asset_id}/. "
                "Supports per-environment and full-project build."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_provenance_tracking",
        "metadata": {
            "description": (
                "Append-only provenance log tracking provider, asset_id, download_time, "
                "version, checksum, and local_path for every acquired asset. "
                "Supports SHA-256 integrity verification."
            ),
        },
    },
    # -----------------------------------------------------------------------
    # Tier 15 — Lighting Intelligence & Cinematic Illumination
    # -----------------------------------------------------------------------
    {
        "type": "semantic_operation",
        "id":   "lighting_intelligence",
        "metadata": {
            "description": (
                "Full cinematic lighting intelligence pipeline: intent → story analysis → "
                "environment mapping → mood inference → color strategy → exposure → "
                "lighting plan + 6-dimension quality review. "
                "Planning only — never creates Houdini lights."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "lighting_strategy",
        "metadata": {
            "description": (
                "Generates holistic lighting strategies from environment, mood, lookdev, and story intent. "
                "Integrates environment mapper, mood engine, color engine, and pattern library. "
                "Outputs: key/fill/rim concepts, color temperature, contrast, volumetrics flag, EV target."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "lighting_planning",
        "metadata": {
            "description": (
                "Builds renderer-agnostic lighting plans: key light, fill light, rim light, "
                "practicals, volumetrics settings, color strategy, and exposure. "
                "Never creates Houdini nodes — produces plan dicts for downstream execution."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "lighting_review",
        "metadata": {
            "description": (
                "6-dimension lighting quality review: readability (20%), mood accuracy (20%), "
                "story support (20%), visual hierarchy (15%), color harmony (15%), exposure quality (10%). "
                "production_ready requires overall_score >= 0.70 and no blocking findings."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "lighting_readability",
        "metadata": {
            "description": (
                "Evaluates visual clarity: subject visibility (30%), silhouette quality (25%), "
                "foreground separation (20%), background separation (15%), contrast balance (10%). "
                "Returns score, findings, and actionable adjustment recommendations."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "lighting_recommendation",
        "metadata": {
            "description": (
                "Recommends production-proven lighting setups from pattern library and strategy engine. "
                "Priority chain: pattern match → strategy derivation. "
                "Returns LightingRecommendation with confidence, rationale, and adjustments."
            ),
        },
    },
    # -----------------------------------------------------------------------
    # §39 — Environment Expansion Pack
    # -----------------------------------------------------------------------
    {
        "type": "semantic_operation",
        "id":   "environment_registry",
        "metadata": {
            "description": (
                "Central registry of all 55 production environments across 9 categories "
                "(industrial, scientific, military, sci-fi, urban, interior, nature, fantasy, "
                "post-apocalyptic). Each environment has keywords, asset affinities, "
                "storytelling tags, lookdev tags, lighting tags, and camera tags."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "environment_expansion",
        "metadata": {
            "description": (
                "Full expansion of environment awareness from 5 canonical environments to 55 "
                "production-scale environments. Automatically integrates with asset mapping, "
                "intent parsing, lighting intelligence, placement templates, storytelling layout, "
                "workflow packs, and semantic retrieval."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "environment_statistics",
        "metadata": {
            "description": (
                "Track and query environment usage statistics: usage_count, success_rate, "
                "review_average, asset_count, and lighting_pattern_usage per environment. "
                "In-memory, capped at 2000 records."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "environment_recommendation",
        "metadata": {
            "description": (
                "Recommend the best-matching environment for a scene intent from the 55 built-in "
                "environments using keyword inference + category affinity scoring. "
                "Returns ranked environment list with confidence scores."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "environment_workflow_pack",
        "metadata": {
            "description": (
                "Retrieve or execute a production workflow pack for any of the 55 environments. "
                "13 built-in packs covering: industrial_hangar, robotics_lab, control_room, "
                "sci_fi_corridor, abandoned_factory, western_room, space_station, research_lab, "
                "forest, city_street, castle_hall, military_base, survival_camp."
            ),
        },
    },
    # -----------------------------------------------------------------------
    # Tier 9.4 — Real Asset Spatial Intelligence
    # -----------------------------------------------------------------------
    {
        "type": "semantic_operation",
        "id":   "spatial_metadata",
        "metadata": {
            "description": (
                "Extract or estimate bounding box, footprint area, placement radius, "
                "world scale, unit system, and placement type for any production asset. "
                "Priority chain: explicit fields → placement-type defaults → category defaults. "
                "All dimensions in meters. No file I/O."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "collision_detection",
        "metadata": {
            "description": (
                "AABB (Axis-Aligned Bounding Box) collision detection for placed assets. "
                "Detects overlapping assets and reports penetration depth per axis. "
                "collision_count > 0 is a hard block on production_ready."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "layout_optimization",
        "metadata": {
            "description": (
                "Find valid, collision-free world-space positions for production assets "
                "using a deterministic expanding-grid search (radii × angles). "
                "Resolves both AABB collisions and minimum-clearance violations. "
                "Same inputs always produce the same output."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "semantic_placement",
        "metadata": {
            "description": (
                "Semantic zone/anchor placement rules for 16 placement types. "
                "Examples: table is an anchor supporting chairs/lanterns; "
                "bucket prefers service_area or wall zones; machine requires hero_zone "
                "or midground with 2 m clearance radius. "
                "Evaluates per-asset zone compatibility and compliance score."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "clearance_validation",
        "metadata": {
            "description": (
                "Enforce minimum edge-to-edge separation distances between asset "
                "placement types. Key rules: chair↔chair 0.4 m, machine↔machine 2.0 m, "
                "vehicle↔vehicle 2.5 m, machine↔wall 1.0 m. "
                "Default 0.3 m between any unlisted pair."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "spatial_review",
        "metadata": {
            "description": (
                "5-dimension spatial quality evaluation: "
                "collision (0.35) + clearance (0.25) + semantic zone (0.20) + walkability (0.20). "
                "collision_count > 0 → production_ready = False (hard rule). "
                "production_ready requires overall_score >= 0.70 and no collisions."
            ),
        },
    },
    # Scale-Aware Spatial Placement (§42) -------------------------------------
    {
        "type": "semantic_operation",
        "id":   "unit_normalization",
        "metadata": {
            "description": (
                "Convert asset dimensions from any source unit (cm, mm, m, inch, ft) "
                "to meters before placement. Fixes the root cause of Megascans/Fab assets "
                "imported in centimeter space being placed with meter-space offsets. "
                "Includes heuristic detection: bbox values > 10 in any dimension → assume cm."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_scale_classification",
        "metadata": {
            "description": (
                "Classify assets into physical scale classes: tiny (<0.15 m), "
                "small (<0.50 m), medium (<1.50 m), large (<4.00 m), structural (>=4.00 m "
                "OR placement_type in {wall, column, beam, platform, crane, terrain} "
                "OR category in {structure, architectural, terrain}). "
                "Scale class drives spacing, zone assignment, and structural routing."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "footprint_calculation",
        "metadata": {
            "description": (
                "Calculate real floor footprint (bbox_x × bbox_z, m²) and clearance "
                "radius (max(bbox_x, bbox_z) / 2) for each asset. Used by "
                "LayoutSpacingEngine to compute physically correct gap distances."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "scale_aware_layout_spacing",
        "metadata": {
            "description": (
                "Replace fixed index×3 m slot spacing with dimension-aware spacing: "
                "gap = radius_a + clearance_margin + radius_b. Supports linear rows, "
                "anchor clusters (chairs around table), and overflow positions. "
                "Clearance margin varies by scale class pair (tiny↔tiny=0.05 m to large↔large=0.35 m)."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "role_based_placement",
        "metadata": {
            "description": (
                "Assign semantic roles (seating, furniture_anchor, decoration, structure, "
                "architectural, electronic, machinery, vegetation, terrain, prop) and "
                "placement modes (around_anchor, near_wall, corner, wall_only, "
                "route_to_structure, hero_center) to assets. "
                "Structural assets (beam, wall, column) are routed to EnvironmentStructureBuilder "
                "instead of the furniture placement pipeline."
            ),
        },
    },
    # Structural Environment Assembly (§41) ------------------------------------
    {
        "type": "semantic_operation",
        "id":   "environment_structure",
        "metadata": {
            "description": (
                "Structure-First environment scaffolding: build floor, walls, columns, "
                "doors, and windows before any asset is placed. Produces an "
                "EnvironmentStructure with structural elements and zone definitions "
                "for 21 production environments. Never places assets at the world origin."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "architectural_blueprints",
        "metadata": {
            "description": (
                "Hard-coded EnvironmentBlueprint definitions for 21 environments: "
                "western_room, saloon, living_room, office, hotel_lobby, restaurant, "
                "library, industrial_hangar, warehouse, abandoned_factory, robotics_lab, "
                "research_lab, medical_lab, control_room, sci_fi_corridor, space_station, "
                "city_street, forest, desert, castle_hall, survival_camp, dungeon. "
                "Each blueprint declares required/optional structural elements and asset layers."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "anchor_asset_layout",
        "metadata": {
            "description": (
                "Determine major focal anchors for an environment: primary anchor + "
                "secondary anchors with zone, position hint, and semantic child "
                "relationships (chair belongs_near table; cup belongs_on bar_counter). "
                "Enforces that hero assets receive contextual support props."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "decorative_population",
        "metadata": {
            "description": (
                "Fill environment zones with contextually appropriate small props and "
                "surface dressing. Respects zone budgets, anchor-relative placement "
                "(on_table / near_wall / wall_mounted), and semantic parent-child "
                "relationships. Decoration runs after structure + anchors are defined."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "environment_completeness_review",
        "metadata": {
            "description": (
                "6-dimension completeness review: structure (0.35) + anchor (0.25) + "
                "zones (0.15) + support (0.10) + decoration (0.10) + atmosphere (0.05). "
                "Blocking findings: floor missing, wall missing, required structure missing, "
                "anchor asset missing, no zones. production_ready requires score >= 0.70 "
                "and no blocking findings."
            ),
        },
    },
    # Geometry Intelligence (§43) -----------------------------------------------
    {
        "type": "semantic_operation",
        "id":   "geometry_analysis",
        "metadata": {
            "description": (
                "Full geometry intelligence for one asset: bounding box (priority chain: "
                "explicit bbox_min/max → bounding_box dict → USD extent → aabb → scalar "
                "fields → placement-type table → category table → 1×1×1 m fallback), "
                "pivot detection, ground contact points, and support surface detection. "
                "Returns AssetMetrics as the authoritative source for all placement systems. "
                "6 scale classes: tiny/small/medium/large/structural/hero."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "pivot_detection",
        "metadata": {
            "description": (
                "Detect the pivot type and position for an asset: "
                "bottom_center (floor-placed furniture, machines, vehicles), "
                "center (floating/suspended), top_center (ceiling-mounted), "
                "bottom_left (modular/grid-snap), custom (explicit metadata). "
                "Confidence 1.0 for explicit fields, 0.9 for known placement types, "
                "0.5 for generic fallback."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "support_surface_detection",
        "metadata": {
            "description": (
                "Detect valid horizontal surfaces on which child assets can be placed: "
                "tabletop (table), worktop (desk, workbench), countertop (counter, bar_counter), "
                "shelves (shelf, cabinet, wardrobe), rack units (server_rack — 1U = 0.044 m), "
                "pallet surface. Returns surface_type, height_m, area_m2, normal, load_capacity. "
                "Empty list for non-surface types (chair, vehicle, bucket, beam, wall)."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "ground_contact_detection",
        "metadata": {
            "description": (
                "Detect ground contact points: "
                "leg (chair/table/desk → 4 corner legs), "
                "base_ring (bucket/barrel/column → 8-point ring), "
                "base_plane (machine/crate/cabinet → flat base), "
                "wheel (vehicle → 4 wheels on 2 axles), "
                "skid (pallet → 2 rails), track (crane → 2 tracks). "
                "Empty list for hanging/floating assets (pendant_light, sprinkler)."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "asset_metrics",
        "metadata": {
            "description": (
                "Comprehensive asset metric extraction via AssetMetrics dataclass: "
                "width_m, height_m, depth_m, volume_m3, footprint_m2, placement_radius, "
                "bbox_min, bbox_max, pivot_type, pivot_position, support_surfaces, "
                "ground_contacts, scale_class (tiny/small/medium/large/structural/hero), "
                "role (prop/furniture/structure/vehicle/character/vegetation/hero_asset), "
                "source (explicit/format_metadata/estimated). "
                "Replaces SpatialMetadata and AssetScaleProfile for geometry-aware workflows."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "geometry_review",
        "metadata": {
            "description": (
                "5-dimension geometry quality evaluation: "
                "bbox_validity (0.30) + pivot_validity (0.20) + surface_detection (0.25) + "
                "ground_contact_detection (0.15) + scale_accuracy (0.10). "
                "Blocking findings: 'zero dimensions', 'no support surfaces', 'invalid role'. "
                "Role consistency: structural types cannot be furniture/prop; "
                "chair/table cannot be structure. "
                "production_ready requires overall_score >= 0.70 and no blocking findings."
            ),
        },
    },
    # Environment Construction Package (§44) -----------------------------------
    {
        "type": "runtime_service",
        "id":   "environment_blueprints",
        "metadata": {"description": "Environment blueprint templates for 20 production environment types"},
    },
    {
        "type": "runtime_service",
        "id":   "environment_construction",
        "metadata": {"description": "Structure-first environment construction: floor/walls/ceiling/doors/windows scaffold"},
    },
    {
        "type": "runtime_service",
        "id":   "environment_zones",
        "metadata": {"description": "Canonical zone construction for environments (hero/entrance/seating/service/background)"},
    },
    {
        "type": "runtime_service",
        "id":   "anchor_asset_placement",
        "metadata": {"description": "Major focal anchor placement with semantic child-type relationships"},
    },
    {
        "type": "runtime_service",
        "id":   "support_asset_placement",
        "metadata": {"description": "Secondary prop placement relative to anchor assets"},
    },
    {
        "type": "runtime_service",
        "id":   "decorative_population_service",
        "metadata": {"description": "Small decorative prop population using per-environment definitions"},
    },
    {
        "type": "runtime_service",
        "id":   "atmosphere_construction",
        "metadata": {"description": "Volumetric and atmospheric effect planning (8 built-in profiles)"},
    },
    {
        "type": "runtime_service",
        "id":   "environment_review",
        "metadata": {"description": "6-dimension environment completeness review: structure/zones/anchors/support/decoration/atmosphere"},
    },
    # §45 — Semantic Asset Suitability Ranking (Tier 12.85) -------------------
    {
        "type": "runtime_service",
        "id":   "asset_suitability_ranking",
        "metadata": {"description": "7-factor suitability scoring replacing semantic similarity as primary ranking criterion"},
    },
    {
        "type": "runtime_service",
        "id":   "environment_affinity",
        "metadata": {"description": "Keyword-based environment affinity scoring: preferred/rejected keyword tables for 21 environments"},
    },
    {
        "type": "runtime_service",
        "id":   "style_affinity",
        "metadata": {"description": "Visual style affinity scoring per environment (weathered, rustic, sterile, futuristic, …)"},
    },
    {
        "type": "runtime_service",
        "id":   "role_affinity",
        "metadata": {"description": "Asset role slot matching: exact/partial/rejected type tables for 35+ roles"},
    },
    {
        "type": "runtime_service",
        "id":   "material_affinity",
        "metadata": {"description": "Material composition affinity scoring per environment (wood, chrome, stone, steel, …)"},
    },
    {
        "type": "runtime_service",
        "id":   "story_affinity",
        "metadata": {"description": "Narrative prop scoring per environment: canonical story assets and rejected anachronisms"},
    },
    {
        "type": "runtime_service",
        "id":   "asset_selection_validation",
        "metadata": {"description": "Validate that a selected asset matches its requested role and environment before placement"},
    },
    # §46 — Semantic Furniture Layout Engine (Tier 9.8) ----------------------
    {
        "type": "runtime_service",
        "id":   "semantic_layout",
        "metadata": {
            "description": (
                "Full relationship-based furniture layout pipeline: "
                "anchor placement → relationship graph → furniture clustering → "
                "surface placement → wall attachment → decoration → review. "
                "Assets placed relative to other assets, not independently in zones."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "relationship_graph",
        "metadata": {
            "description": (
                "Directed semantic relationship graph between placed assets. "
                "Supported types: supports, contains, attached_to, around, near, "
                "against, inside, hanging_from, mounted_on, facing. "
                "Chair 'around' table; bottle 'supports' table surface; poster 'attached_to' wall."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "affordance_reasoning",
        "metadata": {
            "description": (
                "Per-asset-type affordance profiles: provides_surface, provides_around, "
                "is_anchor, is_wall_attachable, is_ceiling_hangable, is_against_wall, is_corner_placed. "
                "Determines placement mode (hero_center, around_anchor, on_surface, wall_only, corner, …) "
                "for every furniture and prop type."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "surface_placement",
        "metadata": {
            "description": (
                "Places small objects on actual host surfaces at the correct Y height. "
                "Surface heights: table=0.75 m, bar_counter=1.05 m, shelf=1.40 m, workbench=0.90 m. "
                "Items spread deterministically across surface width; overflow items rejected not floor-placed."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "wall_attachment",
        "metadata": {
            "description": (
                "Mounts wall-attachable objects (poster/lantern/sign/banner/shelf) on room walls "
                "at the correct height with wall-normal orientation. "
                "Height rules: poster 1.4–1.8 m, lantern/torch 2.0–2.8 m, shelf 1.2–1.6 m. "
                "Items distributed across four labelled walls (north/south/east/west)."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "furniture_clustering",
        "metadata": {
            "description": (
                "Groups anchor assets with their semantic dependents into named clusters. "
                "Examples: saloon_table_cluster (table + 4 chairs + bottle + lantern), "
                "bar_cluster (bar_counter + stools + bottles), workbench_cluster (workbench + tools + containers). "
                "Chair orbit positions N/S/E/W at 0.9 m facing centre."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "contextual_decoration",
        "metadata": {
            "description": (
                "Assigns contextual placement targets to decorative assets using per-environment "
                "preference tables (21 environments). "
                "western_room → barrel/lantern/wanted_poster/whiskey_bottle; "
                "castle_hall → banner/torch/candle; robotics_lab → electronic/cable/warning_sign."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "layout_review",
        "metadata": {
            "description": (
                "5-dimension semantic layout quality review: "
                "relationship_accuracy (0.30) + surface_accuracy (0.25) + wall_attachment (0.20) + "
                "cluster_quality (0.15) + contextual_quality (0.10). "
                "Blocking findings: 'bottle on floor when table exists', 'poster not attached to wall', "
                "'no relationships defined', 'no anchors placed'. "
                "production_ready requires overall_score ≥ 0.70 and no blocking findings."
            ),
        },
    },
    # §47 — Layout Realization & Scene Constraint Solver (Tier 9.9) ----------
    {
        "type": "runtime_service",
        "id":   "layout_realization",
        "metadata": {
            "description": (
                "Convert a Tier 9.8 LayoutPlan into a ResolvedSceneLayout: "
                "concrete world-space transforms (tx, ty, tz, rx, ry, rz) for every asset. "
                "Pipeline: cluster realization → surface realization → wall realization → "
                "collision solving → constraint solving → scene assembly."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "constraint_solving",
        "metadata": {
            "description": (
                "Scene-level spatial constraint enforcement: minimum spacing (0.30 m), "
                "cluster centroid spacing (2.50 m), wall clearance, door clearance (1.50 m), "
                "hero asset visibility, camera sightline protection."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "collision_resolution",
        "metadata": {
            "description": (
                "AABB collision detection and resolution: push-apart, slide, rotate strategies. "
                "Iterative solver (max 5 passes). Marks unresolved assets with is_collision_free=False. "
                "Checks: bbox overlap, wall penetration, cluster overlap."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "transform_resolution",
        "metadata": {
            "description": (
                "Convert semantic positions (anchor, relative cluster offset, surface height, "
                "wall normal) into explicit world-space 9-DOF transforms (tx/ty/tz/rx/ry/rz/sx/sy/sz). "
                "Y-up convention. Deterministic — same LayoutPlan → same transforms."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "scene_realization",
        "metadata": {
            "description": (
                "Full pipeline from LayoutPlan to production-ready Houdini scene: "
                "realize → solve → apply via LayoutApplicationEngine (bridge adapter). "
                "Replaces linear build_scene_from_assets() with semantic placement."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "surface_realization",
        "metadata": {
            "description": (
                "Place surface items on host asset surfaces at correct Y height. "
                "ty = host_world_y + surface_height + child_half_height. "
                "Heights: table=0.75m, bar_counter=1.05m, shelf=1.40m, workbench=0.90m."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "wall_realization",
        "metadata": {
            "description": (
                "Realize wall-mounted assets: compute ry from wall normal, snap to wall face "
                "with inset, validate position inside room bounds. "
                "poster=1.6m, lantern=2.4m, banner=2.15m, shelf=1.4m."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "cluster_realization",
        "metadata": {
            "description": (
                "Realize FurnitureClusters into world-space transforms: "
                "anchor at zone position, chairs orbit at 0.9m cardinal directions, "
                "surface props spread across tabletop width. All members tagged with cluster_id."
            ),
        },
    },
    # §49 — Structural Environment Realization (Tier 10.0) --------------------
    {
        "type": "runtime_service",
        "id":   "environment_realization",
        "metadata": {
            "description": (
                "Full structural realization pipeline: environment name → RoomShell "
                "(floor + 4 walls + ceiling + openings + beams + columns) + zone regions + "
                "Houdini transaction ops. Supports 55 environments including outdoor ground planes."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "room_generation",
        "metadata": {
            "description": (
                "Generate complete RoomShell for any of 55 environments: "
                "dimensions from production table, materials from environment category, "
                "room_closed=True for all indoor environments. "
                "Outdoor environments receive a large ground plane only."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "structural_generation",
        "metadata": {
            "description": (
                "Orchestrate floor+wall+ceiling+opening+beam generation "
                "into a flat StructuralElement list + Houdini op dicts. "
                "Transaction ops include tx/ty/tz/dimensions/material per element."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "wall_generation",
        "metadata": {
            "description": (
                "Generate four perimeter walls (N/S/E/W) with environment-appropriate material "
                "and thickness. Materials: wood=western/residential, stone=castle/dungeon, "
                "concrete=lab/industrial, sci_fi_panel=corridor/station."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "floor_generation",
        "metadata": {
            "description": (
                "Generate floor element with environment-appropriate material: "
                "wood_planks=western/saloon, stone=castle/dungeon, concrete=lab/industrial, "
                "marble=hotel, tile=medical, sand/dirt=outdoor. "
                "Outdoor environments get a 50×50m ground plane."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "ceiling_generation",
        "metadata": {
            "description": (
                "Generate ceiling element: beam_ceiling=western/saloon/warehouse, "
                "flat_ceiling=office/lab/medical, industrial_ceiling=hangar/factory, "
                "arched_ceiling=castle/dungeon, sci_fi_ceiling=corridor/station. "
                "Outdoor environments return None (open_sky)."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "opening_generation",
        "metadata": {
            "description": (
                "Generate doors, windows, archways, vents per environment: "
                "western_room → 1 swing_door + 2 windows; "
                "industrial_hangar → 1 hangar_opening + 4 skylights; "
                "sci_fi_corridor → 2 sliding_doors + 4 vents; "
                "castle_hall → 1 archway + 4 arrow_slits. "
                "All openings reference parent wall via wall_id."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "beam_generation",
        "metadata": {
            "description": (
                "Generate beams and columns: wooden_beam=western/saloon/warehouse, "
                "steel_girder=industrial_hangar/shipyard, panel_rib=sci_fi_corridor, "
                "stone_arch=castle_hall/dungeon, concrete_column=lab/parking. "
                "Beams span east-west at ceiling height; columns at perimeter."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "architectural_validation",
        "metadata": {
            "description": (
                "Validate RoomShell structural constraints: room_closure, "
                "opening-inside-wall, ceiling-dimension-match, opening-fits-wall. "
                "Corrections: snap ceiling to room dimensions, trim overflow openings."
            ),
        },
    },
    # §48 — Structural Asset Classification (Tier 10.3) ----------------------
    {
        "type": "semantic_operation",
        "id":   "structural_asset_classification",
        "metadata": {
            "description": (
                "Automatically classify assets as structural (beam/column/doorway/fireplace/"
                "wall/archway/stair/railing/…) or non-structural (furniture/prop/decoration) "
                "using 3 signals: geometry bounding-box ratios, metadata keyword tables, and "
                "environment-context affinity. Ensures 0 architectural assets enter furniture "
                "or decoration pipelines."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "geometry_role_detection",
        "metadata": {
            "description": (
                "Classify structural role from bounding-box dimensions (metres): "
                "beam (span ≥ 2m, cross-section ≤ 0.6m, ratio ≥ 4), "
                "column (h ≥ 2m, footprint ≤ 0.8m, h/footprint ≥ 3.5), "
                "doorway (h ≥ 1.8m, d ≤ 0.5m, h/d ≥ 3), "
                "wall_segment (h ≥ 2m, w ≥ 1.5m, d ≤ 0.5m), "
                "floor_piece (h ≤ 0.25m, footprint ≥ 1.0m²). "
                "Validation scenario: 3.7×0.3×0.3m → beam (0.86), "
                "2.3×4.0×0.7m → doorway (0.78), 0.8×0.8×0.9m → furniture (0.65)."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "metadata_role_classification",
        "metadata": {
            "description": (
                "Classify structural role from asset name, tags, and category using "
                "keyword tables (120+ entries). High-confidence keywords: "
                "doorway (0.90), beam (0.85–0.90), column/pillar (0.88), "
                "fireplace/hearth (0.88–0.92), archway (0.90), wall_panel (0.88). "
                "Metadata confidence ≥ 0.80 overrides geometry signal."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "environment_structural_affinity",
        "metadata": {
            "description": (
                "Adjust structural role confidence based on environment context: "
                "preferred roles get +0.10 boost (capped at 1.0); "
                "irrelevant roles capped at 0.50. "
                "western_room prefers doorway/beam/fireplace; "
                "sci_fi_corridor prefers wall_segment/ceiling_piece/door_frame; "
                "castle_hall prefers archway/column/fireplace. "
                "Covers 25 environments with per-environment preferred/irrelevant tables."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "structural_placement_intent",
        "metadata": {
            "description": (
                "Derive placement routing and attachment rules for each structural role: "
                "doorway → OpeningBuilder (wall_opening); "
                "beam/support_beam → BeamBuilder (ceiling_support); "
                "column → BeamBuilder (floor_perimeter); "
                "fireplace → AnchorAssetBuilder (wall_face); "
                "floor_piece → FloorBuilder; wall/wall_segment → EnvironmentStructureBuilder. "
                "All structural roles are forbidden from furniture_cluster, seating, "
                "decoration, and surface_prop pipelines."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "structural_layout_review",
        "metadata": {
            "description": (
                "4-dimension structural placement quality review: "
                "placement_validity (0.35) + pipeline_integrity (0.30) + "
                "role_accuracy (0.20) + coverage (0.15). "
                "Blocking findings: 'floating structural asset', "
                "'architectural asset in cluster', 'doorway placed on floor center', "
                "'beam treated as decoration', 'fireplace placed as free-standing'. "
                "production_ready requires score ≥ 0.70 and no blocking findings."
            ),
        },
    },
    # §54 — Environment Shell Construction (Tier 10.4) -----------------------
    {
        "type": "runtime_service",
        "id":   "environment_shell_construction",
        "metadata": {
            "description": (
                "6-phase environment shell construction pipeline: floor → walls → ceiling → "
                "structural anchors → structural placement → validation. "
                "Produces EnvironmentShell with environment_ready gate. "
                "No asset may be placed until environment_ready = True."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "environment_readiness_gate",
        "metadata": {
            "description": (
                "Environment readiness gate: floor_exists AND (ceiling_exists OR outdoor) "
                "AND wall_count >= required AND enclosure_valid. "
                "Gate failure → ENVIRONMENT_NOT_READY (BLOCKING). "
                "Blocks: FurnitureClusterBuilder, SurfacePlacementEngine, "
                "DecorationLayoutEngine, SceneRealityValidation."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "shell_floor_construction",
        "metadata": {
            "description": (
                "Phase 1: floor element with material per environment. "
                "floor_exists=True, floor_area=width*length, walkable_surface=True. "
                "Outdoor → 50×50m ground plane. Status: FLOOR_CONSTRUCTION_COMPLETE."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "shell_wall_construction",
        "metadata": {
            "description": (
                "Phase 2: four perimeter walls (N/S/E/W) with environment material, 0.3m thick. "
                "enclosure_valid=True for indoor. Outdoor skips walls. "
                "Status: WALL_CONSTRUCTION_COMPLETE."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "shell_ceiling_construction",
        "metadata": {
            "description": (
                "Phase 3: ceiling element (beam/flat/sci_fi/vaulted/arched/industrial). "
                "ceiling_exists=True, ceiling_height=room_height. "
                "Outdoor → open_sky (no element). Status: CEILING_CONSTRUCTION_COMPLETE."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "structural_anchor_generation",
        "metadata": {
            "description": (
                "Phase 4: generate door/window/beam/column/fireplace anchor points. "
                "Per-environment counts from production tables. "
                "Status: STRUCTURAL_ANCHORS_READY."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "shell_structural_placement",
        "metadata": {
            "description": (
                "Phase 5: attach structural assets to anchors. "
                "doorway→OpeningBuilder, beam→BeamBuilder, "
                "column→BeamBuilder, fireplace→AnchorAssetBuilder. "
                "Status: STRUCTURAL_PLACEMENT_COMPLETE."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "shell_validation",
        "metadata": {
            "description": (
                "Phase 6: validate completed shell — floor_exists, ceiling_exists/outdoor, "
                "wall_count >= required, room_bounds_valid, enclosure_valid. "
                "Status: ENVIRONMENT_VALIDATION_COMPLETE."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "environment_shell_audit",
        "metadata": {
            "description": (
                "Audit report: floor_exists, wall_count, ceiling_exists, "
                "door/window/beam attachment counts, environment_ready, "
                "environment_valid, geometry_valid, semantic_valid, plausibility_valid, "
                "production_ready = all four True."
            ),
        },
    },
    {
        "type": "runtime_service",
        "id":   "shell_review",
        "metadata": {
            "description": (
                "6-dimension shell quality review: "
                "floor(0.25)+wall(0.25)+ceiling(0.20)+anchors(0.15)+enclosure(0.10)+phases(0.05). "
                "Grade A/B → production_ready=True. "
                "Blocking: 'floor missing', 'wall missing', 'ceiling missing'."
            ),
        },
    },
    # §53 — Scene Reality Validation (Tier 14.3) ------------------------------
    {
        "type": "semantic_operation",
        "id":   "scene_reality_validation",
        "metadata": {
            "description": (
                "Validates scene correctness beyond execution success. "
                "Runs 5 rules on ResolvedSceneLayout and produces four verdicts: "
                "geometry_valid (no occupancy/support violations), "
                "semantic_valid (relationships OK + no orphans, score>=0.95), "
                "plausibility_valid (human usage score>=0.90), "
                "production_ready (all three). "
                "Acceptance criteria: no props inside chair volumes, "
                "no floor-level surface props when table exists, "
                "all chairs near valid anchor, plausibility>=0.90, semantic>=0.95."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "support_surface_validation",
        "metadata": {
            "description": (
                "Rule 1: Detects surface-affinity props (bottle, cup, teapot, book, …) "
                "resting on the floor (ty < 0.35m) when a valid host surface "
                "(table, shelf, bar_counter, …) exists in the scene. "
                "Violation: INVALID_SUPPORT_RELATION (BLOCKING)."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "occupancy_violation_detection",
        "metadata": {
            "description": (
                "Rule 2: Generates AABB occupancy volumes for furniture assets "
                "(chair, table, cabinet, bed, …). Detects small props whose "
                "world-space centre falls inside a host AABB. "
                "Parent-child and same-cluster pairs are exempt. "
                "Violation: OCCUPANCY_VIOLATION (BLOCKING)."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "functional_relationship_validation",
        "metadata": {
            "description": (
                "Rule 3: Validates expected semantic relationships — "
                "chair→around table, bottle→supports table, poster→attached_to wall, "
                "beam→attached_to ceiling, door→attached_to wall. "
                "Checks both relationship tag and parent asset type. "
                "Violation: RELATIONSHIP_FAILURE (WARNING)."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "human_plausibility_evaluation",
        "metadata": {
            "description": (
                "Rule 4: Simulates five human-usage checks — "
                "can_sit (chair seat at 0.45m ± 0.30m), "
                "can_access (table clearance >= 0.5m), "
                "can_reach (surface props ty <= 2.0m), "
                "door_clear (doorways not blocked within 0.8m), "
                "floor_space (>= 30% floor free). "
                "plausibility_score = mean of five checks (0.0–1.0). "
                "Threshold: >= 0.90 → plausibility_valid = True."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "orphan_object_detection",
        "metadata": {
            "description": (
                "Rule 5: Detects assets with no valid semantic parent. "
                "chair without nearby table (1.5m), bottle without table (0.8m), "
                "poster/painting/banner with no wall in scene, "
                "lantern with no valid attachment point. "
                "Assets with parent_id or cluster_id are exempt. "
                "Violation: ORPHAN_OBJECT (WARNING)."
            ),
        },
    },
    # -----------------------------------------------------------------------
    # Tier 10.5 — Structural Openings & Architectural Features
    # -----------------------------------------------------------------------
    {
        "type": "semantic_operation",
        "id":   "structural_openings",
        "metadata": {
            "description": (
                "Convert door and window anchors from EnvironmentShell into physical "
                "boolean opening specifications. Each door_anchor and window_anchor "
                "must produce exactly one ArchitecturalOpening or the result is FAIL. "
                "Dimensions from environment blueprint. No bridge calls."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "fireplace_attachment",
        "metadata": {
            "description": (
                "Validate and plan fireplace placement from fireplace_anchors. "
                "Rules: back_face_distance <= 0.05m from wall face; forward_axis "
                "must equal the room-interior vector for the wall; fireplace centre "
                "must align to wall centreline. No bridge calls."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "beam_attachment",
        "metadata": {
            "description": (
                "Plan beam placements from beam_anchors. Rules: beam long axis must "
                "align with room width or room length; beam top must be within 0.05m "
                "of ceiling_height; beam cross-section must not exceed wall boundaries. "
                "No bridge calls."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "shelf_attachment",
        "metadata": {
            "description": (
                "Attach wall-shelf assets to wall faces at validated mount heights "
                "(1.20–1.80m). Every shelf must be parented to a wall attachment "
                "point — floating shelves are blocking findings. No bridge calls."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "architectural_geometry",
        "metadata": {
            "description": (
                "Create Houdini geometry nodes for every ArchitecturalPlan feature: "
                "/obj/sh_door_opening_*, /obj/sh_window_opening_*, /obj/sh_beam_*, "
                "/obj/sh_fireplace_*, /obj/sh_shelf_*. "
                "ArchitecturalFeatureRealizer is the ONLY Tier 10.5 module that calls "
                "get_bridge(). All other modules are pure planning."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "environment_architecture_review",
        "metadata": {
            "description": (
                "ARCHITECTURE_STATUS (PASS / FAIL) review for Tier 10.5 features. "
                "Score weights: door_openings 0.30, window_openings 0.25, fireplace 0.20, "
                "beams 0.15, shelves 0.10. PASS criterion: score >= 0.80 AND no missing "
                "door or window openings. Hard rule: any missing opening → production_ready = False."
            ),
        },
    },
    # -----------------------------------------------------------------------
    # Tier 14.4.3 — Relationship Realization Audit
    # -----------------------------------------------------------------------
    {
        "type": "semantic_operation",
        "id":   "relationship_realization_audit",
        "metadata": {
            "description": (
                "Tier 14.4.3: Verifies that relationship-aware transforms are correctly applied "
                "to Houdini nodes after realization. Routes per relationship edge field rather than "
                "asset type. PASS criterion: relationship_realization_score >= 0.95. "
                "Hard Fail: any 'supports' relationship resulting in floor placement (ty < 0.10m)."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "supports_relationship_audit",
        "metadata": {
            "description": (
                "Audit 'supports' relationship edges: child world Y must equal parent surface "
                "height ± 2cm; child must be horizontally inside parent surface bounds; "
                "fail if ty < 0.10m when a supports relationship exists (Hard Fail)."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "belongs_near_audit",
        "metadata": {
            "description": (
                "Audit 'belongs_near' relationship edges: XZ distance to anchor must be "
                "within 2.5m; forward axis must face the anchor within 15° tolerance."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "wall_attachment_audit",
        "metadata": {
            "description": (
                "Audit 'attached_to wall_*' relationship edges: position drift vs planned "
                "must be ≤ 5cm; asset must not penetrate the wall plane; forward axis must "
                "face room interior within 20° (wall_north → ry=0°, wall_south → ry=180°, "
                "wall_east → ry=90°, wall_west → ry=270°)."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "ceiling_attachment_audit",
        "metadata": {
            "description": (
                "Audit 'attached_to ceiling' relationship edges: object must be below the "
                "ceiling height (ty < ceiling_height); parent anchor must exist."
            ),
        },
    },
    # Tier 14.4.4 — Relationship Metadata Persistence
    # -----------------------------------------------------------------------
    {
        "type": "semantic_operation",
        "id":   "relationship_metadata_persistence",
        "metadata": {
            "description": (
                "Tier 14.4.4: Writes 9 vibrante_ user-data keys to every realized Houdini node "
                "(role, relationship_type, expected_parent, actual_parent, support_surface, "
                "anchor_id, anchor_type, placement_engine, layout_cluster_id). "
                "PASS criterion: metadata_coverage == 100%, missing_metadata == 0."
            ),
        },
    },
    # Tier 14.4.5 — Asset Identity Audit
    # -----------------------------------------------------------------------
    {
        "type": "semantic_operation",
        "id":   "asset_identity_audit",
        "metadata": {
            "description": (
                "Tier 14.4.5: Verifies every realized Houdini node has a persistent semantic "
                "identity. Reads vibrante_asset_id, vibrante_asset_name, vibrante_asset_category "
                "plus all 9 relationship keys. Detects opaque Megascans-style IDs (e.g. "
                "'xgihfgbqx'). Validates role vs engine and role vs category. "
                "PASS: identity_coverage == 100%, unclassified_assets == 0, opaque_assets == 0."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "opaque_id_detection",
        "metadata": {
            "description": (
                "Detect opaque Megascans-style identifiers that contain no semantic meaning. "
                "Pattern: all lowercase [a-z], 5–15 chars, no separators, no vocabulary match. "
                "Opaque names must be replaced with human-readable asset names before production."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "role_engine_validation",
        "metadata": {
            "description": (
                "Cross-validate vibrante_asset_role against vibrante_placement_engine. "
                "Each engine owns a fixed role set: AnchorLayoutEngine→anchor; "
                "FurnitureClusterBuilder→cluster_member; SurfacePlacementEngine→surface_child; "
                "WallAttachmentEngine→wall_mount/wall_adjacent/ceiling_mount; "
                "DecorationLayoutEngine→decoration/proximity_prop."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "role_geometry_validation",
        "metadata": {
            "description": (
                "Validate vibrante_asset_role against vibrante_asset_category as a geometry proxy. "
                "Structural categories (beam, column, wall) cannot have surface_child or "
                "cluster_member roles. Decoration category cannot be an anchor. "
                "Same input always produces the same validation result."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "identity_metadata_write",
        "metadata": {
            "description": (
                "Write 3 identity user-data keys to every realized Houdini node: "
                "vibrante_asset_id (catalog ID), vibrante_asset_name (human-readable display name), "
                "vibrante_asset_category (semantic category). Category is inferred from asset name "
                "keywords when not explicitly provided."
            ),
        },
    },
    # §54 — Reality Intelligence (Tier 15.0+) ---------------------------------
    {
        "type": "semantic_operation",
        "id":   "reality_intelligence",
        "metadata": {
            "description": (
                "Tier 15.0+: full Reality Intelligence pipeline — human reasoning, "
                "functional zones, support rules, floating-object raycast, beam "
                "connections, architectural integrity, density, composition, "
                "correction plan and visual review. production_ready requires ALL "
                "nine §54 success criteria; visual believability is the final authority."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "human_reasoning",
        "metadata": {
            "description": (
                "Every asset must answer six questions: why it exists, who uses it, "
                "what activity happens around it, what supports it, what it relates "
                "to, and whether it improves the scene story. Unjustified assets are "
                "rejected — never ask 'can I place this', ask 'would a human place this here'."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "functional_zoning",
        "metadata": {
            "description": (
                "Build functional zones (dining, fireplace, bar, work, sleeping, "
                "storage, wall decor, structure) before placement; assign every asset "
                "to a zone. No orphan assets allowed."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "support_rule_validation",
        "metadata": {
            "description": (
                "Enforce the §54 support table: bottle→table/shelf/bar, cup→table/shelf, "
                "plate→table, lantern→table/wall/ceiling, chair→table/desk/fireplace/bar, "
                "stool→bar, fireplace→wall, window/door→wall opening. Missing support "
                "rejects the placement."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "floating_object_detection",
        "metadata": {
            "description": (
                "No Floating Objects Rule: any asset whose bottom is above floor+0.10 m "
                "must pass raycast_down() against actual support geometry. Failures are "
                "BLOCKING and produce automatic relocation suggestions."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "beam_connection_validation",
        "metadata": {
            "description": (
                "Beams must connect architecture: wall-to-wall, wall-to-column or "
                "column-to-column. Both rotated beam endpoints must intersect a wall "
                "plane or column footprint; floating mid-room beams are invalid."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "architectural_integrity",
        "metadata": {
            "description": (
                "Walls, windows, doors, ceilings, floors, columns and beams form one "
                "system. Doors and windows require real wall openings — no decorative "
                "fakes. Fireplaces require wall backing; assets may not poke through "
                "the room perimeter."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "environment_density",
        "metadata": {
            "description": (
                "density_score = placed_assets / room_area. Small rooms (<150 m²) need "
                "10–20 assets, medium (<600 m²) 20–40, large 40–80. Empty rooms are invalid."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "scene_composition",
        "metadata": {
            "description": (
                "Every room needs a primary focal point, a secondary focal point and "
                "negative space (≥25% walkable floor). Focal priority: fireplace > "
                "table > bar > machine > desk > bed."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "reality_correction_pass",
        "metadata": {
            "description": (
                "Relationship Correction Pass: plans and applies geometry fixes for "
                "floating props, unsupported assets, chairs not facing their anchor, "
                "wall intersections and isolated assets. Modifies actual Houdini "
                "geometry via CorrectionApplier — not metadata, not plans."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "geometry_truth_inspection",
        "metadata": {
            "description": (
                "Reality First Rule: inspect actual Houdini geometry (world transforms "
                "+ cooked bounding boxes) after realization and reconcile against "
                "planner metadata. When geometry contradicts metadata, GEOMETRY WINS."
            ),
        },
    },
    {
        "type": "semantic_operation",
        "id":   "visual_review",
        "metadata": {
            "description": (
                "Final §54 review answering the four artist questions (would an "
                "environment artist approve, production-game quality, film-set quality, "
                "would a human use the room) from nine derived success criteria. "
                "production_ready only when all criteria hold."
            ),
        },
    },
]


class CapabilityRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        # id → {"type": str, "id": str, "metadata": dict}
        self._caps: Dict[str, Dict[str, Any]] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        for cap in _BUILTIN_CAPABILITIES:
            self._caps[cap["id"]] = {
                "type": cap["type"],
                "id":   cap["id"],
                "metadata": dict(cap.get("metadata", {})),
            }

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_capability(self, cap_type: str, cap_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Register or update a capability.

        Args:
            cap_type: One of the CAPABILITY_TYPES strings.
            cap_id:   Unique string identifier (e.g. "karma", "create_node").
            metadata: Arbitrary dict of extra information.

        Raises:
            ValueError: If cap_type is not a known capability type.
        """
        if cap_type not in CAPABILITY_TYPES:
            raise ValueError(f"Unknown capability type: {cap_type!r}. Valid types: {sorted(CAPABILITY_TYPES)}")
        if not cap_id:
            raise ValueError("cap_id must be a non-empty string")
        with self._lock:
            self._caps[cap_id] = {
                "type":     cap_type,
                "id":       cap_id,
                "metadata": dict(metadata or {}),
            }

    def deregister_capability(self, cap_id: str) -> bool:
        """Remove a capability by id. Returns True if found and removed."""
        with self._lock:
            if cap_id in self._caps:
                del self._caps[cap_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query_capabilities(self, cap_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all capabilities, optionally filtered by type.

        Returns a list of dicts sorted by (type, id) for deterministic output.
        """
        with self._lock:
            caps = list(self._caps.values())
        if cap_type is not None:
            caps = [c for c in caps if c["type"] == cap_type]
        return sorted(caps, key=lambda c: (c["type"], c["id"]))

    def supports(self, capability_id: str) -> bool:
        """Return True if the given capability id is registered."""
        with self._lock:
            return capability_id in self._caps

    def get(self, capability_id: str) -> Optional[Dict[str, Any]]:
        """Return the capability dict for the given id, or None."""
        with self._lock:
            cap = self._caps.get(capability_id)
            return dict(cap) if cap else None

    # ------------------------------------------------------------------
    # Tier 4 — MCP tool exposure
    # ------------------------------------------------------------------

    def expose_via_mcp(self, cap_id: str, tool_schema: Optional[Dict[str, Any]] = None) -> None:
        """Mark a capability as exposed via the MCP server runtime.

        Registers an ``mcp_tool`` capability whose metadata contains the
        inputSchema used by the MCP server.  The cap_id must already exist
        in the registry.
        """
        tool_schema = dict(tool_schema or {})
        existing    = self.get(cap_id)
        description = existing.get("metadata", {}).get("description", cap_id) if existing else cap_id
        with self._lock:
            self._caps[f"mcp:{cap_id}"] = {
                "type":     "mcp_tool",
                "id":       f"mcp:{cap_id}",
                "metadata": {
                    "tool_name":   cap_id,
                    "description": description,
                    "inputSchema": tool_schema,
                },
            }

    def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """Return all MCP-exposed tools in MCP tool-list format."""
        with self._lock:
            tools = [c for c in self._caps.values() if c["type"] == "mcp_tool"]
        return sorted(
            [
                {
                    "name":        t["metadata"].get("tool_name", t["id"]),
                    "description": t["metadata"].get("description", ""),
                    "inputSchema": t["metadata"].get("inputSchema", {}),
                }
                for t in tools
            ],
            key=lambda t: t["name"],
        )

    # ------------------------------------------------------------------
    # Tier 4 — Remote / federated capability registration
    # ------------------------------------------------------------------

    def register_remote_capability(
        self,
        runtime_id: str,
        cap_type:   str,
        cap_id:     str,
        metadata:   Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a capability from a remote federated runtime.

        The cap_id is namespaced as ``<runtime_id>:<cap_id>`` to avoid
        collisions with local capabilities.

        Raises:
            ValueError: If cap_type is not a valid CAPABILITY_TYPES entry.
        """
        namespaced_id = f"{runtime_id}:{cap_id}"
        meta = dict(metadata or {})
        meta["runtime_id"] = runtime_id
        meta["remote"]     = True
        self.register_capability("remote_capability", namespaced_id, meta)

    def get_remote_capabilities(self, runtime_id: str) -> List[Dict[str, Any]]:
        """Return all capabilities registered from a specific remote runtime."""
        with self._lock:
            return [
                dict(c) for c in self._caps.values()
                if c["type"] == "remote_capability"
                and c.get("metadata", {}).get("runtime_id") == runtime_id
            ]

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_type: Dict[str, int] = {}
            for cap in self._caps.values():
                by_type[cap["type"]] = by_type.get(cap["type"], 0) + 1
            return {
                "total": len(self._caps),
                "by_type": by_type,
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_REGISTRY: Optional[CapabilityRegistry] = None
_REGISTRY_LOCK = threading.Lock()


def get_capability_registry() -> CapabilityRegistry:
    global _REGISTRY
    with _REGISTRY_LOCK:
        if _REGISTRY is None:
            _REGISTRY = CapabilityRegistry()
        return _REGISTRY


def reset_capability_registry_for_tests() -> None:
    global _REGISTRY
    with _REGISTRY_LOCK:
        _REGISTRY = None
