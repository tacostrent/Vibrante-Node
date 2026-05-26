# Vibrante-Node — Developer Guide for Codex / Claude

This file teaches Codex and Claude how to create nodes for this node-based visual workflow platform and how to interact with the runtime directly.

**Vibrante-Node** is a Python node-based visual framework for building modular systems through connected nodes and data flows. It provides an intuitive graph interface, an extensible node system, multi-DCC integration (Houdini, Maya, Blender, Prism), and an optional AI runtime layer.

The primary interface is the visual canvas — workflows are built by connecting nodes, executed via F5, and inspected through the log panel and live wire inspector. Advanced automation can also be done programmatically or via MCP:

1. **Visual Workflow Orchestration** — build graphs on the canvas and run via F5.
2. **Direct Runtime Orchestration** *(advanced)* — Claude, Codex, or Cursor connects to `scripts/run_vibrante_mcp.py` via MCP stdio and uses 12 semantic tools to inspect, plan, and execute Houdini scene operations.

---

## 1. Node File Format

Every node is a single `.json` file in `nodes/`. It has this structure:

```json
{
    "node_id": "my_node",
    "name": "my_node",
    "description": "What this node does.",
    "category": "Houdini",
    "icon_path": "icons/houdini.svg",
    "use_exec": true,
    "inputs": [
        { "name": "some_input", "type": "string", "widget_type": "text", "options": null, "default": null },
        { "name": "exec_in",   "type": "any",    "widget_type": null,   "options": null, "default": null }
    ],
    "outputs": [
        { "name": "some_output", "type": "string", "widget_type": null, "options": null, "default": null },
        { "name": "exec_out",    "type": "any",    "widget_type": null, "options": null, "default": null }
    ],
    "python_code": "..."
}
```

- **`use_exec: true`** — means the node participates in execution flow. Always include `exec_in` / `exec_out` in the inputs/outputs arrays when true.
- **`category`** — used for grouping in the UI. Use `"Houdini"` for all Houdini-related nodes.
- **`icon_path`** — use `"icons/houdini.svg"` for Houdini nodes, or `null`.
- **`python_code`** — the full Python source as a single JSON string (use `\n` for newlines, `\"` for quotes).

### Port types

| type     | widget_type     | notes                        |
|----------|-----------------|------------------------------|
| `string` | `"text"`        | text input widget            |
| `float`  | `"float"`       | numeric float widget         |
| `int`    | `"int"`         | numeric integer widget       |
| `bool`   | `"checkbox"`    | checkbox widget              |
| `any`    | `null`          | generic exec/data port       |

---

## 2. Python Code Rules

### 2.1 Class skeleton

```python
from src.nodes.base import BaseNode
from src.utils.hou_bridge import get_bridge   # for Houdini nodes

class My_Node(BaseNode):
    name = "my_node"   # must match node_id

    def __init__(self):
        super().__init__()   # IMPORTANT: this already adds exec_in + exec_out
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("some_input", "string", widget_type="text")
        self.add_input("a_float",   "float",  widget_type="float", default=1.0)
        self.add_output("some_output", "string")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        value = inputs.get("some_input", "")
        # ... do work ...
        return {
            "some_output": result,
            "exec_out": True
        }

def register_node():
    return My_Node
```

### 2.2 Critical rules for `__init__`

- `super().__init__()` calls `BaseNode.__init__(use_exec=True)` which **automatically adds `exec_in` and `exec_out`**. Do NOT add them again manually.
- Only add the **extra** ports specific to your node inside the `# [AUTO-GENERATED-PORTS-START]` block.
- Never add ports twice. Duplicate calls to `add_input` / `add_output` for the same name will create duplicate ports in the UI.

### 2.3 `execute` return value

Always return a dict whose keys match your output port names. Always include `"exec_out": True` for exec-flow nodes.

```python
return {
    "my_output": some_value,
    "exec_out": True
}
```

---

