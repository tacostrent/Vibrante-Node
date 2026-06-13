# Vibrante-Node — Full-Stack Tier Audit Prompt
## Post-MCP-Connection Verification of All Runtime Tiers

**Version:** 2.5.0+  
**Usage:** Paste this document into the Claude conversation immediately after the MCP connection to Houdini is established. Execute each phase in sequence. Report PASS / FAIL / WARN per check.

---

## How to Run

After the Houdini–Claude MCP connection is live, send:

```
Run the Vibrante full-stack tier audit. Follow VIBRANTE_TIER_AUDIT.md exactly.
Execute every phase in order. For each check call the exact MCP tool listed.
After each check report: CHECK NAME | PASS / FAIL / WARN | one-line finding.
At the end print the complete summary table.
```

---

## Phase 0 — MCP Connection & Bridge Alive

> Verify the transport is up and Houdini is responding before any tier logic runs.

### 0.1 Runtime Bootstrap

```
TOOL: initialize_runtime_context
ARGS: {}
```

**Pass if:**
- `ok == true`
- `version` contains `"2.5.0"` (or higher)
- `bridge_status` is `"connected"` or ping latency is reported
- `execution_rules` list is non-empty (≥ 7 rules)

**Fail diagnosis:** MCP server not running; Houdini port not open; `VIBRANTE_NODE_APP` env var unset.

---

### 0.2 Houdini Bridge Ping

```
TOOL: query_scene_context
ARGS: {}
```

**Pass if:**
- `ok == true`
- `hip_file` is a non-empty string
- `houdini_version` is returned
- `frame_range` is a 2-element list

**Fail diagnosis:** `vibrante_hou_server.py` not running inside Houdini; wrong port (`VIBRANTE_HOU_PORT`).

---

### 0.3 Configuration Check

```
TOOL: check_vibrante_config
ARGS: {}
```

**Pass if:**
- `all_configured == true`
- `missing_critical` is an empty list
- `VIBRANTE_MEGASCANS_LIBRARY` path exists on disk

**Warn if:** `VIBRANTE_MEGASCANS_TOKEN` or `VIBRANTE_ASSET_CACHE` missing (non-critical for offline use).

**Fail diagnosis:** Follow `how_to_fix` in the tool response for each missing variable.

---

## Phase 1 — Runtime Identity & Capability Surface

> Verify version, capability count, and all 12 MCP tools are registered.

### 1.1 Capability Enumeration

```
TOOL: query_capabilities
ARGS: {"type": "all"}
```

**Pass if:**
- Total capabilities ≥ 150
- `houdini_op` count ≥ 9
- `semantic_operation` count ≥ 100
- `runtime_service` count ≥ 40
- `dcc_integration` list contains `"houdini"`

---

### 1.2 Tier Capability Cross-Check

Verify the following specific capability IDs are present in the response from 1.1.  
Call `query_capabilities` once — check all IDs in the result.

| Capability ID | Tier | Must Exist |
|---|---|---|
| `asset_realization` | 13 | YES |
| `asset_import` | 13 | YES |
| `material_intelligence` | 14 | YES |
| `lookdev_patterns` | 14 | YES |
| `lighting_intelligence` | 15 | YES |
| `lighting_strategy` | 15 | YES |
| `fab_library_scan` | 12.5 | YES |
| `asset_acquisition` | 12.5 | YES |
| `semantic_asset_catalog` | 12.7 | YES |
| `semantic_vector_search` | 12.8 | YES |
| `asset_retrieval` | 12.8 | YES |
| `hybrid_asset_ranking` | 12.8 | YES |
| `asset_suitability_ranking` | 12.85 | YES |
| `online_asset_acquisition` | 12.9 | YES |
| `spatial_metadata` | 9.4 | YES |
| `collision_detection` | 9.4 | YES |
| `geometry_analysis` | 9.7 | YES |
| `semantic_layout` | 9.8 | YES |
| `environment_blueprints` | 9.5/44 | YES |
| `environment_construction` | 9.5/44 | YES |
| `structural_asset_classification` | 10.3 | YES |
| `geometry_role_detection` | 10.3 | YES |
| `environment_realization` | 10.0 | YES |
| `room_generation` | 10.0 | YES |
| `environment_registry` | 39 | YES |
| `environment_expansion` | 39 | YES |

