# 09 — Advanced Topics

**Vibrante-Node v2.5.0 — Technical Reference**

This document covers advanced usage patterns, production deployment, DCC integration deep-dives, headless execution, custom executors, security considerations, and version migration. It is intended for pipeline TDs, tool developers, and studio engineers who need to go beyond the basic node-authoring workflow.

---

## Table of Contents

1. [Building a Node Plugin Package](#1-building-a-node-plugin-package)
2. [Remote and Headless Execution](#2-remote-and-headless-execution)
3. [Distributed Workflows](#3-distributed-workflows)
4. [Custom Executors](#4-custom-executors)
5. [Houdini Integration Deep-Dive](#5-houdini-integration-deep-dive)
6. [Maya Headless Integration](#6-maya-headless-integration)
7. [Blender Headless Integration](#7-blender-headless-integration)
8. [Prism Pipeline Integration](#8-prism-pipeline-integration)
9. [Production Deployment with PyInstaller](#9-production-deployment-with-pyinstaller)
10. [Scaling Workflows](#10-scaling-workflows)
11. [Memory and State Management](#11-memory-and-state-management)
12. [Security Considerations](#12-security-considerations)
13. [Version Migration](#13-version-migration)
14. [Extending the Node Builder with AI](#14-extending-the-node-builder-with-ai)
15. [Hot-Reload during Development](#15-hot-reload-during-development)

---

## 1. Building a Node Plugin Package

A node plugin package is a directory (or zip-distributed directory) containing `.json` node definition files and optionally `.py` script files. The engine loads it at startup when the `v_nodes_dir` environment variable points to its location.

### Recommended folder structure

```
my_pipeline_nodes/
├── README.md
├── icons/
│   └── my_pipeline.svg
├── scripts/               # optional; shown in Scripts menu via v_scripts_path
│   ├── publish_asset.py
│   └── open_shot_folder.py
└── nodes/
    ├── my_get_asset.json
    ├── my_publish_version.json
    ├── my_open_in_nuke.json
    └── my_slate_generator.json
```

### Registering the package

#### Option A: Environment variable (any host)

Set `v_nodes_dir` to the `nodes/` subdirectory before launching Vibrante-Node:

```batch
:: Windows batch
set v_nodes_dir=C:\pipeline\my_pipeline_nodes\nodes
python src\main.py
```

```bash
# Linux/macOS
export v_nodes_dir=/pipeline/my_pipeline_nodes/nodes
python src/main.py
```

Multiple directories are separated by the OS path separator (`;` on Windows, `:` on Linux/macOS):

```
v_nodes_dir=C:\nodes\houdini_nodes;C:\nodes\prism_nodes;C:\nodes\nuke_nodes
```

#### Option B: Houdini package JSON

When Vibrante-Node is launched from Houdini, the `vibrante_node.json` package file can set `v_nodes_dir` for that DCC context:

```json
{
    "env": [
        { "VIBRANTE_NODE_APP": "C:/pipeline/vibrante_node_app" },
        { "VIBRANTE_PYTHON_EXE": "C:/Python311/python.exe" },
        { "v_nodes_dir": "C:/pipeline/my_pipeline_nodes/nodes" }
    ],
    "path": "$VIBRANTE_NODE_APP/plugins/houdini/houdini"
}
```

#### Option C: scripts directory for v_scripts_path

Point `v_scripts_path` to the `scripts/` subdirectory to populate the Scripts menu:

```
v_scripts_path=C:\pipeline\my_pipeline_nodes\scripts
```

Script files (`.py`) in that directory appear as clickable menu items. They are executed with:
```python
exec(script_code, {'window': main_window, 'scene': current_scene})
```

### Node JSON authoring checklist

- `node_id` must be globally unique. Use a studio prefix: `acme_get_asset`, not `get_asset`.
- `category` groups nodes in the Library panel. Use a consistent studio category: `"ACME Pipeline"`.
- `icon_path` can be an absolute path or a path relative to the app root.
- `use_exec: true` for any node that participates in the execution flow.
- Include `exec_in` / `exec_out` in the `inputs` / `outputs` arrays when `use_exec: true`; the registry auto-inserts them if missing.
- `python_code` must be a single JSON string. Use `\n` for newlines and `\"` for quotes. Test parsing with Python's `json.loads()` before committing.

---

## 2. Remote and Headless Execution

Vibrante-Node does not have a dedicated headless runner, but the engine can be instantiated and run without the Qt UI by running `src/core/engine.py` directly from a script.

### Minimal headless runner

```python
# headless_run.py
import asyncio
import json
import sys

# Qt is required for QObject (NetworkExecutor inherits it)
from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)

from src.core.models import WorkflowModel
from src.core.graph import GraphManager
from src.core.registry import NodeRegistry
from src.core.engine import NetworkExecutor

# Load node definitions
NodeRegistry.load_all_with_extras("nodes")

# Load workflow
with open(sys.argv[1]) as f:
    data = json.load(f)
model = WorkflowModel.model_validate(data)

gm = GraphManager()
gm.from_model(model)

# Wire up logging
executor = NetworkExecutor(gm)
executor.node_log.connect(lambda nid, msg, lvl: print(f"[{lvl}] {msg}"))
executor.node_error.connect(lambda nid, msg: print(f"ERROR: {msg}", file=sys.stderr))
executor.execution_finished.connect(lambda ok: print(f"Finished: {ok}") or app.quit())

# Run via asyncio directly (no _EventLoopRunner needed for headless)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

task = loop.create_task(executor.run())

# Pump both loops
import time
while not task.done():
    loop.call_soon(loop.stop)
    loop.run_forever()
    app.processEvents()
    time.sleep(0.005)

loop.close()
sys.exit(0 if not executor._is_stopped else 1)
```

Usage:
```
python headless_run.py my_workflow.json
```

### CLI argument pattern

For scheduled or farm-submitted workflows, pass the workflow path and any parameter overrides as arguments:

```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("workflow", help="Path to .json workflow file")
parser.add_argument("--param", nargs=2, action="append", metavar=("NODE_ID:PORT", "VALUE"))
args = parser.parse_args()

# Override parameters before execution:
if args.param:
    for node_port, value in args.param:
        node_id, port = node_port.split(":", 1)
        for node_model in model.nodes:
            if node_model.node_id == node_id:
                node_model.parameters[port] = value
```

### Exit code convention

Return exit code `0` on success, `1` on failure. Connect `execution_finished`:
```python
_result = [True]
executor.execution_finished.connect(lambda ok: _result.__setitem__(0, ok))
# ... run ...
sys.exit(0 if _result[0] else 1)
```

---

## 3. Distributed Workflows

Vibrante-Node does not have built-in distributed execution, but workflows can be split across machines using the following strategies.

### Strategy 1: Split at file boundaries

Design your workflow so that each segment writes its outputs to disk (files, databases, or shared network storage) at strategic checkpoints. Split the monolithic workflow into multiple smaller `.json` files:

```
00_asset_resolve.json    → writes asset_list.json to NAS
01_scene_setup.json      → reads asset_list.json, writes hip files to NAS
02_render_submit.json    → reads hip paths, submits to farm
```

Each workflow file is a self-contained unit that can be run on any machine with `headless_run.py`. A pipeline coordinator (e.g. a render farm scheduler, a Jenkins pipeline, or a simple Python script) runs them in sequence.

### Strategy 2: Action-list pattern with DCC subprocesses

For DCC-specific work, use the headless action-list pattern (see sections 6 and 7). The Vibrante-Node workflow runs on one machine and launches DCC subprocesses on the same or remote machines via network file system + command-line:

```python
# In a node's execute():
import subprocess
ssh_cmd = ["ssh", "render_farm_host", "mayapy", "/nas/scripts/process_asset.py", asset_path]
result = await asyncio.create_subprocess_exec(*ssh_cmd, stdout=asyncio.subprocess.PIPE)
stdout, _ = await result.communicate()
```

### Strategy 3: Message queue integration

For true distributed workflows, add a node that publishes a message (e.g. to RabbitMQ, Redis Streams, or a REST API) and a separate workflow that subscribes and processes. This pattern decouples the publisher from the consumer and allows arbitrary scaling.

### Practical considerations

- **Shared filesystem**: All machines must be able to read/write to a common NAS path for the file-passing strategy.
- **Node registration**: Each machine must have `v_nodes_dir` pointing to the same plugin package (or a network copy of it).
- **Credentials and secrets**: Pass credentials via environment variables, not hardcoded in node JSON.
- **Idempotency**: Design nodes so that re-running them produces the same result. This makes retry logic safe.

---

## 4. Custom Executors

### Subclassing NetworkExecutor

You can subclass `NetworkExecutor` to add pre/post hooks, intercept signals, or alter execution behaviour:

```python
from src.core.engine import NetworkExecutor

class AuditingExecutor(NetworkExecutor):
    """Logs every node execution to an external audit trail."""

    def __init__(self, graph_manager, audit_client):
        super().__init__(graph_manager)
        self._audit = audit_client
        # Connect to our own signals to audit them
        self.node_started.connect(self._on_started)
        self.node_finished.connect(self._on_finished)
        self.node_error.connect(self._on_error)

    def _on_started(self, node_id):
        self._audit.record_start(str(node_id))

    def _on_finished(self, node_id, status):
        self._audit.record_finish(str(node_id), status)

    def _on_error(self, node_id, message):
        self._audit.record_error(str(node_id), message)
```

### Adding pre-execution hooks

Override `run()` to inject setup logic:

```python
async def run(self, init_only=False):
    # Pre-execution setup
    await self._pre_run_hook()
    # Run the standard engine
    await super().run(init_only=init_only)
    # Post-execution cleanup
    await self._post_run_hook()

async def _pre_run_hook(self):
    self.node_log.emit(
        list(self.graph_manager.nodes.keys())[0],
        "Pre-run hook: validating credentials...",
        "info"
    )
    # ... your setup logic ...

async def _post_run_hook(self):
    # ... your cleanup logic ...
    pass
```

### Intercepting node output

Override `_run_single_node_impl()` to intercept output after each node:

```python
async def _run_single_node_impl(self, node_id, is_data_pull=False):
    result = await super()._run_single_node_impl(node_id, is_data_pull)
    if result and node_id in self.node_results:
        self._validate_outputs(node_id, self.node_results[node_id])
    return result

def _validate_outputs(self, node_id, outputs):
    for key, value in outputs.items():
        if value is None and key != "exec_out":
            self.node_log.emit(node_id, f"Warning: output '{key}' is None", "warning")
```

### Using a custom executor in the UI

```python
# In MainWindow.execute_pipeline():
from my_pipeline.executor import AuditingExecutor

executor = AuditingExecutor(graph_manager, audit_client=self._audit_client)
runner = _EventLoopRunner(executor)
# ... connect signals, start runner ...
```

---

## 5. Houdini Integration Deep-Dive

### Architecture overview

```
Houdini process                          Vibrante-Node subprocess
┌─────────────────────────────────┐     ┌──────────────────────────────────┐
│  hou (Python API)               │     │  NetworkExecutor                 │
│                                 │     │      │                           │
│  vibrante_hou_server.py         │◄────┤  HouBridge._send()               │
│    ├─ _accept_loop (thread)     │     │      │ JSON-RPC over TCP          │
│    ├─ _handle_client (thread)   │     │      │ 127.0.0.1:18811            │
│    └─ hdefereval.executeDeferred│     │      │                           │
│           (Houdini main thread) │     │  node python_code:               │
│                                 │     │    bridge = get_bridge()         │
│  pythonrc.py (startup)          │     │    bridge.create_node(...)       │
│  vibrante_node_houdini.py       │     │    bridge.set_parm(...)          │
│    ├─ launch()                  │─────►    bridge.run_code(...)          │
│    ├─ setup_env()               │     └──────────────────────────────────┘
│    └─ _ensure_command_server()  │
└─────────────────────────────────┘
```

### RPC server lifecycle (vibrante_hou_server.py)

The server starts when `launch()` is called inside Houdini:

1. `_ensure_command_server()` calls `vibrante_hou_server.start()`.
2. `start()` acquires `_lock` to prevent double-bind race conditions.
3. Creates a TCP socket bound to `127.0.0.1:18811` with `SO_REUSEADDR`.
4. Starts `_accept_loop()` in a daemon background thread.
5. Returns the port number, which is passed to the subprocess as `VIBRANTE_HOU_PORT`.

Per client connection, `_handle_client()` runs in its own daemon thread, reading newline-delimited JSON commands and dispatching them.

### Main-thread dispatch

All Houdini API calls must run on Houdini's main thread. The server uses `hdefereval.executeDeferred()`:

```python
event = threading.Event()
result_box = {"result": None, "error": None, "done": False}

def _run(h=handler, p=params, box=result_box, evt=event):
    try:
        box["result"] = h(p)
    except Exception as exc:
        box["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    box["done"] = True
    evt.set()

hdefereval.executeDeferred(_run)
event.wait(timeout=30)
```

The client thread blocks on `event.wait()` (max 30 seconds) while Houdini's main thread executes the command. If Houdini is blocked (e.g. cooking a slow geometry), the wait times out and the error is returned to the client.

### HouBridge client thread safety

`HouBridge._send()` acquires `self._lock` before touching the socket. This means multiple nodes executed concurrently (from parallel exec chains) can safely call bridge methods without corrupting the response stream.

### Environment variable flow

When `launch()` is called:

1. `setup_env()` builds the subprocess environment:
   - Strips `PYTHONHOME`, `PYTHONSTARTUP` (Houdini's Python vars that break system Python).
   - Adds `$HFS/python3.Xlibs` to `PYTHONPATH` (so `import hou` works in the subprocess).
   - Adds `$HFS/bin` to `PATH` (for `_hou.pyd` DLL dependencies).
   - Sets `v_nodes_dir` to `plugins/houdini/v_nodes_houdini/`.
   - Sets `v_scripts_path` to `plugins/houdini/v_scripts_houdini/`.
   - Sets `VIBRANTE_HOUDINI_MODE=subprocess`.
   - Sets `VIBRANTE_HIP_FILE` if a .hip is open.
   - Sets `VIBRANTE_HOU_PORT` to the command server port.

2. `_find_system_python()` locates a Python 3.11 installation with PyQt5 (Houdini's Python ships without PyQt5). Resolution order: `VIBRANTE_PYTHON_EXE` env var → Windows Registry → Windows Python Launcher → common paths → PATH scan.

3. `subprocess.Popen([python_exe, "src/main.py"], cwd=app_root, env=env)` launches the UI.

### Accessing HIP context in nodes

After `launch_with_context()`, these environment variables are available inside node `execute()` code:

```python
import os
hip_file = os.environ.get("VIBRANTE_HIP_FILE", "")
hip_name = os.environ.get("VIBRANTE_HIP_NAME", "")
hou_version = os.environ.get("VIBRANTE_HOUDINI_VERSION", "")
```

### Known server behaviours and workarounds

| Situation | Behaviour |
|-----------|-----------|
| `hou.playbar` in headless (hbatch/hython) | `AttributeError` caught; `frame_range` returns `[1, 240]` |
| `setDisplayFlag` on unsupported node types | `getattr` capability check + `hou.OperationFailed` guard; raises `ValueError` with message |
| Double `start()` call | `_lock` prevents double-bind; logs existing port and returns it |
| Houdini blocked cooking > 30s | `event.wait(timeout=30)` expires; error returned to client; bridge disconnects |
| Broken pipe (Houdini closed) | Client catches `BrokenPipeError`, reconnects once, retries |

---

## 6. Maya Headless Integration

Maya integration uses the **action-list pattern**: nodes in Vibrante-Node build a list of action dictionaries, which a separate Maya subprocess processes in a single headless invocation. This avoids the overhead of launching Maya once per node.

### Action node skeleton

```python
# nodes/maya_action_set_attr.json python_code:
from src.nodes.base import BaseNode

class Maya_Action_Set_Attr(BaseNode):
    name = "maya_action_set_attr"
    category = "Maya"

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("actions_in", "list")
        self.add_input("node_path", "string", widget_type="text")
        self.add_input("attribute", "string", widget_type="text")
        self.add_input("value", "any")
        self.add_output("actions_out", "list")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        actions = list(inputs.get("actions_in") or [])
        actions.append({
            "type": "set_attr",
            "node": inputs.get("node_path", ""),
            "attr": inputs.get("attribute", ""),
            "value": inputs.get("value"),
        })
        return {"actions_out": actions, "exec_out": True}

def register_node():
    return Maya_Action_Set_Attr
```

### Maya executor node

A terminal node (e.g. `maya_headless_execute`) receives the final action list and runs Maya:

```python
import subprocess, json, tempfile, os

async def execute(self, inputs):
    actions = inputs.get("actions_in") or []
    scene_file = inputs.get("scene_file", "")
    maya_exe = inputs.get("maya_exe", "mayapy")

    # Write actions to temp file (avoid shell quoting issues)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                     delete=False) as f:
        json.dump({"scene": scene_file, "actions": actions}, f)
        actions_path = f.name

    runner_script = os.path.join(
        os.path.dirname(__file__), "maya_runner.py"
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            maya_exe, runner_script, actions_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            self.log_error(f"Maya failed:\n{stderr.decode()}")
            return {"success": False, "exec_fail": True}

        self.log_success("Maya execution complete.")
        return {"success": True, "exec_out": True}
    finally:
        os.unlink(actions_path)
```

### Maya runner script (maya_runner.py)

```python
# maya_runner.py — runs inside mayapy
import sys, json
import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds

with open(sys.argv[1]) as f:
    data = json.load(f)

if data.get("scene"):
    cmds.file(data["scene"], open=True, force=True)

handlers = {
    "set_attr": lambda a: cmds.setAttr(f"{a['node']}.{a['attr']}", a["value"]),
    "select":   lambda a: cmds.select(a["nodes"]),
    # ... add more action types here
}

for action in data.get("actions", []):
    handler = handlers.get(action["type"])
    if handler:
        handler(action)
    else:
        print(f"Warning: unknown action type '{action['type']}'", file=sys.stderr)

maya.standalone.uninitialize()
```

### Node ID convention

Maya action nodes should use the prefix `maya_action_` (e.g. `maya_action_set_attr`, `maya_action_export_fbx`). The terminal executor node uses `maya_headless_execute`. Use category `"Maya"` for all Maya nodes.

---

## 7. Blender Headless Integration

Blender follows the same action-list pattern as Maya. The key difference is that Blender's headless Python (`blender --background --python script.py`) does not use `standalone.initialize()`.

### Blender runner script (blender_runner.py)

```python
# blender_runner.py — runs inside blender --background
import sys, json
import bpy

with open(sys.argv[-1]) as f:
    data = json.load(f)

if data.get("scene"):
    bpy.ops.wm.open_mainfile(filepath=data["scene"])

handlers = {
    "set_object_location": lambda a: (
        setattr(bpy.data.objects[a["name"]].location, "x", a["x"]),
        setattr(bpy.data.objects[a["name"]].location, "y", a["y"]),
        setattr(bpy.data.objects[a["name"]].location, "z", a["z"]),
    ),
    "render": lambda a: (
        setattr(bpy.context.scene.render, "filepath", a.get("output", "/tmp/")),
        bpy.ops.render.render(write_still=True),
    ),
    # ... more action types
}

for action in data.get("actions", []):
    handler = handlers.get(action["type"])
    if handler:
        handler(action)
    else:
        print(f"Unknown action: {action['type']}")

bpy.ops.wm.quit_blender()
```

### Launching Blender subprocess

```python
proc = await asyncio.create_subprocess_exec(
    "blender",
    "--background",
    "--python", runner_script,
    "--",            # separator: everything after -- is sys.argv in the script
    actions_path,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
```

Note the `--` separator: Blender passes all arguments after `--` as `sys.argv` to the Python script.

### Node ID convention

Use prefix `blender_action_` for action nodes and `blender_headless_execute` for the terminal node. Use category `"Blender"`.

---

## 8. Prism Pipeline Integration

Prism Pipeline is a studio project management system. Vibrante-Node integrates with it via `PrismCore`, which provides APIs for assets, shots, versions, and file paths.

### Bootstrap (prism_core_init node)

Place a `prism_core_init` node anywhere in the graph. The engine detects it during `_bootstrap_prism_if_needed()` before main graph execution and calls `bootstrap_prism_core()` on the Qt main thread:

```python
# From engine.py
for node_id, node_model in self.graph_manager.nodes.items():
    if node_model.node_id == "prism_core_init":
        params = node_model.parameters
        bootstrap_prism_core(
            prism_scripts_path=params.get("prism_scripts_path",
                                          "C:/Program Files/Prism2/Scripts"),
            load_project=bool(params.get("load_project", True)),
            show_ui=bool(params.get("show_ui", False)),
        )
        break
```

`bootstrap_prism_core()` (`src/utils/prism_core.py`) adds `prism_scripts_path` to `sys.path`, imports `PrismCore`, and calls `PrismCore.create(prismArgs=["noUI", "loadProject"])`. The resulting object is stored in both `_CACHED_PRISM_CORE` (module-level) and `BaseNode.memory["_prism_core"]`.

**The `prism_core_init` node does not need to be wired to anything.** Its mere presence in the graph triggers the bootstrap.

### Core resolution (resolve_prism_core)

Every `prism_*` node (except `prism_core_init`) gets its `core = inputs.get('core')` line automatically rewritten by `NodeRegistry._prepare_definition()` to:

```python
core = resolve_prism_core(inputs)
```

`resolve_prism_core()` checks four sources in order:
1. `inputs["core"]` (explicit wire — backward compatible)
2. `BaseNode.memory["_prism_core"]` (shared workflow memory)
3. `_CACHED_PRISM_CORE` (module-level cache, survives multiple runs)
4. `__main__.pcore` (for nodes running directly inside a DCC that has Prism loaded)

### Prism node categories and examples

Prism nodes are organised by the area of the pipeline they address. All use `category: "Prism"` and `icon_path: "icons/prism_icon.png"`.

| Category | Node IDs (examples) |
|----------|-------------------|
| Project | `prism_get_project_info`, `prism_set_project` |
| Assets | `prism_get_assets`, `prism_get_asset_info`, `prism_create_asset` |
| Shots | `prism_get_shots`, `prism_get_shot_info`, `prism_create_shot` |
| Sequences | `prism_get_sequences` |
| Versions | `prism_get_latest_version`, `prism_create_version`, `prism_get_version_path` |
| Export | `prism_export_scene`, `prism_publish_version` |
| Import | `prism_import_product`, `prism_load_asset_version` |
| Render | `prism_submit_render`, `prism_get_render_outputs` |
| Playblast | `prism_create_playblast` |
| Review | `prism_open_in_rv`, `prism_send_to_review` |
| Users | `prism_get_current_user`, `prism_get_users` |
| Settings | `prism_get_setting`, `prism_set_setting` |

### Writing a Prism node

```json
{
    "node_id": "prism_get_assets",
    "name": "prism_get_assets",
    "category": "Prism",
    "icon_path": "icons/prism_icon.png",
    "use_exec": true,
    "inputs": [
        {"name": "exec_in", "type": "exec"},
        {"name": "entity_type", "type": "string", "widget_type": "text", "default": ""}
    ],
    "outputs": [
        {"name": "exec_out", "type": "exec"},
        {"name": "assets", "type": "list"}
    ],
    "python_code": "..."
}
```

```python
# python_code (the registry auto-rewrites the core line):
from src.nodes.base import BaseNode

class Prism_Get_Assets(BaseNode):
    name = "prism_get_assets"

    def __init__(self):
        super().__init__()
        self.add_input("entity_type", "string", widget_type="text")
        self.add_output("assets", "list")

    async def execute(self, inputs):
        core = inputs.get("core")   # auto-rewritten to resolve_prism_core(inputs)
        if core is None:
            self.log_error("PrismCore not initialized.")
            return {"assets": [], "exec_out": True}
        try:
            assets = core.getAssets()
            return {"assets": assets, "exec_out": True}
        except Exception as e:
            self.log_error(f"Prism error: {e}")
            return {"assets": [], "exec_out": True}

def register_node():
    return Prism_Get_Assets
```

### Qt compatibility for Prism

Prism internally uses `QColor.fromString()` and `shiboken2` stubs that may not exist in all Qt5 builds. `src/utils/qt_compat.py` provides shims:

```python
from src.utils.qt_compat import ensure_qcolor_from_string, ensure_shiboken_stub
ensure_qcolor_from_string()
ensure_shiboken_stub()
```

`bootstrap_prism_core()` calls both of these before importing `PrismCore`. Prism node authors do not need to call them directly.

---

## 9. Production Deployment with PyInstaller

Vibrante-Node is bundled for distribution using PyInstaller with the spec file `vibrante_node.spec`.

### Bundling

```batch
pyinstaller vibrante_node.spec
```

The resulting `dist/vibrante_node/` directory (or `dist/vibrante_node.exe` for one-file mode) contains the full Python runtime, all dependencies, and the application code.

### Spec file customisation points

The spec file needs attention in several areas:

#### Hidden imports

Some imports are dynamic (via `exec()` in `NodeRegistry`) and PyInstaller cannot detect them statically. Add them to `hiddenimports`:

```python
# vibrante_node.spec
a = Analysis(
    ['src/main.py'],
    hiddenimports=[
        'PyQt5.Qsci',           # optional QScintilla
        'toposort',
        'pydantic',
        'pydantic.v1',          # some Prism versions use pydantic v1 shim
        'PrismCore',            # if Prism nodes are bundled
    ],
    # ... other Analysis arguments ...
)
```

#### Data files

Node JSON files and icons must be included as data:

```python
a = Analysis(
    # ...
    datas=[
        ('nodes', 'nodes'),           # bundled node definitions
        ('icons', 'icons'),           # icon SVG/PNG files
        ('plugins', 'plugins'),       # plugin directories
    ],
    # ...
)
```

The `resource_path()` function (`src/utils/paths.py`) handles the runtime path difference between running from source and running from a PyInstaller bundle (using `sys._MEIPASS` when frozen).

#### User nodes directory

User-created nodes are stored in `app_dir()/nodes/`, where `app_dir()` returns the directory of the executable (not `sys._MEIPASS`). This allows users to add nodes without extracting the bundle:

```
dist/vibrante_node/          ← PyInstaller bundle root
    vibrante_node.exe        ← or vibrante_node on Linux/macOS
    _internal/               ← frozen modules and bundled nodes
        nodes/               ← bundled node definitions (resource_path)
nodes/                       ← user-created nodes (app_dir)
```

#### Excluding Houdini-specific dependencies

Houdini integration relies on `hou`, which is only available inside Houdini's Python. Do **not** bundle `hou` in the PyInstaller distribution. The bridge is designed to work via dynamic import at runtime.

### Distributing to artists

Typical studio distribution:

1. Build the bundle on a reference machine (same OS as target).
2. Place the `dist/vibrante_node/` directory on a network share.
3. Artists run `vibrante_node.exe` (or `./vibrante_node`) directly from the network share, or IT creates a shortcut/module to it.
4. Each artist's user nodes directory (`app_dir()/nodes/`) is local to their machine or in their user profile.

### Version locking

Pin all dependencies in `requirements.txt` to exact versions for reproducible builds:

```
PyQt5==5.15.10
PyQt5-Qt5==5.15.2
pydantic==2.6.4
toposort==1.10
QScintilla==2.14.1
```

---

## 10. Scaling Workflows

### Node count

The engine is designed for typical workflow sizes of 5–50 nodes. For graphs with 100+ nodes:

- **Pre-calculation is O(n + e)**: The lookup maps (`_incoming_data_conns`, `_driven_by_flow`) are built once per run from all connections. This is fast even for large graphs.
- **Topological sort**: The `toposort` library is O(n + e). Sorting 1000 nodes typically takes under 1 ms.
- **Scene rendering**: The Qt scene renders all visible items on every paint event. For 200+ nodes, enable Qt's BSP tree (`scene.setItemIndexMethod(QGraphicsScene.BspTreeIndex)`) for faster item lookup. This is the default.
- **History snapshots**: Each `push_history()` serialises the entire graph. For 100+ nodes with complex parameters, this can take 10–50 ms. If undo performance is degraded, reduce the history depth or skip history on mouse-move events (only push on mouse-release).

### Connection count

Each node output traverses all connections during reactive propagation. For a node with 500 downstream connections (unusual but possible in fan-out graphs), each `set_output()` call iterates 500 connection objects. This is rarely a bottleneck in practice but can be addressed by batching outputs.

### Memory per node result

`node_results` holds every output of every node. For a 100-node workflow where each node outputs a 10 MB numpy array, `node_results` holds 1 GB in memory. Design pipelines to either:

- Chain data through a single path (pass by reference, not copy), or
- Offload large data to disk and pass file paths between nodes.

### Profiling

To profile execution time per node, add `time.perf_counter()` calls around the `SafeRuntime.run_node_safe()` call (already done in `MainWindow` for the log panel). For deep profiling, use Python's `cProfile`:

```python
import cProfile
cProfile.run('asyncio.run(executor.run())', 'profile_output')
import pstats
p = pstats.Stats('profile_output')
p.sort_stats('cumulative').print_stats(20)
```

---

## 11. Memory and State Management

### BaseNode.memory

`BaseNode.memory` is a class-level `Dict[str, Any]` shared across all node instances in a run. It is cleared at the start of every `run()` call.

Use it for:
- Passing values between nodes that are not directly connected (e.g. `SetVariable` / `GetVariable`).
- Caching expensive lookups (e.g. database connections, credential tokens) across multiple nodes in the same run.
- Storing loop state.

Do **not** use it for:
- Persistent state between separate run clicks (it is cleared each time).
- Large data structures that should be passed via wires (use output ports for that).
- Cross-tab state (each tab has its own executor, which clears `memory`).

### Persistent state between runs

If a node needs to persist state between run clicks (e.g. a connection pool, a cached credential), use Python module-level globals in the node's code, or a file-based cache. Module-level state persists for the lifetime of the Python process.

```python
# In node python_code:
_CACHED_TOKEN = None

async def execute(self, inputs):
    global _CACHED_TOKEN
    if _CACHED_TOKEN is None:
        _CACHED_TOKEN = await _authenticate(inputs.get("api_key"))
    # use _CACHED_TOKEN
```

Be aware that reloading the workflow (which re-registers the node class via `exec()`) resets module-level state in that scope.

### GroupNode memory isolation

`GroupNode` saves and restores `BaseNode.memory` around sub-execution:

```python
saved_memory = dict(_BaseNode.memory)
await sub_executor.run()   # clears memory internally
_BaseNode.memory.clear()
_BaseNode.memory.update(saved_memory)
```

Sub-graph nodes can read and write their own memory keys without affecting the outer graph's variables. Variables set in the outer graph before the `GroupNode` are visible to inner nodes because the sub-executor starts with an empty memory (not a copy of the outer memory).

If you need to pass data from the outer graph into a sub-graph, use the `GroupInNode` / data wire mechanism, not `memory`.

### Clearing state between runs

`NetworkExecutor.run()` clears at the start:
```python
BaseNode.memory.clear()
self._executed_nodes.clear()
self._currently_executing.clear()
self._is_stopped = False
self._active_tasks.clear()
self.node_results = {}
self.node_instances = {}
```

All node instances are re-created from scratch each run. Python objects held by previous instances are garbage-collected.

---

## 12. Security Considerations

### Node code execution

Node `python_code` is executed via `exec()` in `NodeRegistry.register_definition()`:

```python
namespace = {}
exec(definition.python_code, namespace)
```

This runs arbitrary Python code with the full privileges of the Python process. There is **no sandboxing**.

### Implications

- A malicious node JSON file can execute any code on the machine, including file deletion, network access, and registry modification.
- Users who load workflows from untrusted sources are at risk if those workflows reference malicious node types.
- Nodes distributed via `v_nodes_dir` are loaded automatically on startup.

### Mitigations in production

1. **Code review before deployment**: All node JSON files in the studio's plugin package should be reviewed by a trusted engineer before being added to `v_nodes_dir`.
2. **Read-only plugin directories**: Set the `v_nodes_dir` directory to read-only for regular users so they cannot replace node files with malicious versions.
3. **Workflow allowlists**: If running headless on a farm, validate that the workflow only uses node IDs from an approved list before executing.
4. **Network isolation**: Run the Vibrante-Node process under a service account with limited network and file system permissions.
5. **Signed nodes** (future): A potential enhancement is to require cryptographic signatures on node JSON files (e.g. using `nacl` or `cryptography`). Unsigned nodes would be rejected by the registry.

### Houdini bridge security

The Houdini command server listens on `127.0.0.1` only (loopback). It cannot be accessed from other machines on the network. All commands require the caller to already have a local process on the same machine, which means an attacker would need local code execution to reach the server — at which point they already have the same privileges.

### Autosave file

The autosave file at `~/.vibrante_node_autosave.json` contains a complete serialization of all open workflows. It is written with normal user file permissions. On shared workstations, other users with file system access could read workflow data. If workflows contain sensitive information (API keys in parameter widgets, file paths, credentials stored in node parameters), consider encrypting the autosave file or disabling it for sensitive use cases.

---

## 13. Version Migration

Vibrante-Node uses Pydantic v2 for workflow serialization. The `WorkflowModel` schema has been stable since v1.5.0, but field additions and changes require migration logic for older files.

### How Pydantic handles missing fields

Pydantic v2's `model_validate()` uses the field's `default` or `default_factory` for any key absent from the JSON. This means older workflow files load without errors even when new fields have been added, as long as new fields always have defaults.

Current fields with defaults that were added in later versions:

| Model | Field | Added in | Default |
|-------|-------|----------|---------|
| `NodeInstanceModel` | `bypassed` | v1.6.0 | `False` |
| `NodeInstanceModel` | `init_priority` | v1.8.5 | `0` |
| `WorkflowModel` | `sticky_notes` | v1.7.0 | `[]` |
| `WorkflowModel` | `backdrops` | v1.7.0 | `[]` |
| `WorkflowModel` | `metadata` | v1.8.0 | `{}` |
| `ConnectionModel` | `is_exec` | v1.5.0 | `False` |

All of these have safe defaults that make old files load correctly without any migration script.

### Node ID changes

If a node is renamed (its `node_id` changes), existing workflows that use the old `node_id` will fail to load that node (the registry will not find it). To handle this:

#### Option A: Alias registration

Register the node under both the old and new IDs:

```python
# In NodeRegistry.register_builtins() or a plugin's __init__:
NodeRegistry._classes["old_node_id"] = NewNodeClass
NodeRegistry._definitions["old_node_id"] = NodeRegistry._definitions.get("new_node_id")
```

#### Option B: Migration script

Write a one-time script that reads old workflow files and rewrites the `node_id`:

```python
import json, glob, os

OLD_ID = "my_old_node"
NEW_ID = "my_new_node"

for path in glob.glob("workflows/**/*.json", recursive=True):
    with open(path) as f:
        data = json.load(f)
    changed = False
    for node in data.get("nodes", []):
        if node.get("node_id") == OLD_ID:
            node["node_id"] = NEW_ID
            changed = True
    if changed:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Migrated: {path}")
```

#### Option C: Compatibility shim in the registry

Override `register_definition()` to detect old IDs during loading and transparently remap them:

```python
LEGACY_NODE_IDS = {
    "my_old_node": "my_new_node",
    "hou_create_geo_v1": "hou_create_geo",
}

@classmethod
def load_node(cls, file_path):
    # ... existing load logic ...
    with open(file_path) as f:
        data = json.load(f)
    # Remap legacy node_id in the JSON before validation
    if data.get("node_id") in LEGACY_NODE_IDS:
        data["node_id"] = LEGACY_NODE_IDS[data["node_id"]]
    definition = NodeDefinitionJSON.model_validate(data)
    # ...
```

For workflow files that reference legacy `node_id` values, add the remapping in `NodeScene.from_workflow_model()`:

```python
for node_model in model.nodes:
    if node_model.node_id in LEGACY_NODE_IDS:
        node_model.node_id = LEGACY_NODE_IDS[node_model.node_id]
```

### Parameter schema changes

When a node's parameter names change, old workflow files will have the old key in `NodeInstanceModel.parameters`. The node's `restore_from_parameters()` method is the right place to handle this migration:

```python
def restore_from_parameters(self, parameters):
    # Legacy: "file" was renamed to "file_path" in v1.8.0
    if "file" in parameters and "file_path" not in parameters:
        parameters["file_path"] = parameters.pop("file")
    # ... rest of restore logic ...
```

### Workflow version field

`WorkflowModel.metadata` (a `Dict[str, Any]`) can store a version number:

```python
# When saving:
model = scene.to_workflow_model()
model.metadata["vibrante_version"] = "2.1.0"
```

```python
# When loading:
ver = model.metadata.get("vibrante_version", "unknown")
if ver < "2.0.0":
    # apply migration
    pass
```

Version comparison with semantic version strings should use `packaging.version.Version` for correctness:

```python
from packaging.version import Version
if Version(ver) < Version("2.0.0"):
    # migrate
    pass
```

---

## 14. Extending the Node Builder with AI

The `NodeBuilderDialog` includes a `GeminiChatWidget` that connects to the Gemini API for AI-assisted node code generation. This can be extended or replaced with a different AI provider.

### Adding a custom AI provider

1. Create a new chat widget class that inherits from `QWidget` and emits `code_generated(str)` when the AI returns code.
2. Replace the `GeminiChatWidget` instantiation in `NodeBuilderDialog._init_ui()` with your widget.
3. Connect the signal to `self.code_edit.setPlainText(code)`.

### Prompt engineering for node generation

The most effective prompts include:

- The full `CLAUDE.md` / `GEMINI.md` developer guide as system context.
- The specific node category and DCC target.
- Example input/output port names and data types.
- A description of what the node should do.

The AI should output a complete JSON block (with `python_code` included) or just the `python_code` string, which the dialog can auto-fill into the editor.

---

## 15. Hot-Reload during Development

During active node development, it is not necessary to restart the application to pick up code changes in a node's `.json` file.

### Reloading a single node

```python
# From the Scripting Console:
from src.core.registry import NodeRegistry

# Re-read from disk and re-compile
ok = NodeRegistry.reload_node_definition("my_node_id")
if ok:
    print("Reloaded successfully")
else:
    print(f"Error: {NodeRegistry.last_error}")

# Refresh the Library panel to show updated ports
window.library_panel.refresh()
```

After reload, any newly placed `NodeWidget` of this type will use the new code. Existing widgets in the scene will continue to use the old instance until the scene is reloaded or the widget is removed and re-added.

### Reloading all nodes from a directory

```python
# From the Scripting Console:
from src.core.registry import NodeRegistry
NodeRegistry._load_directory("/path/to/my_nodes")
window.library_panel.refresh()
```

This scans the directory and re-registers any changed `.json` files. Existing node IDs are overwritten.

### Live code testing in the Scripting Console

You can prototype node logic directly in the Scripting Console before writing it into a `.json` file:

```python
from src.nodes.base import BaseNode
import asyncio

class TestNode(BaseNode):
    name = "test"
    def __init__(self):
        super().__init__(use_exec=False)
        self.add_input("x", "float", default=1.0)
        self.add_output("y", "float")

    async def execute(self, inputs):
        return {"y": inputs["x"] * 2}

n = TestNode()
result = asyncio.run(n.execute({"x": 5.0}))
print(result)  # {"y": 10.0}
```

This runs synchronously in the console and gives immediate feedback on the node's logic without touching the registry or canvas.