## 3. Houdini Bridge

Houdini nodes communicate with a live Houdini session over a local TCP socket (JSON-RPC). The bridge client lives in `src/utils/hou_bridge.py`.

### 3.1 Getting the bridge

```python
from src.utils.hou_bridge import get_bridge

bridge = get_bridge()   # returns the HouBridge singleton
```

**Never** import `hou` directly. **Never** call `hou_bridge.get_hou()` — that function does not exist.

### 3.2 All bridge methods and their return values

#### `bridge.ping()`
Returns: `{"status": "ok", "version": "<houdini version string>"}`

#### `bridge.create_node(parent, node_type, name="")`
Creates a node inside `parent`.
Returns: `{"path": "/obj/geo1", "name": "geo1", "type": "geo"}`
```python
result = bridge.create_node("/obj", "geo", "my_geo")
geo_path = result["path"]   # e.g. "/obj/my_geo"
```

#### `bridge.delete_node(path)`
Returns: `{"deleted": "/obj/my_geo"}`

#### `bridge.set_parm(node, parm, value)`
Sets a single parameter.
Returns: `{"set": True}`
```python
bridge.set_parm("/obj/my_geo/alembic1", "fileName", "/path/to/file.abc")
```

#### `bridge.get_parm(node, parm)`
Returns: `{"value": <current value>}`
```python
result = bridge.get_parm("/obj/my_geo/alembic1", "fileName")
value = result["value"]
```

#### `bridge.set_parms(node, parms)`
Sets multiple parameters at once.
Returns: `{"set": True, "count": N}`
```python
bridge.set_parms("/obj/my_geo/null1", {"tx": 1.0, "ty": 2.0})
```

#### `bridge.get_parms(node)`
Returns a flat dict of all parameter name→value pairs.

#### `bridge.connect_nodes(from_node, to_node, output=0, input_idx=0)`
Wires `from_node`'s output into `to_node`'s input.
Returns: `{"connected": True}`
```python
bridge.connect_nodes(abc_path, convert_path, output=0, input_idx=0)
```

#### `bridge.cook_node(path, force=False)`
Returns: `{"cooked": True}`

#### `bridge.run_code(code)`
Executes arbitrary Python code **inside Houdini**. `hou` is available. Assign to `result` to get a value back.
Returns: `{"result": <value of local variable named 'result', or None>}`
```python
run_result = bridge.run_code(
    "n = hou.node('/obj/my_geo'); result = n.displayNode().path() if n and n.displayNode() else None"
)
display_path = run_result.get("result")   # e.g. "/obj/my_geo/convert1" or None
```

#### `bridge.scene_info()`
Returns: `{"hip_file": ..., "hip_name": ..., "houdini_version": ..., "fps": ..., "frame": ..., "frame_range": [start, end]}`

#### `bridge.node_info(path)`
Returns detailed info about a node:
```python
{
    "path": "/obj/my_geo",
    "name": "my_geo",
    "type": "geo",
    "category": "Object",        # "Object", "Sop", "Shop", etc.
    "input_connectors": 0,
    "output_connectors": 0,
    "inputs": ["/obj/other"],    # list of connected input node paths (or None)
    "outputs": ["/obj/child"],   # list of connected output node paths
    "children": ["alembic1", "convert1"]  # child node names (not full paths)
}
```

#### `bridge.children(path="/obj")`
Lists children of a node.
Returns: list of `{"name": ..., "type": ..., "path": ...}` dicts.
```python
children = bridge.children("/obj/my_geo")
for child in children:
    bridge.delete_node(child["path"])
```

#### `bridge.node_exists(path)`
Returns: `{"exists": True}` or `{"exists": False}`
```python
exists = bridge.node_exists("/obj/my_geo")["exists"]
```

#### `bridge.set_display_flag(path, on=True)`
Returns: `{"set": True}`

#### `bridge.set_render_flag(path, on=True)`
Returns: `{"set": True}`

