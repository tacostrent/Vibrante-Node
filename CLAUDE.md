# Vibrante-Node — Developer Guide for Claude

---

## INTERNAL DOCUMENT — VISIBILITY POLICY

This file is an **internal engineering and release orchestration document only**.

It must **NEVER** appear publicly in:
- website pages, HTML docs, markdown docs, generated docs, portal docs, API docs
- onboarding, README sections, tutorials, examples, release notes
- SEO metadata, navigation systems, help menus, search indexes
- generated static content, screenshots, code snippets, public references

**Do NOT:**
- mention `CLAUDE.md` in any public-facing content
- reference internal prompts or AI orchestration systems
- expose autonomous release engineering workflows or internal automation prompts
- expose internal implementation instructions

**If documentation generation scans repository files:**
- explicitly exclude `CLAUDE.md`
- exclude internal prompts and engineering orchestration instructions
- exclude autonomous release protocols

The public-facing ecosystem must expose **only** real technical documentation, real APIs, real workflows, real runtime architecture, real integrations, and real onboarding content. Docs must feel human-authored, professional, and technically authentic — not AI-prompt-generated or internally orchestrated.

---

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
| `v_nodes_dir` | `setup_env()` → path to `v_nodes_houdini/` **and/or** `EnvManager` config | `NodeRegistry.load_all_with_extras()` in `window.py` |
| `v_scripts_path` | `setup_env()` → path to `v_scripts_houdini/` **and/or** `EnvManager` config | `MainWindow._populate_scripts_menu()` in `window.py` |

**General-purpose**: `v_nodes_dir` and `v_scripts_path` are general-use variables, not Houdini-only. Users can configure them in Settings → Application Paths; `EnvManager.initialize()` merges those config paths with any values already set by Houdini's `setup_env()`. Both support multiple directories (os.pathsep-separated). Both consumers (`load_all_with_extras` and `_populate_scripts_menu`) already split on `os.pathsep`.

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

**Bug fixes (v2.1.0)**:
- `_autosave()` now strips the `"* "` dirty prefix from tab names before writing. Without this, a dirty tab named `"* my_graph.json"` was restored as `"[Recovered] * my_graph.json"`. Fix: `tab_name = tabText(i); if tab_name.startswith("* "): tab_name = tab_name[2:]`.
- `_try_restore_autosave()` now sets `scene._dirty = True` and emits `dirty_changed(True)` after `from_workflow_model()`. `from_workflow_model` suppresses `push_history` via `_undoing`, so restored tabs started with `_dirty = False` — no `*` marker, no save prompt on close. Recovered data is unsaved crash content and must be treated as dirty.

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

### 10.13 `window.py` — F5 / Shift+F5 shortcuts not wired
**Symptom**: Execute (F5) and Stop (Shift+F5) toolbar buttons showed the shortcuts in their tooltips but pressing the keys did nothing.  
**Fix**: Added `self.execute_btn.setShortcut("F5")` and `self.stop_btn.setShortcut("Shift+F5")` immediately after the `setToolTip` calls in `_init_toolbar()`.  
**File**: `src/ui/window.py`

### 10.14 `scene.py` — Type mismatch warning on port connection
**Feature**: When a user connects two ports whose types are incompatible (e.g. `string` → `float`), a `"warning"` level message is logged to the log panel immediately after the connection is made. The connection is still allowed — the warning is informational only.

**How it works:**
- `NodeScene._get_port_data_type(port)` — private helper that reads `.type` (PortModel) or `.data_type` (Port base class), falling back to `"any"`. Placed just above `_trigger_unplug`.
- `mouseReleaseEvent` — after `_trigger_plug(target_output, target_input)`, calls `_get_port_data_type` on both ports and logs if neither side is `"any"` and the types differ:
  ```
  Type mismatch: 'NodeA.result' (string) → 'NodeB.count' (int)
  ```
- `"any"` is always compatible (exec flow ports use `type="any"`). Same types always pass silently.  
**File**: `src/ui/canvas/scene.py`

### 10.15 Unsaved-Changes Detection (tab `*` marker + close prompts)

**Feature**: Any edit to a workflow marks its tab with a `*` prefix (e.g. `* my_graph.json`). Closing a dirty tab or the whole app shows a Save / Discard / Cancel dialog per dirty tab.

**How it works:**

`src/ui/canvas/scene.py`:
- `NodeScene.dirty_changed = Signal(bool)` — class-level signal emitted when clean↔dirty state transitions.
- `NodeScene._dirty = False` — initialised in `__init__`.
- `push_history()` — after appending the snapshot, if `_dirty` was `False` it sets it to `True` and emits `dirty_changed(True)`. Subsequent edits are no-ops (signal only fires on clean→dirty transition).
- `mark_clean()` — sets `_dirty = False` and emits `dirty_changed(False)`. Called by `MainWindow` after a successful save.

`src/ui/window.py`:
- `add_new_workflow()` — connects `scene.dirty_changed` to `lambda dirty, v=view: self._update_tab_dirty_marker(v, dirty)`.
- `_update_tab_dirty_marker(view, dirty)` — finds the tab index for `view`, prepends `"* "` when dirty, strips it when clean. No-op if already in the correct state.
- `save_workflow()` / `save_workflow_as()` — call `scene.mark_clean()` immediately after `setTabText(...)`.
- `_close_tab(index)` — before `removeTab`, if `scene._dirty`: shows QMessageBox(Save|Discard|Cancel). Save → calls `save_workflow()`; if still dirty (dialog cancelled) → aborts close. Cancel → aborts close. Discard → proceeds.
- `closeEvent()` — loops all tabs before `_save_user_settings()`; same Save/Discard/Cancel logic per dirty tab; calls `event.ignore()` and returns early on Save-cancelled or Cancel.

