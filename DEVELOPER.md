# Vibrante-Node — Developer Guide

**Version:** v2.4.0 | [User Guide](USER_GUIDE.md) | [Node Builder API](NODE_BUILDER_API.md) | [Automation API](AUTOMATION_API.md) | [Technical Reference](DOCUMENTATION.md)

This guide describes the internal architecture of Vibrante-Node: the execution engine, node registry, serialization system, Qt threading model, runtime layer, environment management, and plugin architecture. It is written for contributors, pipeline TDs, and developers who need to understand what happens between a user pressing Run (or an automation script triggering execution) and the last node completing.

---

## Contents

1. [Architecture Layers](#1-architecture-layers)
2. [Runtime Layer — AI Orchestration (Tiers 1–6)](#2-runtime-layer)
3. [Execution Engine — NetworkExecutor](#3-execution-engine)
4. [Event Loop Integration](#4-event-loop-integration)
5. [Data Flow and Propagation](#5-data-flow-and-propagation)
6. [Execution Ordering](#6-execution-ordering)
7. [Loop Execution](#7-loop-execution)
8. [GroupNode Sub-Executor](#8-groupnode-sub-executor)
9. [Bypass and Init-First Handling](#9-bypass-and-init-first-handling)
10. [Error Propagation and Cancellation](#10-error-propagation-and-cancellation)
11. [Node Registry System](#11-node-registry-system)
12. [Serialization System](#12-serialization-system)
13. [Qt Frontend Architecture](#13-qt-frontend-architecture)
14. [Thread Safety — MainThreadDispatcher](#14-thread-safety)
15. [Environment System — EnvManager](#15-environment-system)
16. [Plugin Architecture — Houdini](#16-plugin-architecture)
17. [Performance Considerations](#17-performance-considerations)

---

## 1. Architecture Layers

Vibrante-Node is organized into four required layers plus one optional extension. Dependencies flow top-to-bottom — no lower layer imports from a higher one. The Runtime Extensions are optional and additive: they call into Core and Utils but are not imported by them.

```
┌─────────────────────────────────────────────────────────┐
│  UI Layer  (src/ui/)                                     │
│  Qt canvas, panels, dialogs, node widgets, toolbars      │
│  — not imported in headless/MCP server mode              │
├─────────────────────────────────────────────────────────┤
│  Core Layer  (src/core/)                                 │
│  Execution engine, graph manager, node registry          │
├─────────────────────────────────────────────────────────┤
│  Nodes Layer  (src/nodes/)                               │
│  BaseNode, builtins, JSON-compiled dynamic nodes         │
├─────────────────────────────────────────────────────────┤
│  Utils Layer  (src/utils/)                               │
│  HouBridge, EnvManager, PrismCore, qt_compat,            │
│  async runtime, config manager                           │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│  Runtime Extensions  (src/runtime/)  ← optional          │
│  MCP server, AI planning, transaction system,            │
│  validation, analytics  (Tiers 1–6, 40+ modules)        │
└─────────────────────────────────────────────────────────┘
```

The Runtime Extensions are an optional addition in v2.4.0 — `scripts/run_vibrante_mcp.py` starts the full runtime without importing Qt.

### Key Files

| File | Responsibility |
|------|---------------|
| `scripts/run_vibrante_mcp.py` | MCP server entry point (headless mode) |
| `src/runtime/mcp_transport.py` | MCP stdio server — list/call tool handlers |
| `src/runtime/mcp_tool_registry.py` | 12 semantic MCP tools, `register_all_tools()` |
| `src/runtime/semantic_execution.py` | `SemanticExecutor` — intent → ops → transaction |
| `src/runtime/ai_planner.py` | `AIPlanner` — NL → structured execution plan |
| `src/runtime/intent_parser.py` | `IntentParser` — keyword → intent with LLM enhancement |
| `src/runtime/transaction_manager.py` | `TransactionManager` — begin/record/commit/rollback |
| `src/runtime/houdini_runtime.py` | `scene_context()`, `build_node_chain()`, rollback handlers |
| `src/runtime/validation_engine.py` | `ValidationEngine` — pre-execution structural validation |
| `src/runtime/runtime_constraints.py` | `RuntimeConstraints` — protected paths, forbidden ops |
| `src/runtime/scene_cache.py` | `SceneCache` — TTL cache + dirty tracking |
| `src/runtime/runtime_identity.py` | Constants: tool names, execution rules, identity |
| `src/runtime/runtime_bootstrap.py` | Singleton warm-up; structured bootstrap data |
| `src/runtime/mcp_session.py` | `SessionManager` — per-connection session lifecycle |
| `src/core/engine.py` | `NetworkExecutor` — the async execution engine |
| `src/core/graph.py` | `GraphManager` — topological sort, entry-node detection |
| `src/core/registry.py` | `NodeRegistry` — node type registration, hot-reload |
| `src/core/models.py` | Pydantic data models — workflow serialization |
| `src/ui/window.py` | `MainWindow` — menus, tabs, toolbar, dock layout |
| `src/ui/canvas/scene.py` | `NodeScene` — QGraphicsScene, wiring, group/ungroup |
| `src/ui/canvas/view.py` | `NodeView` — QGraphicsView, zoom, pan, minimap host |
| `src/ui/node_widget.py` | `NodeWidget` — per-node Qt rendering, reactive propagation |
| `src/ui/node_builder.py` | `NodeBuilderDialog` — GUI node authoring tool |
| `src/nodes/base.py` | `BaseNode`, `Port` — base class for all nodes |
| `src/utils/hou_bridge.py` | `HouBridge` — TCP JSON-RPC client for Houdini |
| `src/utils/prism_core.py` | `PrismCore` resolution, bootstrap, shared memory |
| `src/utils/env_manager.py` | `EnvManager` — environment variables, path management |
| `src/utils/qt_compat.py` | Qt5/Qt6 compatibility layer |

---

## 2. Runtime Layer — AI Orchestration (Tiers 1–6)

The `src/runtime/` module is the orchestration seam between AI/graph nodes and the Houdini bridge. It operates fully independently of the Qt UI and can be started headlessly via `scripts/run_vibrante_mcp.py`.

### Design Rules (Non-Negotiable)

1. **MCP is transport only.** The MCP server receives tool calls and routes them through the runtime; it never delegates scene understanding or planning to an LLM directly.
2. **No arbitrary Python execution.** AI-facing nodes and tools never accept a `code`/`python`/`script` argument. All execution is structured, validated, deterministic.
3. **Validation before mutation.** Every op list is shape-checked by `ValidationEngine` and policy-gated by `RuntimeConstraints` before any bridge interaction.
4. **Transaction boundary.** All mutations route through `TransactionManager.begin_transaction` → `execute_operation` → `commit_transaction` / `rollback_transaction`.
5. **Context first.** `scene_context()` provides the structured snapshot that AI agents read before acting.

### Tier Summary

| Tier | Modules | What it adds |
|---|---|---|
| 1 | `mcp_runtime`, `houdini_runtime`, `scene_cache` | MCP client sessions, scene context, node chain builder |
| 2 | `transaction_manager`, `scene_cache` (dirty) | Transaction lifecycle, rollback, dirty tracking, graph diff |
| 2.5 | `dependency_graph`, `validation_engine`, `audit_store`, `execution_scheduler` | Dependency tracking, pre-execution validation, audit log, serialized execution queue |
| 2.75 | `capability_registry`, `resource_estimator`, `runtime_constraints`, `workflow_templates`, `semantic_registry`, `semantic_execution` | Semantic op registry, constraint policies, deterministic workflow templates, full semantic executor |
| 3 | `llm_provider`, `intent_parser`, `contextual_reasoning`, `ai_planner`, `plan_validator`, `approval_pipeline`, `planning_memory` | Controlled AI planning pipeline with approval gate |
| 4 | `agent_runtime`, `distributed_runtime`, `multi_dcc_runtime`, `knowledge_graph`, `workflow_federation`, `runtime_federation_api` | Supervised agents, distributed workers, multi-DCC routing, federated workflows |
| 5 | `workflow_optimizer`, `runtime_analytics`, `predictive_execution`, `recommendation_engine`, `execution_quality`, `studio_knowledge` | Advisory analytics — no execution authority |
| 6 | `runtime_identity`, `runtime_bootstrap`, `runtime_prompt_context`, `mcp_session`, `mcp_tool_registry`, `mcp_transport` | Full MCP server: 12 semantic tools, stdio transport, session management |

### MCP Transport Architecture (Tier 6)

```
External AI client (Claude Desktop / Codex CLI / Cursor)
    ↓  stdin/stdout (MCP stdio protocol)
MCPTransport._run_async()
    ├── app.list_tools()  → MCPToolRegistry.list_tools()
    └── app.call_tool()   → MCPToolRegistry.dispatch_tool(name, args)
                                    ↓
                          tool handler function
                                    ↓
                          SemanticExecutor / TransactionManager / houdini_runtime
                                    ↓
                          returns TextContent(type="text", text=json.dumps(result))
```

The MCP SDK is imported lazily on first `run_stdio()` call (`_require_mcp_server()`). Importing `mcp_transport` at startup costs nothing.

`dispatch_tool` never raises — all exceptions are caught and returned as `{"ok": False, "error": str(exc)}`. The transport process never crashes due to a tool failure.

### Forbidden Tool Surface

The `mcp_tool_registry` must never register these names (test-enforced in `test_mcp_tool_registry.py`):

```python
FORBIDDEN_TOOLS = {
    "create_node", "set_parm", "set_parms", "run_python",
    "run_code", "delete_node", "raw_houdini_execute",
    "connect_nodes", "cook_node",
}
```

### Execution Safety Invariants

All PRs touching `src/runtime/` must verify:

1. `AgentRuntime.submit_proposal()` returns a plan; it never calls `execute_operation` directly.
2. `DistributedRuntime._execute_local()` calls `RuntimeConstraints.validate_transaction()` and `ValidationEngine.validate_operations()` before any bridge interaction.
3. `execute_workflow_transaction` tool handler: plans with `ok=False` are rejected; plans with `requires_approval=True` return `pending_approval` unless `approver` is supplied.
4. No Tier 5 module calls `get_bridge()`, `houdini_runtime`, `TransactionManager`, or `ExecutionScheduler.enqueue()`.
5. Built-in MCP server tools cannot be deregistered (`deregister_tool()` raises `ValueError` for built-ins).

### Adding a New MCP Tool

1. Write an `async` handler function. It must return a `dict` (or any JSON-serializable value); exceptions are caught by `dispatch_tool`.
2. Create a `ToolDefinition(name, description, inputSchema, handler, category)`.
3. Call `registry.register_tool(defn)` inside `register_all_tools()` in `mcp_tool_registry.py`.
4. Add the name to `MCP_TOOL_NAMES` in `runtime_identity.py`.
5. Add the name to `EXPECTED_TOOLS` in `tests/unit/test_mcp_tool_registry.py`.
6. Check that the name is not in `FORBIDDEN_TOOLS`.

### Scene Cache Invalidation Rule

Any function in `houdini_runtime.py` or a rollback handler that mutates Houdini state **must** call:

```python
from src.runtime.scene_cache import get_scene_cache
get_scene_cache().invalidate("scene_context::")
```

before returning. `build_node_chain` and all rollback handlers in `_ROLLBACK_HANDLERS` already follow this pattern — copy it when adding new mutating operations.

---

## 3. Execution Engine — NetworkExecutor

`NetworkExecutor` (`src/core/engine.py`) is the central execution engine. It is a `QObject` (not a `QThread`) and runs entirely on the Qt main thread.

### Startup Sequence

When the user presses F5 (or calls `app.execute_pipeline()`):

```
MainWindow._on_execute_clicked()
    │
    ├── scene.get_workflow_model() → WorkflowModel
    │
    ├── GraphManager(workflow_model) → graph
    │
    ├── NetworkExecutor(graph, signals)
    │
    ├── [Prism bootstrap if prism_core_init detected]
    │
    └── executor.run()
              │
              ├── Instantiate all nodes (restore_from_parameters + clear_outputs)
              ├── Detect entry nodes
              ├── Start each entry node as an asyncio.Task
              └── Drive asyncio loop via _EventLoopRunner
```

### Node Instantiation

For each `NodeInstanceModel` in the workflow:

1. Look up the class in `NodeRegistry._classes[node_id]`.
2. Instantiate: `node = NodeClass()`.
3. Call `node.restore_from_parameters(saved_params)` — rebuilds dynamic ports.
4. Apply all saved parameters to the instance: `node.set_parameter(name, value)` for each saved key-value pair. This step ensures embedded scripts (`python_code`), dynamic state, and widget values from the saved workflow are available when `execute()` runs.
5. Call `node.clear_outputs()` — reset all output port values.

### Signals Emitted by the Engine

| Signal | Payload | When |
|--------|---------|------|
| `node_started` | `node_instance_id: str` | Before `execute()` is called |
| `node_finished` | `node_instance_id: str, results: dict` | After `execute()` returns |
| `node_error` | `node_instance_id: str, error: str` | Unhandled exception in `execute()` |
| `node_output` | `node_instance_id: str, results: dict` | Alias for `node_finished`; used by UI |
| `execution_started` | — | When the run begins |
| `execution_finished` | — | When all entry tasks complete |

`MainWindow` connects to these signals to update the Log Panel, update node border colors, and invoke `scene.update_edge_value()` for the Live Wire Inspector.

---

## 4. Event Loop Integration

Qt and asyncio each require ownership of the thread's event loop. Vibrante-Node bridges them with `_EventLoopRunner`, a zero-delay `QTimer` that drives the asyncio loop from inside Qt's event loop.

```
QTimer(interval=0) ──► _EventLoopRunner._step()
                              │
                              ├─ loop.call_soon(loop.stop)   ← queue stop at end of ready callbacks
                              └─ loop.run_forever()           ← drains ready callbacks, then stops
```

Each call to `_step()`:
1. Queues `loop.stop` at the back of the asyncio ready queue.
2. Calls `loop.run_forever()`. Since `loop.stop` was queued last, `run_forever` returns after processing all currently-ready callbacks (typically in microseconds).
3. Returns control to Qt's event loop, keeping the UI responsive.

This scheme interleaves Qt events and asyncio tasks with zero blocking. The practical consequence: every `await` in a node's `execute()` yields control to both Qt and other asyncio tasks.

---

## 5. Data Flow and Propagation

### Wire Model

Each connection in the workflow maps an output port on one node to an input port on another. The engine maintains a `node_results` dict (`dict[instance_id, dict[port_name, value]]`) that accumulates outputs as each node completes.

### Output Propagation

After a node's `execute()` returns:

1. The engine stores the result dict in `node_results[instance_id]`.
2. For each output port in the result dict, the engine walks all outgoing wires.
3. For each wire's destination node, the corresponding input parameter is updated: `dest_node.set_parameter(port_name, value)`.
4. If the destination node has `on_parameter_changed` defined, it is called.
5. If the source port was `exec_out`, the destination node's execution is scheduled as the next asyncio task.

### Reactive Propagation (Outside Execution)

During parameter changes (user typing in a widget), `NodeWidget._update_param()` calls `_propagate_all_outputs()`. This scans all outgoing wires on every output port and pushes the current values downstream — updating widget displays in real time without a full execution run.

**Critical:** `_propagate_all_outputs()` must run on the Qt main thread because it calls `widget.setText()` and similar methods. It is dispatched via `_MainThreadDispatcher` (see [Section 13](#13-thread-safety)).

---

## 6. Execution Ordering

### Entry Node Detection

Entry nodes are nodes with no incoming `exec_in` wire. The engine starts execution from all entry nodes as concurrent asyncio tasks. For a simple single-chain workflow, this is one node; for a forked workflow, it may be several.

Data-only nodes (no exec pins) are never entry nodes in exec-flow mode. They are reached only by the data-pull mechanism.

### Data-Pull Recursion

Before any exec-flow node's `execute()` is called, the engine recursively "pulls" data from all upstream data-only nodes:

```
_run_single_node(exec_node)
    │
    └── for each input port of exec_node:
            find connected upstream node
            if upstream is data-only (use_exec=False):
                _run_single_node(upstream)   ← recursive pull
            copy upstream output → exec_node input
```

This guarantees that data-only nodes (math, string, config) always provide fresh values to exec-flow nodes, even without explicit exec wiring.

### Topological Sort (Data-Flow Only)

When a workflow contains only data-only nodes (no exec pins anywhere), `GraphManager.topological_sort()` determines execution order using `toposort`. The engine executes nodes in dependency order, layer by layer.

---

## 7. Loop Execution

### For Loop

`for_loop` builds the complete index list `[0, 1, ..., N-1]` inside a single `execute()` call, returns it via the `indices` output port, and fires `exec_out` once. `loop_body` then drives per-item iteration.

The `loop_body` node iterates the list in its own `execute()`, calling `_run_from_node()` on its downstream chain once per item. The removal of `_exec_lock` (done in v1.0.5) makes this re-entrant execution safe — the engine can enter `_run_from_node()` recursively from within an active `execute()` coroutine.

### While Loop

`while_loop` checks its `condition` input, and if `True`, fires `exec_out` and then re-evaluates. Because re-entrant execution is lock-free, the while loop's recursive `_run_from_node()` calls do not deadlock. The downstream chain is responsible for eventually setting the condition to `False` (or the user presses Stop).

### Break

The `loop_break` node checks a boolean condition and, if `True`, sets an internal flag that causes `loop_body` to stop iteration after the current item.

---

## 8. GroupNode Sub-Executor

`GroupNode` (defined in `src/nodes/builtins/group_node.py`) stores a full `WorkflowModel` in its `parameters["__workflow__"]`. When the engine executes a GroupNode:

1. A nested `NetworkExecutor` is created for the inner `WorkflowModel`.
2. Boundary input values from the outer graph are injected into `GroupInNode` instances via `parameters["_injected_value"]`.
3. The inner graph executes fully.
4. `GroupOutNode` values are read from `node_results` of the inner executor.
5. These values are written to the GroupNode's output ports and returned.
6. If the inner graph completes without exception: `exec_out` fires.
7. If any inner node raises an unhandled exception: `exec_fail` fires.

Inner-graph log messages are forwarded to the outer `MainWindow` log panel.

### Subgraph Tab Editing

`MainWindow._open_subgraph_tab()` creates a new tab for the inner workflow. A `_sync_callback` closure is attached to the inner `NodeScene` via `scene._sync_callback`. This closure is called by `push_history()`, `undo()`, and `redo()` on the inner scene — it serializes the inner scene state and writes it back to `group_widget.node_definition.parameters["__workflow__"]`, and pushes a history entry on the parent scene.

---

## 9. Bypass and Init-First Handling

### Bypass

`NetworkExecutor._run_single_node_impl()` checks `node.bypassed` before calling `execute()`:

- If `True`: copy the primary input value to the primary output, fire `exec_out`, skip `execute()`.
- The downstream chain is unbroken.
- Bypassed nodes appear faded on the canvas (set by `NodeWidget`).

### Init-First (init_priority)

`NodeScene.from_workflow_model()` performs a two-pass load:

**Pass 1:** Create and connect all nodes with `init_priority > 0`. Their `on_plug_sync` callbacks fire as wires are connected, so they can read connected values immediately.

**Pass 2:** Create and connect all remaining nodes.

This guarantees that authentication nodes and server-connect nodes are fully instantiated and wired before any downstream node that depends on them via `on_plug_sync` is created.

---

## 10. Error Propagation and Cancellation

### Unhandled Exceptions

If `execute()` raises any unhandled exception:

1. The engine catches it.
2. `node_error` signal is emitted with the exception string.
3. The node's visual state is set to error (red border).
4. The error is logged to the Log Panel.
5. The downstream exec chain from that node does **not** continue.
6. Other independent branches continue executing.

For GroupNode inner exceptions, `exec_fail` fires on the GroupNode instead.

### Cancellation

The user pressing Stop (`Shift+F5`) sets a cancellation flag accessible via `node.is_stopped()`. Long-running nodes should check this in loops:

```python
for item in large_list:
    if self.is_stopped():
        return {"exec_out": True}
    # ... process item ...
```

The `asyncio.Task.cancel()` API is also used for immediate cancellation of nodes that are `await`-ing I/O.

---

## 11. Node Registry System

### Loading

`NodeRegistry.load_all_with_extras(bundled_nodes_dir)` is the primary load path. It:

1. Loads built-in Python nodes from `src/nodes/builtins/`.
2. Loads JSON nodes from `bundled_nodes_dir` (the `nodes/` directory).
3. Loads JSON nodes from all paths in `os.environ.get("v_nodes_dir", "")` (colon-separated).

`_load_directory(path)` scans a directory for `.json` files and calls `load_node(path)` for each.

### Compilation

`load_node(json_path)` reads the JSON, validates it as `NodeDefinitionJSON`, then calls `_compile_node_class(definition)`:

1. Prepend standard imports to `python_code`.
2. For `prism_*` nodes: inject `resolve_prism_core` import and rewrite the core access line.
3. `exec(python_code, module_globals)` in an isolated namespace.
4. Retrieve the class returned by `register_node()`.
5. Inject `node_id` and `display_name` as class attributes.
6. Store in `_classes[node_id]` and `_definitions[node_id]`.
7. Store the source path in `_source_paths[node_id]`.

### Hot Reload

`reload_node_definition(node_id)`:

1. Reads the file at `_source_paths[node_id]`.
2. Recompiles the class (same steps as above).
3. Replaces `_classes[node_id]` and `_definitions[node_id]`.
4. Returns `True` on success.

`NodeScene.reload_node_type(node_id)` calls `reload_node_definition()` then iterates all `NodeWidget` instances in the scene, calling `widget.reload_definition(new_definition)` on matching ones.

`NodeWidget.reload_definition(new_definition)`:
1. Replaces internal definition reference.
2. Removes existing port items from the QGraphicsScene.
3. Calls `_build_ports(new_definition)`.
4. Re-applies parameters where the port still exists and type is compatible.
5. Removes wires to deleted ports.

---

## 12. Serialization System

### WorkflowModel

```python
class WorkflowModel(BaseModel):
    nodes:        list[NodeInstanceModel]   = []
    connections:  list[ConnectionModel]     = []
    sticky_notes: list[StickyNoteModel]     = []
    backdrops:    list[BackdropModel]       = []
```

All fields are optional/defaulted. Any valid JSON that parses to this shape is a valid workflow (missing fields default). This is why the `_looks_like_node_json()` guard is needed in `load_workflow()`.

### NodeInstanceModel

```python
class NodeInstanceModel(BaseModel):
    node_id:      str
    instance_id:  str        # UUID as string
    display_name: str        # canvas label
    position:     dict       # {"x": float, "y": float}
    parameters:   dict       # all widget values, output cache, embedded scripts
```

### ConnectionModel

```python
class ConnectionModel(BaseModel):
    from_node:  str    # source instance_id
    from_port:  str    # output port name
    to_node:    str    # destination instance_id
    to_port:    str    # input port name
```

### Save and Load

**Save:** `NodeScene.save_workflow_model()`:
1. Iterates all `NodeWidget` instances → `NodeInstanceModel`.
2. Iterates all `Edge` items → `ConnectionModel`.
3. Iterates sticky notes and backdrops.
4. Strips non-serializable runtime values (Qt objects, live references) from `parameters`.
5. Returns `WorkflowModel`, serialized to JSON with `model.model_dump_json(indent=2)`.

**Load:** `NodeScene.from_workflow_model(workflow_model)`:
1. Sets `_undoing = True` to suppress `push_history()` calls during load.
2. Creates all Init First nodes (Pass 1).
3. Creates all remaining nodes (Pass 2).
4. Creates all connections.
5. Places sticky notes and backdrops.
6. Restores `_undoing` to original value.
7. If a `_sync_callback` is attached (subgraph tab), calls it.

---

## 13. Qt Frontend Architecture

### QGraphicsScene — NodeScene

`NodeScene` manages all canvas items:

- **`NodeWidget`** (`QGraphicsItem`) — the visual box, port items, widgets.
- **`Edge`** (`QGraphicsPathItem`) — a wire between two ports.
- **`PortItem`** (`QGraphicsEllipseItem`) — a single port connection point.
- **`StickyNote`** (`QGraphicsRectItem`) — an annotation box.
- **`Backdrop`** (`QGraphicsRectItem`) — a grouping region.
- **`MiniMap`** (`QGraphicsView`) — a second view sharing the same scene; child widget of `NodeView`.

### NodeView — QGraphicsView

`NodeView` hosts the canvas. Key responsibilities:

- Mouse wheel → `scale()` for zoom.
- Middle-mouse drag → `translate()` for pan.
- `resizeEvent` → repositions `CanvasSearchBar` and `MiniMap`.
- Delegates `keyPressEvent` to `NodeScene` after checking `QApplication.focusWidget()` (prevents hotkeys firing inside text inputs).

### History and Undo/Redo

`NodeScene` maintains a `_history` list of serialized `WorkflowModel` snapshots. `push_history()` appends a snapshot (unless `_undoing` is True). `undo()` / `redo()` index into `_history`, call `from_workflow_model()` with `_undoing = True` to suppress recursive history pushes.

Dirty state: `push_history()` sets `_dirty = True` and emits `dirty_changed(True)` on the first change after a save (clean → dirty transition). `mark_clean()` resets to clean.

---

## 14. Thread Safety — MainThreadDispatcher

The asyncio execution engine and Qt UI both run on the same OS thread (the Qt main thread). However, `asyncio` coroutines can be interleaved with each other and with Qt slots. This creates one specific hazard:

**`_propagate_all_outputs()` in `NodeWidget`** accesses `scene().edges` and calls widget methods (`w.setText()`, `w.setValue()`). If called from inside the asyncio execution path (e.g., from `on_parameter_changed` triggered by engine output propagation), it runs "inside" an asyncio coroutine on the main thread. Qt widget method calls are safe on the main thread, but they must not preempt other Qt operations mid-frame.

**Solution:** `_MainThreadDispatcher` is a module-level `QObject` with a `pyqtSignal(object)` connected with `Qt.QueuedConnection`. Emitting this signal from any context queues a deferred call to the slot, which runs at the next Qt event loop iteration — after the current asyncio step completes.

```python
# _MainThreadDispatcher usage (src/ui/node_widget.py)
_main_dispatcher.dispatch_signal.connect(
    _main_dispatcher._on_dispatch, Qt.QueuedConnection
)

# From inside a coroutine or background context:
_main_dispatcher.post(self._propagate_all_outputs)
# This queues the call for the next Qt event loop iteration
```

---

## 15. Environment System — EnvManager

`EnvManager` (`src/utils/env_manager.py`) is a singleton that manages all environment configuration. It is initialized once at startup via `env_manager.initialize()` in `src/main.py`.

### Configuration Keys (persisted in `~/.vibrante_node_config.json`)

| Key | Type | Purpose |
|-----|------|---------|
| `env.vibrante_pythonpath` | `list[str]` | Injected into `sys.path` at startup |
| `env.v_nodes_dir` | `list[str]` | Merged into `os.environ["v_nodes_dir"]` |
| `env.v_scripts_path` | `list[str]` | Merged into `os.environ["v_scripts_path"]` |
| `env.custom_variables` | `dict[str, str]` | Injected into `os.environ` |

### Merge Semantics

`v_nodes_dir` and `v_scripts_path` are **merged** — paths already in `os.environ` (e.g. set by Houdini's `setup_env()`) are preserved; config paths are appended. No paths are dropped.

`VIBRANTE_PYTHONPATH` injects into `sys.path` only — it does not overwrite the `PYTHONPATH` env var.

Custom variables are injected directly into `os.environ` (process-scoped; not permanent).

### Thread Safety

All reads and writes go through a `threading.Lock`. Safe to call from any thread.

### Subprocess Helper

```python
env = env_manager.apply_to_subprocess_env(base_env=None)
```

Returns a new `dict` (copy of `os.environ` with all managed variables applied) for use as `subprocess.Popen(env=...)`. Never mutates `os.environ` directly.

### Reinitialize

After saving settings changes (Settings dialog OK), `env_manager.reinitialize()` re-reads all config values and re-applies them. This is safe to call at runtime.

### Import / Export

```python
data = env_manager.export_settings()
# Returns: {"vibrante_pythonpath": [...], "v_nodes_dir": [...], "v_scripts_path": [...], "custom_variables": {...}}

env_manager.import_settings(data)
# Persists all four groups. Unknown keys are silently ignored.
```

---

## 16. Plugin Architecture — Houdini

The Houdini integration consists of two sides: code running inside Houdini and the Vibrante-Node subprocess.

### Plugin Layout

```
plugins/houdini/
├── vibrante_node.json          ← Houdini package file (user installs this)
├── v_nodes_houdini/            ← Houdini-specific node JSON definitions
│   ├── hou_create_geo.json
│   └── ...
├── v_scripts_houdini/          ← Houdini-specific .py scripts (Scripts menu)
│   └── hou_create_box_demo.py
└── houdini/                    ← Added to HOUDINI_PATH by package JSON
    ├── MainMenuCommon.xml      ← Adds "Vibrante-Node" menu to Houdini
    ├── toolbar/vibrante_node.shelf
    └── scripts/python/
        ├── pythonrc.py         ← Startup diagnostics (printed to Python console)
        ├── vibrante_node_houdini.py   ← launch(), setup_env()
        └── vibrante_hou_server.py     ← JSON-RPC server
```

### Launch Sequence

When the user clicks **Vibrante-Node → Launch** in Houdini:

1. `vibrante_node_houdini.launch()` calls `setup_env()` once.
2. `setup_env()` starts `vibrante_hou_server.start()` (binds TCP port 18811).
3. Sets `VIBRANTE_HOU_PORT`, `VIBRANTE_HOUDINI_MODE=subprocess`, `VIBRANTE_HIP_FILE`, `v_nodes_dir` (pointing to `v_nodes_houdini/`), `v_scripts_path`.
4. Spawns `python src/main.py` as a subprocess with this environment.

### JSON-RPC Server (`vibrante_hou_server.py`)

- Listens on `localhost:18811` (configurable via `VIBRANTE_HOU_PORT`).
- Accepts JSON-encoded RPC calls: `{"method": "create_node", "params": {...}}`.
- Returns JSON-encoded results.
- Thread-safe: `threading.Lock` around start/stop; each request is handled in the accept loop (single-threaded).
- Gracefully handles headless Houdini: `hou.playbar.frameRange()` is wrapped in `try/except AttributeError` with fallback `[1, 240]`.
- Guards `setDisplayFlag`/`setRenderFlag` with capability checks and `try/except hou.OperationFailed`.

### HouBridge Client (`src/utils/hou_bridge.py`)

- Singleton per process, accessed via `get_bridge()`.
- `socket.TCP_NODELAY` set on connect (eliminates ~40 ms Nagle delay on Windows).
- `socket.timeout(30)` — raises `ConnectionError` if the server doesn't respond.
- `threading.Lock` per instance — `_send()` is thread-safe.
- Auto-reconnect on `BrokenPipeError` / `ConnectionResetError`.

---

## 17. Performance Considerations

### CPU-Bound Work

The asyncio engine runs on the main thread. CPU-bound operations in `execute()` will block the event loop and freeze the UI. Offload them to a thread pool:

```python
import asyncio

async def execute(self, inputs):
    data = inputs.get("data")
    result = await asyncio.to_thread(heavy_cpu_computation, data)
    return {"result": result, "exec_out": True}
```

### I/O-Bound Work

Use async I/O libraries where possible:

```python
import aiohttp, aiofiles

async def execute(self, inputs):
    async with aiohttp.ClientSession() as session:
        async with session.get(inputs["url"]) as resp:
            data = await resp.text()
    return {"result": data, "exec_out": True}
```

If only synchronous I/O is available, use `asyncio.to_thread()`.

### Large Graphs

- `NodeRegistry.load_all_with_extras()` compiles all node classes on startup. 166 nodes adds ~200–400 ms to launch time; this is acceptable.
- `WorkflowModel` serialization is O(N nodes + M wires). Large graphs (>500 nodes) may have noticeable save/load times.
- The `_history` list stores serialized snapshots per undo step. Limit undo history depth if memory is a concern (configurable in `NodeScene`).

### Wire Value Inspector

`Edge.shape()` overrides the default 2 px path with a 12 px stroked hit-area to make hover detection reliable. On very dense graphs with hundreds of edges, this has negligible rendering cost but do not further inflate the hit area.

### Reactive Propagation Frequency

Every keystroke in a widget triggers `_propagate_all_outputs()`. For deeply connected graphs this can traverse many nodes. Keep `on_parameter_changed` implementations fast and avoid I/O there.

---

**See also:**

- [Node Builder API](NODE_BUILDER_API.md) — `BaseNode` contract, port system, lifecycle hooks
- [Automation API](AUTOMATION_API.md) — `NodeRegistry` hot-reload, scene manipulation from scripts, MCP runtime API
- [Technical Reference](DOCUMENTATION.md) — complete signal catalogue, model schemas, MCP tool reference
- `src/runtime/` — Runtime Layer source (40+ modules, Tiers 1–6)
- `scripts/run_vibrante_mcp.py` — MCP server entry point
- `src/core/engine.py` — `NetworkExecutor` source
- `src/core/registry.py` — `NodeRegistry` source
- `src/core/models.py` — Pydantic models source
- `docs_src/06_backend_architecture.md` — deeper execution flow detail with ASCII diagrams
- `docs_src/07_frontend_architecture.md` — Qt canvas architecture in full depth
