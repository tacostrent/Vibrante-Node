# Full API Reference — Vibrante-Node v2.5.0

This document is the complete public API reference for all classes, signals,
and utilities available to node authors, workflow automation scripts, and
plugin developers.

---

## Table of Contents

1. [BaseNode](#1-basenode)
2. [Port](#2-port)
3. [NetworkExecutor](#3-networkexecutor)
4. [GraphManager](#4-graphmanager)
5. [NodeRegistry](#5-noderegistry)
6. [WorkflowModel](#6-workflowmodel)
7. [NodeInstanceModel](#7-nodeinstancemodel)
8. [ConnectionModel](#8-connectionmodel)
9. [PortModel](#9-portmodel)
10. [NodeDefinitionJSON](#10-nodedefinitionjson)
11. [StickyNoteModel](#11-stickynotemodel)
12. [BackdropModel](#12-backdropmodel)
13. [Scripting Console API](#13-scripting-console-api)
14. [Automation API](#14-automation-api)
15. [ConfigManager](#15-configmanager)
16. [HouBridge](#16-houbridge)
17. [Prism Integration](#17-prism-integration)

---

## 1. BaseNode

**Module:** `src.nodes.base`

Abstract base class for all custom nodes. See
[14_custom_nodes_api.md](14_custom_nodes_api.md) for the full developer guide.

### Class attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"BaseNode"` | Registry key. Must match `node_id`. |
| `node_id` | `str` | (injected by registry) | Same as `name` for JSON nodes. |
| `description` | `str` | `""` | Shown in UI tooltips. |
| `category` | `str` | `"General"` | Library grouping. |
| `icon_path` | `Optional[str]` | `None` | Relative path to SVG/PNG icon. |
| `memory` | `Dict[str, Any]` | `{}` | Class-level shared dict, cleared each run. |

### Instance attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `inputs` | `Dict[str, Port]` | Input ports keyed by name. |
| `outputs` | `Dict[str, Port]` | Output ports keyed by name. |
| `parameters` | `Dict[str, Any]` | Widget values, output cache, internal state. |
| `parameter_types` | `Dict[str, Type]` | Optional type hints for `add_parameter()`. |

### Constructor

```python
def __init__(self, use_exec: bool = True)
```

Adds `exec_in` (input) and `exec_out` (output) of type `exec` when
`use_exec=True`.

### Methods

| Signature | Returns | Description |
|-----------|---------|-------------|
| `add_input(name, type="any", widget_type=None, options=None, default=None)` | None | Add input port + initialize parameter. |
| `add_output(name, type="any", default=None)` | None | Add output port + initialize parameter. |
| `add_exec_input(name="exec_in")` | None | Add exec-type input. |
| `add_exec_output(name="exec_out")` | None | Add exec-type output. |
| `add_parameter(name, param_type, default=None)` | None | Add internal non-port parameter. |
| `rebuild_ports()` | None | Notify canvas to refresh port layout. |
| `is_port_connected(name, is_input)` | `bool` | Query wire connection state. |
| `is_stopped()` | `bool` | True if pipeline cancellation requested. |
| `async set_output(name, value)` | None | Reactive value push + exec chain trigger. |
| `clear_outputs()` | None | Reset outputs to defaults (called by engine). |
| `set_parameter(name, value)` | None | Set parameter; handles dropdown list updates. |
| `get_parameter(name, default=None)` | `Any` | Safe parameter read. |
| `log_info(msg)` | None | Info-level log message. |
| `log_success(msg)` | None | Success-level log message. |
| `log_error(msg)` | None | Error-level log message. |
| `restore_from_parameters(parameters)` | None | Override to recreate dynamic ports. |
| `async on_parameter_changed(name, value)` | None | Override for reactive parameter response. |
| `async on_plug(port, is_input, node, port)` | None | Override for async connection event. |
| `on_plug_sync(port, is_input, node, port)` | None | Override for sync connection event. |
| `async on_unplug(port, is_input)` | None | Override for async disconnect event. |
| `on_unplug_sync(port, is_input)` | None | Override for sync disconnect event. |
| `async execute(inputs)` | `dict` | **Abstract. Implement in every node.** |

---

## 2. Port

**Module:** `src.nodes.base`

Describes a single input or output connection point.

### Constructor

```text
Port(
    name: str,
    data_type: str = "any",
    widget_type: str = None,
    options: List[str] = None,
    default: Any = None
)
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Port name. Unique within node inputs or outputs. |
| `data_type` | `str` | `string`, `int`, `float`, `bool`, `list`, `dict`, `any`, or `exec`. |
| `widget_type` | `Optional[str]` | Inline editor type. `None` = no editor. |
| `options` | `Optional[List[str]]` | Dropdown options. Non-`None` only for `dropdown` widgets. |
| `default` | `Any` | Default value when unconnected. |

Port objects are data-only and have no methods. Ports are stored in
`node.inputs` and `node.outputs` dicts, keyed by `name`.

---

## 3. NetworkExecutor

**Module:** `src.core.engine`

The async execution engine. Receives a `GraphManager`, prepares all node
instances, and runs the graph.

### Constructor

```text
NetworkExecutor(graph_manager: GraphManager)
```

`NetworkExecutor` is a `QObject`. It emits Qt signals for UI feedback.

### Signals

| Signal | Signature | Description |
|--------|-----------|-------------|
| `node_started` | `(UUID)` | Emitted just before a node's `execute()` is called. |
| `node_finished` | `(UUID, str)` | Emitted after a node completes. `str` is `"success"` or `"failed"`. |
| `node_error` | `(UUID, str)` | Emitted when a node raises an unhandled exception. `str` is the error message. |
| `node_output` | `(UUID, dict)` | Emitted after `execute()` returns or after `set_output()`. `dict` maps port names to values. |
| `node_log` | `(UUID, str, str)` | Emitted by `log_info/error/success`. Args: node UUID, message, level string (`"info"`, `"error"`, `"success"`). |
| `execution_finished` | `(bool)` | Emitted when the entire pipeline completes. `bool` is `True` if not stopped. |

### Methods

#### run (async)

```python
async def run(self, init_only: bool = False) -> None
```

Executes the full pipeline. The execution sequence:

1. `BaseNode.memory.clear()` — shared memory reset.
2. Precalculate exec-driven node set and data connection lookup maps.
3. For each node: instantiate, `restore_from_parameters()`, sync parameters,
   `clear_outputs()`, wire engine hooks.
4. `_bootstrap_prism_if_needed()` — initialise PrismCore if a
   `prism_core_init` node is present.
5. `_run_init_nodes()` — run nodes with `init_priority > 0` sequentially.
6. If `init_only=True`, stop here and emit `execution_finished(True)`.
7. Identify entry nodes (nodes with exec-out but no wired exec-in, plus all
   data-only connected nodes).
8. Kick off all entry nodes as async tasks; wait for all to complete.
9. Emit `execution_finished(not self._is_stopped)`.

When no exec connections exist, falls back to classic topological-sort
data-flow execution (layers run in parallel via `asyncio.gather`).

**Parameters:**
- `init_only` — When `True`, only the init phase runs (steps 1–6 above).
  Used after loading a saved workflow to trigger auth/login nodes automatically.

#### stop

```python
def stop(self) -> None
```

Requests cancellation. Sets `_is_stopped = True` and cancels all active
asyncio tasks. Calls `_finished_event.set()` to unblock the wait loop.

### Internal attributes (read-only)

| Attribute | Type | Description |
|-----------|------|-------------|
| `node_instances` | `Dict[UUID, BaseNode]` | Live node instances keyed by UUID. |
| `node_results` | `Dict[UUID, Dict[str, Any]]` | Output result cache keyed by UUID → port name. |
| `_is_stopped` | `bool` | Cancellation flag. |
| `_executed_nodes` | `Set[UUID]` | UUIDs of nodes that completed successfully this run. |

---

## 4. GraphManager

**Module:** `src.core.graph`

Manages the in-memory graph: nodes and connections. Validates DAG invariants.

### Constructor

```python
GraphManager()
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `nodes` | `Dict[UUID, NodeInstanceModel]` | Node instances keyed by UUID. |
| `connections` | `List[ConnectionModel]` | All connection edges. |

### Methods

#### add_node

```python
def add_node(self, node: NodeInstanceModel) -> None
```

Adds a node to the graph. The node is keyed by `node.instance_id`.

#### remove_node

```python
def remove_node(self, node_id: UUID) -> None
```

Removes the node and all connections touching it.

#### add_connection

```python
def add_connection(self, connection: ConnectionModel) -> bool
```

Adds a connection edge after checking for cycles. Returns `False` and discards
the connection if it would create a cycle (the graph must remain a DAG).

```python
conn = ConnectionModel(
    from_node=node_a.instance_id,
    from_port="result",
    to_node=node_b.instance_id,
    to_port="input",
    is_exec=False,
)
if not gm.add_connection(conn):
    print("Cycle detected — connection not added.")
```

#### remove_connection

```python
def remove_connection(self, connection_id: UUID) -> None
```

Removes the connection with the given UUID.

#### is_dag

```python
def is_dag(self) -> bool
```

Returns `True` if the current graph contains no cycles. Uses topological sort
internally; returns `False` if `toposort.CircularDependencyError` is raised.

#### get_topological_sort

```python
def get_topological_sort(
    self,
    ignore_ports: List[str] = None
) -> List[Set[UUID]]
```

Returns the nodes in topological order as a list of sets. Each set contains
nodes that can execute in parallel. Sets are ordered from upstream to
downstream.

**Parameters:**
- `ignore_ports` — Port names that are excluded from dependency calculation.
  Default is `["break_condition"]`, which prevents `WhileLoopNode`'s
  feedback port from creating false cycles.

Raises `toposort.CircularDependencyError` if a cycle exists.

#### to_model

```python
def to_model(self) -> WorkflowModel
```

Serialises the graph to a `WorkflowModel` (suitable for JSON export).

#### from_model

```python
def from_model(self, model: WorkflowModel) -> None
```

Populates the graph from a `WorkflowModel`. Replaces any existing nodes and
connections.

---

## 5. NodeRegistry

**Module:** `src.core.registry`

Class-level registry that maps `node_id` strings to `NodeDefinitionJSON` and
`Type[BaseNode]`.

### Class attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `_definitions` | `Dict[str, NodeDefinitionJSON]` | All registered definitions. |
| `_classes` | `Dict[str, Type[BaseNode]]` | All compiled node classes. |
| `_source_paths` | `Dict[str, str]` | node_id → on-disk JSON path (for reload). |
| `last_error` | `Optional[str]` | Error message from the most recent failed load. |

### Methods

#### load_all

```python
@classmethod
def load_all(cls, directory: str) -> None
```

Loads built-in nodes (via `register_builtins()`) then recursively scans
`directory` for `.json` files. Creates the directory if it does not exist.

#### load_all_with_extras

```python
@classmethod
def load_all_with_extras(cls, default_directory: str) -> None
```

Calls `load_all(default_directory)` then loads any additional directories
listed in the `v_nodes_dir` environment variable (path-separated).

**Always use this method (not `load_all`) when launching the full application.**

```python
NodeRegistry.load_all_with_extras("nodes")
```

#### _load_directory

```python
@classmethod
def _load_directory(cls, directory: str) -> None
```

Walks a single directory recursively and calls `load_node()` for every `.json`
file found. Does not register builtins.

#### load_node

```python
@classmethod
def load_node(cls, file_path: str) -> bool
```

Loads and registers a single `.json` file. Returns `True` on success. Sets
`last_error` and returns `False` on failure (JSON parse error, validation
error, or compile error).

#### register_builtins

```python
@classmethod
def register_builtins(cls) -> None
```

Registers all built-in node classes:
- `FileLoaderNode`, `DataProcessorNode`, `ConsoleSinkNode`
- `SequenceNode`, `SetVariableNode`, `GetVariableNode`
- `TwoWaySwitchNode`, `ForEachNode`, `ListAppendNode`, `WhileLoopNode`
- `GroupInNode`, `GroupOutNode`, `GroupNode` (in `_classes` only — hidden
  from the search popup but loadable from saved workflows)

#### register_definition

```python
@classmethod
def register_definition(cls, definition: NodeDefinitionJSON) -> bool
```

Normalizes a `NodeDefinitionJSON` (adds missing exec pins, applies Prism
auto-patching), compiles the `python_code`, and stores the result in
`_definitions` and `_classes`. Returns `True` on success.

#### get_definition

```python
@classmethod
def get_definition(cls, node_id: str) -> Optional[NodeDefinitionJSON]
```

Returns the registered `NodeDefinitionJSON` for `node_id`, or `None`.

#### get_class

```python
@classmethod
def get_class(cls, node_id: str) -> Optional[Type[BaseNode]]
```

Returns the compiled node class for `node_id`, or `None`.

#### list_node_ids

```python
@classmethod
def list_node_ids(cls) -> List[str]
```

Returns all registered `node_id` strings. Includes only nodes in
`_definitions` (i.e., excludes `GroupInNode`, `GroupOutNode`, `GroupNode`).

#### get_source_path

```python
@classmethod
def get_source_path(cls, node_id: str) -> Optional[str]
```

Returns the absolute path to the `.json` file the node was loaded from.
Returns `None` for built-in nodes (they have no on-disk JSON).

#### reload_node_definition

```python
@classmethod
def reload_node_definition(cls, node_id: str) -> bool
```

Re-reads the node's JSON from disk and re-registers it. Returns `True` on
success. The updated class is available immediately for new node instances, but
existing `NodeWidget` instances in the canvas are not automatically refreshed.

#### delete_node

```python
@classmethod
def delete_node(cls, node_id: str, directory: str) -> None
```

Removes the node from `_definitions` and `_classes`, and deletes the
corresponding `.json` file from `directory` if it exists.

---

## 6. WorkflowModel

**Module:** `src.core.models`

Pydantic model representing a complete workflow (all nodes, connections, notes,
backdrops, and metadata).

### Constructor / Fields

```python
class WorkflowModel(BaseModel):
    nodes:        List[NodeInstanceModel] = []
    connections:  List[ConnectionModel]  = []
    sticky_notes: List[StickyNoteModel]  = []
    backdrops:    List[BackdropModel]    = []
    metadata:     Dict[str, Any]         = {}
```

### Serialisation

```python
# From dict / JSON:
workflow = WorkflowModel.model_validate(data_dict)

# To dict (for JSON serialisation):
data_dict = workflow.model_dump()

# JSON round-trip:
import json
json_str = json.dumps(workflow.model_dump())
workflow  = WorkflowModel.model_validate(json.loads(json_str))
```

UUIDs are serialised as strings in JSON. When loading, Pydantic coerces string
UUIDs back to `UUID` objects automatically.

### metadata field

`metadata` is a free-form dict for workflow-level information. Currently unused
by the engine but available for tooling (e.g., storing author, version,
description):

```python
workflow.metadata["author"] = "Studio Pipeline Team"
workflow.metadata["vibrante_version"] = "2.1.0"
```

---

## 7. NodeInstanceModel

**Module:** `src.core.models`

Pydantic model for a single node placed on the canvas.

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `instance_id` | `UUID` | auto | Unique instance ID. Generated by `uuid4()`. |
| `node_id` | `str` | — | References `NodeDefinitionJSON.node_id`. |
| `position` | `Tuple[float, float]` | — | (x, y) canvas position in scene coordinates. |
| `parameters` | `Dict[str, Any]` | `{}` | Saved widget values and dynamic port state. |
| `state` | `str` | `"idle"` | UI state hint. One of `"idle"`, `"running"`, `"success"`, `"failed"`. |
| `bypassed` | `bool` | `False` | When `True`, the engine skips `execute()` and passes exec through. |
| `init_priority` | `int` | `0` | `> 0` = run this node before the main graph. Higher values run first. |

### Example

```python
from uuid import uuid4
from src.core.models import NodeInstanceModel

node = NodeInstanceModel(
    node_id="text_upper",
    position=(200.0, 150.0),
    parameters={"text": "hello world"},
)
```

---

## 8. ConnectionModel

**Module:** `src.core.models`

Pydantic model for a single connection edge between two node ports.

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `UUID` | auto | Unique connection ID. |
| `from_node` | `UUID` | — | Source node `instance_id`. |
| `from_port` | `str` | — | Source port name. |
| `to_node` | `UUID` | — | Target node `instance_id`. |
| `to_port` | `str` | — | Target port name. |
| `is_exec` | `bool` | `False` | `True` for exec-type connections (triggers execution flow). |

### is_exec detection

The engine sets `is_exec=True` when both `from_port` and `to_port` are
`exec`-type ports. The UI sets this automatically when drawing wires. When
building connections programmatically:

```python
conn = ConnectionModel(
    from_node=a_uuid,
    from_port="exec_out",
    to_node=b_uuid,
    to_port="exec_in",
    is_exec=True,   # must be set manually when building programmatically
)
```

---

## 9. PortModel

**Module:** `src.core.models`

Pydantic model describing a port as stored in a `NodeDefinitionJSON`. Not the
same as `Port` (the runtime object in `src.nodes.base`).

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | — | Port name. |
| `type` | `str` | `"any"` | Data type string. |
| `widget_type` | `Optional[str]` | `None` | Inline editor type. |
| `options` | `Optional[List[str]]` | `None` | Dropdown option list. |
| `default` | `Optional[Any]` | `None` | Default value. |

---

## 10. NodeDefinitionJSON

**Module:** `src.core.models`

Pydantic model for the full node definition as stored on disk.

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `node_id` | `str` | — | Unique identifier. |
| `name` | `str` | — | Display name. |
| `description` | `str` | `""` | Tooltip text. |
| `category` | `str` | `"General"` | Library grouping. |
| `icon_path` | `Optional[str]` | `None` | Icon file path. |
| `use_exec` | `bool` | `True` | Auto-add exec pins. |
| `inputs` | `List[PortModel]` | `[]` | Input port definitions. |
| `outputs` | `List[PortModel]` | `[]` | Output port definitions. |
| `python_code` | `str` | — | Full Python source string. |

---

## 11. StickyNoteModel

**Module:** `src.core.models`

Pydantic model for a sticky note annotation on the canvas.

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `UUID` | auto | Unique ID. |
| `position` | `Tuple[float, float]` | — | (x, y) scene position. |
| `size` | `Tuple[float, float]` | `(200.0, 150.0)` | (width, height) in scene units. |
| `text` | `str` | `"New Note"` | Note content (plain text). |
| `color` | `str` | `"#ffffcc"` | Background color (hex string). |

---

## 12. BackdropModel

**Module:** `src.core.models`

Pydantic model for a backdrop (network box) grouping visual area on the canvas.

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `UUID` | auto | Unique ID. |
| `position` | `Tuple[float, float]` | — | (x, y) scene position (top-left corner). |
| `size` | `Tuple[float, float]` | `(400.0, 300.0)` | (width, height) in scene units. |
| `title` | `str` | `"Network Box"` | Label shown on the backdrop header. |
| `color` | `str` | `"#444444"` | Background color (hex string). |

---

## 13. Scripting Console API

The Scripting Console (View → Scripting Console, or Window → Scripting Console)
provides an interactive Python editor with access to the live application state.

### Available objects

| Variable | Type | Description |
|----------|------|-------------|
| `app` | `MainWindow` | The main application window. |
| `scene` | `NodeScene` | The currently active canvas scene. |
| `registry` | `NodeRegistry` | The class-level node registry. |
| `print` | function | Redirected — output appears in the log panel and debug panel. |
| `git` | Git | Wrapper around `subprocess.run(["git", ...])`. |

### scene methods available in scripts

| Method | Returns | Description |
|--------|---------|-------------|
| `scene.add_node_by_name(node_id, (x, y))` | `NodeWidget` | Add a node to the canvas. |
| `scene.find_node_by_name(name)` | `NodeWidget \| None` | Find the first node by display name. |
| `scene.connect_nodes(from_widget, from_port, to_widget, to_port)` | `Edge \| None` | Draw a wire. |

### app methods available in scripts

| Method | Description |
|--------|-------------|
| `app.get_current_scene()` | Returns the `NodeScene` for the active tab. |
| `app.execute_pipeline()` | Starts a pipeline run (same as clicking Run). |
| `app.log_panel.log(msg, level)` | Write a message to the log panel. `level` is `"info"`, `"success"`, or `"error"`. |

### Example: build a small workflow from script

```python
# Add two nodes
n1 = scene.add_node_by_name("text_upper", (100, 200))
n2 = scene.add_node_by_name("Console Sink", (400, 200))

# Set widget values
if n1:
    n1.set_parameter("text", "hello from script")

# Wire them together
if n1 and n2:
    edge = scene.connect_nodes(n1, "exec_out", n2, "exec_in")
    data_edge = scene.connect_nodes(n1, "result", n2, "data")

# Run the pipeline
app.execute_pipeline()
```

### Example: inspect all registered nodes

```python
for node_id in sorted(registry.list_node_ids()):
    defn = registry.get_definition(node_id)
    print(f"{node_id} ({defn.category}): {defn.description}")
```

---

## 14. Automation API

You can run workflows completely headlessly (without Qt or the GUI) from a
Python script.

### Minimal headless run

```python
import asyncio
import json
from src.core.models import WorkflowModel
from src.core.graph import GraphManager
from src.core.engine import NetworkExecutor
from src.core.registry import NodeRegistry

# 1. Load node definitions
NodeRegistry.load_all_with_extras("nodes")

# 2. Load workflow from file
with open("my_workflow.json") as f:
    workflow_data = json.load(f)
workflow = WorkflowModel.model_validate(workflow_data)

# 3. Build graph
gm = GraphManager()
gm.from_model(workflow)

# 4. Run
executor = NetworkExecutor(gm)

# Optional: connect signals for logging
executor.node_log.connect(lambda uid, msg, lvl: print(f"[{lvl}] {msg}"))
executor.execution_finished.connect(lambda ok: print(f"Done: {ok}"))

asyncio.run(executor.run())
```

Note: `NetworkExecutor` is a `QObject`. In a fully headless environment you need
a `QCoreApplication` instance for the Qt event loop and signal system:

```python
from PyQt5.QtCore import QCoreApplication
import sys
app_instance = QCoreApplication(sys.argv)
# ... then run executor as above
```

### Init-only run (load-time initialisation)

```python
# Runs init_priority > 0 nodes only (auth/login nodes)
asyncio.run(executor.run(init_only=True))
```

### Accessing results after a run

```python
# After asyncio.run(executor.run()):
for node_uuid, results in executor.node_results.items():
    node_model = gm.nodes.get(node_uuid)
    print(f"{node_model.node_id}: {results}")
```

### Building a workflow programmatically

```python
from uuid import uuid4
from src.core.models import NodeInstanceModel, ConnectionModel, WorkflowModel
from src.core.graph import GraphManager

gm = GraphManager()

# Create node instances
n1 = NodeInstanceModel(node_id="text_upper", position=(0, 0),
                        parameters={"text": "hello"})
n2 = NodeInstanceModel(node_id="Console Sink", position=(300, 0))
gm.add_node(n1)
gm.add_node(n2)

# Connect exec chain
gm.add_connection(ConnectionModel(
    from_node=n1.instance_id, from_port="exec_out",
    to_node=n2.instance_id,   to_port="exec_in",
    is_exec=True,
))

# Connect data
gm.add_connection(ConnectionModel(
    from_node=n1.instance_id, from_port="result",
    to_node=n2.instance_id,   to_port="data",
))

# Run
executor = NetworkExecutor(gm)
asyncio.run(executor.run())
```

---

## 15. ConfigManager

**Module:** `src.utils.config_manager`

Singleton that persists user settings to `~/.vibrante_node_config.json`.

### Accessing the singleton

```python
from src.utils.config_manager import config   # pre-instantiated singleton

# Or:
from src.utils.config_manager import ConfigManager
config = ConfigManager()   # returns the same singleton
```

### Generic key/value access

#### get

```python
def get(self, key: str, default=None) -> Any
```

Returns the value for `key`, or `default` if not set.

```python
theme = config.get("theme", "dark")
```

#### set

```python
def set(self, key: str, value: Any) -> None
```

Sets `key` to `value` and immediately writes to disk.

```python
config.set("theme", "light")
```

### Recent files

#### get_recent_files

```python
def get_recent_files(self) -> List[str]
```

Returns the list of up to 10 recently opened file paths (newest first).

#### add_recent_file

```python
def add_recent_file(self, path: str) -> None
```

Prepends `path` to the recent files list, removes any existing entry for the
same path, and trims to 10 entries. Saves immediately.

#### clear_recent_files

```python
def clear_recent_files(self) -> None
```

Empties the recent files list and saves.

### Gemini API key

#### get_gemini_api_key

```python
def get_gemini_api_key(self) -> str
```

Returns the stored Gemini API key string, or `""` if not set.

#### set_gemini_api_key

```python
def set_gemini_api_key(self, api_key: str) -> None
```

Stores the Gemini API key and saves to disk.

### Config file location

```python
import os
path = os.path.expanduser("~/.vibrante_node_config.json")
```

---

## 16. HouBridge

**Module:** `src.utils.hou_bridge`

JSON-RPC client for the Houdini command server (`vibrante_hou_server.py`)
running inside a live Houdini session.

### Getting the singleton

```python
from src.utils.hou_bridge import get_bridge

bridge = get_bridge()   # returns the module-level HouBridge singleton
```

```python
from src.utils.hou_bridge import is_available

if is_available():
    bridge = get_bridge()
    # ... do Houdini work
else:
    self.log_error("Houdini is not connected.")
```

### Constructor (advanced use)

```text
HouBridge(host: str = "127.0.0.1", port: int = None)
```

`port` defaults to the value of the `VIBRANTE_HOU_PORT` environment variable,
or `18811` if the variable is not set.

### Connection management

The bridge connects lazily on the first method call. It uses:
- `socket.TCP_NODELAY` — disables Nagle's algorithm (~40 ms latency eliminated
  on Windows).
- `socket.timeout(30)` — 30-second timeout per call. If the server does not
  respond, a `ConnectionError` is raised with a descriptive message.
- Auto-reconnect on `BrokenPipeError` / `ConnectionResetError` — the client
  retries the `sendall` once after reconnecting.
- `threading.Lock` — `_send()` is fully thread-safe.

### API Methods

All methods are synchronous. They block until the Houdini server responds (up
to 30 seconds by default).

---

#### ping

```python
def ping(self) -> dict
```

Checks if the server is alive.

**Returns:** `{"status": "ok", "version": "<Houdini version string>"}`

---

#### create_node

```python
def create_node(self, parent: str, node_type: str, name: str = "") -> dict
```

Creates a new node inside the given parent path.

**Parameters:**
- `parent` — Parent node path (e.g., `"/obj"`, `"/obj/geo1"`).
- `node_type` — Houdini node type string (e.g., `"geo"`, `"box"`, `"attribwrangle"`).
- `name` — Optional name. Houdini auto-names if empty.

**Returns:** `{"path": "/obj/geo1", "name": "geo1", "type": "geo"}`

```python
result = bridge.create_node("/obj", "geo", "my_geo")
geo_path = result["path"]   # "/obj/my_geo"
```

---

#### delete_node

```python
def delete_node(self, path: str) -> dict
```

Deletes the node at the given path and all its children.

**Returns:** `{"deleted": "/obj/my_geo"}`

---

#### set_parm

```python
def set_parm(self, node: str, parm: str, value: Any) -> dict
```

Sets a single parameter value.

**Returns:** `{"set": True}`

```python
bridge.set_parm("/obj/my_geo/alembic1", "fileName", "/path/to/file.abc")
bridge.set_parm("/obj/my_geo/null1", "tx", 1.5)
```

---

#### get_parm

```python
def get_parm(self, node: str, parm: str) -> dict
```

Gets the current value of a single parameter.

**Returns:** `{"value": <current value>}`

```python
result = bridge.get_parm("/obj/my_geo/alembic1", "fileName")
path = result["value"]
```

---

#### set_parms

```python
def set_parms(self, node: str, parms: dict) -> dict
```

Sets multiple parameters in a single round-trip. More efficient than calling
`set_parm` repeatedly.

**Returns:** `{"set": True, "count": N}` where N is the number of parameters set.

```python
bridge.set_parms("/obj/my_geo/null1", {
    "tx": 1.0,
    "ty": 2.0,
    "tz": 0.0,
})
```

---

#### get_parms

```python
def get_parms(self, node: str) -> dict
```

Returns a flat dict of all parameter names and their current values for the
given node.

**Returns:** `{"parm_name": value, ...}` — one entry per parameter.

---

#### connect_nodes

```python
def connect_nodes(
    self,
    from_node: str,
    to_node: str,
    output: int = 0,
    input_idx: int = 0
) -> dict
```

Wires `from_node`'s output index `output` to `to_node`'s input index
`input_idx`.

**Returns:** `{"connected": True}`

```python
bridge.connect_nodes("/obj/geo1/alembic1", "/obj/geo1/convert1",
                     output=0, input_idx=0)
```

---

#### cook_node

```python
def cook_node(self, path: str, force: bool = False) -> dict
```

Forces the node to cook (evaluate). When `force=True`, invalidates the cook
cache first.

**Returns:** `{"cooked": True}`

---

#### run_code

```python
def run_code(self, code: str) -> dict
```

Executes arbitrary Python code **inside Houdini**. The `hou` module is
available. To return a value, assign to the local variable `result`.

**Returns:** `{"result": <value of local variable 'result', or None>}`

```python
result = bridge.run_code(
    "n = hou.node('/obj/my_geo'); "
    "result = n.displayNode().path() if n and n.displayNode() else None"
)
display_path = result.get("result")
```

---

#### scene_info

```python
def scene_info(self) -> dict
```

Returns information about the current Houdini scene.

**Returns:**
```python
{
    "hip_file":        "/path/to/scene.hip",
    "hip_name":        "scene.hip",
    "houdini_version": "20.5.410",
    "fps":             24.0,
    "frame":           1.0,
    "frame_range":     [1, 240],   # [1, 240] fallback in headless Houdini
}
```

Note: `frame_range` falls back to `[1, 240]` in headless Houdini (hbatch /
hython) because `hou.playbar.frameRange()` raises `AttributeError` in that
context.

---

#### node_info

```python
def node_info(self, path: str) -> dict
```

Returns detailed information about a specific node.

**Returns:**
```python
{
    "path":              "/obj/my_geo",
    "name":              "my_geo",
    "type":              "geo",
    "category":          "Object",     # "Object", "Sop", "Shop", etc.
    "input_connectors":  0,
    "output_connectors": 0,
    "inputs":            ["/obj/other"],  # connected input paths (or None)
    "outputs":           ["/obj/child"],  # connected output paths
    "children":          ["alembic1", "convert1"],  # child node names
}
```

---

#### children

```python
def children(self, path: str = "/obj") -> list
```

Lists the child nodes of the given path.

**Returns:** List of dicts, each with:
```python
{"name": "alembic1", "type": "alembic", "path": "/obj/my_geo/alembic1"}
```

```python
for child in bridge.children("/obj/my_geo"):
    print(child["path"])
    bridge.delete_node(child["path"])
```

---

#### node_exists

```python
def node_exists(self, path: str) -> dict
```

Checks whether a node exists at the given path.

**Returns:** `{"exists": True}` or `{"exists": False}`

```python
if bridge.node_exists("/obj/my_geo")["exists"]:
    bridge.delete_node("/obj/my_geo")
```

---

#### set_display_flag

```python
def set_display_flag(self, path: str, on: bool = True) -> dict
```

Sets the display flag on a SOP node. Raises `ValueError` (surfaced from
`hou.OperationFailed`) if the node type does not support display flags.

**Returns:** `{"set": True}`

---

#### set_render_flag

```python
def set_render_flag(self, path: str, on: bool = True) -> dict
```

Sets the render flag on a SOP node. Raises `ValueError` on unsupported types.

**Returns:** `{"set": True}`

---

#### layout_children

```python
def layout_children(self, path: str = "/obj") -> dict
```

Auto-layouts all child nodes within the given path.

**Returns:** `{"done": True}`

---

#### save_hip

```python
def save_hip(self, path: str = "") -> dict
```

Saves the current HIP file. When `path` is empty, saves to the current file
path. When `path` is provided, saves as a new file at that path.

**Returns:** `{"saved": "/path/to/saved.hip"}`

---

#### set_expression

```python
def set_expression(
    self,
    node: str,
    parm: str,
    expression: str,
    language: str = "hscript"
) -> dict
```

Sets a parameter expression. `language` must be `"hscript"` or `"python"`.

**Returns:** `{"set": True}`

```python
bridge.set_expression("/obj/geo1/null1", "tx", "sin($F * 0.1)", language="hscript")
bridge.set_expression("/obj/geo1/null1", "ty", "hou.frame() * 0.05", language="python")
```

---

#### set_keyframe

```python
def set_keyframe(
    self,
    node: str,
    parm: str,
    frame: float,
    value: float
) -> dict
```

Sets a keyframe on a parameter at the given frame.

**Returns:** `{"set": True}`

```python
bridge.set_keyframe("/obj/geo1/null1", "tx", frame=1,   value=0.0)
bridge.set_keyframe("/obj/geo1/null1", "tx", frame=100, value=10.0)
```

---

#### set_frame

```python
def set_frame(self, frame: float) -> dict
```

Sets the current frame in Houdini's timeline.

**Returns:** `{"frame": <new frame>}`

---

#### set_playback_range

```python
def set_playback_range(self, start: float, end: float) -> dict
```

Sets the playback frame range.

**Returns:** `{"start": <start>, "end": <end>}`

---

### Error handling with HouBridge

All `HouBridge` methods raise:

- `ConnectionError` — when the socket cannot connect, times out (30 s), or
  the server closes the connection unexpectedly.
- `RuntimeError` — when the Houdini server returns an `"error"` key in the
  JSON-RPC response (e.g., the node path does not exist, or a Houdini API
  call fails).

Standard pattern for Houdini nodes:

```python
from src.utils.hou_bridge import get_bridge

async def execute(self, inputs):
    try:
        bridge = get_bridge()
        result = bridge.create_node("/obj", "geo", "my_geo")
        geo_path = result["path"]
        # ... more bridge calls ...
        return {"result_path": geo_path, "exec_out": True}
    except Exception as e:
        self.log_error(f"Houdini operation failed: {e}")
        return {"result_path": "", "exec_out": True}
```

---

## 17. Prism Integration

**Module:** `src.utils.prism_core`

Utilities for resolving and bootstrapping a `PrismCore` instance from Prism
Pipeline 2.x.

### resolve_prism_core

```python
def resolve_prism_core(inputs: dict = None) -> Optional[PrismCore]
```

Resolves the active `PrismCore` instance using the following priority order:

1. **`inputs["core"]`** — if `inputs` is a dict and contains a `"core"` key
   with a non-`None` value, that value is stored and returned.
2. **`BaseNode.memory["_prism_core"]`** — shared workflow memory (set by the
   engine's Prism bootstrap step or a previous call to `store_prism_core()`).
3. **Module-level cache** (`_CACHED_PRISM_CORE`) — survives across runs.
4. **`__main__.pcore`** — checks if a `pcore` attribute exists in `__main__`
   (present when running from inside a live Prism DCC session).

Returns `None` if PrismCore is not available.

**Usage inside a `prism_*` node (after auto-patching by registry):**

```python
async def execute(self, inputs):
    core = resolve_prism_core(inputs)   # auto-inserted by registry
    if core is None:
        self.log_error("PrismCore not initialized.")
        return {"exec_out": True}
    # use core normally
```

### bootstrap_prism_core

```python
def bootstrap_prism_core(
    prism_scripts_path: str = "C:/Program Files/Prism2/Scripts",
    load_project: bool = True,
    show_ui: bool = False,
) -> PrismCore
```

Synchronously initialises `PrismCore` on the calling thread and caches it.
**Must be called from the Qt main thread** because Prism's Qt widgets must be
parented to the main event loop.

Called automatically by `NetworkExecutor._bootstrap_prism_if_needed()` when a
`prism_core_init` node is present in the graph. You rarely need to call this
directly.

**Parameters:**
- `prism_scripts_path` — Path to the Prism 2 Scripts directory.
- `load_project` — If `True`, calls Prism with the `"loadProject"` arg.
- `show_ui` — If `True`, shows the Prism UI; otherwise creates a headless core.

**Returns:** The initialised `PrismCore` instance.

### store_prism_core

```python
def store_prism_core(core: Any) -> Any
```

Writes `core` to both `BaseNode.memory["_prism_core"]` and the module-level
cache. Returns `core`. Called automatically by `resolve_prism_core()` whenever
it successfully finds a core instance.

### Prism node pattern

```python
from src.nodes.base import BaseNode
from src.utils.prism_core import resolve_prism_core

class Prism_Get_Assets(BaseNode):
    name = "prism_get_assets"
    category = "Prism"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("entity",  "string", widget_type="text")
        self.add_output("assets", "list")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        core = resolve_prism_core(inputs)
        if core is None:
            self.log_error("PrismCore not available. Add a prism_core_init node.")
            return {"assets": [], "exec_out": True}
        try:
            assets = core.getAssets(entity=inputs.get("entity", ""))
            return {"assets": list(assets), "exec_out": True}
        except Exception as e:
            self.log_error(f"Prism error: {e}")
            return {"assets": [], "exec_out": True}

def register_node():
    return Prism_Get_Assets
```

### Prism node conventions

| Convention | Rule |
|-----------|------|
| `node_id` | Must start with `prism_` (e.g., `prism_get_assets`) |
| `category` | Must be `"Prism"` |
| `icon_path` | Use `"icons/prism_icon.png"` |
| `core` port | Do NOT add — resolved automatically |
| Guard | Always check `if core is None` and return a safe default |
| List outputs | Wrap in `list(...)` to ensure serializability |
| `prism_core_init` node | Must be present anywhere in the graph; bootstraps automatically |

### Auto-patching for prism_ nodes

The `NodeRegistry._prepare_definition()` method automatically patches any
node whose `node_id` starts with `prism_` (except `prism_core_init`):

1. Prepends `from src.utils.prism_core import resolve_prism_core` if missing.
2. Replaces `core = inputs.get('core')` with `core = resolve_prism_core(inputs)`.

This means existing nodes written with the old `core` wire pattern continue to
work without modification. New nodes can write `core = inputs.get("core")` and
the registry replaces it at compile time.

---

*For node development tutorials and examples, see [05_node_development.md](05_node_development.md).*  
*For the full custom node SDK reference, see [14_custom_nodes_api.md](14_custom_nodes_api.md).*