#### `bridge.layout_children(path="/obj")`
Auto-layouts child nodes.
Returns: `{"done": True}`

#### `bridge.save_hip(path="")`
Returns: `{"saved": "<hip file path>"}`

#### `bridge.set_expression(node, parm, expression, language="hscript")`
Returns: `{"set": True}`
```python
bridge.set_expression("/obj/my_geo/null1", "tx", "sin($F * 0.1)", language="hscript")
bridge.set_expression("/obj/my_geo/null1", "tx", "hou.frame() * 0.1", language="python")
```

#### `bridge.set_keyframe(node, parm, frame, value)`
Returns: `{"set": True}`

#### `bridge.set_frame(frame)`
Returns: `{"frame": <new frame>}`

#### `bridge.set_playback_range(start, end)`
Returns: `{"start": ..., "end": ...}`

---

## 4. Common Houdini Node Patterns

### 4.1 Create a geo container with SOPs inside it

```python
# Create /obj-level geo container
geo_result = bridge.create_node("/obj", "geo", "my_geo")
geo_path = geo_result["path"]

# Clear default nodes Houdini adds automatically
for child in bridge.children(geo_path):
    bridge.delete_node(child["path"])

# Create SOPs inside the geo
sop_result = bridge.create_node(geo_path, "box", "my_box")
sop_path = sop_result["path"]

bridge.set_display_flag(sop_path, True)
bridge.set_render_flag(sop_path, True)
bridge.layout_children(geo_path)
```

### 4.2 Resolve input: Object vs SOP

When a node accepts a `geo_path` that could be either an Object-level geo node or a SOP node:

```python
node_info = bridge.node_info(geo_path)
category = node_info.get("category", "")

if category == "Object":
    # Get the display SOP inside the geo container
    run_result = bridge.run_code(
        f"n = hou.node('{geo_path}'); result = n.displayNode().path() if n and n.displayNode() else None"
    )
    input_sop = run_result.get("result")
    if not input_sop:
        raise Exception(f"No display SOP found inside: {geo_path}")
    sop_context = geo_path
elif category == "Sop":
    sop_context = "/".join(geo_path.rstrip("/").split("/")[:-1])
    input_sop = geo_path
else:
    raise Exception(f"Unsupported category '{category}': {geo_path}")
```

### 4.3 VEX wrangle via attribwrangle

```python
vex_code = (
    'vector p0 = point(0, "P", primpoint(0, @primnum, 0));\n'
    'vector p1 = point(0, "P", primpoint(0, @primnum, 1));\n'
    'vector dir = normalize(p1 - p0);\n'
    'if (abs(dot(dir, set(1,0,0))) < 0.9) { removeprim(0, @primnum, 1); }'
)

wrangle_result = bridge.create_node(sop_context, "attribwrangle", "my_wrangle")
wrangle_path = wrangle_result["path"]
bridge.connect_nodes(input_sop, wrangle_path, output=0, input_idx=0)
bridge.set_parm(wrangle_path, "class", 1)       # 0=detail, 1=primitive, 2=point, 3=vertex
bridge.set_parm(wrangle_path, "snippet", vex_code)
```

### 4.4 Standard execute pattern for Houdini nodes

```python
async def execute(self, inputs):
    geo_path = inputs.get("geo_path", "")
    if not geo_path:
        self.log_error("No geo path provided.")
        return {"result_path": "", "exec_out": True}

    try:
        bridge = get_bridge()
        # ... create nodes ...
        return {"result_path": result_path, "exec_out": True}
    except Exception as e:
        self.log_error(f"Houdini operation failed: {str(e)}")
        return {"result_path": "", "exec_out": True}
```

---

## 5. Mistakes to Avoid

