# Release Notes — Vibrante-Node v2.4.0

**Released:** 2026-05-26
**Type:** Minor — New features, backward-compatible

---

## Highlights

v2.4.0 is the largest feature release in Vibrante-Node's history. It introduces a complete **AI-assisted orchestration runtime layer** — six tiers of deterministic, validated, transactional infrastructure that enables AI agents (Claude, Codex, GPT) to plan, preview, execute, and review Houdini operations through a structured MCP server interface. Every mutation still goes through the full validation + constraint + transaction pipeline — no arbitrary execution, no autonomous mutation.

---

## New Features

### MCP Operational Runtime (Tier 6)

Vibrante-Node is now a **full MCP server**. Run `scripts/run_vibrante_mcp.py` to start the server, then add it to Claude Desktop, Codex CLI, or Cursor. External AI clients get 12 structured semantic tools — planning, preview, execution, review — with no raw Houdini API exposure.

**Claude Desktop** (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "vibrante": {
      "command": "python",
      "args": ["D:/Vibrante-Node/source/scripts/run_vibrante_mcp.py"]
    }
  }
}
```

The 12 MCP tools (organized into Runtime / Knowledge / Planning / Execution categories):
- `initialize_runtime_context` — call first; returns bootstrap data + system prompt
- `query_runtime_state` — live metrics and module status
- `query_scene_context` — structured Houdini scene snapshot
- `query_capabilities` — enumerate available operations
- `query_workflow_templates` — browse 7 built-in templates (pyro, karma, USD export, etc.)
- `query_examples` — execution examples for a named intent
- `query_node_parameters` — **new** — list all parameter names + values for any Houdini node
- `plan_scene` — NL prompt → AI plan (no execution)
- `preview_execution` — validate + risk-predict operations without executing
- `validate_execution_plan` — structural + constraint pass only
- `execute_workflow_transaction` — execute via transaction system with optional dry-run + approval gate
- `review_execution` — post-execution intent-match review

### AI Orchestration Tiers 1–5

The `src/runtime/` module contains 40+ deterministic runtime modules spanning six tiers:

| Tier | Modules | Purpose |
|---|---|---|
| 1 | `mcp_runtime`, `houdini_runtime`, `scene_cache` | MCP client sessions, semantic Houdini ops, TTL cache |
| 2 | `transaction_manager`, `scene_cache` (extended) | Transaction lifecycle, rollback, graph diff |
| 2.5 | `dependency_graph`, `validation_engine`, `audit_store`, `execution_scheduler` | Pre-execution validation, audit trail, serialized execution |
| 2.75 | `semantic_registry`, `semantic_execution`, `capability_registry`, `workflow_templates`, `resource_estimator`, `runtime_constraints` | Named semantic operations, policy gate, template system |
| 3 | `ai_planner`, `intent_parser`, `contextual_reasoning`, `plan_validator`, `execution_explainer`, `approval_pipeline`, `planning_memory`, `llm_provider` | AI planning pipeline (deterministic-first, LLM-enhanced) |
| 4 | `distributed_runtime`, `agent_runtime`, `multi_dcc_runtime`, `knowledge_graph`, `semantic_memory`, `worker_runtime`, `workflow_federation`, `runtime_federation_api`, `mcp_server_runtime` | Distributed execution, supervised agents, multi-DCC routing |
| 5 | `workflow_optimizer`, `runtime_analytics`, `predictive_execution`, `orchestration_heuristics`, `recommendation_engine`, `resource_optimizer`, `failure_intelligence`, `execution_quality`, `studio_knowledge` | Advisory intelligence — no execution authority |

### New Nodes

**Generic MCP nodes** (bundled with every install, `category: "MCP"`):
- `mcp_server_init` — configure and open an MCP session
- `mcp_list_tools` — enumerate tools on a registered server
- `mcp_call_tool` — invoke a tool with JSON arguments

**Houdini AI nodes** (Houdini plugin only, `plugins/houdini/v_nodes_houdini/`):

| Node | Purpose |
|---|---|
| `hou_mcp_scene_context` | Structured scene snapshot for AI agents (linchpin node) |
| `hou_mcp_build_node_chain` | Build a Houdini network from a JSON spec |
| `hou_mcp_transaction` | Wrap mutations in a begin/commit/rollback boundary |
| `hou_mcp_graph_diff` | Read the scene dirty-state ledger after a transaction |
| `hou_mcp_execution_preview` | Preview operations without executing (no bridge calls) |
| `hou_mcp_replay_transaction` | Deterministically replay a recorded transaction |
| `hou_mcp_semantic_execute` | Translate + execute a named semantic intent |
| `hou_mcp_runtime_capabilities` | Query the capability registry |
| `hou_mcp_workflow_templates` | Browse templates and resolve to op lists |
| `hou_mcp_ai_plan` | Parse NL prompt → validated execution plan |
| `hou_mcp_ai_preview` | Validate an AI plan without executing |
| `hou_mcp_ai_execute` | Execute a validated AI plan with approval gate |
| `hou_mcp_ai_review` | Post-execution intent-match review |
| `hou_mcp_runtime_analytics` | Runtime execution metrics and trends |
| `hou_mcp_predictive_execution` | Heuristic failure prediction before execution |
| `hou_mcp_workflow_optimizer` | Advisory plan analysis and optimization tips |
| `hou_mcp_recommendation_engine` | Workflow / template / strategy recommendations |
| `hou_mcp_execution_quality` | Post-execution orchestration quality scoring |
| `hou_mcp_runtime_federation` | Register / discover peer runtimes |
| `hou_mcp_distributed_execute` | Execute on a distributed worker pool |
| `hou_mcp_agent_plan` | Submit a supervised agent proposal (no direct execution) |
| `hou_mcp_remote_worker` | Register / heartbeat / acquire remote workers |
| `hou_mcp_knowledge_query` | Query the production knowledge graph |

**Utility nodes:**
- `list_images_recursive` — recursively list image files in a directory with filtering

### New Bridge Methods (`src/utils/hou_bridge.py`)

- `bridge.get_selection()` — returns currently selected node paths; `[]` in headless Houdini
- `bridge.network_summary(path)` — returns children with `{name, type, path, category}` in one round-trip

### Subprocess Crash Logging

The Houdini plugin now writes all subprocess stdout/stderr to `~/.vibrante_node_subprocess.log`. The file is auto-rotated at 5 MB. Each launch session is delimited by a timestamp header, making crash diagnostics possible without a Python debugger.

### MCP Shutdown Safety

`MainWindow.closeEvent` now calls `mcp_runtime.shutdown_all_sync()`, cleanly tearing down any stdio MCP server subprocesses and SSE connections when the application exits. Without this, stdio servers would leak as zombie processes.

---

## Bug Fixes

- **`build_node_chain` parent ordering** — specs containing both a geo container and its children previously failed with `"parent node does not exist"`. The executor now topologically sorts nodes so parents are always created before their children. Also tracks Houdini name-collision remapping (when Houdini appends a suffix to avoid conflicts).

- **`review_execution` always scored 0%** — The plan-dict execution path in `execute_workflow_transaction` did not include `operations_executed` in its return dict, causing the reviewer's `_score_from_ops([])` to always return `0.0`. Fixed: op results are now tracked and included in the execution result. Secondary fix: if `operations_executed` is absent but `status == "committed"`, the reviewer now correctly treats `match_score` as `1.0`.

- **`preview_execution` ImportError** — The `preview_execution` tool handler imported `get_predictive_execution` (which does not exist) instead of `get_predictive_engine`. Fixed.

---

## Node ID Cleanup

Several bundled nodes were renamed to consistent prefixed IDs. Saved workflows that reference the old node IDs will fail to load those nodes. Affected renames:

| Old ID / file | New ID / file |
|---|---|
| `add` / `add.json` | `math_add` / `math_add.json` |
| `subtract` / `subtract.json` | `math_subtract` / `math_subtract.json` |
| `divide` / `divide.json` | `math_divide` / `math_divide.json` |
| `modulo` / `modulo.json` | `math_modulo` / `math_modulo.json` |
| `lowercase` / `lowercase.json` | `string_lowercase` / `string_lowercase.json` |
| `uppercase` / `uppercase.json` | `string_uppercase` / `string_uppercase.json` |
| `replace` / `replace.json` | `string_replace` / `string_replace.json` |
| `split` / `split.json` | `string_split` / `string_split.json` |
| `append_file` / `append_file.json` | `file_append` / `file_append.json` |
| `write_file` / `write_file.json` | `file_write` / `file_write.json` |
| `random_float` / `random_float.json` | `example_random_float` / `example_random_float.json` |

Removed nodes (no direct replacement):
- `concat` — use `string_replace` or Python expression nodes
- `multiply` — use `math_add` chain or a wrangle node

---

## Test Coverage

70+ new unit test files covering every runtime module (Tiers 1–6). Key additions:

- `test_mcp_runtime.py`, `test_houdini_runtime.py`, `test_houdini_mcp_nodes.py`
- `test_transaction_manager.py`, `test_graph_diff.py`
- `test_dependency_graph.py`, `test_validation_engine.py`, `test_audit_store.py`, `test_scheduler.py`
- `test_capability_registry.py`, `test_semantic_registry.py`, `test_semantic_execution.py`
- `test_ai_planner.py`, `test_intent_parser.py`, `test_plan_validator.py`, `test_execution_review.py`, `test_approval_pipeline.py`
- `test_mcp_tool_registry.py`, `test_mcp_transport.py`, `test_runtime_bootstrap.py`, `test_runtime_prompt_context.py`
- `test_workflow_optimizer.py`, `test_predictive_execution.py`, `test_execution_quality.py` (and 40+ more)

`test_all_workflows.py` now auto-discovers all plugin node directories (`plugins/*/v_nodes_*`) so adding a new DCC plugin requires zero test changes.

`test_settings_persistence.py` now properly isolates config writes to a per-test temp path, preventing leakage into the user's live `~/.vibrante_node_config.json`.

---

## Migration Notes

### Upgrading from v2.3.0

1. **Install new dependency**: `pip install "mcp>=1.0.0"`
2. **Node ID renames**: If you have saved workflows using the old node IDs listed in the "Node ID Cleanup" section above, you must update those workflow JSON files to use the new node IDs.
3. **Removed nodes**: `concat` and `multiply` have been removed. Replace with equivalent logic using available nodes.
4. **New capabilities are additive** — no existing node API has changed.

### MCP Server Setup (optional)

To use Vibrante as an MCP server for Claude Desktop or Cursor:
1. Ensure `mcp>=1.0.0` is installed.
2. Start Houdini with the Vibrante-Node plugin (for scene operations).
3. Add the entry point to your AI client config (see Highlights section above).

---

## Dependency Changes

| Package | Change |
|---|---|
| `mcp>=1.0.0` | **New** — required for MCP client/server transport |

---

## Full Documentation

- Full HTML documentation regenerated to v2.4.0
- `CLAUDE.md` expanded with complete Tier 1–6 architecture documentation (§12–§19)
- `ABOUT.md` added (Wikipedia-style project overview)
- Linux packaging guide: `linux/README.md` and `linux/BUILDING.md`