**Pass if:** All 26 capability IDs present.  
**Fail diagnosis:** Missing tier was not registered in `capability_registry.py`.

---

### 1.3 Runtime Services Alive

```
TOOL: query_runtime_state
ARGS: {}
```

**Pass if:**
- `transaction_manager.active == true`
- `scene_cache.active == true`
- `audit_store.active == true`
- `execution_scheduler.active == true`
- No service reports `status == "error"`

---

## Phase 2 — Houdini Bridge Layer (Tier 1 / 2)

> Verify basic Houdini operations route correctly through the transaction system.

### 2.1 Plan a Simple Scene Operation

```
TOOL: plan_scene
ARGS: {
  "intent": "create a geo node in /obj",
  "context": {}
}
```

**Pass if:**
- `ok == true`
- `operations` list is non-empty
- `intent_parsed.primary_intent` is non-empty
- `risk_level` is one of: `"low"`, `"medium"`, `"high"`

---

### 2.2 Preview Execution (no commit)

Use the plan from 2.1.

```
TOOL: preview_execution
ARGS: {
  "operations": <operations from 2.1>
}
```

**Pass if:**
- `ok == true`
- `resource_estimate` is returned
- `validation_warnings` is a list (may be empty)
- `risk_prediction` is returned

---

### 2.3 Validate Plan

```
TOOL: validate_execution_plan
ARGS: {
  "operations": <operations from 2.1>
}
```

**Pass if:**
- `ok == true`
- `errors` list is empty
- `risk_level` is not `"critical"`

---

## Phase 3 — Workflow Templates & Examples (Tier 2 Planning)

### 3.1 Template Listing

```
TOOL: query_workflow_templates
ARGS: {}
```

**Pass if:**
- `ok == true`
- At least 5 templates returned
- Templates include tags like `"environment"`, `"lighting"`, `"assets"`

---

### 3.2 Example Retrieval

```
TOOL: query_examples
ARGS: {"intent": "build western room scene"}
```

**Pass if:**
- `ok == true`
- At least 1 example returned
- Example contains `operations` or `steps`

---

## Phase 4 — Asset Discovery Layer (Tier 8 + 12.5 + 12.7 + 12.8)

> Verify the full asset intelligence stack: local library → catalog → vector search → retrieval.

### 4.1 Intent Parser (Tier 12.8)

Execute via `plan_scene` with a rich intent:

```
TOOL: plan_scene
ARGS: {
  "intent": "assemble a dark atmospheric western saloon with wooden chairs around a bar counter, oil lanterns on the walls, and wanted posters",
  "context": {"environment": "saloon"}
}
```

**Pass if:**
- `intent_parsed.environment` is `"saloon"` or `"western_room"`
- `intent_parsed.keywords` contains at least 4 terms (chair, lantern, bar, poster, etc.)
- `intent_parsed.role` or `intent_parsed.storytelling` is non-empty
- Plan `operations` list is non-empty

---

### 4.2 Asset Search (Tier 12.7 + 12.8 + 12.85)

```
TOOL: build_scene_from_assets
ARGS: {
  "intent": "wooden chair saloon",
  "top_k": 3,
  "parent": "/obj",
  "environment": "western_room",
  "room_half_width": 5.0
}
```

**Pass if:**
- `ok == true`
- `asset_count` ≥ 1
- `source` is one of: `"catalog"`, `"local_library"`, `"megascans_api"`
- `layout_pipeline_report.routing_ok == true`

**Warn if:** `asset_count == 0` and source is `"none"` — library may be empty; check `VIBRANTE_MEGASCANS_LIBRARY`.

---

## Phase 5 — Structural Routing Verification (Tier 10.3 + 10.3.5)

> Confirm that StructuralRoutingEngine is wired into `build_scene_from_assets`.

