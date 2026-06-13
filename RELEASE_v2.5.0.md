# Vibrante-Node v2.5.0 — Release Notes

**Released:** 2026-06-13
**Type:** Minor — massive AI intelligence expansion (Tiers 8–15), 200+ new Houdini nodes, 250+ new tests

---

## Summary

v2.5.0 is the largest feature release in Vibrante-Node's history. It introduces a complete AI-native environment assembly pipeline spanning 18 intelligence tiers, from natural language scene intent extraction through reality validation and live geometry correction in Houdini. Every tier is deterministic, planning-only (no bridge calls), and backed by a dedicated unit test suite.

---

## What's New

### Semantic Scene Intent System (Phase 1)

New `src/runtime/semantic/` sub-package — a full NL → structured intent extraction pipeline:

- **`SceneIntentExtractor`** — orchestrates LLM-optional extraction; produces typed `SceneIntent` dataclasses
- **`SceneIntentValidator`** — enum/range/contradiction validation on all 14 schema fields
- **`SceneIntentEnricher`** — deterministically enriches intents with implied requirements; every enrichment records reason, source, and confidence
- **`IntentSerializer`** — JSON persistence with schema version migration
- **`SemanticLogger`** — pipeline trace for every extraction step
- **`IntentRecommendationEngine`** — production-proven recommendations from memory + patterns + knowledge graph
- Schema constants: `ENVIRONMENT_TYPES`, `STYLE_TYPES`, `MOOD_TYPES`, `CINEMATIC_STYLE_VALUES`, `ATMOSPHERIC_EFFECT_TYPES`, and more (55 environments)
- 5 new Houdini nodes: `hou_mcp_scene_intent_extract`, `hou_mcp_scene_intent_validate`, `hou_mcp_scene_intent_enrich`, `hou_mcp_scene_intent_recommend`, `hou_mcp_build_scene_from_intent`

### Production Semantic Intelligence Layer (Tier 2.9)

4 new runtime modules for cinematic goal orchestration:

- **`goal_decomposer`** — "create cinematic explosion scene" → 9 ordered workflow stages; pure keyword matching, no LLM required
- **`review_engine`** — specific per-stage critique ("smoke breakup lacks variation", "depth pass not in world units"); never returns generic "Execution successful"
- **`scene_awareness`** — analyzes scene_context dicts for terrain scale, renderer, lighting environment, and render cost estimation
- **`runtime_narration`** — `[Runtime]`/`[Planning]`/`[Execution]`/`[Review]` narration blocks for all orchestration steps

### Cinematic Orchestration Suite (§23)

6 new planning modules with zero Houdini dependency:

- **`semantic_lighting_engine`** — cinematic lighting plans from scene intent + mood context
- **`cinematic_camera_engine`** — camera orchestration plans (push-in, orbital, dutch, etc.)
- **`atmosphere_orchestrator`** — fog, volumetric, and particle atmosphere plans
- **`visual_hierarchy_engine`** — hero focus, depth layering, and balance evaluation
- **`render_preparation_engine`** — renderer settings, AOV strategy, and complexity scoring
- **`cinematic_scene_review`** — 9-dimension cinematic quality evaluation

### Production Knowledge System (§24)

6 new modules that learn from production history:

- **`production_memory`** — append-only store of successful/failed scenes, pattern usage, review outcomes
- **`pattern_library`** — reusable production pattern registry with usage-based ranking
- **`production_scoring`** — deterministic multi-dimension quality scoring (readability, composition, lighting, camera, atmosphere)
- **`review_feedback`** — structured feedback extraction from review results → improvement actions
- **`asset_knowledge_graph`** — semantic relationship graph: `commonly_used_with`, `same_environment`, `same_style`, `successful_pairing`
- **`scene_recommendation_engine`** — production-proven scene configuration recommendations from memory + patterns + graph

### Scene Planning Runtime (§27)

3 new modules + 4 Houdini nodes:

- **Scene Plan creation** — `SceneIntent` → `ScenePlan` with zones, composition rules, camera targets, asset queries
- **Scene Plan validation** — structural consistency checks on zone completeness and camera targets
- **Asset Query Generation** — structured provider-agnostic search queries from any `ScenePlan`
- New nodes: `hou_mcp_scene_plan_create`, `hou_mcp_scene_plan_validate`, `hou_mcp_scene_plan_recommend`, `hou_mcp_scene_asset_query_generate`

