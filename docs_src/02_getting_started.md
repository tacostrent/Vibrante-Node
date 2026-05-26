# Vibrante-Node v2.4.0 — Getting Started

This guide takes you from a fresh machine to running your first workflow. It covers installation, the project layout, a complete first-workflow tutorial, and a detailed explanation of what happens when you press F5.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation on Windows](#installation-on-windows)
3. [macOS and Linux Notes](#macos-and-linux-notes)
4. [Running from Source vs. Running the .exe](#running-from-source-vs-running-the-exe)
5. [Project Structure Walkthrough](#project-structure-walkthrough)
6. [First Launch — What You See](#first-launch--what-you-see)
7. [Your First Workflow — Step by Step](#your-first-workflow--step-by-step)
8. [Understanding Execution Flow](#understanding-execution-flow)
9. [The Node Library Panel](#the-node-library-panel)
10. [Saving and Loading Workflows](#saving-and-loading-workflows)

---

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| **Operating System** | Windows 10 64-bit | Windows 11 64-bit |
| **Python** | 3.10 | 3.11 |
| **PyQt5** | 5.15 | 5.15.x latest |
| **QScintilla** | 2.13 | 2.14 |
| **pydantic** | 2.0 | 2.x latest |
| **toposort** | 1.10 | 1.10 |
| **RAM** | 4 GB | 8 GB |
| **Disk** | 200 MB | 1 GB (for workflows and assets) |

**Optional dependencies by integration:**

| Integration | Additional Requirement |
|---|---|
| Houdini Bridge | Houdini 19.5 or 20.x with the `plugins/houdini/` package installed |
| Maya Headless | Autodesk Maya 2022+ with `mayapy` on PATH |
| Blender Headless | Blender 3.x or 4.x with `blender` on PATH |
| Prism Pipeline | Prism 2.x installed, `PrismCore` importable from Python |
| Deadline | Thinkbox Deadline 10.x client installed |
| Gemini AI | `google-generativeai` Python package, valid API key |
| MCP Runtime (Claude/Codex/Cursor) | `mcp>=1.0.0` Python package (`pip install "mcp>=1.0.0"`) |

---

## Installation on Windows

### Step 1 — Install Python

Download Python 3.11 from [python.org](https://www.python.org/downloads/). During installation:

- Check **Add Python to PATH**.
- Check **Install pip**.

Verify the installation:

```
python --version
pip --version
```

### Step 2 — Clone the Repository

```
git clone https://github.com/your-org/vibrante-node.git
cd vibrante-node
```

If you received a ZIP archive instead of a git URL, extract it to a folder of your choice (e.g. `C:\vibrante-node`).

### Step 3 — Install Python Dependencies

From inside the project root (the folder containing `requirements.txt`):

```
pip install -r requirements.txt
```

This installs: `PyQt5`, `QScintilla`, `pydantic`, `toposort`, `pytest`, `pytest-qt`, `google-generativeai`, and `pytest-asyncio`.

If `QScintilla` fails on your system, the app will still run — it falls back to a plain `QPlainTextEdit`-based code editor automatically. To install QScintilla manually:

```
pip install QScintilla
```

### Step 4 — Run the Application

```
python src/main.py
```

The splash screen appears briefly, then the main window opens.

### Step 5 — (Optional) Install the Houdini Plugin

If you use Houdini and want to control it from Vibrante-Node:

1. Locate your Houdini packages folder. On Windows this is typically:
   ```
   C:\Users\<username>\Documents\houdini20.5\packages\
   ```
2. Copy `plugins/houdini/vibrante_node.json` into that folder.
3. Open the file in a text editor and set the two required paths:
   ```json
   {
       "env": [
           { "VIBRANTE_NODE_APP": "C:/vibrante-node" },
           { "VIBRANTE_PYTHON_EXE": "C:/Python311/python.exe" }
       ],
       "path": "$VIBRANTE_NODE_APP/plugins/houdini/houdini"
   }
   ```
   - `VIBRANTE_NODE_APP` must be the absolute path to the project root (where `src/main.py` lives).
   - `VIBRANTE_PYTHON_EXE` must point to a Python 3.11 executable that has PyQt5 installed.
4. Restart Houdini. The **Vibrante-Node** menu appears in the Houdini menu bar.
5. Use **Vibrante-Node > Launch Vibrante-Node** to start the app from inside Houdini.

---

## macOS and Linux Notes

Vibrante-Node is developed and tested on Windows. macOS and Linux are supported on a best-effort basis.

### PyQt5 on macOS

Install PyQt5 via pip. If you encounter issues with Qt platform plugins:

```bash
pip install PyQt5
export QT_QPA_PLATFORM=xcb   # Linux only
```

On macOS, Homebrew Python 3.11 is recommended over the system Python.

### PyQt5 on Linux

Ubuntu / Debian:

```bash
sudo apt-get install python3-pyqt5 python3-pyqt5.qsci
pip install pydantic toposort
```

Or install everything via pip (requires Qt development libraries):

```bash
sudo apt-get install libgles2-mesa-dev libxcb-xinerama0
pip install -r requirements.txt
```

### Known Limitations on Non-Windows

- The Windows `.exe` build (`dist/vibrante_node.exe`) does not run on macOS or Linux.
- Houdini plugin features (`vibrante_node.json`, `pythonrc.py`) are tested only on Windows and Linux.
- The Blender and Maya headless executors depend on DCC executables being accessible on PATH, which varies by OS.

---

## Running from Source vs. Running the .exe

### From Source

```
python src/main.py
```

Use this during development or when you need to modify nodes, add Python nodes, or debug. Changes to `.json` node files are picked up on the next launch (or after Ctrl+Shift+R to reload all nodes). Changes to Python node files or source code require restarting the application.

### From the .exe

The `dist/vibrante_node.exe` is a PyInstaller-bundled single-file executable for Windows. It includes Python 3.10, PyQt5, QScintilla, pydantic, toposort, and all bundled nodes. It does not require a separate Python installation.

**Limitations of the .exe:**

- You cannot modify source files inside the bundle.
- Custom nodes must be placed next to the `.exe` in a `nodes/` folder — the registry scans this location at startup.
- For the Houdini plugin, `VIBRANTE_PYTHON_EXE` must still point to a system Python 3.11 with PyQt5 because the plugin launches Vibrante-Node as a subprocess, not the bundled `.exe`.

---

## Project Structure Walkthrough

```
vibrante-node/
├── src/                        Main application source code
│   ├── main.py                 Entry point; creates QApplication and MainWindow
│   ├── core/
│   │   ├── engine.py           NetworkExecutor — async graph runner
│   │   ├── graph.py            GraphManager — DAG with toposort
│   │   ├── models.py           Pydantic data models (WorkflowModel, etc.)
│   │   ├── registry.py         NodeRegistry — loads JSON + Python nodes
│   │   ├── persistence.py      Workflow JSON serialisation / deserialisation
│   │   └── loader.py           Node JSON file loader utilities
│   ├── nodes/
│   │   ├── base.py             BaseNode abstract class
│   │   └── builtins/           Built-in Python nodes (Sequence, ForEach, etc.)
│   ├── ui/
│   │   ├── window.py           MainWindow — top-level Qt window
│   │   ├── library_panel.py    Node library sidebar
│   │   ├── log_panel.py        Execution log display
│   │   ├── node_widget.py      NodeWidget (QGraphicsItem)
│   │   ├── port_widget.py      Port widgets on node cards
│   │   ├── code_editor.py      Python code editor (QScintilla or fallback)
│   │   ├── node_builder.py     Node Builder dialog
│   │   ├── script_editor.py    Standalone script editor dialog
│   │   ├── scripting_console.py Interactive Python REPL
│   │   └── canvas/
│   │       ├── scene.py        NodeScene (QGraphicsScene)
│   │       ├── view.py         NodeView (QGraphicsView)
│   │       ├── edge.py         Edge (wire) items
│   │       ├── mini_map.py     MiniMap overlay widget
│   │       ├── canvas_search_bar.py  Ctrl+F search bar
│   │       ├── node_search_popup.py  Tab node search
│   │       ├── backdrop.py     Backdrop / network box items
│   │       └── sticky_note.py  Sticky note annotation items
│   └── utils/
│       ├── hou_bridge.py       HouBridge TCP client (Houdini integration)
│       ├── prism_core.py       PrismCore resolver and bootstrap
│       ├── config_manager.py   App settings and recent files
│       ├── qt_compat.py        PyQt5 / Qt6 compatibility shims
│       └── runtime.py          SafeRuntime for wrapping async node execution
│
├── nodes/                      JSON node definitions (loaded at startup)
│   ├── console_print.json
│   ├── python_script.json
│   ├── if_condition.json
│   ├── prism_core_init.json
│   ├── maya_headless.json
│   └── ...                     (90+ node files)
│
├── plugins/
│   └── houdini/
│       ├── vibrante_node.json  Houdini package file (user installs this)
│       ├── v_nodes_houdini/    Houdini-specific node JSON files
│       ├── v_scripts_houdini/  Houdini-specific Python scripts (Scripts menu)
│       └── houdini/
│           ├── MainMenuCommon.xml
│           ├── toolbar/vibrante_node.shelf
│           └── scripts/python/
│               ├── pythonrc.py
│               ├── vibrante_node_houdini.py
│               └── vibrante_hou_server.py
│
├── workflows/                  Saved workflow JSON files (user-created)
├── docs_src/                   Documentation source (this folder)
├── examples/                   Example workflow JSON files
├── icons/                      SVG and PNG icons used by node definitions
├── requirements.txt            Python package dependencies
├── CLAUDE.md                   Node authoring guide for AI assistants
└── DEVELOPER.md                Developer reference documentation
```

---

## First Launch — What You See

When Vibrante-Node starts for the first time, the main window is divided into four areas.

```
+------------------------------------------------------------------+
|  Menu Bar: File  Edit  Window  Help                              |
|  Toolbar:  [New] [Open] [Save] [Run] [Stop] [Add Node] [Edit]   |
+------------------------------------------------------------------+
|           |                                     |                |
|  Library  |           Canvas (NodeView)         |                |
|  Panel    |                                     |                |
|           |   (empty — grey or dark grid)       |                |
|  Search:  |                                     |                |
|  [______] |                                     |   [mini-map]   |
|           |                                     |   200x150 px   |
|  General  |                                     |   bottom-right |
|  > print  |                                     |                |
|  > script |                                     |                |
|  > concat |                                     |                |
|  Houdini  |                                     |                |
|  > create |                                     |                |
|  ...      |                                     |                |
|           |                                     |                |
+-----------+-------------------------------------+----------------+
|  Log Panel                                                       |
|  [info]  Welcome to Vibrante-Node v2.4.0                        |
+------------------------------------------------------------------+
```

### The Canvas

The large central area is the **canvas** — a `NodeView` (QGraphicsView) containing a `NodeScene` (QGraphicsScene). This is where you place and connect nodes. It starts empty. A grid pattern is drawn in the background.

The **mini-map** thumbnail appears in the bottom-right corner of the canvas. It shows a scaled-down view of the entire scene and a blue rectangle indicating the current viewport. Toggle it with Ctrl+M.

### The Library Panel

The left sidebar lists every registered node, organised by category. Expand a category by clicking its header. Click a node to select it; double-click to add it to the centre of the canvas. You can also search nodes by typing in the search box at the top of the panel.

Categories you will see on first launch:

- **General** — console print, python script, math, string, list, dictionary, file, logic, control flow
- **Houdini** — create geo, set parm, cook node, save hip, scene info (if running standalone without the Houdini plugin, these appear greyed out)
- **Maya** — headless Maya batch actions
- **Blender** — headless Blender batch actions
- **Prism** — Prism Pipeline project/asset/shot management
- **Deadline** — render farm submission

### The Log Panel

The bottom strip is the **log panel**. Every node that calls `self.log_info()`, `self.log_success()`, or `self.log_error()` in its Python code writes a timestamped line here. The engine also writes timing lines: `Node 'X' finished in 0.34s`. Messages are colour-coded: grey for info, green for success, red for error.

### The Toolbar

| Button | Action | Shortcut |
|---|---|---|
| New | Create a new empty workflow tab | Ctrl+N |
| Open | Open a saved workflow JSON file | Ctrl+O |
| Save | Save the current workflow | Ctrl+S |
| Run | Execute the workflow | F5 |
| Stop | Cancel a running execution | (toolbar only) |
| Add Node | Open the node search popup | Tab |
| Edit Node | Open selected node in Node Builder | Ctrl+E |

---

## Your First Workflow — Step by Step

In this tutorial you will build a minimal workflow: a text value flows into a print node, which prints it to the log panel when you press F5.

### Step 1 — Open the Application

Run `python src/main.py` (or double-click the `.exe`). The main window opens with an empty canvas.

### Step 2 — Add a Console Print Node

Press **Tab** to open the node search popup. A floating search box appears at the cursor position.

Type `print`. The list narrows to show `console_print`. Press **Enter** or click `console_print`.

A node labelled **console_print** appears on the canvas near where you pressed Tab. It has:
- A white square input pin on the left labelled `exec_in`
- A text input widget labelled `message`
- A white square output pin on the right labelled `exec_out`

### Step 3 — Add an Exec Start Trigger

You need something to fire `exec_in` on the print node. Any node whose `exec_out` is connected to another node's `exec_in` will trigger it.

Press **Tab** again and search for `sequence`. Add a **sequence** node. This node has one `exec_in` and two `exec_out` pins (`out_1` and `out_2`), and it fires them in order. It is a good starting trigger.

Alternatively, the `console_print` node has no dependency on an upstream exec trigger — the engine will run any node whose `exec_in` is not connected, treating it as an entry point. So if you skip this step, `console_print` will still run when you press F5.

### Step 4 — Add a Variable Node and Wire It

Press **Tab** and search for `variable`. Add a **variable_node**. This node has:
- A text widget labelled `value` (your input)
- A data output pin labelled `out`
- No exec pins — it is a pure data node

Click on the `value` text field in the variable node and type `Hello, Vibrante-Node!`.

Now wire the variable node to the print node:
1. **Hover** over the variable node's `out` port (right side, coloured circle).
2. **Click and drag** from `out` toward the `console_print` node.
3. **Release** on the `message` input port (left side) of the `console_print` node.

A curved line (wire) now connects the two nodes. The wire colour matches the port data type.

### Step 5 — Connect Exec Pins (Optional)

If you added a sequence node, drag from its `out_1` exec output to the `exec_in` of `console_print`. This creates an exec wire (white, square connectors).

If you did not add a sequence node, skip this step. The engine will treat `console_print` as an entry point because its `exec_in` has no incoming connection.

### Step 6 — Press F5 to Run

Press **F5** (or click the **Run** button in the toolbar). The engine executes the workflow.

Watch the canvas: the running node briefly highlights in a different colour. When it finishes, the highlight clears.

In the **log panel** at the bottom, you should see:

```
[info]  Hello, Vibrante-Node!
[info]  Node 'console_print' finished in 0.00s
```

The text you typed in the variable node has flowed through the wire and been printed.

### Step 7 — Inspect the Wire

After execution, hover your mouse over the wire connecting the variable node's `out` port to the `console_print` node's `message` port.

A tooltip appears showing:

```
message: 'Hello, Vibrante-Node!'
```

This is the **live wire value inspector**. It shows the last value that flowed through every connected wire, without needing to re-run.

### Step 8 — Save the Workflow

Press **Ctrl+S**. A file dialog opens. Choose a location, enter a filename (e.g. `my_first_workflow`), and click Save. The file is saved as a `.json` file.

The title bar updates to show the filename. The workflow is now in **File > Open Recent** for quick access.

### Step 9 — Reload and Re-run

Close the workflow tab (click the X on the tab). Open it again with **Ctrl+O** or via **File > Open Recent > my_first_workflow.json**. Press F5. The same output appears in the log panel.

---

## Understanding Execution Flow

When you press F5, the following sequence occurs:

### 1. Serialise the Scene

`MainWindow` calls `scene.to_workflow_model()`, which traverses all `NodeWidget` and `Edge` items in the `NodeScene` and builds a `WorkflowModel` — a Pydantic model containing lists of `NodeInstanceModel`, `ConnectionModel`, `StickyNoteModel`, and `BackdropModel` objects.

### 2. Build the Graph

A `GraphManager` is constructed from the `WorkflowModel`. It stores nodes in a dict keyed by UUID and connections in a list. The `GraphManager` uses the `toposort` library to detect cycles — if you accidentally created a cycle, an error is reported and execution stops.

### 3. Create Node Instances

For each `NodeInstanceModel`, `NetworkExecutor` looks up the corresponding class in `NodeRegistry`. For JSON nodes, this is a dynamically generated `BaseNode` subclass created when the JSON was loaded. For builtin nodes (like `SequenceNode`, `ForEachNode`), it is the hand-written Python class. An instance is created, its parameters are restored from the saved workflow, and engine hooks are set up.

### 4. Identify Entry Nodes

The engine scans all node instances. **Entry nodes** are those whose `exec_in` pin has no incoming exec connection. If a node has no exec pins at all (a pure data node), it is evaluated lazily — only when another node needs its output.

### 5. Execute Entry Nodes

Each entry node's `execute()` coroutine is scheduled as an `asyncio.Task`. Multiple entry nodes run concurrently if they are independent.

Inside `execute()`, the engine:
1. **Pulls upstream data nodes** — for every input port that has an incoming data connection, the upstream node is executed first (if it has not already run).
2. **Syncs parameters** — the upstream node's output values are written into the current node's input parameters.
3. **Calls `execute(inputs)`** — the node's Python code runs. `inputs` is a dict of all parameter values.
4. **Processes the return dict** — each key-value pair in the returned dict is stored in `node_results` and emitted via `node_output`.

### 6. Follow Exec Pins

When a node calls `await self.set_output("exec_out", True)`, or returns `{"exec_out": True}` from `execute()`, the engine finds all exec connections from that pin and schedules the downstream node for execution. This is the exec chain: the `exec_out` of one node fires the `exec_in` of the next.

Nodes with multiple exec outputs (like `if_condition` with `true_out` / `false_out`, or `GroupNode` with `exec_out` / `exec_fail`) route selectively — only the pin that is set to `True` fires its downstream chain.

### 7. Complete and Signal

When all scheduled tasks complete (or the Stop button cancels them), the executor emits `execution_finished(success)`. The UI re-enables the Run button, and the log panel shows any final messages.

### Execution Flow Diagram

```
F5 pressed
    |
    v
WorkflowModel built from scene
    |
    v
GraphManager + NetworkExecutor created
    |
    v
Node instances created + parameters restored
    |
    v
Entry nodes identified (exec_in unconnected)
    |
    +---- Entry Node A ----+---- Entry Node B ----+
    |                      |                      |
    v (async)              v (async)              v (async)
execute() called    execute() called        execute() called
    |
    | pulls upstream data nodes recursively
    |
    v
inputs dict built
    |
    v
node python code runs
    |
    v
returns {"some_output": value, "exec_out": True}
    |                   |
    v                   v
node_results updated    exec chain fires
live wire updated       downstream node executes
log panel updated
    |
    v
All tasks complete
    |
    v
execution_finished emitted
UI re-enabled
```

---

## The Node Library Panel

The Library panel is the left sidebar that lists all registered nodes.

### Categories

Nodes are grouped by their `category` field in the JSON definition. Standard categories are:

| Category | Contents |
|---|---|
| General | Math, string, list, dict, file, logic, control flow, print, script |
| Houdini | Create node, set parm, cook, save hip, scene snapshot |
| Maya | Headless Maya batch actions |
| Blender | Headless Blender batch actions |
| Prism | 60+ Prism Pipeline nodes |
| Deadline | Render farm submission |

### Searching Nodes

Type in the search box at the top of the Library panel to filter all categories simultaneously. The filter matches against both the display name and the `node_id`. Results update as you type.

### Adding Nodes from the Library

- **Double-click** a node in the Library to add it to the centre of the current canvas view.
- **Drag** a node from the Library onto the canvas to place it at a specific position.

### The Node Search Popup (Tab)

Press **Tab** anywhere on the canvas to open a floating search popup at the cursor position. Type to search, click or press Enter to add the node at the cursor position. This is faster than the Library panel for experienced users.

---

## Saving and Loading Workflows

### Workflow File Format

Workflows are saved as human-readable JSON files. A minimal workflow looks like this:

```json
{
    "nodes": [
        {
            "instance_id": "550e8400-e29b-41d4-a716-446655440000",
            "node_id": "variable_node",
            "position": [100.0, 200.0],
            "parameters": { "value": "Hello, Vibrante-Node!" },
            "state": "idle",
            "bypassed": false,
            "init_priority": 0
        },
        {
            "instance_id": "550e8400-e29b-41d4-a716-446655440001",
            "node_id": "console_print",
            "position": [400.0, 200.0],
            "parameters": { "message": "" },
            "state": "idle",
            "bypassed": false,
            "init_priority": 0
        }
    ],
    "connections": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440002",
            "from_node": "550e8400-e29b-41d4-a716-446655440000",
            "from_port": "out",
            "to_node": "550e8400-e29b-41d4-a716-446655440001",
            "to_port": "message",
            "is_exec": false
        }
    ],
    "sticky_notes": [],
    "backdrops": [],
    "metadata": {}
}
```

Each node is identified by its `instance_id` (UUID) and its `node_id` (the type identifier matching a `.json` definition file). Connections reference source and target nodes by UUID.

### Saving

- **Ctrl+S** — save to the current file path. If the workflow has never been saved, prompts for a filename.
- **Ctrl+Shift+S** (File > Save As) — always prompts for a new filename.

### Loading

- **Ctrl+O** — open a file picker and load a workflow into a new tab.
- **File > Open Recent** — load one of the last 10 workflows directly without a file picker.

### Tabs

Vibrante-Node supports multiple workflows open simultaneously, each in its own tab. Click the **+** button at the right of the tab bar to add a new empty tab. Click a tab to switch. Click the X on a tab to close it (with a save prompt if unsaved changes exist).

### Autosave and Crash Recovery

Every 2 minutes, Vibrante-Node silently writes all non-empty open tabs to:

```
~/.vibrante_node_autosave.json
```

If the application exits cleanly, this file is deleted. If the application crashes or is force-closed, the file remains. On the next launch, a dialog offers to restore the last session. Accepting restores all tabs; declining discards the autosave and opens fresh.

The autosave file is never used as a substitute for an explicit Save — it only appears after an unexpected exit.

---

## 11. Direct Runtime Orchestration — MCP Quick Start *(Advanced)*

Vibrante-Node includes a headless MCP server that lets Claude Desktop, Codex CLI, Cursor, and any MCP-compatible AI client orchestrate Houdini scenes without the visual canvas.

### Prerequisites

```bash
pip install "mcp>=1.0.0" pydantic toposort
```

### Optional: Start the Houdini bridge

1. Open Houdini with the Vibrante plugin installed.
2. Click **Vibrante-Node → Launch Vibrante-Node** in the Houdini menu bar. This starts the TCP bridge on port 18811.
3. The bridge must be running for scene-interaction tools. Planning and knowledge tools work without it.

### Start the MCP server

```bash
# From the repo root
python scripts/run_vibrante_mcp.py
```

The server starts on stdio and stays running until the client disconnects.

### Configure your AI client

**Claude Desktop** (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "vibrante": {
      "command": "python",
      "args": ["/path/to/vibrante-node/scripts/run_vibrante_mcp.py"],
      "env": { "VIBRANTE_HOU_PORT": "18811" }
    }
  }
}
```

**Codex CLI** (`~/.config/codex/config.toml`):
```toml
[mcp_servers.vibrante]
command     = "python"
args        = ["/path/to/vibrante-node/scripts/run_vibrante_mcp.py"]
trust_level = "trusted"
```

### First session with Claude

Once connected, follow this sequence:

1. **Initialize:** ask Claude to call `initialize_runtime_context` — receives the system prompt and bootstrap data.
2. **Inspect:** ask Claude to call `query_scene_context` — returns structured scene state.
3. **Plan:** ask Claude "build a pyro smoke simulation in /obj" → calls `plan_scene` → returns a plan.
4. **Preview:** Claude calls `preview_execution(plan.operations)` → returns risk level and warnings.
5. **Execute:** Claude calls `execute_workflow_transaction(plan_json=...)` → commits or rolls back atomically.
6. **Review:** Claude calls `review_execution(...)` → reports outcome and match score.

---

*Vibrante-Node v2.4.0 — Released 2026-05-26*