### 5.1 Pipeline Report Contains Routing Fields

Use the response from Phase 4.2.

**Check `layout_pipeline_report` for:**

| Field | Expected |
|---|---|
| `structural_assets_routed` | integer ≥ 0 |
| `furniture_assets_to_layout` | integer ≥ 0 |
| `routing_ok` | `true` |

**Pass if:** All three fields exist in `layout_pipeline_report`.  
**Fail diagnosis:** Routing phase not wired — `mcp_tool_registry.py` is missing Phase 1.5 insertion.

---

### 5.2 Structural Split Correctness

If `asset_count ≥ 2` from Phase 4.2:

**Pass if:**
```
structural_assets_routed + furniture_assets_to_layout == imported_assets
```

**Warn if** both counts are 0 — no assets were imported, skip.

---

### 5.3 Structural Classification Module (Tier 10.3) Import Check

Run via `plan_scene` with a structural asset intent:

```
TOOL: plan_scene
ARGS: {
  "intent": "import old wooden beam and historic door into western room",
  "context": {"environment": "western_room"}
}
```

**Pass if:**
- `intent_parsed` identifies structural asset types
- Plan does not route structural assets to furniture layout steps

---

## Phase 6 — Spatial Intelligence (Tier 9.4 → 9.9)

> Verify the full spatial/layout pipeline fires and produces valid transforms.

### 6.1 Layout Pipeline Metrics

From the Phase 4.2 response:

**Pass if `layout_pipeline_report` contains:**

| Field | Pass Condition |
|---|---|
| `assets_with_metrics` | ≥ 1 (AssetMetrics ran) |
| `assets_in_clusters` | ≥ 0 (may be 0 for single asset) |
| `assets_resolved` | ≥ 1 (transforms applied) |
| `collision_count_after` | 0 (collisions resolved) |
| `constraint_violations` | 0 |

**Warn if** `assets_resolved == 0` and `asset_count > 0` — layout realization failed silently.

---

### 6.2 Furniture Cluster Formation (Tier 9.8)

```
TOOL: build_scene_from_assets
ARGS: {
  "intent": "wooden table with four chairs around it and a bottle on the surface",
  "top_k": 6,
  "parent": "/obj/western_room_test",
  "environment": "western_room",
  "room_half_width": 5.0
}
```

**Pass if:**
- `layout_pipeline_report.assets_in_clusters` ≥ 2
- `layout_pipeline_report.assets_on_surfaces` ≥ 1 (bottle on table)
- `layout_pipeline_report.collision_count_after == 0`

---

## Phase 7 — Geometry Intelligence (Tier 9.7)

### 7.1 AssetMetrics Run Confirmation

From Phase 6.1:

**Pass if:**
- `assets_with_metrics ≥ 1`
- `assets_with_metrics` equals or is close to `imported_assets` (gap ≤ 1 for assets without bbox data)

**Fail diagnosis:** `AssetMetricsBuilder` import failing — check `src/runtime/assets/geometry/asset_metrics.py`.

---

## Phase 8 — Environment Realization (Tier 10.0)

> Verify that room shell generation is available and would produce a complete shell.

### 8.1 Room Shell Completeness via query_capabilities

From Phase 1.1 output, verify:

**Pass if** ALL of the following capability IDs are present:
- `room_generation`
- `wall_generation`  
- `floor_generation`
- `ceiling_generation`
- `opening_generation`
- `beam_generation`
- `architectural_validation`

---

### 8.2 Environment Blueprint Available (Tier 44)

```
TOOL: query_capabilities
ARGS: {"type": "runtime_service"}
```

**Pass if** `environment_blueprints` and `environment_construction` are in the runtime service list.

---

## Phase 9 — Lookdev Intelligence (Tier 14)

### 9.1 Lookdev Capabilities Present

From Phase 1.1, verify:

| Capability ID | Must Exist |
|---|---|
| `material_intelligence` | YES |
| `lookdev_patterns` | YES |
| `material_recommendation` | YES |
| `material_assignment` | YES |
| `lookdev_review` | YES |
| `renderer_profiles` | YES |