**Invariants:**
- Load / autosave-restore → scene starts with `_dirty = False` (data matches disk).
- Undo/redo do NOT call `mark_clean()` — once dirty, only an explicit save cleans the tab.
- Subgraph tabs participate in the same mechanism (edits propagate via `push_history`).
- `from_workflow_model()` saves and restores `_undoing` around its body (`_prev_undoing = self._undoing; self._undoing = True … self._undoing = _prev_undoing`). This suppresses all nested `push_history` calls (from `connect_nodes`, `add_sticky_note`, `add_backdrop`) so loading a file never sets `_dirty = True`. `undo()`/`redo()` already set `_undoing = True` before calling `from_workflow_model`, so the save/restore is a safe no-op in those paths.

### 10.16 `scripting_console.py` — theme not applied on theme switch

**Symptom**: Switching to the light theme left the Scripting Console's code editor, debug output panel, and Git status panel still rendering with the dark palette.

**Root causes**:
1. `debug_output` and `git_status` `QTextEdit`s had hardcoded dark-theme stylesheets set at construction time (`"background-color: #282a36; …"`) and were never updated on theme change.
2. `_cascade_editor_theme()` in `window.py` only searches for `QsciScintilla` children; if QScintilla is not installed it returns early, leaving the fallback `QPlainTextEdit`-based `CodeEditor` untouched.

**Fix**:
- Added `ScriptingConsole.apply_theme(is_dark: bool)` in `src/ui/scripting_console.py` that:
  - Delegates to `self.editor.apply_theme(is_dark)` (handles both QScintilla and fallback implementations).
  - Switches `debug_output` and `git_status` between the dark (`#282a36`/`#f8f8f2`) and light (`#fafafa`/`#383a42`) palettes.
- In `src/ui/window.py`, `_apply_dark_theme()` and `_apply_light_theme()` now call `self.scripting_console.apply_theme(is_dark)` alongside the existing panel calls, before `_cascade_editor_theme()` runs.

**Files**: `src/ui/scripting_console.py`, `src/ui/window.py`

### 10.17 `vibrante_node.spec` — "Unknown publisher" on Windows 11

**Symptom**: Running `Vibrante-Node.exe` on Windows 11 shows "Unknown publisher" in the security dialog and the file Properties → Details tab contains no company, product, or version metadata.

**Root cause**: `EXE()` in `vibrante_node.spec` had no `version=` parameter, so PyInstaller built the exe without a Windows `VERSIONINFO` resource. Windows reads this resource to populate publisher metadata; without it, the OS displays "Unknown publisher".

**Fix**: Added `file_version_info.txt` (PyInstaller `VSVersionInfo` format) and wired it into the spec:
```python
# vibrante_node.spec — EXE() call
version='file_version_info.txt',   # Embeds VERSIONINFO — fixes "Unknown publisher" on Windows 11
```
`file_version_info.txt` embeds: `CompanyName=Vibrante-Node`, `ProductName=Vibrante-Node`, `FileVersion=2.1.1.0`, `LegalCopyright=Copyright (C) 2024-2026 Mahmoud Kamal (KamalTD)`.

**Limitation**: Windows SmartScreen and UAC elevation dialogs ("orange shield") still show "Unknown publisher" because those require a trusted Authenticode signature. VERSIONINFO fixes the Properties → Details metadata only. Authenticode signing is handled separately (see below).

**Authenticode signing** (removes "Unknown publisher" from security dialogs):

- `tools/create_dev_cert.ps1` — creates a self-signed code signing cert and trusts it in `CurrentUser\Trusted Root CA`. Changes "Unknown publisher" → "Vibrante-Node Dev" on the local machine. Self-signed certs are NOT trusted by Windows SmartScreen for other users.
- `tools/sign_release.ps1` — signs the built exe with the best available cert in the cert store. Pass `-Thumbprint` to target a specific cert.

```
# Dev/testing (local machine only):
powershell -ExecutionPolicy Bypass -File tools\create_dev_cert.ps1
powershell -ExecutionPolicy Bypass -File tools\sign_release.ps1

# Release (requires commercial OV or EV cert installed in cert store):
powershell -ExecutionPolicy Bypass -File tools\sign_release.ps1
```

OV cert (~$100-200/yr): removes "Unknown publisher" from SmartScreen after ~100 clean downloads.  
EV cert (~$300-500/yr): removes "Unknown publisher" from SmartScreen immediately.

**Maintenance rule**: When bumping the app version, update both `filevers`/`prodvers` tuples and the `FileVersion`/`ProductVersion` strings in `file_version_info.txt` to keep them in sync with the version shown in the About dialog (`src/ui/window.py`).

**Files**: `file_version_info.txt`, `vibrante_node.spec`, `tools/sign_release.ps1`, `tools/create_dev_cert.ps1`

### 10.18 Documentation Build System — Release Maintenance Rules

**Context**: HTML docs are generated by `tools/build_docs.py` (simple docs) and `tools/build_docs_portal.py` (portal docs). Both scripts have hardcoded version strings that must be updated on every release.

**On every version bump, update ALL of the following:**

| File | What to change |
|---|---|
| `src/main.py` | `SplashScreen.VERSION = "vX.Y.Z"` |
| `src/ui/window.py` | About dialog `h3` string; add `("vX.Y.Z", "RELEASE_vX.Y.Z.md")` to release notes list |
| `file_version_info.txt` | `filevers`, `prodvers` tuples and `FileVersion`, `ProductVersion` strings |
| `vibrante_node.spec` | Comment on line 2 |
| `RELEASE_vX.Y.Z.md` | Create new release notes file at project root |
| `tools/build_docs.py` | Add `("RELEASE_vX.Y.Z.md", "Release Notes vX.Y.Z")` to top of `RELEASE_DOCS`; update `v2.x.x` in three template strings |
| `tools/build_docs_portal.py` | Update `v2.x.x` in four template strings |
| `docs_src/01_introduction.md` | Add row to version history table; add `RELEASE_vX.Y.Z.md` to docs map; update footer |
| `docs_src/02_getting_started.md` | Update title and footer |
| `docs_src/03_user_guide.md` | Update title and footer |
| `docs_src/05_node_development.md` | Update title |
| `docs_src/06_backend_architecture.md` | Update header |
| `docs_src/07_frontend_architecture.md` | Update header |
| `docs_src/09_advanced_topics.md` | Update header |
| `docs_src/11_troubleshooting.md` | Update opening paragraph |
| `CHANGELOG.md` | Add new `## [vX.Y.Z]` section at top |
| `README.md` | Add latest features under `## 🌟 Latest Enhancements`; update release notes link |