### Asset Intelligence Runtime (Tier 8)

New `src/runtime/assets/` package — full pipeline from queries to ranked recommendations:

- **Providers**: `SketchfabProvider`, `PolyhavenProvider`, `LocalLibraryProvider`
- **`AssetDiscoveryEngine`** — queries all providers, merges, deduplicates; no downloads, no auth
- **`AssetValidationEngine`** — category, format, scale, and conflict validation
- **`AssetRankingEngine`** — 6-factor deterministic scoring with production memory/pattern/graph boost
- **`AssetRecommendationEngine`** — full pipeline orchestrator
- New nodes: `hou_mcp_asset_discover`, `hou_mcp_asset_validate`, `hou_mcp_asset_rank`, `hou_mcp_import_asset`

### Semantic Asset Catalog & Megascans Knowledge Layer (Tier 12.7)

17-module semantic catalog in `src/runtime/assets/semantic/`:

- Environment mapping (55 environments), role classification (6 roles), storytelling mapping, lookdev tagging, cinematic usage
- Megascans metadata client (offline-safe; official API only; no scraping)
- Knowledge graph with 6 relationship types
- Priority chain: local manifest → catalog → API → fallback
- 6 Houdini nodes + 130 tests

### Semantic Vector Search & Asset Retrieval (Tier 12.8)

14-module vector search in `src/runtime/assets/vector_search/`:

- **`DeterministicEmbeddingProvider`** — 128-dim, no ML dependencies; same text → same vector always
- **`SentenceTransformersProvider`** — optional `all-MiniLM-L6-v2` upgrade when available
- **`HybridRankingEngine`** — 6-signal scoring: vector 40%, environment 20%, storytelling 15%, lookdev 10%, graph 10%, memory 5%
- 6 Houdini nodes + 175 tests

### Semantic Asset Suitability Ranking (Tier 12.85)

12-module suitability engine in `src/runtime/assets/suitability/`:

- 7-factor scoring replaces raw similarity: environment, role, style, material, scale, placement, story affinity
- Wooden Saloon Chair scores 0.905 vs Modern Plastic Chair 0.550 for western_room — correct contextual selection
- 4 Houdini nodes + 110 tests

### Local Asset Acquisition (Tier 12.5)

6-module acquisition service in `src/runtime/assets/acquisition/`:

- Scans local Fab and Megascans library directories — no network calls, no authentication
- Priority chain: registry → index → Fab scan → Megascans scan → not_found

### Online Asset Acquisition (Tier 12.9)

15-module acquisition pipeline in `src/runtime/assets/acquisition_online/`:

- Cache-first fetcher; Megascans API fallback (token via `VIBRANTE_MEGASCANS_TOKEN`)
- Persistent download queue, rate-limited scheduler, SHA-256 asset cache
- Project-local staging, append-only provenance tracking
- **Fab Socket Receiver** — started automatically at `initialize_runtime_context`; accepts push events from the Fab desktop app / Unreal Engine
- Token never stored in serialized output (`to_dict()` → `"***"`)
- 14 tests

### Asset Realization & DCC Integration (Tier 13)

12-module realization pipeline in `src/runtime/assets/realization/`:

- Import → convert → normalize → resolve dependencies → map materials → build USD → instance → realize as transaction ops → validate → review
- No bridge calls; all modules are planning-only
- SUPPORTED_FORMATS: fbx, obj, gltf, glb, usd, usda, usdc, usdz
- SUPPORTED_RENDERERS: arnold, usd_preview_surface, generic_pbr, karma

### Lookdev & Material Intelligence (Tier 14)

10-module lookdev layer in `src/runtime/lookdev/`:

- 13 built-in material categories, 5 environment patterns, 3 renderer profiles
- Recommendation priority: LookdevPatterns → MaterialKnowledge → RendererDefault
- 4-dimension review scoring; blocking findings for "no materials", "zero assignments"

### Lighting Intelligence (Tier 15)

