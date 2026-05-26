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

### 10.33 v2.4.0 Release Maintenance Rules

**Version**: v2.4.0 — Released 2026-05-26
**Type**: Minor — New features, backward-compatible

All version update targets as per section 10.18 have been updated for v2.4.0. Key notes for future reference:

- `mcp_session.py` — `update_session(self, sid: str, **kwargs)` uses `sid` (not `session_id`) as the positional parameter to avoid collision when callers pass `session_id=` as a kwarg (non-mutable field test).
- Node ID renames: 11 bundled nodes renamed to prefixed IDs (`add`→`math_add`, `lowercase`→`string_lowercase`, etc.). Saved workflows that reference old IDs will fail to load those nodes. See RELEASE_v2.4.0.md for the full migration table.
- `concat` and `multiply` nodes removed — no direct replacement; use string/math alternatives.
- `mcp>=1.0.0` added as a required dependency. Run `pip install "mcp>=1.0.0"` after upgrade.
- `MCP_TOOL_NAMES` in `runtime_identity.py` is the authoritative source for the 12 tool names. Update it when adding new MCP tools; `runtime_prompt_context.py` `get_tool_guide()` and `test_mcp_tool_registry.py` `EXPECTED_TOOLS` must stay in sync.
- `build_docs.py` `RELEASE_DOCS` list already contains `RELEASE_v2.4.0.md` at index 0; new releases always go at the top.
- `src/__init__.py` and `vibrante_node/__init__.py` both carry `__version__` — update both on version bump.

---

## 11. Autonomous Release Engineering Protocol

### Role & Mission

You are a Principal Software Architect, Staff Software Engineer, Release Engineer, Build Engineer, DevOps Engineer, QA Lead, and Technical Writer.

Your mission is to autonomously prepare a complete production-ready software release while preserving stability, backward compatibility, and repository consistency.

You must:

1. Analyze all unreleased changes.
2. Detect differences between the latest stable release and current commits.
3. Determine the correct semantic version.
4. Synchronize ALL version references across the entire repository.
5. Update UI, docs, HTML, manifests, installers, and metadata.
6. Generate professional release notes and migration notes.
7. Validate release readiness.
8. Build production binaries using Python 3.10.
9. Commit, tag, push, create GitHub release, and upload artifacts.

You must NEVER perform uncontrolled refactors.

All changes must be surgical, minimal, and safe.

---

### Core Engineering Rules

#### Surgical Editing Rules

##### Touch Only What Is Necessary
- Do not reformat unrelated code.
- Do not rewrite unrelated comments.
- Do not reorganize working systems unless necessary.
- Do not rename files/classes/functions unless required.
- Do not perform broad refactors.

---

#### Match Existing Style
- Follow the repository architecture and coding style exactly.
- Preserve naming conventions and structure.
- Maintain compatibility with existing systems.

---

#### Clean Only Your Own Debris
- Remove unused imports/functions introduced by your changes.
- Do not clean unrelated legacy code.
- Do not silently remove deprecated systems.

---

### Phase 1 — Repository & Release Discovery

#### Detect Latest Stable Release

Identify:
- latest stable git tag
- release branch
- previous release version
- unreleased commits
- release comparison range

Use:
```bash
git describe --tags --abbrev=0
git log <latest_tag>..HEAD --oneline
```

Also analyze:
- merged PRs
- hotfix branches
- reverted commits
- release branches
- semantic commit messages

---

### Phase 2 — Repository-Wide Impact Analysis

Read and analyze:
- `CLAUDE.md`
- architecture docs
- project maps
- package manifests
- build systems
- CI/CD workflows
- release scripts
- installer configs

Determine:
- affected modules
- public API changes
- internal-only changes
- schema/database changes
- environment/config changes
- serialization/file format changes
- UI changes
- dependency changes
- deployment impact
- compatibility risks

---

### Phase 3 — Intelligent Change Classification

Classify all changes into:

- Features
- Fixes
- Improvements
- Performance
- Refactors
- Security
- Dependencies
- Build/CI
- Documentation
- Breaking Changes
- Deprecated Features

Ignore:
- formatting-only commits
- lint-only changes
- merge noise
- temporary debug commits
- trivial typo-only changes

Group related commits logically.

---

### Phase 4 — Semantic Version Recommendation

Recommend:
- PATCH
- MINOR
- MAJOR

Explain WHY.

Rules:
- PATCH → fixes only
- MINOR → backward-compatible features
- MAJOR → breaking changes

Also detect:
- hidden breaking changes
- API incompatibilities
- config incompatibilities
- serialization incompatibilities
- removed behaviors
- dependency breakages

---

### Phase 5 — Full Repository Version Synchronization

You MUST update ALL old version references across the ENTIRE repository.

Search for:
- hardcoded versions
- semantic versions
- release labels
- duplicated version constants
- metadata versions
- embedded UI versions
- hidden version strings

---

#### Mandatory Version Update Targets

##### Application/UI

Update:
- About window
- Splash screen
- Welcome screen
- Footer versions
- Settings/About dialogs
- Window titles
- Plugin manager
- Node editor labels
- CLI `--version`
- API version endpoints
- Tooltips/help dialogs
- Update dialogs

Ensure all displayed versions match.

---

##### Documentation

Update:
- `CHANGELOG.md`
- `README.md`
- docs/
- tutorials
- installation guides
- migration guides
- API documentation
- getting started guides
- examples/snippets
- generated docs
- release announcements

Also detect:
- outdated screenshots
- stale examples
- deprecated instructions
- old download URLs

---

##### HTML / Website / Static Pages

Update:
- HTML docs
- landing pages
- release banners
- navbar/footer versions
- SEO metadata
- schema metadata
- download links
- CDN references
- embedded script versions
- HTML docs Subpage

Ensure no stale version references remain.

---

##### Build / Packaging / Distribution

Update:
- `package.json`
- `pyproject.toml`
- `setup.py`
- `Cargo.toml`
- `CMakeLists.txt`
- installer configs
- Docker tags
- CI/CD variables
- manifest files
- NSIS/Inno installers
- build constants

Ensure all package/build versions match release version.

---

### Phase 6 — Documentation & Release Notes Generation

Generate:

#### Developer Changelog
Detailed technical changelog.

---

#### User-Facing Release Notes
Professional readable release notes.

---

#### Migration Notes
Explain:
- breaking changes
- upgrade paths
- deprecated APIs
- required config changes
- required environment changes
- compatibility concerns

---

#### Deployment Notes
Explain:
- infrastructure changes
- dependency upgrades
- rebuild requirements
- DB migrations
- cache invalidation
- deployment warnings

---

### Phase 7 — Validation & Consistency Audit

Before finalizing:

#### Validate Version Consistency

Ensure:
- all versions match
- no stale version references remain
- UI/docs/builds all match
- manifests match installers
- generated docs regenerated
- API versions match binaries

---

#### Detect Problems

Flag:
- TODO/FIXME/HACK additions
- accidental debug code
- experimental unfinished features
- undocumented changes
- missing tests
- stale screenshots
- deprecated APIs without warnings
- hidden regressions
- incomplete release notes

---

### Phase 8 — Testing & Regression Safety

#### Goal-Driven Development

Convert modifications into verifiable goals.

##### TDD Workflow
1. Write/update tests first.
2. Confirm tests fail.
3. Implement changes.
4. Confirm tests pass.

---

#### Regression Validation

Ensure:
- existing tests pass
- old features still work
- APIs remain compatible
- UI remains functional
- examples/docs still work
- builds launch successfully

---

### Phase 9 — State Synchronization

Immediately update:
- `CLAUDE.md`
- architecture docs
- release docs
- migration docs
- project maps

Document:
- deprecated systems
- technical debt
- postponed cleanup
- compatibility layers

---

### Phase 10 — Git Operations

After validations pass:

#### Commit All Changes

Commit:
- source modifications
- version updates
- docs updates
- changelog updates
- generated docs
- manifests
- release assets

Use semantic commit messages.

Example:
```bash
git commit -m "release: prepare vX.Y.Z"
```

---

#### Push Changes

Push:
- current branch
- release branches
- tags

Example:
```bash
git push origin <branch>
git push origin --tags
```

---

#### Create Release Tag

Create annotated git tag.

Example:
```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
```

Ensure:
- tag matches release version
- manifests/UI/docs all match tag

---

### Phase 11 — GitHub Release Creation

Automatically create GitHub Release.

Include:
- release title
- semantic version
- generated release notes
- migration warnings
- breaking changes
- installation/update notes

Ensure:
- correct tag attached
- draft/prerelease flags correct
- release notes formatted professionally

Use:
- GitHub CLI (`gh`)
- GitHub API
- or release automation systems

Example:
```bash
gh release create vX.Y.Z
```

---

### Phase 12 — Production Build Generation

#### Python Environment

The production build MUST use:

```text
Python 3.10
```

Validate:
- interpreter version
- venv paths
- dependency compatibility
- compiled extension compatibility

---

#### Build Requirements

Generate production-ready builds:
- executable builds
- installers
- portable builds
- wheel packages
- standalone distributions

Validate:
- startup
- packaging integrity
- embedded resources
- dependency resolution
- version metadata

---

#### Build Artifact Validation

Ensure:
- About window version matches release
- executable metadata matches release
- no debug mode enabled
- no development configs included
- no temporary files included

---

### Phase 13 — Upload Release Artifacts

Upload release artifacts to GitHub Release.

Examples:
- `.zip`
- `.exe`
- `.msi`
- `.whl`
- `.tar.gz`

Ensure:
- filenames contain correct version
- artifacts are production-ready
- old artifacts are not uploaded
- checksums generated if needed

Example:
```bash
gh release upload vX.Y.Z build/*.zip
```

---

### Phase 14 — Final Release Readiness Audit

Before completion verify:

- GitHub release exists
- artifacts uploaded successfully
- release notes attached
- builds downloadable
- build uses Python 3.10
- no stale version references remain
- tests pass
- deployment notes complete
- migration notes complete
- docs synchronized
- UI versions synchronized

---

### Required Final Output

#### Release Summary
- Previous Version:
- Suggested Version:
- Release Type:
- Risk Level:
- Release Status:

---

#### Key Changes

##### Features
- ...

##### Fixes
- ...

##### Improvements
- ...

##### Performance
- ...

##### Refactors
- ...

##### Security
- ...

##### Breaking Changes
- ...

##### Deprecated Features
- ...

##### Dependencies
- ...

---

#### Technical Impact Analysis

Include:
- affected modules
- API impact
- migration requirements
- deployment considerations
- compatibility risks
- database/schema impact

---

#### Updated Files Report

List ALL modified:
- source files
- docs
- HTML
- manifests
- installers
- release assets
- CI/CD files

Explain WHY each was updated.

---

#### Remaining Manual Tasks

List:
- screenshots needing update
- assets needing regeneration
- manual QA tasks
- deployment tasks
- unresolved risks
- external store submission tasks

---

#### Final Release Readiness Report

State:
- release ready / not ready
- known risks
- regression concerns
- migration warnings
- missing requirements

---

### Critical Rules

- NEVER hallucinate repository changes.
- ONLY report verified modifications.
- NEVER leave stale version references.
- NEVER update changelog alone.
- ALWAYS synchronize docs/UI/build metadata.
- ALWAYS maintain backward compatibility unless intentionally changed.
- ALWAYS preserve repository architecture/style.
- ALWAYS use surgical modifications only.
- ALWAYS validate before release.
- ALWAYS think before coding.

---

### Final Execution Command

Execution order:
1. Detect latest release
2. Analyze unreleased changes
3. Perform impact analysis
4. Recommend semantic version
5. Synchronize versions globally
6. Update UI/docs/build systems
7. Generate release notes
8. Run tests & validations
9. Build production version using Python 3.10
10. Commit all changes
11. Create release tag
12. Push commits & tags
13. Create GitHub release
14. Upload release artifacts
15. Produce final release readiness report

---

Verify that:

- User Guide updated
- Developer Guide updated
- Technical Reference updated
- Automation API updated
- Node Builder API updated
- Portal Docs updated
- sidebar navigation updated
- Help menu synchronized
- website pages
- HTML docs
- markdown docs
- generated docs
- portal docs
- API docs
- onboarding
- README sections
- tutorials
- examples
- release notes
- SEO metadata
- navigation systems
- help menus
- search indexes
- generated static content
- screenshots
- code snippets
- public references
- all routes accessible
- no placeholder pages remain

Think carefully before modifying anything.

---

## 12. Runtime Layer & MCP Integration (Tier 1)

The `src/runtime/` module is the orchestration seam between graph nodes and the underlying DCC bridges / external MCP servers. It exists so new agent-facing features compose semantic operations + structured context + (future) transactions on top of the raw bridge, rather than every node calling `get_bridge()` directly.

The architecture is intentionally **AI → Runtime → Graph → MCP → Houdini**, not **AI → Houdini**. MCP is treated as **transport + capability discovery only** — intelligence stays in the runtime.

### 12.1 Design rules (non-negotiable)

1. **MCP is transport only.** Never delegate scene understanding or graph planning to MCP. Intelligence lives in `src/runtime/`.
2. **No arbitrary Python execution as the default path.** No new agent-facing `execute_python(code)` style nodes. Semantic tool calls + validated specs only. The existing `run_code` bridge method stays available but the runtime layer does NOT expose it as a primary AI-facing tool.
3. **Context first.** `hou_mcp_scene_context` is the linchpin — agents read structured scene state before acting.
4. **Runtime stability first.** Async safety, reconnect, timeouts, transactions, caching all land before any AI planning or dynamic tool discovery. Tiers 2–4 are deferred until Tier 1 is proven.

### 12.2 Module layout

```
src/runtime/
    __init__.py          ← re-exports mcp_runtime, houdini_runtime, scene_cache
    mcp_runtime.py       ← long-lived MCP client session registry (Phase 1)
    houdini_runtime.py   ← semantic Houdini ops: scene_context + build_node_chain (Phases 3–4)
    scene_cache.py       ← per-run TTL cache (Phase 3)
```

Future tiers add `transaction_manager.py`, `execution_history.py`, and per-DCC modules (`maya_runtime.py`, `blender_runtime.py`) at this same layer — keep DCC interaction here, not in node `python_code`, so the eventual multi-DCC story works without rewriting nodes.

### 12.3 MCP runtime (`src.runtime.mcp_runtime`)

Async-first registry of MCP `ClientSession`s. Supports two transports:

```python
# stdio: launch a subprocess speaking MCP over stdin/stdout
await mcp_runtime.register_server(
    "everything", "stdio",
    {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"], "env": None},
)

# sse: connect to a running HTTP/SSE server
await mcp_runtime.register_server(
    "remote", "sse",
    {"url": "https://mcp.example.com/sse", "headers": {"Authorization": "Bearer …"}},
)
```

Public async API:

| Function | Purpose |
|---|---|
| `register_server(name, transport, config)` | Open + cache a session by `name`. Idempotent — re-running with the same name is a no-op. |
| `list_tools(server_name)` | `[{"name", "description", "inputSchema"}, …]` |
| `call_tool(server_name, tool_name, arguments)` | `{"result", "result_json", "is_error"}` — content blocks are flattened to JSON-serialisable dicts |
| `shutdown_server(name)` / `shutdown_all()` | Async teardown |
| `shutdown_all_sync()` | Sync wrapper for `MainWindow.closeEvent` |

**Lifecycle constraint:** the long-lived async-context-manager for each transport is held open inside a background task on Vibrante's existing event loop (the one `_EventLoopRunner` steps from the Qt main thread, CLAUDE.md §10.20). Sessions persist across graph executions. They are torn down only by `shutdown_server` / `shutdown_all`.

**Per-call timeout:** 30 s default. Override via env var `VIBRANTE_MCP_TIMEOUT` or by passing `_timeout_sec` inside the `arguments` dict (the runtime strips it before forwarding).

**Hard rule:** do not call MCP SDK transports from node `python_code` directly. Always go through `mcp_runtime` so session caching, timeout handling, and shutdown remain consistent.

### 12.4 Scene cache (`src.runtime.scene_cache`)

Thread-safe in-memory cache with monotonic-clock TTL + prefix invalidation. Used by `houdini_runtime.scene_context()` to dedupe bridge reads inside a single execution.

```python
from src.runtime.scene_cache import get_scene_cache
cache = get_scene_cache()
cache.set("scene_context::scene", {…}, ttl_sec=5.0)
cache.get("scene_context::scene")
cache.invalidate("scene_context::")   # called after every mutating op
```