**Pass if:** All 6 present.

---

### 9.2 Lookdev via Workflow Template

```
TOOL: query_workflow_templates
ARGS: {"tags": ["lookdev", "material"]}
```

**Pass if:**
- `ok == true`
- At least 1 template returned with lookdev/material tag

**Warn if** 0 results — lookdev workflow packs may not be registered.

---

## Phase 10 — Lighting Intelligence (Tier 15)

### 10.1 Lighting Capabilities Present

From Phase 1.1, verify:

| Capability ID | Must Exist |
|---|---|
| `lighting_intelligence` | YES |
| `lighting_strategy` | YES |
| `lighting_planning` | YES |
| `lighting_review` | YES |
| `lighting_readability` | YES |
| `lighting_recommendation` | YES |

**Pass if:** All 6 present.

---

### 10.2 Lighting Plan via Scene Plan

```
TOOL: plan_scene
ARGS: {
  "intent": "dramatic cinematic key light for western saloon hero shot, warm lantern practicals, heavy atmosphere",
  "context": {"environment": "saloon", "mood": "dramatic"}
}
```

**Pass if:**
- `ok == true`
- `operations` contains at least one lighting operation
- `intent_parsed` identifies `mood` or `lighting_intent`

---

## Phase 11 — Asset Realization Pipeline (Tier 13)

### 11.1 Realization Capabilities Present

From Phase 1.1, verify:

| Capability ID | Must Exist |
|---|---|
| `asset_realization` | YES |
| `asset_import` | YES |
| `asset_conversion` | YES |
| `asset_dependency_resolution` | YES |
| `usd_asset_generation` | YES |

**Pass if:** All 5 present.

---

## Phase 12 — Online Acquisition (Tier 12.9)

### 12.1 Acquisition Capabilities Present

From Phase 1.1, verify:

| Capability ID | Must Exist |
|---|---|
| `online_asset_acquisition` | YES |
| `asset_fetching` | YES |
| `download_management` | YES |
| `asset_caching` | YES |
| `project_asset_staging` | YES |
| `asset_provenance_tracking` | YES |

**Pass if:** All 6 present.

---

### 12.2 Fab Library Scan Capabilities

Verify from Phase 1.1:

| Capability ID | Must Exist |
|---|---|
| `fab_library_scan` | YES |
| `megascans_library_scan` | YES |
| `library_index` | YES |
| `library_watch` | YES |

---

## Phase 13 — Environment Expansion (55 Environments, Tier 39)

### 13.1 Environment Registry Capabilities Present

From Phase 1.1, verify:

| Capability ID | Must Exist |
|---|---|
| `environment_registry` | YES |
| `environment_expansion` | YES |
| `environment_statistics` | YES |
| `environment_recommendation` | YES |
| `environment_workflow_pack` | YES |

---

### 13.2 Multi-Environment Intent Resolution

```
TOOL: plan_scene
ARGS: {
  "intent": "medieval castle hall with stone floor and banners",
  "context": {}
}
```

**Pass if:**
- `intent_parsed.environment` is `"castle_hall"` (not `"western_room"` or generic)

```
TOOL: plan_scene
ARGS: {
  "intent": "space station orbital module sci-fi corridor",
  "context": {}
}
```

**Pass if:**
- `intent_parsed.environment` is `"space_station"` or `"sci_fi_corridor"`

---

## Phase 14 — End-to-End Pipeline (Full Audit Shot)

> This is the master integration test. It exercises every layer in sequence.

### 14.1 Full Western Room Scene Build

```
TOOL: build_scene_from_assets
ARGS: {
  "intent": "western saloon with wooden table, four chairs around it, oil lanterns on walls, whiskey bottles on bar counter, wanted poster on north wall",
  "top_k": 8,
  "parent": "/obj/audit_western_room",
  "environment": "western_room",
  "room_half_width": 5.0
}
```

**Pass criteria (all must be true):**