| Wrong | Correct |
|-------|---------|
| `from src.utils import hou_bridge; hou_bridge.get_hou()` | `from src.utils.hou_bridge import get_bridge; bridge = get_bridge()` |
| `hou.node("/obj").createNode(...)` | `bridge.create_node("/obj", ...)` |
| `node.parm("x").set(1.0)` | `bridge.set_parm(node_path, "x", 1.0)` |
| `result = bridge.create_node(...); result.path()` | `result = bridge.create_node(...); path = result["path"]` |
| `for c in bridge.children(p): c.destroy()` | `for c in bridge.children(p): bridge.delete_node(c["path"])` |
| Adding `exec_in`/`exec_out` in `__init__` manually | They are added by `super().__init__()` automatically |
| Adding ports twice (once in AUTO block, once below it) | Add each port exactly once inside the AUTO block |

---

## 6. Runtime Layer — MCP Integration (v2.4.0+)

Vibrante-Node has a `src/runtime/` module that is the seam between nodes and DCCs. All AI-facing nodes (`hou_mcp_*`, `mcp_*`) call this layer rather than calling the bridge directly. The Runtime Layer is also accessible to Claude/Codex as a **standalone MCP server** without the visual canvas.

### 6.1 Direct connection (Claude/Codex without canvas)

```bash
# 1. Install dependencies
pip install "mcp>=1.0.0" pydantic toposort

# 2. Optional: start Houdini with the Vibrante plugin loaded and bridge running (port 18811)

# 3. Start the MCP server
python scripts/run_vibrante_mcp.py
```

Configure Claude Desktop (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "vibrante": {
      "command": "python",
      "args": ["/path/to/scripts/run_vibrante_mcp.py"]
    }
  }
}
```

### 6.2 Recommended AI workflow (canonical order)

```
initialize_runtime_context  →  query_scene_context
    →  plan_scene("build a pyro sim in /obj")
    →  preview_execution(operations)           # check risk before executing
    →  execute_workflow_transaction(plan_json) # requires approval for high-risk
    →  review_execution(plan, result)
```

**Never** skip `preview_execution` before `execute_workflow_transaction` for high-risk plans.

### 6.3 Runtime Layer design rules (non-negotiable)

1. **MCP is transport only** — never delegate scene understanding to MCP. Intelligence stays in `src/runtime/`.
2. **No arbitrary Python execution** — do not expose `run_python`/`execute_code` as tools. Use structured, validated ops.
3. **Validation before mutation** — all ops go through `ValidationEngine` + `RuntimeConstraints` before any bridge call.
4. **Approval gate** — plans with `requires_approval=True` block until `approver` is supplied.
5. **Cache invalidation** — every `houdini_runtime` function that mutates Houdini must call `get_scene_cache().invalidate("scene_context::")`.

### 6.4 Writing a node that uses the Runtime Layer

Nodes that use `houdini_runtime` or `mcp_runtime` (e.g. all `hou_mcp_*` nodes):

```python
from src.nodes.base import BaseNode
from src.runtime import houdini_runtime

class Hou_Mcp_My_Node(BaseNode):
    name = "hou_mcp_my_node"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("spec_json", "string", widget_type="text_area")
        self.add_output("ok", "bool")
        self.add_output("result_json", "string")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        import json
        try:
            spec = json.loads(inputs.get("spec_json") or "{}")
        except json.JSONDecodeError as e:
            self.log_error(f"Invalid JSON: {e}")
            return {"ok": False, "result_json": "{}", "exec_out": True}

        try:
            result = await houdini_runtime.build_node_chain(spec)
            return {
                "ok": result.get("ok", False),
                "result_json": json.dumps(result),
                "exec_out": True,
            }
        except Exception as e:
            self.log_error(f"Runtime error: {e}")
            return {"ok": False, "result_json": "{}", "exec_out": True}

def register_node():
    return Hou_Mcp_My_Node
