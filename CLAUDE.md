# Vibrante-Node — Developer Guide for Claude

This file teaches Claude how to create nodes for this node-based pipeline, with special focus on nodes that control Houdini via the bridge plugin.

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

## 6. Houdini Plugin Architecture & Environment Variables

The Houdini integration consists of two sides: code running **inside Houdini** and the Vibrante-Node **subprocess**.

### 6.1 Plugin file layout

```
plugins/houdini/
├── vibrante_node.json                  ← Houdini package file (user installs this)
├── v_nodes_houdini/                    ← Houdini-specific node .json definitions
│   ├── hou_create_geo.json
│   └── ...
├── v_scripts_houdini/                  ← Houdini-specific .py scripts (Scripts menu)
│   ├── hou_create_box_demo.py
│   └── ...
└── houdini/                            ← Added to HOUDINI_PATH by package JSON
    ├── MainMenuCommon.xml              ← Adds "Vibrante-Node" menu to Houdini menu bar
    ├── toolbar/vibrante_node.shelf     ← Shelf tool
    └── scripts/python/
        ├── pythonrc.py                 ← Runs at Houdini startup; validates env vars
        ├── vibrante_node_houdini.py    ← launch(), setup_env(), show_about(), etc.
        └── vibrante_hou_server.py      ← JSON-RPC server running inside Houdini
```

### 6.2 vibrante_node.json — what the user must configure

```json
{
    "env": [
        { "VIBRANTE_NODE_APP": "/path/to/node_based_app" },
        { "VIBRANTE_PYTHON_EXE": "C:/Python311/python.exe" }
    ],
    "path": "$VIBRANTE_NODE_APP/plugins/houdini/houdini"
}
```

- `VIBRANTE_NODE_APP` — absolute path to the app root (where `src/main.py` lives). **Must be set.**
- `VIBRANTE_PYTHON_EXE` — path to system Python 3.11 with PyQt5. Optional: auto-detected if missing but slower.
- `path` — adds `plugins/houdini/houdini/` to `HOUDINI_PATH` so Houdini finds `MainMenuCommon.xml`, the shelf, and `pythonrc.py`.

### 6.3 Environment variable flow

When `launch()` is called from Houdini, `setup_env()` builds the subprocess environment:

| Variable | Set by | Consumed by |
|----------|--------|-------------|
| `VIBRANTE_NODE_APP` | `vibrante_node.json` | `vibrante_node_houdini.get_app_root()` |
| `VIBRANTE_PYTHON_EXE` | `vibrante_node.json` | `vibrante_node_houdini._find_system_python()` |
| `VIBRANTE_HOUDINI_MODE` | `setup_env()` → `"subprocess"` | `src/utils/qt_compat.py` (selects PyQt5) |
| `VIBRANTE_HOU_PORT` | `setup_env()` after server starts | `src/utils/hou_bridge.py` (default: 18811) |
| `VIBRANTE_HIP_FILE` | `setup_env()` with hip path | Available in node python_code via `os.environ` |
| `v_nodes_dir` | `setup_env()` → path to `v_nodes_houdini/` | `NodeRegistry.load_all_with_extras()` in `window.py` |
| `v_scripts_path` | `setup_env()` → path to `v_scripts_houdini/` | `MainWindow._populate_scripts_menu()` in `window.py` |

**Critical**: `v_nodes_dir` and `v_scripts_path` are only set in the **subprocess** environment (not in Houdini itself). They are computed by `setup_env()` each time `launch()` is called.

### 6.4 Node loading at startup

`src/ui/window.py` initialises the registry in this order:
1. `NodeRegistry.load_all_with_extras(bundled_nodes)` — loads bundled nodes **and** any paths in `v_nodes_dir`
2. `NodeRegistry._load_directory(self.nodes_dir)` — loads user-created nodes from next to the exe

Always use `load_all_with_extras`, never plain `load_all`, or the Houdini nodes will be silently skipped.

### 6.5 Scripts menu

`MainWindow._populate_scripts_menu()` scans every directory in `v_scripts_path` for `.py` files and adds a clickable menu item for each. Scripts run via `exec()` with `{'window': self, 'scene': self.get_current_scene()}` as globals. A "Refresh Scripts" item re-scans without restarting.

Scripts in `v_scripts_houdini/` can use `get_bridge()` exactly like node python_code.

### 6.6 Startup diagnostics