| Check | Expected |
|---|---|
| `ok == true` | YES |
| `asset_count` ≥ 3 | YES |
| `layout_pipeline_report.routing_ok == true` | YES |
| `layout_pipeline_report.structural_assets_routed ≥ 0` | YES |
| `layout_pipeline_report.furniture_assets_to_layout ≥ 1` | YES |
| `layout_pipeline_report.assets_resolved ≥ 1` | YES |
| `layout_pipeline_report.collision_count_after == 0` | YES |
| `layout_pipeline_report.constraint_violations == 0` | YES |
| `layout_pipeline_report.production_ready == true` | YES |
| `END_TO_END_LAYOUT_STATUS == "PASS"` | YES |
| `pipeline_errors` is empty or warnings only | YES |

---

### 14.2 Post-Build Review

```
TOOL: review_execution
ARGS: {
  "execution_result_json": <full response from 14.1 as JSON string>,
  "plan_json": "{}"
}
```

**Pass if:**
- `ok == true`
- `review.outcome` is `"success"` or `"partial_success"`
- `intent_match_score` ≥ 0.60

---

## Phase 15 — Node Parameter Inspection

### 15.1 Verify Imported Assets Have Correct Transforms

If `imported_paths` from Phase 14.1 is non-empty, pick the first path:

```
TOOL: query_node_parameters
ARGS: {"node_path": "<first path from imported_paths>"}
```

**Pass if:**
- `ok == true`
- `parameters` contains `tx`, `ty`, `tz`, `sx`, `sy`, `sz`
- `ty` is a non-negative float (asset is at or above y=0)

---

## Audit Summary Table

After running all phases, produce this table:

```
╔══════════════════════════════════════════════════════════════════════════╗
║                   VIBRANTE FULL-STACK TIER AUDIT                        ║
║                   Environment: [current hip file]                        ║
║                   Date: [today]                                          ║
╠════════╦══════════════════════════════════════════╦══════════╦══════════╣
║ Phase  ║ Check                                    ║ Result   ║ Finding  ║
╠════════╬══════════════════════════════════════════╬══════════╬══════════╣
║ 0.1    ║ Runtime bootstrap (initialize_runtime)   ║ PASS/FAIL║          ║
║ 0.2    ║ Houdini bridge ping (query_scene)         ║ PASS/FAIL║          ║
║ 0.3    ║ Config check (check_vibrante_config)      ║ PASS/WARN║          ║
║ 1.1    ║ Capability count ≥ 150                    ║ PASS/FAIL║          ║
║ 1.2    ║ All 26 tier capability IDs present        ║ PASS/FAIL║          ║
║ 1.3    ║ Runtime services active                   ║ PASS/FAIL║          ║
║ 2.1-3  ║ Plan / preview / validate (Tier 2)        ║ PASS/FAIL║          ║
║ 3.1-2  ║ Templates + examples available            ║ PASS/FAIL║          ║
║ 4.1    ║ Intent parser (Tier 12.8)                 ║ PASS/FAIL║          ║
║ 4.2    ║ Asset search + import (Tier 12.x)         ║ PASS/WARN║          ║
║ 5.1    ║ Routing fields in pipeline report         ║ PASS/FAIL║          ║
║ 5.2    ║ Structural split correct (10.3.5)         ║ PASS/WARN║          ║
║ 5.3    ║ Structural classification plan            ║ PASS/FAIL║          ║
║ 6.1    ║ Layout pipeline metrics (Tier 9.x)        ║ PASS/FAIL║          ║
║ 6.2    ║ Cluster + surface placement (Tier 9.8)    ║ PASS/WARN║          ║
║ 7.1    ║ AssetMetrics ran (Tier 9.7)               ║ PASS/FAIL║          ║
║ 8.1-2  ║ Room shell capabilities (Tier 10.0)       ║ PASS/FAIL║          ║
║ 9.1    ║ Lookdev capabilities (Tier 14)            ║ PASS/FAIL║          ║
║ 10.1-2 ║ Lighting capabilities + plan (Tier 15)    ║ PASS/FAIL║          ║
║ 11.1   ║ Asset realization capabilities (Tier 13)  ║ PASS/FAIL║          ║
║ 12.1-2 ║ Acquisition capabilities (Tier 12.9+12.5) ║ PASS/FAIL║          ║
║ 13.1-2 ║ 55 environments + routing (Tier 39)       ║ PASS/FAIL║          ║
║ 14.1   ║ End-to-end build_scene_from_assets        ║ PASS/FAIL║          ║
║ 14.2   ║ Post-build review score ≥ 0.60            ║ PASS/FAIL║          ║
║ 15.1   ║ Node transforms applied (ty ≥ 0)          ║ PASS/FAIL║          ║
╠════════╩══════════════════════════════════════════╩══════════╩══════════╣
║ OVERALL: PASS / PARTIAL / FAIL                                           ║
║ Pass: ___ / 25   Warn: ___ / 25   Fail: ___ / 25                        ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Failure Diagnosis Quick Reference

| Symptom | Most Likely Cause | Fix |
|---|---|---|
| Phase 0.1 fails (ok=false) | MCP server not running | Start Vibrante-Node from Houdini menu |
| Phase 0.2 fails (bridge ping) | `vibrante_hou_server.py` not loaded | Houdini restart; check `pythonrc.py` output |
| Phase 0.3 fails (config) | `VIBRANTE_NODE_APP` not set | Edit `vibrante_node.json` with correct paths |
| Phase 1.2 fails (missing caps) | Tier module not registered | Check `capability_registry.py` for missing `register()` calls |
| Phase 4.2 warns (0 assets) | Empty local library | Run Quixel Bridge export to `VIBRANTE_MEGASCANS_LIBRARY` |
| Phase 5.1 fails (routing fields missing) | Phase 1.5 not in `mcp_tool_registry.py` | Verify `structural_routing_engine` import is at line ~1148 |
| Phase 5.2 fails (sum mismatch) | Routing engine crashed silently | Check `pipeline_errors` field for `StructuralRoutingEngine:` entry |
| Phase 6.1 fails (assets_resolved=0) | Layout realization failed | Check `pipeline_errors` for `LayoutRealizationEngine:` entry |
| Phase 6.2 warns (clusters=0) | Only 1 asset imported | Need ≥ 2 assets (chair + table) for cluster to form |
| Phase 7.1 fails (metrics=0) | `AssetMetricsBuilder` import error | Check `src/runtime/assets/geometry/asset_metrics.py` |
| Phase 14.1 fails (collision_after > 0) | Collisions not resolved | Check `CollisionSolver` and asset bbox data |
| Phase 14.2 fails (score < 0.60) | Intent mismatch or no assets placed | Review `pipeline_errors` and asset search results |

---

## Minimum Viable Pass (MVP) Definition

The system is considered **production-ready** after this audit if:

1. Phase 0.1, 0.2 — both PASS (bridge alive)
2. Phase 1.2 — PASS (all 26 capability IDs present)
3. Phase 5.1 — PASS (routing fields in pipeline report)
4. Phase 14.1 — `END_TO_END_LAYOUT_STATUS == "PASS"`
5. Phase 14.1 — `collision_count_after == 0`
6. Phase 14.1 — `routing_ok == true`

If any of the 6 MVP checks fail, the pipeline is not production-ready regardless of other pass counts.

---

## Notes

- **Tier 12.9 online acquisition** requires `VIBRANTE_MEGASCANS_TOKEN` to be set. Without it, checks 12.1 verify capability registration only (module is available, network is disabled).
- **Phase 6.2 (clusters)** requires at least a table + chair asset pair to be found in the local library. With an empty library, this check downgrades to WARN (not FAIL).
- **Phase 14** is the definitive integration test. All previous phases are preparatory. If Phase 14 passes completely, the full Tier 2 → 9.4 → 9.7 → 9.8 → 9.9 → 10.3 → 10.3.5 chain is operational.
- **Structural classification accuracy** depends on asset name/tag metadata. Poor Megascans asset naming will produce low-confidence classifications; this is expected and does not indicate a code defect.