16-module cinematic illumination pipeline in `src/runtime/lighting/`:

- 8 mood profiles, 8 lighting patterns, 10 color palettes, 8 exposure profiles
- 6-dimension review: readability, mood accuracy, story support, visual hierarchy, color harmony, exposure
- All outputs are renderer-agnostic plans — never creates Houdini lights

### Real Asset Spatial Intelligence (Tier 9.4)

AABB collision detection, clearance validation, and placement optimization in `src/runtime/assets/assembly/`:

- `CollisionDetector` — AABB-based collision detection
- `ClearanceValidator` — edge-to-edge clearance rules (machine→machine: 2.0m, vehicle→vehicle: 2.5m)
- `PlacementOptimizer` — 48-candidate radial search for collision-free positions
- `collision_count > 0` is a hard production-ready block

### Scale-Aware Spatial Placement (Tier 9.6)

Fixes the root cause of cm/m unit mismatch from Megascans assets:

- `UnitNormalizer` — detects and converts cm/mm/m/in/ft → meters; heuristic: dim > 10 → assume cm
- `AssetScaleAnalyzer` — 6 scale classes (tiny/small/medium/large/structural/hero)
- `LayoutSpacingEngine` — `spacing = radius_a + clearance_margin + radius_b`; replaces fixed `index × 3.0 m`

### Geometry Intelligence & Asset Metrics (Tier 9.7)

9-module geometry analysis pipeline in `src/runtime/assets/geometry/`:

- 10-step bounding box extraction priority chain (explicit vectors → USD extent → GLTF bounds → placement-type table → generic fallback)
- Pivot detection (5 types), ground contact detection (leg/base_ring/wheel/skid/track), support surface detection (tabletop/shelf/worktop/rack_unit)
- `AssetMetrics` is now the authoritative geometry source for all placement engines

### Environment Construction Package (§44)

14-module environment construction layer in `src/runtime/environment/`:

- 20 built-in templates across Interior, Industrial, Scientific, Sci-Fi, Outdoor, and Fantasy categories
- 8 atmosphere profiles (western_dust, industrial_haze, cold_interior, volumetric_light, etc.)
- 6-dimension review: structure, zones, anchors, support, decoration, atmosphere

### Semantic Furniture Layout Engine (Tier 9.8)

12-module relationship-based placement in `src/runtime/layout/`:

- Assets placed relative to other assets through semantic relationships — not dropped independently into zones
- Chairs orbit table at 0.9m in 4 cardinal directions; bottle placed on table surface at y=0.75m; poster wall-mounted at 1.6m
- 10 relationship types: supports, around, attached_to, against, near, hanging_from, mounted_on, etc.
- `hou_mcp_semantic_layout_debug` logs the full placement tree for every environment

### Layout Realization & Scene Constraint Solver (Tier 9.9)

12-module world-space transform pipeline in `src/runtime/layout_realization/`:

- `LayoutPlan` → `ResolvedSceneLayout` with concrete tx/ty/tz/rx/ry/rz for every asset
- 7-stage pipeline: cluster → surface → wall → decoration → collision → constraint → assemble
- `LayoutApplicationEngine` is the only module that calls `get_bridge()` — isolated adapter
- Parent-child pairs are exempt from AABB collision checks

### Structural Environment Realization (Tier 10.0)

13-module architectural shell builder in `src/runtime/environment_realization/`:

- Floor + walls + ceiling + doors + windows + beams + columns for all 55 environments
- Outdoor environments receive a 50×50m ground plane with no walls/ceiling
- All elements converted to Houdini transaction op dicts for safe application

### Structural Asset Classification (Tier 10.3)

9-module pre-layout classifier in `src/runtime/structure/`:

- 3-signal pipeline: geometry dimensions + metadata keywords + environment affinity
- 20 structural roles: wall, doorway, beam, column, fireplace, archway, stair, railing, etc.
- Doorways, beams, and columns are automatically routed away from the furniture pipeline
- 25 environments with affinity tables; stone arch scores 0.90 in castle_hall, ≤0.50 in western_room

### Environment Shell Construction (Tier 10.4)

6-phase environment-first pipeline in `src/runtime/environment_shell/`:

