# 06 — Backend Architecture

**Vibrante-Node v2.4.0 — Technical Reference**

This document describes the execution engine, graph model, node registry, and all supporting subsystems that make up the Vibrante-Node backend. It is written for contributors, plugin authors, and advanced users who need to understand what happens between the moment the user clicks **Run** and the moment the last node finishes.

---

## Table of Contents

1. [Execution Engine Overview](#1-execution-engine-overview)
2. [Event Loop Integration](#2-event-loop-integration)
3. [Execution Flow Diagram](#3-execution-flow-diagram)
4. [Entry Node Detection](#4-entry-node-detection)
5. [Data-Pull Recursion](#5-data-pull-recursion)
6. [Execution Order Guarantees](#6-execution-order-guarantees)
7. [Loop Execution](#7-loop-execution)
8. [GroupNode Sub-Executor](#8-groupnode-sub-executor)
9. [Bypass Handling](#9-bypass-handling)
10. [init_priority System](#10-init_priority-system)
11. [Error Propagation](#11-error-propagation)
12. [Cancellation](#12-cancellation)
13. [node_results Dictionary](#13-node_results-dictionary)
14. [Signal Catalogue](#14-signal-catalogue)
15. [State Management](#15-state-management)
16. [GraphManager](#16-graphmanager)
17. [NodeRegistry](#17-noderegistry)
18. [BaseNode Contract](#18-basenode-contract)
19. [SafeRuntime and Error Isolation](#19-saferuntime-and-error-isolation)
20. [Performance Considerations](#20-performance-considerations)

---

## 1. Execution Engine Overview

`NetworkExecutor` (`src/core/engine.py`) is the central execution engine. It inherits from `QObject` so it can emit Qt signals from within async code. The engine operates entirely on the Qt main thread — there are no worker threads for node execution. Async I/O is achieved by running an `asyncio` event loop that is manually stepped by a zero-delay `QTimer`.

### What NetworkExecutor does

1. Receives a `GraphManager` instance containing the full node graph.
2. Instantiates one `BaseNode` subclass per `NodeInstanceModel`, restoring its dynamic ports and parameter values from the saved workflow.
3. Determines which nodes are *entry nodes* and which are *data-pull nodes*.
4. Starts all entry nodes as concurrent asyncio tasks.
5. After each node's `execute()` returns, propagates outputs to downstream nodes' inputs reactively.
6. Triggers downstream execution via exec-port connections.
7. Emits Qt signals after every state transition so the UI stays in sync.

### Why async

Node `execute()` coroutines may perform I/O: reading files, making HTTP requests, talking to the Houdini command server over TCP, or calling subprocess-based DCCs. If these were synchronous, they would block the Qt event loop and freeze the entire UI. By using `asyncio`, multiple nodes can be waiting on I/O simultaneously without any threading overhead. A single OS thread handles everything; the event loop interleaves coroutines cooperatively.

The practical rule is: **anything that blocks for more than a few milliseconds must use `await`**. CPU-bound work that cannot be split into coroutines should use `asyncio.to_thread()` to push it to a thread pool without blocking the event loop (see [Performance Considerations](#20-performance-considerations)).

---

## 2. Event Loop Integration

Qt and asyncio each expect to own the thread's event loop. Vibrante-Node bridges them with `_EventLoopRunner` (`src/ui/window.py`), a lightweight adapter that drives the asyncio loop from inside Qt's event loop.

### How _EventLoopRunner works

```
QTimer(interval=0) ──► _EventLoopRunner._step()
                              │
                              ├─ loop.call_soon(loop.stop)
                              │      schedules a stop callback at end of ready queue
                              │
                              └─ loop.run_forever()
                                     runs until the stop callback fires
                                     (processes exactly one round of ready callbacks)
```

`_step()` is called by Qt every time the event loop is idle (interval = 0). Each call to `_step()`:

1. Queues a `loop.stop` at the back of the asyncio ready queue.
2. Calls `loop.run_forever()`. Because `loop.stop` was queued last, `run_forever` returns after draining all currently-ready callbacks — typically in microseconds.
3. Checks whether the main task is done, and if so calls `_cleanup()`.

This scheme means:

- All `await` suspensions resume on the Qt main thread.
- All Qt signals emitted from within `async` code are queued connections that deliver on the main thread — no cross-thread marshalling is ever needed.
- `QBasicTimer` warnings ("timer can only be used with threads started with QThread") cannot occur because the asyncio loop never runs on a background thread.

### Lifecycle

```python
runner = _EventLoopRunner(executor)
runner.start()   # creates asyncio task, starts QTimer
# ... Qt main loop runs ...
runner.stop()    # calls executor.stop(); loop keeps pumping until task finishes
```

`_EventLoopRunner` creates a brand-new `asyncio.new_event_loop()` for each run, so there are no stale tasks or leftover state between executions.

---

## 3. Execution Flow Diagram

```
User clicks Run
      │
      ▼
MainWindow.execute_pipeline()
      │
      ├─ Build GraphManager from WorkflowModel
      ├─ Create NetworkExecutor(graph_manager)
      ├─ Create _EventLoopRunner(executor)
      └─ runner.start()
              │
              ▼
        executor.run()   [async coroutine]
              │
              ├─ 1. PRE-CALCULATE LOOKUP MAPS
              │       _incoming_data_conns: {node_id → [ConnectionModel]}
              │       _driven_by_flow: set of node_ids with exec_in connected
              │
              ├─ 2. PREPARE ALL NODES
              │       for each NodeInstanceModel:
              │           instantiate node_class()
              │           restore_from_parameters()   (dynamic ports)
              │           sync parameters (skip ports with live data connections)
              │           clear_outputs()
              │           install _on_log, _on_output, _check_stopped hooks
              │
              ├─ 3. PRISM BOOTSTRAP (if prism_core_init present)
              │
              ├─ 4. INIT NODES (init_priority > 0, descending order)
              │       each init node's full exec chain completes before next
              │
              ├─ 5. ENTRY NODE DETECTION
              │       exec_conns present?
              │         YES → flow mode:
              │               entry = nodes with exec_out but no connected exec_in
              │                      OR nodes with no exec pins at all
              │         NO  → data-flow mode:
              │               layers = graph_manager.get_topological_sort()
              │               execute layer by layer with asyncio.gather()
              │
              └─ 6. FLOW EXECUTION  [per entry node, concurrent tasks]
                      _execute_flow(node_id)
                            │
                            ├─ BYPASS CHECK → short-circuit if bypassed
                            │
                            ├─ PULL UPSTREAM DATA NODES
                            │       for each input port (in port definition order):
                            │           if upstream node not in _driven_by_flow:
                            │               _run_single_node_impl(upstream, is_data_pull=True)
                            │
                            ├─ node_started signal
                            │
                            ├─ reset exec output parameters
                            │
                            ├─ sync all inputs from node_results cache
                            │
                            ├─ SafeRuntime.run_node_safe(instance.execute, inputs)
                            │
                            ├─ SUCCESS:
                            │     node_results[node_id].update(result)
                            │     node_output signal
                            │     node_finished("success") signal
                            │
                            └─ FAILURE:
                                  node_error signal
                                  node_finished("failed") signal
                                  [exec chain stops here]

     set_output("exec_out", True) called inside execute()
              │
              ├─ stores value in node_results
              ├─ node_output signal (for live wire inspector)
              ├─ REACTIVE DATA PROPAGATION:
              │     for each data connection from this port:
              │         target.parameters[to_port] = value
              │         node_results[to_node][to_port] = value
              │         if target not in _driven_by_flow:
              │             discard from _executed_nodes  (force re-run in loops)
              │         await target.on_parameter_changed(port, value)
              └─ FLOW ROUTING (if port type == 'exec' and value is truthy):
                    for each exec connection from this port:
                        await _execute_flow(to_node)
```

---

## 4. Entry Node Detection

Entry node detection depends on whether the graph contains any exec connections.

### Flow Mode (exec connections present)

A node is an entry node if **either** of these conditions is true:

1. **No exec_in pin** — the node has only data ports. Examples: `GetVariable`, constant value nodes, the `prism_core_init` node. These never need to be triggered by an upstream exec; they run when data-pulled.
2. **Has exec_in pin but no connection to it** — the node is the start of an exec chain. This is the primary category: the first node the user wires up (e.g. a `Sequencer` or a Houdini node with `exec_in` connected to nothing).

Both categories apply even within a single graph. A graph might have two independent exec chains, each starting their own entry node. Both are detected and tracked as concurrent tasks.

Nodes already executed by the init phase (`_executed_nodes`) are excluded from entry detection to avoid double-execution.

```python
# From engine.py (simplified)
entry_nodes = []
for node_id, instance in self.node_instances.items():
    if node_id not in connected_nodes: continue
    if node_id in self._executed_nodes: continue

    has_exec_in_pin = any(p.data_type == 'exec' for p in instance.inputs.values())

    if not has_exec_in_pin:
        entry_nodes.append(node_id)
    elif node_id not in has_exec_in_conn:
        entry_nodes.append(node_id)
```

### Data-Flow Mode (no exec connections)

When the graph has no exec connections at all, the engine falls back to classic topological sort execution. Every node in the graph is placed in a dependency layer, and layers are executed in order using `asyncio.gather()`. This mode is provided for backward compatibility and for simple graphs that do not need flow control.

---

## 5. Data-Pull Recursion

Before executing any node, the engine recursively evaluates all upstream *data-only* nodes. This is called a data pull. Data-only nodes are those not in `_driven_by_flow` (i.e. no exec connection feeds into them).

### The data-pull algorithm

```python
# Pull in port-definition order so values arrive in a predictable sequence
for port_name in instance.inputs:
    for conn in incoming:
        if conn.to_port == port_name:
            from_id = conn.from_node
            is_driven_by_flow = from_id in self._driven_by_flow
            if not is_driven_by_flow:
                await self._run_single_node_impl(from_id, is_data_pull=True)
```

### Guards against double-execution

`_run_single_node_impl` has two guards:

1. **Data-pull guard** — if `is_data_pull=True` and the node is already in `_executed_nodes`, it is skipped immediately. A data node never needs to run twice within one chain of data pulls.
2. **Re-entrancy guard** — if the node is in `_currently_executing`, the call returns immediately. This prevents infinite recursion if a cycle somehow survived DAG validation.

### Cache invalidation in loops

When a node calls `set_output()` with a new value during loop iteration, the engine discards all downstream data-only nodes from `_executed_nodes`. This forces them to re-run and pick up the new value on the next iteration rather than serving a stale cached result. This is essential for patterns like `ForEach → GetListItem → SomeDataTransform → HoudiniNode`.

---

## 6. Execution Order Guarantees

### Exec-chain order

Within a single exec chain, nodes execute strictly sequentially. Node B does not start until node A's `execute()` coroutine returns and all reactive data propagation has completed. This is because `_execute_flow` is a single `await` chain: A calls `set_output("exec_out", True)`, which `await`s `_execute_flow(B)`, and so on.

### Parallel chains

Multiple independent exec chains (multiple entry nodes) are launched as concurrent asyncio tasks. They interleave at `await` points, which means I/O in one chain does not block progress in another. Shared state (e.g. `BaseNode.memory`) is not protected by a lock; if two chains write to the same variable key simultaneously, the result is non-deterministic. Design parallel chains to be independent or to use different variable namespaces.

### Data node order

In data-flow mode (no exec connections), nodes in the same topological layer run concurrently via `asyncio.gather()`. Nodes in later layers are guaranteed to run after all nodes in earlier layers have completed.

In flow mode, data-only upstream nodes are pulled in port-definition order. The order in which ports were added to the node definition determines the order upstream data nodes are evaluated.

---

## 7. Loop Execution

Two builtin nodes implement looping: `ForEachNode` and `WhileLoopNode`. Both use `set_output` to trigger exec flow from within a single `execute()` coroutine.

### ForEach

`ForEachNode.execute()` iterates over a list. For each element it:

1. Calls `await self.set_output("current_item", element)` and `await self.set_output("current_index", i)`. This propagates the values to downstream data nodes and marks those nodes as stale in `_executed_nodes` (via the reactive propagation logic in the engine).
2. Calls `await self.set_output("exec_step", True)`. The engine sees an exec output become truthy and follows all exec connections from `exec_step`, executing the downstream chain to completion.
3. Repeats for the next element.

After all elements are processed, `ForEachNode` calls `await self.set_output("exec_out", True)` to signal completion.

Because each `set_output("exec_step", True)` call awaits the full downstream chain before returning, iterations are strictly sequential — there is no concurrency between loop bodies.

### WhileLoop

`WhileLoopNode.execute()` reads a `break_condition` input at the start of each iteration. The `break_condition` port is excluded from cycle detection in `GraphManager.get_topological_sort()` (via `ignore_ports=["break_condition"]`), which is what allows the feedback wire without triggering a `CircularDependencyError`.

On each iteration, `WhileLoopNode`:

1. Checks `inputs.get("break_condition")`. If truthy, fires `exec_out` and returns.
2. Fires `exec_loop_body` to execute the loop body chain.
3. After the loop body completes, pulls the `break_condition` again (it was discarded from `_executed_nodes` by reactive propagation).
4. Repeats.

The `is_stopped()` check should be called inside long-running while loops to respect cancellation:

```python
while not self.is_stopped():
    if inputs.get("break_condition"):
        break
    await self.set_output("exec_loop_body", True)
    inputs = self.parameters.copy()  # re-read inputs after body
```

---

## 8. GroupNode Sub-Executor

`GroupNode` (`src/nodes/builtins/group_node.py`) encapsulates a complete `WorkflowModel` and runs it with a nested `NetworkExecutor`.

### Memory preservation

The outer executor sets `BaseNode.memory` to the current shared variable state before the sub-executor runs. The sub-executor's `run()` clears `BaseNode.memory` at the start (as it does for every run). To prevent this from erasing the outer execution's variables, `GroupNode.execute()` saves and restores memory around the sub-execution:

```python
saved_memory = dict(_BaseNode.memory)
sub_executor = NetworkExecutor(gm)
# ... connect signals ...
try:
    await sub_executor.run()
finally:
    _BaseNode.memory.clear()
    _BaseNode.memory.update(saved_memory)
```

### Input injection

External input values are injected into `GroupInNode` instances via `parameters["_injected_value"]` rather than `parameters["value"]`. The `value` key is an output port; the engine's `clear_outputs()` resets it to `None` during node preparation, before `execute()` is called. Using a distinct internal key (`_injected_value`) avoids the wipe.

### Output collection

After the sub-executor finishes, `GroupNode` collects outputs by reading from `sub_executor.node_results` of the *source* nodes connected to each `GroupOutNode`'s `value` input, rather than from `GroupOutNode` itself. This avoids a timing issue where `GroupOutNode` (a data-entry node) might have executed before the exec chain populated its input.

### Error propagation

`GroupNode` has two exec output ports:

- `exec_out` — fires when the inner graph completes with no unhandled exceptions.
- `exec_fail` — fires when the inner graph has at least one unhandled node exception (a `node_error` signal was emitted inside).

Semantic failures (e.g. a Houdini node returning `success=False`) are not considered unhandled exceptions; they are the inner graph's responsibility to route via its own exec pins.

---

## 9. Bypass Handling

A node can be bypassed by right-clicking it and selecting **Bypass** (or pressing **Ctrl+B**). The `bypassed` flag is stored on `NodeInstanceModel.bypassed`.

When the engine encounters a bypassed node during exec-chain traversal:

1. `node_started` is emitted immediately.
2. The node's `execute()` is not called.
3. `node_finished("success")` is emitted.
4. Every exec connection from this node is followed (all exec outputs fire), so the downstream chain continues uninterrupted.

Data inputs are **not** propagated through bypassed nodes. If a downstream node depended on this node's data output, it receives whatever default value the port was initialized with. This is intentional — bypass is a flow control shortcut, not a data pass-through.

---

## 10. init_priority System

`NodeInstanceModel.init_priority` is an integer field (default `0`). Any value greater than `0` marks the node as an initialisation node.

### Execution order

At the start of every run, before entry-node detection, the engine collects all nodes with `init_priority > 0`, sorts them in descending order (higher number runs first), and executes each one's full exec chain to completion before starting the next:

```python
init_node_ids = sorted(
    [nid for nid, m in self.graph_manager.nodes.items() if m.init_priority > 0],
    key=lambda nid: self.graph_manager.nodes[nid].init_priority,
    reverse=True,
)
for node_id in init_node_ids:
    self._track_task(self._execute_flow(node_id))
    # wait for all active tasks to finish before next init node
```

### Use cases

- `prism_core_init` — must run before any `prism_*` node so `PrismCore` is available in shared memory.
- Authentication nodes — log in to an API before the main pipeline starts.
- Data-initialisation nodes — pre-load a large dataset so it is ready when fast processing nodes need it.

### init_only mode

`NetworkExecutor.run(init_only=True)` runs only the init phase and then emits `execution_finished(True)` without proceeding to the main graph. This mode is used immediately after a workflow is loaded, giving init nodes a chance to set up environment state without requiring the user to click Run.

---

## 11. Error Propagation

When `SafeRuntime.run_node_safe()` catches an exception from `execute()`:

1. `node_error(node_id, error_message)` is emitted with the full traceback string.
2. `node_finished(node_id, "failed")` is emitted.
3. The function returns `False`. The caller (`_run_single_node_impl`) discards control — it does **not** follow any exec connections from the failed node.
4. The exec chain stops at the failed node. All downstream nodes in that chain are never executed.

The `node_error` signal is connected in `MainWindow` to the log panel, which displays the error in red with the node name.

### GroupNode error propagation

When a node inside a `GroupNode` fails, the sub-executor emits `node_error`. `GroupNode.execute()` catches this via a connected slot that appends to `inner_errors`. After the sub-executor finishes, if `inner_errors` is non-empty, `GroupNode` fires `exec_fail` instead of `exec_out` and calls `self.log_error()` to forward the messages to the parent executor's log.

### Manual error handling in nodes

Nodes can signal errors without raising exceptions by calling `self.log_error(msg)`. This writes to the log panel at "error" level but does not stop the exec chain. The node should still return a valid dict (with `exec_out: True` if it wants execution to continue) or `exec_out: False` to halt the chain deliberately.

---

## 12. Cancellation

The user can stop a running pipeline by clicking the **Stop** button, which calls `_EventLoopRunner.stop()`, which calls `executor.stop()`.

`NetworkExecutor.stop()`:

1. Sets `self._is_stopped = True`.
2. Calls `task.cancel()` on every task in `self._active_tasks`. This injects `CancelledError` into any awaiting coroutine.
3. Sets `self._finished_event` so the wait loop in `run()` exits.

### Cooperative cancellation inside long nodes

A node whose `execute()` runs a long synchronous loop should periodically check `self.is_stopped()`:

```python
async def execute(self, inputs):
    for frame in range(start, end):
        if self.is_stopped():
            self.log_info("Stopped by user.")
            return {"exec_out": False}
        await self.set_output("current_frame", frame)
        await self.set_output("exec_step", True)
    return {"exec_out": True}
```

For CPU-bound work offloaded with `asyncio.to_thread()`, cancellation of the outer task will cancel the `to_thread` call but the thread itself will continue running until Python's GIL allows it to be interrupted. Design threads to check a shared stop event if immediate termination is required.

---

## 13. node_results Dictionary

`NetworkExecutor.node_results` is a `Dict[UUID, Dict[str, Any]]` that stores the most recent output values of every node in the current run.

```python
# Structure
node_results = {
    node_instance_id_1: {"output_port_a": value, "output_port_b": value},
    node_instance_id_2: {"result": value, "exec_out": True},
    # ... one entry per executed node ...
}
```

### Population

Values enter `node_results` in two ways:

1. **From `execute()` return value** — after `SafeRuntime.run_node_safe()` returns successfully, the engine calls `self.node_results[node_id].update(result)`.
2. **From `set_output()` streaming** — when a node calls `await self.set_output(name, value)`, the engine's output handler stores `self.node_results[node_id][name] = value` immediately, before the exec chain fires.

### Use by the wire value inspector

`MainWindow._on_node_output` is connected to `node_output`. When it fires, the handler calls `scene.update_edge_value(node_widget, port_name, value)` for every key in the result dict. `NodeScene.update_edge_value()` finds all `Edge` items whose `from_port` matches and calls `edge.set_live_value(value)`. This makes the value visible as a tooltip when hovering over the wire.

`node_results` persists after execution completes, so users can inspect final wire values without re-running.

---

## 14. Signal Catalogue

All signals are defined on `NetworkExecutor(QObject)`. They are all thread-safe because they originate from the Qt main thread (via `_EventLoopRunner`).

| Signal | Parameters | When it fires |
|--------|-----------|---------------|
| `node_started` | `UUID` node_id | Immediately before `execute()` is called (or immediately for bypassed nodes) |
| `node_finished` | `UUID` node_id, `str` status | After `execute()` returns; status is `"success"` or `"failed"` |
| `node_error` | `UUID` node_id, `str` error_message | When `execute()` raises an unhandled exception; message includes full traceback |
| `node_output` | `UUID` node_id, `dict` output_data | After `execute()` returns (with the full result dict), and also after each `set_output()` call (with a single-key dict) |
| `node_log` | `UUID` node_id, `str` message, `str` level | When a node calls `log_info()`, `log_success()`, or `log_error()` |
| `execution_finished` | `bool` success | After all tasks complete or after `stop()` is called; `success=False` if stopped |

### Connecting to signals from outside the executor

```python
executor = NetworkExecutor(graph_manager)
executor.node_started.connect(lambda nid: print(f"Starting {nid}"))
executor.node_log.connect(lambda nid, msg, lvl: print(f"[{lvl}] {msg}"))
executor.execution_finished.connect(lambda ok: print(f"Done: {ok}"))
```

---

## 15. State Management

### What is reset on each run

- `BaseNode.memory` — cleared at the start of `run()`. This is a class-level dict shared by all nodes.
- `node_results` — reset to `{}` at the start of `run()`.
- `node_instances` — re-instantiated from scratch each run.
- `_executed_nodes`, `_currently_executing` — cleared.
- `_is_stopped` — set to `False`.
- All node output parameters — reset to their port defaults by `clear_outputs()`.

### What persists between runs

- `NodeInstanceModel.parameters` — widget values entered by the user persist across runs. Only ports with an incoming data connection are reset to the port's default at run start (to prevent stale widget values from overriding live data).
- `NodeRegistry._classes` / `_definitions` — the node library is not re-scanned between runs.
- File handles, external connections, and any Python-level state held by node instances are discarded because `node_instances` is rebuilt each run.

### BaseNode.memory

`BaseNode.memory` is a class-level `Dict[str, Any]` that acts as a simple shared scratchpad. Nodes access it directly:

```python
# SetVariable node
BaseNode.memory["my_var"] = value

# GetVariable node
value = BaseNode.memory.get("my_var")
```

Memory is shared across all nodes in the current run, including nodes inside `GroupNode` sub-executors (with the save/restore mechanism described in section 8). It is **not** thread-safe for concurrent access from multiple parallel exec chains.

---

## 16. GraphManager

`GraphManager` (`src/core/graph.py`) is a lightweight container for the graph's node and connection data. It does not execute anything; it is purely a data structure.

### Key attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `nodes` | `Dict[UUID, NodeInstanceModel]` | All nodes, keyed by instance UUID |
| `connections` | `List[ConnectionModel]` | All wires between ports |

### Cycle detection

`add_connection()` calls `is_dag()` after tentatively appending the new connection. `is_dag()` runs `get_topological_sort()` which uses the `toposort` library. If a `CircularDependencyError` is raised, the connection is removed and `add_connection()` returns `False`.

The `break_condition` port is excluded from dependency calculation by default, allowing while-loop feedback wires without being flagged as cycles:

```python
def get_topological_sort(self, ignore_ports=None):
    if ignore_ports is None:
        ignore_ports = ["break_condition"]
    # ...
    for conn in self.connections:
        if conn.to_port in ignore_ports:
            continue
        data[conn.to_node].add(conn.from_node)
```

### Serialization

`to_model()` returns a `WorkflowModel` (a Pydantic model). `from_model(model)` reconstructs the graph from a `WorkflowModel`. Both operations are `O(n)` in the number of nodes and connections.

---

## 17. NodeRegistry

`NodeRegistry` (`src/core/registry.py`) is a class-level singleton that stores all node definitions and their compiled Python classes.

### Three storage maps

| Map | Key | Value |
|-----|-----|-------|
| `_classes` | `node_id` (str) | `Type[BaseNode]` subclass |
| `_definitions` | `node_id` (str) | `NodeDefinitionJSON` Pydantic model |
| `_source_paths` | `node_id` (str) | Absolute path to the `.json` file on disk |

### Loading order on startup

```
NodeRegistry.load_all_with_extras(bundled_nodes)
      │
      ├─ register_builtins()
      │       Registers Python-class nodes (ForEach, WhileLoop, etc.)
      │       GroupInNode, GroupOutNode, GroupNode go into _classes only
      │       (hidden from search popup, still executable)
      │
      ├─ _load_directory(bundled_nodes)
      │       walks nodes/ recursively, calls load_node() for each .json
      │
      └─ extra_dirs from v_nodes_dir env var (OS path separator)
              _load_directory(extra_dir) for each
```

### JSON node registration

`register_definition(definition)` does two things:

1. Normalises the definition: inserts `exec_in` / `exec_out` ports if `use_exec=True` and they are missing; applies the Prism auto-rewrite if `node_id` starts with `prism_`.
2. Compiles the `python_code` with `exec()` and extracts the node class via `register_node()` (preferred) or a bare `execute()` function (simplified format).

### Hot-reload

`reload_node_definition(node_id)` re-reads the JSON from `_source_paths[node_id]` and re-registers. After calling this, any live `NodeWidget` instances bound to this `node_id` must be refreshed to pick up new ports or code. The Node Builder dialog calls this automatically after saving a node edit.

### Prism auto-rewrite

When `node_id.startswith("prism_")` and the code does not already import `resolve_prism_core`, the registry automatically prepends the import and rewrites:

```python
core = inputs.get('core')
# becomes:
core = resolve_prism_core(inputs)
```

This means every prism node automatically resolves `PrismCore` from shared memory without the author needing to wire a `core` output between nodes.

---

## 18. BaseNode Contract

Every node class must inherit from `BaseNode` and implement `execute()`. The full contract:

### Required

```python
class MyNode(BaseNode):
    name = "my_node"         # must match node_id; used as class identifier

    def __init__(self):
        super().__init__()   # adds exec_in, exec_out automatically
        self.add_input("some_input", "string", widget_type="text")
        self.add_output("some_output", "string")

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        value = inputs.get("some_input", "")
        return {"some_output": result, "exec_out": True}

def register_node():
    return MyNode
```

### Optional hooks

| Method | When called | Notes |
|--------|------------|-------|
| `restore_from_parameters(params)` | By engine before each run | Restore dynamic ports from saved workflow |
| `on_plug_sync(port, is_input, other, other_port)` | Synchronously when a wire is connected | Called on the Qt main thread |
| `on_unplug_sync(port, is_input)` | Synchronously when a wire is removed | Called on the Qt main thread |
| `async on_plug(port, is_input, other, other_port)` | Asynchronously when a wire is connected | Use for async initialization |
| `async on_unplug(port, is_input)` | Asynchronously when a wire is removed | |
| `async on_parameter_changed(name, value)` | When reactive data propagation updates an input | Re-run reactive nodes (TwoWaySwitch, GetVariable) |

### Streaming outputs

`set_output(name, value)` is an async method that pushes a single output value during execution without waiting for `execute()` to return:

```python
async def execute(self, inputs):
    for i in range(10):
        await self.set_output("progress", i / 10.0)
        await asyncio.sleep(0.1)   # simulate work
    return {"result": "done", "exec_out": True}
```

Every call to `set_output()` triggers reactive data propagation and, if the port is an exec port with a truthy value, triggers downstream execution.

---

## 19. SafeRuntime and Error Isolation

`SafeRuntime.run_node_safe()` wraps every `execute()` call in a `try/except`:

```python
@staticmethod
async def run_node_safe(fn, inputs):
    try:
        result = await fn(inputs)
        return True, result, None
    except Exception as e:
        error_msg = f"Node execution failed: {str(e)}\n{traceback.format_exc()}"
        return False, None, error_msg
```

This means a bug in one node's `execute()` never crashes the engine process. The error is captured as a string, emitted via `node_error`, and execution of that branch halts cleanly.

`SafeRuntime` does not suppress `asyncio.CancelledError` — cancellation from `runner.stop()` propagates normally through `await` chains.

---

## 20. Performance Considerations

### Blocking calls are dangerous

The asyncio event loop and the Qt event loop share the same OS thread. Any blocking call inside `execute()` — a synchronous `time.sleep()`, a blocking socket receive without timeout, a `subprocess.run()` call without async — will freeze the Qt UI for the duration of the block. No mouse events, no repaints, no signal deliveries.

Rules:
- Use `await asyncio.sleep(n)` instead of `time.sleep(n)`.
- Use `asyncio.open_connection()` instead of blocking sockets.
- Use `asyncio.create_subprocess_exec()` for subprocesses.
- For blocking Python code that cannot be made async, use `asyncio.to_thread()`.

### Offloading CPU work

```python
import asyncio

async def execute(self, inputs):
    heavy_data = inputs.get("data")
    result = await asyncio.to_thread(self._cpu_intensive, heavy_data)
    return {"output": result, "exec_out": True}

def _cpu_intensive(self, data):
    # This runs in a thread pool — does not block the event loop
    return expensive_computation(data)
```

`asyncio.to_thread()` is available in Python 3.9+. For older versions use `loop.run_in_executor(None, fn, *args)`.

### Houdini bridge latency

Each `HouBridge` RPC call involves: serialising JSON, a TCP round-trip to the local Houdini server, `hdefereval.executeDeferred()` scheduling on Houdini's main thread, execution, serialisation, and a TCP reply. On a local machine this is typically 1–5 ms per call (with `TCP_NODELAY` set). A node that makes 100 bridge calls will take ~100–500 ms. Batch multiple parameter sets with `bridge.set_parms()` and batch child queries with a single `bridge.run_code()` call where possible.

### Graph size

For graphs with 100+ nodes, the topological sort (`toposort` library) and connection lookup become measurable. The engine pre-calculates `_incoming_data_conns` and `_driven_by_flow` once per run to avoid per-node O(n) scans. The main loop is O(n + e) where n = node count and e = connection count. Execution time is dominated by `execute()` coroutine time, not engine overhead.

### Memory

`node_results` stores every output value of every node. For nodes that output large data structures (big lists, numpy arrays, large strings), this can accumulate significant memory during a run. Values are discarded when `node_results` is reset at the next run's start. If memory is a concern, avoid storing large objects in `node_results` across the run — produce them, consume them, and release references.
