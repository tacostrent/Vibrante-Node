# Vibrante-Node — Node Builder API

**Version:** v2.4.0 | [User Guide](USER_GUIDE.md) | [Automation API](AUTOMATION_API.md) | [Developer Guide](DEVELOPER.md) | [Technical Reference](DOCUMENTATION.md)

This document is the complete reference for building custom nodes: `BaseNode`, port configuration, lifecycle hooks, the JSON node schema, distribution patterns, and integration with Houdini, Maya, Blender, and Prism Pipeline.

---

## Contents

1. [Node Architecture](#1-node-architecture)
2. [Node JSON Schema](#2-node-json-schema)
3. [BaseNode Class Reference](#3-basenode-class-reference)
4. [Port System](#4-port-system)
5. [Lifecycle Hooks](#5-lifecycle-hooks)
6. [Logging](#6-logging)
7. [Advanced Patterns](#7-advanced-patterns)
8. [Houdini Bridge Nodes](#8-houdini-bridge-nodes)
9. [Headless Action Nodes — Maya and Blender](#9-headless-action-nodes)
10. [Prism Pipeline Nodes](#10-prism-pipeline-nodes)
11. [Node Builder GUI](#11-node-builder-gui)
12. [Distribution and Installation](#12-distribution-and-installation)
13. [Common Mistakes](#13-common-mistakes)

---

## 1. Node Architecture

### What a Node Is

A node is a **Python class** (`BaseNode` subclass) paired with a **JSON definition file**. The class implements the logic; the JSON describes the ports, metadata, and embeds the Python source as a string.

At runtime the `NodeRegistry` reads the JSON, compiles the `python_code` field into a live Python class, and registers it. Users place the node on the canvas, wire its ports, and the execution engine calls `execute()`.

### Node Lifecycle During Execution

```
Engine starts a run
    │
    ▼
restore_from_parameters(saved_params)
    │ Rebuilds dynamic ports from the saved workflow state.
    ▼
clear_outputs()
    │ Resets all output port values to their defaults.
    ▼
sync inputs from upstream node results
    │ Wire values are copied into the node's parameter dict.
    ▼
execute(inputs)  ◄── your implementation runs here
    │
    ├──► await self.set_output(name, value)    (optional mid-execution push)
    │
    └──► return {"port_name": value, "exec_out": True}
              │
              └── engine propagates outputs, triggers downstream exec chain
```

### Minimal Node Example

```python
from src.nodes.base import BaseNode

class Repeat_String(BaseNode):
    name = "repeat_string"     # must match node_id in the JSON

    def __init__(self):
        super().__init__()     # adds exec_in and exec_out automatically
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("text",   "string", widget_type="text",  default="hello")
        self.add_input("count",  "int",    widget_type="int",   default=3)
        self.add_output("result", "string")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        text  = inputs.get("text", "")
        count = int(inputs.get("count", 1))
        return {
            "result":   (text + " ") * count,
            "exec_out": True,
        }

def register_node():
    return Repeat_String
```

---

## 2. Node JSON Schema

Every node is distributed as a single `.json` file. All fields:

```json
{
    "node_id":     "repeat_string",
    "name":        "repeat_string",
    "display_name": "Repeat String",
    "description": "Repeats a string N times.",
    "category":    "String",
    "icon_path":   "icons/string.svg",
    "use_exec":    true,
    "init_priority": 0,
    "inputs": [
        {
            "name":        "text",
            "type":        "string",
            "widget_type": "text",
            "options":     null,
            "default":     "hello"
        },
        {
            "name":        "count",
            "type":        "int",
            "widget_type": "int",
            "options":     null,
            "default":     3
        },
        {
            "name":        "exec_in",
            "type":        "any",
            "widget_type": null,
            "options":     null,
            "default":     null
        }
    ],
    "outputs": [
        {
            "name":        "result",
            "type":        "string",
            "widget_type": null,
            "options":     null,
            "default":     null
        },
        {
            "name":        "exec_out",
            "type":        "any",
            "widget_type": null,
            "options":     null,
            "default":     null
        }
    ],
    "python_code": "..."
}
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `node_id` | `string` | Yes | Registry key. Must match `BaseNode.name`. Unique across all loaded nodes. |
| `name` | `string` | Yes | Same as `node_id` for JSON-defined nodes. |
| `display_name` | `string` | No | Text shown in the canvas header. Defaults to `name`. |
| `description` | `string` | No | Tooltip shown in the Library panel. |
| `category` | `string` | Yes | Library grouping folder name. |
| `icon_path` | `string` | No | Relative path to SVG or PNG icon, or `null`. |
| `use_exec` | `bool` | Yes | `true` adds `exec_in`/`exec_out` ports. `false` for data-only reactive nodes. |
| `init_priority` | `int` | No | `> 0` marks the node as Init First — created before all other nodes during workflow load. Default `0`. |
| `inputs` | `array` | Yes | List of input port definitions (see [Port System](#4-port-system)). |
| `outputs` | `array` | Yes | List of output port definitions. |
| `python_code` | `string` | Yes | Full Python source as a JSON string (`\n` for newlines, `\"` for quotes). |

> When `use_exec: true`, the `exec_in` and `exec_out` ports **must** appear in the `inputs` and `outputs` arrays. However, the `BaseNode.__init__` call adds these automatically — do not also add them via `add_input()`/`add_output()` in your Python code or they will be duplicated.

---

## 3. BaseNode Class Reference

**Module:** `src.nodes.base`

### Class Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"BaseNode"` | Registry key. Must match `node_id`. |
| `node_id` | `str` | (injected) | Assigned by the registry on load. |
| `display_name` | `str` | `""` | Canvas header text. Falls back to `name` if empty. |
| `description` | `str` | `""` | Tooltip in the Library panel. |
| `category` | `str` | `"General"` | Library grouping. |
| `icon_path` | `str\|None` | `None` | Relative path to icon file. |
| `init_priority` | `int` | `0` | Values `> 0` = Init First ordering. |
| `memory` | `dict` | `{}` | Class-level shared dict, cleared at the start of each run. |

### Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `inputs` | `dict[str, Port]` | Input ports keyed by name. |
| `outputs` | `dict[str, Port]` | Output ports keyed by name. |
| `parameters` | `dict[str, Any]` | Widget values, output cache, and internal state. |
| `bypassed` | `bool` | `True` when the node is bypassed by the user. |

### Constructor

```python
def __init__(self, use_exec: bool = True)
```

`super().__init__()` (with default `use_exec=True`) automatically adds:
- `exec_in` as an input of type `any`
- `exec_out` as an output of type `any`

Do **not** add these manually in your port setup block.

### Methods

| Signature | Returns | Description |
|-----------|---------|-------------|
| `add_input(name, type="any", widget_type=None, options=None, default=None)` | `None` | Add an input port and initialize its parameter slot. |
| `add_output(name, type="any", default=None)` | `None` | Add an output port and initialize its parameter slot. |
| `add_exec_input(name="exec_in")` | `None` | Add an exec-type input (type `"any"`, no widget). Called by `__init__` automatically. |
| `add_exec_output(name="exec_out")` | `None` | Add an exec-type output. Called by `__init__` automatically. |
| `add_parameter(name, param_type, default=None)` | `None` | Define an internal non-port parameter (not shown as a port). |
| `set_parameter(name, value)` | `None` | Update a widget value. For dropdown ports, passing a `list` updates the options. Triggers downstream reactive sync. |
| `get_parameter(name, default=None)` | `Any` | Safe parameter read. Returns `default` if the key is absent. |
| `rebuild_ports()` | `None` | Signal the canvas to refresh port layout after dynamic port changes. |
| `is_port_connected(name, is_input)` | `bool` | Returns `True` if the named port has a wire connected. |
| `is_stopped()` | `bool` | Returns `True` if the user pressed Stop. Check this in long loops. |
| `async set_output(name, value)` | `None` | Push a value to downstream nodes reactively **before** `exec_out` fires. |
| `clear_outputs()` | `None` | Reset all output values to defaults. Called by the engine before execution. |
| `log_info(msg)` | `None` | Send an info-level message to the Log Panel. Thread-safe. |
| `log_success(msg)` | `None` | Send a success-level message. |
| `log_error(msg)` | `None` | Send an error-level message. |
| `restore_from_parameters(params)` | `None` | Override to recreate dynamic ports from saved state on workflow load. |

### execute() — Abstract

```python
async def execute(self, inputs: dict) -> dict:
    ...
```

- **Must** be `async def`.
- `inputs` is a `dict` mapping port name → current value.
- Must return a `dict` whose keys match your output port names.
- Must include `"exec_out": True` for exec-flow nodes.
- Any unhandled exception is caught by the engine; the node gets a red border and the error is logged.

---

## 4. Port System

### Port Types

| Type | Usage | Python type at runtime |
|------|-------|----------------------|
| `string` | Text values | `str` |
| `int` | Integer values | `int` |
| `float` | Float values | `float` |
| `bool` | Boolean values | `bool` |
| `list` | Python lists | `list` |
| `dict` | Python dicts | `dict` |
| `any` | Generic / exec flow | any |

### Widget Types (input ports only)

| Widget | Renders as | When to use |
|--------|-----------|-------------|
| `"text"` | Single-line text box | Short strings, file paths, names |
| `"text_area"` | Multi-line text area | Code, long content, JSON |
| `"int"` | Integer spinbox | Count, index, frame number |
| `"float"` | Float spinbox | Numeric values, scale factors |
| `"bool"` / `"checkbox"` | Checkbox | On/off flags |
| `"dropdown"` | Drop-down selector | Fixed option sets |
| `"slider"` | Horizontal slider | Constrained numeric range |
| `"file"` | Text + browse button (open) | Input file paths |
| `"file_save"` | Text + browse button (save) | Output file paths |
| `null` | No widget (display only) | Ports that only receive wired data |

### Dropdown Ports

Pass a list of strings as `options` to populate the dropdown:

```python
self.add_input("format", "string", widget_type="dropdown",
               options=["alembic", "fbx", "obj", "usd"])
```

To update options programmatically without resetting the selection:

```python
self.set_parameter("format", ["alembic", "fbx", "obj", "usd", "gltf"])
```

### Port Definition in Code vs JSON

Ports defined in `__init__` via `add_input()` / `add_output()` must **exactly match** the ports listed in the `inputs` / `outputs` JSON arrays. The Node Builder keeps these in sync automatically. If you edit a JSON file by hand, ensure both are consistent.

---

## 5. Lifecycle Hooks

### execute(inputs) — Primary Hook

Called by the engine during a workflow run. See [BaseNode.execute()](#execute--abstract) above.

### on_parameter_changed(name, value)

```python
async def on_parameter_changed(self, name: str, value: Any) -> None:
    ...
```

Triggered when:
- A user interacts with a node widget (types, selects, toggles).
- Reactively during execution when an upstream node's output is propagated to this node's input port.

**Not** triggered during:
- The pre-execute input sync sweep (the step that copies wire values into parameters before `execute()` begins).

**Use for:** real-time output mirroring (pass-through nodes), reactive calculations, updating internal state as the user types.

**Keep it fast.** Avoid heavy I/O in this hook; it fires on every keystroke.

```python
# Pass-through: mirror input to output as the user types
async def on_parameter_changed(self, name, value):
    if name == "input_text":
        self.parameters["output_text"] = value
```

### on_plug_sync(port_name, is_input, other_node, other_port_name)

```python
def on_plug_sync(self, port_name: str, is_input: bool,
                  other_node: BaseNode, other_port_name: str) -> None:
    ...
```

Called **synchronously** on the Qt main thread the moment a wire is connected. Use for immediate UI updates or initial data copying.

```python
def on_plug_sync(self, port_name, is_input, other_node, other_port_name):
    if is_input and port_name == "config":
        value = other_node.get_parameter(other_port_name)
        self.set_parameter("config_preview", str(value))
```

### on_unplug_sync(port_name, is_input)

```python
def on_unplug_sync(self, port_name: str, is_input: bool) -> None:
    ...
```

Called synchronously when a wire is disconnected. Use to reset widgets or clear cached state.

### on_plug / on_unplug — Async Variants

```python
async def on_plug(self, port_name, is_input, other_node, other_port_name): ...
async def on_unplug(self, port_name, is_input): ...
```

For heavy async work (network calls, file reads) triggered by a connection event. These run on the asyncio event loop.

---

## 6. Logging

All log methods are **thread-safe** and can be called from inside `execute()` even though execution runs on the asyncio loop.

| Method | Log level | Log panel color |
|--------|-----------|----------------|
| `self.log_info(msg)` | Info | White |
| `self.log_success(msg)` | Success | Green |
| `self.log_error(msg)` | Error | Red — also sets node red border |

```python
async def execute(self, inputs):
    path = inputs.get("file_path", "")
    if not path:
        self.log_error("No file path provided.")
        return {"result": "", "exec_out": True}

    self.log_info(f"Processing: {path}")
    # ... do work ...
    self.log_success("Done.")
    return {"result": output, "exec_out": True}
```

---

## 7. Advanced Patterns

### Data-Only Nodes (use_exec=False)

Nodes without exec pins participate exclusively in reactive data flow. They update whenever their inputs change and are "pulled" by exec-flow nodes before execution.

```python
class Math_Multiply(BaseNode):
    name = "math_multiply"

    def __init__(self):
        super().__init__(use_exec=False)    # no exec_in / exec_out
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("a", "float", widget_type="float", default=1.0)
        self.add_input("b", "float", widget_type="float", default=1.0)
        self.add_output("result", "float")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        a = float(inputs.get("a", 1.0))
        b = float(inputs.get("b", 1.0))
        return {"result": a * b}
```

In JSON: `"use_exec": false`. Do not include `exec_in` / `exec_out` in the port arrays.

### Reactive Output — set_output()

Use `await self.set_output(name, value)` inside `execute()` to push a value to downstream nodes **before** `exec_out` fires. This is useful when downstream nodes need data before their own execution is triggered.

```python
async def execute(self, inputs):
    items = inputs.get("items", [])
    for item in items:
        await self.set_output("current", item)   # push each item
        # exec_out fires after the loop completes
    return {"exec_out": True}
```

### Dynamic Ports

Override `restore_from_parameters()` to recreate ports from saved state on workflow load. This is how `GroupNode` works internally.

```python
def restore_from_parameters(self, params):
    # recreate ports based on saved config
    for port_def in params.get("__port_defs__", []):
        if port_def["is_input"]:
            self.add_input(port_def["name"], port_def["type"])
        else:
            self.add_output(port_def["name"], port_def["type"])
    self.rebuild_ports()
```

### Shared State — BaseNode.memory

`BaseNode.memory` is a class-level `dict` shared across all node instances in the same run. It is cleared at the start of each run. Use it to pass data between nodes without wiring — for example, a configuration node writing values that other nodes read.

```python
class Config_Writer(BaseNode):
    async def execute(self, inputs):
        BaseNode.memory["studio_root"] = inputs.get("path", "")
        return {"exec_out": True}

class Config_Reader(BaseNode):
    async def execute(self, inputs):
        root = BaseNode.memory.get("studio_root", "")
        return {"path": root, "exec_out": True}
```

### Stopping Gracefully

For long loops, check `self.is_stopped()` to respect the Stop button:

```python
async def execute(self, inputs):
    for i in range(1000):
        if self.is_stopped():
            self.log_info("Stopped by user.")
            return {"exec_out": True}
        # ... process item i ...
    return {"exec_out": True}
```

---

## 8. Houdini Bridge Nodes

Houdini nodes communicate with a live Houdini session via `HouBridge` — a TCP JSON-RPC client.

### Setup

```python
from src.nodes.base import BaseNode
from src.utils.hou_bridge import get_bridge

class Hou_Create_Box(BaseNode):
    name = "hou_create_box"
    category = "Houdini"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("parent", "string", widget_type="text", default="/obj")
        self.add_input("name",   "string", widget_type="text", default="my_box")
        self.add_output("geo_path", "string")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        parent = inputs.get("parent", "/obj")
        name   = inputs.get("name", "my_box")
        try:
            bridge = get_bridge()
            geo = bridge.create_node(parent, "geo", name)
            geo_path = geo["path"]

            # Clear auto-generated default nodes
            for child in bridge.children(geo_path):
                bridge.delete_node(child["path"])

            # Create a box SOP inside
            box = bridge.create_node(geo_path, "box", "box1")
            bridge.set_display_flag(box["path"], True)
            bridge.set_render_flag(box["path"], True)
            bridge.layout_children(geo_path)

            return {"geo_path": geo_path, "exec_out": True}
        except Exception as e:
            self.log_error(f"Houdini error: {e}")
            return {"geo_path": "", "exec_out": True}
```

### HouBridge Method Quick Reference

| Method | Returns | Description |
|--------|---------|-------------|
| `bridge.create_node(parent, type, name="")` | `{"path", "name", "type"}` | Create a node |
| `bridge.delete_node(path)` | `{"deleted"}` | Delete a node |
| `bridge.set_parm(node, parm, value)` | `{"set": True}` | Set single parameter |
| `bridge.get_parm(node, parm)` | `{"value": ...}` | Get single parameter |
| `bridge.set_parms(node, parms_dict)` | `{"set": True}` | Set multiple parameters |
| `bridge.connect_nodes(from, to, output=0, input=0)` | `{"connected": True}` | Wire nodes |
| `bridge.cook_node(path)` | `{"cooked": True}` | Cook a node |
| `bridge.run_code(code)` | `{"result": ...}` | Run Python inside Houdini |
| `bridge.node_info(path)` | info dict | Node type, category, children |
| `bridge.node_exists(path)` | `{"exists": bool}` | Check path exists |
| `bridge.children(path)` | list of `{"name", "type", "path"}` | List child nodes |
| `bridge.set_display_flag(path, on=True)` | `{"set": True}` | Display flag |
| `bridge.set_render_flag(path, on=True)` | `{"set": True}` | Render flag |
| `bridge.layout_children(path)` | `{"done": True}` | Auto-layout |
| `bridge.save_hip(path="")` | `{"saved": path}` | Save scene |
| `bridge.set_expression(node, parm, expr, language="hscript")` | `{"set": True}` | Set expression |
| `bridge.scene_info()` | scene metadata dict | HIP file, FPS, frame range |
| `bridge.ping()` | `{"status": "ok", "version": ...}` | Connectivity check |

See `CLAUDE.md` section 3 for full return value documentation.

---

## 9. Headless Action Nodes — Maya and Blender

Maya and Blender nodes use a **list-builder** pattern. Action nodes append operation dicts to a list; a headless executor node runs them all in a batch DCC session.

### Action Node Skeleton

```python
class Maya_Action_Render(BaseNode):
    name = "maya_action_render"
    category = "Maya"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("actions_in", "list")
        self.add_input("camera",     "string", widget_type="text",     default="persp")
        self.add_input("start_frame","int",    widget_type="int",      default=1)
        self.add_input("end_frame",  "int",    widget_type="int",      default=48)
        self.add_output("actions_out", "list")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        actions = list(inputs.get("actions_in") or [])
        actions.append({
            "type":        "render",
            "camera":      inputs.get("camera", "persp"),
            "start_frame": inputs.get("start_frame", 1),
            "end_frame":   inputs.get("end_frame",   48),
        })
        return {"actions_out": actions, "exec_out": True}
```

**Conventions:**

- `node_id` prefix: `maya_action_*` / `blender_action_*`
- `category`: `"Maya"` / `"Blender"`
- Always use `list(inputs.get("actions_in") or [])` — never mutate the original list.
- The `"type"` field must match a handler in the corresponding runner script.

### Executor Node

Chain action nodes to `maya_headless` or `blender_headless`. The executor spawns the DCC process, sends it the action list, and returns a result dict.

---

## 10. Prism Pipeline Nodes

All Prism nodes share a common skeleton with automatic `PrismCore` resolution.

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
            return {"assets": assets, "exec_out": True}
        except Exception as e:
            self.log_error(f"Prism error: {e}")
            return {"assets": [], "exec_out": True}

def register_node():
    return Prism_Get_Assets
```

**Prism node conventions:**

- `node_id` must start with `prism_`
- `category` must be `"Prism"`
- `icon_path` should be `"icons/prism_icon.png"`
- Never add a `core` input port — it is resolved automatically by `resolve_prism_core()`
- Always guard with `if core is None`
- Return safe empty defaults (`[]` / `{}`) on failure

> **Registry injection:** When a `prism_*` node's Python code is compiled, the registry automatically rewrites `core = inputs.get('core')` → `core = resolve_prism_core(inputs)` and injects the import. You do not need to add the import manually in JSON-embedded code.

---

## 11. Node Builder GUI

**Open:** Nodes → Node Builder, or press `Ctrl+E` with a node selected to edit its definition.

### Workflow

1. **Node Metadata** — set ID, display name, category, description, icon path, and exec/init flags.
2. **Input / Output Tables** — add rows for each port. Columns: Name, Type, Widget, Options, Default.
3. **Code Editor** — the Python code is generated and previewed here. The editor is bi-directional: editing the tables updates the code; editing the code updates the tables.
4. **Save & Register** — writes the JSON file to the `nodes/` directory and registers the node immediately.

### Exec Checkbox

Checking "Use Exec" adds `exec_in` and `exec_out` to the port tables and to the generated code's `super().__init__(use_exec=True)` call. Do not add exec ports manually as table rows when this checkbox is enabled — they will be duplicated.

### Edit Existing Node

Select a node on the canvas → `Ctrl+E`. The Node Builder opens with that node's current definition pre-loaded. `exec_in`/`exec_out` rows are filtered from the tables (they are managed by the exec checkbox, not the table). Change ports, code, or metadata, then Save & Register. Hot-reload the live canvas instances with `Ctrl+R`.

### Gemini Assistance

The Node Builder can optionally call Gemini to suggest code snippets and starter templates while you write node logic. Enable it in the Node Builder settings and provide an API key. Always review generated code before executing in production.

---

## 12. Distribution and Installation

### Single-File Distribution

A node is a single `.json` file. Distribute it by sharing the file. Recipients install it via:

**Nodes → Load Node From JSON** — validates the file, copies it to the user `nodes/` directory, and registers it immediately.

The installer:
1. Checks for `node_id` and `python_code` fields (rejects workflow files with a clear error).
2. Creates the `nodes/` directory if absent.
3. Copies the file.
4. Updates `NodeRegistry._source_paths` so hot-reload targets the installed copy.

### Directory Distribution

For larger node libraries, distribute a folder of `.json` files. Users point `v_nodes_dir` to that folder via **Edit → Preferences → Application Paths**. The registry loads all `.json` files from every `v_nodes_dir` path on startup.

### Houdini Plugin Distribution

For Houdini-specific node libraries, place the folder in `plugins/houdini/v_nodes_houdini/` (or configure `v_nodes_dir` to point to it). The Houdini `setup_env()` adds this path to the environment automatically when Vibrante-Node is launched from Houdini.

### Built-in Nodes (Source)

To add a node directly to the application source:

1. Create a class in `src/nodes/builtins/nodes.py` inheriting from `BaseNode`.
2. Implement `__init__`, `execute()`, and `register_node()`.
3. Call `NodeRegistry.register(MyNode)` in the `register_builtins()` function.

---

## 13. Common Mistakes

| Mistake | Correct Approach |
|---------|-----------------|
| `super().__init__()` not called | Always call `super().__init__()` as the first line of `__init__`. |
| Adding `exec_in` / `exec_out` manually in `__init__` | They are added automatically by `super().__init__()`. Adding them again creates duplicate ports. |
| `exec_in` / `exec_out` missing from the JSON port arrays | When `use_exec: true`, these must appear in the JSON arrays even though the Python code doesn't add them manually. |
| `return {}` (empty) | Always return `{"exec_out": True}` for exec-flow nodes, even on early exit. |
| `time.sleep(n)` in `execute()` | Use `await asyncio.sleep(n)` — synchronous sleep blocks the Qt event loop. |
| Calling `hou_bridge.get_hou()` | This function does not exist. Use `get_bridge()` to get the bridge singleton. |
| `result = bridge.create_node(...); result.path()` | The bridge returns dicts, not objects. Use `result["path"]`. |
| Mutating `inputs.get("actions_in")` directly | Always wrap: `actions = list(inputs.get("actions_in") or [])` |
| Adding ports twice (in AUTO block and below it) | Each port name must appear exactly once. |
| Using `import hou` directly | Never import `hou` in node code — use the bridge. `hou` is only available inside Houdini's own process. |

---

**See also:**

- [User Guide](USER_GUIDE.md) — using the Node Builder GUI
- [Automation API](AUTOMATION_API.md) — programmatic node creation
- [Developer Guide](DEVELOPER.md) — registry internals and hot-reload
- [Technical Reference](DOCUMENTATION.md) — complete BaseNode API table, port schema, JSON schema