**Rule:** any new runtime function that mutates Houdini state MUST call `get_scene_cache().invalidate("scene_context::")` (or a more specific prefix) before returning success. `build_node_chain` already does this — copy the pattern.

### 12.5 Houdini runtime (`src.runtime.houdini_runtime`)

#### `scene_context(include_selection=True, include_assets=True, include_render=True, force_refresh=False)`

Returns one **shape-stable** dict suitable for LLM prompts. Every key is always present even when empty — that stability is what makes the output safe to template into prompts.

```json
{
  "scene":     {"hip_file", "hip_name", "houdini_version", "fps", "frame", "frame_range"},
  "selection": [{"path", "type", "category"}, …],
  "networks":  {"obj":[…], "mat":[…], "out":[…], "stage"?:[…], "tasks"?:[…], …},
  "assets":    {"hda_files": [path, …], "definitions": [{"name", "label", "file", "category"}, …]},
  "render":    {"render_nodes": [{"path", "type"}, …]}
}
```

- Optional networks (`stage`, `tasks`, `shop`, `vex`, `ch`) only appear when the corresponding `/network` exists; the four core networks (`obj`, `mat`, `out`) and the four top-level keys are always present.
- Selection is empty in headless / batch Houdini (the bridge handler catches the missing `hou.selectedNodes` gracefully — see §6.7 fallback pattern).
- Render-node classification uses a hard-coded set (`karma`, `mantra`, `ifd`, `opengl`, `arnold`, `redshift_rop`, `vray_renderer`, `usdrender_rop`, `lop_render`, `ris`). Extend the set in `_fetch_render` if your studio uses other ROP types.

#### `build_node_chain(spec)`

Declarative, validated, transactional-ish creation. Spec shape:

```python
{
    "intent": "string (free-form label, used for logs only)",
    "nodes": [
        {"id": "n1", "parent": "/obj/geo1", "type": "sphere", "name": "src",
         "params": {"radx": 2.0}},
        ...
    ],
    "connections": [
        {"from": "n1", "to": "n2", "out": 0, "in": 0},
        ...
    ],
    "layout": True,
    "cook": False,
}
```

Execution order: **validate → create → param → connect → layout → cook**. On any failure, returns `{"ok": False, "error": "...", "created_paths": [...], "id_to_path": {...}}` with the partial state intact so a future transaction node (Tier 3) can roll it back. **No automatic rollback in Tier 1.**

Validation rejects: missing required fields, duplicate node ids, connections that reference unknown ids, parents that don't exist in the scene.

### 12.6 New bridge methods (Phase 3 prerequisites)

| Client `hou_bridge.py` | Server `vibrante_hou_server.py` | Purpose |
|---|---|---|
| `bridge.get_selection()` | `_cmd_get_selection` | Selected node paths; `[]` in headless |
| `bridge.network_summary(path)` | `_cmd_network_summary` | Children with `{name, type, path, category}` in one round-trip — avoids the children + node_info per-child pattern |

Both follow the deferred-main-thread + ValueError-on-missing pattern documented in §6.7. The runtime layer prefers `network_summary` over `children` for performance; if a future server build omits the new handler, `_safe_network_summary` transparently falls back to `children`.

### 12.7 Tier 1 nodes

The 5 nodes are split by their dependency on Houdini. Generic MCP client nodes are DCC-agnostic and ship in the bundled `nodes/` folder; Houdini-specific AI nodes need the live bridge and ship under the Houdini plugin's `v_nodes_houdini/` folder (loaded via the `v_nodes_dir` env var only when the Houdini plugin is installed — see §6.3 / §6.4).

| node_id | Category | Location | Purpose |
|---|---|---|---|
| `mcp_server_init` | MCP | `nodes/` | Configure + open an MCP session; cached by `server_name` |
| `mcp_list_tools` | MCP | `nodes/` | Enumerate tools on a registered server |
| `mcp_call_tool` | MCP | `nodes/` | Invoke a tool with JSON arguments |
| `hou_mcp_scene_context` | Houdini | `plugins/houdini/v_nodes_houdini/` | The linchpin: structured scene snapshot for AI agents |
| `hou_mcp_build_node_chain` | Houdini | `plugins/houdini/v_nodes_houdini/` | Build a Houdini network from a JSON spec |

**Rationale for the split:**
- The generic `mcp_*` nodes can call any MCP server from any workflow — no Houdini dependency, so they belong in the bundled set every user gets.
- The `hou_mcp_*` nodes import `from src.runtime import houdini_runtime`, which uses `hou_bridge`. They only function when launched from Houdini, so shipping them with the Houdini plugin keeps the bundled node list lean for users on other DCCs.

**Naming convention:**
- `mcp_*` — generic, DCC-agnostic MCP client primitives. Always `category: "MCP"`.
- `hou_mcp_*` — Houdini-specific AI-facing semantic operations. Always `category: "Houdini"`.
- Existing `houdini_*` / `houdini_action_*` nodes (bridge primitives and headless action builders) are unchanged — the new layer rides on top, it does not replace them.

**Connection convention:** MCP nodes resolve their server by string `server_name` from the registry (mirrors the Prism `resolve_prism_core` auto-resolution pattern from §8.1). The connection is not a wire-able object — you do not pass a "client" handle between nodes.

### 12.8 Shutdown lifecycle

`MainWindow.closeEvent` in `src/ui/window.py` calls `mcp_runtime.shutdown_all_sync()` after `_save_user_settings()` and autosave removal. `shutdown_all_sync` is idempotent and no-ops when no sessions exist. Without this, stdio MCP servers would leak as zombie subprocesses on app close.

When adding new long-lived runtime resources (Tier 3 transactions, future per-DCC sessions), wire their teardown into the same closeEvent block.

### 12.9 Test conventions

| File | Coverage |
|---|---|
| `tests/unit/test_mcp_runtime.py` | Registry CRUD + result shaping with mocked sessions (no real MCP transport) |
| `tests/unit/test_houdini_runtime.py` | scene_context shape + build_node_chain validation with a `FakeBridge` injected via `monkeypatch.setattr(bridge_module, "get_bridge", lambda: fake)` |
| `tests/unit/test_houdini_mcp_nodes.py` | Per-node JSON schema + class registration + port presence for all 5 nodes. Holds an explicit `_NODE_PATHS` map because the 5 files live in two locations (`nodes/` + `plugins/houdini/v_nodes_houdini/`) and the second is not on the default discovery path. |
| `tests/unit/test_all_workflows.py` | Auto-discovers the 3 bundled `mcp_*` files from `nodes/`. The 2 Houdini plugin files are intentionally NOT discovered here — they're covered by `test_houdini_mcp_nodes.py` which explicitly loads the plugin folder. |

**Pattern for new runtime tests:** monkey-patch the bridge module (`src.utils.hou_bridge`), not `bridge.get_bridge` directly — the runtime imports the module and resolves `get_bridge()` lazily, so the test patch needs to land on the module attribute.

### 12.10 Roadmap (Tier 1 done — see §13 for Tier 2, plan file for Tiers 3–4)

- ~~**Tier 2** — transaction system + rollback + graph diff + dirty tracking~~ ✓ implemented (see §13)
- **Tier 3** — `hou_mcp_create_material`, `hou_mcp_execute_hda` (semantic execution; needs new bridge methods for HDA install/list); HIP-level snapshots to make `delete_node` rollbacks recoverable
- **Tier 4** — `ai_intent_parser`, `ai_graph_planner`, dynamic MCP node generation from tool schemas

Each later tier plugs into the same runtime seam.

---

## 13. Runtime Layer & MCP Integration (Tier 2)

Tier 2 adds the **transactional execution boundary** that the AI-Plan → Execution flow has to pass through. Without it, an AI plan that fails halfway through leaves Houdini in a partial state. With it, the runtime captures a per-op rollback snapshot, walks operations in reverse on failure, and reports a structured graph diff back to the caller.

### 13.1 New runtime modules

```
src/runtime/
    transaction_manager.py    ← Tier 2: lifecycle + history + DCC-agnostic rollback dispatch
    scene_cache.py            ← extended with dirty scene tracking
    houdini_runtime.py        ← extended with execute_operation + per-op rollback handlers
```

`src/runtime/__init__.py` import order is load-bearing — `houdini_runtime` registers its rollback handlers with `transaction_manager` at import time. The `__init__.py` imports `transaction_manager` first, then `houdini_runtime` (via `noqa: F401`), so the handler table is populated before any node code runs.

### 13.2 Transaction model

A transaction is a structured dict:

```python
{
    "id":             "uuid4 string",
    "name":           "user-provided label",
    "created_at":     1700000000.0,
    "committed_at":   None | float,
    "rolled_back_at": None | float,
    "status":         "pending" | "committed" | "rolled_back" | "failed",
    "operations":     [recorded_op, ...],
    "snapshots":      [op["snapshot"], ...],   # convenience view
    "metadata":       {...},
    "dirty_nodes":    [path, ...],
    "errors":         [{"op": ..., "error": ...}, ...],
}
```

Each **recorded operation**:

```python
{
    "op":        "create_node" | "set_parms" | ... ,
    "params":    {...},                # the original op args
    "result":    {...},                # what the executor returned
    "snapshot":  {...},                # op-specific data for rollback
    "status":    "ok" | "failed",
    "error":     "..."                 # only when status == "failed"
    "dirty":     [path, ...],          # paths this op mutated (for diff)
    "timestamp": 1700000000.0,
}
```

### 13.3 Lifecycle (`transaction_manager.TransactionManager`)

```
begin_transaction(name) → txn_id (pending)
    ↓
record_operation(txn_id, op)         # one per executed op
    ↓
┌─→ commit_transaction(txn_id) → committed   (success path)
│
└─→ rollback_transaction(txn_id) → rolled_back  (calls handlers in reverse)
    │
    └─→ mark_failed(txn_id, error) → failed   (no rollback — record failure only)
```

State-transition rules:
- `record_operation` only works on `pending` transactions
- `commit_transaction` only works on `pending`; transitions to `committed`
- `rollback_transaction` works on `pending` or `failed`; transitions to `rolled_back`
- `mark_failed` works on `pending` only; transitions to `failed`
- Each non-pending state is terminal

### 13.4 Rollback dispatch (DCC-agnostic)

`transaction_manager` knows nothing about Houdini. Rollback is dispatched via a module-level handler registry:

```python
from src.runtime import transaction_manager
transaction_manager.register_rollback_handler("create_node", _rollback_create_node)
```

Handlers are `async`, receive the full recorded operation dict, and must return `{"ok": bool, "error"?: str, ...}`. **They MUST NOT raise** — if they do, the manager captures the exception into `rollback_errors` and continues with the next operation. Rollback never crashes the runtime.

`houdini_runtime._register_rollback_handlers()` runs at module import time and wires handlers for every op in `SUPPORTED_OPS`. Future per-DCC modules (e.g. `maya_runtime.py`) register their own handlers the same way.

### 13.5 Supported operations (`houdini_runtime.SUPPORTED_OPS`)

| op | reversible? | snapshot captures | rollback behaviour |
|---|---|---|---|
| `create_node` | yes | new path | `delete_node(path)` |
| `set_parms` | yes (per-key) | prev value per key | `set_parm(node, key, prev)` for each captured |
| `connect_nodes` | yes (best-effort) | previous input source path on the target | restore prior connection if any, else `setInput(idx, None)` |
| `delete_node` | **no** (Tier 2 limit) | `node_info` snapshot for diagnostics | reports `"cannot restore deleted node"` cleanly |
| `set_display_flag` | yes | prev flag state (via `run_code`) | set flag back |
| `set_render_flag` | yes | prev flag state (via `run_code`) | set flag back |
| `cook_node` | n/a (read) | path | no-op |
| `layout_children` | n/a (visual) | path | no-op |
| `build_node_chain` | yes | all created paths from result | `delete_node` for each in reverse |

**Validation rules** (`houdini_runtime._validate_operation`):
- `op` must be one of `SUPPORTED_OPS`
- Per-op required fields enforced (e.g. `create_node` needs `parent` + `type`)
- `set_parms.parms` must be a dict
- `build_node_chain.spec` must be a dict

`hou_mcp_transaction` calls `_validate_operation` on every op BEFORE executing any of them, so a single bad op aborts the entire transaction with a clear error report (no partial mutations from a malformed plan).

### 13.6 Operation execution invariants

`houdini_runtime.execute_operation(op)`:
1. Validates the op shape — if bad, returns `status="failed"` with the validation error
2. Captures any rollback snapshot data the op needs (e.g. previous parm values, current connection source)
3. Executes the bridge call(s)
4. Marks dirty state via `scene_cache.mark_*`
5. Invalidates the `scene_context::*` cache so subsequent `scene_context()` calls reflect the mutation
6. Returns a recorded-operation dict ready for `record_operation`

Invariant: **`execute_operation` never raises.** Any bridge failure is captured into the returned dict's `status` / `error` fields.

**Internal use of `run_code`:** rollback snapshots for flags + connections need to read state that has no dedicated bridge method (e.g. `isDisplayFlagSet`, `node.inputs()`). The runtime layer uses `bridge.run_code` internally for these reads. This is **infrastructure-only** — there is no `run_python` operation type exposed to AI agents, by design (see §13.10).

### 13.7 Dirty scene tracking (`scene_cache`)

The cache now carries a six-category dirty ledger:

```python
{
    "modified":             set[str],      # parameter / attribute changes
    "created":              set[str],
    "deleted":              set[str],
    "cooked":               set[str],
    "connections_changed":  set[(from, to, in_idx)],
    "flags_changed":        set[str],
}
```

API:
```python
cache.mark_node_dirty(path)
cache.mark_node_created(path)
cache.mark_node_deleted(path)
cache.mark_node_cooked(path)
cache.mark_connection_changed(from_path, to_path, in_idx=0)
cache.mark_flag_changed(path)
cache.get_dirty_nodes() -> dict[str, list]   # sorted, JSON-friendly snapshot
cache.clear_dirty_state()
```

**Rules:**
- The ledger holds **paths only** — never full node state. It is a lightweight indicator, not a snapshot.
- It is updated **by executors** when they mutate; nothing else writes to it. Never query the bridge to populate it.
- `mark_node_deleted(path)` supersedes earlier `created` / `modified` / `cooked` / `flags_changed` entries for the same path (deleted means gone — no point reporting it as also modified).
- `mark_node_created(path)` discards any prior `deleted` mark on the same path (re-created in the same session).
- `get_dirty_nodes()` returns sorted lists — output ordering must be deterministic for LLM prompts and audit logs.

### 13.8 Graph diff node (`hou_mcp_graph_diff`)

Reads the dirty ledger and returns a structured diff. No bridge calls — pure cache read. `clear_after_read=true` (default) drains the ledger so the next diff starts fresh.

Output:
```json
{
  "created":             [...],
  "deleted":             [...],
  "modified":            [...],
  "cooked":              [...],
  "connections_changed": [{"from": "...", "to": "...", "in": 0}, ...],
  "flags_changed":       [...],
  "total_changes":       12
}
```

### 13.9 Transaction node (`hou_mcp_transaction`)

The user-facing execution boundary. Inputs:
- `transaction_name` (string)
- `operations` (string — JSON list of structured ops, or live list when wired)
- `dry_run` (bool) — validate only, no execution
- `auto_commit` (bool, default true) — commit on full success
- `rollback_on_error` (bool, default true) — roll back on the first failed op

Behaviour:
1. Clear the dirty-state ledger so the returned `graph_diff` reflects only this transaction
2. Parse + validate all ops up front — any validation error aborts before any mutation
3. If `dry_run`: return `status="validated"` with no executions
4. `begin_transaction(name, metadata)`
5. For each op: `execute_operation` → `record_operation`
6. On a failed op: stop the loop. If `rollback_on_error`, call `rollback_transaction`; otherwise `mark_failed`
7. On full success with `auto_commit`: `commit_transaction`
8. Return a structured report (`transaction_id`, `status`, `operations_executed`, `rollback_performed`, `errors`, `graph_diff`, `report_json`)

### 13.10 Execution safety rules (non-negotiable)