- Phase 1–6: floor → walls → ceiling → structural anchors → structural placement → shell validation
- `ENVIRONMENT_NOT_READY` gate is BLOCKING — furniture placement cannot proceed until gate passes
- `hou_mcp_shell_gate` has dual exec output: `exec_out_ready` and `exec_out_blocked`

### Structural Openings & Architectural Features (Tier 10.5)

Door/window openings, fireplace/beam/shelf attachment, and `/obj/sh_*` geometry in `src/runtime/architectural_features/`.

### Scene Reality Validation (Tier 14.3)

5-rule validation in `src/runtime/scene_validation/`:

- Support surface, occupancy AABB, relationship graph, human plausibility, orphan detection
- Replaces bare `production_ready` bool with `geometry_valid + semantic_valid + plausibility_valid + production_ready`

### Asset Identity Audit (Tier 14.4.5)

8-module identity auditor in `src/runtime/asset_identity/`:

- 3 new `vibrante_` user-data keys on every Houdini node (`vibrante_asset_id`, `vibrante_asset_name`, `vibrante_asset_category`)
- Opaque ID detection, role/engine and role/category cross-validation

### Reality Intelligence (Tier 15.0+)

16-module senior-artist intelligence layer in `src/runtime/reality/`:

- **Core rule**: never ask "Can I place this asset?" — always ask "Would a human intentionally place this here?"
- **Reality First Rule**: geometry wins over metadata when the two conflict
- `GeometryInspector` — BRIDGE: reads actual Houdini geometry; `reconcile()` enforces GEOMETRY WINS
- `CorrectionApplier` — BRIDGE: applies geometry fixes via `set_parms`; all other modules are pure planning
- Support rule table: bottle requires table/shelf/bar; chair requires table/desk/fireplace/bar within 2.0m; fireplace requires wall
- `FloatingObjectDetector` — `raycast_down()` for any asset with bottom_y > floor + 0.10m
- `VisualReviewEngine` — 9 criteria ALL required: physically_plausible, functionally_usable, architecturally_valid, visually_believable, compositionally_balanced, relationship_consistent, no_floating_objects, no_orphan_assets, no_impossible_placements

### Environment Expansion Pack (§39)

55 production environments across 9 categories in `src/runtime/environments/`:

- Industrial (8): industrial_hangar, warehouse, shipyard, oil_refinery, power_station, mining_facility…
- Scientific (6): robotics_lab, research_lab, medical_lab, clean_room, biohazard_facility, control_room
- Military (5), Sci-Fi (6), Urban (6), Interior (8), Nature (7), Fantasy (5), Post-Apocalyptic (4)
- All 55 environments have lighting profiles, storytelling narratives, lookdev keywords, and workflow packs

### `build_scene_from_assets` MCP Tool

New MCP tool registered in `MCPToolRegistry`:

- **Required first step** for all scene-building intents — real assets, never primitives
- Pipeline: intent → keyword extraction → local catalog search → Megascans import → structural routing → semantic layout → layout realization → Houdini transforms
- `query_examples()` now returns a concrete `scene_building_example` dict for scene intents

### 200+ New Houdini MCP Nodes

Complete node set for the full assembly pipeline in `plugins/houdini/v_nodes_houdini/`:

- Scene intent: `hou_mcp_scene_intent_extract`, `hou_mcp_scene_intent_validate`, `hou_mcp_scene_intent_enrich`, `hou_mcp_scene_intent_recommend`
- Scene planning: `hou_mcp_scene_plan_create`, `hou_mcp_scene_plan_validate`, `hou_mcp_scene_plan_recommend`
- Asset pipeline: `hou_mcp_asset_discover`, `hou_mcp_asset_validate`, `hou_mcp_asset_rank`, `hou_mcp_asset_suitability`, `hou_mcp_asset_retrieval`
- Layout: `hou_mcp_layout_cluster`, `hou_mcp_surface_placement`, `hou_mcp_layout_graph`, `hou_mcp_realize_layout`, `hou_mcp_apply_layout`
- Environment: `hou_mcp_build_shell`, `hou_mcp_shell_gate`, `hou_mcp_build_environment`, `hou_mcp_environment_blueprint`
- Structural: `hou_mcp_structural_classifier`, `hou_mcp_geometry_analyze`, `hou_mcp_collision_review`
- Lookdev & lighting: `hou_mcp_material_recommend`, `hou_mcp_lighting_strategy`, `hou_mcp_lighting_plan`, `hou_mcp_lighting_review`
- Reality: `hou_mcp_reality_check`, `hou_mcp_reality_correction`, `hou_mcp_visual_review`, `hou_mcp_geometry_truth`
- Workflow: `hou_mcp_workflow_pack`, `hou_mcp_workflow_recommend`, `hou_mcp_workflow_execute`