**After editing source files**, regenerate all HTML:
```bash
python tools/build_docs.py        # regenerates docs/ + docs/portal/
```

**Older release markdown files** (v1.0.5 through v1.8.3) live in `releases/` not root. The build script references them with the `releases/` prefix; new releases go at root.

**Files**: `tools/build_docs.py`, `tools/build_docs_portal.py`, `CHANGELOG.md`

### 10.19 `window.py` — About dialog LICENSE fallback with clickable link (exe builds)

**Context**: `LICENSE` is bundled in `vibrante_node.spec` as `('LICENSE', '.')` → placed in `_internal/` by PyInstaller. `resource_path('LICENSE')` resolves to `sys._MEIPASS/LICENSE` in the frozen exe and finds the file. The `license_is_fallback` branch is a safety net for dev environments where LICENSE might be absent.

**Previous behavior**: The fallback set plain text `"LICENSE file not found. See https://vibrante-node.com for full license terms."` via `setPlainText()` inside a monospace `QTextEdit` — URL was not clickable.

**Fix**: Added `license_is_fallback` boolean flag. When `True` (exe build, file missing), the widget uses `setHtml()` with a proper `<a href>` and `setOpenExternalLinks(True)` so the URL is clickable. When `False` (dev mode, file found), existing monospace `setPlainText()` behavior is unchanged.

**Widget type**: The license display widget is `QTextBrowser` (not `QTextEdit`). `QTextBrowser` is a subclass of `QTextEdit` and is the only Qt widget that supports both `setOpenExternalLinks(True)` and the full `QTextEdit` API (`setFont`, `setLineWrapMode`, `setPlainText`, `setHtml`). `QTextEdit` does NOT have `setOpenExternalLinks` — calling it crashes with `AttributeError`. Do not revert to `QTextEdit`.

**File**: `src/ui/window.py` — `_show_about()`

---

## 11. Settings & Environment Variable Architecture

### 11.1 EnvManager (`src/utils/env_manager.py`)

Singleton (matches `ConfigManager` pattern). Loaded once in `src/main.py` at startup.

```python
from src.utils.env_manager import env_manager
env_manager.initialize()   # called once at startup in main.py
```

**Config keys** (stored via existing `config.get/set` API in `~/.vibrante_node_config.json`):
- `env.vibrante_pythonpath` — `List[str]` of extra sys.path entries
- `env.v_nodes_dir` — `List[str]` of extra node directories (general-use, not Houdini-only)
- `env.v_scripts_path` — `List[str]` of extra script directories (general-use, not Houdini-only)
- `env.custom_variables` — `Dict[str, str]` of user-defined os.environ variables

**Key API**:
```python
# VIBRANTE_PYTHONPATH
env_manager.get_vibrante_pythonpath()         # → List[str]
env_manager.set_vibrante_pythonpath(paths)    # persists to config

# v_nodes_dir (multi-path, supports multiple extra node directories)
env_manager.get_v_nodes_dir()                 # → List[str]
env_manager.set_v_nodes_dir(paths)            # persists to config

# v_scripts_path (multi-path, supports multiple extra script directories)
env_manager.get_v_scripts_path()              # → List[str]
env_manager.set_v_scripts_path(paths)         # persists to config

# Custom variables
env_manager.get_custom_variables()            # → Dict[str, str]
env_manager.set_custom_variables(d)           # persists all
env_manager.set_custom_variable(name, value)  # set one
env_manager.remove_custom_variable(name)      # remove one
env_manager.get_custom_variable(name)         # → str | None

# Subprocess helper — returns a new dict, never mutates os.environ
env = env_manager.apply_to_subprocess_env(base_env=None)

# Re-apply after settings change at runtime
env_manager.reinitialize()
```