1. **No arbitrary Python operation type.** The runtime deliberately does not expose a `run_python` / `execute_code` op. Operations must remain structured, validated, deterministic. Internal `run_code` usage is allowed only as infrastructure (rollback snapshot reads).
2. **Validation before mutation.** Every op is shape-checked before the transaction begins executing. A malformed plan never causes a partial mutation.
3. **Rollback tolerance.** A failed rollback handler never crashes the runtime — errors are captured into `rollback_errors` and returned in the report.
4. **Dirty state baseline.** `hou_mcp_transaction` clears the dirty ledger before begin so `graph_diff` in the report reflects only the current transaction.
5. **Cache invalidation.** Every executor that mutates Houdini calls `scene_cache.invalidate("scene_context::")` so subsequent `scene_context()` calls reflect ground truth.

### 13.11 Node location conventions (codified)

Rules used by `tests/unit/test_houdini_mcp_nodes.py` (`test_generic_mcp_nodes_in_bundled_dir`, `test_houdini_mcp_nodes_in_plugin_dir`) — they fail loudly if a future PR puts a file in the wrong place.

**`nodes/`** — bundled with every install:
- Generic runtime / MCP-protocol nodes
- DCC-independent, reusable orchestration primitives
- Cross-DCC functionality
- Examples: `mcp_server_init`, `mcp_list_tools`, `mcp_call_tool`, the loops + sequence + variable builtins

**`plugins/houdini/v_nodes_houdini/`** — loaded only when the Houdini plugin is installed (via `v_nodes_dir` env var):
- Houdini-specific semantic nodes
- Anything that touches `hou_bridge` / `houdini_runtime`
- Scene / runtime operations on a live Houdini session
- Examples: every `hou_*` and `houdini_*` node (including `hou_mcp_scene_context`, `hou_mcp_build_node_chain`, `hou_mcp_graph_diff`, `hou_mcp_transaction`)

Future DCCs follow the same convention: `plugins/maya/v_nodes_maya/`, `plugins/blender/v_nodes_blender/`, etc.

### 13.12 Path-agnostic plugin discovery

`tests/unit/test_all_workflows.py::_discover_plugin_node_dirs()` automatically scans every `plugins/*/v_nodes_*` directory and loads them into the registry. Adding a new DCC plugin requires zero test changes — the test discovery is purely path-pattern driven. **Do not hardcode plugin paths anywhere new**; the convention is the contract.

### 13.13 Tier 2 test conventions

| File | Coverage |
|---|---|
| `tests/unit/test_transaction_manager.py` | 24 tests — lifecycle, rollback dispatch, history bounded cap, rollback-handler tolerance (raising handlers caught), end-to-end via mocked bridge for create / set_parms / delete failures |
| `tests/unit/test_graph_diff.py` | 18 tests — dirty-state semantics (delete supersedes, create-after-delete, empty-path ignored, sorted output), executor → dirty-state pipeline, the graph_diff node via the live registry |
| `tests/unit/test_houdini_mcp_nodes.py` | Extended to cover all 7 Tier-1+Tier-2 nodes via the `_NODE_PATHS` map |

**Pattern for transaction tests:** use the `fresh_manager` fixture (`reset_transaction_manager_for_tests()`) to guarantee a clean singleton between cases. Combine with the `fake_bridge` fixture that monkey-patches `src.utils.hou_bridge.get_bridge` to test end-to-end execute → record → rollback without a live Houdini.

### 13.14 Tier 2 deferred items (NOT in this work)

- **HIP-level snapshots** for full delete-rollback recoverability (currently `delete_node` rollback returns `{"ok": False, "error": "cannot restore..."}` cleanly)
- **Cross-transaction history persistence** — the bounded history is in-memory only (cap 200, drops oldest)
- **Multi-DCC runtime modules** — the dispatch table is ready; `maya_runtime.py` / `blender_runtime.py` would register their handlers the same way `houdini_runtime` does
- **AI planning layer** (Tier 4) — `ai_intent_parser` / `ai_graph_planner` would feed the transaction node; never call executors directly


---

## 14. Runtime Intelligence Layer (Tier 2.5)

Tier 2.5 adds **execution intelligence** on top of the Tier 2 transaction system — NOT AI autonomy. Every component is advisory and/or deterministic. No language model involvement; no autonomous decision-making.

```
AI request -> Execution Preview -> Validation Engine -> Transaction (Tier 2) -> Rollback
                                        | warns
                                  Dependency Graph
                                        | populates
                              Scene Cache Viz Data
                                        | persisted
                                  Audit Store
                                        ^ read by
                             Replay Transaction node
```

### 14.1 Dependency Graph (`src/runtime/dependency_graph.py`)

Lightweight, in-memory, thread-safe directed graph of inter-node dependencies.

**Dependency types:** `connection`, `parameter_reference`, `cook_dependency`, `display_dependency`, `render_dependency`

```python
from src.runtime.dependency_graph import get_dependency_graph

graph = get_dependency_graph()
graph.register_dependency("/obj/sphere1", "/obj/mountain1", "connection")
graph.get_downstream("/obj/sphere1")        # [{"source", "target", "type"}]
graph.get_upstream("/obj/mountain1")        # same shape
graph.get_affected_nodes(["/obj/sphere1"])  # BFS -> sorted list of affected paths
graph.get_cook_chain("/obj/sphere1")        # connection + cook_dependency edges only
graph.remove_node("/obj/old")              # wipes all incident edges
graph.clear()                              # full reset (scene reload)
graph.stats()                              # {"nodes_with_upstream", "nodes_with_downstream", "total_edges"}
graph.all_edges()                          # [{"source", "target", "type"}, ...]
```

**Edge direction:** source -> target means "target depends on source". BFS in `get_affected_nodes` walks downstream.

**Self-dependencies and empty paths are silently ignored.** Invalid dep_type raises `ValueError`.

**Singleton:** `get_dependency_graph()` / `reset_dependency_graph_for_tests()`.

### 14.2 Validation Engine (`src/runtime/validation_engine.py`)

Stateless pre-execution validator. Runs semantic checks before any mutation.

```python
from src.runtime.validation_engine import get_validation_engine

engine = get_validation_engine()
result = await engine.validate_operations(operations)
# result = {
#     "valid": bool,
#     "errors": [{"index", "op", "message"}],
#     "warnings": [{"index", "op", "message"}],
#     "risk_level": "low" | "medium" | "high",
#     "op_count": int,
#     "summary": str,
# }
```

**Checks performed:**
- Op shape (delegates to `houdini_runtime._validate_operation`)
- Self-connections -> error
- Dangerous deletes (downstream dependents in dependency graph) -> warning
- `build_node_chain` sub-spec validation (duplicate ids, self-connections, missing ids)
- Empty `parms` dict -> warning (no-op)
- Non-dict op items -> error

**Risk scoring (per-op weights, summed across batch):**

| Op | Weight |
|---|---|
| create_node, set_display_flag, set_render_flag, layout_children | 0 |
| set_parms, connect_nodes, cook_node | 1 |
| build_node_chain | 2 |
| delete_node | 10 |

`low` < 1, `medium` 1-9, `high` >= 10.

**The validation engine does NOT query the bridge.** It reads only the dependency graph and the op vocabulary.

### 14.3 Audit Store (`src/runtime/audit_store.py`)

Optional JSONL-backed persistent transaction audit trail.

```python
from src.runtime.audit_store import get_audit_store, AuditStore

store = get_audit_store()                              # default: ~/.vibrante_node_audit.jsonl
# or: AuditStore(path=None)                           # in-memory only (tests)

audit_id = await store.log_transaction(data)
record   = await store.get_transaction(txn_id)        # by id / transaction_id / audit_id
records  = await store.query_transactions(limit=100)  # newest first; status= filter available
pruned   = await store.compact()
store.stats()   # {"path", "records_in_memory", "write_count", ...}
```

**Storage invariants:**
- Lazy disk load (on first read or write)
- Disk writes via `asyncio.to_thread` — never block the event loop
- Write failures silently swallowed (audit must never block execution)
- `compact()` prunes by `max_age_days` (default 30) AND `max_records` (default 10,000)
- Auto-compact when buffer > 2 * max_records
- Atomic rewrite: `.tmp` file then `rename`
- Corrupt JSONL lines skipped on load

**Override path:** `VIBRANTE_AUDIT_PATH` env var or `path=` constructor argument.

**Singleton:** `get_audit_store()` / `reset_audit_store_for_tests()`.

### 14.4 Execution Scheduler (`src/runtime/execution_scheduler.py`)

Serialised FIFO mutation queue preventing concurrent bridge mutations.

```python
from src.runtime.execution_scheduler import get_execution_scheduler

scheduler = get_execution_scheduler()
result = await scheduler.enqueue(my_async_factory, transaction_id="txn-42")
# returns factory return value, or raises if factory raised

await scheduler.cancel("txn-42")  # True if found and marked; False if already running/done
scheduler.stats()   # {"running", "queue_size", "processed", "cancelled", "errors"}
```

**Architecture:**
- Single `asyncio.Queue` + single consumer pump coroutine
- `enqueue()` pushes item + returns a Future resolved when callable completes
- `cancel()` marks item; pump skips it and cancels its Future
- `start()` / `stop()` idempotent; `enqueue()` auto-starts if not running
- Pump exits cleanly on `__stop__` sentinel from `stop()`
- Exceptions propagate to the awaiting caller; pump continues

**Singleton:** `get_execution_scheduler()` / `reset_execution_scheduler_for_tests()`.

### 14.5 Scene Cache -- Graph Visualization Data

`SceneCache` now carries a third responsibility: graph-state metadata for display (data only, no rendering).

```python
cache = get_scene_cache()
cache.record_transaction_ownership(["/obj/geo1"], "txn-uuid")
cache.record_validation_warning("/obj/old", "downstream dependents will break")
data = cache.get_graph_visualization_data()
# {
#     "recently_modified": {path: timestamp},
#     "transaction_ownership": {path: txn_id},
#     "validation_warnings": {path: [warning, ...]},
# }
cache.clear_visualization_data()
```

All three dicts are guarded by `_viz_lock` (separate from `_dirty_lock` and `_lock`).

### 14.6 Transaction Manager -- Visualization Helpers

`TransactionManager` exposes `get_graph_visualization_data()` (synchronous):

```python
mgr = get_transaction_manager()
viz = mgr.get_graph_visualization_data()
# {
#     "pending_count": int,
#     "committed_count": int,
#     "rolled_back_count": int,
#     "failed_count": int,
#     "rollback_states": {txn_id: status},
#     "recent_names": [last 5 names, newest first],
# }
```

### 14.7 Houdini Node -- `hou_mcp_execution_preview`

**Location:** `plugins/houdini/v_nodes_houdini/hou_mcp_execution_preview.json`

Preview impact of a batch of operations WITHOUT mutating Houdini. Safe at any time.

Inputs: `operations` (JSON list), `include_dependencies` (bool), `estimate_cooks` (bool)

Outputs: `nodes_to_create`, `nodes_to_modify`, `nodes_to_delete`, `affected_nodes`, `estimated_cooks`, `risk_level`, `warnings`, `errors`, `dependency_impact`, `preview_json`

**No bridge calls. No dirty-state mutations. No transaction manager interaction.**

### 14.8 Houdini Node -- `hou_mcp_replay_transaction`

**Location:** `plugins/houdini/v_nodes_houdini/hou_mcp_replay_transaction.json`

Deterministically replay a previously recorded transaction.

Inputs: `transaction_id`, `dry_run` (bool), `rollback_on_error` (bool)

Outputs: `replayed`, `operations_executed`, `errors`, `graph_diff`, `status`, `report_json`

**Replay semantics:**
1. Reads stored ops from `TransactionManager.get_transaction(txn_id)` (params only, not snapshots)
2. Re-validates all ops via `ValidationEngine` before any execution
3. Begins a NEW transaction for the replay (new txn_id, name `replay_{txn_id[:8]}`)
4. Executes ops via `houdini_runtime.execute_operation` in original order
5. Commits or rolls back based on outcome

### 14.9 Tier 2.5 test conventions

| File | Coverage |
|---|---|
| `tests/unit/test_dependency_graph.py` | 42 tests -- register/remove/remove_node, BFS multi-hop/diamond, cook chain, clear/stats/all_edges, singleton |
| `tests/unit/test_validation_engine.py` | 22 tests -- risk levels, shape errors, self-connections, dangerous-delete warnings, build_node_chain sub-spec, singleton |
| `tests/unit/test_audit_store.py` | 20 tests -- log/get/query, disk round-trip, corrupt JSONL skipped, compact, in-memory-only, singleton |
| `tests/unit/test_scheduler.py` | 15 tests -- lifecycle, enqueue/FIFO/exception-propagation, cancel, stats, singleton |
| `tests/unit/test_execution_preview.py` | 18 tests -- node registration, no bridge calls, op classification, risk, dep impact, preview_json |
| `tests/unit/test_transaction_replay.py` | 16 tests -- error paths, empty txn, dry_run, replay, rollback-on-failure, report_json |

### 14.10 Tier 2.5 deferred items (NOT in this work)

- **Dependency graph population from live scene** -- currently populated only when ops execute; a "scan existing scene -> build graph" bridge call is Tier 3.
- **Auto-log to audit store from hou_mcp_transaction** -- intentionally not wired yet (requires path config).
- **Execution scheduler integration into hou_mcp_transaction** -- exists but not wired; concurrent callers should route through scheduler.
- **sqlite backend** for audit store (richer queries, range scans by timestamp/status).


---

## 15. Semantic Runtime Layer (Tier 2.75)

Tier 2.75 adds **deterministic semantic intelligence** on top of the Tier 2.5 intelligence layer. The key distinction from an "AI planning" layer is that all translation is deterministic Python â€” no LLMs, no dynamic decisions, no autonomous graph mutation. An LLM can *name* an intent; it cannot *execute* one without going through the full validation/constraint/transaction pipeline.

Architecture:
```
LLM (names intent only)
    â†’ SemanticRegistry (intent â†’ op list, deterministic)
    â†’ CapabilityRegistry (required capability check)
    â†’ RuntimeConstraints (policy gate)
    â†’ ValidationEngine (structural check)
    â†’ ResourceEstimator (cost estimate)
    â†’ ExecutionPlan (inspect, approve, optionally modify)
    â†’ SemanticExecutor.execute() â†’ TransactionManager â†’ houdini_runtime
    â†’ AuditStore (lineage)
```

**Non-negotiable:** `LLM â†’ direct graph mutation` is never permitted. The semantic layer is the mandatory choke point.

### 15.1 Capability Registry (`src.runtime.capability_registry`)

Dynamic registry of what the runtime can currently do. Pre-populated at import time with all built-in houdini ops, runtime services, DCC integrations, and known renderers.

Capability types: `houdini_op`, `runtime_service`, `semantic_operation`, `mcp_server`, `dcc_integration`, `renderer`

```python
from src.runtime.capability_registry import get_capability_registry

caps = get_capability_registry()
caps.register_capability("mcp_server", "my_server", {"url": "http://..."})
caps.supports("karma")       # True (built-in)
caps.query_capabilities(cap_type="renderer")
caps.deregister_capability("my_server")
```

Singleton: `get_capability_registry()` / `reset_capability_registry_for_tests()`.

### 15.2 Resource Estimator (`src.runtime.resource_estimator`)

Heuristic-only cost estimation. No bridge calls, no profiling.

```python
from src.runtime.resource_estimator import get_resource_estimator

est = get_resource_estimator()
est.estimate_operation({"op": "create_node", "type": "pyro"})
# â†’ {memory_impact: 0.85, cook_cost: 0.8, risk_level: "low", notes: [...]}

est.estimate_transaction(ops)
# â†’ {op_count, estimated_memory, estimated_cook_cost, risk_level, graph_complexity, per_op}

est.estimate_graph_complexity(n_nodes=20, n_connections=15)
# â†’ "high"
```

Risk weights mirror `validation_engine` for consistency (`create_node`=0, `set_parms`=1, `delete_node`=10). Simulation/volume node types bump memory and cook cost to 0.8+.

Singleton: `get_resource_estimator()` / `reset_resource_estimator_for_tests()`.

### 15.3 Runtime Constraints (`src.runtime.runtime_constraints`)

Policy-based gate that runs BEFORE the transaction system. Built-in policies always active:

| Policy id | Type | Rule |
|---|---|---|
| `_builtin_protect_stage` | `protected_path` | `/stage` and subpaths forbidden |
| `_builtin_protect_out` | `protected_path` | `/out` and subpaths forbidden |
| `_builtin_max_ops` | `max_ops` | Max 100 ops per transaction |

User-configurable policy types: `protected_path`, `forbidden_op`, `forbidden_node_type`, `max_ops`, `permission` (callable check).

