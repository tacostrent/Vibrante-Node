# Vibrante-Node — User Guide

**Version:** v2.4.0 | [Node Builder API](NODE_BUILDER_API.md) | [Automation API](AUTOMATION_API.md) | [Developer Guide](DEVELOPER.md) | [Technical Reference](DOCUMENTATION.md)

---

## Contents

1. [Interface Overview](#1-interface-overview)
2. [Canvas Navigation](#2-canvas-navigation)
3. [Building Workflows](#3-building-workflows)
4. [Execution Model](#4-execution-model)
5. [Control Flow — Loops and Conditions](#5-control-flow)
6. [Group Nodes — Subgraphs](#6-group-nodes)
7. [Python Script Node](#7-python-script-node)
8. [Workflow File Management](#8-workflow-file-management)
9. [Node Library and Canvas Search](#9-node-library-and-canvas-search)
10. [Prism Pipeline Integration](#10-prism-pipeline-integration)
11. [Houdini Integration](#11-houdini-integration)
12. [AI Orchestration — MCP Runtime](#12-ai-orchestration)
13. [Settings and Environment](#13-settings-and-environment)
14. [Keyboard Shortcuts Reference](#14-keyboard-shortcuts-reference)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Interface Overview

The main window is divided into four primary regions.

```
┌─────────────────────────────────────────────────────────────────┐
│  Toolbar: File · Nodes · Edit · Themes · Window · Help          │
│  [New][Open][Save] [Add Node][Run(F5)][Stop] [Tab1][Tab2][+]    │
├──────────────┬──────────────────────────────────────────────────┤
│              │                                                  │
│  Library     │                                                  │
│  ─────────   │                  Canvas                          │
│  ▸ General   │          (node graph workspace)                  │
│  ▸ Houdini   │                                                  │
│  ▸ Maya      │                                                  │
│  ▸ Blender   │                                                  │
│  ▸ Prism     │                                                  │
│  ▸ Data      │                                                  │
│              │                                                  │
│  [search...] │                                         [minimap]│
├──────────────┴──────────────────────────────────────────────────┤
│  Log Panel:  ▸ [info] Node 'Export' finished in 1.23s           │
│              ▸ [error] No display SOP found inside: /obj/geo1   │
└─────────────────────────────────────────────────────────────────┘
```

### Library Panel (left)

Lists all available node types organized by category. Every entry shows the node name; hover to read its description.

- **Double-click** or **drag onto canvas** to add a node
- Use the **search field** at the top to filter by name or node ID
- Categories can be expanded and collapsed
- Right-click an entry to see install location or reload

### Canvas (center)

The primary workspace. Nodes appear as boxes; wires connect their ports.

- **Input ports** on the left side of each node (circles / squares)
- **Output ports** on the right side
- **Exec ports** — white squares — control execution order
- **Data ports** — colored circles — carry typed values

**Port color legend:**

| Color | Type |
|-------|------|
| Cyan | `int` |
| Purple | `string` |
| Orange | `float` |
| Green | `bool` |
| White / grey | `any` (exec flow, generic) |
| Blue | `list` |

### Log Panel (bottom)

Receives real-time messages during execution.

| Level | Color | Source |
|-------|-------|--------|
| Info | White | `self.log_info("msg")` |
| Success | Green | `self.log_success("msg")` |
| Warning | Yellow | type-mismatch detection, connection events |
| Error | Red | `self.log_error("msg")` — node gets a red border |

Each executed node also logs its elapsed time: `Node 'Get Asset' finished in 0.34s`.

Right-click the log panel to copy entries or clear the history.

### Toolbar

| Button | Shortcut | Action |
|--------|----------|--------|
| New | `Ctrl+N` | New workflow tab |
| Open | `Ctrl+O` | Load workflow from disk |
| Save | `Ctrl+S` | Save current workflow |
| Add Node | `Tab` | Open node search popup |
| Run | `F5` | Execute current workflow |
| Stop | `Shift+F5` | Cancel running execution |

---

## 2. Canvas Navigation

| Action | Input |
|--------|-------|
| Pan | Middle-mouse drag |
| Zoom | Mouse wheel |
| Focus selected nodes | `F` |
| Focus entire graph | `F` with nothing selected |
| Canvas search | `Ctrl+F` |
| Toggle mini-map | `Ctrl+M` |

### Mini-map

A 200×150 px thumbnail in the bottom-right corner shows the full canvas at a glance. The blue rectangle indicates the current viewport. Click or drag the mini-map to pan the main view. Toggle with **Ctrl+M** or **Window → Toggle Mini-map**.

### Adding Nodes — Three Methods

**1. Library drag** — drag a node type from the Library panel onto the canvas.

**2. Tab / search popup** — press `Tab` anywhere on the canvas to open the Add Node popup at the cursor position. Type to filter, press Enter or double-click to place.

**3. Right-click context menu** — right-click empty canvas space → "Add Node".

### Connecting Ports

1. Click and drag from any **output port** (right side of a node).
2. Drag to any compatible **input port** (left side of another node).
3. Release to create the connection.

Additional rules:

- Each input port accepts at most **one** incoming wire; connecting a second automatically replaces the first.
- You can drag from an existing wire near the input end to re-route it.
- Connecting ports of different types (e.g. `string` → `int`) logs a **warning** to the Log Panel but the connection is still allowed. `any`-typed ports are always compatible.

### Selection and Organization

| Action | How |
|--------|-----|
| Select node | Click |
| Multi-select | Ctrl+click or rubber-band drag |
| Select all | `Ctrl+A` |
| Delete selected | `Delete` |
| Copy / Paste | `Ctrl+C` / `Ctrl+V` |
| Wrap in Backdrop | `Ctrl+G` |
| Collapse to Group Node | `Ctrl+Shift+G` |
| Undo / Redo | `Ctrl+Z` / `Ctrl+Y` |

### Live Wire Value Inspector

After execution completes, hover any connected wire to see a tooltip showing the last value that passed through it:

```
port_name: repr(value)       (capped at 300 characters)
```

Values persist until the next run begins. This lets you inspect the final state of the entire graph without re-executing.

---

## 3. Building Workflows

A workflow is a directed graph where:

- **Execution** flows through exec pins (white squares, left to right).
- **Data** flows through typed data pins (colored circles).
- Data pins update **reactively** as you change values — even before pressing F5.

### Typical Single-Chain Pattern

```
[File Reader] ──exec──► [Text Transform] ──exec──► [File Writer]
      │                        │
      │ file_content            │ result
      └──────────────────────► [Console Print]
```

### Configuring Node Parameters

Each node widget displays its input ports as interactive controls. The control type depends on the port's widget type:

| Widget type | Control |
|-------------|---------|
| `text` | Single-line text input |
| `text_area` | Multi-line text input |
| `int` | Integer spinbox |
| `float` | Float spinbox |
| `bool` / `checkbox` | Checkbox |
| `dropdown` | Drop-down list |
| `file` | File path + browse button (open) |
| `file_save` | File path + browse button (save) |

> **Connected ports**: When a port is connected to an upstream node, its widget is **disabled** (grayed out). The widget acts as a live monitor — it updates in real time to show the incoming value.

### Reactive Data Propagation

Changing any node parameter immediately propagates through all connected downstream nodes. For example:

- Type in a `concat` node's input → the `result` output updates instantly.
- Downstream nodes that display or depend on that value reflect the change.

This lets you preview what the workflow will produce before running it.

---

## 4. Execution Model

Vibrante-Node uses a **Hybrid Flow + Data** execution model built on `asyncio`.

### Exec Pins — Flow Mode

When `exec_in` and `exec_out` ports are wired, the engine follows them sequentially:

```
[Node A]──exec_out──►[Node B]──exec_out──►[Node C]
```

Execution order: A → B → C. The engine waits for each `execute()` coroutine to complete (or to `await` a result) before triggering the next node.

### Data-Only Mode — Topological

Nodes without exec pins execute in topological dependency order. The engine determines which nodes must run before others by walking the data-wire graph. Data-only nodes also participate in reactive propagation during parameter changes.

### Data Pull Before Execution

Before an exec-flow node runs, the engine **recursively pulls** fresh values from all upstream data-only nodes. This ensures exec nodes always receive current data even when those upstream providers lack exec pins.

### Async Execution and UI Responsiveness

Every node's `execute()` is an `async def` coroutine. The execution engine and the Qt UI share the same thread via a zero-delay `QTimer` that drives the asyncio event loop. This means:

- The UI remains responsive while nodes execute.
- Long-running nodes should `await` I/O rather than blocking (`await asyncio.sleep(...)`, `await aiohttp.get(...)`, etc.).
- The **Stop** button (`Shift+F5`) cancels execution immediately — any node that checks `self.is_stopped()` will terminate cleanly.

### Node Execution States

| State | Visual | Meaning |
|-------|--------|---------|
| Idle | Normal border | Not yet executed in this run |
| Running | Highlighted border | `execute()` is active |
| Success | Brief green flash | Completed without exception |
| Error | Persistent red border | Exception raised inside `execute()` |
| Bypassed | Faded/dimmed | User-bypassed; passthrough behavior |

### Bypass

Right-click any node → **Bypass** to exclude it from execution. A bypassed node:
- Passes its primary input directly to its primary output.
- Fires `exec_out` normally, so the downstream chain is not interrupted.
- Is visually faded on the canvas.

Right-click → **Remove Bypass** to restore normal behavior.

### Init-First Nodes

Some nodes need to be fully initialized before the rest of the graph is built — for example, authentication nodes or server-connect nodes. To mark a node as Init First:

1. Right-click the node → **Init First**. A badge appears on the node header.
2. During workflow load, all Init First nodes are created and wired **before** all other nodes.

To demote, right-click → **Remove Init First**.

---

## 5. Control Flow

### For Loop

The `for_loop` node generates a list of integer indices (`0` to `count - 1`) and fires `exec_out` **once** after building the complete list. The `loop_body` node drives per-item iteration.

```
[for_loop]                      [loop_body]
  count (int) ◄── [N]             list ◄── [for_loop.indices]
  exec_out ──────────────────►    exec_in
  indices ────────────────────►   current_index ──► [your work node]
                                  exec_out  (fires once per item)
                                  exec_on_finished  (fires when done)
```

`loop_body.break_condition` — connect a boolean to stop the loop early.

### While Loop

`while_loop` repeats while its `condition` input is `True`.

```
[while_loop]
  condition (bool) ◄── [condition source]
  exec_out ──► [work nodes] ──► [eventually sets condition to False]
```

> Ensure your loop has a guaranteed exit condition. If `condition` never becomes `False`, the application will appear to hang (though the Stop button will still work).

### If Condition

Routes execution to either `exec_true` or `exec_false` based on a boolean:

```
[if_condition]
  condition (bool)
  exec_true  ──► [true branch]
  exec_false ──► [false branch]
```

### Loop Body Lifetime

`exec_on_finished` on `loop_body` fires once after all iterations complete — use it to run downstream logic that depends on the entire loop's output.

---

## 6. Group Nodes — Subgraphs

Group nodes let you collapse a selection of connected nodes into a single, encapsulated unit.

### Creating a Group

1. Select 2 or more connected nodes.
2. Press **Ctrl+Shift+G** (or Edit → Group Selection).
3. The selection is replaced by a single **GroupNode**. Its ports mirror the boundary connections of the original selection.

### Inspecting and Editing

Double-click a GroupNode to open the subgraph in a new tab. The tab is labeled `[group_name]`. Edits inside the subgraph tab — adding/removing nodes, changing parameters — sync back to the parent workflow in real time. Undo/redo works across both levels.

### GroupNode Port Routing

| Port | Behavior |
|------|----------|
| `exec_in` | Triggers execution of the inner graph |
| `exec_out` | Fires when the inner graph completes without an unhandled exception |
| `exec_fail` | Fires only when an unhandled exception occurs inside the subgraph |

> `exec_out` fires for any completion — including semantic failures like a Maya node returning an error code. Wire `exec_fail` only for catastrophic exception handling.

---

## 7. Python Script Node

The `python_script` node embeds arbitrary Python code directly in a workflow.

### Usage

1. Place a `python_script` node on the canvas.
2. Click the **Edit Script** button on the node to open the code editor.
3. Write your logic. Your script receives:
   - `inputs` — dict of all connected input port values
4. Assign your primary output to a variable named `result`.

```python
# Compute word count of an input string
text = inputs.get("text", "")
result = len(text.split())
```

5. Close the editor. The script is saved inside the workflow JSON and restored automatically on reload.

### Code Editor Features

When **QScintilla** is installed (`pip install QScintilla`):

- Syntax highlighting (Python, Dracula-inspired dark theme / One-Light theme)
- Autocomplete for Python keywords and common node methods
- Inline syntax error detection with gutter highlighting
- Ctrl+Wheel to zoom

Without QScintilla, a plain text fallback editor is used. The node functions identically in both cases.

---

## 8. Workflow File Management

### Save and Load

| Action | Shortcut | Notes |
|--------|----------|-------|
| Save | `Ctrl+S` | Smart-saves to current path; prompts on first save |
| Save As | `Ctrl+Shift+S` | Always prompts for path |
| Load | `Ctrl+O` | Standard file picker |
| Recent files | File → Open Recent | Last 10 workflows; grayed-out if file no longer exists |
| New tab | `Ctrl+N` | Empty workflow in a new tab |

Workflow files are standard `.json` — portable, version-controllable, and human-readable.

### Tab Management and Dirty Detection

Any edit to a workflow marks its tab with a `*` prefix: `my_graph.json` → `* my_graph.json`.

Closing a dirty tab shows: **Save | Discard | Cancel**. Closing the application checks all open tabs.

### Autosave and Crash Recovery

Every **2 minutes**, all non-empty open tabs are written to `~/.vibrante_node_autosave.json`. If the application exits uncleanly (crash, forced kill), the next launch detects this file and shows a **Restore Session** dialog with the recovered tab names.

- Restored tabs start as **dirty** (marked `*`) — they contain unsaved crash content.
- Choosing "Discard" in the restore dialog permanently deletes the autosave.
- On a clean exit (`File → Exit` or window close), the autosave file is deleted automatically.

### Installing Custom Nodes

Use **Nodes → Load Node From JSON** to install a `.json` node definition file. The file is:

1. Validated (must contain `node_id` and `python_code` fields).
2. Copied into the user `nodes/` directory (created if absent).
3. Registered in the node library immediately — no restart required.

> Selecting a workflow file by mistake shows a clear "Wrong File Type" message instead of silently failing.

---

## 9. Node Library and Canvas Search

### Library Categories

The Library panel organizes all 200+ bundled nodes into categories:

| Category | Description |
|----------|-------------|
| General / IO | Console, file reader/writer, HTTP request, delay |
| Control Flow | `if_condition`, `for_loop`, `while_loop`, `loop_body`, `branch` |
| Data | `create_list`, `create_dictionary`, JSON parser |
| String | `string_concat`, `string_split`, `string_lowercase`, `string_uppercase` |
| Math | `math_add`, `compare`, `math_abs` |
| Logic | `logic_and`, `logic_compare` |
| MCP | `mcp_server_init`, `mcp_list_tools`, `mcp_call_tool` — generic MCP client nodes |
| Houdini | Live bridge nodes + AI orchestration nodes (`hou_mcp_*`) |
| Maya | Headless action-list nodes |
| Blender | Headless action-list nodes |
| Prism | 62 Prism Pipeline v2 nodes |

> **Note:** Houdini AI orchestration nodes (`hou_mcp_*`) appear in the Houdini category only when the Houdini plugin is installed and `v_nodes_dir` includes `plugins/houdini/v_nodes_houdini/`.

### Canvas Search — Ctrl+F

Press `Ctrl+F` to open a floating search bar centered at the top of the canvas. It filters all nodes currently on the canvas (not the library):

- **Type** to filter by display name or node ID
- **Enter / ↓** to advance to the next match and pan the view
- **Shift+Enter / ↑** to go back to the previous match
- **Escape** to close

The match counter shows "X / N matches".

---

## 10. Prism Pipeline Integration

Vibrante-Node includes 62 Prism Pipeline nodes covering the full Prism v2 API.

### Initial Setup

1. Drag a `prism_core_init` node onto the canvas.
2. Set the `prism_root` parameter to your Prism installation directory.
3. Connect nothing — `PrismCore` is shared automatically across all `prism_*` nodes.

### Auto-Bootstrap

Before any node in the graph executes, the engine:
1. Scans for a `prism_core_init` node.
2. Calls `bootstrap_prism_core()` on the Qt main thread.
3. Stores the resulting `PrismCore` instance in a global cache.

All subsequent `prism_*` nodes resolve this cached instance via `resolve_prism_core()` — no wiring required.

### Available Node Groups

| Group | Key Nodes |
|-------|-----------|
| Core | `prism_core_init`, `prism_core_info` |
| Entities | `prism_get_assets`, `prism_get_shots`, `prism_build_entity` |
| Products | `prism_get_products`, `prism_create_product_version`, `prism_get_latest_product_path` |
| Media | `prism_get_media`, `prism_create_playblast` |
| Scenes | `prism_open_scene`, `prism_save_scene_version`, `prism_get_scene_path` |
| Config | `prism_get_config`, `prism_set_config` |
| Projects | `prism_list_projects`, `prism_create_project`, `prism_change_project` |
| USD | `prism_usd_entity_path`, `prism_usd_sublayer_path`, `prism_usd_update_department_layer` |
| Advanced | `prism_eval`, `prism_register_callback`, `prism_login_token` |

### Troubleshooting Prism

| Symptom | Resolution |
|---------|-----------|
| "PrismCore not initialized" | Add `prism_core_init` to the graph; verify `prism_root` path |
| Nodes not visible in library | Check `v_nodes_dir` in Settings → Application Paths |
| `getShots()` returns empty | Prism v2.1+ changed the API shape; ensure node version is ≥ v1.7 |

---

## 11. Houdini Integration

Vibrante-Node communicates with a live Houdini session over a local TCP JSON-RPC socket.

### Plugin Setup

1. Open `plugins/houdini/vibrante_node.json` and set:
   ```json
   { "VIBRANTE_NODE_APP": "/absolute/path/to/Vibrante-Node" }
   ```
2. Install the package in Houdini (add the file path to `HOUDINI_PACKAGE_DIR`).
3. Restart Houdini. A **Vibrante-Node** shelf and menu entry will appear.

### Launching

Click **Vibrante-Node → Launch** in Houdini's menu bar. This starts a JSON-RPC server inside Houdini and launches the Vibrante-Node application as a subprocess, pre-wired to that session.

### Available Houdini Nodes

| Node | Purpose |
|------|---------|
| `hou_create_geo` | Create an Object-level geo container |
| `hou_set_parm` / `hou_get_parm` | Read/write node parameters |
| `hou_set_parms` | Set multiple parameters at once |
| `hou_cook` | Cook a node |
| `hou_connect` | Wire node inputs/outputs |
| `hou_run_code` | Execute arbitrary Python inside Houdini |
| `hou_scene_info` | Get HIP file, version, FPS, frame range |
| `hou_save_hip` | Save the current scene |
| `hou_set_display` / `hou_set_render` | Set display and render flags |

### Connection Behavior

- The bridge uses `TCP_NODELAY` for minimal latency on Windows.
- A 30-second socket timeout raises `ConnectionError` if Houdini stops responding.
- The client reconnects automatically on `BrokenPipeError`.

---

## 12. AI Orchestration — MCP Runtime

Vibrante-Node v2.4.0 adds a complete AI orchestration runtime accessible in two ways: through visual node graphs (Visual Workflow Orchestration) and through a direct MCP server connection (Direct Runtime Orchestration).

### Visual Workflow Orchestration

Use the `hou_mcp_*` node family inside a workflow to build AI-driven Houdini pipelines with visual debugging, step-by-step inspection, and interactive approval gates.

**Generic MCP client nodes** (bundled in all installations, `category: MCP`):

| Node | Purpose |
|------|---------|
| `mcp_server_init` | Connect to any MCP server by name. Supports stdio (subprocess) and SSE (HTTP) transports. |
| `mcp_list_tools` | List all tools available on a registered MCP server. |
| `mcp_call_tool` | Call any tool on a registered MCP server with JSON arguments. |

**Houdini AI orchestration nodes** (`category: Houdini`, requires Houdini plugin):

| Node | Purpose |
|------|---------|
| `hou_mcp_scene_context` | Read the current Houdini scene state as a structured snapshot (networks, selection, HDAs, render nodes). The linchpin node — read this before planning. |
| `hou_mcp_build_node_chain` | Build a Houdini network from a JSON spec: create nodes, set parameters, connect them, layout, optionally cook. |
| `hou_mcp_transaction` | Execute a batch of ops atomically. Validates all ops up front; rolls back on failure. |
| `hou_mcp_graph_diff` | Read the dirty-state ledger — what was created, modified, deleted, or connected since the last diff. |
| `hou_mcp_ai_plan` | Parse a natural language prompt → intent → context analysis → structured execution plan. Never executes. |
| `hou_mcp_ai_preview` | Validate an AI plan without executing: risk level, errors, dependency impact, capability gaps. |
| `hou_mcp_ai_execute` | Execute a validated plan via the transaction system. Blocks on high-risk plans until an `approver` is supplied. |
| `hou_mcp_ai_review` | Post-execution review: did execution match the original intent? Returns outcome, match score, recommendations. |

**Canonical AI planning workflow:**

```
hou_mcp_scene_context   ── read current scene state
    ↓ context
hou_mcp_ai_plan         ── "build a pyro smoke source inside /obj/geo1"
    ↓ plan
hou_mcp_ai_preview      ── validate risk, check constraints
    ↓ preview
if_condition            ── check risk_level == "low" or approval given
    ↓ (approved)
hou_mcp_ai_execute      ── execute transactionally, rollback on failure
    ↓ result
hou_mcp_ai_review       ── verify intent matched execution
    ↓ review
console_print           ── log outcome
```

### Direct Runtime Orchestration — Headless MCP Server

Run the Vibrante runtime as a standalone MCP server and connect Claude Desktop, Codex CLI, or Cursor directly. No visual canvas is needed.

**Step 1 — Start the Houdini bridge** (if using Houdini scene operations):
```
Houdini → Vibrante-Node menu → Launch Vibrante-Node
```

**Step 2 — Start the MCP server:**
```bash
python scripts/run_vibrante_mcp.py
```

**Step 3 — Configure your AI client.** See [README.md](README.md) for Claude Desktop, Codex CLI, and Cursor configuration.

**Step 4 — In your AI client session:**

Call `initialize_runtime_context` first, then use any of the 12 semantic tools:

| Category | Tools |
|---|---|
| Runtime | `initialize_runtime_context`, `query_runtime_state`, `query_scene_context` |
| Knowledge | `query_capabilities`, `query_workflow_templates`, `query_examples` |
| Planning | `plan_scene`, `preview_execution`, `validate_execution_plan` |
| Execution | `execute_workflow_transaction`, `review_execution` |
| Node Info | `query_node_parameters` |

### Runtime Safety Rules

Regardless of orchestration mode, the runtime enforces these rules:

- All mutations route through the transaction system (begin → validate → execute → commit/rollback)
- Plans with `ok=False` are never executed
- High-risk plans (`requires_approval=True`) block until an approver identity is supplied
- `delete_node` operations are treated as high-risk (10× weight) and always trigger approval review
- No raw Houdini API calls are exposed to AI tools — only semantic, validated operations

---

## 13. Settings and Environment

### Preferences Dialog — Edit → Preferences (`Ctrl+,`)

| Page | Contents |
|------|----------|
| **Python Runtime** | `VIBRANTE_PYTHONPATH` — extra `sys.path` entries, one per line. Shows current `sys.path` state. |
| **Application Paths** | `v_nodes_dir` — extra node directories. `v_scripts_path` — extra script directories. Supports multiple paths (one per line). |
| **Environment Variables** | Custom `os.environ` key/value pairs. Validated (alphanumeric + underscore names). |
| **Vibrante Variables** | Read-only table of all built-in runtime variables with current values. Refresh button. |

Clicking **OK** applies all changes immediately:
- Node library reloads (picks up new `v_nodes_dir` paths).
- Scripts menu rebuilds (picks up new `v_scripts_path` scripts).
- Custom variables are injected into `os.environ`.
- No restart required.

### Import and Export Settings

Two buttons at the bottom-left of the Preferences dialog:

- **Export Settings…** — saves all four configuration groups to a portable `.json` file. Captures the current dialog state (including unsaved edits).
- **Import Settings…** — loads a settings file and populates all four UI widgets for review. Changes are not committed until you click OK.

**Settings file format:**
```json
{
  "vibrante_pythonpath": ["C:/MyLibs/python"],
  "v_nodes_dir": ["C:/Studio/nodes"],
  "v_scripts_path": ["C:/Studio/scripts"],
  "custom_variables": {"STUDIO_ROOT": "/studio", "PROJECT": "myproject"}
}
```

### Scripts Menu

**Scripts → [script name]** runs any `.py` file found in the `v_scripts_path` directories. Scripts execute with `window` and `scene` in their global namespace. Use **Scripts → Refresh Scripts** to rescan without restarting.

---

## 14. Keyboard Shortcuts Reference

### Graph Navigation

| Shortcut | Action |
|----------|--------|
| Mouse Wheel | Zoom in / out |
| Middle-mouse drag | Pan canvas |
| `F` | Focus view on selected nodes; focus canvas center if nothing selected |
| `Ctrl+F` | Open canvas search bar |
| `Ctrl+M` | Toggle mini-map |

### Node Operations

| Shortcut | Action |
|----------|--------|
| `Tab` | Open "Add Node" search popup at cursor |
| `Ctrl+C` | Copy selected nodes |
| `Ctrl+V` | Paste nodes at cursor position |
| `Delete` | Delete selected nodes or wires |
| `Ctrl+E` | Edit selected node in Node Builder |
| `Ctrl+R` | Reload selected node from disk |
| `Ctrl+Shift+R` | Reload all registered node types from disk |
| `Ctrl+G` | Wrap selection in Backdrop |
| `Ctrl+Shift+G` | Collapse selection into Group Node |
| Ctrl+Wheel | Zoom in code editor widgets |

### Execution

| Shortcut | Action |
|----------|--------|
| `F5` | Execute current workflow |
| `Shift+F5` | Stop / cancel execution |

### Workflow Editing

| Shortcut | Action |
|----------|--------|
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+S` | Save workflow |
| `Ctrl+Shift+S` | Save workflow as |
| `Ctrl+O` | Open workflow |
| `Ctrl+N` | New workflow tab |
| `Ctrl+W` | Close current tab |
| `Ctrl+,` | Open Preferences (Settings) |
| `Ctrl+A` | Select all nodes |

> **Hotkey suppression**: All shortcuts are disabled when a text input widget on the canvas has keyboard focus. Typing in node text fields will not accidentally trigger graph operations.

---

## 15. Troubleshooting

| Symptom | Likely Cause | Resolution |
|---------|-------------|-----------|
| Node shows red border | Exception inside `execute()` | Check the Log Panel for the error message and stack trace |
| Widget is grayed out | Port is connected upstream | Normal — widget shows the incoming live value |
| "PrismCore not initialized" | Missing `prism_core_init` | Add `prism_core_init` node; set valid `prism_root` |
| Stale ports after editing a node | JSON definition changed | Select node → `Ctrl+R` to reload from disk |
| Crash on startup | Import or plugin error | Check `crash.log` in the project directory |
| Session restore dialog on launch | Previous session crashed | Choose Restore to recover, or Discard to start fresh |
| Canvas search shows no matches | Filtering canvas nodes, not library | The search bar (Ctrl+F) only filters nodes on the current canvas |
| "Wrong File Type" on workflow load | Selected a node JSON instead of workflow | Use Nodes → Load Node From JSON for node files |
| Houdini nodes not in library | Plugin `v_nodes_dir` not configured | Verify `VIBRANTE_NODE_APP` in `vibrante_node.json`; check Houdini console |
| "Unknown publisher" on exe | Unsigned binary | Expected for dev builds; see `tools/sign_release.ps1` |
| Loop appears to hang | While loop condition never becomes False | Add a `loop_break` node or verify condition logic |
| Type mismatch warning in log | Connected ports of different types | Informational only — connection still works; `any` ports are always compatible |
| MCP server won't start | `mcp` package missing | `pip install "mcp>=1.0.0"` |
| `query_scene_context` returns "bridge not available" | Houdini bridge not running | Launch Vibrante-Node from Houdini menu bar; verify `VIBRANTE_HOU_PORT` |
| `execute_workflow_transaction` returns `pending_approval` | Plan marked as high-risk | Supply `approver="your_name"` argument to authorize execution |
| `hou_mcp_ai_plan` not in library | Houdini plugin path missing | Set `v_nodes_dir` to `plugins/houdini/v_nodes_houdini/` in Preferences → Application Paths |
| AI plan `ok=False` | Planning failed | Check `error` output on `hou_mcp_ai_plan`; verify parent path exists in scene |

**Log files:**

- `crash.log` — unhandled exception traces, written to the project root directory

**Related documentation:**

- [Node Builder API](NODE_BUILDER_API.md) — creating and distributing custom nodes
- [Automation API](AUTOMATION_API.md) — scripting the application programmatically
- [Developer Guide](DEVELOPER.md) — engine internals and architecture
- [Technical Reference](DOCUMENTATION.md) — complete API and schema reference