```

**Placement rules for new nodes:**
- DCC-agnostic nodes (e.g. generic MCP client) → `nodes/` (bundled)
- Houdini-specific AI nodes → `plugins/houdini/v_nodes_houdini/`

### 6.5 Forbidden MCP tool names

Never register these as MCP tools (the test suite enforces this):

`create_node`, `set_parm`, `set_parms`, `run_python`, `run_code`, `delete_node`, `raw_houdini_execute`, `connect_nodes`, `cook_node`

### 6.6 New bridge methods (v2.4.0+)

Two new methods added for the Runtime Layer:

```python
bridge.get_selection()          # → {"paths": [str, ...]}
bridge.network_summary(path)    # → [{"name", "type", "path", "category"}, ...]
```

---

## 7. Headless Action Nodes (v1.5.0)

Headless action nodes (Maya, Houdini, Blender) follow a "list-builder" pattern. They don't perform work themselves; they just append a dictionary to a list that is later processed by the Headless Executor.

### 7.1 Action Node Skeleton

```python
class DCC_Action_Node(BaseNode):
    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("actions_in", "list")
        self.add_input("some_param", "string", widget_type="text")
        self.add_output("actions_out", "list")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        actions = list(inputs.get("actions_in") or [])
        
        # Build the action dictionary
        action = {
            "type": "my_action_type",
            "some_param": inputs.get("some_param", "")
        }
        
        actions.append(action)
        
        return {
            "actions_out": actions,
            "exec_out": True
        }
```

### 7.2 Conventions for Action Nodes

- **`node_id`** should follow the pattern: `maya_action_...`, `houdini_action_...`, or `blender_action_...`.
- **`category`** should be `"Maya"`, `"Houdini"`, or `"Blender"`.
- **`actions_in` / `actions_out`** are mandatory for chaining.
- Always use `list(inputs.get("actions_in") or [])` to avoid mutating the original list or failing on None.
- The `type` field in the dictionary must match a handler in the corresponding DCC runner script.

---

## 8. Prism Pipeline Integration (v1.6.0)

Prism nodes communicate with the Prism Pipeline studio-management system. PrismCore is resolved automatically — you never need to wire it between nodes.

### 8.1 Core resolution

```python
from src.utils.prism_core import resolve_prism_core

async def execute(self, inputs):
    core = resolve_prism_core(inputs)   # checks inputs, global cache, shared memory
    if core is None:
        self.log_error("PrismCore not initialized. Add a prism_core_init node to the graph.")
        return {"exec_out": True}
    # use core normally
```

The registry automatically rewrites `core = inputs.get('core')` → `core = resolve_prism_core(inputs)` for any node whose `node_id` starts with `prism_`. You never need to do this manually.

### 8.2 Auto-bootstrap

Place a `prism_core_init` node anywhere in the graph. Before the main execution starts, the engine detects it and calls `bootstrap_prism_core()` on the Qt main thread. All subsequent `prism_*` nodes share the same `PrismCore` instance without any wiring.

### 8.3 Prism node skeleton

```python
from src.nodes.base import BaseNode
from src.utils.prism_core import resolve_prism_core

class Prism_Get_Assets(BaseNode):
    name = "prism_get_assets"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("entity",  "string", widget_type="text")
        self.add_output("assets", "list")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        core = resolve_prism_core(inputs)
        if core is None:
            self.log_error("PrismCore not available.")
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

### 8.4 Conventions for Prism nodes

- **`node_id`** must start with `prism_` (e.g., `prism_get_assets`).
- **`category`** must be `"Prism"`.
- **`icon_path`** use `"icons/prism_icon.png"`.
- Never add a `core` input port — it is resolved automatically.
- Always guard with `if core is None` and return a safe default.
- Use `list(...)` or `{}` as safe empty defaults for list/dict outputs.

### 8.5 Qt compatibility

If a node needs Qt features that differ between Qt5 and Qt6, import from `src.utils.qt_compat`:

```python
from src.utils.qt_compat import QtWidgets, QtGui, QtCore
```

The compat module also ensures `QColor.fromString()` and shiboken stubs exist, which Prism requires at import time.