Built-in policies cannot be removed (`remove_policy` returns `False` for them). Policy ids starting with `_builtin_` are reserved.

```python
from src.runtime.runtime_constraints import get_runtime_constraints

r = get_runtime_constraints()
r.add_policy("forbidden_node_type", "no_python", {"node_type": "python"})
r.validate_operation(op)         # {valid, violations}
r.validate_transaction(ops)     # {valid, violations, op_count}
```

Singleton: `get_runtime_constraints()` / `reset_runtime_constraints_for_tests()`.

### 15.4 Workflow Templates (`src.runtime.workflow_templates`)

Parameterised workflow blueprints with `{varname}` interpolation. Resolve to concrete op lists â€” no bridge calls, no side effects.

Built-in templates: `pyro_source`, `usd_export`, `karma_render`, `geometry_cache`, `asset_publish`, `vfx_container`, `solaris_lighting_setup`.

```python
from src.runtime.workflow_templates import get_workflow_templates

wt = get_workflow_templates()
wt.list_templates(tag="vfx")
ops = wt.apply_template("karma_render", {
    "name": "final_karma", "stage_path": "/stage",
    "output_path": "$HIP/render/$F4.exr",
    "res_x": "1920", "res_y": "1080",
})
```

Variable interpolation is recursive: `{varname}` in any string value (including nested dicts/lists) is substituted. Missing variables raise `KeyError` with a message listing provided keys.

Singleton: `get_workflow_templates()` / `reset_workflow_templates_for_tests()`.

### 15.5 Semantic Registry (`src.runtime.semantic_registry`)

Registry of named semantic operations. Each handler is a pure Python function: `context dict â†’ list[dict]`.

Built-in operations: `create_geo_container`, `build_pyro_source`, `setup_karma_renderer`, `export_to_usd`, `cache_geometry`, `asset_publish_scaffold`, `solaris_lighting_setup`.

```python
from src.runtime.semantic_registry import get_semantic_registry

r = get_semantic_registry()
r.register_operation("my_op", {"description": "...", "tags": ["custom"]},
    lambda ctx: [{"op": "create_node", "parent": ctx["parent"], "type": "geo"}]
)
plan = r.resolve_to_execution_plan("my_op", {"parent": "/obj"})
# â†’ {ok, operation_id, operations, op_count, error, metadata}
```

Handlers **MUST** be deterministic and free of side-effects. `handler` is never included in `get_operation()` / `list_operations()` output â€” metadata only.

Singleton: `get_semantic_registry()` / `reset_semantic_registry_for_tests()`.

### 15.6 Semantic Executor (`src.runtime.semantic_execution`)

Orchestrates the full translation + execution pipeline.

```python
from src.runtime.semantic_execution import get_semantic_executor

exec_ = get_semantic_executor()

# Translate only (no execution)
plan = await exec_.translate("build_pyro_source", {"parent": "/obj", "name": "fire"})

# Full execution
result = await exec_.execute("build_pyro_source", {"parent": "/obj", "name": "fire"},
    dry_run=False, auto_commit=True, rollback_on_error=True
)
```

Execution pipeline:
1. `SemanticRegistry.resolve_to_execution_plan` â€” intent â†’ op list
2. `CapabilityRegistry` â€” warn on missing required capabilities
3. `RuntimeConstraints.validate_transaction` â€” policy gate (errors on violation)
4. `ValidationEngine.validate_operations` â€” structural op validation
5. `ResourceEstimator.estimate_transaction` â€” cost estimate
6. If dry_run: return plan with `status="validated"`
7. `TransactionManager.begin_transaction` â†’ execute each op via `houdini_runtime.execute_operation` â†’ commit/rollback
8. `SceneCache.record_semantic_execution` â€” lineage
9. `AuditStore.log_transaction` â€” fire-and-forget

Singleton: `get_semantic_executor()` / `reset_semantic_executor_for_tests()`.

### 15.7 Scene Cache â€” Semantic Lineage (extension)

```python
cache = get_scene_cache()
cache.record_semantic_execution(intent_id, txn_id, op_count)
cache.get_semantic_lineage()        # [{intent_id, txn_id, op_count, timestamp}, ...]
cache.clear_semantic_lineage()
```

All three lists guarded by `_viz_lock` (same lock used for visualization data).

### 15.8 Tier 2.75 nodes

Three new Houdini plugin nodes in `plugins/houdini/v_nodes_houdini/`:

| node_id | Purpose |
|---|---|
| `hou_mcp_semantic_execute` | Translate + optionally execute a named intent via the semantic pipeline |
| `hou_mcp_runtime_capabilities` | Query the capability registry (no bridge calls) |
| `hou_mcp_workflow_templates` | Browse templates and/or resolve one to concrete ops (no bridge calls) |

All three are `category: "Houdini"` and `use_exec: true`. `hou_mcp_workflow_templates` intentionally returns `operations` (a list) that is safe to wire into `hou_mcp_transaction` for execution â€” the two nodes are designed to be chained.

### 15.9 Tier 2.75 test conventions

| File | Coverage |
|---|---|
| `tests/unit/test_capability_registry.py` | Built-ins, register/deregister, query, supports/get, stats, singleton |
| `tests/unit/test_resource_estimator.py` | Risk levels, node-type bumps, estimate_transaction, graph_complexity, singleton |
| `tests/unit/test_runtime_constraints.py` | Built-in policies, protected paths, forbidden ops/types, max_ops, permission callable, add/remove, validate_transaction, singleton |
| `tests/unit/test_workflow_templates.py` | Built-ins, list/get/apply, variable interpolation, missing var raises, register/deregister, singleton |
| `tests/unit/test_semantic_registry.py` | Built-ins, register/deregister, get/list, resolve happy/error/non-list-return, context vars, singleton |
| `tests/unit/test_semantic_execution.py` | translate shape/unknown/constraint/missing-cap, dry_run, execute commit, rollback simulation, lineage, report_json, singleton |

**Pattern for semantic execution tests:** register a simple ad-hoc operation via `get_semantic_registry().register_operation()` rather than relying on built-ins, so tests are isolated from built-in implementation changes. Combine with `fake_bridge` fixture to run through the full execute pipeline without a live Houdini.

### 15.10 Tier 2.75 deferred items (NOT in this work)

- **Template â†’ Workflow Template â†’ Transaction wiring in UI** â€” the `hou_mcp_workflow_templates` + `hou_mcp_transaction` pair already supports this; the UI node library just needs to surface them together in documentation/examples.
- **Semantic registry persistence** â€” currently in-memory only; a YAML/JSON registry file would allow studio-defined operations to survive restarts without code changes.
- **Capability registry auto-update on MCP server connect** â€” `mcp_runtime.register_server()` could call `capability_registry.register_capability("mcp_server", name, {...})` automatically on success.
- **Constraint profiles** â€” named sets of policies that can be loaded atomically (e.g. "strict_prod", "dev_sandbox").
- **Audit store integration for semantic operations** â€” currently fires-and-forgets; a dedicated `semantic_operations` table/query would enable replay-by-intent.

---

## 16. Controlled AI Planning Layer (Tier 3)

Tier 3 adds **controlled AI orchestration** on top of the Tier 2/2.5/2.75 runtime. The key distinction from a naive "AI planning" system is the mandatory pipeline:

```
LLM (names intent only, via intent_parser)
    → ContextualReasoner (scene analysis, no bridge calls)
    → AIPlanner (deterministic plan generation)
    → PlanValidator (multi-layer pre-execution validation)
    → ApprovalPipeline (human approval gate — required for high-risk plans)
    → SemanticExecutor / TransactionManager (execution via transaction system)
    → ExecutionReviewer (post-execution review)
    → PlanningMemory (structured audit log)
```

**Non-negotiable safety rules:**
1. `LLM → direct graph mutation` is NEVER permitted.
2. The pipeline `LLM → Intent → Planning → Validation → Preview → Transaction → Execution` is always enforced.
3. Do NOT build autonomous agents. Build controlled AI orchestration.
4. All AI output must remain: structured, inspectable, replayable, deterministic, constraint-aware.
5. Do NOT allow uncontrolled execution, AI self-modification, constraint bypass, or transaction bypass.

### 16.1 New Tier 3 runtime modules

```
src/runtime/
    llm_provider.py          ← Provider-agnostic LLM abstraction (Tier 3)
    planning_memory.py       ← Synchronous structured planning event store (Tier 3)
    intent_parser.py         ← Deterministic NL→intent keyword parser + LLM enhancement (Tier 3)
    contextual_reasoning.py  ← Pre-planning scene analysis (no bridge calls) (Tier 3)
    ai_planner.py            ← Plan generation from parsed intent + context (Tier 3)
    plan_validator.py        ← Multi-layer pre-execution plan validation (Tier 3)
    execution_explainer.py   ← Template-based human-readable explanation generator (Tier 3)
    execution_review.py      ← Post-execution intent-match review (Tier 3)
    approval_pipeline.py     ← Human approval state machine (Tier 3)
```

### 16.2 LLM provider abstraction (`src.runtime.llm_provider`)

Provider-agnostic interface. The runtime is fully functional without any LLM — all core operations are deterministic. LLMs add optional intelligence for intent disambiguation and plan refinement **only**.

| Provider | Purpose |
|---|---|
| `NoOpLLMProvider` | Default — always available, returns `enhanced=False`, never fails |
| `MockLLMProvider` | Deterministic testing — takes `responses: Dict[str, Dict]` keyed by prompt substring |
| `ClaudeLLMProvider` | Production — requires `anthropic` SDK + `ANTHROPIC_API_KEY`; returns structured JSON only |

**Safety rules for all providers:**
1. Return STRUCTURED DICTS only — never raw executable text.
2. No provider may execute operations or mutate Houdini state.
3. All provider output is validated before use.
4. Providers are stateless between calls.
5. API keys never appear in logs or audit trails.

```python
from src.runtime.llm_provider import get_llm_provider, set_llm_provider, MockLLMProvider
set_llm_provider(MockLLMProvider(responses={"pyro": {"intent": "build_pyro_source", "confidence": 0.95}}))
```

Singleton: `get_llm_provider()` / `set_llm_provider(provider)` / `reset_llm_provider_for_tests()`.

### 16.3 Intent parser (`src.runtime.intent_parser`)

Deterministic-first intent resolver. Keyword scoring runs before any LLM involvement.

```python
from src.runtime.intent_parser import get_intent_parser
parser = get_intent_parser()
result = await parser.parse("build a pyro smoke simulation inside /obj/geo1")
# result["intent"] = "build_pyro_source"
# result["parameters"] = {"style": "smoke", "parent": "/obj/geo1"}
# result["confidence"] = 0.9
# result["llm_enhanced"] = False
```

**LLM enhancement rule:** the LLM result replaces the deterministic result ONLY if `llm_confidence > deterministic_confidence` OR the deterministic layer found no intent. This prevents a misconfigured LLM from degrading a well-working parser.

**Supported intents:** `build_pyro_source`, `create_geo_container`, `setup_karma_renderer`, `export_to_usd`, `cache_geometry`, `asset_publish_scaffold`, `solaris_lighting_setup`.

Singleton: `get_intent_parser()` / `reset_intent_parser_for_tests()`.

### 16.4 Contextual reasoning (`src.runtime.contextual_reasoning`)

Analyzes the current runtime context BEFORE planning. No bridge calls — reads only in-memory state (scene_cache, dependency_graph, transaction_manager, capability_registry). All reads wrapped in try/except for graceful degradation when systems are not initialized.

```python
from src.runtime.contextual_reasoning import get_contextual_reasoner
reasoner = get_contextual_reasoner()
analysis = reasoner.analyze(intent, parameters, scene_context=None)
# analysis["existing_workflows"]       — prior executions of this intent
# analysis["recommended_actions"]      — ["extend_existing"] or ["create_new"]
# analysis["conflicts"]                — dependency chain conflicts
# analysis["optimization_suggestions"] — advisory hints
# analysis["scene_complexity"]         — "low" | "medium" | "high"
# analysis["scene_summary"]            — human-readable one-liner
```

Singleton: `get_contextual_reasoner()` / `reset_contextual_reasoner_for_tests()`.

### 16.5 AI planner (`src.runtime.ai_planner`)

Generates a structured execution plan from a parsed intent + context analysis. Deterministic by default; LLM refinement is advisory only.

```python
from src.runtime.ai_planner import get_ai_planner
planner = get_ai_planner()
plan = await planner.plan(parsed_intent, context_analysis, scene_context=None)
# plan["plan_id"]              — uuid4
# plan["ok"]                   — False if errors
# plan["intent"]               — resolved semantic op id
# plan["selected_template"]    — template id used (or None → semantic registry)
# plan["operations"]           — concrete op list ready for SemanticExecutor
# plan["requires_approval"]    — True if high-risk / destructive / large
# plan["approval_reasons"]     — why approval is required
# plan["resource_estimate"]    — from ResourceEstimator
# plan["reasoning"]            — list of planner decision explanations
# plan["llm_refined"]          — True if LLM added suggestions
```

**Approval triggers:** `requires_approval=True` in plan, `risk_level="high"`, `delete_node` ops present, `estimated_cook_cost > 0.8`, `op_count > 20`, constraint violations.

Singleton: `get_ai_planner()` / `reset_ai_planner_for_tests()`.

### 16.6 Plan validator (`src.runtime.plan_validator`)

Multi-layer pre-execution validation. Runs BEFORE the approval gate and before any transaction begins. Stateless — no bridge calls.

**Validation layers (in order):**
1. Structural validity — op fields, required keys
2. Capability check — required capabilities registered
3. Constraint compliance — RuntimeConstraints policy gate
4. Dependency validity — delete targets with downstream dependents → warning
5. Safety checks — destructive risk, self-connections, large batch deletes
6. Resource thresholds — cook cost / memory / op count limits

```python
from src.runtime.plan_validator import get_plan_validator
validator = get_plan_validator()
result = await validator.validate(plan, intent_metadata=None, max_cook_cost=1.5, max_op_count=150)
# result["valid"]             — bool
# result["errors"]            — list of blocking issues
# result["warnings"]          — advisory issues
# result["capability_gaps"]   — missing required capabilities
# result["safety_warnings"]   — destructive-risk notices
# result["dependency_impact"] — downstream affected nodes
# result["risk_level"]        — "low" | "medium" | "high"
```

Singleton: `get_plan_validator()` / `reset_plan_validator_for_tests()`.

### 16.7 Execution explainer (`src.runtime.execution_explainer`)

Template-based human-readable explanation generator. Zero LLM calls, zero bridge calls. Output is deterministic.

```python
from src.runtime.execution_explainer import get_execution_explainer
expl = get_execution_explainer()
expl.explain_plan(plan)             # plan explanation + op list + approval text
expl.explain_validation(result)     # validation PASSED/FAILED + issues
expl.explain_approval(state)        # approval status + reasons
expl.explain_execution(result)      # execution commit/rollback + scene changes
expl.explain_review(review)         # outcome + findings + recommendations
```

Each method returns a dict with `summary`, `full_text`, and type-specific detail fields. `full_text` is formatted for log panels and debug output.

Singleton: `get_execution_explainer()` / `reset_execution_explainer_for_tests()`.

### 16.8 Execution reviewer (`src.runtime.execution_review`)

Post-execution structured review. Compares actual execution against the original plan. NOT autonomous self-repair — purely observational.

```python
from src.runtime.execution_review import get_execution_reviewer
reviewer = get_execution_reviewer()
review = reviewer.review(plan, execution_result)
# review["outcome"]              — "success" | "partial" | "failure" | "undetermined"
# review["intent_match_score"]   — 0.0–1.0 (fraction of ops that completed OK)
# review["findings"]             — specific observations
# review["recommendations"]      — advisory next steps (never auto-executed)
# review["diff_analysis"]        — created/modified/deleted vs planned
```

Singleton: `get_execution_reviewer()` / `reset_execution_reviewer_for_tests()`.

### 16.9 Approval pipeline (`src.runtime.approval_pipeline`)

Synchronous approval state machine for high-risk plans. Not required for safe low-risk plans (which are auto-approved via `auto_approve()`).

```python
from src.runtime.approval_pipeline import get_approval_pipeline
pipe = get_approval_pipeline()

if pipe.requires_approval(plan):
    req_id = pipe.submit_for_approval(plan, submitter="ai_node")
    # ... human reviews ...
    pipe.approve(req_id, approver="td_lead", notes="Verified OK.")
    # OR pipe.reject(req_id, reason="Too many deletes.")
    # OR pipe.defer(req_id)
else:
    decision = pipe.auto_approve(plan)
```