**Safety constraints**:
- `VIBRANTE_PYTHONPATH` injects into `sys.path` only (not `PYTHONPATH`). Does NOT overwrite existing `sys.path` entries.
- `v_nodes_dir` and `v_scripts_path` are **merged** into `os.environ` — existing values (e.g. set by Houdini's `setup_env()`) are preserved; config paths are appended as additional entries. No paths are dropped.
- Custom variables inject into `os.environ` at the process level — app-scoped only, not permanent.
- `apply_to_subprocess_env()` never mutates `os.environ` — returns a copy.
- Thread-safe via `threading.Lock`.

### 11.2 Settings Window (`src/ui/settings_window.py`)

`SettingsWindow(QDialog)` — opened via Edit → Preferences… (Ctrl+,) from `MainWindow._open_settings()`.

**Sidebar pages:**

| Page | Contents |
|------|----------|
| Python Runtime | VIBRANTE_PYTHONPATH editor (one path per line) + Browse button + sys.path preview |
| Application Paths | `v_nodes_dir` and `v_scripts_path` editors (one path per line each) + Browse buttons. Node changes require restart; script changes apply via Scripts → Refresh Scripts. |
| Environment Variables | QTableWidget of custom Name/Value pairs with Add/Remove |
| Vibrante Variables | Read-only table of built-in Vibrante-Node env vars (`_VIBRANTE_BUILTIN_VARS`) with current `os.environ` values + Refresh button. Does NOT include `v_nodes_dir`/`v_scripts_path` (those are on Application Paths). |

**General page**: `_build_general_page()` is preserved in the file but **not wired** to the sidebar/stacked widget — hidden for future use.

**Save flow**: validates paths (warn-on-missing, not block) → validates variable names (alphanumeric + underscore) → calls `env_manager.set_vibrante_pythonpath()` + `env_manager.set_custom_variables()` → calls `env_manager.reinitialize()` → `accept()`.

### 11.3 Startup sequence (main.py)

```python
_apply_pythonpath()          # existing: reads system PYTHONPATH env var
_register_houdini_dlls()     # existing: registers HFS DLL dirs
env_manager.initialize()     # NEW: injects VIBRANTE_PYTHONPATH + custom vars
```

Order matters: `env_manager.initialize()` runs after the existing bootstraps and before Qt / MainWindow are imported.

### 11.4 Accessing variables in nodes

Custom variables are standard `os.environ` entries after `initialize()`. Nodes access them normally:

```python
import os
studio_root = os.environ.get("STUDIO_ROOT", "")
```

VIBRANTE_PYTHONPATH entries are in `sys.path`, so `import mylib` works without any special node code.

### 11.5 What NOT to do with EnvManager

- Do NOT call `env_manager.initialize()` from node `execute()` — it runs once at startup only.
- Do NOT read `config.get("env.*")` directly in node code — use `os.environ` for custom vars, `sys.path` for Python paths.
- Do NOT call `apply_to_subprocess_env()` and then assign its result to `os.environ` — that would mutate the shared process environment.

---

### 10.20 `node_widget.py` — Typing crash: Qt thread violation in reactive propagation (v2.1.2+)

**Symptom**: App crashes when typing in a node's text input (e.g. Message Node) while it is wired to a downstream node (e.g. Console Print).

**Root cause**: `_update_param` and `set_parameter` called `_propagate_all_outputs()` directly inside the `_run_then_propagate` async coroutine. That coroutine runs on the `AsyncRuntime` background thread. `_propagate_all_outputs` accesses `scene().edges` and calls Qt widget methods (`w.blockSignals()`, `w.setText()`, `w.setValue()`) — all of which are Qt threading violations when called from a non-main thread.

**Fix**: `_propagate_all_outputs` is now dispatched to the Qt main thread via `_main_dispatcher.post(self._propagate_all_outputs)`. `_MainThreadDispatcher` is a module-level `QObject` whose `pyqtSignal` is connected with `Qt.QueuedConnection`. Qt automatically routes the signal delivery to the receiver's thread (main thread) when emitted from a background thread. The `_is_propagating` re-entry guard was moved from the coroutine into `_propagate_all_outputs` itself (with try/finally), so it still prevents double-propagation if `_propagate_all_outputs` is queued multiple times before executing.

**Files**: `src/ui/node_widget.py`

**Test**: `tests/unit/test_reactive_propagation.py` — `test_reactive_propagation_runs_on_main_thread` directly verifies the thread via a patch on `_propagate_all_outputs`.

### 10.21 `window.py` — Settings changes not applied in the same session (v2.1.2+)

**Symptom**: After clicking OK in the Settings dialog (Edit → Preferences), changes to `v_nodes_dir`, `v_scripts_path`, and custom variables took effect only on the next application launch. The Library panel did not refresh and new script paths were not added to the Scripts menu.

**Root cause**: `_open_settings()` called `dialog.exec_()` but discarded the return value, so it never checked whether the user clicked OK or Cancel. No refresh logic ran at all after the dialog closed.

**Fix**: Check `dialog.exec_() == QDialog.Accepted`. On accept, call:
1. `NodeRegistry.load_all_with_extras(resource_path('nodes'))` — picks up new `v_nodes_dir` paths
2. `NodeRegistry._load_directory(self.nodes_dir)` — reloads user node dir if it exists
3. `self.library_panel.refresh()` — updates the Library panel UI
4. `self._populate_scripts_menu()` — rebuilds the Scripts menu from updated `v_scripts_path`
5. `self.log_panel.log("[Settings] Settings saved and applied.", "info")` — user feedback

Also added `QDialog` to the top-level `PyQt5.QtWidgets` import at line 7.

**Files**: `src/ui/window.py` — `_open_settings()`

**Test**: `tests/unit/test_settings_persistence.py` — `test_open_settings_refreshes_library_and_scripts_on_accept` and `test_open_settings_no_refresh_on_cancel`.

### 10.22 `settings_window.py` — Import / Export settings to file (v2.1.2+)

**Feature**: Two buttons at the bottom-left of the Settings dialog: **Import Settings…** and **Export Settings…**. Allows saving all settings to a portable JSON file and restoring them on another machine or after a reinstall.

**Data layer** (`src/utils/env_manager.py`):
- `env_manager.export_settings()` → `dict` with keys `vibrante_pythonpath`, `v_nodes_dir`, `v_scripts_path`, `custom_variables`. Pure read — does not mutate state.
- `env_manager.import_settings(data: dict)` → persists all 4 groups via the existing `set_*` methods. Unknown keys are silently ignored for forward-compatibility. Each key is type-checked before calling `set_*` (list or dict as appropriate).

**UI layer** (`src/ui/settings_window.py`):
- **Import Settings…**: opens a `QFileDialog` for a `.json` file → reads JSON → validates it is a `dict` → populates all four UI widgets (text editors + variable table) without saving. The user reviews and clicks OK to persist.
- **Export Settings…**: opens a `QFileDialog` (save) → reads current UI widget state (not saved config) → writes JSON with `indent=2`. Captures unsaved edits so "export what I see" semantics are preserved.
- Both buttons show a `QMessageBox.critical` on file I/O errors.

**File format**:
```json
{
  "vibrante_pythonpath": ["C:/MyLibs/python"],
  "v_nodes_dir": ["C:/MyStudio/nodes"],
  "v_scripts_path": ["C:/MyStudio/scripts"],
  "custom_variables": {"STUDIO_ROOT": "/studio"}
}
```

**Files**: `src/utils/env_manager.py`, `src/ui/settings_window.py`

**Tests**: `tests/unit/test_settings_persistence.py` — `test_export_settings_returns_all_required_keys`, `test_export_settings_reflects_current_state`, `test_import_settings_applies_values`, `test_import_settings_ignores_unknown_keys`, `test_settings_file_round_trip`.

### 10.23 v2.2.0 Release Maintenance Rules

**Version**: v2.2.0 — Released 2026-05-15
**Type**: Minor

All version update targets as per section 10.18 have been updated for v2.2.0. Key items for future reference:

- `file_version_info.txt` tuples map directly to semver: `(MAJOR, MINOR, PATCH, 0)` — e.g. v2.2.0 → `(2, 2, 0, 0)`, v2.2.1 → `(2, 2, 1, 0)`.
- `tools/build_docs.py` and `tools/build_docs_portal.py` are in `.gitignore` as a directory path but tracked individually — use `git add -f tools/build_docs.py tools/build_docs_portal.py` when staging.
- Build artifacts live in `dist/Vibrante-Node-v{ver}-Windows-x64.zip`. GitHub release upload requires `gh auth login` first.

### 10.24 v2.2.1 Release Maintenance Rules

**Version**: v2.2.1 — Released 2026-05-15
**Type**: Patch — exe build bug fixes only

All version update targets as per section 10.18 have been updated for v2.2.1. Key fixes recorded in this release:

- `QTextEdit` → `QTextBrowser` in `_show_about()` — `QTextEdit` does not have `setOpenExternalLinks()`. `QTextBrowser` is the drop-in subclass that supports both `setOpenExternalLinks(True)` and the full `QTextEdit` API. **Never revert to `QTextEdit` for the license panel.**
- `LICENSE` added to PyInstaller `datas` as `('LICENSE', '.')` → lands in `_internal/`. `resource_path('LICENSE')` resolves to `sys._MEIPASS/LICENSE` in the frozen exe. Both the fallback branch and the real file path now work correctly in the exe.

### 10.25 `window.py` — "Load Node from JSON" crash when nodes directory absent

**Symptom**: Nodes → Load Node from JSON… → select any valid node JSON → `[Errno 2] No such file or directory: '…\nodes\<node_id>.json'` error dialog. The node appears to load (registry validation passes) but the install step fails.

**Root cause**: `load_node_json()` called `shutil.copy2(file_path, dest_path)` where `dest_path` is inside `self.nodes_dir` (`<app_dir>/nodes/`). That directory is never created automatically when running the compiled exe from a fresh location — startup only calls `_load_directory(self.nodes_dir)` if `os.path.isdir(self.nodes_dir)` is already true. No creation code existed for the user-writable nodes directory.

**Fix** (3 lines added in `load_node_json()`, `src/ui/window.py`):
```python
os.makedirs(self.nodes_dir, exist_ok=True)          # create dir if absent
shutil.copy2(file_path, dest_path)
NodeRegistry._source_paths[node_id] = dest_path     # reload targets installed copy
```
`os.makedirs(..., exist_ok=True)` is idempotent — no-op if the directory already exists.

**`_source_paths` update**: After copying, the registry's source path for the node is updated to `dest_path`. Without this, "Reload Selected Node" in the current session would target the original file location (wherever the user selected it from), rather than the installed copy in the user's node directory. This could silently fail if the original file is later moved or deleted.

**Do not** create `self.nodes_dir` at `__init__` time — the directory should only be created on first actual use (lazy creation) to avoid leaving an empty `nodes/` folder for users who never use this feature.

**File**: `src/ui/window.py` — `load_node_json()`

### 10.26 `window.py` — "Load Node From JSON" opened a workflow tab on first use

**Symptom**: First use of Nodes → Load Node from JSON… resulted in a workflow tab opening instead of the node appearing in the library. Selecting a workflow `.json` file showed no clear error, or the dialog silently misdirected the user.

**Root causes** (two independent issues):

1. **Wrong initial directory**: `QFileDialog.getOpenFileName` was called with `dir=""`. On Windows, Qt's native file dialog inherits the shell's last-visited directory from any previous dialog in the same process. If `Load Workflow` (which starts in `"workflows"`) had been used earlier, `Load Node From JSON` would also open in `workflows/`, presenting workflow files to the user.

2. **No content pre-check**: If the user selected a workflow file, `NodeRegistry.load_node()` would return `False` with a raw Pydantic `ValidationError` — no message indicating it was a workflow file. The user could misread the failure or accidentally trigger the File → Load Workflow path separately.

**Fix** (`src/ui/window.py` — `load_node_json()`):

```python
# Start in user nodes dir (predictable; does not inherit workflow dir)
start_dir = self.nodes_dir if os.path.isdir(self.nodes_dir) else os.path.expanduser("~")
file_path, _ = QFileDialog.getOpenFileName(self, "Load Node JSON", start_dir, "Node Files (*.json)")

# Content pre-check before touching the registry
with open(file_path, "r", encoding="utf-8") as _f:
    _raw = json.load(_f)
if not isinstance(_raw, dict) or "node_id" not in _raw or "python_code" not in _raw:
    if isinstance(_raw, dict) and ("nodes" in _raw or "connections" in _raw):
        QMessageBox.critical(self, "Wrong File Type",
            "This is a workflow file, not a node definition.\n\n"
            "Use File → Load Workflow to open workflow files.")
    else:
        QMessageBox.critical(self, "Invalid Node File",
            "The selected file is missing required node fields ('node_id' and/or 'python_code').")
    return
```

**Invariants**:
- The `nodes_dir` starting directory is only used once it exists (lazy — same policy as section 10.25).
- The pre-check reads the file exactly once; `NodeRegistry.load_node()` re-reads it internally. No double-parse overhead in the happy path since the pre-check only runs before the expensive registry call.
- The `"nodes"` / `"connections"` heuristic correctly identifies standard workflow JSONs. Custom files that have neither key but are still missing `node_id`/`python_code` fall into the generic "missing required fields" branch.

**File**: `src/ui/window.py` — `load_node_json()`

### 10.27 `window.py` — "Load Workflow" silently accepted node JSON files

**Symptom**: `[INFO] Workflow loaded: …/website_examples/http_request.json` — selecting a node definition file through File → Load Workflow created an empty workflow tab with no error. `WorkflowModel.model_validate_json()` accepts any valid JSON (all fields optional, extras ignored).

**Root cause**: `load_workflow()` and `_load_workflow_from_path()` passed `json_data` directly to `WorkflowModel.model_validate_json()` without first checking whether the file was actually a workflow. Node JSON files (which have `node_id` and `python_code` at the top level) produce a valid but empty `WorkflowModel`.

**Fix** (`src/ui/window.py`):

Added one shared private helper and applied the pre-check to both callers:

```python
@staticmethod
def _looks_like_node_json(raw) -> bool:
    return isinstance(raw, dict) and "node_id" in raw and "python_code" in raw
```

Inserted between the empty-file guard and `model_validate_json` in both `load_workflow()` and `_load_workflow_from_path()`:

```python
try:
    _raw = json.loads(json_data)
    if self._looks_like_node_json(_raw):
        QMessageBox.critical(self, "Wrong File Type",
            "This is a node definition file, not a workflow.\n\n"
            "Use Nodes → Load Node From JSON to install it.")
        self.log_panel.log(f"Rejected node JSON selected as workflow: {file_path}", "warning")
        return
except json.JSONDecodeError:
    pass  # handled by model_validate_json below
```

**Invariants**:
- Uses the already-read `json_data` string — no extra file I/O.
- `json.JSONDecodeError` is intentionally swallowed: `model_validate_json` raises its own exception for malformed JSON, caught by the existing handler.
- Symmetric with 10.26: `load_node_json` detects workflow files; `load_workflow` / `_load_workflow_from_path` detect node files — bidirectional cross-protection.

**Files**: `src/ui/window.py` — `_looks_like_node_json()`, `load_workflow()`, `_load_workflow_from_path()`

### 10.28 `node_builder.py` — Edit Node corrupts exec port types

**Symptom**: Opening any hand-written node JSON for editing via Node Builder, then saving, changes the type of `exec_in` / `exec_out` — or adds a duplicate `add_input("exec_in", "any")` alongside the `add_exec_input("exec_in")` call.

**Root cause**: `_load_existing_node()` passed `defn.inputs` / `defn.outputs` directly to `_update_table()`. Hand-written node JSONs list `exec_in` and `exec_out` in their arrays (type `any`). Once those rows appear in the ports table, `_sync_ui_to_code()` regenerates the `[AUTO-GENERATED-PORTS-START]` block and emits `self.add_input("exec_in", "any")` alongside the `self.add_exec_input("exec_in")` line that the exec checkbox generates. The two calls conflict; if the user changes the type combo for that row before the 1-second debounce clears it, the exec port is permanently saved with the wrong type.

**Fix** — three locations in `src/ui/node_builder.py`:

1. **`_load_existing_node()`** — filter before populating tables:
```python
_exec_names = {"exec_in", "exec_out"}
self._update_table(self.inputs_table, [p for p in defn.inputs if p.name not in _exec_names])
self._update_table(self.outputs_table, [p for p in defn.outputs if p.name not in _exec_names])
```

2. **`_sync_code_to_ui()`** — filter AST results before updating tables (catches exec ports injected by a prior buggy round-trip):
```python
_exec_names = {"exec_in", "exec_out"}
input_list = [(k, v[0], v[1]) for k, v in inputs.items() if k not in _exec_names]
output_list = [(k, v[0], v[1]) for k, v in outputs.items() if k not in _exec_names]
```

3. **`save_node()`** — defensive guard so exec ports can never enter the JSON arrays regardless of table state:
```python
if not name or name in seen_inputs or name in {"exec_in", "exec_out"}: continue
# ... (same pattern for outputs)
```

**Invariant**: `exec_in` and `exec_out` are exclusively owned by the exec checkboxes + `add_exec_input` / `add_exec_output` calls. They must never appear as table rows or in the `inputs` / `outputs` JSON arrays.

**File**: `src/ui/node_builder.py` — `_load_existing_node()`, `_sync_code_to_ui()`, `save_node()`

### 10.29 `node_builder.py` — Edit Node silently cleared all `PortModel.default` values

**Symptom**: Opening any node for editing via Node Builder and saving reset every port's `default` value to `null` — regardless of what was in the original JSON.

**Root cause**: The port tables had 4 columns (Name, Type, Widget, Options) with no Default column. `_update_table()` read `name`, `type`, `widget_type`, and `options` from `PortModel` but ignored `default`. `save_node()` constructed `PortModel(…)` without a `default=` argument, so every round-trip through the editor silently zeroed all defaults.

**Fix** — five locations in `src/ui/node_builder.py`:

| Location | Change |
|---|---|
| `_init_ui()` | Tables: 4 → 5 columns; header added `"Default"` at index 4 |
| `_update_table()` | Reads `p.default`, writes `str(value)` or `""` to column 4 |
| `_add_row()` | Initialises column 4 with empty `QTableWidgetItem` |
| `save_node()` | Reads column 4 text for both inputs and outputs; passes `default=value or None` to `PortModel` |
| `get_node_definition()` | Reads column 4; includes `"default"` key in the returned port dict when non-empty |

**Invariants**:
- Default values are stored as strings in the table; `None` is stored as `""` and round-trips back to `None`.
- When `_sync_code_to_ui()` rebuilds the table from AST (no default info in Python code), the Default column is cleared — consistent with how Options is also cleared on port list changes. This is acceptable: defaults come from the JSON definition, not the Python code.
- `get_node_definition()` (used by Gemini chat context) now also surfaces defaults.

**File**: `src/ui/node_builder.py` — `_init_ui()`, `_update_table()`, `_add_row()`, `save_node()`, `get_node_definition()`

### 10.30 `node_builder.py` — Icon path change incorrectly mutated exec ports, `init_first`, and `use_exec`

**Symptom**: Changing the icon path field (typing or using the browse button) unexpectedly modified `init_first`, `use_exec`, and exec input/output port settings in the generated code.

**Root cause**: `icon_edit.textChanged` was connected to `lambda: self._sync_ui_to_code(update_exec_hints=False)`. `_sync_ui_to_code` is a full pipeline that always runs — regardless of flags — the AUTO-GENERATED-PORTS rebuild, exec-line strip/re-inject, `init_first` insertion/update, `use_exec` rewrite inside `super().__init__()`, and class-name/name-attribute sync. Every keystroke in the icon field triggered all of this, causing `super().__init__()` to be rewritten to `super().__init__(use_exec=True)`, `init_first = False` to be inserted if absent, and exec port lines to be stripped and re-emitted.

**Fix**: Replaced the `icon_edit.textChanged` connection with a dedicated `_sync_icon_to_code()` method that performs exactly one operation — update the `self.icon_path = …` assignment line via a single `re.sub` — and returns. It reads no other UI state and writes no other code.

```python
def _sync_icon_to_code(self):
    if self._is_syncing:
        return
    self._is_syncing = True
    try:
        code = self.code_edit.toPlainText()
        icon_val = self.icon_edit.text().strip()
        icon_replacement = f'self.icon_path = "{icon_val}"' if icon_val else 'self.icon_path = None'
        new_code = re.sub(r'self\.icon_path\s*=\s*(?:"[^"]*"|None)', icon_replacement, code)
        if new_code != code:
            self.code_edit.setPlainText(new_code)
    finally:
        self._is_syncing = False
```

**Invariant**: `_sync_ui_to_code` still syncs `icon_path` at its end — so any other UI change (table, exec checkbox, metadata) also keeps the icon line correct. `_sync_icon_to_code` is only called from `icon_edit.textChanged`; nothing else routes through it.

**File**: `src/ui/node_builder.py` — `__init__` (signal re-wire), `_sync_icon_to_code()` (new method)

### 10.31 `http_request` node — UI freezes during execution

**Symptom**: Running the `http_request` node caused the application window to become unresponsive for the full duration of the HTTP request (could be 1–30 s).

**Root cause**: The `_EventLoopRunner` drives the asyncio event loop on the **main Qt thread** via a zero-interval QTimer stepping approach. The original node used `aiohttp` as the primary HTTP path. `aiohttp` makes synchronous OS-level calls during connection setup on Windows (SSL certificate store access, IOCP binding) that execute synchronously inside the stepped event loop, blocking the Qt main thread. The `urllib` fallback used `asyncio.to_thread` (Python ≥ 3.9 only), which is the correct direction but still interacts with the async I/O poller.

**Fix**: Replaced both paths with a single approach that always runs the entire HTTP request (DNS → TCP connect → TLS → body read) in a thread pool via `loop.run_in_executor(None, _sync_do)` using stdlib `urllib.request`. The request is completely decoupled from the asyncio/Qt main thread — the event loop idles between steps while the thread works.

```python
loop = asyncio.get_running_loop()
status, text = await loop.run_in_executor(None, _sync_do)
```

**Additional improvement**: `urllib.error.HTTPError` now returns the actual response body (previously returned empty string on 4xx/5xx). The `headers` dict is defensively copied with `dict(...)` before `setdefault` to avoid mutating the caller's data.

**Do NOT revert to `aiohttp`** — it requires the event loop to run continuously, which is incompatible with the QTimer-stepped `_EventLoopRunner` architecture on Windows.

**Files**: `nodes/http_request.json`, `website_examples/http_request.json` — `python_code` field

### 10.32 `node_widget.py` + `view.py` — Drag trail of port connectors on canvas

**Symptom**: Dragging any node across the canvas left a persistent "trail" of port connector shapes (exec arrows, data circles) at every previous position. The trail remained until the canvas was fully redrawn.

**Root cause**: `NodeWidget.boundingRect()` returned `QRectF(0, 0, self.width, self.height)`. `PortWidget` children are positioned at x=0 (input ports) and x=self.width (output ports), and each draws its shape ±`radius` (6 px) from that centre — so exec arrows and data circles **paint 6 px outside the declared bounding rect on both sides**. Qt uses `boundingRect()` to decide which screen pixels to erase before a redraw. Pixels outside that rect are never invalidated → the trail persists across drag moves.

A secondary fix (setting `BoundingRectViewportUpdate`) was applied to `view.py` first but was insufficient on its own because the item's declared rect was still wrong.

**Fix** — three changes in `src/ui/node_widget.py`:

1. **`boundingRect()`**: Expand by ±8 px margin (port radius 6 + pen 1 + 1 safety) so Qt erases the full port overhang area on every drag step:
```python
def boundingRect(self):
    margin = 8  # port connectors extend 6px past node edges; +2 for pen and safety
    return QRectF(-margin, 0, self.width + margin * 2, self.height)
```

2. **`shape()` (new override)**: Returns the original body path so rubber-band selection and click hit-testing remain tight to the visible node body, not the expanded dirty rect:
```python
def shape(self):
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, self.width, self.height), 10, 10)
    return path
```

3. **`paint()`**: Replaced all three `self.boundingRect()` calls with a local `_r = QRectF(0, 0, self.width, self.height)` so the drawn rounded rect is still the correct visual size (not the expanded dirty rect).

**Invariant**: `boundingRect()` ≠ the drawn body rect. Always use `_r` (or `QRectF(0, 0, self.width, self.height)`) for any drawing in `paint()`. `boundingRect()` is exclusively for Qt's dirty-region / culling machinery.

**Files**: `src/ui/canvas/view.py` — `NodeView.__init__` (`setViewportUpdateMode`); `src/ui/node_widget.py` — `boundingRect()`, `shape()` (new), `paint()`

---

## 11. Autonomous Release Engineering Protocol

### Role & Mission

You act as Principal Software Architect, Staff Software Engineer, Release Engineer, Build Engineer, DevOps Engineer, QA Lead, and Technical Writer for every release cycle.

Your mission is to autonomously prepare a complete production-ready software release while preserving stability, backward compatibility, and repository consistency.

---

### Core Engineering Rules

**Surgical editing only.** Touch only what is necessary. Do not reformat unrelated code, rewrite unrelated comments, reorganize working systems, rename files/classes/functions, or perform broad refactors. All changes must be minimal and safe.

**Match existing style.** Follow the repository architecture and coding style exactly. Preserve naming conventions and structure. Maintain compatibility with existing systems.

**Clean only your own debris.** Remove unused imports/functions introduced by your changes. Do not clean unrelated legacy code.

---

### Phase 1 — Repository & Release Discovery

Identify:
- Latest stable git tag
- Release branch and previous release version
- All unreleased commits since the tag

```bash
git describe --tags --abbrev=0
git log <latest_tag>..HEAD --oneline
```

Also analyze: merged PRs, hotfix branches, reverted commits, release branches, semantic commit messages.

---

### Phase 2 — Repository-Wide Impact Analysis

Read and analyze: architecture docs, project maps, package manifests, build systems, CI/CD workflows, release scripts, installer configs.

Determine: affected modules, public API changes, internal-only changes, schema/config changes, serialization/file format changes, UI changes, dependency changes, compatibility risks.

---

### Phase 3 — Intelligent Change Classification

Classify all changes into: Features, Fixes, Improvements, Performance, Refactors, Security, Dependencies, Build/CI, Documentation, Breaking Changes, Deprecated Features.

Ignore: formatting-only commits, lint-only changes, merge noise, temporary debug commits, trivial typo-only changes.

---

### Phase 4 — Semantic Version Recommendation

| Bump | When |
|------|------|
| PATCH | fixes only |
| MINOR | backward-compatible features |
| MAJOR | breaking changes |

Also detect: hidden breaking changes, API/config/serialization incompatibilities, removed behaviors, dependency breakages.

---

### Phase 5 — Full Repository Version Synchronization

Search and update ALL old version references across the entire repository.

**Mandatory update targets (see also section 10.18 checklist):**

| Category | Targets |
|----------|---------|
| Application/UI | About window, splash screen, welcome screen, footer, settings/about dialogs, window titles, CLI `--version`, API version endpoints, tooltips |
| Documentation | `CHANGELOG.md`, `README.md`, docs/, tutorials, installation guides, migration guides, API docs, getting started guides, examples |
| HTML / Website | HTML docs, release banners, navbar/footer versions, SEO metadata, schema metadata, download links |
| Build / Packaging | `pyproject.toml`, `setup.py`, `file_version_info.txt`, `vibrante_node.spec`, installer configs, CI/CD variables, manifest files |

Ensure no stale version references remain anywhere.

---

### Phase 6 — Documentation & Release Notes Generation

Generate:
- **Developer Changelog** — detailed technical changelog
- **User-Facing Release Notes** — professional readable release notes
- **Migration Notes** — breaking changes, upgrade paths, deprecated APIs, required config/environment changes
- **Deployment Notes** — infrastructure changes, dependency upgrades, rebuild requirements, deployment warnings

---

### Phase 7 — Validation & Consistency Audit

Before finalizing, ensure:
- All versions match across UI/docs/builds/manifests
- No stale version references remain
- Generated docs regenerated
- API versions match binaries

Flag: TODO/FIXME/HACK additions, accidental debug code, experimental unfinished features, undocumented changes, missing tests, stale screenshots, deprecated APIs without warnings, hidden regressions, incomplete release notes.

---

### Phase 8 — Testing & Regression Safety

- Convert modifications into verifiable goals
- Write/update tests first (TDD where applicable)
- Confirm existing tests pass
- Verify old features still work, APIs remain compatible, UI remains functional, examples/docs still work, builds launch successfully

---

### Phase 9 — State Synchronization

Immediately update: `CLAUDE.md`, architecture docs, release docs, migration docs, project maps.

Document: deprecated systems, technical debt, postponed cleanup, compatibility layers.

---

### Phase 10 — Git Operations

Commit all changes (source, version updates, docs, changelog, generated docs, manifests, release assets) with semantic commit messages:

```bash
git commit -m "release: prepare vX.Y.Z"
git push origin <branch>
git push origin --tags
git tag -a vX.Y.Z -m "Release vX.Y.Z"
```

---

### Phase 11 — GitHub Release Creation

```bash
gh release create vX.Y.Z
```

Include: release title, semantic version, generated release notes, migration warnings, breaking changes, installation/update notes. Ensure correct tag attached and release notes formatted professionally.

---

### Phase 12 — Production Build Generation

The production build **MUST** use **Python 3.10**.

Validate: interpreter version, venv paths, dependency compatibility, compiled extension compatibility.

Generate: executable builds, installers, portable builds, wheel packages, standalone distributions.

Validate: startup, packaging integrity, embedded resources, dependency resolution, version metadata.

About window version must match release; no debug mode; no development configs; no temporary files.

---

### Phase 13 — Upload Release Artifacts

```bash
gh release upload vX.Y.Z build/*.zip
```

Ensure: filenames contain correct version, artifacts are production-ready, checksums generated if needed.

---

### Phase 14 — Final Release Readiness Audit

Before completion verify:
- GitHub release exists with artifacts uploaded and release notes attached
- Build uses Python 3.10
- No stale version references remain
- Tests pass
- Deployment and migration notes complete
- Docs, UI versions, and all routes synchronized
- No placeholder pages remain

---

### Required Final Output Format

```
Release Summary
- Previous Version:
- Suggested Version:
- Release Type:
- Risk Level:
- Release Status:

Key Changes
  Features:
  Fixes:
  Improvements:
  Performance:
  Refactors:
  Security:
  Breaking Changes:
  Deprecated Features:
  Dependencies:

Technical Impact Analysis
  Affected modules:
  API impact:
  Migration requirements:
  Deployment considerations:
  Compatibility risks:

Updated Files Report
  (list all modified source files, docs, HTML, manifests, installers, release assets, CI/CD files with WHY each was updated)

Remaining Manual Tasks
  (screenshots needing update, manual QA tasks, deployment tasks, unresolved risks, external store submissions)

Final Release Readiness Report
  (release ready / not ready; known risks; regression concerns; migration warnings; missing requirements)
```

---

### Critical Rules

- **NEVER** hallucinate repository changes — only report verified modifications.
- **NEVER** leave stale version references anywhere.
- **NEVER** update changelog alone — always synchronize docs/UI/build metadata.
- **ALWAYS** maintain backward compatibility unless intentionally changed.
- **ALWAYS** preserve repository architecture and style.
- **ALWAYS** validate before release.
- **ALWAYS** think before coding.