---

## Changed

- **`vibrante_node.json`** — expanded from 2 to 14 env vars; new acquisition and storage paths are optional (backward-compatible with v2.4.0 installs)
- **`RECOMMENDED_EXECUTION_FLOW`** — step 7 added: `hou_mcp_build_scene_from_intent` for scene intents (geometry before lights)
- **`initialize_runtime_context`** — now reports asset path status, starts Fab socket receiver, and pushes `vibrante_node.json` values into the live Houdini session
- **`query_examples()`** — returns `scene_building_example` dict for scene-building intents; redirects callers to `build_scene_from_assets` (not `plan_scene + execute_workflow_transaction`)
- **`workflow_templates`** — new `scene_from_assets` template for the full Tier 12.8 → 10.3.5 → 9.8 → 9.9 pipeline
- **`pythonrc.py`** — Houdini startup now prints `VIBRANTE_MEGASCANS_LIBRARY` and `VIBRANTE_ASSET_CACHE` status
- **`run_vibrante_mcp.py`** — documentation updated with Claude Code MCP setup instructions (`claude mcp add-json`)
- **Release notes** moved from repository root to `releases/` directory; root keeps only the current release

---

## Fixed

- `asset_cache_manager.py` — deadlock in `remove_asset()` caused `tests/unit/test_asset_cache_manager.py` to hang forever (see §10.13 in CLAUDE.md)

---

## Dependencies

- **`networkx`** added to `requirements.txt` — required by asset knowledge graph modules

---

## Migration Notes

### Upgrading from v2.4.0

No breaking changes. All v2.4.0 workflows, nodes, and MCP tools continue to work unchanged.

**Optional new configuration** in `vibrante_node.json`:

```json
{ "VIBRANTE_MEGASCANS_LIBRARY": "<path to local Megascans Downloaded/3d>" },
{ "VIBRANTE_FAB_LIBRARY":       "<path to local Fab Library>" },
{ "VIBRANTE_ASSET_STORAGE":     "<root for Vibrante databases, e.g. E:/vibrante_db>" },
{ "VIBRANTE_ASSET_CACHE":       "<subfolder for vector index, e.g. E:/vibrante_db/vector_cache>" }
```

All are optional — without them, asset discovery falls back to local file scan only and the vector index is not persisted between sessions.

**Install `networkx`** if using asset knowledge graph features:

```bash
pip install networkx
```

### Scene-Building Intents

For prompts like "build a western room" or "create a sci-fi corridor":

- Use `build_scene_from_assets` (new MCP tool) — this runs the full Tier 12.8 → layout → Houdini pipeline with real assets
- Do NOT use `plan_scene + execute_workflow_transaction` for environment building — that path handles primitive geometry only

---

## Known Limitations

- `SentenceTransformersProvider` requires `sentence_transformers` to be pre-installed and the `all-MiniLM-L6-v2` model to be cached; it silently falls back to `DeterministicEmbeddingProvider` if unavailable
- `GeometryInspector.reconcile()` requires a live Houdini bridge; `build_op_dicts()` provides a dry-run path for testing
- Online Megascans download requires `VIBRANTE_MEGASCANS_TOKEN` — without it the system operates in offline mode (local library scan only)

---

## Stats

| Metric | Count |
|---|---|
| New runtime modules | 120+ |
| New Houdini MCP nodes | 200+ |
| New unit test files | 250+ |
| Intelligence tiers | Tiers 2.9, 8, 9.4–9.9, 10.0–10.5, 12.5–12.9, 13–15.0+ |
| Supported environments | 55 |
| New capabilities registered | 80+ |