**State machine:** `pending → approved | rejected | deferred`. Terminal states only. `approve/reject/defer` return `False` for non-pending or unknown requests.

**Approval triggers:** `plan.requires_approval=True`, `risk_level="high"`, `delete_node` ops.

Singleton: `get_approval_pipeline()` / `reset_approval_pipeline_for_tests()`.

### 16.10 Planning memory (`src.runtime.planning_memory`)

Synchronous structured event store for planning metadata. NOT a chat log. Enables analytics, replayability, explainability, and debugging.

**Valid event types:** `intent_parsed`, `plan_generated`, `plan_validated`, `plan_approved`, `plan_rejected`, `plan_deferred`, `execution_result`, `review_result`.

```python
from src.runtime.planning_memory import get_planning_memory
mem = get_planning_memory()
eid = mem.record("plan_approved", {"intent": "build_pyro_source", "plan_id": "..."})
events = mem.query(event_type="plan_approved", intent="build_pyro_source", limit=10)
stats  = mem.stats()
```

Optional JSONL persistence: `VIBRANTE_PLANNING_MEMORY_PATH` env var. In-memory cap: 500 records (lazy prune at 2x). Singleton: `get_planning_memory()` / `reset_planning_memory_for_tests()`.

### 16.11 Tier 3 nodes

Four new Houdini plugin nodes in `plugins/houdini/v_nodes_houdini/`:

| node_id | Purpose |
|---|---|
| `hou_mcp_ai_plan` | Parse a natural language prompt → intent → context analysis → plan dict. NEVER executes. |
| `hou_mcp_ai_preview` | Validate an AI plan WITHOUT executing. Returns risk, errors, capability gaps, explanation. |
| `hou_mcp_ai_execute` | Execute a validated AI plan via the transaction system with optional approval gate. |
| `hou_mcp_ai_review` | Post-execution review: did execution match intent? Returns outcome, match score, findings. |

**Canonical workflow:** `hou_mcp_ai_plan` → `hou_mcp_ai_preview` → (human review) → `hou_mcp_ai_execute` → `hou_mcp_ai_review`.

**`hou_mcp_ai_execute` approval gate:** Supply an `approver` name to authorize high-risk execution. Without an `approver`, the node blocks with `status=pending_approval` rather than auto-executing a dangerous plan.

**`hou_mcp_ai_plan` note:** Internally calls `IntentParser.parse()` + `ContextualReasoner.analyze()` + `AIPlanner.plan()`. No bridge calls.

### 16.12 Tier 3 AI execution invariants (non-negotiable)

1. **No bypass of the constraint system.** `hou_mcp_ai_execute` always reads the plan's `ok` flag; a plan with `ok=False` is rejected before any bridge call.
2. **No bypass of the transaction system.** All execution goes through `TransactionManager.begin_transaction` + `execute_operation` + `commit/rollback`. There is no direct bridge call in AI node code.
3. **No arbitrary Python execution.** The AI nodes do not expose `run_python` or `execute_code` operations. Execution is always via structured, validated ops.
4. **Approval is synchronous.** `hou_mcp_ai_execute` blocks (returns `pending_approval` status) rather than auto-executing a plan that requires approval but has no approver supplied.
5. **Review is observational only.** `hou_mcp_ai_review` produces findings and recommendations. It NEVER triggers re-execution or self-repair. Its output is for human consumption.
6. **LLM output is advisory only.** `ClaudeLLMProvider` output is schema-validated before use. LLM confidence must exceed deterministic confidence to override the parser. LLM refinement suggestions are surfaced as warnings — never as automatic parameter changes.
7. **Planning memory is audit-only.** Records written to `PlanningMemory` cannot trigger execution. They are read-only from the perspective of the execution pipeline.

### 16.13 Tier 3 test conventions

| File | Coverage |
|---|---|
| `tests/unit/test_planning_memory.py` | record/query/stats/clear, disk JSONL, max_records prune, singleton |
| `tests/unit/test_intent_parser.py` | All 7 intents, parameter extraction, style extraction, ambiguity, LLM enhancement, singleton |
| `tests/unit/test_contextual_reasoning.py` | Complexity scoring, existing workflow detection (lineage + dirty state), conflicts, singleton |
| `tests/unit/test_ai_planner.py` | Plan shape, no-intent failure, template vs registry fallback, constraint violations, approval triggers, LLM refinement, singleton |
| `tests/unit/test_plan_validator.py` | All structural error types, capability gaps, dependency impact, safety warnings, constraint errors, resource thresholds, singleton |
| `tests/unit/test_execution_explainer.py` | explain_plan/validation/approval/execution/review for all status variants, _op_to_human coverage, singleton |
| `tests/unit/test_execution_review.py` | Outcome classification, match score, findings, recommendations, op_stats, singleton |
| `tests/unit/test_approval_pipeline.py` | requires_approval triggers, state machine transitions, expiry, auto_approve, list_pending, singleton |

**Pattern:** use `MockLLMProvider` + `set_llm_provider()` for LLM-dependent tests. Always `reset_llm_provider_for_tests()` in autouse fixture. No live API calls, no live Houdini.

### 16.14 Tier 3 deferred items (NOT in this work)

- **End-to-end NL→execution demo workflow** — a single workflow JSON chaining `hou_mcp_ai_plan` → `hou_mcp_ai_preview` → `hou_mcp_ai_execute` → `hou_mcp_ai_review`. Deferred to Tier 4 examples.
- **`ai_graph_planner` multi-step planning** — planning sequences that produce multiple semantic intents per prompt (e.g. "build a full VFX shot" → pyro + lighting + render). Requires intent dependency ordering.
- **Dynamic MCP node generation from tool schemas** — generate in-memory nodes from MCP tool schemas discovered via `mcp_list_tools`. Deferred until approval pipeline is hardened through production use.
- **`planning_memory` replay-by-intent** — query planning memory to replay a previous AI plan by intent name. The memory store is already built; the replay UI/node is deferred.
- **Constraint profiles** — named sets of policies (e.g. "strict_prod", "dev_sandbox") loadable atomically into RuntimeConstraints.
- **Approval pipeline persistence** — pending approvals currently live in-memory only; a persistent approval queue would survive process restarts.


---

## 17. Distributed Autonomous Orchestration Infrastructure (Tier 4)

Tier 4 introduces the **distributed AI-native orchestration layer** — the infrastructure enabling multiple runtimes, DCCs, and supervised agents to collaborate on complex production tasks. This is NOT uncontrolled autonomous AI. Every agent, every cross-DCC operation, every remote execution still goes through the full validation/constraint/transaction pipeline.

**Mandatory safety invariant (non-negotiable):**

```
External AI → Agent Runtime (Supervised) → ValidationEngine → RuntimeConstraints
    → TransactionManager → houdini_runtime.execute_operation → AuditStore
```

`External AI → direct execution authority` is NEVER permitted, anywhere in this tier.

### 17.1 MCP Server Runtime (`src.runtime.mcp_server_runtime`)

Tier 4 makes Vibrante-Node an **MCP server** — exposing structured runtime tools to external AI clients. This is the counterpart to Tier 1's MCP client.

**Built-in tools exposed:**

| Tool name | Handler | Purpose |
|---|---|---|
| `vibrante_plan_workflow` | `_handle_plan_workflow` | Submit a natural-language prompt for AI planning |
| `vibrante_preview_plan` | `_handle_preview_plan` | Preview operations without executing |
| `vibrante_list_capabilities` | `_handle_list_capabilities` | Enumerate available capabilities |
| `vibrante_list_templates` | `_handle_list_templates` | Browse + apply workflow templates |
| `vibrante_query_audit` | `_handle_query_audit` | Query the audit store for transaction history |
| `vibrante_get_scene_status` | `_handle_get_scene_status` | Current dirty-state + semantic lineage |

Tools are sorted alphabetically in `list_tools()`. Custom tools can be registered/deregistered; built-in tools cannot be deregistered (raises `ValueError`).

**handle_request invariant:** never raises — all exceptions are caught and returned as `{"is_error": True, "error": "..."}`.

**Singleton:** `get_mcp_server_runtime()` / `reset_mcp_server_runtime_for_tests()`.

### 17.2 Distributed Runtime (`src.runtime.distributed_runtime`)

Worker pool + execution dispatch. Maintains a registry of workers (local or remote), routes operations to the best available worker by capability and load.

**Worker model:**
- Each worker has: `name`, `capabilities`, `endpoint`, `max_load`, `current_load`, `status`
- Endpoint `local://` → execution goes through the full local pipeline (ValidationEngine + RuntimeConstraints + TransactionManager + houdini_runtime)
- Endpoint `remote://...` → recorded as `dispatched` (transport wired externally)

**Worker selection:** least-load-ratio worker with all required capabilities.

**Local execution pipeline (safety-enforcing):**
```
validate_transaction() → validate_operations() → begin_transaction()
    → execute_operation() per op → commit/rollback → record_dispatch()
```

**Dispatch record:** every dispatch (including remote) is logged via `_record_dispatch(dispatch_id, data)` and retrievable by `get_dispatch_status(dispatch_id)`.

**Singleton:** `get_distributed_runtime()` / `reset_distributed_runtime_for_tests()`.

### 17.3 Agent Runtime (`src.runtime.agent_runtime`)

Runtime-supervised agent system. Agents do NOT execute — they plan. Execution requires a separate human-approval step.

**Supervision levels:**

| Level | `execution_authorized` | `requires_approval` | Notes |
|---|---|---|---|
| `advisory` | always `False` | always `True` | Dry-run / advisory output only; never authorizes |
| `strict` | always `False` | always `True` | Human approval always required before any execution |
| `standard` | `True` only when plan is valid + risk != high + not requires_approval | conditional | Safe plans may be auto-authorized |

**Proposal lifecycle:**
1. `register_agent(name, supervision_level, role)` → `agent_id`
2. `submit_proposal(agent_id, proposal)` → runs IntentParser + ContextualReasoner + AIPlanner + PlanValidator
3. `_apply_supervision(level, plan, validation)` → `supervision_result` with `execution_authorized`, `requires_approval`, `reason`
4. Proposal stored; `proposal_count` incremented

**Execution gate:** `execution_authorized=True` (standard level only) means the caller MAY submit the plan to `hou_mcp_ai_execute`. It does NOT mean execution happens automatically.

**Singleton:** `get_agent_runtime()` / `reset_agent_runtime_for_tests()`.

### 17.4 Multi-DCC Runtime (`src.runtime.multi_dcc_runtime`)

DCC routing + adapter protocol. Determines which DCC handles which operation and dispatches accordingly.

**DccAdapter protocol:**

```python
class DccAdapter:
    @property
    def is_available(self) -> bool: ...
    async def execute_operations(self, ops, dry_run=False) -> dict: ...
```

Built-in adapters:
- `HoudiniDccAdapter` — routes via `DistributedRuntime.dispatch_operations()`. Auto-registers a local worker on first call.
- `MockAdapter` (test-only) — always returns `{"ok": True, "status": "mock_ok", ...}`

**Routing priority (per op):**
1. `hint_dcc` if provided and registered
2. Op type in DCC's declared capabilities
3. `_HOUDINI_OPS` fallback set (the standard Houdini op names)
4. `"houdini"` default

**`execute_cross_dcc(ops)`** partitions ops by `route_operations()`, executes each DCC's slice via `execute_for_dcc()`, and returns `{"ok", "by_dcc", "errors"}`.

**Singleton:** `get_multi_dcc_runtime()` / `reset_multi_dcc_runtime_for_tests()`.

### 17.5 Knowledge Graph (`src.runtime.knowledge_graph`)

In-memory semantic relationship store for production entities.

**Entity types:** `asset`, `shot`, `sequence`, `worker`, `dcc_session`, `workflow`, `render`, `custom`

**Relationship types:** `depends_on`, `created_by`, `rendered_in`, `submitted_to`, `part_of`, `executed_by`, `produces`, `references`, `custom`

Key invariants:
- `add_relationship()` auto-creates entity stubs (type `"custom"`) for unknown ids — no pre-registration required
- Self-relationships raise `ValueError`
- `remove_entity()` cascades: all incident relationships removed atomically
- `find_path()` is outbound-only BFS with configurable `max_depth` (default 6)
- `query_related(direction="both")` returns entities on either end of incident edges

**Singleton:** `get_knowledge_graph()` / `reset_knowledge_graph_for_tests()`.

### 17.6 Semantic Memory (`src.runtime.semantic_memory`)

Persistent structured orchestration pattern store.

**Pattern types:** `execution_pattern`, `planning_pattern`, `optimization_hint`, `workflow_lineage`

**Outcome values:** `success`, `partial`, `failure`, `unknown`

**NOT stored:** raw LLM prompts, chat logs, personal user data, unparsed free-text. Only structured metadata.

**`get_best_patterns(intent)`** sort key: `success < partial < unknown < failure` (then `-timestamp` within each outcome group) — most successful recent patterns first.

**Persistence:** JSONL append-only file. Path from `VIBRANTE_SEMANTIC_MEMORY_PATH` env var. Write failures silently swallowed — memory must never block execution. Prune at 2x `max_records` (default 1,000).

**Singleton:** `get_semantic_memory()` / `reset_semantic_memory_for_tests()`.

### 17.7 Worker Runtime (`src.runtime.worker_runtime`)

Worker pool accounting. Distinct from `DistributedRuntime` (which handles dispatch); `WorkerRuntime` manages the pool's lifecycle state.

**Worker lifecycle:** `registered → idle ↔ busy → offline`

**Stale detection:** `check_stale_workers(timeout_sec=60)` marks workers as `offline` when `last_heartbeat` is older than `timeout_sec`. Returns sorted list. Does NOT re-check already-offline workers.

**`acquire_worker()`** is atomic: increments `current_load` and sets `status="busy"` under the lock. Returns the least-load-ratio matching worker, or `None` if none available.

**`update_heartbeat()`** revives `offline` workers back to `idle` (if load=0) or `busy`.

**Singleton:** `get_worker_runtime()` / `reset_worker_runtime_for_tests()`.

### 17.8 Workflow Federation (`src.runtime.workflow_federation`)

Cross-DCC federated workflow execution. A federated workflow is a DAG of segments; each segment targets a specific DCC and carries its own operation list.

