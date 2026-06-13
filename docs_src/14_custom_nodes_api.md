# Custom Nodes SDK / API Reference — Vibrante-Node v2.5.0

This document is the authoritative reference for every class, method, attribute,
and hook exposed to custom node authors. It covers the full lifecycle from
`__init__` through execution, persistence, dynamic ports, and packaging.

---

## Table of Contents

1. [BaseNode Class Reference](#1-basenode-class-reference)
2. [Port Class Reference](#2-port-class-reference)
3. [Exec Pin Mechanics](#3-exec-pin-mechanics)
4. [set_output() Reactive System](#4-set_output-reactive-system)
5. [clear_outputs() Call Sequence](#5-clear_outputs-call-sequence)
6. [is_stopped() Cancellation](#6-is_stopped-cancellation)
7. [restore_from_parameters()](#7-restore_from_parameters)
8. [on_parameter_changed() Hook](#8-on_parameter_changed-hook)
9. [on_plug / on_unplug Hooks](#9-on_plug--on_unplug-hooks)
10. [Node Lifecycle](#10-node-lifecycle)
11. [JSON Schema Reference](#11-json-schema-reference)
12. [python_code Compilation](#12-python_code-compilation)
13. [register_node() Function](#13-register_node-function)
14. [Exec Flow Semantics](#14-exec-flow-semantics)
15. [Multiple Exec Outputs](#15-multiple-exec-outputs)
16. [GroupNode Pattern](#16-groupnode-pattern)
17. [Quick-Reference Tables](#17-quick-reference-tables)
18. [Packaging Node Plugins](#18-packaging-node-plugins)
19. [Distributing Nodes](#19-distributing-nodes)

---

## 1. BaseNode Class Reference

```python
from src.nodes.base import BaseNode
```

`BaseNode` is an abstract class. Every custom node must inherit from it and
implement `execute()`.

### Class Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"BaseNode"` | Must match `node_id` in the JSON file. Used as the primary key in the registry. |
| `description` | `str` | `""` | Human-readable description shown in the library and node tooltip. |
| `category` | `str` | `"General"` | Groups the node in the library panel. |
| `icon_path` | `Optional[str]` | `None` | Relative path from app root to an SVG or PNG icon. |
| `memory` | `Dict[str, Any]` | `{}` | **Class-level** shared dict. Cleared to `{}` at the start of each pipeline run. All instances see the same dict within a run. |
| `node_id` | `str` | (set by registry) | Set by `NodeRegistry` at registration time. Mirrors `name` for JSON-defined nodes. |

### Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `inputs` | `Dict[str, Port]` | All input ports, keyed by port name. Populated in `__init__`. |
| `outputs` | `Dict[str, Port]` | All output ports, keyed by port name. Populated in `__init__`. |
| `parameters` | `Dict[str, Any]` | Persistent key/value store. Widget values, output values, and internal state all live here. |
| `parameter_types` | `Dict[str, Type]` | Optional type hints per parameter key (used by `add_parameter()`). |

### Internal Hooks (do not set manually)

These are set by the engine and UI at runtime. They are documented here for
completeness but you should never assign to them directly in your node.

| Attribute | Set by | Purpose |
|-----------|--------|---------|
| `_on_log` | Engine | Routes `log_*` calls to the log panel signal. |
| `_pending_logs` | BaseNode | Buffer for log calls made before `_on_log` is wired. |
| `_on_output` | Engine | Called by `set_output()` to propagate values and trigger exec chains. |
| `_check_stopped` | Engine | Returns `True` if the user clicked Stop. |
| `_on_ports_changed` | UI | Called by `rebuild_ports()` to refresh the canvas widget. |
| `_is_port_connected` | UI | Returns `True` if a named port has a connected wire. |
| `_on_dropdown_options_changed` | UI | Called by `set_parameter()` when a dropdown's option list changes. |

---

### Constructor

```python
def __init__(self, use_exec: bool = True)
```

**Parameters:**

- `use_exec` — When `True` (the default), automatically adds `exec_in` (input)
  and `exec_out` (output) ports of data_type `exec`. Pass `False` for
  data-only nodes.

**You must call `super().__init__()` as the very first line of your `__init__`.**
Do not pass arguments unless you intentionally want `use_exec=False`:

```python
def __init__(self):
    super().__init__()            # use_exec=True (default)
    # ... add your ports here
```

```python
def __init__(self):
    super().__init__(use_exec=False)   # no exec pins
    # ... add your ports here
```

---

### Port Management Methods

#### add_input

```python
def add_input(
    self,
    name: str,
    data_type: str = "any",
    widget_type: str = None,
    options: List[str] = None,
    default: Any = None
) -> None
```

Adds an input port. Also initializes `self.parameters[name]` to `default` if
the key does not already exist. Default values are coerced by type if `default`
is `None`:

| `data_type` | Auto-default |
|-------------|-------------|
| `string` | `""` |
| `list` | `[]` |
| `bool` | `False` |
| `int` / `float` / `number` | `0` |
| others | `None` |

**Call this only inside `__init__` or `restore_from_parameters()`.** Calling it
during `execute()` creates ports mid-run which the engine was not prepared for.

#### add_output

```python
def add_output(
    self,
    name: str,
    data_type: str = "any",
    default: Any = None
) -> None
```

Adds an output port. Applies the same type-based auto-default as `add_input`.
Also initializes `self.parameters[name]` to `default`.

#### add_exec_input

```python
def add_exec_input(self, name: str = "exec_in") -> None
```

Convenience wrapper: calls `add_input(name, data_type="exec")`. Rarely needed
directly — `super().__init__(use_exec=True)` already calls it.

#### add_exec_output

```python
def add_exec_output(self, name: str = "exec_out") -> None
```

Convenience wrapper: calls `add_output(name, data_type="exec")`. Use this to
add additional exec outputs beyond the default `exec_out`:

```python
self.add_exec_output("exec_fail")   # adds a failure branch
```

#### add_parameter

```python
def add_parameter(self, name: str, param_type: Type, default: Any = None) -> None
```

Adds an internal parameter (not a port). Useful for storing typed configuration
that does not appear as a port but is saved/restored with the workflow.

#### rebuild_ports

```python
def rebuild_ports(self) -> None
```

Notifies the UI canvas to redraw this node's ports. Call once after all
`add_input` / `del self.inputs[name]` operations are complete.

---

### Parameter Access Methods

#### set_parameter

```python
def set_parameter(self, name: str, value: Any) -> None
```

Sets `self.parameters[name] = value`. When `value` is a list **and** the named
port has `widget_type="dropdown"`, the dropdown's option list is replaced and
`_on_dropdown_options_changed` is fired. The current selection is preserved if
it still exists in the new list; otherwise the first option is selected.

#### get_parameter

```python
def get_parameter(self, name: str, default: Any = None) -> Any
```

Returns `self.parameters.get(name, default)`. Safe to call at any time.

#### `__getitem__` shortcut

```python
value = node["port_name"]   # equivalent to node.get_parameter("port_name")
```

---

### Connection Query Methods

#### is_port_connected

```python
def is_port_connected(self, name: str, is_input: bool) -> bool
```

Returns `True` if the named port currently has a connected wire. Queries the
UI via the `_is_port_connected` hook. Returns `False` if the hook is not set
(e.g., when running headlessly or in tests).

---

### Logging Methods

#### log_info

```python
def log_info(self, msg: str) -> None
```

Emits an informational (white/grey) message to the log panel.

#### log_success

```python
def log_success(self, msg: str) -> None
```

Emits a success (green) message to the log panel.

#### log_error

```python
def log_error(self, msg: str) -> None
```

Emits an error (red) message to the log panel.

All three methods buffer the message if `_on_log` is not yet wired (which can
happen if you log during `__init__`). The buffer is flushed when the engine
wires the hook before calling `execute()`.

---

### Output Methods

#### set_output (async)

```python
async def set_output(self, name: str, value: Any) -> None
```

Pushes `value` to the named output port reactively — before `execute()`
returns. The engine immediately:

1. Updates `self.parameters[name]` and the engine's `node_results` cache.
2. Propagates the value to all downstream nodes connected to this port.
3. If `name` is an `exec`-type port and `value` is truthy, triggers the
   full exec chain of every downstream node connected to it.

**Must be awaited.** Calling without `await` discards the coroutine silently.

#### clear_outputs

```python
def clear_outputs(self) -> None
```

Resets every output port's value in `self.parameters` to its default.
Called by the engine during node preparation, before `execute()` is called.
You should not call this manually.

---

### Cancellation

#### is_stopped

```python
def is_stopped(self) -> bool
```

Returns `True` if the user has requested pipeline cancellation (clicked Stop).
Check this inside long loops or before expensive operations:

```python
for item in items:
    if self.is_stopped():
        self.log_info("Cancelled by user.")
        break
    process(item)
```

Returns `False` when running headlessly (no hook wired).

---

### Abstract Method

#### execute (async, abstract)

```python
@abstractmethod
async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]
```

**You must implement this method.** It is the main execution entry point.

- **`inputs`** — A snapshot of `self.parameters` after all upstream values have
  been merged in. Read input values from here rather than from `self.parameters`
  to avoid race conditions with reactive propagation.
- **Return value** — A dict mapping output port names to values. Include
  `"exec_out": True` for exec-flow nodes to continue the chain. Return an empty
  dict or `None` if you have no outputs (rare).

---

## 2. Port Class Reference

```python
from src.nodes.base import Port
```

`Port` describes a single connection point on a node.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Unique name within the node's inputs or outputs dict. |
| `data_type` | `str` | One of `string`, `int`, `float`, `bool`, `list`, `dict`, `any`, `exec`. |
| `widget_type` | `Optional[str]` | Inline editor type shown when the port is unconnected. |
| `options` | `Optional[List[str]]` | Option list for `dropdown` widgets. `None` for all other types. |
| `default` | `Any` | Value used when no wire is connected and no widget value has been set. |

### Accessing ports

```python
port = instance.inputs["my_port"]
print(port.name, port.data_type, port.default)

port = instance.outputs["result"]
print(port.widget_type)   # always None for outputs
```

Ports are plain data objects — they do not have methods. To query whether a
port is connected, use `self.is_port_connected()`.

---

## 3. Exec Pin Mechanics

Exec pins are ports with `data_type="exec"`. They represent the **execution
flow** — the sequence in which nodes fire.

### exec_in

An exec-type input. When the upstream node fires `exec_out` (or any exec output
wired to this node's `exec_in`), the engine calls `execute()` on this node.

Nodes with `exec_in` only run when an exec signal arrives. They are **not** run
automatically by the engine's data-pull mechanism.

### exec_out

An exec-type output. When your `execute()` returns `{"exec_out": True}` or you
call `await self.set_output("exec_out", True)`, the engine recursively executes
all nodes whose `exec_in` is wired to this port.

### How the exec chain works

```
Node A (exec_out) ──► Node B (exec_in / exec_out) ──► Node C (exec_in)
```

1. Node A's `execute()` returns `{"exec_out": True}`.
2. The engine sees `exec_out` is truthy and its port type is `exec`.
3. The engine calls `_execute_flow(Node B)`.
4. Node B's `execute()` runs and returns `{"exec_out": True}`.
5. The engine calls `_execute_flow(Node C)`.
6. Node C's `execute()` runs.

The chain is depth-first. If Node B has two downstream exec nodes they are
triggered in order of connection.

### exec pins added by super().__init__()

When `use_exec=True`:
- `exec_in` is added to `self.inputs` with `data_type="exec"`.
- `exec_out` is added to `self.outputs` with `data_type="exec"`.

These are plain `Port` objects. The engine identifies exec ports by checking
`port.data_type == "exec"`.

### Deleting the default exec_out

Some built-in nodes (e.g., `ForEachNode`) delete the default `exec_out` and
replace it with more descriptive outputs:

```python
def __init__(self):
    super().__init__(use_exec=True)
    if "exec_out" in self.outputs:
        del self.outputs["exec_out"]
    self.add_exec_output("each_item")
    self.add_exec_output("exec_on_finished")
```

This is safe — the engine treats any `exec`-type output the same way.

---

## 4. set_output() Reactive System

`await self.set_output(name, value)` is the mechanism for reactive, mid-
execution value propagation.

### What happens when you call set_output

Inside the engine's `_on_output` handler (set up per-node before execution):

1. `node_results[node_id][name] = value` — result cache updated immediately.
2. `node_output` signal emitted — the UI updates wire tooltips.
3. For every data connection from this port to a downstream node:
   - `target.parameters[conn.to_port] = value` — downstream parameter updated.
   - `target_node_results[to_port] = value` — downstream result cache updated.
   - If the target node is not exec-driven (`to_node not in _driven_by_flow`),
     it is **invalidated** from `_executed_nodes` so it re-runs on next pull.
   - `await target.on_parameter_changed(to_port, value)` — reactive hook called.
4. If `name` is an exec port and `value` is truthy:
   - For every exec connection from this port, `_execute_flow(downstream_node)`
     is awaited sequentially.

### Ordering: set_output vs. return dict

The return dict is processed **after** `execute()` returns. Values pushed via
`set_output()` arrive at downstream nodes earlier. This matters for loops:

```python
# Loop iteration pattern
for item in items:
    await self.set_output("current_item", item)   # downstream sees item NOW
    await self.set_output("exec_step", True)       # trigger downstream exec chain
    await asyncio.sleep(0)                          # yield

return {"current_item": last_item, "exec_out": True}  # final cleanup
```

### set_output is safe to call multiple times

You can call `set_output` for the same port multiple times. Each call fully
propagates before the next `await` returns.

### set_output on exec ports: flow control

```python
await self.set_output("exec_out", True)   # continues the chain
await self.set_output("exec_fail", True)  # continues the failure branch
```

You can fire both in the same execute() call — both chains will run. To
restrict to one branch, use conditional logic.

---

## 5. clear_outputs() Call Sequence

The engine calls `instance.clear_outputs()` during node preparation — after
`restore_from_parameters()` but before syncing upstream values or calling
`execute()`.

```python
def clear_outputs(self) -> None:
    for name, port in self.outputs.items():
        self.parameters[name] = port.default
```

This resets every output port's cached value to its declared default (e.g.,
`""` for string, `[]` for list, `False` for bool).

**Why this matters for GroupInNode:** The `value` output port is reset to
`None` by `clear_outputs()` before `execute()` runs. That is why `GroupInNode`
reads from `self.parameters["_injected_value"]` (not `"value"`) — the injected
value is stored under a different key that `clear_outputs()` does not touch.

---

## 6. is_stopped() Cancellation

```python
def is_stopped(self) -> bool
```

Internally calls `self._check_stopped()`, which is wired by the engine to
`NetworkExecutor._is_stopped`. Returns `False` if the hook is not set.

### Pattern for long operations

```python
async def execute(self, inputs):
    for i, path in enumerate(file_list):
        if self.is_stopped():
            self.log_info(f"Stopped after {i} files.")
            return {"processed": i, "exec_out": True}

        process_file(path)
        if i % 10 == 0:
            await asyncio.sleep(0)   # yield periodically

    return {"processed": len(file_list), "exec_out": True}
```

### Pattern for async operations

The engine also cancels active `asyncio.Task` objects when `stop()` is called.
If your node is inside an `await`, the task receives `asyncio.CancelledError`.
Catch it if you need to clean up:

```python
try:
    result = await some_long_operation()
except asyncio.CancelledError:
    self.log_info("Operation cancelled.")
    raise   # re-raise so the engine knows the task was cancelled
```

---

## 7. restore_from_parameters()

```python
def restore_from_parameters(self, parameters: Dict[str, Any]) -> None
```

Called by the engine during node preparation — after the node class is
instantiated but before `clear_outputs()` and `execute()`. The `parameters`
argument is the dict loaded from the saved workflow file.

The base implementation does nothing (`pass`). Override it to recreate
**dynamic ports** from saved state.

### When to override

Override `restore_from_parameters()` if your node:
- Adds input or output ports dynamically at runtime.
- Needs to restore non-port state before execution (e.g., parse a config).

### Typical pattern

```python
def restore_from_parameters(self, parameters: Dict[str, Any]) -> None:
    # Recreate any step_N ports that were saved
    for key in parameters:
        if key.startswith("step_") and key not in self.inputs:
            self.add_input(key, "any")

    # Update internal counter
    count = max(
        (int(k.split("_")[1]) + 1 for k in parameters if k.startswith("step_")),
        default=1,
    )
    self._step_count = count
```

### Important: do not call rebuild_ports() here

`restore_from_parameters()` runs in the engine before the UI canvas exists
(when running headlessly) or before the canvas widget has been fully
initialized. Calling `rebuild_ports()` here is safe but unnecessary — the UI
rebuilds all ports when it creates the `NodeWidget`.

---

## 8. on_parameter_changed() Hook

```python
async def on_parameter_changed(self, name: str, value: Any) -> None
```

Called by the engine's reactive propagation system when an upstream node
pushes a new value to a data port of this node (via `set_output`). At this
point `self.parameters[name]` has already been updated.

**This is not called during `execute()` pre-sync.** It is only triggered by
reactive propagation mid-run.

### Use cases

- Recompute a derived output when an upstream value changes (e.g., `TwoWaySwitchNode`).
- Update dropdown options based on a connected category port.
- Log changes for debugging.

### Example: reactive switch

```python
async def on_parameter_changed(self, name: str, value: Any) -> None:
    if name in ("condition", "input_1", "input_2"):
        cond = bool(self.get_parameter("condition", False))
        val1 = self.get_parameter("input_1")
        val2 = self.get_parameter("input_2")
        await self.set_output("output", val1 if cond else val2)
```

This pattern allows `TwoWaySwitchNode` to update its output in real-time as
upstream nodes push new values during a `ForEachNode` loop, without waiting for
its own exec trigger.

---

## 9. on_plug / on_unplug Hooks

Four hooks fire when connections are created or removed in the canvas.

### on_plug (async)

```python
async def on_plug(
    self,
    port_name: str,
    is_input: bool,
    other_node: BaseNode,
    other_port_name: str
) -> None
```

Called asynchronously when a wire is connected to one of this node's ports.
Use for async operations that should happen when a port is connected (e.g.,
fetching options from a connected node).

### on_plug_sync

```python
def on_plug_sync(
    self,
    port_name: str,
    is_input: bool,
    other_node: BaseNode,
    other_port_name: str
) -> None
```

Called synchronously when a wire is connected. Use for immediate UI updates
such as adding a dynamic port:

```python
def on_plug_sync(self, port_name, is_input, other_node, other_port_name):
    if is_input and port_name == f"step_{self._step_count - 1}":
        self.add_input(f"step_{self._step_count}", "any")
        self._step_count += 1
        self.rebuild_ports()
```

### on_unplug (async)

```python
async def on_unplug(self, port_name: str, is_input: bool) -> None
```

Called asynchronously when a wire is removed from one of this node's ports.

### on_unplug_sync

```python
def on_unplug_sync(self, port_name: str, is_input: bool) -> None
```

Called synchronously when a wire is removed. Use for immediate port cleanup.

---

## 10. Node Lifecycle

The complete sequence from workflow load to execution completion:

```
1. NodeRegistry.get_class(node_id) → node_class
2. instance = node_class()
       │
       └── BaseNode.__init__(use_exec=True)
               ├── self.inputs = {}
               ├── self.outputs = {}
               ├── self.parameters = {}
               ├── add_exec_input("exec_in")
               ├── add_exec_output("exec_out")
               └── [your __init__ code: add_input(), add_output(), ...]

3. instance.restore_from_parameters(workflow_node.parameters)
       └── [your override: recreate dynamic ports from saved state]

4. Sync parameters from workflow:
       ├── For ports with incoming data connections: reset to port default
       └── For all other parameters: copy from saved workflow

5. instance.clear_outputs()
       └── self.parameters[output_name] = port.default  (for every output)

6. Upstream data nodes are pulled recursively (if not exec-driven)

7. Incoming connection values merged into instance.parameters

8. inputs = instance.parameters.copy()

9. instance.execute(inputs)
       ├── [your code: read inputs, compute results]
       ├── await self.set_output(...)  → reactive propagation + exec triggers
       └── return {output_name: value, ..., "exec_out": True}

10. result merged into node_results[node_id]
11. node_output signal emitted
12. node_finished signal emitted
```

---

## 11. JSON Schema Reference

Every node JSON file must conform to the `NodeDefinitionJSON` Pydantic model.

### Top-level fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `node_id` | `str` | Yes | Unique identifier. Snake_case recommended. Must match `name` class attribute. |
| `name` | `str` | Yes | Display name. Usually identical to `node_id`. |
| `description` | `str` | No | Shown in library tooltip. Defaults to `""`. |
| `category` | `str` | No | Library grouping. Defaults to `"General"`. |
| `icon_path` | `str \| null` | No | Relative path to an icon file. |
| `use_exec` | `bool` | No | Adds exec_in/exec_out if `true`. Defaults to `true`. |
| `inputs` | `PortModel[]` | No | List of input port definitions. |
| `outputs` | `PortModel[]` | No | List of output port definitions. |
| `python_code` | `str` | Yes | Full Python source as a single string. Use `\n` for newlines. |

### PortModel fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Port name. Must be unique within inputs (or outputs). |
| `type` | `str` | No | Data type. Defaults to `"any"`. |
| `widget_type` | `str \| null` | No | Inline editor. `null` = no widget. |
| `options` | `str[] \| null` | No | Options list for `dropdown` widgets. |
| `default` | `any` | No | Default value. `null` defers to type-based auto-default. |

### Exec pin normalization

When `use_exec=true`, the registry normalizes the JSON before compiling:

- If no input named `"exec_in"` exists, one is prepended automatically.
- If no output named `"exec_out"` exists, one is prepended automatically.

This means you can safely declare `"use_exec": true` and omit the exec pins
from the `inputs`/`outputs` arrays — the registry adds them. However, for
clarity it is recommended to include them explicitly.

### Minimal valid JSON

```json
{
    "node_id": "hello_world",
    "name": "hello_world",
    "python_code": "from src.nodes.base import BaseNode\n\nclass Hello_World(BaseNode):\n    name = 'hello_world'\n\n    async def execute(self, inputs):\n        self.log_info('Hello, World!')\n        return {'exec_out': True}\n\ndef register_node():\n    return Hello_World"
}
```

---

## 12. python_code Compilation

The registry compiles `python_code` using Python's built-in `exec()`:

```python
namespace = {}
exec(definition.python_code, namespace)
```

The compiled namespace is inspected for:

1. **`register_node` function** (preferred) — called to get the node class:
   ```python
   node_class = namespace['register_node']()
   ```

2. **`execute` function** (simplified format) — if no `register_node` but an
   `execute` function exists, a `DynamicNode` class is generated automatically.
   Any function in the namespace whose name starts with `_` is promoted to a
   class method.

### Class attribute injection

After the class is retrieved, the registry injects class attributes from the
JSON definition:

```python
node_class.name = definition.name
node_class.node_id = definition.node_id
node_class.category = definition.category
node_class.description = definition.description
node_class.icon_path = definition.icon_path
```

This means you do not need to set these in the class body — but setting them
there is harmless and useful for IDE autocomplete during development.

### Prism node auto-patching

For nodes whose `node_id` starts with `prism_` (except `prism_core_init`), the
registry automatically:

1. Prepends `from src.utils.prism_core import resolve_prism_core` if not already present.
2. Replaces `core = inputs.get('core')` with `core = resolve_prism_core(inputs)`.
3. Replaces `core = inputs.get("core")` with `core = resolve_prism_core(inputs)`.

This means `prism_*` nodes never need to wire a `core` input — PrismCore is
resolved automatically from the shared cache.

### Compilation errors

If `exec()` raises or the resulting class does not subclass `BaseNode`,
`NodeRegistry.last_error` is set to a descriptive message and the node is not
registered. Check this attribute after loading if a node silently disappears.

---

## 13. register_node() Function

```python
def register_node() -> Type[BaseNode]:
    return My_Node_Class
```

`register_node` must be a module-level function (not a method) that returns the
node class (not an instance). The registry calls it once at load time.

### Why not just import the class?

Using a function makes the registry agnostic to the class name. The function
acts as an explicit declaration: "this is the node class for this file."

### Alternative: no register_node

If `register_node` is absent but an `execute` function exists at module level,
the registry creates a `DynamicNode` wrapper. This simplified format works for
stateless one-file nodes but does not support lifecycle hooks.

---

## 14. Exec Flow Semantics

### When exec_out fires

`exec_out` fires in two ways:

1. **Via return dict** — `return {"exec_out": True}`. The engine processes the
   full return dict after `execute()` returns, then triggers exec chains.
2. **Via set_output** — `await self.set_output("exec_out", True)`. The exec
   chain fires immediately at that point, before `execute()` returns.

For simple nodes, use the return dict. For loops and streaming patterns, use
`set_output()`.

### When set_output fires vs. return dict

```
execute() called
    │
    ├── await self.set_output("partial", val)   ← fires NOW (reactive)
    │       └── downstream data nodes updated
    │
    ├── await self.set_output("exec_step", True) ← fires NOW (exec chain)
    │       └── downstream exec nodes run to completion
    │       └── control returns here after all downstream nodes finish
    │
    ├── ... more loop iterations ...
    │
    └── return {"result": val, "exec_out": True}
            └── exec_out chain fires AFTER execute() returns
```

### Bypass mode

When a node is bypassed (user right-clicked → Bypass), the engine skips
`execute()` and instead fires all exec outputs unconditionally, passing data
through unchanged. This allows the pipeline to run end-to-end even when
individual nodes are disabled.

---

## 15. Multiple Exec Outputs

Use multiple exec outputs to implement branching:

```python
self.add_exec_output("exec_success")   # fires when operation succeeds
self.add_exec_output("exec_fail")      # fires when operation fails
```

Only one branch fires per run (unless you explicitly fire both):

```python
async def execute(self, inputs):
    try:
        result = risky_operation()
        await self.set_output("exec_success", True)
        return {"result": result, "exec_success": True, "exec_fail": False}
    except Exception as e:
        self.log_error(str(e))
        await self.set_output("exec_fail", True)
        return {"result": None, "exec_success": False, "exec_fail": True}
```

Wire `exec_success` to normal downstream nodes and `exec_fail` to error
handling nodes (e.g., a notification node or a cleanup node).

### GroupNode exec branches

`GroupNode` uses exactly this pattern:
- `exec_out` fires when the inner graph completes without exceptions.
- `exec_fail` fires when an inner node emits `node_error`.

---

## 16. GroupNode Pattern

A `GroupNode` is a node that embeds a complete `WorkflowModel` and executes it
via a headless `NetworkExecutor` sub-process when triggered.

### How GroupNode executes

```python
async def execute(self, inputs):
    workflow = WorkflowModel.model_validate(self.parameters["__workflow__"])
    
    # Inject external inputs into group_in nodes
    for node_model in workflow.nodes:
        if node_model.node_id == "group_in":
            port_name = node_model.parameters.get("port_name", "")
            if port_name in inputs:
                node_model.parameters["_injected_value"] = inputs[port_name]
    
    gm = GraphManager()
    gm.from_model(workflow)
    
    sub_executor = NetworkExecutor(gm)
    await sub_executor.run()
    
    # Collect outputs from group_out nodes
    for inst_id, node_model in gm.nodes.items():
        if node_model.node_id == "group_out":
            port_name = node_model.parameters.get("port_name", "")
            value = sub_executor.node_results.get(inst_id, {}).get("value")
            await self.set_output(port_name, value)
```

### Creating nodes that run sub-executors

If you want a custom node that runs a sub-workflow, follow this pattern:
- Store the sub-workflow as `self.parameters["__workflow__"]` (a dict).
- In `restore_from_parameters()`, recreate dynamic ports from `parameters["__port_defs__"]`.
- In `execute()`, instantiate `GraphManager`, call `gm.from_model(workflow)`,
  create `NetworkExecutor(gm)`, and `await sub_executor.run()`.
- Save outer `BaseNode.memory` before and restore it after (the sub-executor
  clears memory on startup).

### GroupInNode injection key

GroupInNode reads `self.parameters["_injected_value"]` — not `"value"`. This
is critical because `"value"` is an output port and `clear_outputs()` resets it
to `None` before `execute()` is called. The `"_injected_value"` key is written
by the parent GroupNode after `clear_outputs()` has already run.

---

## 17. Quick-Reference Tables

### All port data types

| Type | Widget types available | Default value |
|------|----------------------|---------------|
| `string` | `text`, `text_area`, `dropdown`, `file`, `file_save` | `""` |
| `int` | `int`, `slider` | `0` |
| `float` | `float`, `slider` | `0` |
| `bool` | `bool` (checkbox) | `False` |
| `list` | none | `[]` |
| `dict` | none | `{}` |
| `any` | none (generic) | `None` |
| `exec` | none (internal) | `None` |

### All widget types

| `widget_type` | Data type | Description |
|---------------|-----------|-------------|
| `text` | string | Single-line text input |
| `text_area` | string | Multi-line text editor |
| `int` | int | Integer spinner |
| `float` | float | Float spinner |
| `bool` | bool | Checkbox toggle |
| `dropdown` | string | Combo box; requires `options` list |
| `slider` | int or float | 0–100 range slider |
| `file` | string | File path picker (open) |
| `file_save` | string | File path picker (save) |

### All BaseNode methods

| Method | Async | Returns | Description |
|--------|-------|---------|-------------|
| `add_input(name, type, widget_type, options, default)` | No | None | Add input port |
| `add_output(name, type, default)` | No | None | Add output port |
| `add_exec_input(name)` | No | None | Add exec input port |
| `add_exec_output(name)` | No | None | Add exec output port |
| `add_parameter(name, type, default)` | No | None | Add internal parameter |
| `rebuild_ports()` | No | None | Notify UI to redraw ports |
| `is_port_connected(name, is_input)` | No | `bool` | Check if port has a wire |
| `is_stopped()` | No | `bool` | Check if pipeline was cancelled |
| `set_output(name, value)` | Yes | None | Reactive value push |
| `clear_outputs()` | No | None | Reset outputs to defaults |
| `set_parameter(name, value)` | No | None | Set parameter (handles dropdown) |
| `get_parameter(name, default)` | No | `Any` | Safe parameter read |
| `log_info(msg)` | No | None | Info log message |
| `log_success(msg)` | No | None | Success log message |
| `log_error(msg)` | No | None | Error log message |
| `execute(inputs)` | Yes | `dict` | **Abstract — implement this** |
| `restore_from_parameters(params)` | No | None | Override to restore dynamic ports |
| `on_parameter_changed(name, value)` | Yes | None | Override for reactive response |
| `on_plug(port, is_input, node, port)` | Yes | None | Override for async connection event |
| `on_plug_sync(port, is_input, node, port)` | No | None | Override for sync connection event |
| `on_unplug(port, is_input)` | Yes | None | Override for async disconnect event |
| `on_unplug_sync(port, is_input)` | No | None | Override for sync disconnect event |

---

## 18. Packaging Node Plugins

A node plugin is a directory containing one or more node files plus an optional
metadata manifest.

### Recommended directory structure

```
my_nodes/
├── README.md                  ← (optional) human docs
├── nodes/
│   ├── my_category/
│   │   ├── my_node_a.json
│   │   └── my_node_b.json
│   └── my_other_node.json
├── icons/
│   └── my_icon.svg
└── scripts/
    └── my_script.py
```

The `NodeRegistry._load_directory()` method walks the directory recursively, so
any depth of nesting works.

### Icon paths

If your nodes reference custom icons, use paths relative to the **app root**
(where `src/main.py` lives), not relative to the plugin directory. When
distributing a plugin, either:
- Include the icons in the app's `icons/` directory.
- Use absolute paths in `icon_path`.
- Accept that icons will be missing on other machines (the node still works).

### Node file format checklist

Before packaging:
- `node_id` and `name` match and are snake_case.
- `python_code` compiles without errors (`exec(code, {})` in a Python REPL).
- All ports declared in `inputs`/`outputs` have matching `add_input`/`add_output`
  calls in `python_code`.
- `exec_in`/`exec_out` are not added manually in `__init__` for `use_exec=true` nodes.
- `register_node()` returns the correct class.
- The class has `name = "node_id"` matching the JSON.

---

## 19. Distributing Nodes

### Using the v_nodes_dir environment variable

Set `v_nodes_dir` to a colon-separated (Unix) or semicolon-separated (Windows)
list of directories. `NodeRegistry.load_all_with_extras()` loads nodes from
every directory in this list after loading the bundled nodes.

```bash
# Unix
export v_nodes_dir="/home/user/my_nodes:/shared/studio_nodes"

# Windows
set v_nodes_dir=C:\my_nodes;\\fileserver\studio_nodes
```

### Houdini plugin integration

For nodes specific to Houdini, place them in the plugin's `v_nodes_houdini/`
folder. The Houdini launch script (`vibrante_node_houdini.py`) sets
`v_nodes_dir` to include this folder automatically.

```
plugins/houdini/
└── v_nodes_houdini/
    ├── hou_create_geo.json
    ├── hou_set_parm.json
    └── ...
```

These nodes appear in the library only when the app is launched from Houdini.

### Registering nodes programmatically

```python
from src.core.registry import NodeRegistry

# Load an entire directory
NodeRegistry._load_directory("/path/to/my_nodes")

# Load a single file
NodeRegistry.load_node("/path/to/my_node.json")

# Register a Python class directly (for built-ins)
NodeRegistry._register_builtin_class(MyNodeClass)
```

### Reloading a node after editing

```python
# After editing my_node.json on disk:
NodeRegistry.reload_node_definition("my_node")
```

This re-reads the JSON, re-compiles the Python code, and replaces the class in
`_classes`. Existing `NodeWidget` instances in the canvas are **not** updated
automatically — close and reopen the workflow, or refresh via the Node Builder.

### Checking for registration errors

```python
if not NodeRegistry.load_node("/path/to/my_node.json"):
    print(NodeRegistry.last_error)
```

`last_error` is a string describing the most recent load failure, or `None` if
the last load succeeded.