`pythonrc.py` runs inside Houdini on every startup and prints to the Houdini Python console:
- `VIBRANTE_NODE_APP` — OK / ERROR (not set or path doesn't exist)
- `VIBRANTE_PYTHON_EXE` — OK / WARNING (missing or path not found)
- `v_nodes_houdini/` — OK / MISSING
- `v_scripts_houdini/` — OK / MISSING

Use **Vibrante-Node → About Vibrante-Node Integration** in Houdini's menu bar to see the same info on demand, including real-time OK/MISSING status for both plugin folders.

### 6.7 Houdini command server (vibrante_hou_server.py) — known behaviours

- `hou.playbar.frameRange()` raises `AttributeError` in headless Houdini (hbatch / hython). The server catches this and returns `[1, 240]` as fallback.
- `setDisplayFlag` / `setRenderFlag` raise `hou.OperationFailed` on node types that don't support flags (e.g. `null` at Object level). The server catches and re-raises as `ValueError` with a clear message.
- `start()` / `stop()` are guarded by a module-level `threading.Lock` to prevent double-bind race conditions.

### 6.8 HouBridge client (src/utils/hou_bridge.py) — known behaviours

- Each `HouBridge` instance has its own `threading.Lock`; `_send()` is thread-safe.
- `socket.TCP_NODELAY` is set on connect to avoid ~40 ms Nagle delay on Windows.
- A 30-second `socket.timeout` is set. If the server doesn't respond (e.g. Houdini is blocked cooking), `ConnectionError` is raised with a clear message and the socket is closed so the next call reconnects.
- On `BrokenPipeError` / `ConnectionResetError` the client reconnects once automatically.

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

---

## 9. Code Editor & QScintilla (v1.8.5+)

`src/ui/code_editor.py` provides `CodeEditor`, a Python-aware code editor used in the Node Builder, Script Editor dialog, and Scripting Console.

### 9.1 QScintilla is optional

QScintilla (`PyQt5.Qsci`) is tried first. If it is not installed, the module silently falls back to a `QPlainTextEdit`-based implementation with a `QSyntaxHighlighter`. **Do not re-raise `ImportError`** if QScintilla is missing — the app must still start.

```python
# Correct pattern inside code_editor.py
try:
    from PyQt5.Qsci import QsciScintilla, QsciLexerPython, QsciAPIs
    _QSCINTILLA_AVAILABLE = True
except ImportError:
    _QSCINTILLA_AVAILABLE = False
    # fallback class defined below

# Do NOT do this — it crashed the app on systems without QScintilla:
# raise ImportError("QScintilla is required...")
```

To install the full editor:
```
pip install QScintilla
```

### 9.2 Public API — same in both implementations

| Method / attribute | Notes |
|--------------------|-------|
| `setPlainText(text)` | Set editor content |
| `toPlainText()` | Get editor content |
| `textChanged` signal | Emitted on every keystroke |
| `lineNumberArea.hide()` / `.show()` | Compatibility shim |
| `apply_theme(is_dark: bool)` | Switch Dracula-dark / One-Light palette |
| `set_completer_list(words)` | Replace autocomplete word list |
| `append_completer_list(words)` | Add words to autocomplete list |
| `error_line` | Line number of last syntax error (-1 if none) |
| Ctrl+Wheel | Zoom in/out |

---

## 10. Bug History & What NOT to Revert (v1.8.5+)

These bugs were found and fixed. Do not revert these changes.

### 10.1 `code_editor.py` — hard crash when QScintilla missing
**Symptom**: `ImportError: No module named 'PyQt5.Qsci'` on startup, app exits immediately.  
**Fix**: Wrap import in `try/except`; define a `QPlainTextEdit`-based fallback `CodeEditor` class instead of raising.  
**File**: `src/ui/code_editor.py`

### 10.2 `hou_bridge.py` — socket issues on Windows
**Symptoms**: ~40 ms latency per RPC call; silent hangs when Houdini was busy; concurrent node calls corrupted the response stream.  
**Fixes**:
- `socket.TCP_NODELAY` set on connect to disable Nagle's algorithm
- `threading.Lock` per instance; `_send()` acquires lock before touching the socket
- `socket.timeout` (30 s) caught in `recv()` loop — disconnects and raises `ConnectionError` with a clear message
- Reconnect retry `sendall` wrapped in `try/except OSError`  
**File**: `src/utils/hou_bridge.py`

### 10.3 `vibrante_hou_server.py` — crashes in headless / non-interactive Houdini
**Symptoms**: `AttributeError` on `hou.playbar.frameRange()` when running hbatch or hython; `hou.OperationFailed` when setting display/render flags on unsupported nodes; port double-bind if `start()` called twice concurrently.  
**Fixes**:
- `hou.playbar.frameRange()` wrapped in `try/except AttributeError`; fallback `[1, 240]`
- `setDisplayFlag` / `setRenderFlag` guarded with `getattr` capability check + `try/except hou.OperationFailed`
- Module-level `threading.Lock` around `start()` / `stop()`  
**File**: `plugins/houdini/houdini/scripts/python/vibrante_hou_server.py`

### 10.4 `vibrante_node_houdini.py` — double `setup_env()` call
**Symptom**: Environment variables like `PYTHONHOME` were being stripped twice; `v_nodes_dir` / `v_scripts_path` were appended twice causing duplicate entries.  
**Fix**: `launch()` accepts `hip_file=""` directly and calls `setup_env()` once internally. `launch_with_context()` calls `launch(hip_file=hip_file)` — no longer calls `setup_env()` itself.  
**File**: `plugins/houdini/houdini/scripts/python/vibrante_node_houdini.py`

### 10.8 Live Wire Value Inspector (v1.8.6+)

**Feature**: Hover over any connected wire during or after execution to see the last value that flowed through it as a tooltip (`port_name: repr(value)`, capped at 300 chars).

**How it works:**
- `Edge.set_live_value(value)` stores the value and calls `self.setToolTip(label)`. Qt shows the tooltip automatically on hover.
- `Edge.shape()` overrides the default 2 px hit area with a 12 px stroked path so the wire is easy to hover over.
- `Edge.clear_live_value()` resets both `_live_value` and the tooltip.
- `NodeScene.update_edge_value(node_widget, port_name, value)` finds every edge whose `from_port.parentItem() is node_widget` and `from_port.port_definition.name == port_name`, then calls `set_live_value()`.
- `NodeScene.clear_edge_values()` clears all edges — called at the start of each execution run.
- `MainWindow._on_node_output` calls `scene.update_edge_value()` for every port in `results` immediately after calling `widget.set_parameter()`.

**Values persist after execution** so the user can inspect the final state of every wire without re-running. They are cleared only when the next execution starts.

### 10.7 Autosave / Crash Recovery (v1.8.6+)

**Feature**: A `QTimer` fires every 2 minutes and writes all non-empty open tabs to `~/.vibrante_node_autosave.json`. On the next launch, if that file exists, the user is offered a restore dialog. On clean exit (`closeEvent`), the file is deleted so the dialog is never shown unnecessarily.

**Format**:
```json
{"version": 1, "tabs": [{"name": "tab label", "file_path": "/saved/path.json or ''", "workflow": {...WorkflowModel dict...}}]}
```

**Key methods in `MainWindow`**:
- `_autosave()` — serialises all tabs; skips empty tabs and skips if `_is_executing`; silent on failure (prints to console only)
- `_try_restore_autosave()` — called in `__init__` before `add_new_workflow()`; returns `True` if any tab was restored (suppresses default empty tab); always deletes the autosave file after the dialog regardless of user choice
- `closeEvent` — calls `os.remove(_autosave_path)` after `_save_user_settings()`

**Guarded against**: execution in progress (`_is_executing`), empty tabs, corrupt autosave file (silently deleted), missing file on removal.

### 10.6 Recent Files (v1.8.6+)

**Feature**: File menu → **Open Recent** submenu lists the last 10 saved/loaded workflows. Entries for files that no longer exist on disk are shown grayed-out (disabled). "Clear Recent Files" wipes the list.

**Storage**: `config.get_recent_files()` / `config.add_recent_file(path)` / `config.clear_recent_files()` in `src/utils/config_manager.py`. Key: `"recent_files"` (JSON list of absolute paths, max 10, newest first).

**Registration**: `MainWindow._add_recent_file(path)` is called at the end of every successful `save_workflow`, `save_workflow_as`, and `load_workflow`. Opening from the menu calls `_load_workflow_from_path(path)` — same logic as `load_workflow` but without the file dialog.

**Menu rebuild**: `file_menu.aboutToShow` triggers `_rebuild_recent_menu()` so the list is always fresh when the File menu opens.

### 10.5 `window.py` — Houdini nodes and scripts never loaded
**Symptoms**: Nodes from `v_nodes_houdini/` did not appear in the Library after launching from Houdini. No Scripts menu. `v_scripts_path` env var was set but never read.  
**Fixes**:
- Changed `NodeRegistry.load_all(bundled_nodes)` → `NodeRegistry.load_all_with_extras(bundled_nodes)` so `v_nodes_dir` is honoured
- Added `&Scripts` menu in `_init_menu()` populated by `_populate_scripts_menu()` which scans `v_scripts_path`
- Added `_run_script_file(path)` to execute scripts in window/scene context  
**File**: `src/ui/window.py`

### 10.9 Canvas Search Bar — Ctrl+F (v1.8.7+)

**Feature**: Press Ctrl+F (or Edit → Find in Canvas…) to open a floating search bar centred at the top of the canvas. Type to filter `scene.nodes` by display name or `node_id`. The matched node is selected and the view pans to it. Enter/▼ cycles forward; Shift+Enter/▲ cycles backward. Match counter shows "X / N". Escape closes.

**Architecture:**
- `src/ui/canvas/canvas_search_bar.py` — `CanvasSearchBar(QFrame)`, child widget of `NodeView`. Positioned with `move(x, 8)` on show; repositioned in `NodeView.resizeEvent` if visible.
- `NodeView` — instantiates `_canvas_search_bar` in `__init__`; exposes `show_canvas_search()`.
- `MainWindow._init_menu()` — Edit menu separator + "Find in Canvas… Ctrl+F" action → `_find_in_canvas()`.
- Theme detected from `scene.backgroundBrush().color().lightness() < 128` (same pattern as `NodeSearchPopup`).

**Key search logic** (in `CanvasSearchBar._on_text_changed`):
```python
self._matches = [
    w for w in scene.nodes
    if t in w.node_definition.name.lower()
    or t in getattr(w.node_definition, 'node_id', '').lower()
]
```
Panning: `self._view.centerOn(node)` after `node.setSelected(True)`.

### 10.10 Node Execution Timing (v1.8.7+)

**Feature**: The log panel now shows how long each node took to execute — e.g. `Node 'Get Asset' finished in 0.34s`.

**Implementation** — 4 surgical changes to `src/ui/window.py` only:
- `import time` added to stdlib imports.
- `self._node_start_times = {}` reset in `execute_pipeline` before the executor is created (per-run isolation).
- `_on_node_started`: `self._node_start_times[node_instance_id] = time.perf_counter()`
- `_on_node_finished`: pops the start time, computes `elapsed = time.perf_counter() - t0`, logs `"Node 'X' finished in {elapsed:.2f}s"` at level `"info"`. `dict.pop(key, None)` guards against any race where finish fires without a matching start.

No changes to `engine.py` or any signal signatures.

### 10.11 Mini-map (v1.8.7+)

**Feature**: A 200×150 px thumbnail of the full canvas is always visible in the bottom-right corner of each `NodeView`. A blue semi-transparent rectangle shows the current viewport. Click or drag the mini-map to pan the main view. Toggle with Ctrl+M or Window → Toggle Mini-map.

**Architecture:**
- `src/ui/canvas/mini_map.py` — `MiniMap(QGraphicsView)`, child widget of `NodeView`. Shares the same `QGraphicsScene` — Qt renders the scene automatically.
- `setInteractive(False)` prevents scene items from receiving mouse events through the mini-map; `mousePressEvent`/`mouseMoveEvent` are overridden to call `self._main_view.centerOn(scene_pos)`.
- `drawForeground()` draws the viewport indicator in scene coordinates: maps `main_view.viewport().rect()` corners to scene space via `main_view.mapToScene()`, then draws a `QRectF`.
- `_do_fit()` calls `self.fitInView(scene.itemsBoundingRect() + padding, Qt.KeepAspectRatio)` and is debounced at 80 ms via a single-shot `QTimer` connected to `scene.changed`.
- `NodeView.__init__`: instantiates mini-map, calls `attach_scene(scene)`, connects `horizontalScrollBar().valueChanged` and `verticalScrollBar().valueChanged` to `mini_map.refresh()` (which just calls `update()`). Also calls `mini_map.refresh()` after `scale()` in `wheelEvent` and `mini_map.reposition()` in `resizeEvent`.
- `NodeView.apply_theme(is_dark)` cascades to `mini_map.apply_theme()` — called from `MainWindow._apply_dark_theme()` / `_apply_light_theme()`.
- `MainWindow._toggle_mini_map()` toggles `view._mini_map.setVisible(...)` for the current tab.

**Do not** call `setInteractive(True)` on the mini-map — scene item events must stay suppressed.

### 10.13 `asset_cache_manager.py` — deadlock in `remove_asset` (fixed 2026-06-12)

**Symptom**: `tests/unit/test_asset_cache_manager.py::test_remove_asset` (and any caller of `AssetCacheManager.remove_asset`) hung forever; full `pytest tests/unit` runs never finished.
**Cause**: `remove_asset()` called `_save_index()` while holding `self._lock`; `_save_index()` acquires the same non-reentrant `threading.Lock` → deadlock.
**Fix**: mutate the index under the lock, release it, then call `_save_index()` — the same pattern `cache_asset()` already used. Do not move `_save_index()` back inside the `with self._lock:` block.
**File**: `src/runtime/assets/acquisition_online/asset_cache_manager.py`

### 10.12 Subgraph / Group Node (v1.9.0+)

**Feature**: Select 2+ connected nodes and press **Ctrl+Shift+G** (Edit → Group Selection) to collapse them into a single `GroupNode` that stores the subgraph as an embedded `WorkflowModel`. Double-click the GroupNode to open the subgraph in a new tab (read-only view — edits there don't propagate back yet).

**Node classes** (`src/nodes/builtins/group_node.py`):
- `GroupInNode` (`group_in`): `use_exec=False`; input `port_name` (text widget); output `value`. Returns `{"value": self.parameters.get("_injected_value")}`. **Critical**: injection uses `parameters["_injected_value"]`, not `parameters["value"]` — `value` is an output port and the engine's `clear_outputs()` resets it to `None` during node prep, before `execute()` is called.
- `GroupOutNode` (`group_out`): `use_exec=True`; inputs `exec_in` + `port_name` (text widget) + `value`; outputs `exec_out` + `value`. Calls `set_output("exec_out", True)` so the inner exec chain can route explicitly through it. When no exec connection exists (legacy subgraphs), it runs as a data entry node — backward compatible.
- `GroupNode` (`group_node`): `use_exec=True`; fixed ports `exec_in`, `exec_out` (success), `exec_fail` (failure); stores `__workflow__` (WorkflowModel dict), `__port_defs__` (list of `{name, type, is_input}`), `__name__` (display name) in `self.parameters`. Dynamic ports are re-added at load time via `restore_from_parameters()`.
  - `exec_out` fires when the inner graph completes without an unhandled exception — regardless of semantic outcomes (e.g. a DCC node returning `success=False`). The inner graph is responsible for routing its own success/failure via exec pins.
  - `exec_fail` fires **only** when the inner graph has an unhandled exception (a node threw and `node_error` was emitted). Wire downstream error-handling nodes here for catastrophic failures only.
  - `group_out` values are read directly from the *source* node's `node_results` (not from `group_out` itself) to avoid a race where `group_out` executes as an entry node before the exec chain populates its value.

**Registry registration** (`src/core/registry.py`):
```python
from src.nodes.builtins.group_node import GroupInNode, GroupOutNode, GroupNode
for _cls in (GroupInNode, GroupOutNode, GroupNode):
    _cls.node_id = _cls.name
    cls._classes[_cls.name] = _cls
```
Registered in `_classes` only (not `_definitions`) → hidden from the node search popup but still executable and loadable from saved workflows.

**Collapsing** (`NodeScene.group_selection()` in `src/ui/canvas/scene.py`):
1. Classify all edges incident on selected nodes as boundary_in (external→selected), boundary_out (selected→external), boundary_exec_in, boundary_exec_out, or internal.
2. Build a `WorkflowModel` with: all selected `NodeInstanceModel`s + one `GroupInNode` per unique boundary_in port + one `GroupOutNode` per unique boundary_out port, wired to the corresponding inner node inputs/outputs.
3. Remove selected nodes and their edges from the scene.
4. Create a `GroupNode` widget at the centroid; set `__workflow__`, `__port_defs__`, `__name__` parameters; call `rebuild_ports()` to materialize the dynamic ports.
5. Reconnect external boundary edges to the new GroupNode's ports.

**UUID safety**: `widget.instance_id` can be a `UUID` object or a string UUID (paste path). Always compare with `str(instance_id)`.

**Double-click to inspect** (`NodeScene.mouseDoubleClickEvent`):
```python
def mouseDoubleClickEvent(self, event):
    for item in self.items(event.scenePos()):
        target = item
        while target is not None and not isinstance(target, NodeWidget):
            target = target.parentItem()
        if isinstance(target, NodeWidget) and getattr(target.node_definition, 'node_id', '') == 'group_node':
            parent = self.parent()
            if parent and hasattr(parent, '_open_subgraph_tab'):
                parent._open_subgraph_tab(target)
            event.accept()
            return
    super().mouseDoubleClickEvent(event)
```

**Tab opener** (`MainWindow._open_subgraph_tab(group_widget)`):
- Reads `group_widget.node_definition.parameters["__workflow__"]`
- Validates as `WorkflowModel`
- Calls `add_new_workflow(f"[{group_name}]")` → `view.scene().from_workflow_model(workflow_model)`
- Sets `scene._sync_callback` — a closure that writes every change back to `group_widget.node_definition.parameters["__workflow__"]` and pushes the parent scene's history. Triggered by `push_history()` (user edits), `undo()`, and `redo()` on the subgraph scene. Subgraph tabs are now fully editable.

**Keyboard shortcut conflict note**: Ctrl+G is already used by "Wrap in Backdrop" in `view.keyPressEvent`. Group Selection uses **Ctrl+Shift+G** instead.

---

## 33. Asset Realization & DCC Integration (Tier 13)

Tier 13 converts AssetDescriptors from Tiers 8/12 into production-ready scene assets through a deterministic pipeline: import → convert → normalize → resolve dependencies → map materials → build USD → instance → realize as transaction ops → validate → review.

**Non-negotiable design rules:**
1. No bridge calls. All modules are planning/advisory only. Never import or call `get_bridge()`.
2. No randomness. Same input always produces the same output.
3. All mutations generate transaction operation dicts — never direct Houdini mutations.
4. Review must be specific — never return "Execution successful".
5. Never raises in public methods — capture errors in result dicts.
6. Singleton pattern — every module has `get_X()` and `reset_X_for_tests()`.
7. Use `threading.Lock` for thread safety.
8. `dataclass` + `to_dict()` / `from_dict()` pattern for all models.

### 33.1 Module layout

```
src/runtime/assets/realization/
    __init__.py                    ← full re-export of all public surface
    asset_importer.py              ← ImportResult + AssetImporter (SUPPORTED_FORMATS)
    asset_converter.py             ← ConversionResult + AssetConverter (CONVERSION_MATRIX)
    asset_normalizer.py            ← NormalizationResult + AssetNormalizer (_UNIT_SCALE_FACTORS)
    asset_dependency_resolver.py   ← DependencyResult + AssetDependencyResolver
    asset_material_mapper.py       ← MaterialProfile + MaterialMappingResult + AssetMaterialMapper (SUPPORTED_RENDERERS)
    usd_builder.py                 ← UsdAsset + UsdBuildResult + UsdBuilder (USD_SCHEMA_VERSION = "1.0")
    asset_instancer.py             ← AssetInstance + InstancePlan + AssetInstancer
    scene_asset_realizer.py        ← RealizationSpec + RealizationPlan + RealizedAsset + SceneAssetRealizer
    asset_validation_pipeline.py   ← PipelineValidationResult + AssetValidationPipeline
    asset_realization_review.py    ← RealizationReviewResult + AssetRealizationReview
    realization_serializer.py      ← RealizationSerializer (sorted-key JSON, _schema_version = "1.0.0")
    realization_statistics.py      ← RealizationStatistics (in-memory, capped at 2000 records)
```

### 33.2 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_asset_import` | Import an asset descriptor with provenance tracking |
| `hou_mcp_asset_convert` | Convert asset format (default: usd) |
| `hou_mcp_asset_realize` | Build RealizationPlan + transaction ops |
| `hou_mcp_asset_dependencies` | Resolve textures, materials, references |
| `hou_mcp_asset_materials` | Map materials to renderer profiles |
| `hou_mcp_usd_builder` | Generate USD hierarchy + metadata |
| `hou_mcp_realization_review` | Quality review: grade, score, production_ready, findings |

**Canonical workflow:** `hou_mcp_asset_import` → `hou_mcp_asset_convert` → `hou_mcp_asset_dependencies` → `hou_mcp_asset_materials` → `hou_mcp_usd_builder` → `hou_mcp_asset_realize` → `hou_mcp_realization_review`

### 33.3 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `asset_realization` | Full pipeline from AssetDescriptor to transaction ops |
| `asset_import` | Import with provenance tracking |
| `asset_conversion` | Format conversion using CONVERSION_MATRIX |
| `asset_normalization` | Scale, orientation, units, pivot normalization |
| `asset_dependency_resolution` | Texture, material, reference resolution |
| `usd_asset_generation` | USD hierarchy + metadata descriptor generation |

### 33.4 Key constants

- `SUPPORTED_FORMATS = frozenset({"fbx","obj","gltf","glb","usd","usda","usdc","usdz"})`
- `SUPPORTED_RENDERERS = frozenset({"arnold","usd_preview_surface","generic_pbr","karma"})`
- `USD_SCHEMA_VERSION = "1.0"`
- Score weights: `import=0.20, conversion=0.20, dependency=0.25, material=0.20, realization=0.15`
- `production_ready` requires `overall_score >= 0.7` AND no blocking findings

### 33.5 Deferred items (NOT in this work)

- **Real file I/O** — AssetImporter and AssetConverter generate metadata only; no actual file read/write.
- **Real USD SDK** — UsdBuilder generates descriptive data structures; no `pxr.Usd` imports.
- **Real DCC conversion** — CONVERSION_MATRIX validates paths; no subprocess calls to Houdini/FBX SDK.
- **Real shader generation** — AssetMaterialMapper generates MaterialProfile dicts; no HDA/VOP node creation.
- **Realization execution** — SceneAssetRealizer generates transaction ops; actual execution routes through `hou_mcp_transaction` (Tier 2).

---

## 35. Fab / Quixel Asset Acquisition Service (Tier 12.5)

Tier 12.5 upgrades the simulated AssetDownloadManager into a real local-library acquisition layer. Vibrante discovers, indexes, tracks, and consumes assets acquired through official Fab/Megascans workflows. It never scrapes websites, bypasses authentication, or hardcodes credentials.

**Non-negotiable safety rules:**
1. No network calls in any acquisition module.
2. No Epic/Fab authentication — only reads local filesystem.
3. No hardcoded credentials.
4. Actual downloading is external — done by the user through the official Fab desktop application.
5. Vibrante only discovers, indexes, tracks, and consumes what is already on disk.

### 35.1 Module layout

```
src/runtime/assets/acquisition/
    __init__.py                  ← full re-export of all public surface
    fab_library_scanner.py       ← FabAssetRecord + FabScanResult + FabLibraryScanner
    megascans_scanner.py         ← MegascansAssetRecord + MegascansScanResult + MegascansScanner
    download_registry.py         ← RegistryEntry + DownloadRegistry (persistent JSON)
    library_index.py             ← IndexEntry + IndexSearchResult + LibraryIndex
    library_watcher.py           ← WatchEntry + NewAssetEvent + LibraryWatcher
    acquisition_manager.py       ← AcquisitionRequest + AcquisitionResult + AcquisitionManager
```

### 35.2 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_asset_acquisition` | ensure/locate/request/register assets |
| `hou_mcp_library_scan` | scan Fab + Megascans libraries |
| `hou_mcp_library_index` | search/stats/save/providers/categories |
| `hou_mcp_library_watch` | watch/snapshot/detect/stats/recent |

**Canonical workflow:** `hou_mcp_library_scan` → `hou_mcp_library_index` (search) → `hou_mcp_asset_acquisition` (ensure) → existing realization pipeline

### 35.3 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `fab_library_scan` | Scan local Fab library for acquired assets |
| `megascans_library_scan` | Scan local Megascans library |
| `asset_acquisition` | Orchestrate local asset acquisition |
| `library_index` | Searchable index of local libraries |
| `library_watch` | Detect newly downloaded assets |

### 35.4 Environment variables

| Variable | Used by |
|---|---|
| `VIBRANTE_FAB_LIBRARY` | FabLibraryScanner, LibraryWatcher |
| `VIBRANTE_MEGASCANS_LIBRARY` | MegascansScanner, LibraryWatcher |
| `VIBRANTE_ASSET_STORAGE` | DownloadRegistry (registry file), LibraryIndex (index file) |

### 35.5 Megascans asset type → Vibrante category mapping

| ms_type | category |
|---|---|
| `3d` | `prop` |
| `3dplant` | `vegetation` |
| `surface` | `material` |
| `decal` | `material` |
| `imperfection` | `material` |
| `atlas` | `material` |
| `brush` | `material` |

### 35.6 AcquisitionManager.ensure_asset_available() priority chain

```
ensure_asset_available(provider, asset_id):
  1. DownloadRegistry.find()              → "registry"
  2. LibraryIndex.get_entry()             → "library_index"
  3. FabLibraryScanner.index_assets()     → "fab_scan"      (provider=fab or "")
  4. MegascansScanner.scan_megascans()    → "megascans_scan" (provider=megascans/quixel or "")
  → if none found: source="not_found", warns user to fetch via Fab desktop app
```

### 35.7 Test conventions

- Reset ALL singletons in `autouse` fixture via `monkeypatch.delenv` for env vars
- `test_acquisition_manager` resets: manager + registry + index + fab_scanner + megascans_scanner
- `test_library_watcher` resets: watcher + registry
- All Fab/Megascans scan tests use `tmp_path` with hand-crafted JSON manifests + empty asset files
- No network assertions, no real Fab/Megascans directories required

---

## 36. Semantic Vector Search & Asset Retrieval (Tier 12.8)

Tier 12.8 extends the Tier 12.7 semantic catalog into intent-driven vector retrieval. It understands production intent and retrieves the most suitable assets semantically.

**Non-negotiable design rules (same as Tier 12.7):**
1. No bridge calls, no network calls.
2. Deterministic with DeterministicEmbeddingProvider — same input → same output.
3. Never raises in public methods.
4. Singleton pattern + injectable providers for tests.
5. Thread-safe throughout.

### 36.1 What Tier 12.8 does NOT do

- Download assets
- Build Houdini nodes or scenes
- Generate shaders
- Perform real ML training

### 36.2 Module layout

```
src/runtime/assets/vector_search/
    __init__.py                       ← full re-export of all public surface
    semantic_similarity.py            ← cosine_similarity, rank_similarity, score_match, normalize_scores
    embedding_provider.py             ← DeterministicEmbeddingProvider (128-dim, no deps) + SentenceTransformersProvider
    intent_parser.py                  ← ParsedIntent + IntentParser (keyword extraction, no ML)
    asset_vector_store.py             ← VectorSearchResult + AssetVectorStore (pure-Python, optional FAISS)
    retrieval_statistics.py           ← RetrievalStatistics (capped at 2000)
    retrieval_serializer.py           ← RetrievalSerializer (sorted-key JSON, schema 1.0.0)
    asset_embedding_builder.py        ← EmbeddedAsset + AssetEmbeddingBuilder
    intent_embedding_engine.py        ← IntentEmbeddingEngine
    vector_search_engine.py           ← VectorSearchResponse + VectorSearchEngine
    hybrid_ranking_engine.py          ← RankedAsset + HybridRankingEngine (6-signal scoring)
    retrieval_pipeline.py             ← RetrievalResult + RetrievalPipeline (full pipeline)
    retrieval_review.py               ← RetrievalReviewResult + RetrievalReview
    catalog_vector_index_builder.py   ← IndexBuildResult + CatalogVectorIndexBuilder
```

### 36.3 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_vector_search` | Vector search: search/search_environment/search_role/search_storytelling/search_cinematic |
| `hou_mcp_asset_retrieval` | Full retrieval pipeline: retrieve/retrieve_environment/retrieve_hero/retrieve_storytelling |
| `hou_mcp_intent_parser` | Parse natural language intent into structured fields |
| `hou_mcp_hybrid_ranking` | Rank asset candidates using hybrid 6-signal scoring |
| `hou_mcp_vector_index` | Build/rebuild/update/stats for the vector index |
| `hou_mcp_retrieval_review` | Review retrieval quality: score/grade/production_ready |

**Canonical workflow:** `hou_mcp_catalog_sync` → `hou_mcp_vector_index` (build_full) → `hou_mcp_asset_retrieval` → `hou_mcp_retrieval_review`

### 36.4 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `semantic_vector_search` | 128-dim deterministic or sentence-transformers vector search |
| `asset_retrieval` | Full pipeline: intent → embed → vector search → hybrid ranking → assets |
| `intent_embedding` | Convert ParsedIntent into embedding vectors |
| `hybrid_asset_ranking` | 6-signal weighted ranking (vector 40%, env 20%, story 15%, lookdev 10%, graph 10%, memory 5%) |
| `vector_index_management` | Build/update/rebuild vector index from semantic catalog |
| `retrieval_review` | Evaluate precision, semantic relevance, env accuracy, role accuracy |

### 36.5 Embedding architecture

**DeterministicEmbeddingProvider** (default, always available):
- 128 dimensions — 110 fixed vocabulary dims + 18 SHA-256 overflow dims
- No external ML dependencies required
- Deterministic: same text → same vector across all runs/machines
- Vocabulary covers 110 production terms (environments, roles, lookdev, categories, materials)
- Unknown tokens → `SHA256(token) % 18` overflow dimension
- L2-normalized output

**SentenceTransformersProvider** (optional enhancement):
- Uses `all-MiniLM-L6-v2` (384 dims) if `sentence_transformers` is installed and model is cached
- Falls back to DeterministicEmbeddingProvider silently if unavailable
- Model must be pre-cached — no auto-download

**Provider injection for tests:**
```python
from src.runtime.assets.vector_search import set_embedding_provider, DeterministicEmbeddingProvider
set_embedding_provider(DeterministicEmbeddingProvider())
```

### 36.6 Hybrid ranking weights

| Signal | Weight | Source |
|---|---|---|
| `vector_similarity` | 0.40 | Cosine similarity from vector store |
| `environment_fit` | 0.20 | primary_env match / environments list match |
| `storytelling_match` | 0.15 | Exact storytelling field match |
| `lookdev_match` | 0.10 | Lookdev tag presence |
| `knowledge_graph` | 0.10 | Knowledge graph neighbor relationships |
| `production_memory` | 0.05 | importance field (primary/secondary/tertiary/ambient) |

Weights sum to exactly 1.0.

### 36.7 Retrieval review grade mapping

| Score | Grade | production_ready |
|---|---|---|
| ≥ 0.85 | A | ✓ |
| ≥ 0.70 | B | ✓ |
| ≥ 0.55 | C | ✗ |
| ≥ 0.40 | D | ✗ |
| < 0.40 | F | ✗ |

Score dimensions: `result_count (0.25) + semantic_relevance (0.30) + environment_accuracy (0.25) + role_accuracy (0.20)`

### 36.8 Test conventions

- Reset ALL singletons in `autouse` fixture (including `set_embedding_provider(DeterministicEmbeddingProvider())`)
- 12 test files in `tests/unit/`: `test_embedding_provider.py`, `test_semantic_similarity.py`, `test_intent_parser.py`, `test_asset_vector_store.py`, `test_asset_embedding_builder.py`, `test_hybrid_ranking_engine.py`, `test_intent_embedding_engine.py`, `test_vector_search_engine.py`, `test_retrieval_pipeline.py`, `test_retrieval_review.py`, `test_retrieval_statistics.py`, `test_retrieval_serializer.py`, `test_catalog_vector_index_builder.py`
- Always inject `DeterministicEmbeddingProvider` in fixtures — never rely on sentence-transformers in tests
- No network calls, no real DCC calls, no real Megascans directories

---

## 34. Lookdev & Material Intelligence (Tier 14)

Tier 14 provides a deterministic material intelligence layer: understand material semantics, recommend production-proven materials, map to renderer-aware profiles, generate assignment plans, and evaluate lookdev quality. This tier is planning and advisory only — it never generates shaders, builds Arnold/Karma node graphs, or performs rendering.

**Non-negotiable design rules (same as Tier 13):**
1. No bridge calls. All modules are planning/advisory only.
2. No randomness. Same input always produces the same output.
3. Never raises in public methods — errors in result dicts.
4. Singleton pattern — `get_X()` + `reset_X_for_tests()`.
5. Thread-safe (`threading.Lock` per instance).
6. `dataclass` + `to_dict()` / `from_dict()` pattern on all result classes.

### 34.1 Module layout

```
src/runtime/lookdev/
    __init__.py                    ← full re-export of all public surface
    material_library.py            ← MaterialEntry + MaterialLibrary (13 built-ins)
    material_knowledge.py          ← MaterialInference + MaterialKnowledge (keyword inference)
    lookdev_patterns.py            ← LookdevPattern + LookdevPatterns (5 built-in environments)
    renderer_profiles.py           ← RendererProfile + RendererProfiles (arnold/karma/usd)
    material_recommendation.py     ← MaterialRecommendation + MaterialRecommendationResult + MaterialRecommendationEngine
    material_assignment_engine.py  ← AssignmentEntry + AssignmentPlan + MaterialAssignmentEngine
    lookdev_review.py              ← LookdevReviewResult + LookdevReview (4-dimension scoring)
    lookdev_statistics.py          ← LookdevStatistics (in-memory, capped at 2000)
    lookdev_serializer.py          ← LookdevSerializer (sorted-key JSON, _schema_version = "1.0.0")
    lookdev_validation.py          ← LookdevValidation (structural validation)
```

### 34.2 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_material_library` | Browse/search material definitions |
| `hou_mcp_material_recommend` | Recommend material for an asset |
| `hou_mcp_material_assign` | Generate assignment plan (transaction ops) |
| `hou_mcp_lookdev_review` | Evaluate lookdev quality |
| `hou_mcp_renderer_profile` | Get renderer material class + input map |
| `hou_mcp_lookdev_patterns` | Browse/rank lookdev recipes |

**Canonical workflow:** `hou_mcp_lookdev_patterns` → `hou_mcp_material_recommend` → `hou_mcp_material_assign` → `hou_mcp_lookdev_review`

### 34.3 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `material_intelligence` | Full lookdev pipeline — planning only |
| `lookdev_patterns` | Environment-matched lookdev recipes |
| `material_recommendation` | Priority-chain material recommendation |
| `material_assignment` | Semantic assignment plan generation |
| `lookdev_review` | 4-dimension lookdev quality evaluation |
| `renderer_profiles` | Renderer-aware material class mappings |

### 34.4 Key constants

- `BUILTIN_MATERIAL_CATEGORIES` — `frozenset` of 13 material category names
- `SUPPORTED_RENDERERS = frozenset({"arnold", "karma", "usd_preview_surface"})`
- `LOOKDEV_SCHEMA_VERSION = "1.0.0"`
- Score weights: `material_consistency=0.30, environment_coherence=0.25, renderer_compatibility=0.25, visual_quality=0.20`
- `production_ready` requires `overall_score >= 0.70` AND no blocking findings

### 34.5 Recommendation priority chain

```
recommend_material(asset_dict, renderer):
    1. LookdevPatterns.rank_patterns(asset_dict)   → confidence 0.85  (source: "lookdev_pattern")
    2. MaterialKnowledge.build_material_profile()  → confidence 0.70  (source: "material_knowledge")
    3. RendererProfiles.get_profile(renderer)      → confidence 0.50  (source: "renderer_default")
```

### 34.6 Lookdev review grade mapping

| Score | Grade | production_ready |
|---|---|---|
| ≥ 0.85 | A | ✓ (if no blocking findings) |
| ≥ 0.70 | B | ✓ (if no blocking findings) |
| ≥ 0.55 | C | ✗ |
| ≥ 0.40 | D | ✗ |
| < 0.40 | F | ✗ |

Blocking findings contain keywords: `"no materials"`, `"zero assignments"`, `"invalid renderer"`, `"empty plan"`.

### 34.7 Test conventions

- Reset ALL singletons in `autouse` fixture (including transitive deps)
- `recommend_material` tests reset: engine + library + knowledge + patterns + renderer_profiles
- `assign_materials` tests reset: engine + recommendation engine + all recommendation deps
- `review_lookdev` tests reset: engine + library + renderer_profiles + patterns
- Never import from Houdini, Arnold, Karma, or real USD in tests

---

## 35. Semantic Asset Catalog & Megascans Knowledge Layer (Tier 12.7)

Tier 12.7 transforms raw asset metadata into production knowledge. It provides a semantic catalog capable of understanding environments, storytelling roles, cinematic usage, lookdev suitability, and placement context.

**Non-negotiable design rules:**
1. No bridge calls, no network calls unless Megascans token is configured.
2. No randomness. Same input always produces the same output.
3. Never raises in public methods — errors in result dicts.
4. Singleton pattern — `get_X()` + `reset_X_for_tests()`.
5. Thread-safe (`threading.Lock` per instance).
6. `dataclass` + `to_dict()` / `from_dict()` pattern on all result classes.
7. Local metadata always takes priority over API calls.

### 35.1 What Tier 12.7 does NOT do

- Download assets
- Build Houdini nodes or scenes
- Generate shaders
- Scrape websites or bypass authentication

### 35.2 Module layout

```
src/runtime/assets/semantic/
    __init__.py                    ← full re-export of all public surface
    asset_environment_mapper.py    ← EnvironmentMapping + AssetEnvironmentMapper (5 built-in envs)
    asset_role_classifier.py       ← RoleClassification + AssetRoleClassifier (6 roles)
    asset_storytelling_mapper.py   ← StorytellingMapping + AssetStorytellingMapper (5 roles)
    asset_lookdev_mapper.py        ← LookdevMapping + AssetLookdevMapper (10 tags)
    asset_cinematic_mapper.py      ← CinematicMapping + AssetCinematicMapper (5 usages)
    asset_catalog_statistics.py    ← StatRecord + CatalogStatistics (capped at 2000 records)
    asset_catalog_serializer.py    ← AssetCatalogSerializer (sorted-key JSON, schema 1.0.0)
    asset_manifest_reader.py       ← ManifestRecord + AssetManifestReader (asset.json/manifest.json/metadata.json)
    megascans_metadata_client.py   ← MegascansAssetMetadata + MegascansMetadataClient (official API, offline safe)
    asset_metadata_extractor.py    ← ExtractedMetadata + AssetMetadataExtractor
    semantic_asset_enricher.py     ← EnrichedAsset + SemanticAssetEnricher (runs all mappers)
    asset_knowledge_graph.py       ← KnowledgeRelationship + AssetKnowledgeGraph
    asset_catalog.py               ← CatalogEntry + AssetCatalog (in-memory + JSON persistence)
    asset_metadata_provider.py     ← MetadataRecord + AssetMetadataProvider (priority chain)
    asset_catalog_sync.py          ← SyncReport + AssetCatalogSync
    asset_query_engine.py          ← QueryResult + AssetQueryEngine (intent-driven retrieval)
    asset_catalog_review.py        ← CatalogReviewResult + AssetCatalogReview
```

### 35.3 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_asset_catalog` | Register, update, remove, get, search catalog assets |
| `hou_mcp_asset_search` | Semantic search by environment, role, lookdev, intent |
| `hou_mcp_asset_environment` | Map/rank environments or query by environment |
| `hou_mcp_asset_storytelling` | Map storytelling roles or query by role |
| `hou_mcp_asset_graph` | Add/remove/query knowledge graph relationships |
| `hou_mcp_catalog_sync` | Sync from Megascans API or refresh existing entries |

**Canonical workflow:** `hou_mcp_catalog_sync` (sync_new) → `hou_mcp_asset_search` → `hou_mcp_asset_environment` → `hou_mcp_asset_storytelling` → `hou_mcp_asset_graph` (build) → `hou_mcp_asset_catalog` (review)

### 35.4 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `semantic_asset_catalog` | Persistent semantic database with environment/role/lookdev metadata |
| `semantic_asset_search` | Intent-driven semantic asset retrieval |
| `megascans_metadata_sync` | Sync Megascans API metadata into catalog (offline-safe) |
| `environment_asset_mapping` | Keyword-based environment → asset mapping |
| `asset_storytelling_mapping` | Narrative role classification for assets |
| `asset_knowledge_graph` | Semantic relationship graph between catalog assets |

### 35.5 Metadata source priority chain

```
get_metadata(asset_id, local_path):
  1. Local Asset Manifest (asset.json / manifest.json / metadata.json)  → "local_manifest"
  2. Local Semantic Catalog (AssetCatalog.get_asset())                  → "catalog"
  3. Megascans API (MegascansMetadataClient.get_asset())                → "megascans_api"
  4. Provider Fallback                                                   → "provider_fallback"
```

Never queries Megascans API if local metadata exists.

### 35.6 Built-in constants

- `BUILTIN_ENVIRONMENTS = frozenset({"industrial_hangar", "robotics_lab", "control_room", "sci_fi_corridor", "abandoned_factory"})`
- `BUILTIN_ROLES = frozenset({"hero", "support", "foreground", "midground", "background", "set_dressing"})`
- `STORYTELLING_ROLES = frozenset({"hero_object", "context_builder", "scale_reference", "visual_anchor", "atmosphere_builder"})`
- `LOOKDEV_TAGS = frozenset({"clean", "weathered", "aged", "industrial", "sci_fi", "rusted", "polished", "worn", "damaged", "pristine"})`
- `CINEMATIC_USAGES = frozenset({"hero_focus", "silhouette", "foreground_interest", "depth_layer", "visual_balance"})`
- `RELATIONSHIP_TYPES = frozenset({"commonly_used_with", "same_environment", "same_style", "same_template", "successful_pairing"})`

### 35.7 Catalog review grade mapping

| Score | Grade | production_ready |
|---|---|---|
| ≥ 0.85 | A | ✓ (if no blocking findings) |
| ≥ 0.70 | B | ✓ (if no blocking findings) |
| ≥ 0.55 | C | ✗ |
| ≥ 0.40 | D | ✗ |
| < 0.40 | F | ✗ |

Score weights: `env_coverage=0.35, role_coverage=0.30, lookdev_coverage=0.20, enrich_fraction=0.15`
Blocking findings contain keywords: `"empty catalog"`, `"no environments"`, `"no roles"`.

### 35.8 Megascans token environment variable

```
VIBRANTE_MEGASCANS_TOKEN  — Megascans / Fab API token (optional)
```

If not set, all MegascansMetadataClient operations return `source="offline"` with a clear advisory message. No exceptions, no crashes.

MegascansMetadataClient supports an injectable `_transport` attribute for testing:
```python
client = get_megascans_metadata_client()
client._transport = MyMockTransport()  # .get(url, token, params) → dict
```

### 35.9 Test conventions

- Reset ALL singletons in `autouse` fixture (all 17 singletons)
- All tests in `tests/unit/test_semantic_catalog.py`
- No network calls — Megascans API tested via injectable mock transport
- Manifest tests use `tmp_path` with hand-crafted JSON files
- No assertions about real Fab/Megascans directories

---

## 37. Online Asset Acquisition & Intelligent Asset Fetching (Tier 12.9)

Tier 12.9 completes the acquisition loop. It adds authenticated provider sessions, selective asset downloads (only for semantically-ranked assets), download queue management, project-local staging, and asset provenance tracking.

**Non-negotiable design rules:**
1. No hardcoded credentials. Tokens read from environment only (`VIBRANTE_MEGASCANS_TOKEN`).
2. No network calls unless a token is set.
3. Never download assets that haven't been selected by the semantic intelligence layers.
4. No randomness. Same input always produces the same output.
5. Never raises in public methods — errors in result dicts.
6. Singleton pattern — `get_X()` + `reset_X_for_tests()`.
7. Thread-safe (`threading.Lock` per instance).
8. `dataclass` + `to_dict()` / `from_dict()` pattern on all result classes.
9. Injectable `_transport` attribute on all network-calling classes for tests.

### 37.1 Module layout

```
src/runtime/assets/acquisition_online/
    __init__.py                       ← full re-export of all public surface
    provider_session_manager.py       ← ProviderSession + ProviderSessionManager
    megascans_auth.py                 ← AuthToken + MegascansAuth
    megascans_search.py               ← MegascansSearchRecord + MegascansSearch
    megascans_download.py             ← DownloadResult + MegascansDownloader
    asset_fetcher.py                  ← FetchResult + AssetFetcher (cache-first)
    download_queue.py                 ← DownloadTask + DownloadQueue (persistent JSON)
    download_scheduler.py             ← SchedulerResult + DownloadScheduler
    asset_cache_manager.py            ← CacheEntry + AssetCacheManager
    project_asset_staging.py          ← StagingEntry + ProjectAssetStaging
    asset_provenance_tracker.py       ← ProvenanceRecord + AssetProvenanceTracker
    acquisition_pipeline.py           ← AcquisitionPipelineResult + AcquisitionPipeline
    download_review.py                ← DownloadReviewResult + DownloadReview
    download_statistics.py            ← DownloadRecord + DownloadStatistics
    download_serializer.py            ← DownloadSerializer (sorted-key JSON, schema 1.0.0)
```

### 37.2 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_asset_fetch` | Cache-first acquisition for semantically-selected assets |
| `hou_mcp_asset_download` | Megascans downloader with checksum validation and retry |
| `hou_mcp_download_queue` | Manage the persistent download queue |
| `hou_mcp_asset_cache` | Inspect and manage the local asset cache |
| `hou_mcp_asset_staging` | Project-local asset staging |
| `hou_mcp_download_review` | Validate acquisition quality |

**Canonical workflow:** `hou_mcp_asset_retrieval` → `hou_mcp_asset_fetch` → `hou_mcp_asset_staging` → `hou_mcp_download_review`

### 37.3 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `online_asset_acquisition` | Full intelligent acquisition pipeline |
| `asset_fetching` | Cache-first asset fetcher with Megascans API fallback |
| `download_management` | Persistent queue + rate-limited scheduler |
| `asset_caching` | Local cache with SHA-256 deduplication |
| `project_asset_staging` | Project-local asset sets |
| `asset_provenance_tracking` | Append-only provenance log with integrity verification |

### 37.4 Environment variables

| Variable | Used by |
|---|---|
| `VIBRANTE_MEGASCANS_TOKEN` | MegascansAuth, MegascansSearch, MegascansDownloader |
| `VIBRANTE_ASSET_CACHE` | AssetCacheManager, DownloadQueue, AssetProvenanceTracker |
| `VIBRANTE_PROJECT_STAGING` | ProjectAssetStaging |

### 37.5 Acquisition priority chain

```
AssetFetcher.ensure_asset_available(asset_id, provider):
  1. AssetCacheManager.asset_exists()              → source="cache"
  2. AcquisitionManager.ensure_asset_available()  → source="registry"
  3. MegascansDownloader.download_asset()          → source="megascans_api"
  → if offline/no token: source="offline", advises user to set VIBRANTE_MEGASCANS_TOKEN
```

### 37.6 Download review grade mapping

| Score | Grade | production_ready |
|---|---|---|
| ≥ 0.85 | A | ✓ |
| ≥ 0.70 | B | ✓ |
| ≥ 0.55 | C | ✗ |
| ≥ 0.40 | D | ✗ |
| < 0.40 | F | ✗ |

Score weights: `download_success=0.35, integrity=0.30, cache_efficiency=0.20, provenance_quality=0.15`
Blocking findings contain keywords: `"no assets"`, `"zero downloads"`, `"all failed"`, `"no provenance"`

### 37.7 Security rules

- **Never** hardcode credentials.
- **Never** store the raw token in any serialized output — `AuthToken.to_dict()` always returns `"***"`.
- **Never** restore a token from a serialized `AuthToken.from_dict()` — `token` field is always set to `""`.
- **Never** download assets not selected by `AssetFetcher` / `AcquisitionPipeline`.
- The injectable `_transport` attribute on `MegascansAuth`, `MegascansSearch`, `MegascansDownloader` is for **tests only** — never set it in production code.

### 37.8 Test conventions

- Reset ALL singletons in `autouse` fixture (14 singletons)
- Inject `_MockAuthTransport` and `_MockDownloadTransport` in fixtures — never use real Megascans API
- Use `monkeypatch.setenv("VIBRANTE_MEGASCANS_TOKEN", "tok")` to simulate auth
- Use `tmp_path` for `VIBRANTE_ASSET_CACHE` and `VIBRANTE_PROJECT_STAGING`
- No real network calls, no real credentials, no real purchases
- 14 test files in `tests/unit/`: `test_provider_session_manager.py`, `test_megascans_auth.py`, `test_megascans_search.py`, `test_megascans_download.py`, `test_asset_fetcher.py`, `test_download_queue.py`, `test_download_scheduler.py`, `test_asset_cache_manager.py`, `test_project_asset_staging.py`, `test_asset_provenance_tracker.py`, `test_acquisition_pipeline.py`, `test_download_review.py`, `test_download_statistics.py`, `test_download_serializer.py`

---

## 38. Lighting Intelligence & Cinematic Illumination (Tier 15)

Tier 15 provides production-aware lighting intelligence. It understands mood, story intent, cinematic language, environment context, material response, visual hierarchy, and readability. Generates renderer-agnostic lighting plans. Never creates Houdini lights.

**Non-negotiable design rules:**
1. No bridge calls. All modules are planning/advisory only. Never import or call `get_bridge()`.
2. No randomness. Same input always produces the same output.
3. Never raises in public methods — errors in result dicts.
4. Singleton pattern — `get_X()` + `reset_X_for_tests()`.
5. Thread-safe (`threading.Lock` per instance).
6. `dataclass` + `to_dict()` / `from_dict()` pattern on all result classes.
7. Generate plans, not renderer nodes.

### 38.1 Module layout

```
src/runtime/lighting/
    __init__.py                       ← full re-export of all public surface
    lighting_knowledge.py             ← LightingConcept + LightingKnowledge (14 builtin concepts)
    lighting_language.py              ← LightingIntent + LightingLanguage (keyword intent parsing)
    lighting_patterns.py              ← LightingPattern + LightingPatterns (8 builtin patterns)
    lighting_environment_mapper.py    ← EnvironmentLightingMapping + LightingEnvironmentMapper
    lighting_mood_engine.py           ← MoodProfile + LightingMoodEngine (8 builtin moods)
    lighting_readability_engine.py    ← ReadabilityResult + LightingReadabilityEngine
    lighting_hierarchy_engine.py      ← HierarchyEntry + FocusHierarchy + LightingHierarchyEngine
    lighting_color_engine.py          ← ColorStrategy + LightingColorEngine (10 palettes)
    lighting_exposure_engine.py       ← ExposureStrategy + LightingExposureEngine (8 profiles)
    lighting_strategy_engine.py       ← LightingStrategy + LightingStrategyEngine
    lighting_recommendation_engine.py ← LightingRecommendation + LightingRecommendationEngine
    lighting_plan_builder.py          ← LightSpec + LightPlan + LightingPlanBuilder
    lighting_review.py                ← LightingReviewResult + LightingReview
    lighting_statistics.py            ← LightingStatistics (in-memory, capped at 2000)
    lighting_serializer.py            ← LightingSerializer (sorted-key JSON, schema 1.0.0)
    lighting_validation.py            ← LightingValidation
```

### 38.2 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_lighting_strategy` | Generate lighting strategy from intent/environment/mood |
| `hou_mcp_lighting_plan` | Build renderer-agnostic lighting plan (key/fill/rim/practicals/volumetrics) |
| `hou_mcp_lighting_review` | 6-dimension quality review |
| `hou_mcp_lighting_pattern` | Browse/search/rank/recommend patterns |
| `hou_mcp_lighting_mood` | Infer mood from intent or build mood profile |
| `hou_mcp_lighting_readability` | Evaluate visual readability and recommend adjustments |

**Canonical workflow:** `hou_mcp_lighting_strategy` → `hou_mcp_lighting_plan` → `hou_mcp_lighting_review`

### 38.3 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `lighting_intelligence` | Full cinematic illumination pipeline — planning only |
| `lighting_strategy` | Holistic strategy from intent + environment + mood |
| `lighting_planning` | Renderer-agnostic plan generation |
| `lighting_review` | 6-dimension quality evaluation |
| `lighting_readability` | Visual clarity and hierarchy evaluation |
| `lighting_recommendation` | Pattern-first production recommendation |

### 38.4 Key constants

- `BUILTIN_LIGHTING_ROLES = frozenset({"key", "fill", "rim", "bounce", "practical", "motivated", "atmospheric", "volumetric"})`
- `BUILTIN_MOODS = frozenset({"hopeful", "dramatic", "tense", "dangerous", "mystical", "industrial", "clinical", "cinematic"})`
- `HIERARCHY_ROLES = frozenset({"hero", "support", "background", "atmosphere"})`
- `LIGHTING_SCHEMA_VERSION = "1.0.0"`
- Review score weights: `readability=0.20, mood_accuracy=0.20, story_support=0.20, visual_hierarchy=0.15, color_harmony=0.15, exposure_quality=0.10`
- `production_ready` requires `overall_score >= 0.70` AND no blocking findings

### 38.5 Lighting review grade mapping

| Score | Grade | production_ready |
|---|---|---|
| ≥ 0.85 | A | ✓ |
| ≥ 0.70 | B | ✓ |
| ≥ 0.55 | C | ✗ |
| ≥ 0.40 | D | ✗ |
| < 0.40 | F | ✗ |

Blocking findings contain keywords: `"no key light"`, `"no lighting defined"`, `"empty plan"`, `"no light sources"`, `"zero lights"`.

### 38.6 Lighting Intelligence Rules

1. Lighting exists to support story — every light must have a narrative justification.
2. Readability is more important than complexity.
3. Mood drives illumination decisions — infer mood from intent before building any plan.
4. Visual hierarchy must be preserved — hero subjects get maximum rim + dedicated key targeting.
5. Use production memory when available — pattern library captures proven setups.
6. Prefer deterministic planning — same intent always produces the same plan.
7. Generate plans, not renderer nodes — all outputs are renderer-agnostic dicts.
8. Never create Houdini lights directly — plans are for downstream realization.
9. Always review — call `hou_mcp_lighting_review` after plan generation.
10. Color temperature tells a story — warm = safety/intimacy; cool = threat/technology.
11. Contrast ratio controls emotional weight — high for drama/danger; low for clinical/hopeful.
12. Volumetrics add narrative depth — use only when environment warrants it.

### 38.7 Test conventions

- Reset ALL singletons in `autouse` fixture (16 singletons for full plan tests)
- No Houdini dependency, no renderer dependency, no internet
- Plan builder tests reset: builder + strategy + mood + env mapper + patterns + color + exposure + hierarchy + knowledge
- Review tests reset: review + readability + mood + color + exposure
- No mocked environments needed — builtin patterns + profiles cover all test scenarios
- 16 test files in `tests/unit/`: `test_lighting_knowledge.py`, `test_lighting_language.py`, `test_lighting_patterns.py`, `test_lighting_environment_mapper.py`, `test_lighting_mood_engine.py`, `test_lighting_readability_engine.py`, `test_lighting_hierarchy_engine.py`, `test_lighting_color_engine.py`, `test_lighting_exposure_engine.py`, `test_lighting_strategy_engine.py`, `test_lighting_recommendation_engine.py`, `test_lighting_plan_builder.py`, `test_lighting_review.py`, `test_lighting_statistics.py`, `test_lighting_serializer.py`, `test_lighting_validation.py`

---

## 39. Environment Expansion Pack (§39)

Vibrante now supports 55 production environments across 9 categories. All environment-aware systems are automatically integrated.

### 39.1 Environment categories and names

| Category | Environments |
|---|---|
| Industrial (8) | industrial_hangar, abandoned_factory, warehouse, shipyard, oil_refinery, power_station, mining_facility, construction_site |
| Scientific (6) | robotics_lab, research_lab, medical_lab, clean_room, biohazard_facility, control_room |
| Military (5) | military_base, command_center, military_hangar, checkpoint, bunker |
| Sci-Fi (6) | sci_fi_corridor, space_station, spaceship_bridge, engineering_bay, alien_facility, cyberpunk_city |
| Urban (6) | city_street, alleyway, subway_station, parking_garage, rooftop, shopping_mall |
| Interior (8) | western_room, saloon, living_room, office, hotel_lobby, restaurant, workshop, library |
| Nature (7) | forest, jungle, desert, canyon, mountain, coastline, swamp |
| Fantasy (5) | castle_hall, dungeon, wizard_tower, ancient_ruins, temple |
| Post-Apocalyptic (4) | abandoned_city, destroyed_highway, ruined_industrial_site, survival_camp |

### 39.2 New module: `src/runtime/environments/`

```
src/runtime/environments/
    __init__.py                  ← full re-export of public surface
    environment_registry.py      ← EnvironmentDefinition + EnvironmentRegistry (55 built-ins)
    environment_statistics.py    ← EnvironmentStatRecord + EnvironmentStatistics (capped at 2000)
```

**EnvironmentDefinition** fields: `name, category, description, keywords, asset_categories, hero_asset_types, support_asset_types, storytelling_tags, lookdev_tags, lighting_tags, camera_tags, atmosphere_tags`

**EnvironmentRegistry** methods: `register_environment(), get_environment(), list_environments(), search_environments(), get_by_category(), get_statistics()`

**EnvironmentStatistics** methods: `record_usage(), record_success(), record_failure(), record_review(), record_lighting_pattern(), usage_count(), success_rate(), review_average(), asset_count_average(), lighting_pattern_usage(), top_environments(), summary()`

Singleton pattern: `get_environment_registry()` / `reset_environment_registry_for_tests()`, `get_environment_statistics()` / `reset_environment_statistics_for_tests()`

### 39.3 Updated systems

| System | Change |
|---|---|
| `asset_environment_mapper.py` | `BUILTIN_ENVIRONMENTS` expanded from 5 → 55 with full `_ENV_KEYWORDS` and `_CATEGORY_ENV_AFFINITY` for all new environments |
| `intent_parser.py` | `_ENV_ALIASES` and `_ENV_SINGLE_HINTS` expanded to cover all 55 environments |
| `lighting_patterns.py` | 8 new builtin patterns added: western_room, space_station, forest, military_base, cyberpunk_city, castle_hall, desert, survival_camp |
| `lighting_environment_mapper.py` | All 55 environments have lighting profiles; `_ENV_ALIASES` covers all new names |
| `placement_templates.py` | 7 new builtin templates: warehouse, space_station, western_room, forest, military_base, castle_hall, survival_camp |
| `storytelling_layout_engine.py` | All 55 environments have `_ENV_NARRATIVES` entries with theme, beats, viewer_path, visual_flow |
| `workflow_pack.py` | `VALID_ENVIRONMENT_TYPES` expanded to 55; 8 new builtin packs (total 13) |
| `capability_registry.py` | 5 new capabilities: environment_registry, environment_expansion, environment_statistics, environment_recommendation, environment_workflow_pack |

### 39.4 New builtin workflow packs (§39)

`western_room_pack`, `space_station_pack`, `research_lab_pack`, `forest_pack`, `city_street_pack`, `castle_hall_pack`, `military_base_pack`, `survival_camp_pack`

### 39.5 Keyword inference examples

| Intent text | Resolved environment |
|---|---|
| "cowboy saloon western" | western_room / saloon |
| "space station orbital module" | space_station |
| "military barracks tactical base" | military_base |
| "deep forest woodland trees" | forest |
| "medieval castle hall throne" | castle_hall |
| "post apocalyptic survival camp fire" | survival_camp |
| "cyberpunk neon rain city" | cyberpunk_city |
| "dungeon chain torch dark" | dungeon |

### 39.6 Lighting integration

Each new environment has a dedicated lighting profile in `lighting_environment_mapper.py` specifying: `recommended_sources`, `volumetrics`, `exposure_ev`, `contrast`, `mood_hints`, `color_temperature`, `notes`.

Key lighting characteristics:
- **western_room / saloon**: warm, lantern practical, low contrast
- **space_station / clean_room / medical_lab**: cool, clinical, low contrast
- **forest / jungle / swamp**: volumetric, green-filtered, nature diffuse
- **dungeon / bunker**: extreme low EV (< −2), single source, high contrast
- **cyberpunk_city**: neon competing keys, heavy volumetric, cool
- **desert**: high EV (+1.5), harsh overhead, warm bleached

### 39.7 Storytelling integration

Every environment in `_ENV_NARRATIVES` defines: `theme`, `hero_beat`, `support_beat`, `atmosphere_beat`, `viewer_path`, `visual_flow`.

Visual flow patterns across new environments:
- **grid**: warehouse, research_lab, clean_room, office, library, robotics_lab
- **linear**: city_street, alleyway, subway_station, destroyed_highway, sci_fi_corridor
- **convergent**: castle_hall, command_center, medical_lab, temple, control_room
- **upward**: shipyard, oil_refinery, construction_site, mountain, hotel_lobby
- **exploratory**: forest, jungle, swamp, ancient_ruins, abandoned_city
- **centrifugal**: industrial_hangar, western_room, cyberpunk_city, survival_camp

### 39.8 Test conventions

- Reset all singletons in `autouse` fixture (registry + statistics + mapper + intent_parser + lighting + capability + workflow)
- 5 test files: `test_environment_registry.py`, `test_environment_statistics.py`, `test_environment_expansion.py`, `test_environment_workflow_packs.py`, `test_environment_mapper_expansion.py`
- No network calls, no Houdini, no randomness
- All 55 environments covered in mapper keyword tests

---

## 40. Real Asset Spatial Intelligence (Tier 9.4)

Tier 9.4 upgrades the Environment Construction layer to be fully aware of real asset dimensions, bounding boxes, world scale, footprint, collision avoidance, semantic placement relationships, walkable space, and clearance rules. Fixes the placeholder-cube assumption that caused chairs inside tables, buckets inside chairs, and machines intersecting hero assets.

**Non-negotiable design rules:**
1. No bridge calls. All modules are planning/advisory only. Never import or call `get_bridge()`.
2. No randomness. Same input always produces the same output.
3. collision_count > 0 → production_ready = False (hard rule).
4. Never raises in public methods — errors in result dicts.
5. Singleton pattern — every module has `get_X()` and `reset_X_for_tests()`.
6. Use `threading.Lock` for thread safety.
7. `dataclass` + `to_dict()` / `from_dict()` pattern for all models.

### 40.1 Module layout

```
src/runtime/assets/assembly/   (new files added to existing Tier 9 assembly dir)
    spatial_metadata.py              ← SpatialMetadata (bbox, footprint, placement_type)
    bounding_box_extractor.py        ← BBoxExtractor (estimate dims from metadata)
    collision_detector.py            ← CollisionDetector (AABB)
    clearance_validator.py           ← ClearanceValidator (edge-to-edge clearance rules)
    placement_optimizer.py           ← PlacementOptimizer (find collision-free positions)
    semantic_placement_rules.py      ← SemanticPlacementRules (table→chair, bucket→wall)
    spatial_review.py                ← SpatialReview (5-dimension quality evaluation)
```

**Updated existing files:**
- `asset_placement_engine.py` — now builds SpatialMetadata for every asset, runs PlacementOptimizer, reports collision_count + clearance_violations on PlacementPlan
- `environment_review.py` — EnvironmentReviewResult gains collision_count / clearance_violations fields; collision_count > 0 blocks production_ready
- `__init__.py` — exports all 7 new modules

### 40.2 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_spatial_metadata` | Extract/build SpatialMetadata for an asset |
| `hou_mcp_collision_review` | Detect all AABB collisions in a placement plan |
| `hou_mcp_clearance_validator` | Validate minimum clearance between asset pairs |
| `hou_mcp_layout_optimizer` | Resolve collisions and optimize placement positions |
| `hou_mcp_spatial_debug` | Display bbox, footprint, radius, zone, position, collision status |

**Canonical workflow:** `hou_mcp_spatial_metadata` → `hou_mcp_layout_optimizer` → `hou_mcp_collision_review` → `hou_mcp_clearance_validator` → `hou_mcp_spatial_debug`

### 40.3 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `spatial_metadata` | Bounding box extraction and scale normalization |
| `collision_detection` | AABB-based collision detection |
| `layout_optimization` | Collision-free position search |
| `semantic_placement` | Semantic zone and anchor placement rules |
| `clearance_validation` | Minimum separation distance enforcement |
| `spatial_review` | 5-dimension spatial quality evaluation |

### 40.4 SpatialMetadata fields

| Field | Type | Description |
|---|---|---|
| `asset_id` | str | Asset identifier |
| `bbox_x` | float | Width in meters |
| `bbox_y` | float | Height in meters |
| `bbox_z` | float | Depth in meters |
| `footprint_area` | float | bbox_x × bbox_z |
| `placement_radius` | float | max(bbox_x, bbox_z) / 2.0 |
| `world_scale` | float | Applied uniform scale |
| `unit_system` | str | meters / centimeters / millimeters / inches / feet |
| `placement_type` | str | table / chair / machine / vehicle / terrain / etc. |
| `anchor_capable` | bool | Can support child assets |
| `walkable_obstacle` | bool | Blocks walkable floor space |

### 40.5 Dimension priority chain

```
BBoxExtractor.extract_bbox(asset):
  1. Explicit bbox_x/bbox_y/bbox_z fields in asset metadata
  2. Placement-type defaults (table → 2.2 × 0.8 × 1.3 m, machine → 2.5 × 2.0 × 2.0 m)
  3. Category defaults (furniture → 1.0 × 0.9 × 0.6 m, vehicle → 4.5 × 2.0 × 2.2 m)
  4. Generic fallback (1.0 × 1.0 × 1.0 m)
```

### 40.6 Clearance rules (edge-to-edge, meters)

| Type A | Type B | Minimum clearance |
|---|---|---|
| chair | chair | 0.4 m |
| machine | machine | 2.0 m |
| machine | wall | 1.0 m |
| machine | door | 1.5 m |
| vehicle | vehicle | 2.5 m |
| vehicle | wall | 1.0 m |
| vehicle | machine | 2.0 m |
| crane | crane | 5.0 m |
| table | table | 1.0 m |
| any | any | 0.3 m (default) |

### 40.7 Semantic placement rules

| Type | Is anchor | Supports | Preferred zones |
|---|---|---|---|
| table | ✓ | chair, stool, bucket, lantern | hero_zone, midground |
| chair | — | — (anchors to table) | hero_zone, midground |
| machine | ✓ | pipe, electronic, bucket | hero_zone, midground |
| crane | ✓ | pipe | hero_zone |
| bucket | — | — | service_area, background, wall zones |
| lantern | — | — | hero_zone, midground, wall zones |
| vehicle | — | — | hero_zone |
| terrain | ✓ | table, chair, machine, vehicle, barrel | background |

### 40.8 PlacementOptimizer algorithm

```
find_valid_position(proposed_pos, meta, placed):
  1. Try original slot position (attempt 1)
  2. Expand search: for radius in [0.5, 1.0, 1.5, 2.0, 3.0, 4.0] m:
       for angle in [0°, 90°, 180°, 270°, 45°, 135°, 225°, 315°]:
           candidate = (px + r·cos(θ), py, pz + r·sin(θ))
           if collision-free AND clearance-met: accept
  3. If no valid position found: keep original, log warning
```

### 40.9 Spatial review grade mapping

| Score | Grade | production_ready |
|---|---|---|
| ≥ 0.90 | A | ✓ |
| ≥ 0.80 | B | ✓ |
| ≥ 0.70 | C | ✓ |
| ≥ 0.55 | D | ✗ |
| < 0.55 | F | ✗ |

**Hard rule**: `collision_count > 0` → `production_ready = False` regardless of score.

Score dimensions: `collision(0.35) + clearance(0.25) + semantic(0.20) + walkability(0.20)`

### 40.10 AssetPlacementEngine integration

`PlacementPlan` gains:
- `collision_count: int` — collisions remaining after optimization
- `clearance_violations: int` — clearance violations remaining
- `spatial_optimized: bool` — True if optimizer was run

`AssetPlacement` gains:
- `spatial_metadata: Optional[Dict]` — the SpatialMetadata for the placed asset

`EnvironmentReviewResult` gains:
- `collision_count`, `clearance_violations`, `semantic_placement_score`, `walkability_score`, `layout_quality_score`
- `evaluate_environment()` now accepts `placement_plan` parameter and surfaces spatial violations

### 40.11 Test conventions

- Reset ALL singletons in `autouse` fixture (7 spatial singletons + collision_detector + clearance_validator)
- Use deterministic asset inputs (no RNG)
- Test overlapping asset cases (chairs at same position → collision detected)
- Test large asset cases (machine + machine at 3m apart → clearance violation)
- No network calls, no Houdini dependency
- 7 test files in `tests/unit/`: `test_spatial_metadata.py`, `test_bbox_extractor.py`, `test_collision_detector.py`, `test_clearance_validator.py`, `test_semantic_placement_rules.py`, `test_layout_optimizer.py`, `test_spatial_review.py`

---

## 41. Structural Environment Assembly (Tier 9.5)

Tier 9.5 upgrades environment construction from "asset scattering" to true structural assembly. The system builds a complete environment scaffold (floor, walls, columns, doors) before placing any asset, then assigns anchors, support props, and decorative dressing relative to that structure rather than the world origin.

**Non-negotiable design rules:**
1. No bridge calls. All modules are planning/advisory only.
2. No randomness. Same input always produces the same output.
3. Structure-first: environment structure must be built before any asset is placed.
4. Never raises in public methods — errors captured in result dicts.
5. Singleton pattern — every module has `get_X()` and `reset_X_for_tests()`.
6. `dataclass` + `to_dict()` / `from_dict()` pattern for all models.
7. Review is specific — never returns a generic "success" message.

### 41.1 Module layout

```
src/runtime/assets/assembly/   (new files added to existing Tier 9 assembly dir)
    environment_blueprint.py          ← EnvironmentBlueprint (structural requirements)
    environment_zones.py              ← ZONE_TYPES, StructuralZone, BUILTIN_ZONE_DEFINITIONS
    architectural_templates.py        ← ArchitecturalTemplates (21 environments)
    environment_structure_builder.py  ← StructuralElement + EnvironmentStructure + EnvironmentStructureBuilder
    anchor_asset_engine.py            ← AnchorAsset + AnchorPlan + AnchorAssetEngine + SEMANTIC_RELATIONSHIPS
    decorative_population_engine.py   ← DecorativeItem + DecorationPlan + DecorativePopulationEngine
    environment_completeness_review.py ← EnvironmentCompletenessReview + EnvironmentCompletenessReviewer
```

**Houdini debug node:**
```
plugins/houdini/v_nodes_houdini/hou_mcp_environment_debug.json
```

### 41.2 Structure-First execution order (mandatory)

1. `EnvironmentStructureBuilder.build_structure()` — floor, walls, columns, structural elements
2. Validate completeness (missing_required checked automatically)
3. `AnchorAssetEngine.get_anchor_plan()` — major focal elements assigned to zones
4. `ScenePopulationEngine` / `AssetPlacementEngine` — assets placed relative to structure and anchors
5. `DecorativePopulationEngine.get_decoration_plan()` — small props on/near anchors
6. Atmosphere added via lighting and placement layers
7. `EnvironmentCompletenessReviewer.review()` — final completeness check

Assets may **not** be placed before the structure exists.

### 41.3 EnvironmentBlueprint fields

| Field | Type | Description |
|---|---|---|
| `floor_required` | bool | Floor must exist |
| `wall_required` | bool | Perimeter walls must exist |
| `ceiling_required` | bool | Ceiling must exist |
| `door_required` | bool | At least one door/entrance required |
| `window_required` | bool | At least one window/viewport required |
| `structural_assets` | List[str] | Element types defining the structure |
| `anchor_assets` | List[str] | Major focal element types |
| `support_assets` | List[str] | Secondary prop types |
| `decorative_assets` | List[str] | Small dressing prop types |
| `atmosphere_assets` | List[str] | Lighting/volumetric element types |
| `structural_optional` | List[str] | Nice-to-have structural elements |
| `zone_order` | List[str] | Zone population execution order |

### 41.4 Supported environments (21 built-in templates)

| Category | Environments |
|---|---|
| Interior | western_room, saloon, living_room, office, hotel_lobby, restaurant, library |
| Industrial | industrial_hangar, warehouse, abandoned_factory |
| Scientific | robotics_lab, research_lab, medical_lab, control_room |
| Sci-Fi | sci_fi_corridor, space_station |
| Outdoor | city_street, forest, desert |
| Fantasy | castle_hall, survival_camp, dungeon |

Unknown environments get a generic fallback blueprint (`floor_required=True`, `wall_required=True`).

### 41.5 Zone types (6 canonical zones)

| Zone type | Role | Position hint |
|---|---|---|
| `entrance_zone` | Viewer entry / camera approach | foreground |
| `hero_zone` | Primary focal point — major anchors | center |
| `support_zone` | Secondary context assets | midground / perimeter |
| `decoration_zone` | Small props and surface dressing | scattered |
| `atmosphere_zone` | Lighting, volumetrics, HDRI | ceiling / perimeter |
| `background_zone` | Distant architectural fills | background |

### 41.6 Anchor asset semantic relationships

```python
SEMANTIC_RELATIONSHIPS = {
    "chair":    {"belongs_near": ["table", "bar_counter", "desk"], "belongs_on": [], ...},
    "cup":      {"belongs_near": [], "belongs_on": ["table", "bar_counter", "desk"], ...},
    "bucket":   {"belongs_near": ["wall", "corner"], "belongs_on": [], ...},
    "lantern":  {"belongs_near": [], "belongs_on": ["table", "wall", "ceiling"], ...},
    ...
}
```

`AnchorAssetEngine.get_semantic_relationship(asset_type)` returns the full relationship dict.
`AnchorAssetEngine.get_children_for_anchor(env, anchor_type)` returns the child types that belong near/on that anchor.

### 41.7 Decorative placement targets

`on_table`, `near_wall`, `corner`, `ceiling`, `floor`, `on_shelf`, `near_anchor`, `scattered`, `wall_mounted`, `ceiling_mounted`

All decorative items have a `placement_target` (how to place) and optionally a `parent_anchor` (what anchor they relate to).

### 41.8 Completeness review dimensions and weights

| Dimension | Weight | Blocks production if |
|---|---|---|
| structure | 0.35 | floor/wall missing |
| anchor | 0.25 | no anchors defined |
| zones | 0.15 | no zones defined |
| support | 0.10 | — |
| decoration | 0.10 | — |
| atmosphere | 0.05 | — |

**Grade mapping:**

| Score | Grade | production_ready |
|---|---|---|
| ≥ 0.85 | A | ✓ |
| ≥ 0.70 | B | ✓ |
| ≥ 0.55 | C | ✗ |
| ≥ 0.40 | D | ✗ |
| < 0.40 | F | ✗ |

**Blocking findings** (block `production_ready` regardless of score):
- `"floor missing"` — floor required but no floor element in structural_assets
- `"wall missing"` — walls required but no wall element in structural_assets
- `"required structure missing"` — other required element absent
- `"anchor asset missing"` — no anchor assets in the anchor plan
- `"no zones"` — no structural zones defined

### 41.9 Debug node

`hou_mcp_environment_debug` logs a complete environment report to the Vibrante-Node log panel:

```
--------------------------------------------------
ENVIRONMENT STRUCTURE: western_room
  floor_required: True  wall_required: True
  Structural elements (4):
    [floor] @ entire_floor_plane
    [wall]  @ four_perimeter_walls
    ...
ZONES (6):
  [hero_zone] Main Table Area — max 5 assets [REQUIRED]
  ...
ANCHOR ASSETS (3):
  PRIMARY: table in hero_zone
           Main dining table — chairs gather around it
           Supports: ['chair', 'cup', 'bottle', 'lantern']
  bar_counter in support_zone @ background
  ...
DECORATIVE ITEMS (8 types, 31 total):
  x4 cup [on_table] (on/near table) → hero_zone
  x3 bottle [on_table] (on/near table) → hero_zone
  ...
COMPLETENESS REVIEW:
  Structure:   1.00   Anchor: 1.00   Zones: 1.00
  Support:     1.00   Decoration: 1.00  Atmosphere: 1.00
  Overall:     1.00   Grade: A   Production: YES
--------------------------------------------------
```

Outputs: `structure_json`, `anchor_json`, `decoration_json`, `review_json`, `production_ready`.

### 41.10 Test conventions

- Reset ALL singletons in `autouse` fixture (builder + templates + anchor + deco + reviewer)
- All tests deterministic — no RNG, no network, no Houdini dependency
- Test all 21 environments for structural completeness and production_ready
- Test blocking-finding conditions explicitly (empty anchors, empty zones)
- 6 test files in `tests/unit/`: `test_environment_blueprint.py`, `test_architectural_templates.py`, `test_environment_structure_builder.py`, `test_anchor_asset_engine.py`, `test_decorative_population.py`, `test_environment_completeness_review.py`

---

## 42. Scale-Aware Spatial Placement (Tier 9.6)

Tier 9.6 fixes the root cause of scene overlap and invalid layouts when using real Megascans/Fab assets. Assets are imported in centimeter space; the placement engine was using meter-space offsets with fixed index-based spacing, making every chair 48.9 m wide and every item placed 3 m apart regardless of size.

**Root causes fixed:**
1. Assets imported in cm space, placement in meter space → 100× size error
2. Fixed slot overflow: `tx = index × 3.0 m` ignores asset size
3. Structural assets (beam, wall, column) treated as furniture
4. No semantic clustering (chairs around tables, buckets in corners)

### 42.1 Module layout

```
src/runtime/assets/assembly/   (new files in existing Tier 9 assembly dir)
    unit_normalizer.py          ← UnitNormalizer — cm/mm/m/in/ft → meters
    asset_scale_analyzer.py     ← AssetScaleProfile + AssetScaleAnalyzer (5 scale classes)
    footprint_calculator.py     ← FootprintResult + FootprintCalculator
    layout_spacing_engine.py    ← SpacedPosition + LayoutSpacingEngine
    placement_relationships.py  ← PlacementRelationship + PlacementRelationships
```

**Updated files:**
- `bounding_box_extractor.py` — `extract_bbox` now calls `UnitNormalizer.detect_unit()` + `normalize_bbox()` for explicit bbox fields (fixes cm→m conversion)
- `asset_placement_engine.py` — 7-step pipeline; each placement tagged with `scale_class`, `role`, `is_structural`; overflow spacing uses `_scale_aware_step()` instead of fixed 3.0 m

**Houdini debug node:** `hou_mcp_layout_debug.json`

### 42.2 Unit normalization

`UnitNormalizer` recognises all common unit spellings and converts to meters:

| Input | Factor | Example |
|---|---|---|
| cm / centimeters | 0.01 | 48.9 cm → 0.489 m |
| mm / millimeters | 0.001 | 489 mm → 0.489 m |
| m / meters | 1.0 | 1.5 m → 1.5 m |
| in / inch | 0.0254 | 12 in → 0.305 m |
| ft / feet | 0.3048 | 3 ft → 0.914 m |

**Detection priority:**
1. Explicit field: `unit`, `unit_system`, `units`, `bbox_unit`, `source_unit`
2. Heuristic: if any bbox dimension > 10 → assume centimeters
3. Default: meters

### 42.3 Scale classes

| Class | max_dim | Examples |
|---|---|---|
| tiny | < 0.15 m | cup, bottle, book |
| small | < 0.50 m | bucket, stool, lantern |
| medium | < 1.50 m | chair (0.84 m), table (0.70 m) |
| large | < 4.00 m | large machine, vehicle |
| structural | ≥ 4.00 m OR type/category override | beam (3.777 m via category), wall, column |

Structural override rules (category or placement_type wins regardless of size):
- `placement_type` in `{wall, column, platform, crane, terrain, beam, roof, support_column, support_beam}`
- `category` in `{structure, architectural, terrain}`

### 42.4 Layout spacing formula

Replace: `tx = index * 3.0` (fixed, ignores size)

With: `spacing = radius_a + clearance_margin + radius_b`

Clearance margins by scale class pair:

| Pair | Margin |
|---|---|
| tiny ↔ tiny | 0.05 m |
| small ↔ medium | 0.12 m |
| medium ↔ medium | 0.20 m |
| large ↔ large | 0.35 m |

**Overflow fallback** (replaces fixed 2.0/3.0 m constants):
```python
step = max(0.8, min(3.0, zone_width / 4.0))
```

### 42.5 Structural asset routing

Assets with `role="structure"` or `placement_mode="route_to_structure"` must go to `EnvironmentStructureBuilder`, not the furniture placement pipeline.

`PlacementRelationships.filter_structural(assets)` → returns `(placeable, structural)`.

Structural keyword hints in asset names: `beam`, `wall`, `column`, `roof`, `pillar`, `rafter`, `truss`, `catwalk`, etc.

### 42.6 Semantic placement modes

| Mode | Examples |
|---|---|
| `around_anchor` | chair (around table), stool (around bar_counter) |
| `near_wall` | bench, server_rack, filing_cabinet |
| `corner` | bucket, barrel, plant |
| `wall_only` | door, window, poster, torch |
| `ceiling_mounted` | hanging light, overhead hazard sign |
| `hero_center` | table, desk, console, main machine |
| `route_to_structure` | beam, wall, column, floor, roof |
| `scattered` | generic props, fallback |

### 42.7 7-step placement pipeline (AssetPlacementEngine)

Each asset now goes through:
1. **Analyze scale** — `UnitNormalizer.detect_unit()` + `AssetScaleAnalyzer.analyze_asset()` → `AssetScaleProfile`
2. **Calculate footprint** — `FootprintCalculator.calculate(asset)` → `FootprintResult`
3. **Select semantic zone** — EnvironmentBuilder zones (existing)
4. **Compute valid position** — template slot or scale-aware overflow via `_scale_aware_step()`
5. **Validate spacing** — `PlacementOptimizer` (existing Tier 9.4)
6. **Validate collisions** — `CollisionDetector` (existing Tier 9.4)
7. **Commit placement** — `AssetPlacement` now carries `scale_class`, `role`, `is_structural`

Structural assets get a `plan.warnings` entry directing routing to `EnvironmentStructureBuilder`.

### 42.8 hou_mcp_layout_debug node

Input: `assets_json` (list), `environment_name`

Logs per asset:
```
Asset:    Wooden Chair
  Role:          seating
  Scale class:   medium
  Source unit:   cm
  BBox (meters): 0.489 x 0.838 x 0.433 m
  Footprint:     0.212 m²
  Radius:        0.244 m
  Placement mode:around_anchor
  Position:      (-0.37, 0.0, 0.0)

Asset:    Old Wooden Beam
  Role:          structure
  Scale class:   structural
  ...
  STRUCTURAL → route to EnvironmentStructureBuilder
```

Outputs: `layout_report_json`, `structural_count`.

### 42.9 Test conventions

- Reset ALL singletons in `autouse` fixture (normalizer + analyzer + calculator + spacing + relationships + bbox_extractor)
- Always test with real Megascans cm values (48.9, 83.8, 43.3 cm)
- Test that chair/table do NOT overlap after normalization
- Test that beam is excluded from furniture placement
- No network calls, no Houdini, no randomness
- 6 test files in `tests/unit/`: `test_unit_normalizer.py`, `test_scale_analyzer.py`, `test_footprint_calculator.py`, `test_layout_spacing_engine.py`, `test_role_based_placement.py`, `test_scale_aware_layout.py`

---

## 43. Geometry Intelligence & Asset Metrics (Tier 9.7)

Tier 9.7 introduces a Geometry Intelligence layer that becomes the authoritative source for all asset physical characteristics. It replaces dimension estimates with a structured analysis pipeline: bounding box extraction → pivot detection → ground contact detection → support surface detection → scale classification → role validation → geometry review.

**Non-negotiable design rules:**
1. No bridge calls. All modules are planning/advisory only. Never import or call `get_bridge()`.
2. No randomness. Same asset metadata dict → same result.
3. Never raises in public methods — errors captured in result dicts.
4. Singleton pattern — every module has `get_X()` + `reset_X_for_tests()`.
5. Thread-safe (`threading.Lock` per instance).
6. `dataclass` + `to_dict()` / `from_dict()` pattern for all models.
7. No placement may occur without Geometry Intelligence — placement engines must call GeometryAnalyzer if metrics are absent.

### 43.1 Module layout

```
src/runtime/assets/geometry/
    __init__.py                    ← full re-export of all public surface
    asset_metrics.py               ← SupportSurface + GroundContact + AssetMetrics + AssetMetricsBuilder
    bounding_box_extractor.py      ← GeometryBBoxExtractor (10-step priority chain)
    pivot_detector.py              ← PivotDetector (5 pivot types)
    ground_contact_detector.py     ← GroundContactDetector (leg/base_ring/base_plane/wheel/skid/track)
    support_surface_detector.py    ← SupportSurfaceDetector (tabletop/shelf/worktop/rack_unit)
    geometry_analyzer.py           ← GeometryAnalysisResult + GeometryAnalyzer (main orchestrator)
    geometry_review.py             ← GeometryReviewResult + GeometryReview (5-dimension scoring)
    geometry_serializer.py         ← GeometrySerializer (sorted-key JSON, schema 1.0.0)
    geometry_statistics.py         ← GeometryStatRecord + GeometryStatistics (capped at 2000)
```

### 43.2 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_geometry_analyze` | Full geometry analysis: bbox, pivot, contacts, surfaces, scale class, role |
| `hou_mcp_geometry_metrics` | Individual metric values: volume, footprint, radius, surface_count, contact_count |
| `hou_mcp_support_surfaces` | Detect valid horizontal placement surfaces with height and area |
| `hou_mcp_geometry_review` | 5-dimension quality review: grade, score, production_ready, findings |

**Canonical workflow:** `hou_mcp_geometry_analyze` → `hou_mcp_geometry_metrics` → `hou_mcp_support_surfaces` → `hou_mcp_geometry_review`

### 43.3 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `geometry_analysis` | Full geometry intelligence pipeline from asset metadata dict |
| `pivot_detection` | Pivot position and type detection (5 types, confidence-scored) |
| `support_surface_detection` | Valid horizontal placement surface detection with area and load capacity |
| `ground_contact_detection` | Ground contact point detection (leg/ring/plane/wheel/skid/track) |
| `asset_metrics` | Comprehensive AssetMetrics dataclass — authoritative geometry source |
| `geometry_review` | 5-dimension geometry quality evaluation with role consistency checks |

### 43.4 AssetMetrics fields

| Field | Type | Description |
|---|---|---|
| `asset_id` | str | Asset identifier |
| `width_m` | float | X dimension in meters |
| `height_m` | float | Y dimension in meters (up) |
| `depth_m` | float | Z dimension in meters |
| `volume_m3` | float | width × height × depth |
| `footprint_m2` | float | width × depth |
| `placement_radius` | float | max(width, depth) / 2.0 |
| `bbox_min` | List[float] | Minimum corner [x, y, z] in object space |
| `bbox_max` | List[float] | Maximum corner [x, y, z] in object space |
| `pivot_type` | str | bottom_center / center / bottom_left / top_center / custom |
| `pivot_position` | List[float] | Pivot position in object space |
| `pivot_confidence` | float | Detection confidence (0.5–1.0) |
| `support_surfaces` | List[SupportSurface] | Valid horizontal surfaces for child placement |
| `ground_contacts` | List[GroundContact] | Floor contact points |
| `scale_class` | str | tiny/small/medium/large/structural/hero |
| `role` | str | prop/furniture/structure/vehicle/character/vegetation/hero_asset |
| `is_structural` | bool | True → route to EnvironmentStructureBuilder |
| `is_hero` | bool | True → major focal element of the scene |
| `source` | str | explicit/format_metadata/estimated |

### 43.5 Bounding box extraction priority chain (10 steps)

```
GeometryBBoxExtractor.extract(asset):
  1. Explicit bbox_min / bbox_max vectors
  2. bounding_box dict with min/max keys
  3. USD extent list [[min_x,y,z], [max_x,y,z]]
  4. aabb / mesh_bounds / world_bounds dict
  5. dimensions / size dict (width/height/depth keys)
  6. GLTF-specific bounds (gltf_bbox, gltf_bounds, gltf_extent)
  7. Scalar bbox_x / bbox_y / bbox_z fields (Tier 9.4/9.6 format)
  8. Scalar width / height / depth fields
  9. Placement-type dimension table (39 types)
 10. Category dimension table (14 categories) → generic 1×1×1 m fallback
```

Unit detection: explicit `unit` field → heuristic (any bbox dim > 10 → assume cm).

### 43.6 Scale classification (6 classes)

| Class | Condition | Examples |
|---|---|---|
| `tiny` | max_dim < 0.15 m | cup, button, small prop |
| `small` | max_dim < 0.50 m | bucket, stool, lantern |
| `medium` | max_dim < 1.50 m | chair, cabinet, barrel |
| `large` | max_dim < 4.00 m | table, bench, door, shelf |
| `structural` | max_dim ≥ 4.00 m OR placement_type in STRUCTURAL_PLACEMENT_TYPES OR category in STRUCTURAL_CATEGORIES | beam, wall, column, crane |
| `hero` | placement_type in HERO_PLACEMENT_TYPES (machine, vehicle, crane, main_prop, reactor) | machine, large_machine, vehicle |

Structural overrides hero: if placement_type is `crane`, it maps to `structural` (not `hero`) because `crane` is in both. Check STRUCTURAL_PLACEMENT_TYPES first.

### 43.7 Support surface types

| placement_type | Surfaces detected |
|---|---|
| table | tabletop at height_m |
| desk, workbench | worktop at height_m + lower_shelf if h > 0.95 m |
| counter, bar_counter | countertop at height_m + lower_shelf if h > 1.0 m |
| cabinet | top_surface + N internal shelves (1 per 0.30 m) |
| wardrobe | top_surface + upper_shelf at 55% height |
| shelf | N shelves at 0.30 m intervals |
| server_rack | rack_unit every 0.044 m (max 42U), starting at 0.12 m |
| console, display_case | worktop / top_surface + display_shelf |
| crate | top_surface (heavy capacity) |
| pallet | pallet_surface (heavy capacity) |
| chair, bucket, vehicle, machine, wall, beam | (none — not surface-providing) |

### 43.8 Ground contact types

| placement_type | contact_type | count |
|---|---|---|
| chair, table, desk, stool, bench, sofa, bed | leg | 4 |
| server_rack, rack, display_case | foot | 4 |
| barrel, bucket, column | base_ring | 8 |
| machine, large_machine, cabinet, crate, pallet, terrain | base_plane | 1 |
| vehicle, vehicle_small | wheel | 4 (2 axles) |
| crane | track | 2 |
| pallet | skid | 2 |
| hanging_light, pendant_light, sprinkler | (none — ceiling-mounted) | — |

### 43.9 Geometry review grade mapping

| Score | Grade | production_ready |
|---|---|---|
| ≥ 0.85 | A | ✓ (if no blocking findings) |
| ≥ 0.70 | B | ✓ (if no blocking findings) |
| ≥ 0.55 | C | ✗ |
| ≥ 0.40 | D | ✗ |
| < 0.40 | F | ✗ |

Score dimensions: `bbox_validity(0.30) + pivot_validity(0.20) + surface_detection(0.25) + ground_contact_detection(0.15) + scale_accuracy(0.10)`

Blocking findings contain: `"zero dimensions"`, `"no support surfaces"`, `"invalid role"`

Role consistency rules:
- Structural placement types (`wall`, `beam`, `column`, `roof`, …) → role must NOT be `"furniture"` or `"prop"`
- Furniture types (`chair`, `table`, `bench`, …) → role must NOT be `"structure"`
- `door` / `window` → role `"prop"` triggers a non-blocking warning

### 43.10 Test conventions

- Reset ALL singletons in `autouse` fixture (analyzer + builder + bbox_extractor + pivot + contacts + surfaces + review)
- No network calls, no Houdini, no randomness
- Test with real geometry values (explicit bbox_min/max) AND placement-type fallbacks
- Test cm→m unit conversion (55 cm → 0.55 m)
- Test blocking-finding conditions explicitly
- Test role consistency violations (beam with role="furniture" → invalid role)
- 7 test files in `tests/unit/`: `test_geometry_analyzer.py`, `test_bounding_box_extractor_geometry.py`, `test_pivot_detector.py`, `test_ground_contact_detector.py`, `test_support_surface_detector.py`, `test_asset_metrics.py`, `test_geometry_review.py`

---

## 44. Environment Construction Package (Tier 9.5 — src/runtime/environment/)

`src/runtime/environment/` is the higher-level environment construction layer. It provides template-driven, structure-first environment assembly with 20 built-in environment types. It works alongside `src/runtime/assets/assembly/` (Tier 9 placement) but operates at a higher level of abstraction.

**Non-negotiable design rules:**
1. No bridge calls. All modules are planning/advisory only. Never import or call `get_bridge()`.
2. No randomness. Same input always produces the same output.
3. Never raises in public methods — errors captured in result dicts.
4. Singleton pattern — every module has `get_X()` and `reset_X_for_tests()`.
5. Thread-safe (`threading.Lock` per instance).
6. `dataclass` + `to_dict()` / `from_dict()` pattern for all models.
7. Structure-first: environment structure must be built before any asset is placed.

### 44.1 Module layout

```
src/runtime/environment/
    __init__.py                      ← full re-export of all public surface
    environment_blueprint.py         ← EnvironmentBlueprint (name, category, required_structure, zones, anchors, atmosphere_profile)
    environment_template_library.py  ← 20 built-in templates + EnvironmentTemplateLibrary
    environment_requirements.py      ← RequirementsCheckResult + EnvironmentRequirements
    environment_zone_builder.py      ← EnvironmentZone + ZonePlan + EnvironmentZoneBuilder
    environment_structure_builder.py ← BuiltStructuralElement + EnvironmentStructurePlan + EnvironmentStructureBuilder
    anchor_asset_builder.py          ← PlacedAnchor + AnchorPlan + AnchorAssetBuilder
    support_asset_builder.py         ← SupportAsset + SupportPlan + SupportAssetBuilder
    decorative_population.py         ← DecorativeItem + DecorationPlan + DecorativePopulation
    atmosphere_builder.py            ← AtmosphereProfile + AtmospherePlan + AtmosphereBuilder (8 profiles)
    environment_completeness.py      ← CompletenessResult + EnvironmentCompleteness (10-dimension)
    environment_review.py            ← EnvironmentReviewResult + EnvironmentReview (6-dimension)
    environment_serializer.py        ← EnvironmentSerializer (sorted-key JSON, schema 1.0.0)
    environment_statistics.py        ← EnvironmentStatRecord + EnvironmentStatistics (capped at 2000)
```

### 44.2 20 built-in environment templates

| Category | Environments |
|---|---|
| Interior (7) | western_room, saloon, living_room, office, hotel_lobby, restaurant, library |
| Industrial (3) | warehouse, industrial_hangar, abandoned_factory |
| Scientific (4) | robotics_lab, control_room, medical_lab, research_lab |
| Sci-Fi (1) | sci_fi_corridor |
| Outdoor (3) | city_street, forest, desert |
| Fantasy (2) | castle_hall, survival_camp |

Unknown environments fall back to a generic blueprint (floor + wall required, warm_interior atmosphere).

### 44.3 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_environment_blueprint` | Get blueprint for an environment: template, atmosphere_profile, construction_order |
| `hou_mcp_environment_structure` | Build structural scaffold: floor, walls, ceiling, doors, windows, support elements |
| `hou_mcp_environment_zones` | Build canonical zone set for an environment |
| `hou_mcp_environment_complete` | Run full completeness check against all pipeline stages |
| `hou_mcp_environment_review` | 6-dimension quality review: structure/zones/anchors/support/decoration/atmosphere |
| `hou_mcp_environment_debug` | Full pipeline debug report with all stages in one node |

**Canonical workflow:** `hou_mcp_environment_blueprint` → `hou_mcp_environment_structure` → `hou_mcp_environment_zones` → (anchor/support/deco/atmosphere nodes) → `hou_mcp_environment_complete` → `hou_mcp_environment_review`

**Debug shortcut:** `hou_mcp_environment_debug` runs the entire pipeline internally and logs a formatted report.

### 44.4 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `environment_blueprints` | Template library for 20 production environment types |
| `environment_construction` | Structure-first scaffold: floor/walls/ceiling/doors/windows |
| `environment_zones` | Canonical zone construction (hero/entrance/seating/service/background) |
| `anchor_asset_placement` | Major focal anchor placement with semantic child-type relationships |
| `support_asset_placement` | Secondary prop placement relative to anchor assets |
| `decorative_population_service` | Small decorative prop population using per-environment definitions |
| `atmosphere_construction` | Volumetric and atmospheric effect planning (8 built-in profiles) |
| `environment_review` | 6-dimension environment completeness review |

### 44.5 Environment review scoring

Score weights: `structure=0.35, zones=0.15, anchors=0.25, support=0.10, decoration=0.10, atmosphere=0.05`

Grade mapping:
| Score | Grade | production_ready |
|---|---|---|
| ≥ 0.85 | A | ✓ |
| ≥ 0.70 | B | ✓ |
| ≥ 0.55 | C | ✗ |
| ≥ 0.40 | D | ✗ |
| < 0.40 | F | ✗ |

Blocking findings (block production_ready regardless of score): `"floor missing"`, `"wall missing"`, `"anchor asset missing"`, `"no zones defined"`

### 44.6 8 built-in atmosphere profiles

| Profile | Primary effect | Environments |
|---|---|---|
| `western_dust` | dust | western_room, saloon, desert |
| `industrial_haze` | haze | industrial_hangar, warehouse, abandoned_factory |
| `factory_smoke` | smoke | abandoned_factory |
| `warm_interior` | none | western_room, living_room, restaurant, hotel_lobby, castle_hall |
| `cold_interior` | none | office, control_room, robotics_lab, medical_lab, research_lab, sci_fi_corridor |
| `sunlit` | volumetric_light | city_street, desert |
| `volumetric_light` | volumetric_light | forest |
| `moonlit` | none | castle_hall, city_street |

### 44.7 Structure-first mandatory workflow

1. Select environment name
2. `EnvironmentTemplateLibrary.get_template()` → `EnvironmentBlueprint`
3. `EnvironmentStructureBuilder.build_environment()` → `EnvironmentStructurePlan`
4. `EnvironmentZoneBuilder.build_zones()` → `ZonePlan`
5. `AnchorAssetBuilder.build_anchors()` → `AnchorPlan`
6. `SupportAssetBuilder.build_support_assets()` → `SupportPlan`
7. `DecorativePopulation.populate()` → `DecorationPlan`
8. `AtmosphereBuilder.build_atmosphere()` → `AtmospherePlan`
9. `EnvironmentCompleteness.check()` → `CompletenessResult`
10. `EnvironmentReview.review()` → `EnvironmentReviewResult`

Assets may **not** be placed before the structure exists.

### 44.8 Test conventions

- Reset ALL singletons in `autouse` fixture (library + structure_builder + zone_builder + anchor + support + deco + atmosphere + completeness + review + serializer + statistics)
- No network calls, no Houdini, no randomness
- Test all 20 environments for blueprint retrieval
- Test blocking-finding conditions (no structure → "floor missing"; no anchors → "anchor asset missing")
- 10 test files in `tests/unit/`: `test_environment_blueprint.py`, `test_environment_template_library.py`, `test_environment_structure_builder.py`, `test_environment_zone_builder.py`, `test_anchor_asset_builder.py`, `test_support_asset_builder.py`, `test_decorative_population.py`, `test_atmosphere_builder.py`, `test_environment_completeness.py`, `test_environment_review.py`

---

## 45. Semantic Asset Suitability Ranking (Tier 12.85)

Tier 12.85 converts asset retrieval from semantic similarity to semantic suitability. Every candidate asset receives a suitability score based on 7 weighted affinity factors. The system selects assets because they are the most contextually appropriate — not merely semantically similar.

**Non-negotiable design rules:**
1. No bridge calls, no Houdini imports.
2. No randomness. Same input always produces the same output.
3. Never raises in public methods — errors in result dicts.
4. Singleton pattern — `get_X()` + `reset_X_for_tests()`.
5. Thread-safe (`threading.Lock` per instance).
6. `dataclass` + `to_dict()` / `from_dict()` pattern on all result classes.

### 45.1 Module layout

```
src/runtime/assets/suitability/
    __init__.py                        ← full re-export of all public surface
    environment_affinity.py            ← EnvironmentAffinity (preferred/rejected keywords per env)
    role_affinity.py                   ← RoleAffinity (exact/partial/rejected role tables)
    style_affinity.py                  ← StyleAffinity (per-env visual style keywords)
    material_affinity.py               ← MaterialAffinity (per-env material keywords)
    scale_affinity.py                  ← ScaleAffinity (6-class compatibility matrix)
    placement_affinity.py              ← PlacementAffinity (per-context accepted/rejected types)
    story_affinity.py                  ← StoryAffinity (narrative props per environment)
    asset_suitability_engine.py        ← SuitabilityRequest + AssetSuitabilityScore + SuitabilityResult + AssetSuitabilityEngine
    asset_suitability_review.py        ← SuitabilityReviewResult + AssetSuitabilityReview
    asset_suitability_statistics.py    ← AssetSuitabilityStatistics (capped at 2000)
    asset_suitability_serializer.py    ← AssetSuitabilitySerializer (sorted-key JSON, schema 1.0.0)
```

### 45.2 Suitability weights (must sum to 1.0)

| Factor | Weight | Module |
|---|---|---|
| `environment_affinity` | 0.25 | environment_affinity.py |
| `role_affinity` | 0.20 | role_affinity.py |
| `style_affinity` | 0.15 | style_affinity.py |
| `material_affinity` | 0.10 | material_affinity.py |
| `scale_affinity` | 0.10 | scale_affinity.py |
| `placement_affinity` | 0.10 | placement_affinity.py |
| `story_affinity` | 0.10 | story_affinity.py |

### 45.3 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_asset_suitability` | Score a batch of candidates; outputs scores_json + best_asset_name + best_score |
| `hou_mcp_asset_ranking` | Rank and select best candidate with full log breakdown |
| `hou_mcp_asset_selection_report` | Full debug report: all candidate scores + review grade + findings |
| `hou_mcp_environment_affinity` | Inspect preferred/rejected keywords and score for a single asset/env pair |

**Canonical workflow:** upstream retrieval → `hou_mcp_asset_ranking` → `hou_mcp_asset_selection_report`

### 45.4 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `asset_suitability_ranking` | 7-factor suitability scoring replacing semantic similarity |
| `environment_affinity` | Keyword-based environment affinity (preferred/rejected tables) |
| `style_affinity` | Visual style affinity per environment |
| `role_affinity` | Asset role slot matching with exact/partial/rejected tables |
| `material_affinity` | Material composition affinity per environment |
| `story_affinity` | Narrative prop scoring — canonical story assets per environment |
| `asset_selection_validation` | Validate selected asset against requested role and environment |

### 45.5 Scoring algorithm

Each affinity module uses text extracted from the asset dict (name, category, type, tags, style_tags, material_tags, environment_tags, description). Score formula:

```
base = 0.5
base += min(0.5, preferred_hits * 0.10)  # each preferred keyword +0.10
base -= min(0.5, rejected_hits * 0.15)   # each rejected keyword -0.15
return clamp(base, 0.0, 1.0)
```

Explicit `environment_tags` match → return 1.0 immediately (strongest signal).
Role exact match (type in _ROLE_EXACT) → 1.0. Role rejected → 0.0–0.3. Role partial → 0.5–0.75.

### 45.6 Review grade mapping

| Score | Grade | production_ready |
|---|---|---|
| ≥ 0.85 | A | ✓ |
| ≥ 0.70 | B | ✓ |
| ≥ 0.55 | C | ✗ |
| ≥ 0.40 | D | ✗ |
| < 0.40 | F | ✗ |

---

## 51. Environment Shell Construction (Tier 10.4)

Tier 10.4 introduces an Environment-First Architecture. No asset (furniture, prop, decoration) may be placed until the environment shell is fully constructed and the readiness gate passes. This fixes the root cause of assets floating in empty space: doors without walls, beams without ceilings, furniture before rooms exist.

**Non-negotiable design rules:**
1. No bridge calls. All modules are planning/advisory only.
2. No randomness. Same environment always produces the same EnvironmentShell.
3. Never raises in public methods — errors in result dicts.
4. Singleton pattern — every module has `get_X()` and `reset_X_for_tests()`.
5. Thread-safe throughout.
6. `dataclass` + `to_dict()` / `from_dict()` pattern on all models.
7. **Structure-First**: environment shell must be built before any asset placement. `environment_ready = False` is a BLOCKING gate — not a warning.

### 51.1 Module layout

```
src/runtime/environment_shell/
    __init__.py                           ← full re-export of all public surface
    environment_shell_blueprint.py        ← EnvironmentShellBlueprint + EnvironmentShellBlueprintFactory
    shell_phase_result.py                 ← ShellPhaseResult + all phase status constants
    shell_floor_builder.py                ← Phase 1: floor construction
    shell_wall_builder.py                 ← Phase 2: wall construction (N/S/E/W)
    shell_ceiling_builder.py              ← Phase 3: ceiling construction
    structural_anchor_generator.py        ← Phase 4: door/window/beam/column/fireplace anchors
    structural_element_placer.py          ← Phase 5: attach structural assets to anchors
    shell_validator.py                    ← Phase 6: validate completed shell
    environment_shell_state.py            ← EnvironmentShell dataclass (accumulates all phases)
    environment_readiness_gate.py         ← ENVIRONMENT_NOT_READY gate + BLOCKED_SYSTEMS
    environment_shell_audit.py            ← ShellAudit (environment_valid + production_ready)
    environment_shell_builder.py          ← EnvironmentShellBuilder (main orchestrator)
    shell_review.py                       ← ShellReviewResult + ShellReview (6-dimension scoring)
    shell_statistics.py                   ← ShellStatistics (in-memory, capped at 2000)
    shell_serializer.py                   ← ShellSerializer (sorted-key JSON, schema 1.0.0)
```

### 51.2 Phase status constants

| Constant | Phase |
|---|---|
| `FLOOR_CONSTRUCTION_COMPLETE` | Phase 1 done |
| `WALL_CONSTRUCTION_COMPLETE` | Phase 2 done |
| `CEILING_CONSTRUCTION_COMPLETE` | Phase 3 done |
| `STRUCTURAL_ANCHORS_READY` | Phase 4 done |
| `STRUCTURAL_PLACEMENT_COMPLETE` | Phase 5 done |
| `ENVIRONMENT_VALIDATION_COMPLETE` | Phase 6 done |
| `ENVIRONMENT_READY` | Gate passed |
| `ENVIRONMENT_NOT_READY` | Gate failed — BLOCKING |

### 51.3 Pipeline (EnvironmentShellBuilder)

```
1. EnvironmentShellBlueprintFactory  → EnvironmentShellBlueprint
2. ShellFloorBuilder                 → FLOOR_CONSTRUCTION_COMPLETE
3. ShellWallBuilder                  → WALL_CONSTRUCTION_COMPLETE
4. ShellCeilingBuilder               → CEILING_CONSTRUCTION_COMPLETE
5. StructuralAnchorGenerator         → STRUCTURAL_ANCHORS_READY
6. StructuralElementPlacer           → STRUCTURAL_PLACEMENT_COMPLETE
7. ShellValidator                    → ENVIRONMENT_VALIDATION_COMPLETE
8. EnvironmentReadinessGate          → ENVIRONMENT_READY / ENVIRONMENT_NOT_READY
9. EnvironmentShellAuditor           → ShellAudit
10. ShellReview                      → ShellReviewResult
11. ShellStatistics                  → record
```

Usage:
```python
from src.runtime.environment_shell import get_environment_shell_builder

result = get_environment_shell_builder().build("western_room")
if not result.shell.environment_ready:
    raise RuntimeError("Environment not ready — cannot place assets.")
# result.review.grade == "A", result.review.production_ready == True
```

### 51.4 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_build_shell` | Full 6-phase pipeline: environment → shell + gate + audit + review |
| `hou_mcp_shell_gate` | Evaluate readiness gate from shell_json; dual exec output (ready/blocked) |
| `hou_mcp_shell_audit` | Structured audit: environment_valid + geometry_valid + production_ready |
| `hou_mcp_shell_review` | 6-dimension quality review: grade, score, production_ready |
| `hou_mcp_shell_debug` | Full pipeline debug with formatted log report |

**Canonical workflow:** `hou_mcp_build_shell` → `hou_mcp_shell_gate` → (exec_out_ready) → `hou_mcp_layout_cluster`

**Debug shortcut:** `hou_mcp_shell_debug` runs all phases and logs a formatted report.

### 51.5 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `environment_shell_construction` | 6-phase shell pipeline; environment_ready gate |
| `environment_readiness_gate` | BLOCKING gate blocking furniture/decoration placement |
| `shell_floor_construction` | Phase 1: floor element with walkable_surface |
| `shell_wall_construction` | Phase 2: four perimeter walls forming enclosure |
| `shell_ceiling_construction` | Phase 3: ceiling element (or open_sky for outdoor) |
| `structural_anchor_generation` | Phase 4: door/window/beam/column/fireplace anchors |
| `shell_structural_placement` | Phase 5: attach structural assets to anchors |
| `shell_validation` | Phase 6: validate enclosure completeness |
| `environment_shell_audit` | Audit: environment_valid + geometry_valid + production_ready |
| `shell_review` | 6-dimension quality review with grade |

### 51.6 EnvironmentShell key fields

| Field | Source phase | Meaning |
|---|---|---|
| `floor_exists` | Phase 1 | Floor element was built |
| `floor_area` | Phase 1 | width × length in m² |
| `wall_count` | Phase 2 | Number of walls built (0 for outdoor) |
| `enclosure_valid` | Phase 2 | Walls form a closed boundary |
| `ceiling_exists` | Phase 3 | Ceiling element was built |
| `ceiling_height` | Phase 3 | Height of ceiling in meters |
| `door_anchor_count` | Phase 4 | Door attachment anchors available |
| `beam_anchor_count` | Phase 4 | Beam attachment anchors available |
| `door_attachment_count` | Phase 5 | Structural assets attached to door anchors |
| `room_bounds_valid` | Phase 6 | Non-zero room dimensions |
| `environment_ready` | Gate | True only after gate passes |

### 51.7 Environment Readiness Gate

Gate condition:
```python
environment_ready = (
    floor_exists
    and (ceiling_exists or is_outdoor)
    and (wall_count >= required_wall_count or is_outdoor)
    and enclosure_valid
)
```

If `environment_ready = False`:
- `gate_status = ENVIRONMENT_NOT_READY`
- `severity = BLOCKING`
- `blocked_systems = [FurnitureClusterBuilder, SurfacePlacementEngine, DecorationLayoutEngine, SceneRealityValidation]`

The `exec_out_blocked` pin on `hou_mcp_shell_gate` fires only on gate failure — wire it to an error handler.

### 51.8 Shell review grade mapping

| Score | Grade | production_ready |
|---|---|---|
| ≥ 0.90 | A | ✓ |
| ≥ 0.75 | B | ✓ |
| ≥ 0.60 | C | ✗ |
| ≥ 0.45 | D | ✗ |
| < 0.45 | F | ✗ |

Score weights: `floor(0.25) + wall(0.25) + ceiling(0.20) + anchors(0.15) + enclosure(0.10) + phases(0.05)`

Blocking findings: `"floor missing"`, `"wall missing"`, `"ceiling missing"`, `"enclosure invalid"`, `"no anchors defined"`

### 51.9 ShellAudit final metrics

```
environment_valid   = floor_exists AND (ceiling_exists OR outdoor) AND wall_count >= required
geometry_valid      = room_bounds_valid AND floor_area > 0
semantic_valid      = True (Tier 9.9/14.3 refines this downstream)
plausibility_valid  = True (Tier 14.3 refines this downstream)
production_ready    = environment_valid AND geometry_valid AND semantic_valid AND plausibility_valid
```

### 51.10 Pipeline insertion point

Insert `hou_mcp_build_shell` at the very start, before any classification or layout:

```
scene_intent
→ hou_mcp_build_shell               [NEW Tier 10.4]
→ hou_mcp_shell_gate                [NEW Tier 10.4]
  exec_out_ready ↓
→ hou_mcp_structural_classifier     [Tier 10.3]
→ hou_mcp_placement_routing_audit   [Tier 10.3.5]
→ hou_mcp_layout_cluster            [Tier 9.8]
→ hou_mcp_realize_layout            [Tier 9.9]
→ hou_mcp_apply_layout              [Tier 9.9]
→ hou_mcp_scene_reality_validation  [Tier 14.3]
  exec_out_blocked ↓
→ error_handler
```

### 51.11 EnvironmentShellBlueprintFactory — supported environments

All 55 production environments (§39) plus their outdoor/indoor classification, floor material, ceiling type, door/window counts. Unknown environments fall back to `(10m × 4m × 12m, flat_ceiling, concrete, 1 door, 2 windows, indoor)`.

### 51.12 Test conventions

- Reset ALL 10 singletons in `autouse` fixture (builder + blueprint_factory + floor + wall + ceiling + anchor + placer + validator + gate + auditor + review + stats)
- No bridge calls, no network calls, no randomness
- Test all canonical acceptance criteria:
  - `western_room`: floor_exists=True, wall_count=4, ceiling_exists=True, door_anchor_count=1, window_anchor_count=2, beam_anchor_count=4, environment_ready=True, grade="A"
  - `forest` (outdoor): floor_exists=True, wall_count=0, ceiling_exists=False, environment_ready=True
  - Empty environment → fallback blueprint → environment_ready=True
- Test gate blocking: manually set floor_exists=False → ENVIRONMENT_NOT_READY + blocked_systems non-empty
- Test audit production_ready: environment_valid AND geometry_valid → production_ready=True
- 8 test files in `tests/unit/`: `test_environment_shell_blueprint.py`, `test_shell_floor_builder.py`, `test_shell_wall_builder.py`, `test_shell_ceiling_builder.py`, `test_structural_anchor_generator.py`, `test_structural_element_placer.py`, `test_shell_validator.py`, `test_environment_readiness_gate.py`, `test_environment_shell_builder.py`

`production_ready` requires `overall_score >= 0.70` AND `best_score >= 0.50` AND no blocking findings.
Blocking findings: `"no candidates"`, `"best score below threshold"`, `"all candidates rejected"`.

### 45.7 Success criteria examples

| Environment | Slot | Before | After |
|---|---|---|---|
| western_room | chair | generic seating / modern plastic chair | Wooden Saloon Chair (0.87) |
| western_room | lantern | bottle | Oil Lantern |
| western_room | poster | random prop | Wanted Poster |
| robotics_lab | machine | western barrel | Robot Arm |
| castle_hall | poster | sci-fi terminal | Castle Banner |

### 45.8 Test conventions

- Reset ALL 8 singletons in `autouse` fixture (engine + 6 affinity modules + review)
- Test all core success criteria explicitly (wooden chair > modern chair, lantern > bottle, poster > rock)
- `test_asset_selection_validation.py` is the end-to-end integration test
- No network calls, no Houdini dependency, no randomness
- 8 test files in `tests/unit/`: `test_asset_suitability_engine.py`, `test_environment_affinity.py`, `test_role_affinity.py`, `test_style_affinity.py`, `test_material_affinity.py`, `test_scale_affinity.py`, `test_story_affinity.py`, `test_asset_selection_validation.py`

---

## 46. Semantic Furniture Layout Engine (Tier 9.8)

Tier 9.8 transforms environment population from zone-based placement into relationship-based placement. Every asset is placed relative to another asset through a semantic relationship — not independently dropped into a zone.

**Before Tier 9.8:**
```
Table           (zone slot 1)
Chair           (zone slot 2)
Bottle          (zone slot 3)
Lantern         (zone slot 4)
Poster          (zone slot 5)   ← floating mid-air
Bench           (zone slot 6)   ← room center
```

**After Tier 9.8:**
```
Hero Table
├── Chair  (around, 0.9m N, faces S)
├── Chair  (around, 0.9m S, faces N)
├── Chair  (around, 0.9m E, faces W)
├── Chair  (around, 0.9m W, faces E)
├── Whiskey Bottle  (supports, on table surface @ y=0.75m)
└── Lantern         (supports, on table surface @ y=0.75m)

Wall North
└── Wanted Poster   (attached_to, h=1.60m)

Corner SW
└── Barrel          (near corner)
```

**Non-negotiable design rules:**
1. No bridge calls. All modules are planning/advisory only. Never import or call `get_bridge()`.
2. No randomness. Same input always produces the same output.
3. Never raises in public methods — errors captured in result dicts.
4. Singleton pattern — every module has `get_X()` and `reset_X_for_tests()`.
5. Thread-safe (`threading.Lock` per instance).
6. `dataclass` + `to_dict()` / `from_dict()` pattern on all result classes.
7. Assets placed relative to other assets — never independently in zones.

### 46.1 Module layout

```
src/runtime/layout/
    __init__.py                    ← full re-export of all public surface
    relationship_graph.py          ← AssetRelationship + AssetRelationshipGraph (10 types)
    affordance_engine.py           ← AffordanceProfile + AffordanceEngine (surface/around/anchor/wall)
    surface_placement_engine.py    ← SurfacePlacement + SurfacePlacementEngine (on-surface Y coords)
    furniture_cluster_builder.py   ← ClusterMember + FurnitureCluster + FurnitureClusterBuilder
    anchor_layout_engine.py        ← AnchorPlacement + AnchorLayoutResult + AnchorLayoutEngine
    wall_attachment_engine.py      ← WallAttachment + WallAttachmentResult + WallAttachmentEngine
    decoration_layout_engine.py    ← DecorativeItem + DecorationLayoutResult + DecorationLayoutEngine
    layout_review.py               ← LayoutReviewResult + LayoutReview (5-dimension scoring)
    layout_serializer.py           ← LayoutSerializer (sorted-key JSON, schema 1.0.0)
    layout_statistics.py           ← LayoutStatRecord + LayoutStatistics (capped at 2000)
    semantic_layout_engine.py      ← LayoutPlan + SemanticLayoutEngine (main orchestrator)
```

### 46.2 Pipeline stages

1. **Anchor Placement** — Hero anchor assets (table, machine, fireplace) placed first at hero_zone. Secondary anchors spread to support_zone/midground.
2. **Relationship Graph** — Semantic edges built for every asset pair: bottle→table `supports`, chair→table `around`, poster→wall `attached_to`, bench→wall `against`.
3. **Furniture Clusters** — Anchor + its dependents grouped as a named cluster: `saloon_table_cluster`, `bar_cluster`, `workbench_cluster`, `campfire_cluster`.
4. **Surface Placement** — Small props placed on actual host surfaces at the correct Y height (table=0.75m, shelf=1.40m, bar_counter=1.05m).
5. **Wall Attachment** — Posters/lanterns/signs mounted on walls at the correct height with wall-normal orientation.
6. **Decoration Layout** — Remaining assets assigned contextual targets per environment (western_room → barrel to corner, lantern to wall).
7. **Layout Review** — 5-dimension quality review produces grade + production_ready.

### 46.3 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_layout_graph` | Build and query the relationship graph |
| `hou_mcp_layout_cluster` | Build furniture clusters with relative positions |
| `hou_mcp_surface_placement` | Place child objects on a host surface at correct Y |
| `hou_mcp_affordance` | Query affordance profile for any asset type |
| `hou_mcp_layout_review` | 5-dimension layout quality review |
| `hou_mcp_semantic_layout_debug` | Full pipeline debug report in one node |

**Canonical workflow:** `hou_mcp_affordance` → `hou_mcp_layout_cluster` → `hou_mcp_surface_placement` → `hou_mcp_layout_graph` → `hou_mcp_layout_review`

**Debug shortcut:** `hou_mcp_semantic_layout_debug` runs all 7 stages and logs a full tree report.

> **Note**: `hou_mcp_layout_debug` is a pre-existing Tier 9.6 node for scale-aware spatial debugging. The Tier 9.8 debug node is `hou_mcp_semantic_layout_debug`.

### 46.4 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `semantic_layout` | Full relationship-based pipeline: 7 stages, anchor→cluster→surface→wall→deco→review |
| `relationship_graph` | Directed semantic graph (10 types: supports/around/attached_to/against/…) |
| `affordance_reasoning` | Per-type affordance profiles: surface/around/anchor/wall/ceiling/corner |
| `surface_placement` | On-surface Y-coord placement (table=0.75m, shelf=1.40m, bar=1.05m) |
| `wall_attachment` | Wall mounting at correct heights (poster 1.4–1.8m, lantern 2.0–2.8m) |
| `furniture_clustering` | Named clusters: saloon_table, bar, workbench, campfire, console |
| `contextual_decoration` | Per-environment decoration preferences (21 environments) |
| `layout_review` | 5-dimension quality review with blocking findings |

### 46.5 Relationship types

| Type | Meaning | Example |
|---|---|---|
| `supports` | Child object ON host surface | bottle supports table |
| `contains` | Child inside host container | book contains shelf |
| `attached_to` | Mounted on host | poster attached_to wall |
| `around` | Orbiting at fixed radius | chair around table (0.9m) |
| `near` | Proximate but unattached | barrel near corner |
| `against` | Flush against host | bench against wall |
| `inside` | Spatially inside host | — |
| `hanging_from` | Hanging below host | lantern hanging_from ceiling |
| `mounted_on` | Flat on host surface | sign mounted_on wall |
| `facing` | Oriented toward host | chair facing table |

### 46.6 Affordance tables

**Surface affordances** (host type → accepts these child types):

| Host | Accepts |
|---|---|
| `table` | bottle, cup, book, plate, lantern, glass, mug, candle, bowl, vase, tool, container, small_prop |
| `workbench` | tool, container, machine_part, wrench, hammer, small_prop |
| `bar_counter` | bottle, cup, glass, mug, bowl, container, small_prop, whiskey_bottle |
| `shelf` | book, bottle, tool, container, vase, small_prop |

**Around affordances** (host type → attracts these child types):

| Host | Attracts |
|---|---|
| `table` | chair, stool |
| `bar_counter` | stool, chair |
| `fireplace` | chair, bench |
| `campfire` | chair, bench, barrel, stool |

### 46.7 Surface heights (meters)

| Host type | Surface height |
|---|---|
| `table` | 0.75 m |
| `desk` | 0.75 m |
| `workbench` | 0.90 m |
| `bar_counter` | 1.05 m |
| `shelf` | 1.40 m |
| `mantle` | 1.20 m |
| `cabinet` | 1.60 m |

### 46.8 Wall mounting heights (meters, midpoint of range)

| Asset type | Height range | Midpoint |
|---|---|---|
| poster / painting / mirror | 1.40–1.80 m | 1.60 m |
| sign / clock | 1.60–2.00 m | 1.80 m |
| banner | 1.80–2.50 m | 2.15 m |
| lantern / torch | 2.00–2.80 m | 2.40 m |
| shelf | 1.20–1.60 m | 1.40 m |

### 46.9 Furniture cluster positions

Chairs orbit the anchor at 0.9 m in four cardinal directions:

| Slot | Offset | Orientation |
|---|---|---|
| South | [0, 0, +0.9] | 180° (faces north) |
| North | [0, 0, −0.9] | 0° (faces south) |
| East | [+0.9, 0, 0] | 270° (faces west) |
| West | [−0.9, 0, 0] | 90° (faces east) |

Surface props spread linearly across the surface width at surface_height Y.

### 46.10 Layout review scoring

Score weights:

| Dimension | Weight | Meaning |
|---|---|---|
| `relationship_accuracy` | 0.30 | Assets placed per their affordances |
| `surface_accuracy` | 0.25 | Surface items actually on surfaces |
| `wall_attachment_accuracy` | 0.20 | Wall items actually on walls |
| `cluster_quality` | 0.15 | Clusters have appropriate members |
| `contextual_quality` | 0.10 | Decorations match environment |

Grade mapping:

| Score | Grade | production_ready |
|---|---|---|
| ≥ 0.85 | A | ✓ |
| ≥ 0.70 | B | ✓ |
| ≥ 0.55 | C | ✗ |
| ≥ 0.40 | D | ✗ |
| < 0.40 | F | ✗ |

**Blocking findings** (force production_ready = False regardless of score):
- `"bottle on floor when table exists"` — bottle-type asset not on any surface when table present
- `"poster not attached to wall"` — poster/painting/banner not wall-mounted
- `"no relationships defined"` — no relationship graph and no clusters
- `"no anchors placed"` — layout has no focal points

### 46.11 Environment decoration preferences (selected)

| Environment | Preferred types |
|---|---|
| `western_room` | barrel, lantern, whiskey_bottle, wanted_poster, rope, bucket, hay_bale |
| `saloon` | barrel, lantern, bottle, wanted_poster, card_deck, chandelier |
| `castle_hall` | banner, torch, armor_stand, tapestry, candle, shield |
| `robotics_lab` | electronic, container, tool, cable, monitor, warning_sign |
| `industrial_hangar` | tool, container, pipe, warning_sign, oil_drum, chain |
| `dungeon` | torch, chain, barrel, shackles |
| `survival_camp` | barrel, crate, rope, lantern, blanket, bucket |

### 46.12 Test conventions

- Reset ALL 11 singletons in `autouse` fixture (engine + all sub-engines + graph + review + stats + serializer)
- No network calls, no Houdini dependency, no randomness
- Test the canonical success criteria explicitly: chairs around table, bottle on surface, poster on wall, bench against wall
- Test determinism: same input → same output across multiple calls
- 9 test files in `tests/unit/`: `test_relationship_graph.py`, `test_affordance_engine.py`, `test_surface_placement_engine.py`, `test_furniture_cluster_builder.py`, `test_anchor_layout_engine.py`, `test_wall_attachment_engine.py`, `test_decoration_layout_engine.py`, `test_layout_review.py`, `test_semantic_layout_engine.py`

---

## 47. Layout Realization & Scene Constraint Solver (Tier 9.9)

Tier 9.9 bridges the Semantic Layout Planning (Tier 9.8) output and the actual Houdini scene. It converts a `LayoutPlan` into a `ResolvedSceneLayout` — a concrete set of world-space transforms (tx, ty, tz, rx, ry, rz) for every asset, after collision resolution and constraint enforcement.

**Root problem solved:**
Before Tier 9.9 the scene builder placed all assets on a linear X-axis (`asset_01 x=0`, `asset_02 x=4`, …). Semantic relationships were computed but never applied. Bottles floated at floor level, posters had no wall attachment, chairs sat at the origin instead of orbiting the table.

**Non-negotiable design rules:**
1. All modules except `layout_application_engine.py` are pure planning — no bridge calls.
2. `layout_application_engine.py` is the ONLY module that imports `get_bridge()` (isolated adapter).
3. No randomness. Same `LayoutPlan` always produces the same `ResolvedSceneLayout`.
4. Never raises in public methods — errors in result dicts.
5. Singleton pattern — `get_X()` + `reset_X_for_tests()` on every module.
6. Thread-safe throughout.
7. Parent-child asset pairs (bottle on table, chair in cluster) are exempt from AABB collision checks.

### 47.1 Module layout

```
src/runtime/layout_realization/
    __init__.py                      <- full re-export of all public surface
    transform_resolver.py            <- ResolvedTransform + TransformResolver (core data type)
    relationship_realizer.py         <- RelationshipRealization + RelationshipRealizer
    surface_realizer.py              <- SurfaceRealizationResult + SurfaceRealizer
    wall_attachment_realizer.py      <- WallRealizationResult + WallAttachmentRealizer
    cluster_realizer.py              <- ClusterRealizationResult + ClusterRealizer
    collision_solver.py              <- CollisionRecord + CollisionResult + CollisionSolver
    scene_constraint_solver.py       <- ConstraintViolation + ConstraintSolveResult + SceneConstraintSolver
    layout_realization_engine.py     <- ResolvedSceneLayout + LayoutRealizationEngine (main orchestrator)
    layout_application_engine.py     <- ApplicationResult + LayoutApplicationEngine (bridge adapter)
    realization_review.py            <- RealizationReviewResult + RealizationReview
    realization_statistics.py        <- RealizationRecord + RealizationStatistics
    realization_serializer.py        <- RealizationSerializer (sorted-key JSON, schema 1.0.0)
```

### 47.2 Pipeline stages (LayoutRealizationEngine)

1. **Cluster Realization** — anchor world position + member relative offsets to world transforms; all members tagged with `cluster_id`
2. **Surface Realization** — `ty = host_world_y + surface_height + child_half_height`; items spread across surface width
3. **Wall Realization** — wall-face position, `ry` from wall normal, inset 0.05m from boundary
4. **Decoration Realization** — floor-level fallback slots for unplaced items
5. **Collision Solving** — AABB push-apart (5 iterations); parent-child pairs exempt
6. **Constraint Solving** — wall clearance, cluster spacing, hero visibility
7. **Final Assembly** — `production_ready = collision_count == 0 AND constraint_violations == 0 AND asset_count > 0`

### 47.3 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_realize_layout` | Full pipeline: LayoutPlan to ResolvedSceneLayout |
| `hou_mcp_constraint_solver` | Wall clearance, cluster spacing, hero visibility |
| `hou_mcp_collision_solver` | AABB collision detection and push-apart |
| `hou_mcp_apply_layout` | Apply transforms to Houdini via set_parms (bridge) |
| `hou_mcp_realization_review` | 6-dimension quality review |
| `hou_mcp_scene_realization_debug` | Full debug pipeline in one node |

**Canonical workflow:** `hou_mcp_realize_layout` -> `hou_mcp_realization_review`

### 47.4 Wall normal to ry mapping

Assets on walls face INTO the room:
- `[0, 0, -1]` north wall -> ry=0 (faces south)
- `[0, 0, +1]` south wall -> ry=180 (faces north)
- `[-1, 0, 0]` east wall  -> ry=90 (faces west)
- `[+1, 0, 0]` west wall  -> ry=270 (faces east)

Formula: `ry = atan2(-nx, -nz)` degrees % 360

### 47.5 Collision solver rules

- Parent-child pairs are exempt (bottle on table does not collide with table)
- Wall-mounted assets (poster, lantern) have radius 0.0 and never collide
- Resolution: push-apart -> slide -> fallback; 5 iteration max
- Unresolved assets flagged with `is_collision_free=False`

### 47.6 Realization review grade mapping

| Score | Grade | production_ready |
|---|---|---|
| >= 0.90 | A | True |
| >= 0.75 | B | True |
| >= 0.60 | C | False |
| >= 0.45 | D | False |
| < 0.45 | F | False |

Score weights: `transform_accuracy(0.25) + relationship_accuracy(0.20) + collision_quality(0.20) + surface_quality(0.15) + wall_attachment_quality(0.10) + visibility_quality(0.10)`

Blocking findings: `"chair inside table"`, `"bottle on floor when table exists"`, `"poster outside wall"`, `"cluster overlap"`, `"hero asset blocked"`

### 47.7 LayoutApplicationEngine (bridge adapter)

`apply_layout(transforms, node_path_map)` calls `get_bridge()`.
`build_transform_op_dicts(transforms, node_path_map)` returns op dicts without the bridge (use for dry-run/tests).

### 47.8 Test conventions

- Reset ALL 7 singletons in `autouse` fixture for engine tests
- No bridge calls in tests — use `build_transform_op_dicts` for application engine tests
- Test western_room canonical criteria: chairs orbit table, glass on bar surface, poster on north wall
- Test determinism: same LayoutPlan produces identical transforms every call
- 12 test files in `tests/unit/`: `test_transform_resolver.py`, `test_cluster_realizer.py`, `test_surface_realizer.py`, `test_wall_attachment_realizer.py`, `test_collision_solver.py`, `test_scene_constraint_solver.py`, `test_relationship_realizer.py`, `test_layout_realization_engine.py`, `test_layout_application_engine.py`, `test_realization_review.py`, `test_realization_statistics.py`, `test_realization_serializer.py`

---

## 49. Structural Environment Realization (Tier 10.0)

Tier 10.0 converts environment blueprints into complete architectural structures. Before this tier, assets were placed in empty space with no room geometry. After this tier, every environment has a physical shell: floor, walls, ceiling, doors, windows, beams, and columns.

**Root problem solved:**
Assets were placed in empty space. There were no walls, no floor geometry, no ceiling, no doors. The environment existed only as zones and asset lists. Tier 10.0 generates the complete architectural shell before any asset placement.

**Non-negotiable design rules:**
1. No bridge calls. All modules are planning/advisory only.
2. No randomness. Same environment always produces the same RoomShell.
3. Never raises in public methods — errors in result dicts.
4. Singleton pattern — `get_X()` + `reset_X_for_tests()` on every module.
5. Thread-safe throughout.
6. Outdoor environments (forest, desert, survival_camp, etc.) receive a 50×50m ground plane and no walls/ceiling.

### 49.1 Module layout

```
src/runtime/environment_realization/
    __init__.py                           <- full re-export of all public surface
    structural_elements.py                <- StructuralElement + RoomShell + EnvironmentRealizationPlan
    floor_builder.py                      <- FloorBuilder (material per environment)
    ceiling_builder.py                    <- CeilingBuilder (type per environment, None for outdoor)
    wall_builder.py                       <- WallBuilder (4 perimeter walls with correct positions)
    opening_builder.py                    <- OpeningBuilder (doors, windows, skylights, vents)
    beam_builder.py                       <- BeamBuilder (beams + columns per environment)
    room_shell_builder.py                 <- RoomShellBuilder (orchestrates sub-builders)
    architectural_constraint_solver.py    <- ArchitecturalConstraintSolver (validates + corrects)
    structural_builder.py                 <- StructuralBuilder (flat elements + transaction ops)
    environment_realization_engine.py     <- EnvironmentRealizationEngine (main orchestrator)
    environment_review.py                 <- EnvRealizationReview (6-dimension quality review)
    environment_statistics.py             <- EnvRealizationStatistics (rolling 2000 records)
    environment_serializer.py             <- EnvRealizationSerializer (sorted-key JSON, 1.0.0)
```

### 49.2 Environment dimensions (selected)

| Environment | Width | Height | Depth | Primary material |
|---|---|---|---|---|
| western_room | 10m | 4m | 12m | wood |
| saloon | 14m | 4.5m | 18m | wood |
| industrial_hangar | 30m | 12m | 40m | industrial_metal |
| warehouse | 20m | 8m | 30m | concrete |
| robotics_lab | 15m | 3.5m | 20m | concrete |
| sci_fi_corridor | 4m | 3m | 20m | sci_fi_panel |
| castle_hall | 20m | 10m | 30m | stone |
| dungeon | 8m | 3m | 10m | stone |
| forest (outdoor) | 50m ground plane | — | — | dirt |

### 49.3 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_build_environment` | Full pipeline: environment name → complete EnvironmentRealizationPlan |
| `hou_mcp_build_structure` | Structural elements only (floor, walls, ceiling) |
| `hou_mcp_build_openings` | Doors, windows, skylights, vents |
| `hou_mcp_build_beams` | Beams and columns |
| `hou_mcp_environment_realization_review` | 6-dimension quality review |
| `hou_mcp_environment_realization_debug` | Full pipeline with formatted log report |

**Canonical workflow:** `hou_mcp_build_environment` → `hou_mcp_environment_realization_review`

### 49.4 Ceiling types by environment

| Type | Environments |
|---|---|
| beam_ceiling | western_room, saloon, warehouse, workshop |
| flat_ceiling | office, control_room, medical_lab, research_lab |
| industrial_ceiling | industrial_hangar, abandoned_factory, shipyard |
| arched_ceiling | dungeon, wizard_tower, ancient_ruins |
| vaulted_ceiling | castle_hall, temple |
| sci_fi_ceiling | sci_fi_corridor, space_station, spaceship_bridge |
| high_ceiling | library, hotel_lobby, shopping_mall |
| open_sky (None) | all outdoor environments |

### 49.5 Canonical openings per environment

| Environment | Openings |
|---|---|
| western_room | 1 swing_door (south) + 2 windows (east/west) |
| saloon | 1 swing_door + 1 side_door + 2 windows |
| industrial_hangar | 1 hangar_opening + 1 side_door + 4 skylights |
| warehouse | 1 loading_door + 1 side_door + 2 skylights |
| sci_fi_corridor | 2 sliding_doors + 4 vents |
| castle_hall | 1 archway + 4 arrow_slits |
| dungeon | 1 door + 4 arrow_slits |

### 49.6 Beam types per environment

| Type | Environments |
|---|---|
| wooden_beam | western_room (4), saloon (6), warehouse (6), library (4) |
| steel_girder | industrial_hangar (8 beams + 6 cols), warehouse (6+4), shipyard (10+8) |
| panel_rib | sci_fi_corridor (8), space_station (6+4) |
| stone_arch | castle_hall (4+8), dungeon (2+4) |
| concrete_column | robotics_lab (0+4), hotel_lobby (0+6) |

### 49.7 Transaction op format

All structural elements are converted to Houdini operation dicts:
```python
{
    "type":         "create_structural_node",
    "element_id":   "floor_western_room",
    "element_type": "floor",
    "environment":  "western_room",
    "parms": {"tx": 0.0, "ty": 0.0, "tz": 0.0, "width": 10.0, "depth": 12.0, ...},
    "material":     "wood",
    "face":         "bottom",
    "wall_id":      "",
    "parent_path":  "/obj/env_western_room",
}
```

### 49.8 Environment review grade mapping

| Score | Grade | production_ready |
|---|---|---|
| >= 0.95 | A | True |
| >= 0.80 | B | True |
| >= 0.65 | C | False |
| >= 0.50 | D | False |
| < 0.50 | F | False |

Score weights: `structural_completeness(0.30) + architectural_validity(0.20) + zone_accuracy(0.15) + opening_quality(0.15) + beam_quality(0.10) + room_integrity(0.10)`

Blocking findings: `"floor missing"`, `"wall missing"`, `"no door"`, `"room not closed"`, `"no zones defined"`

### 49.9 Constraint solver rules

- Ceiling width/depth snapped to room dimensions if mismatch > 0.5m
- Opening height trimmed if it exceeds parent wall height
- Missing wall/floor/ceiling flagged as `room_closure` violation (not corrected)
- Opening with invalid `wall_id` flagged as `door_inside_wall` or `window_inside_wall`

### 49.10 Test conventions

- Reset ALL 11 singletons in `autouse` fixture for engine tests
- No bridge calls, no network calls, no randomness
- Test all 5 canonical environments: western_room, industrial_hangar, castle_hall, sci_fi_corridor, forest
- Test all blocking conditions explicitly
- Shell ID (UUID) excluded from determinism comparisons — compare structure, not identity
- 12 test files in `tests/unit/`: `test_floor_builder.py`, `test_ceiling_builder.py`, `test_wall_builder.py`, `test_opening_builder.py`, `test_beam_builder.py`, `test_room_shell_builder.py`, `test_architectural_constraint_solver.py`, `test_structural_builder.py`, `test_environment_realization_engine.py`, `test_environment_review.py`, `test_environment_realization_statistics.py`, `test_environment_realization_serializer.py`

---

## 50. Structural Asset Classification (Tier 10.3)

Tier 10.3 introduces a dedicated structural classification layer that runs **before** layout generation and environment realization. It automatically identifies architectural and structural assets — doorways, beams, columns, fireplaces, wall segments, archways, stairs, railings — and routes them to the correct builder systems rather than the furniture/decoration pipeline.

**Root problem solved:**
Before Tier 10.3, a 4-meter doorway could enter the furniture cluster, a beam could be placed as a decoration, and a fireplace could become a free-standing prop floating in the room center. All architectural assets were treated identically to furniture unless placement_type was set explicitly.

**Non-negotiable design rules:**
1. No bridge calls. All modules are pure planning. Never import or call `get_bridge()`.
2. No randomness. Same inputs always produce the same classification.
3. Never raises in public methods — errors in result objects.
4. Singleton pattern — every module has `get_X()` and `reset_X_for_tests()`.
5. Thread-safe throughout.
6. `dataclass` + `to_dict()` pattern on all result classes.
7. Classification must run before SemanticLayoutEngine.

### 50.1 Module layout

```
src/runtime/structure/
    __init__.py                          ← full re-export of all public surface
    geometry_role_detector.py            ← GeometryRoleDetector — bbox dimension analysis
    metadata_role_classifier.py          ← MetadataRoleClassifier — name/tag/category keywords
    environment_structural_affinity.py   ← EnvironmentStructuralAffinity — context adjustment
    structural_placement_rules.py        ← PlacementIntent + StructuralPlacementRules
    structural_asset_classifier.py       ← StructuralClassificationResult + StructuralAssetClassifier (main)
    structural_review.py                 ← StructuralReviewResult + StructuralReview
    structural_statistics.py             ← StructuralStatRecord + StructuralStatistics (capped 2000)
    structural_serializer.py             ← StructuralSerializer (sorted-key JSON, schema 1.0.0)
```

### 50.2 Supported structural roles (20 total)

| Role | Placement target | Routes to |
|---|---|---|
| `furniture` | scene_zone | SemanticLayoutEngine |
| `prop` | scene_zone | SemanticLayoutEngine |
| `decoration` | scene_zone | SemanticLayoutEngine |
| `wall` | room_shell / perimeter | EnvironmentStructureBuilder |
| `wall_segment` | wall_face | EnvironmentStructureBuilder |
| `doorway` | wall_opening | OpeningBuilder |
| `door_frame` | wall_opening | OpeningBuilder |
| `window` | wall_opening | OpeningBuilder |
| `window_frame` | wall_opening | OpeningBuilder |
| `fireplace` | wall_face | AnchorAssetBuilder |
| `beam` | ceiling_support | BeamBuilder |
| `support_beam` | ceiling_support | BeamBuilder |
| `column` | floor_perimeter | BeamBuilder |
| `floor_piece` | floor_plane | FloorBuilder |
| `ceiling_piece` | ceiling_plane | CeilingBuilder |
| `stair` | transition_zone | EnvironmentStructureBuilder |
| `railing` | stair_or_balcony | EnvironmentStructureBuilder |
| `archway` | wall_opening | OpeningBuilder |
| `architectural_module` | structure_zone | EnvironmentStructureBuilder |
| `structural_unknown` | structure_zone | EnvironmentStructureBuilder |

### 50.3 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_structural_classifier` | Classify a batch of assets; splits into structural_json / furniture_json |
| `hou_mcp_structural_review` | Validate placement rules; detect blocking findings |
| `hou_mcp_structural_affinity` | Inspect preferred/irrelevant roles for an environment |
| `hou_mcp_structural_debug` | Full pipeline debug: geometry + metadata + affinity + review in one node |

**Canonical workflow:** `hou_mcp_structural_classifier` → `hou_mcp_structural_review` → route structural assets to EnvironmentStructureBuilder / SemanticLayoutEngine

**Debug shortcut:** `hou_mcp_structural_debug` runs the complete pipeline and logs a formatted tree report.

### 50.4 Capability IDs (added to `src/runtime/capability_registry.py`)

| id | description |
|---|---|
| `structural_asset_classification` | Full 3-signal pipeline: geometry + metadata + environment affinity |
| `geometry_role_detection` | Bbox dimension analysis — beam/column/doorway/wall/floor detection |
| `metadata_role_classification` | Keyword tables for 120+ structural terminology strings |
| `environment_structural_affinity` | Per-environment preferred/irrelevant role tables (25 environments) |
| `structural_placement_intent` | Route-to and attach-to rules for all 20 structural roles |
| `structural_layout_review` | 4-dimension review: placement/pipeline/role/coverage |

### 50.5 Classification signals and priority

```
classify(asset, environment):
  1. placement_type field (confidence ≥ 0.85) → fast path, highest priority
  2. MetadataRoleClassifier (name/tags/category)  → overrides geometry if conf ≥ 0.80
  3. GeometryRoleDetector (bbox dimensions)        → used when metadata is weak
  4. Both signals agree → combined boost (+0.05)
  5. EnvironmentStructuralAffinity → adjust winner:
       preferred role: +0.10 (capped at 1.0)
       irrelevant role: capped at 0.50
```

### 50.6 Geometry detection thresholds

| Signal | Condition | Role | Confidence |
|---|---|---|---|
| Beam | w ≥ 2m, h ≤ 0.6m, d ≤ 0.6m, w/cross ≥ 4 | beam | 0.70–0.86 |
| Column | h ≥ 2m, footprint ≤ 0.8m, h/foot ≥ 3.5 | column | 0.70–0.80 |
| Doorway | h ≥ 1.8m, w ≥ 0.5m, d ≤ 0.5m, h/d ≥ 3 | doorway | 0.78 |
| Wall segment | h ≥ 2m, w ≥ 1.5m, d ≤ 0.5m | wall_segment | 0.72–0.75 |
| Floor piece | h ≤ 0.25m, footprint ≥ 1.0m² | floor_piece | 0.80 |
| Archway | h ≥ 1.8m, d ≤ 0.5m, h/w < 1.1 | archway | 0.65 |
| Furniture | max_dim < 2.0m, no extreme ratios | furniture | 0.55–0.65 |

### 50.7 Validation scenarios (expected outcomes)

| Asset | Environment | Expected role | Confidence |
|---|---|---|---|
| Historic Interior Door (1.0 × 2.2 × 0.1 m) | western_room | doorway | 0.98 |
| Old Wooden Beam (3.7 × 0.3 × 0.3 m) | western_room | beam | 1.0 |
| Fireplace | western_room | fireplace | 1.0 |
| Wall Moulding | western_room | wall_segment | 0.95 |
| Wooden Chair (0.5 × 0.9 × 0.5 m) | western_room | furniture | 0.65 |
| Teapot (0.2 × 0.15 × 0.2 m) | western_room | furniture | 0.65 |
| Steel Girder (5.0 × 0.4 × 0.4 m) | industrial_hangar | beam | 1.0 |
| Stone Arch (2.5 × 3.0 × 0.4 m) | castle_hall | archway | 0.90 |
| Stone Column (0.5 × 4.0 × 0.5 m) | industrial_hangar | column | 1.0 |

### 50.8 Environment affinity coverage (25 environments)

western_room, saloon, living_room, office, hotel_lobby, restaurant, library,
industrial_hangar, warehouse, abandoned_factory, shipyard, robotics_lab,
research_lab, medical_lab, control_room, sci_fi_corridor, space_station,
castle_hall, dungeon, wizard_tower, forest, desert, city_street,
survival_camp, military_base

### 50.9 Review blocking findings

| Finding | Condition |
|---|---|
| `"floating structural asset"` | Structural role has no attachment target |
| `"architectural asset in cluster"` | doorway/beam/column inside furniture cluster |
| `"doorway placed on floor center"` | Doorway targeting floor/floor_center |
| `"beam treated as decoration"` | Beam role in decoration list |
| `"fireplace placed as free-standing"` | Fireplace not attached to wall face |

### 50.10 Pipeline insertion point

Insert `hou_mcp_structural_classifier` after geometry analysis and before layout:

```
Asset Import
→ Geometry Extraction (hou_mcp_geometry_analyze)
→ Asset Metrics
→ Structural Classification  ← NEW (Tier 10.3)
→ Structural Placement Intent
→ Suitability Ranking (hou_mcp_asset_ranking)
→ Semantic Layout (hou_mcp_layout_cluster)
→ Layout Realization (hou_mcp_realize_layout)
→ Collision Solver
→ Constraint Solver
→ Scene Application (hou_mcp_apply_layout)
```

Structural assets split off at the Structural Classification step and route directly to `EnvironmentStructureBuilder` / `OpeningBuilder` / `BeamBuilder` / `FloorBuilder`. They never enter the furniture layout pipeline.

### 50.11 Test conventions

- Reset ALL 7 singletons in `autouse` fixture (classifier + geometry_detector + metadata_classifier + affinity + placement_rules + review + stats)
- No bridge calls, no network calls, no randomness
- Test all 9 canonical validation scenarios from §50.7
- Test environment affinity: stone arch conf ≤ 0.50 in western_room, conf ≥ 0.88 in castle_hall
- Test metadata override: "wooden beam" keyword → beam regardless of geometry
- Test placement_type fast path: `placement_type="fireplace"` → fireplace conf ≥ 0.92
- Test review blocking findings explicitly (beam in decoration list, doorway in cluster)
- 7 test files in `tests/unit/`: `test_geometry_role_detector.py`, `test_metadata_role_classifier.py`, `test_environment_structural_affinity.py`, `test_structural_placement_rules.py`, `test_structural_asset_classifier.py`, `test_structural_review.py`, `test_structural_statistics.py`

---

## 54. Reality Intelligence (Tier 15.0+)

Tier 15.0+ upgrades the runtime from a placement engine to a Senior Environment Artist / Layout TD / Level Designer / Set Dresser / Houdini Pipeline TD. The goal is NOT to pass tests — it is believable, physically plausible, human-designed environments. Visual realism, functional logic and spatial storytelling take priority over audit scores.

**Core rule:** never ask "Can I place this asset?" — always ask "Would a human intentionally place this asset here?" If the answer is no, reject the placement.

**Reality First Rule:** the viewport is the source of truth — not metadata, not planner output, not audit scores, not relationship graphs. After realization, inspect actual Houdini geometry. If geometry contradicts metadata: **GEOMETRY WINS**.

**Non-negotiable design rules:**
1. Only `geometry_inspector.py` and `correction_applier.py` touch the Houdini bridge — every other module is pure, deterministic planning.
2. No randomness. Same scene always produces the same result.
3. Never raises in public methods — errors in result dicts.
4. Singleton pattern — `get_X()` + `reset_X_for_tests()` on every module.
5. Thread-safe (`threading.Lock` per instance).
6. `dataclass` + `to_dict()` pattern on all result classes.
7. The Correction Pass modifies ACTUAL Houdini geometry (via CorrectionApplier) — not metadata, not plans.
8. `production_ready` requires ALL nine success criteria — visual believability is the final authority. Passing tests alone is not success.

### 54.1 Module layout

```
src/runtime/reality/
    __init__.py                          ← full re-export of all public surface
    reality_scene_model.py               ← SceneAsset + SceneSnapshot + parse_scene + raycast_down + canonical infer_asset_type
    human_reasoning_engine.py            ← AssetJustification + HumanReasoningEngine (6 questions per asset)
    functional_zone_builder.py           ← FunctionalZone + FunctionalZonePlan + FunctionalZoneBuilder (no orphans)
    support_rule_engine.py               ← SUPPORT_REQUIREMENTS + SupportRuleEngine (§54 support table)
    floating_object_detector.py          ← FloatingViolation + FloatingObjectDetector (raycast_down, auto-relocation)
    beam_connection_validator.py         ← BeamConnection + BeamConnectionValidator (wall/column endpoint checks)
    architectural_integrity_validator.py ← IntegrityViolation + ArchitecturalIntegrityValidator (no fake doors/windows)
    density_engine.py                    ← DensityResult + EnvironmentDensityEngine (assets / room_area)
    composition_engine.py                ← FocalPoint + CompositionResult + CompositionEngine (focal points + negative space)
    correction_pass_engine.py            ← CorrectionOp + CorrectionPlan + RealityCorrectionPass (plans geometry fixes)
    geometry_inspector.py                ← ObservedScene + GeometryInspector (BRIDGE: reads real geometry; reconcile = GEOMETRY WINS)
    correction_applier.py                ← CorrectionApplyResult + CorrectionApplier (BRIDGE: applies fixes via set_parms)
    visual_review_engine.py              ← VisualReviewResult + VisualReviewEngine (9 criteria + 4 artist questions)
    reality_intelligence_engine.py       ← RealityIntelligenceResult + RealityIntelligenceEngine (main orchestrator)
    reality_statistics.py                ← RealityStatRecord + RealityStatistics (capped at 2000)
    reality_serializer.py                ← RealitySerializer (sorted-key JSON, schema 1.0.0)
```

### 54.2 Scene layout dict shape

All engines consume a ResolvedSceneLayout-style dict (Tier 9.9 `transforms` list works directly):

```python
{
    "environment": "western_room",          # optional — provides room dims
    "room_width": 10.0, "room_depth": 12.0, # optional overrides
    "openings": [{"kind": "door", "tx": 0.0, "tz": 5.97}],   # optional
    "transforms": [
        {"asset_id": "table_01", "asset_name": "Saloon Table",
         "tx": 0.0, "ty": 0.375, "tz": 0.0, "ry": 0.0,
         "bbox_half_x": 1.1, "bbox_half_y": 0.375, "bbox_half_z": 0.65},
    ],
}
```

Room is centred at the origin: walls at x=±width/2, z=±depth/2 (same convention as Tier 9.9/10.0). Missing bboxes fall back to per-type defaults.

### 54.3 Support rules (§54 table — BLOCKING)

| Asset type | Requires |
|---|---|
| bottle | table OR shelf OR bar |
| cup | table OR shelf |
| plate | table |
| lantern | table OR wall OR ceiling |
| chair | table OR desk OR fireplace OR bar (within 2.0 m) |
| stool | bar |
| fireplace | wall |
| window / door | wall opening (explicit `openings` entry, or wall-plane fallback) |

### 54.4 No Floating Objects Rule

Any asset with `bottom_y > floor + 0.10 m` must pass `raycast_down()` — support geometry directly beneath its centre within 0.10 m. Exempt: structural types (beam/column/wall/floor/ceiling/door/window), wall-mounted and ceiling-mounted assets. Failures are BLOCKING and carry `suggested_ty` (drop onto the best surface below, else the floor).

### 54.5 Beam Rule

Beam endpoints are computed along the major horizontal bbox axis (ry-rotated). Both endpoints must be within 0.5 m of a wall plane or a column footprint. Valid spans: wall-to-wall, column-to-wall, column-to-column. Anything else is `span_kind="floating"` → FLOATING_BEAM.

### 54.6 Density and composition

- `density_score = placed_assets / room_area`
- small room (< 150 m²) → 10–20 assets; medium (< 600 m²) → 20–40; large → 40–80
- Empty rooms are invalid; under target_min fails; over target_max warns (overcrowded)
- Every room needs a primary + secondary focal point (priority: fireplace > table > bar > machine > desk > bed) and ≥ 25% walkable negative space

### 54.7 Functional zones

`dining`, `fireplace`, `bar`, `work`, `sleeping`, `storage` built from anchors present in the scene; members assigned to the nearest compatible zone within its radius; `structure` and `wall_decor` catch architectural and wall-mounted assets. Anything left is an orphan → `no_orphans=False` (no orphan assets allowed).

### 54.8 Visual review — success criteria

`production_ready` requires ALL nine: physically_plausible, functionally_usable, architecturally_valid, visually_believable, compositionally_balanced, relationship_consistent, no_floating_objects, no_orphan_assets, no_impossible_placements. The four artist questions (artist_would_approve, production_game_quality, film_set_quality, human_would_use_room) are derived from the criteria. Grade: A ≥ 0.95, B ≥ 0.80, C ≥ 0.60, D ≥ 0.40, else F — but grade never overrides the all-criteria requirement.

### 54.9 Node IDs (all in `plugins/houdini/v_nodes_houdini/`)

| node_id | Purpose |
|---|---|
| `hou_mcp_reality_check` | Full §54 pipeline: scene (+optional observed geometry) → reality_json, production_ready, grade |
| `hou_mcp_functional_zones` | Build zones + orphan detection |
| `hou_mcp_support_validation` | §54 support table checks |
| `hou_mcp_floating_objects` | raycast_down floating detection + relocation suggestions |
| `hou_mcp_reality_correction` | Build correction plan; apply=true + node_path_map applies to LIVE Houdini geometry |
| `hou_mcp_visual_review` | Final artist review: 9 criteria + 4 artist questions |
| `hou_mcp_geometry_truth` | BRIDGE: inspect real geometry under a root; reconcile planned scene (GEOMETRY WINS) |

**Canonical workflow:** `hou_mcp_apply_layout` → `hou_mcp_geometry_truth` (observe) → `hou_mcp_reality_check` (with observed_scene_json) → `hou_mcp_reality_correction` (apply=true) → `hou_mcp_visual_review`

### 54.10 Capability IDs (added to `src/runtime/capability_registry.py`)

`reality_intelligence`, `human_reasoning`, `functional_zoning`, `support_rule_validation`, `floating_object_detection`, `beam_connection_validation`, `architectural_integrity`, `environment_density`, `scene_composition`, `reality_correction_pass`, `geometry_truth_inspection`, `visual_review`

### 54.11 Test conventions

- `tests/unit/conftest.py` provides the canonical production-ready `western_room_scene` fixture (19 assets: dining cluster, fireplace zone, storage corner, wall decor, wall-to-wall beams, real door/window) — it must grade A with all criteria met
- Reset ALL singletons in `autouse` fixtures (the orchestrator test resets all 14)
- No bridge calls in tests — `CorrectionApplier.build_op_dicts` for dry-run, `GeometryInspector.reconcile` is pure
- Test GEOMETRY WINS explicitly: planner says bottle on table, viewport says floor 3 m away → review must fail
- 10 test files in `tests/unit/`: `test_reality_scene_model.py`, `test_human_reasoning_engine.py`, `test_functional_zone_builder.py`, `test_support_rule_engine.py`, `test_floating_object_detector.py`, `test_beam_connection_validator.py`, `test_architectural_integrity_validator.py`, `test_density_composition.py`, `test_correction_pass_engine.py`, `test_reality_intelligence_engine.py`