**Creation validation (before any execution):**
- Unique segment ids
- No dependency cycles (Kahn's algorithm)

**Execution order:** topological sort → execute segments in dependency order via `MultiDccRuntime.execute_for_dcc()`.

**Failure behaviour:** on the first failed segment, all remaining segments are marked `"skipped"` and the loop breaks. Each successful segment commits independently through its DCC's validation/transaction pipeline — the federation layer adds no execution authority.

**`get_status()`** returns per-segment statuses without the full result data — use `get_workflow()` for the full dict.

**Singleton:** `get_workflow_federation()` / `reset_workflow_federation_for_tests()`.

### 17.9 Runtime Federation API (`src.runtime.runtime_federation_api`)

Runtime-to-runtime peer discovery and coordinated execution routing.

**Local runtime:** auto-registered at init as `id="local"`, `endpoint="local://"`, `runtime_type="local"`. Cannot be deregistered.

**Runtime types:** `local`, `remote`, `farm`, `cloud`

**`discover_capabilities("local")`** queries the live `CapabilityRegistry` — always reflects current state.

**`discover_capabilities(remote_id)`** returns what was registered at registration time — static snapshot.

**`request_execution(runtime_id, ops)`:**
- Local / `local://` endpoint → `DistributedRuntime.dispatch_operations()`
- Remote endpoint → returns `{"ok": True, "status": "federated_dispatch", "dispatch_id": ...}` (transport wired externally)
- Unknown runtime → `{"ok": False, "error": "Unknown runtime: ..."}`

**Capability exchange:** `exchange_capabilities()` updates the peer's capability list in the local registry and logs the exchange in `_exchanges`.

**Singleton:** `get_runtime_federation_api()` / `reset_runtime_federation_api_for_tests()`.

### 17.10 Capability Registry extensions (Tier 4)

`CAPABILITY_TYPES` extended with two new values:
- `"remote_capability"` — a capability exposed by a remote peer runtime
- `"mcp_tool"` — a tool exposed by a registered MCP server

New methods:
```python
caps.expose_via_mcp(cap_id, tool_schema)         # mark capability as MCP-exposed
caps.get_mcp_tools()                              # list all MCP-exposed capabilities
caps.register_remote_capability(runtime_id, cap_type, cap_id, metadata)
                                                  # namespace: {runtime_id}:{cap_id}
caps.get_remote_capabilities(runtime_id)          # filter by remote=True + runtime_id
```

**Namespacing:** `register_remote_capability()` stores as `{runtime_id}:{cap_id}` to prevent collision with local capability ids.

### 17.11 Tier 4 nodes

| node_id | Location | Purpose |
|---|---|---|
| `hou_mcp_runtime_federation` | `plugins/houdini/v_nodes_houdini/` | Register / discover / exchange capabilities with peer runtimes |
| `hou_mcp_distributed_execute` | `plugins/houdini/v_nodes_houdini/` | Execute operations on a distributed worker pool |
| `hou_mcp_agent_plan` | `plugins/houdini/v_nodes_houdini/` | Submit a supervised agent proposal (planning only — never executes directly) |
| `hou_mcp_remote_worker` | `plugins/houdini/v_nodes_houdini/` | Register / heartbeat / acquire / release remote workers |
| `hou_mcp_knowledge_query` | `plugins/houdini/v_nodes_houdini/` | Query / mutate the production knowledge graph |

All five are `category: "Houdini"` and `use_exec: true`. They follow the same naming convention as Tier 1-3 Houdini nodes.

**`hou_mcp_agent_plan` safety note:** auto-registers the agent if `agent_id` is empty. The proposal result contains `execution_authorized` and `requires_approval` fields. The node NEVER calls `execute_operation` directly — execution must be wired to a separate `hou_mcp_ai_execute` node which the user reviews explicitly.

### 17.12 Tier 4 test conventions

| File | Coverage |
|---|---|
| `tests/unit/test_mcp_server_runtime.py` | list_tools, get_tool, handle_request, register/deregister custom tool, deregister builtin raises, lifecycle, stats, singleton |
| `tests/unit/test_distributed_runtime.py` | worker CRUD, cap_filter, dispatch no_worker, remote dispatch, dispatch_id retrieval, cap mismatch, local dry_run via monkeypatch, stats, singleton |
| `tests/unit/test_agent_runtime.py` | agent CRUD, invalid supervision raises, proposal errors, advisory/strict/standard supervision semantics, proposal_count, get_proposal, stats, singleton |
| `tests/unit/test_multi_dcc_runtime.py` | built-in houdini, register/deregister, routing (hint/capability/fallback), route_operations partition, execute unknown, execute mock, execute_cross_dcc, adapter exception caught, stats, singleton |
| `tests/unit/test_knowledge_graph.py` | entity CRUD, relationship CRUD, auto-stub creation, cascade remove, query_related (outbound/inbound/both/filtered), find_path (direct/multi-hop/no-path/max-depth), all_entities/all_relationships, stats, clear, singleton |
| `tests/unit/test_semantic_memory.py` | record_pattern (valid/invalid-type/invalid-outcome), get_pattern, query_patterns (filters/limit/newest-first), get_best_patterns ordering, record_workflow_lineage, stats, clear, disk round-trip, singleton |
| `tests/unit/test_worker_runtime.py` | register/deregister, heartbeat (revives offline), acquire (least-loaded/at-max/no-match), release (clamped), find_workers_for, check_stale, stats, singleton |
| `tests/unit/test_workflow_federation.py` | create (empty/duplicate/cycle raises), get_workflow/list/get_status, execute all-success, execute failure+skipped, execute dry_run, topological ordering, stats, singleton |
| `tests/unit/test_runtime_federation_api.py` | local auto-registered, register/deregister (local raises), discover_capabilities (local=live/remote=static/unknown=[]), exchange_capabilities, heartbeat, request_execution (local/remote/unknown), stats, singleton |

**Pattern:** use `MockAdapter(DccAdapter)` for workflow federation and multi-DCC tests — inject via `mdr.register_dcc("houdini", MockAdapter(...), [...])` before executing federated workflows so no live Houdini is needed.

**Pattern:** monkeypatch `DistributedRuntime._execute_local` for distributed runtime tests that need to exercise the local dispatch path without a live Houdini.

**Pattern:** use `SemanticMemory(path=None)` for in-memory-only semantic memory tests; use `SemanticMemory(path=tmpfile)` for disk persistence tests.

### 17.13 Tier 4 safety audit

Every Tier 4 module was designed against the following invariants. Any PR modifying Tier 4 must re-verify these:

1. **No agent executes directly.** `AgentRuntime.submit_proposal()` returns a plan + supervision_result. Execution requires wiring to `hou_mcp_ai_execute` and a separate approval step.
2. **Distributed execution is always validated.** `DistributedRuntime._execute_local()` calls `RuntimeConstraints.validate_transaction()` AND `ValidationEngine.validate_operations()` before any bridge interaction.
3. **Remote dispatch is opaque.** Remote endpoints receive a `dispatched` status record only — the actual execution transport is the caller's responsibility and happens outside this module.
4. **Federation adds no authority.** `WorkflowFederation.execute_federated()` calls `execute_for_dcc()` which calls the DCC adapter's `execute_operations()` — each segment still goes through its own full validation/transaction pipeline.
5. **Built-in MCP tools cannot be removed.** `McpServerRuntime.deregister_tool()` raises `ValueError` for built-in tools — external MCP clients cannot remove Vibrante's own tools.
6. **Knowledge graph is advisory.** `KnowledgeGraph` is a read/write cache of production relationships — it has no execution authority and does not interact with the bridge or transaction system.
7. **Semantic memory stores no raw prompts.** `SemanticMemory.record_pattern()` validates `pattern_type` and `outcome` — free-form text is not accepted as pattern data.

### 17.14 Tier 4 deferred items (NOT in this work)

- **Live remote transport for federation.** The federation API records remote dispatches but does not implement the actual network transport (WebSocket, HTTP, gRPC). This is production infrastructure that requires authentication, encryption, and retry handling beyond the scope of the runtime layer.
- **`WorkerRuntime` + `DistributedRuntime` integration.** Currently separate singletons — a future integration would have `DistributedRuntime._select_worker()` consult `WorkerRuntime.acquire_worker()` for heartbeat-validated pool accounting.
- **Federated workflow rollback.** If segment B fails after segment A committed, segment A's changes are not rolled back across DCCs. Cross-DCC rollback requires HIP-level snapshots and coordinated undo (planned for a future tier).
- **Knowledge graph persistence.** The graph is in-memory only; JSONL or SQLite persistence would enable cross-session production relationship tracking.
- **Agent collaboration.** Multiple agents sharing context, negotiating plans, or delegating sub-tasks to each other is explicitly deferred — all proposals remain single-agent for now.
- **MCP server transport.** `McpServerRuntime` defines the tool registry and handlers but does not implement an actual HTTP/SSE or stdio MCP server transport — that requires the `mcp` SDK's server-side APIs (separate from the client used in Tier 1).

---

## 18. Adaptive Procedural Intelligence Layer (Tier 5)

Tier 5 adds **advisory-only adaptive intelligence** on top of Tiers 1–4. The key distinction from active orchestration is that EVERY module in this tier is purely observational, analytical, and advisory. No module in Tier 5 calls `get_bridge()`, `houdini_runtime`, `TransactionManager`, or `ExecutionScheduler` directly.

**Mandatory safety invariant (non-negotiable):**

```
Adaptive Intelligence → Recommendation → Validation → Approval → Transaction → Execution
```

`Adaptive Intelligence → direct execution authority` is NEVER permitted.

**What Tier 5 does:**
- Analyzes execution plans and histories to produce optimization tips
- Predicts failure risk using deterministic heuristics (no opaque ML)
- Recommends workflows, templates, and strategies
- Evaluates execution quality after the fact
- Tracks studio pipeline patterns for future advisory use

**What Tier 5 does NOT do:**
- Execute any operations
- Modify any Houdini state
- Bypass the Validation → Approval → Transaction pipeline
- Use self-modifying AI or autonomous mutation

### 18.1 New Tier 5 runtime modules

```
src/runtime/
    workflow_optimizer.py        ← Advisory execution path analyzer and optimizer
    runtime_analytics.py         ← Execution performance data collector and reporter
    predictive_execution.py      ← Heuristic-based failure prediction
    orchestration_heuristics.py  ← Inspectable, overridable orchestration heuristics
    recommendation_engine.py     ← Advisory workflow/template/strategy recommendations
    resource_optimizer.py        ← Advisory resource allocation optimization
    failure_intelligence.py      ← Failure pattern detection and health analysis
    execution_quality.py         ← Orchestration-level quality evaluation
    studio_knowledge.py          ← Studio pipeline pattern knowledge store
```

`src/runtime/execution_scheduler.py` is also extended with adaptive scheduling metadata (see §18.10).

### 18.2 Workflow Optimizer (`src.runtime.workflow_optimizer`)

Advisory execution path analysis. Reads op lists and history — no bridge calls.

```python
from src.runtime.workflow_optimizer import get_workflow_optimizer

opt = get_workflow_optimizer()
analysis = opt.analyze_plan(operations)
# analysis["risk_score"]         — numeric (delete_node=10, set_parms/connect/cook=1, rest=0)
# analysis["risk_level"]         — "low" | "medium" | "high"
# analysis["op_count"]           — int
# analysis["delete_count"]       — int
# analysis["optimization_tips"]  — advisory list[str]
# analysis["reorder_suggested"]  — True if cooks precede creates
# analysis["batch_suggested"]    — True if op_count >= 15
# analysis["summary"]            — human-readable one-liner

alts = opt.recommend_alternatives(operations, intent="build_pyro_source")
# alts["alternatives"] — list of strategy dicts (id, description, recommended)
# "dry_run_first" is always present; "split_batch" for large batches;
# "wrap_transaction" for delete ops; preferred alternatives indicated for high risk

opt.record_outcome(template_id, outcome)
# outcome ∈ {"success", "partial", "failure", "rolled_back"}
# raises ValueError for invalid outcome

score = opt.score_template(template_id)
# {"template_id", "avg_score", "sample_count", "recommendation"}
# recommendation: "preferred" (avg≥0.8), "acceptable" (avg≥0.5), "avoid" (<0.5), "unknown" (no history)

hist = opt.get_optimization_history(limit=10)
# list of {template_id, outcome, score, timestamp} newest-first
```

**Risk weights:** `delete_node=10`, `set_parms=connect_nodes=cook_node=1`, all others `0`. Risk level: `low` < 5, `medium` 5–14, `high` ≥ 15.

Singleton: `get_workflow_optimizer()` / `reset_workflow_optimizer_for_tests()`.

### 18.3 Runtime Analytics (`src.runtime.runtime_analytics`)

Execution performance data collector. Append-only in-memory records, capped at 2,000.

```python
from src.runtime.runtime_analytics import get_runtime_analytics

analytics = get_runtime_analytics()
analytics.record_execution({"intent": "build_pyro_source", "status": "committed",
                             "duration_sec": 3.0, "op_count": 5, "rollback_performed": False,
                             "worker_id": "w1"})
analytics.record_validation({"valid": True, "risk_level": "low", "op_count": 5,
                              "warning_count": 0, "error_count": 0, "intent": "build_pyro_source"})
analytics.record_worker_event({"event": "acquire", "worker_id": "w1", "success": True,
                                "current_load": 1, "max_load": 4})

report = analytics.get_report()
# report["execution_metrics"]    — {total, success_rate, avg_duration_sec, rollback_rate, top_failure_intents}
# report["failure_metrics"]      — {total_failures, rollback_rate, by_intent, top_failure_intents}
# report["resource_metrics"]     — {acquire_count, release_count, stale_count, by_worker}
# report["workflow_statistics"]  — {by_intent, by_status, total_validations, validation_failure_rate}
# report["generated_at"]         — float timestamp

trends = analytics.get_execution_trends(window_sec=300)
# [{intent, status, duration_sec, op_count, timestamp}, ...] filtered to last window_sec
```

Singleton: `get_runtime_analytics()` / `reset_runtime_analytics_for_tests()`.

### 18.4 Predictive Execution (`src.runtime.predictive_execution`)

Heuristic failure prediction. Deterministic, explainable — no opaque ML.

```python
from src.runtime.predictive_execution import get_predictive_execution

pe = get_predictive_execution()
pred = pe.predict(operations, context={})
# pred["predicted_risk"]         — "low" | "medium" | "high"
# pred["failure_probability"]    — float 0.0–1.0
# pred["risk_factors"]           — list[str] (named, human-readable)
# pred["recommendations"]        — list[str] (advisory)
# pred["confidence"]             — float 0.5–1.0

pressure = pe.predict_resource_pressure(operations, context={})
# pressure["memory_pressure"]    — "low" | "medium" | "high"
# pressure["cook_pressure"]      — "low" | "medium" | "high"
# pressure["notes"]              — list[str]

conflicts = pe.predict_dependency_conflicts(operations)
# conflicts["conflicts"]         — list of {type, op_index, explanation}
# conflicts["risk_level"]        — "none" | "low" | "medium" | "high"

congestion = pe.predict_scheduler_congestion(queue_depth=7)
# congestion["congestion_level"] — "none" | "mild" | "severe"
# congestion["recommendation"]   — advisory string
```

**Named risk factors (all deterministic):**
- `large_batch` (≥ 20 ops)
- `high_delete_count` (≥ 5 delete_node ops)
- `cook_before_connect` (cook ops appear before connect ops in the list)
- `unknown_op_types` (op keys not in SUPPORTED_OPS)
- `high_risk_score` (total risk weight ≥ 20)
- `missing_source_node` (connect_nodes references a path not created in the same batch)

**Heavy node types** (bump memory/cook pressure): `pyro`, `flip`, `vellum`, `ocean`, `crowd`, `smoke`.

Singleton: `get_predictive_execution()` / `reset_predictive_execution_for_tests()`.

### 18.5 Orchestration Heuristics (`src.runtime.orchestration_heuristics`)

Inspectable, overridable heuristics. Every heuristic is named and documented via `list_heuristics()`.

```python
from src.runtime.orchestration_heuristics import get_orchestration_heuristics

h = get_orchestration_heuristics()

h.order_operations(ops)
# {"ordered_indices": [int, ...], "changed": bool, "summary": str}
# Order weights: create_node=1, build_node_chain=2, set_parms=3, connect_nodes=4,
#                flags=5, layout=6, cook=7, delete=8

h.select_worker(workers, required_capabilities)
# {"selected_id": str|None, "alternatives": [...], "reason": str}
# Selects least-loaded idle worker with all required capabilities

h.group_for_batching(ops, max_batch_size=10)
# {"batches": [[indices], ...], "batch_count": int, "summary": str}
# Splits at delete_node boundaries and at max_batch_size

h.route_operation(op, available_dccs)
# {"recommended_dcc": str|None, "confidence": float, "reason": str}
# Priority: hint_dcc > houdini op types > first available DCC fallback

h.prioritize_queue(items)
# {"ordered_ids": [str, ...], "summary": str}
# items: [{id, priority (0–100), risk_level, op_count, timestamp}]
# Sort: (-priority, risk_ord, op_count, timestamp)

h.list_heuristics()
# Returns exactly 5 dicts: [{name, description, inputs, outputs}, ...]
```

Singleton: `get_orchestration_heuristics()` / `reset_orchestration_heuristics_for_tests()`.

### 18.6 Recommendation Engine (`src.runtime.recommendation_engine`)

Advisory recommendations for workflows, templates, and dependency conflicts. Reads SemanticRegistry, WorkflowTemplates, SemanticMemory — never calls bridge.

```python
from src.runtime.recommendation_engine import get_recommendation_engine

engine = get_recommendation_engine()

engine.recommend_workflow(intent, context={})
# {"recommended_op": str|None, "confidence": float, "reasoning": [str], "alternatives": [...]}
# confidence degraded when required capabilities (e.g. karma renderer) are not available

engine.recommend_template(intent)
# {"recommended_template": str|None, "confidence": float, "all_candidates": [...], "reasoning": [str]}
# Checks SemanticMemory for historical best, then built-in intent→template map, then WorkflowTemplates

engine.recommend_strategy(operations)
# {"strategies": [{"id", "description", "recommended": bool}, ...], "primary": str|None}
# "dry_run_first" always present; "wrap_transaction" for delete ops; "split_batch" for ≥ 15 ops

engine.recommend_dependency_resolution(conflicts)
# {"resolutions": [{"conflict_type", "resolution", "confidence"}, ...], "all_resolvable": bool}
# Handles: self_connection (resolvable), missing_source_node (resolvable),
#          cycle (NOT resolvable), unknown type (NOT resolvable)
```

**stats():** `{"recommendation_count": int}` — increments on every `recommend_workflow`, `recommend_template`, `recommend_strategy` call.

Singleton: `get_recommendation_engine()` / `reset_recommendation_engine_for_tests()`.

### 18.7 Resource Optimizer (`src.runtime.resource_optimizer`)

Advisory resource allocation. No bridge calls, no execution authority.

```python
from src.runtime.resource_optimizer import get_resource_optimizer

opt = get_resource_optimizer()

opt.recommend_worker_allocation(operations, workers)
# {"recommended_worker": str|None, "load_after": float, "should_split": bool, "reason": str}
# should_split=True when len(ops) >= _MAX_OPS_PER_TRANSACTION (15)
# load_after = (current_load + 1) / max_load for selected worker

opt.recommend_transaction_sizing(operations)
# {"group_count": int, "split_points": [int], "recommended_size": int, "summary": str}
# Splits at: risk_score≥10, count≥recommended_size, delete_node with prior ops

opt.recommend_scheduling_order(items)
# {"ordered_ids": [str, ...], "summary": str}
# items: [{id, priority, risk_level, op_count, timestamp}]

opt.recommend_load_balancing(workers)
# {"pool_health": "healthy"|"unbalanced"|"overloaded", "actions": [...], "summary": str}
# Actions: "scale_up" (any worker at 100% load), "revive_or_remove" (offline worker),
#          "rebalance" (high variance between worker loads)
```

**Constants:** `_MAX_OPS_PER_TRANSACTION = 15`, `_IDEAL_WORKER_LOAD = 0.7`.

**stats():** `{"call_count": int}` — increments on `recommend_worker_allocation` and `recommend_transaction_sizing`.

Singleton: `get_resource_optimizer()` / `reset_resource_optimizer_for_tests()`.

### 18.8 Failure Intelligence (`src.runtime.failure_intelligence`)

Failure pattern detector and health analyzer. Reads execution history records — no bridge calls.

```python
from src.runtime.failure_intelligence import get_failure_intelligence

fi = get_failure_intelligence()

fi.analyze(records)
# {"failure_patterns": [...], "risk_clusters": [...], "recommendations": [str], "health_score": float}
# health_score = fraction of committed (non-rollback) records; 1.0 for empty input

fi.detect_recurring_patterns(records)
# {"patterns": [{"pattern", "intent"/"count", "recommendation"}, ...]}
# Patterns: repeated_intent_failure (≥2 failures for same intent),
#           high_rollback_rate (≥30% rollbacks), large_batch_failures (op_count>15, ≥2 failures)

fi.detect_risky_structures(operations)
# {"risks": [{"type", "description", "severity"}], "safe": bool}
# Risk types: connect_without_create (connect ops but no create ops in list),
#             interleaved_create_delete (create ops between delete ops),
#             cook_empty_setup (cook before any creates/connects)

fi.get_hotspot_report(records)
# {"clusters": [{"cluster": "intent_hotspot"|"template_hotspot", "intent_or_template", "failure_rate", "count"}]}
# Hotspot: failure_rate ≥ 0.5 with ≥ 2 total records for that intent/template
```

**stats():** `{"analysis_count": int}` — increments on each `analyze()` call.

Singleton: `get_failure_intelligence()` / `reset_failure_intelligence_for_tests()`.

### 18.9 Execution Quality (`src.runtime.execution_quality`)

Orchestration-level quality evaluator. Evaluates EXECUTION QUALITY (timing, stability, correctness) — NOT artistic or render quality.

```python
from src.runtime.execution_quality import get_execution_quality

q = get_execution_quality()

result = q.evaluate(execution_result, plan=None, history=None)
# result["overall_score"]  — float 0.0–1.0 (weighted average of 6 dimensions)
# result["dimensions"]     — dict with exactly 6 keys:
#     "efficiency"             — timing vs budget (2 sec/op default budget)
#     "semantic_correctness"   — ops_executed / plan ops (1.0 if no plan)
#     "stability"              — success fraction from history (1.0 if no history)
#     "validation_reliability" — fraction of valid validation records
#     "replay_consistency"     — heuristic based on rollback flag
#     "dependency_integrity"   — heuristic based on error count
# result["findings"]       — list[str] (at least 1 entry, always present)
# result["grade"]          — "A"|"B"|"C"|"D"|"F"

q.score_efficiency(execution_result)
# budget_sec = _BUDGET_SEC_PER_OP (2.0) × max(op_count, 1)
# returns 1.0 if duration ≤ budget, else budget/duration

q.score_stability(history_records)
# fraction where status=="committed" AND NOT rollback_performed
# 1.0 for empty history

q.score_validation_reliability(validation_records)
# fraction where valid==True; 1.0 for empty list

q.grade(score)
# A (≥0.9), B (≥0.8), C (≥0.7), D (≥0.6), F (<0.6)
```

**stats():** `{"eval_count": int}`.

Singleton: `get_execution_quality()` / `reset_execution_quality_for_tests()`.

### 18.10 Studio Knowledge (`src.runtime.studio_knowledge`)

Structured studio pipeline pattern store. Tracks orchestration outcomes and recipes for advisory use.

```python
from src.runtime.studio_knowledge import get_studio_knowledge, StudioKnowledge

sk = get_studio_knowledge()

sk.record_workflow_pattern({"intent": "build_pyro_source", "outcome": "success",
                             "op_count": 8, "dcc": "houdini", "template_id": "pyro_source"})
sk.record_asset_pattern({"intent": "asset_publish", "outcome": "success", "dcc": "houdini"})
# Both raise ValueError for invalid outcome values

best = sk.get_best_recipe("build_pyro_source", dcc="houdini")
# dict or None — highest op_count success record for the intent/dcc combo

patterns = sk.query_patterns(intent=None, dcc=None, outcome=None, limit=20)
# newest-first list of pattern dicts

insights = sk.get_optimization_insights("build_pyro_source")
# {"intent", "pattern_count", "success_rate", "avg_op_count",
#  "best_template", "best_dcc", "insights": [str]}
```

**Valid outcomes:** `"success"`, `"partial"`, `"failure"`, `"unknown"`.

**Valid pattern types:** `"workflow_pattern"`, `"asset_pattern"`, `"cross_dcc_pattern"`, `"pipeline_recipe"`, `"optimization_hint"`.

**Persistence:** optional JSONL file. Path from `VIBRANTE_STUDIO_KNOWLEDGE_PATH` env var or `StudioKnowledge(path=...)`. Write failures silently swallowed. Corrupt JSONL lines skipped on load. Prunes at 2× `_max_records` (default 1,000).

**Does NOT store:** raw artist conversations, private production data (file paths, asset names), arbitrary free-text or user input.

Singleton: `get_studio_knowledge()` / `reset_studio_knowledge_for_tests()`.

### 18.11 Execution Scheduler extensions (adaptive scheduling)

`ExecutionScheduler.enqueue()` accepts two new optional parameters:

```python
result = await scheduler.enqueue(
    factory_coroutine,
    transaction_id="txn-42",
    priority=80,       # int 0–100, default 50 (clamped)
    risk_level="high", # "low" | "medium" | "high", default "low"
)
```

Two new methods:

```python
scheduler.congestion_level()
# "none" (queue < 5), "mild" (5–9), "severe" (≥ 10)

scheduler.get_pending_items()
# sorted list of {id, queued_at, priority, risk_level, cancelled}
# no callables exposed
```

`stats()` now includes `"congestion_level"` key.

**Architecture note:** priority and risk_level are **metadata only** — they are stored on the item dict for inspection/analytics but do NOT reorder the FIFO pump queue. The adaptive intelligence layer reads this metadata for advisory scheduling recommendations; actual execution order remains FIFO to preserve determinism.

### 18.12 Tier 5 nodes

Five new Houdini plugin nodes in `plugins/houdini/v_nodes_houdini/`. All are `category: "Houdini"` and `use_exec: true`.

| node_id | Inputs | Key Outputs |
|---|---|---|
| `hou_mcp_runtime_analytics` | `report_type`, `window_sec` | `execution_metrics`, `failure_metrics`, `resource_metrics`, `workflow_statistics`, `trends`, `report_json` |
| `hou_mcp_predictive_execution` | `operations_json`, `context_json`, `include_resource_pred`, `queue_depth` | `predicted_risk`, `failure_probability`, `risk_factors`, `recommendations`, `resource_pressure`, `scheduler_status`, `prediction_json` |
| `hou_mcp_workflow_optimizer` | `operations_json`, `intent`, `include_alts` | `risk_level`, `optimization_tips`, `reorder_suggested`, `alternatives`, `preferred_strategy`, `analysis_json` |
| `hou_mcp_recommendation_engine` | `intent`, `operations_json`, `context_json` | `recommended_workflow`, `recommended_template`, `strategies`, `primary_strategy`, `workflow_confidence`, `recommendations_json` |
| `hou_mcp_execution_quality` | `execution_result_json`, `plan_json`, `history_json` | `overall_score`, `grade`, `dimensions`, `findings`, `quality_json` |

All five are safe to call at any time — no bridge calls, no execution authority.

### 18.13 Tier 5 test conventions

| File | Coverage |
|---|---|
| `tests/unit/test_workflow_optimizer.py` | analyze_plan risk levels/tips/reorder/batch/empty, recommend_alternatives dry_run/preferred/split, score_template unknown/preferred/avoid, record_outcome valid/invalid, get_optimization_history newest-first/limit, stats, singleton |
| `tests/unit/test_runtime_analytics.py` | record_execution/validation/worker_event IDs, get_report all 4 metrics keys, success_rate/rollback_rate/top_intents, resource acquire/release/stale, by_intent/by_status/validation_failure_rate, trends window, stats, singleton |
| `tests/unit/test_predictive_execution.py` | predict empty/unknown_ops/large_batch/high_delete/cook_before_connect/high_risk_score, recommendations, confidence range, predict_resource_pressure normal/heavy/cook_count, predict_dependency_conflicts self_connection/no_conflicts, predict_scheduler_congestion none/mild/severe, stats, singleton |
| `tests/unit/test_orchestration_heuristics.py` | order_operations empty/create-before-cook/delete-last/already-ordered, select_worker least-loaded/no-caps/no-idle/alternatives/empty, group_for_batching empty/delete-splits/max-size/single, route_operation explicit/houdini/no-dccs/fallback, prioritize_queue empty/priority/FIFO, list_heuristics 5 entries, singleton |
| `tests/unit/test_recommendation_engine.py` | recommend_workflow known/unknown/missing-cap/reasoning, recommend_template known/unknown/reasoning, recommend_strategy dry_run/delete/large/primary, recommend_dependency_resolution self_connection/missing_source/cycle/empty, stats, singleton |
| `tests/unit/test_resource_optimizer.py` | recommend_worker_allocation best/no-workers/should_split/load_after, recommend_transaction_sizing empty/single/delete-split/size_positive, recommend_scheduling_order empty/priority/FIFO, recommend_load_balancing healthy/overloaded/offline/empty, stats, singleton |
| `tests/unit/test_failure_intelligence.py` | analyze empty/all-success/mixed/keys/low-health-recommendation, detect_recurring_patterns repeated_intent/high_rollback/large_batch/no_failures, detect_risky_structures safe/self_connection/connect_without_create/interleaved, get_hotspot_report intent/template/no_failures, stats, singleton |
| `tests/unit/test_execution_quality.py` | evaluate committed/failed/dimensions/with-plan/partial-plan/with-history/findings/grade, score_efficiency within-budget/2x-budget/zero-duration/zero-op_count, score_stability all-success/all-failed/empty/mixed, score_validation_reliability all-valid/mixed/empty, grade A/B/C/D/F, stats, singleton |
| `tests/unit/test_studio_knowledge.py` | record_workflow_pattern/record_asset_pattern returns id, invalid outcome raises, get_best_recipe best/none/dcc_filter, query_patterns all/intent/dcc/outcome/limit/newest-first, get_optimization_insights shape/empty/success_rate/best_template/best_dcc, stats shape/write_count, disk round-trip, corrupt JSONL skipped, singleton |

**Pattern for Tier 5 tests:** no bridge fixtures needed — all modules are advisory-only. Use `autouse=True` fixture with `reset_X_for_tests()` before and after each test. For `recommendation_engine`, also reset `capability_registry`, `workflow_templates`, and `semantic_registry` to isolate from built-in state. For `studio_knowledge` disk tests, use `tempfile.NamedTemporaryFile` + explicit `os.unlink` in a try/finally.

### 18.14 Tier 5 safety audit

Every Tier 5 module was designed against the following invariants. Any PR modifying Tier 5 must re-verify these:

1. **No direct bridge calls.** None of the 9 Tier 5 modules import or call `get_bridge()` or `houdini_runtime`. Any change that introduces such a call violates the advisory-only contract.
2. **No execution authority.** No Tier 5 module calls `TransactionManager`, `ExecutionScheduler.enqueue()`, or any method that causes Houdini state mutation.
3. **Heuristics are deterministic and named.** All risk factors, patterns, and heuristics in `predictive_execution`, `failure_intelligence`, and `orchestration_heuristics` are Python-literal rules with documented names. No statistical models, no probability distributions, no opaque scoring.
4. **Studio knowledge stores no private data.** `StudioKnowledge._record()` stores only: `intent`, `outcome`, `dcc`, `op_count`, `template_id`, `duration_sec`, `op_fingerprint` (list of op type strings). Asset names, file paths, and free-text are never captured.
5. **Recommendations are advisory only.** Every module's output is a suggestion dict — never an imperative. Nodes that consume Tier 5 output still route execution through `ValidationEngine → RuntimeConstraints → ApprovalPipeline → TransactionManager`.
6. **Execution scheduler metadata does not change FIFO order.** `priority` and `risk_level` on scheduled items are readable via `get_pending_items()` but the pump loop processes items in arrival order. Reordering by priority would introduce non-determinism and is explicitly deferred.

### 18.15 Tier 5 deferred items (NOT in this work)

- **ML-backed risk models.** The current prediction engine is purely heuristic. A future tier could integrate lightweight sklearn-style models (trained on AuditStore data) as an optional enhancement — but only if they remain explainable and produce a named-factor list alongside any score.
- **`StudioKnowledge` SQLite backend.** The JSONL append store is efficient for writes but slow for large-scale queries (pattern_count > 10,000). A SQLite backend with index on `(intent, outcome, timestamp)` would support range queries and aggregation at studio scale.
- **Analytics → optimizer feedback loop.** `RuntimeAnalytics.get_execution_trends()` could feed `WorkflowOptimizer.analyze_plan()` with live window statistics (e.g. "recent executions of this op type fail at 40%"). Currently they are independent singletons.
- **Orchestration heuristic overrides.** The `OrchestrationHeuristics` class is designed for override via subclassing (all heuristics are plain methods). A future `register_heuristic_override(name, fn)` API would let studio pipelines replace individual rules without subclassing.
- **`ExecutionScheduler` priority queue.** If priority reordering is needed in the future, the pump loop must be rebuilt as a `heapq`-based priority queue. This is a breaking change to execution ordering semantics and requires careful regression testing against all scheduling tests.

---

## 19. MCP Operational Runtime (Tier 6)

Tier 6 converts the Vibrante Runtime from a library into a **real MCP server** — a process that Claude Desktop, Codex CLI, Cursor, and any MCP-compatible AI client can connect to via stdio. The MCP protocol is treated strictly as **transport only**; all intelligence, validation, constraints, and execution authority remain in the runtime layer (Tiers 1–5).

**Mandatory safety invariant (non-negotiable):**

```
External AI (Claude / Codex / GPT)
    → MCP stdio transport (MCPTransport)
    → MCPToolRegistry (semantic tools only)
    → SemanticExecutor / TransactionManager / ValidationEngine
    → houdini_runtime.execute_operation
    → AuditStore
```

`External AI → raw Houdini mutation / arbitrary Python execution` is NEVER permitted.

### 19.1 New runtime modules

```
src/runtime/
    runtime_identity.py       ← Operational identity constants consumed by bootstrap + prompt context
    runtime_bootstrap.py      ← Runtime warm-up + structured bootstrap payload for LLMs
    runtime_prompt_context.py ← System prompt and scene context block generators
    mcp_session.py            ← Connected LLM session lifecycle management
    mcp_tool_registry.py      ← MCP-exposed tool registry + all 11 semantic tool handlers
    mcp_transport.py          ← MCP stdio transport (Server, list_tools, call_tool, stdio loop)
```

Entry point: `scripts/run_vibrante_mcp.py`

### 19.2 Runtime identity (`src.runtime.runtime_identity`)

All operational identity constants are defined here and consumed by `runtime_bootstrap` and `runtime_prompt_context`. Nothing in this module does I/O or touches singletons.

```python
RUNTIME_NAME    = "Vibrante Runtime"
RUNTIME_VERSION = "2.4.0"
RUNTIME_TYPE    = "AI-native procedural orchestration runtime"
EXECUTION_MODEL = "semantic_transactional_execution"

EXECUTION_RULES             # list[str]  — 7 operational rules
RECOMMENDED_EXECUTION_FLOW  # list[str]  — 8 ordered steps (initialize → review)
MCP_TOOL_NAMES              # list[str]  — 11 canonical tool names
RUNTIME_IDENTITY            # dict       — merged identity payload
```

**Do not** hardcode `RUNTIME_NAME`, `RUNTIME_VERSION`, or `MCP_TOOL_NAMES` in any other module — always import from `runtime_identity`.

### 19.3 Runtime bootstrap (`src.runtime.runtime_bootstrap`)

Warms up all runtime singletons and produces the structured payload sent to connected LLMs at initialization time.

```python
from src.runtime.runtime_bootstrap import (
    initialize_runtime,
    get_runtime_capabilities,
    get_available_templates,
    get_available_operations,
    get_bootstrap_data,
)

status = initialize_runtime()
# {"ok": True, "initialized_at": float, "modules": [...]}

data = get_bootstrap_data()
# {
#     "runtime_name":              str,
#     "runtime_version":           str,
#     "runtime_type":              str,
#     "execution_model":           str,
#     "runtime_rules":             list[str],
#     "recommended_execution_flow": list[str],
#     "mcp_tools":                 list[str],
#     "workflow_templates":        list[str],
#     "available_capabilities":    list[dict],
#     "available_operations":      list[str],
# }
```

**Graceful degradation:** `get_runtime_capabilities`, `get_available_templates`, and `get_available_operations` each return `[]` on any error — bootstrap never fails the session.

### 19.4 Runtime prompt context (`src.runtime.runtime_prompt_context`)

Generates two prompt artifacts used by the tool handlers:

| Function | When used | Output |
|---|---|---|
| `get_system_prompt()` | Once per connection, via `initialize_runtime_context` | Full operational system prompt; embeds runtime identity, rules, recommended flow, tool guide |
| `get_contextual_prompt(scene_context)` | Mid-session refresh, when scene changes | Shorter prompt — rules + optional scene block only |
| `get_scene_context_block(ctx)` | Inside both of the above | Formatted scene text; truncates network lists at 5 (+N more); returns "not available" for None/empty |

`get_system_prompt()` is idempotent — calling it twice returns an identical string. The prompt embeds a hard rule that `initialize_runtime_context` must be called first and that `preview_execution` must precede `execute_workflow_transaction`.

### 19.5 MCP session lifecycle (`src.runtime.mcp_session`)

Sessions track structured orchestration events — never raw prompts or user text.

```python
from src.runtime.mcp_session import get_session_manager, SESSION_EVENT_TYPES

mgr = get_session_manager()
sid = mgr.create_session("claude-desktop")   # auto-records "session_started"

mgr.update_session(sid,
    active_goals=["build_pyro_smoke"],
    current_plan={"intent": "build_pyro_source", ...},
)
mgr.record_session_event(sid, "plan_generated", {"intent": "build_pyro_source"})
mgr.close_session(sid)
```

**`SESSION_EVENT_TYPES`** (12 valid event types):
`session_started`, `runtime_context_initialized`, `plan_generated`, `execution_started`, `execution_completed`, `review_completed`, `approval_requested`, `approval_granted`, `approval_rejected`, `tool_called`, `error`, `session_closed`

Unknown event types are normalised to `"error"` with the original type recorded in the event data.

**`_MUTABLE_FIELDS`** (only these can be written via `update_session`):
`active_goals`, `pending_approval_ids`, `current_plan`

`session_id`, `client_id`, and `created_at` are immutable after creation. `has_current_plan` is derived from whether `current_plan` is set.

**Singleton:** `get_session_manager()` / `reset_sessions_for_tests()`.

### 19.6 MCP tool registry (`src.runtime.mcp_tool_registry`)

Central registry of all MCP-exposed semantic tools. Completely decoupled from transport — tools can be registered, tested, and dispatched without a running transport.

```python
from src.runtime.mcp_tool_registry import (
    MCPToolRegistry,
    ToolDefinition,
    get_mcp_tool_registry,
    register_all_tools,
)

registry = get_mcp_tool_registry()

# Manual registration
defn = ToolDefinition(
    name="my_tool", description="...", inputSchema={},
    handler=async_handler_fn, category="custom",
)
registry.register_tool(defn)

# Batch registration (all 11 semantic tools)
transport = MCPTransport()
register_all_tools(transport=transport)   # also forwards each to transport.register_tool()

# Dispatch
result = await registry.dispatch_tool("plan_scene", {"prompt": "add a pyro source"})
```

`dispatch_tool` never raises: exceptions are caught and returned as `{"ok": False, "error": "..."}`. Non-dict handler results are wrapped in `{"result": value}`.

**Singleton:** `get_mcp_tool_registry()` / `reset_mcp_tool_registry_for_tests()`.

### 19.7 The 11 semantic tools

All tools are stateless from the transport perspective — session state is managed by `SessionManager`, runtime state by the Tier 1–5 singletons.

**Runtime category (3 tools):**

| Tool | Purpose |
|---|---|
| `initialize_runtime_context` | Warm up runtime singletons; return bootstrap data + system prompt |
| `query_runtime_state` | Current session state, active goals, pending approvals, module status |
| `query_scene_context` | Structured scene snapshot from `houdini_runtime.scene_context()` |

**Knowledge category (3 tools):**

| Tool | Purpose |
|---|---|
| `query_capabilities` | What operations the runtime can perform (`CapabilityRegistry`) |
| `query_workflow_templates` | Browse and optionally resolve workflow templates to op lists |
| `query_examples` | Built-in examples for common intents |

**Planning category (3 tools):**

| Tool | Purpose |
|---|---|
| `plan_scene` | NL prompt → parsed intent → context analysis → validated execution plan |
| `preview_execution` | Validate + predict risk of an op list WITHOUT executing |
| `validate_execution_plan` | Structural + constraint validation only |

**Execution category (2 tools):**

| Tool | Purpose |
|---|---|
| `execute_workflow_transaction` | Execute a plan via the transaction system (dual-path: named intent OR plan_json) |
| `review_execution` | Post-execution review: did execution match intent? |

**`execute_workflow_transaction` dual-path:**
1. `intent` supplied (no `plan_json`) → delegates to `SemanticExecutor.execute()` — the full Tier 2.75 pipeline (registry → constraints → validation → resources → transaction → commit/rollback)
2. `plan_json` supplied → safety gates (ok=False rejected, requires_approval blocked without approver) → `TransactionManager.begin_transaction` → `execute_operation` loop → `commit_transaction` or `rollback_transaction`

**Safety gates on execution:**
- Plans with `ok=False` are rejected before any bridge call
- Plans with `requires_approval=True` return `status="pending_approval"` unless `approver` is supplied
- All ops validated by `ValidationEngine` + `RuntimeConstraints` before execution begins
- `build_node_chain` spec is validated for duplicate ids, missing ids, self-connections, and non-existent parents

### 19.8 Transport architecture (`src.runtime.mcp_transport`)

The transport wraps the `mcp` SDK server-side APIs with Vibrante's tool registry.

```
External AI client (stdio)
    ↓ stdin/stdout
MCPTransport._run_async()
    ├── app.list_tools()  → queries MCPToolRegistry.list_tools()
    └── app.call_tool()   → dispatches to MCPToolRegistry.dispatch_tool()
                                ↓
                          returns TextContent(type="text", text=json.dumps(result))
```

**Deferred SDK imports:** `mcp.server.Server`, `mcp.server.stdio.stdio_server`, and `mcp.types` are imported lazily on the first `run_stdio()` call via `_require_mcp_server()`. This mirrors the client-side pattern in `mcp_runtime.py` — importing `mcp_transport` at startup costs nothing.

**`run_stdio()`** calls `asyncio.run(self._run_async())` — safe because `run_vibrante_mcp.py` is a standalone script, not embedded in the Qt event loop.

**`is_running`** property is guarded by `threading.Lock` for thread-safe inspection from signal handlers.

**Singleton:** `get_mcp_transport()` / `reset_mcp_transport_for_tests()`.

### 19.9 Entry point (`scripts/run_vibrante_mcp.py`)

```python
transport = MCPTransport()
initialize_runtime()          # warms all singletons
register_all_tools(transport) # registers all 11 tools + forwards to transport
transport.run_stdio()         # blocks until the client disconnects
```

The script adds `_ROOT` (project root) to `sys.path` before any imports so `src.*` is importable without installation.

**Without Houdini:** planning, knowledge, and capability tools work fully. `query_scene_context` and `execute_workflow_transaction` return a clear "bridge not available" message when the TCP bridge is not reachable — they never crash the process.

### 19.10 AI client integration

**Claude Desktop** (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "vibrante": {
      "command": "python",
      "args": ["D:/Vibrante-Node/source/scripts/run_vibrante_mcp.py"],
      "env": { "VIBRANTE_HOU_PORT": "18811" }
    }
  }
}
```

**Codex CLI** (`codex.toml` or `~/.config/codex/config.toml`):

```toml
[mcp_servers.vibrante]
command     = "python"
args        = ["D:/Vibrante-Node/source/scripts/run_vibrante_mcp.py"]
trust_level = "trusted"
```

**Cursor** (`.cursor/mcp.json` in workspace root):

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

**Prerequisites:**

```bash
pip install "mcp>=1.0.0" pydantic toposort
```

For Houdini scene operations:
1. Open Houdini with the Vibrante-Node plugin installed.
2. Click **Vibrante-Node → Launch Vibrante-Node** from the Houdini menu bar (starts bridge on port 18811).
3. Run the entry point script — tools like `query_scene_context` and `execute_workflow_transaction` will connect to the bridge automatically.

### 19.11 Orchestration execution invariants (non-negotiable)

1. **No raw Houdini API exposure.** `MCPToolRegistry` must never register `create_node`, `set_parm`, `set_parms`, `run_python`, `run_code`, `delete_node`, `connect_nodes`, `cook_node`, or any other direct bridge method. The `FORBIDDEN_TOOLS` set in `test_mcp_tool_registry.py` is the authoritative list.
2. **No arbitrary Python execution.** No tool handler may accept or evaluate a `code` / `python` / `script` argument. All execution is structured, validated, and deterministic.
3. **All mutations route through the transaction system.** `execute_workflow_transaction` calls either `SemanticExecutor.execute()` (named intent path) or `TransactionManager.begin_transaction` + `execute_operation` per op (plan path). There is no direct call to `houdini_runtime` in tool handler code outside of query operations.
4. **Validation before mutation.** Every `execute_workflow_transaction` call goes through `ValidationEngine.validate_operations()` and `RuntimeConstraints.validate_transaction()` before any bridge interaction.
5. **Approval gate on dangerous plans.** Plans with `requires_approval=True` return `status="pending_approval"` without executing. The caller must supply an `approver` identity to proceed.
6. **Session events, not raw text.** `MCPSession.record_event()` accepts only valid event types from `SESSION_EVENT_TYPES`. User messages and LLM output are never stored in session history.
7. **Tool dispatch never raises.** `dispatch_tool()` wraps all handler execution in `try/except`. Exceptions are captured and returned as `{"ok": False, "error": str(exc)}` — the transport process never crashes due to a tool failure.

### 19.12 Forbidden tool surface (test-enforced)

The `test_mcp_tool_registry.py::test_forbidden_tools_not_present` test fails loudly if any of these names appear in the registered tool set. This prevents accidental exposure of raw bridge methods:

```python
FORBIDDEN_TOOLS = {
    "create_node", "set_parm", "set_parms", "run_python",
    "run_code", "delete_node", "raw_houdini_execute",
    "connect_nodes", "cook_node",
}
```

Any new tool registration must not use these names, even as aliases.

### 19.13 Test conventions

| File | Coverage |
|---|---|
| `tests/unit/test_mcp_transport.py` | Singleton, not_running on creation, register_tool/multiple, stats structure, shutdown, `_require_mcp_server` raises when unavailable, `_run_async` with fully mocked mcp SDK, running flag cleared after `_run_async`, `run_stdio` calls `asyncio.run`, thread-safe concurrent registration |
| `tests/unit/test_mcp_tool_registry.py` | Singleton, `register_all_tools` count == 11, all expected tools present, forbidden tools absent, tools have required fields, categories are semantic only, passes to transport, dispatch known/unknown/exception/non-dict, handler happy paths (mocked runtimes), stats by category (3+3+3+2) |
| `tests/unit/test_mcp_session.py` | Singleton, create_session UUID format, client_id with/without, two sessions distinct, get_session keys, nonexistent returns None, not closed by default, close marks closed, update active_goals/current_plan, update ignores non-mutable, record event valid/invalid normalised, history timestamps, list_sessions, active_session_count, stats counts, to_dict copies not references |
| `tests/unit/test_runtime_bootstrap.py` | initialize_runtime structure, loads at least some modules, ok with forced module errors, get_runtime_capabilities list + graceful, get_available_templates list of strings + graceful, get_available_operations includes builtins + graceful, get_bootstrap_data full key set, JSON-serialisable |
| `tests/unit/test_runtime_prompt_context.py` | execution_rules_block (header, all rules, count == len), recommended_flow_block (header, 8 steps), tool_guide (all 11 tool names, 4 category headers), system_prompt (runtime_name, runtime_type, rules, flow, tools, initialize_first, preview before execute ordering, no-direct-houdini mention, idempotent), scene_context_block (None, empty, full, networks, truncation at 5+, selection, HDAs), contextual_prompt shorter than system_prompt |

**Pattern for transport tests:** monkey-patch `mod._Server`, `mod._stdio_server`, and `mod._mcp_types` with mock objects. Use an `asynccontextmanager` fake `stdio_server` that yields `(MagicMock(), MagicMock())`. Always restore the originals in `finally`. No live `mcp` SDK required.

**Pattern for tool registry handler tests:** use `unittest.mock.patch` on the specific runtime module that the handler imports inside its function body (e.g. `patch("src.runtime.runtime_bootstrap.initialize_runtime", ...)`). This avoids importing the full runtime dependency chain in tests.

**Pattern for session tests:** use an `autouse=True` fixture that calls `reset_sessions_for_tests()` before and after each test.

### 19.14 `src/runtime/__init__.py` additions

The 6 new modules are added to `__all__` and documented in the module docstring with `(§19)` annotations. They are loaded by the existing `__getattr__` lazy loader — no eager imports at startup.

```python
"runtime_identity",       # (§19) Operational identity constants
"runtime_bootstrap",      # (§19) Runtime warm-up + bootstrap payload
"runtime_prompt_context", # (§19) System prompt + scene context generators
"mcp_session",            # (§19) Connected LLM session lifecycle
"mcp_tool_registry",      # (§19) MCP-exposed semantic tool registry
"mcp_transport",          # (§19) MCP stdio transport (Server + message loop)
```

### 19.15 Tier 6 deferred items (NOT in this work)

- **HTTP/SSE transport.** `MCPTransport` currently implements stdio only. An SSE transport for remote AI clients over HTTPS requires the mcp SDK's server-side SSE APIs + authentication middleware.
- **Multi-session concurrency.** The current implementation accepts one stdio connection at a time (one `asyncio.run()` call). Multiple simultaneous AI clients would require the transport to route each connection's session to a distinct `SessionManager` entry and fan out dispatch concurrently.
- **Session persistence across reconnects.** Sessions are in-memory only; reconnecting clients start a fresh session. A persistent session store (keyed by `client_id`) would restore goals and pending approvals across process restarts.
- **Auto-session recording in tool handlers.** Currently, `record_session_event` is called explicitly only in the `initialize_runtime_context` handler. Wiring all 11 handlers to auto-record `"tool_called"` events would give a complete per-session audit trail without manual per-handler effort.
- **`query_examples` live resolution.** The current handler returns static example strings. A future version could query `PlanningMemory` + `SemanticMemory` to surface the most successful real past executions as dynamic examples.
