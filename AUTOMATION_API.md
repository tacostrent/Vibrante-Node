# Vibrante-Node — Automation & Scripting API

**Version:** v2.4.0 | [User Guide](USER_GUIDE.md) | [Node Builder API](NODE_BUILDER_API.md) | [Developer Guide](DEVELOPER.md) | [Technical Reference](DOCUMENTATION.md)

The Scripting Console and Python automation API give programmatic access to every part of the application — graph construction, execution control, parameter updates, node registry management, and environment configuration.

---

## Contents

1. [Scripting Console](#1-scripting-console)
2. [Global Objects Reference](#2-global-objects-reference)
3. [Scene API — NodeScene](#3-scene-api)
4. [Application API — MainWindow](#4-application-api)
5. [Node API — NodeWidget](#5-node-api)
6. [Registry API — NodeRegistry](#6-registry-api)
7. [Git API — GitWrapper](#7-git-api)
8. [Python Runtime and Environment](#8-python-runtime-and-environment)
9. [Headless and Subprocess Execution](#9-headless-and-subprocess-execution)
10. [Automation Script Examples](#10-automation-script-examples)
11. [MCP Runtime API — Direct Orchestration](#11-mcp-runtime-api)

---

## 1. Scripting Console

### Opening the Console

**Window → Show/Hide Scripting Console** — a dockable panel with three sub-panels:

| Sub-panel | Contents |
|-----------|----------|
| **Code Editor** | Python input area with syntax highlighting and autocomplete |
| **Debug Output** | stdout/stderr from executed code; also receives `print()` output |
| **Git Status** | Current repository status (branch, modified files, last commit) |

The console is connected to the **live application state**: running code here directly manipulates the active canvas, triggers execution, and updates the UI in real time.

### Execution

- **Run button** or `Ctrl+Enter` — execute the script.
- `print()` inside scripts is redirected to both the Debug Output panel and the Event Log panel.
- Unhandled exceptions in scripts print a traceback to Debug Output.

### Context

Scripts run with the following globals pre-injected:

```python
app      # MainWindow — high-level application control
scene    # NodeScene  — active canvas manipulation
registry # NodeRegistry — node type database
git      # GitWrapper — source control
```

---

## 2. Global Objects Reference

| Object | Type | Module | Description |
|--------|------|--------|-------------|
| `app` | `MainWindow` | `src.ui.window` | Main application window; tab management, execution, themes |
| `scene` | `NodeScene` | `src.ui.canvas.scene` | Active canvas; node creation, wiring, querying |
| `registry` | `NodeRegistry` | `src.core.registry` | Node type registry; definitions, reload, source paths |
| `git` | `GitWrapper` | `src.utils.git_wrapper` | Git operations on the project repository |
| `print()` | built-in | — | Redirected to Debug Output + Event Log |

---

## 3. Scene API — NodeScene

All scene methods operate on the **currently active tab**. Switch tabs first if you need to target a different workflow.

### Node Creation and Discovery

```python
node = scene.add_node_by_name(node_id, pos=(x, y))
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | `str` | Registry ID of the node type (e.g. `"math_add"`, `"console_print"`) |
| `pos` | `tuple(int, int)` | Canvas position in scene coordinates |
| **Returns** | `NodeWidget` | The newly created node widget |

```python
node = scene.find_node_by_name(display_name)
```

Returns the first `NodeWidget` whose display name matches. Returns `None` if not found.

```python
nodes = scene.nodes
```

List of all `NodeWidget` objects currently on the canvas.

### Wiring

```python
scene.connect_nodes(node_a, port_a, node_b, port_b)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_a` | `NodeWidget` or `str` | Source node (or its display name) |
| `port_a` | `str` | Output port name on node_a |
| `node_b` | `NodeWidget` or `str` | Destination node (or its display name) |
| `port_b` | `str` | Input port name on node_b |

Connecting to an already-occupied input automatically disconnects the previous wire.

### Canvas Control

```python
scene.clear()
```

Removes all nodes, wires, sticky notes, and backdrops from the current canvas. Equivalent to File → New Workflow (but stays in the same tab).

---

## 4. Application API — MainWindow

### Tab Management

```python
app.add_new_workflow(name="Untitled")
```

Opens a new empty workflow tab with the given name. Returns nothing; the new tab becomes active.

```python
app.save_workflow()
```

Triggers a save. If the current workflow has never been saved, opens a Save As dialog. Otherwise writes to the existing path.

### Execution

```python
app.execute_pipeline()
```

Starts the execution engine for the active tab. Equivalent to pressing **F5**. The call is non-blocking — execution runs asynchronously. Monitor the Log Panel or use signals for completion notification.

> **Note**: The engine is asyncio-based on the Qt main thread. Calling `execute_pipeline()` from the Scripting Console while execution is already running will queue a second run after the first completes.

### Theme

```python
app.set_theme("dark")    # Dracula dark theme
app.set_theme("light")   # One-Light theme
```

### Workflow Path

```python
path = app.get_current_workflow_path()   # Returns str or None
```

---

## 5. Node API — NodeWidget

Nodes returned by `scene.add_node_by_name()` or `scene.find_node_by_name()` are `NodeWidget` instances.

### Parameters

```python
node.set_parameter(name, value)
```

Sets a widget value programmatically. Triggers downstream reactive propagation. For dropdown ports, passing a `list` updates the dropdown options.

```python
value = node.get_parameter(name, default=None)
```

Safely reads the current widget or parameter value.

### Node Definition

```python
defn = node.node_definition    # BaseNode subclass instance
```

Access the underlying Python logic object. From `defn` you can:

```python
defn.name          # str — node ID
defn.bypassed      # bool — True if bypassed
defn.log_info(msg) # send a message to the Log Panel
defn.parameters    # dict — full parameter state
```

### Bypass State

```python
node.node_definition.bypassed = True    # bypass
node.node_definition.bypassed = False   # restore
```

### Position

```python
node.setPos(x, y)         # QGraphicsItem.setPos
pos = node.scenePos()     # QPointF scene coordinates
```

### Instance ID

```python
node.instance_id    # UUID — unique per canvas instance
```

---

## 6. Registry API — NodeRegistry

### Querying Definitions

```python
defn = registry.get_definition(node_id)
```

Returns a `NodeDefinitionJSON` (Pydantic model) or `None`. Fields include `node_id`, `name`, `category`, `inputs`, `outputs`, `use_exec`, `python_code`.

```python
all_ids = list(registry._classes.keys())    # all registered node IDs
```

### Source Paths

```python
path = registry.get_source_path(node_id)
```

Returns the absolute on-disk path to the `.json` definition file, or `None` for built-in nodes.

### Hot Reload

```python
success = registry.reload_node_definition(node_id)
```

Re-reads the JSON from disk, recompiles the Python class, and replaces the registry entry. Returns `True` on success. Call `scene.reload_node_type(node_id)` afterward to update live canvas instances:

```python
registry.reload_node_definition("my_custom_node")
scene.reload_node_type("my_custom_node")
```

Or reload all types at once (equivalent to `Ctrl+Shift+R`):

```python
for node_id in list(registry._classes.keys()):
    registry.reload_node_definition(node_id)
```

### Inspect a Node Type

```python
defn = registry.get_definition("math_add")
print(defn.category)      # "Math"
print(defn.use_exec)      # True
for port in defn.inputs:
    print(port.name, port.type, port.widget_type)
```

---

## 7. Git API — GitWrapper

`git` provides source control operations on the project directory.

```python
git.status()                    # Print working tree status
git.commit("message")           # Stage all changes and commit
git.push()                      # Push to remote
git.pull()                      # Pull from remote
git.log(n=10)                   # Print last N commits
```

Example — automated backup after workflow save:

```python
app.save_workflow()
git.commit(f"Automated backup: {app.get_current_workflow_path()}")
git.push()
print("Workflow pushed to repository.")
```

---

## 8. Python Runtime and Environment

### VIBRANTE_PYTHONPATH

Extra `sys.path` entries configured in **Edit → Preferences → Python Runtime**. These are injected at startup, making any Python packages in those directories importable from node code.

```python
# In a node's execute():
import my_studio_lib     # resolvable because its parent dir is in VIBRANTE_PYTHONPATH
```

Access from the Scripting Console:

```python
import sys
print(sys.path)    # verify your paths are present
```

### Custom Environment Variables

Configured in **Edit → Preferences → Environment Variables**. Available as standard `os.environ` entries:

```python
import os
root = os.environ.get("STUDIO_ROOT", "")
```

### v_nodes_dir and v_scripts_path

| Variable | Purpose |
|----------|---------|
| `v_nodes_dir` | Extra directories scanned for `.json` node definitions |
| `v_scripts_path` | Extra directories scanned for Scripts menu `.py` files |

Both support multiple paths (colon-separated on the stored value). Configured in **Edit → Preferences → Application Paths**. Changes apply on OK without restarting.

### Runtime Introspection

```python
import os, sys

# Which node directories are loaded?
print(os.environ.get("v_nodes_dir", "(none)"))

# What Python packages are available?
import importlib
for pkg in ["pydantic", "PyQt5", "aiohttp", "toposort"]:
    try:
        importlib.import_module(pkg)
        print(f"{pkg}: OK")
    except ImportError:
        print(f"{pkg}: not installed")
```

---

## 9. Headless and Subprocess Execution

### Maya — Headless Action Pattern

Maya nodes build an action list; `maya_headless` executes it in a batch Maya session. From a script you can construct and run a Maya pipeline programmatically:

```python
# Build a Maya headless workflow programmatically
scene.clear()

open_node = scene.add_node_by_name("maya_action_open_scene", (0, 0))
open_node.set_parameter("scene_path", "C:/projects/myproject/scenes/shot_010.ma")

render_node = scene.add_node_by_name("maya_action_render", (300, 0))
render_node.set_parameter("camera", "renderCam")
render_node.set_parameter("start_frame", 1001)
render_node.set_parameter("end_frame", 1100)

exec_node = scene.add_node_by_name("maya_headless", (600, 0))

scene.connect_nodes(open_node, "actions_out", render_node, "actions_in")
scene.connect_nodes(render_node, "actions_out", exec_node, "actions_in")
scene.connect_nodes(open_node, "exec_out", render_node, "exec_in")
scene.connect_nodes(render_node, "exec_out", exec_node, "exec_in")

app.execute_pipeline()
```

### Blender — Same Pattern

Replace `maya_action_*` with `blender_action_*` and `maya_headless` with `blender_headless`.

### Houdini — Live Bridge

For Houdini, Vibrante-Node must be launched from within Houdini. From a script you can trigger Houdini operations the same way as from a node:

```python
from src.utils.hou_bridge import get_bridge
bridge = get_bridge()

result = bridge.run_code(
    "nodes = [n.name() for n in hou.node('/obj').children()]; result = nodes"
)
print(result["result"])
```

### Houdini — Runtime Layer (Direct Python Access)

The `src.runtime` module can be called directly from Python scripts without going through the visual canvas. This is useful for pipeline automation tools that embed Vibrante's orchestration logic.

```python
import asyncio
from src.runtime import houdini_runtime, transaction_manager

async def build_pyro_scene():
    # Get structured scene snapshot
    ctx = await houdini_runtime.scene_context()
    print(ctx["scene"]["hip_file"])

    # Execute with automatic rollback on failure
    mgr = transaction_manager.get_transaction_manager()
    txn_id = mgr.begin_transaction("build_pyro")

    op = await houdini_runtime.execute_operation({
        "op": "create_node",
        "parent": "/obj",
        "type": "geo",
        "name": "pyro_geo",
    })

    if op["status"] == "ok":
        mgr.record_operation(txn_id, op)
        mgr.commit_transaction(txn_id)
        print("Created:", op["result"]["path"])
    else:
        mgr.rollback_transaction(txn_id)
        print("Failed:", op["error"])

asyncio.run(build_pyro_scene())
```

---

## 10. Automation Script Examples

The `examples/automation/` directory contains 11 scripts demonstrating real automation patterns. Below are representative examples.

### 01 — Linear Chain

Source: `examples/automation/01_linear_chain.py`

Builds a simple sequential chain of nodes programmatically.

```python
# Build: [Message Node] -> [Console Print]
scene.clear()

msg = scene.add_node_by_name("message_node", (0, 0))
msg.set_parameter("msg", "Hello from automation")

printer = scene.add_node_by_name("console_print", (300, 0))

scene.connect_nodes(msg, "exec_out", printer, "exec_in")
scene.connect_nodes(msg, "out", printer, "data")

app.execute_pipeline()
print("Executed: linear chain")
```

### 02 — Batch Prefix Update

Source: `examples/automation/02_batch_update_prefix.py`

Finds all Message Node instances and updates their values in a batch.

```python
target_prefix = "v2_"

for node in scene.nodes:
    if node.node_definition.name == "message_node":
        current = node.get_parameter("msg") or ""
        if not current.startswith(target_prefix):
            node.set_parameter("msg", target_prefix + current)

print("Batch prefix update complete.")
```

### 03 — Scene Reset

Source: `examples/automation/03_reset_scene.py`

Resets all numeric parameters across the canvas.

```python
reset_nodes = ["math_add", "math_multiply"]

for node in scene.nodes:
    if node.node_definition.name in reset_nodes:
        node.set_parameter("a", 0)
        node.set_parameter("b", 0)

print(f"Reset {len(scene.nodes)} nodes.")
```

### 04 — Batch Execution

Source: `examples/automation/04_batch_execution.py`

Runs the same workflow for a list of input values, capturing each result.

```python
input_node = scene.find_node_by_name("Message Node")
values = ["Asset_A", "Asset_B", "Asset_C"]

for v in values:
    input_node.set_parameter("msg", v)
    app.execute_pipeline()
    # Execution is async — results appear in the Log Panel sequentially
    print(f"Queued execution for: {v}")
```

### 05 — Git Backup

Source: `examples/automation/05_git_backup.py`

Save the current workflow and commit it to version control.

```python
app.save_workflow()
git.status()
git.commit("Automated workflow checkpoint")
git.push()
print("Workflow saved and pushed to remote.")
```

### 07 — Stress Test Grid

Source: `examples/automation/07_stress_test_grid.py`

Generates a grid of nodes to test canvas performance.

```python
scene.clear()
cols, rows = 10, 8
for row in range(rows):
    for col in range(cols):
        n = scene.add_node_by_name("message_node", (col * 280, row * 180))
        n.set_parameter("msg", f"Node [{row},{col}]")

print(f"Created {cols * rows} nodes.")
```

### 08 — Scene Summary

Source: `examples/automation/08_scene_summary.py`

Reports statistics about the current canvas.

```python
from collections import Counter

counts = Counter(n.node_definition.name for n in scene.nodes)

print("=== Canvas Summary ===")
print(f"Total nodes: {len(scene.nodes)}")
for name, count in counts.most_common():
    print(f"  {name}: {count}")
```

### 10 — Session Report

Source: `examples/automation/10_session_report.py`

Generates a human-readable report of the full canvas state.

```python
import json

report = {
    "node_count": len(scene.nodes),
    "nodes": [
        {
            "id":       str(n.instance_id),
            "type":     n.node_definition.name,
            "bypassed": getattr(n.node_definition, "bypassed", False),
        }
        for n in scene.nodes
    ]
}

print(json.dumps(report, indent=2))
```

---

## 11. MCP Runtime API — Direct Orchestration

Vibrante Runtime exposes a full MCP server that external AI clients (Claude Desktop, Codex CLI, Cursor, and any MCP-compatible tool) can connect to **without the visual canvas**. The runtime is fully headless — no Qt dependency, no display required.

### Starting the MCP Server

```bash
# From the repo root
pip install "mcp>=1.0.0" pydantic toposort

python scripts/run_vibrante_mcp.py
```

The server starts on stdio and blocks until the client disconnects. All 12 semantic tools are immediately available. Houdini-dependent tools (`query_scene_context`, `execute_workflow_transaction`) connect to the live bridge automatically when a Houdini session is running.

### AI Client Configuration

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

**Codex CLI** (`~/.config/codex/config.toml`):

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

### Python Client via `mcp_runtime`

From within Vibrante's event loop you can also call external MCP servers as a client:

```python
from src.runtime import mcp_runtime

# Register an MCP server (stdio transport — launches a subprocess)
await mcp_runtime.register_server(
    "my_server", "stdio",
    {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]}
)

# List available tools
tools = await mcp_runtime.list_tools("my_server")
for t in tools:
    print(t["name"], "-", t["description"])

# Call a tool
result = await mcp_runtime.call_tool("my_server", "echo", {"message": "hello"})
print(result["result_json"])
```

### Semantic Execution from Python

The full semantic pipeline is available without the canvas or MCP:

```python
from src.runtime.semantic_execution import get_semantic_executor
from src.runtime.runtime_bootstrap import initialize_runtime

# Initialize all runtime singletons
initialize_runtime()

executor = get_semantic_executor()

# Translate a named intent to an execution plan (no execution)
plan = await executor.translate("build_pyro_source", {
    "parent": "/obj",
    "name": "fire_sim",
    "style": "smoke",
})
print(plan["operations"])

# Execute end-to-end with automatic rollback on failure
result = await executor.execute("build_pyro_source", {
    "parent": "/obj",
    "name": "fire_sim",
}, dry_run=False, auto_commit=True, rollback_on_error=True)

print(result["status"])       # "committed" | "rolled_back" | "failed"
print(result["graph_diff"])   # what changed in the scene
```

### MCP Tool Registry from Python

Register custom tools that the MCP server exposes to AI clients:

```python
from src.runtime.mcp_tool_registry import get_mcp_tool_registry, ToolDefinition

registry = get_mcp_tool_registry()

async def my_handler(arguments):
    return {"ok": True, "result": f"custom: {arguments.get('name', '')}"}

registry.register_tool(ToolDefinition(
    name="my_studio_tool",
    description="Studio-specific operation",
    inputSchema={"type": "object", "properties": {"name": {"type": "string"}}},
    handler=my_handler,
    category="custom",
))
```

> **Forbidden names:** `create_node`, `set_parm`, `set_parms`, `run_python`, `run_code`, `delete_node`, `raw_houdini_execute`, `connect_nodes`, `cook_node` — registering any of these will raise `ValueError`. These are never exposed as MCP tools.

### Execution Safety Invariants

All mutations routed through the runtime respect these invariants regardless of how they are triggered (canvas node, Python API, or MCP tool):

1. `ValidationEngine` and `RuntimeConstraints` run before every transaction.
2. Plans with `ok=False` are rejected before any bridge call.
3. Plans with `requires_approval=True` block until an `approver` is supplied.
4. Rollback handlers never raise — failures are captured and reported.
5. `scene_cache.invalidate("scene_context::")` is called after every mutation.

---

**See also:**

- [User Guide](USER_GUIDE.md) — Scripting Console location and basic usage
- [Node Builder API](NODE_BUILDER_API.md) — building nodes that expose scriptable parameters
- [Developer Guide](DEVELOPER.md) — engine internals, Runtime Layer architecture (Tiers 1–6)
- [Technical Reference](DOCUMENTATION.md) — Runtime Layer API reference, MCP Semantic Tools reference
- `examples/automation/` — full collection of automation scripts
- `examples/nodes/` — custom node Python source examples
- `scripts/run_vibrante_mcp.py` — MCP server entry point
