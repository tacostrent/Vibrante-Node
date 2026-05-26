# Vibrante-Node v2.4.0 — Introduction

**Vibrante-Node** is a Python-based visual node graph automation platform that lets you build, run, and maintain complex multi-step workflows by wiring together reusable node blocks on an interactive canvas. It ships with a PyQt5 graphical interface, an asyncio-based execution engine, and a growing library of nodes covering general-purpose automation, filesystem operations, DCC application control (Maya, Houdini, Blender), studio pipeline management (Prism Pipeline), and render farm submission (Deadline). Every node is a self-contained unit of logic defined in a single JSON file paired with Python code, making the platform trivially extensible by any Python developer without requiring modifications to the core application.

---

## Table of Contents

1. [Core Philosophy](#core-philosophy)
2. [Who Is This For](#who-is-this-for)
3. [Feature Overview](#feature-overview)
4. [Why Visual Node Graphs](#why-visual-node-graphs)
5. [Beyond VFX — General Automation](#beyond-vfx--general-automation)
6. [Supported Integrations](#supported-integrations)
7. [Architecture Overview](#architecture-overview)
8. [Version History](#version-history)
9. [Documentation Map](#documentation-map)

---

## Core Philosophy

### Why Node-Based?

Scripts are linear. Node graphs are not. When a pipeline task grows beyond a handful of steps — conditional branching, parallel tracks, optional DCC calls, error routing — a script becomes a wall of nested `if` statements and callback chains that is hard to read, hard to modify, and impossible to hand off to a non-programmer. A node graph externalises the control flow into a visual structure that anyone can understand at a glance: data flows left to right, execution flows top to bottom, and every node is an isolated contract with defined inputs and outputs.

Vibrante-Node adopts the Unreal Engine Blueprint model of **exec pins** alongside data pins. Exec pins (the white square connectors) explicitly wire the order of operations. Data pins (the coloured circles) carry values between nodes. This dual-channel approach lets you build workflows that are simultaneously readable as flowcharts and correct as programs.

### Why Async?

DCC operations — cooking a Houdini geometry, rendering a Maya scene, querying a Prism Pipeline project database — can take seconds or minutes. A synchronous engine would freeze the UI and prevent you from monitoring progress, reading log output, or stopping a runaway task. Vibrante-Node runs the execution engine on a dedicated asyncio event loop driven by a zero-interval `QTimer` on the Qt main thread (`_EventLoopRunner` in `src/ui/window.py`). Every node's `execute()` method is a Python coroutine (`async def`). This means:

- The UI stays responsive during execution.
- Long-running nodes can `await` external results without blocking.
- The Stop button works immediately.
- Multiple parallel execution branches can run concurrently.

### Why Extensible?

No automation platform ships with every node you will ever need. Vibrante-Node is designed so that adding a new node requires exactly one file: a `.json` file containing the port definitions and the Python code. There is no registration step, no recompile, no plugin manifest beyond dropping the file in the `nodes/` directory. The `NodeRegistry` discovers and registers it automatically on startup. For DCC-specific nodes, the Houdini plugin package (`plugins/houdini/`) adds nodes from `v_nodes_houdini/` and scripts from `v_scripts_houdini/` via environment variables — no changes to the core application.

---

## Who Is This For

Vibrante-Node is built for three overlapping audiences.

### Visual Users and Technical Artists

Artists who need to automate repetitive tasks — renaming files, batch-exporting assets, running Houdini geometry operations — but do not want to write Python scripts. They build workflows by dragging nodes from the Library panel, connecting them on the canvas, and pressing F5. The node library is organised by category, searchable by name, and produces immediate visual feedback through the log panel and live wire value inspector.

**Typical tasks**: batch asset export, scene setup automation, file organisation, render submission.

### Pipeline TDs and Studio Engineers

Technical Directors who build and maintain shared workflows for a team. They author custom nodes using the Node Builder or by editing JSON files directly, package them as Houdini plugin additions or standalone `nodes/` files, and distribute them to artists. They integrate with Prism Pipeline for project/asset/shot management and with Deadline for render farm submission.

**Typical tasks**: pipeline integration nodes, studio-specific workflow templates, Prism entity queries, Deadline job configuration.

### Python Developers

Developers who want to build automated systems with a visual interface without writing a UI framework from scratch. They subclass `BaseNode`, implement `async def execute(self, inputs)`, and return a dict. The engine, canvas, log panel, autosave, and all other infrastructure are provided. They can also drive Vibrante-Node programmatically via the automation API (`AUTOMATION_API.md`).

**Typical tasks**: custom automation tooling, CI/CD pipeline steps, data processing workflows, service integrations.

---

## Feature Overview

| Feature | Description | Shortcut / API |
|---|---|---|
| **Interactive Canvas** | Pan, zoom, rubber-band select on a QGraphicsScene/View canvas | Middle Mouse / Alt+LMB, Ctrl+Wheel, drag |
| **Node Search Popup** | Fuzzy-search all registered nodes by name or ID | Tab |
| **Exec Flow Pins** | White square pins enforce execution order; data pins carry values | Drag output to input |
| **Async Execution Engine** | asyncio coroutines keep the UI responsive during long operations | F5 to run, Stop button to cancel |
| **GroupNode / Subgraph** | Collapse 2+ nodes into a single reusable subgraph node | Ctrl+Shift+G |
| **Mini-map** | 200x150 px canvas thumbnail with viewport indicator in bottom-right | Ctrl+M to toggle |
| **Canvas Search Bar** | Find any node by name in the current canvas | Ctrl+F |
| **Live Wire Inspector** | Hover a connected wire to see the last value that flowed through it | Mouse hover |
| **Bypass Mode** | Skip a node; exec chain continues through it transparently | Ctrl+B |
| **Backdrop / Network Box** | Label and visually group regions of the canvas | Ctrl+G |
| **Sticky Notes** | Free-floating text annotations | Right-click canvas |
| **Node Builder** | GUI editor for creating and editing node JSON + Python code | Ctrl+E |
| **Script Editor** | Standalone Python editor with QScintilla and syntax highlighting | Window menu |
| **Scripting Console** | Interactive Python REPL inside the app | Window menu |
| **Autosave** | Writes all open tabs to `~/.vibrante_node_autosave.json` every 2 minutes | Automatic |
| **Crash Recovery** | On next launch, offers to restore tabs from the autosave file | Automatic |
| **Recent Files** | File > Open Recent lists the last 10 workflows | File menu |
| **Node Execution Timing** | Log panel shows how long each node took, e.g. `finished in 0.34s` | Automatic |
| **Copy / Paste** | Copy and paste node selections within or across workflows | Ctrl+C / Ctrl+V |
| **Reload Node** | Re-read a node's JSON from disk and apply changes live | Ctrl+R |
| **Houdini Bridge** | TCP JSON-RPC connection to a live Houdini session | `get_bridge()` |
| **Maya Headless** | Headless Maya batch executor via action-list pattern | `maya_headless` node |
| **Blender Headless** | Headless Blender batch executor via action-list pattern | `blender_action_*` nodes |
| **Prism Pipeline** | 60+ nodes for project/asset/shot/product management | `prism_*` nodes |
| **Deadline Submission** | Submit render jobs to Thinkbox Deadline | `deadline_*` nodes |
| **Gemini AI Integration** | Chat with Google Gemini AI from within the app | Window menu |
| **Export to Python** | Export a workflow as a standalone Python script | File > Export |
| **Dark / Light Theme** | Toggle between Dracula dark and One-Light themes | Window > Theme |

---

## Why Visual Node Graphs

### The Problem with Plain Scripts

Consider a pipeline task: open a Maya scene, export alembic geometry, import it into Houdini, run a simulation, export the result, and submit a Deadline render job — but only if the simulation produces more than 1000 points, otherwise skip the render and log a warning. In a Python script this requires careful state management, nested conditionals, error handling at every step, and careful documentation so the next person can understand what it does.

In Vibrante-Node, this is five to ten nodes on a canvas. The conditional branch is visible as two exec paths. Error handling is a separate exec path from `exec_fail`. Anyone can understand the flow in ten seconds.

### Specific Benefits

**Discoverability.** Every available operation is in the node library, searchable by name. There is no need to remember function names or read API documentation to get started.

**Reusability.** A GroupNode packages any sub-workflow into a single named block that can be duplicated, shared, or nested. Workflows can be saved as templates and reused across projects.

**Live inspection.** The live wire inspector shows the last value that flowed through every connection after execution. There is no need to add print statements and re-run to debug data flow — hover the wire.

**Non-destructive iteration.** Bypass a node with Ctrl+B to skip it without deleting it. Reconnect differently. The canvas is a whiteboard that invites experimentation.

**Team collaboration.** A workflow file is a JSON document. It can be checked into version control, diffed, and merged. Artists can build workflows without writing code; developers can build nodes without building UIs.

---

## Beyond VFX — General Automation

While Vibrante-Node ships with deep VFX and animation pipeline integrations, the core platform is entirely domain-agnostic. The execution engine, canvas, node library, and file format do not have any VFX-specific logic. Any Python task can become a node.

**Examples of non-VFX use cases:**

- **File processing pipelines** — watch a folder, process new files, move or rename outputs, write a report.
- **Data transformation** — load JSON or CSV, filter, transform, write results. The `python_script` node runs arbitrary Python inline.
- **API orchestration** — call REST APIs in sequence, pass results between calls, handle errors on separate branches.
- **Build and deployment automation** — run shell commands via `python_script`, check exit codes via `compare` or `logical_gate`, conditionally proceed.
- **Machine learning experiments** — string together data loading, preprocessing, model training, and evaluation steps with visual control flow.
- **Database workflows** — query databases, transform results, insert or update records, log summaries.
- **Report generation** — pull data from multiple sources, aggregate, format, write files.

Any step that can be expressed as a Python function with typed inputs and outputs can be a Vibrante-Node node.

---

## Supported Integrations

### Houdini (Interactive Bridge)

The Houdini integration runs a JSON-RPC server (`vibrante_hou_server.py`) inside a live Houdini session over a local TCP socket. Vibrante-Node nodes call `bridge.create_node()`, `bridge.set_parm()`, `bridge.cook_node()`, and other methods to build and run Houdini networks interactively. The bridge supports all common Houdini operations: create/delete nodes, set parameters, wire connections, cook, save hip files, set keyframes, run arbitrary Python code inside Houdini via `bridge.run_code()`.

The Houdini plugin is installed by placing `plugins/houdini/vibrante_node.json` in the Houdini packages folder. It adds the Vibrante-Node menu to Houdini's menu bar, loads a shelf tool, and provides **Launch Vibrante-Node** and **Reconnect** commands.

### Maya (Headless Executor)

Maya nodes follow an "action list" pattern. Each `maya_action_*` node appends a dictionary to a list. The `maya_headless` node receives the completed action list and passes it to a headless Maya subprocess (`mayapy`) that executes each action in sequence. This approach does not require a running Maya session — it is suitable for batch processing and render farm pipelines.

Actions include: open/save/new scene, import/export alembic/FBX/OBJ, import/export camera, reference scene, assign material, create render layer, set AOVs, set render settings, set frame range, playblast, and custom Python.

### Blender (Headless Executor)

Blender nodes use the same action-list pattern as Maya. Each `blender_action_*` node appends an action dict. The executor runs Blender in background mode (`blender --background --python`). Actions include: open/save/new blend file, import/export alembic/FBX/glTF/OBJ/USD, render, set render settings, set frame range, scene info, and custom Python.

### Prism Pipeline

Prism Pipeline is a studio-grade project management system. Vibrante-Node ships with over 60 Prism nodes covering the full Prism API surface: initialise PrismCore, list/create/switch projects, query assets/shots/sequences, get product versions, export paths, save scene versions, create playblasts, manage USD layers, trigger callbacks, and more.

PrismCore is resolved automatically from a shared cache — there is no need to wire a `core` output between every Prism node. Place a `prism_core_init` node anywhere in the graph and all `prism_*` nodes find the same instance.

### Deadline (Thinkbox)

Deadline submission nodes (`deadline_maya_submit`, `deadline_houdini_submit`, `deadline_blender_submit`) wrap the Deadline command-line client to submit render jobs with configurable job name, pool, priority, frame range, and renderer settings.

---

## Architecture Overview

The following diagram shows how the major components relate to one another at runtime.

```
+----------------------------------------------------------+
|                     MainWindow (PyQt5)                   |
|  Menu Bar | Toolbar | Tab Bar                            |
|  +--------------------+  +----------------------------+  |
|  |  Library Panel     |  |  NodeView (QGraphicsView)  |  |
|  |  (node categories) |  |  +----------------------+  |  |
|  |  [search box]      |  |  |  NodeScene           |  |  |
|  |  [node list]       |  |  |  (QGraphicsScene)    |  |  |
|  +--------------------+  |  |  NodeWidget items    |  |  |
|                          |  |  Edge items          |  |  |
|  +--------------------+  |  |  Backdrop items      |  |  |
|  |  Log Panel         |  |  |  StickyNote items    |  |  |
|  |  [info/warn/err]   |  |  +----------------------+  |  |
|  +--------------------+  |  |  MiniMap overlay     |  |  |
|                          |  |  CanvasSearchBar     |  |  |
|                          +----------------------------+  |
+----------------------------------------------------------+
          |                          |
          | F5 / Run                 | Scene -> WorkflowModel
          v                          v
+--------------------+    +------------------------+
|  GraphManager      |    |  Persistence           |
|  (DAG + toposort)  |    |  (JSON load/save)      |
+--------------------+    +------------------------+
          |
          v
+--------------------+
|  NetworkExecutor   |   (QObject, asyncio coroutines)
|  node_started      |-->  UI: highlights running node
|  node_finished     |-->  UI: clears highlight
|  node_log          |-->  Log Panel
|  node_output       |-->  Live Wire Inspector
|  execution_finished|-->  UI: re-enable Run button
+--------------------+
          |
          | instantiates & calls execute()
          v
+------------------------------------------+
|  BaseNode subclasses (per node)          |
|  JSON nodes  |  Python builtins          |
+------------------------------------------+
          |
          | (Houdini nodes)     (Maya/Blender)    (Prism)
          v                     v                  v
+---------------+   +-------------------+   +-----------+
|  HouBridge    |   |  Headless         |   | PrismCore |
|  TCP JSON-RPC |   |  Subprocess       |   | (shared)  |
|  port 18811   |   |  (mayapy/blender) |   |           |
+---------------+   +-------------------+   +-----------+
          |
          v
   Live Houdini session
   (vibrante_hou_server.py)
```

**Data flow summary:**

1. The user builds a workflow on the **NodeScene** canvas. Each node is a `NodeWidget`; each connection is an `Edge`.
2. On F5, `MainWindow` serialises the scene to a `WorkflowModel` (Pydantic), builds a `GraphManager` from it, and creates a `NetworkExecutor`.
3. The executor identifies entry nodes (nodes with no connected `exec_in`), fires their `execute()` coroutines, and follows `exec_out` connections to chain subsequent nodes.
4. Data flows backward by pulling: when a node needs an input value from an upstream data node, the executor runs that upstream node first.
5. Results are broadcast via Qt signals: `node_output` updates the live wire inspector, `node_log` writes to the log panel, `node_started`/`node_finished` update node widget state.
6. DCC nodes call out to their respective bridges or subprocesses. All DCC calls are blocking within an `async def execute()` — the `await` call yields control to the event loop while waiting.

---

## Version History

| Version | Release | Major Milestones |
|---|---|---|
| **v1.0** | 2026 Q1 | Initial release. JSON node format, PyQt5 canvas, async engine, exec/data pins, Library panel, log panel, dark theme. |
| **v1.5** | 2026 Q2 | Headless action node pattern for Maya, Houdini, and Blender. Deadline submission nodes. `python_script` inline node. |
| **v1.6** | 2026 Q2 | Prism Pipeline integration (40+ nodes). `prism_core_init` auto-bootstrap. Shared PrismCore cache. |
| **v1.8.4** | 2026 Q2 | Node Builder GUI. Scripting Console. Script Editor with QScintilla. Export to Python. Import from Python. |
| **v1.8.5** | 2026 Q2 | QScintilla optional fallback (no hard crash on missing dependency). Houdini bridge socket fixes (TCP_NODELAY, lock, timeout). `vibrante_hou_server.py` headless fixes. `window.py` Houdini node/script loading fix. |
| **v2.0.0** | 2026-05-10 | Live Wire Inspector. Autosave / Crash Recovery. Recent Files. Node Execution Timing. Canvas Search Bar (Ctrl+F). Mini-map (Ctrl+M). Subgraph / Group Node (Ctrl+Shift+G) with editable subgraph tabs and sync-back. GroupNode bugs fixed (exec_fail, injected value, UUID serialization). KeyboardInterrupt crash fix. |
| **v2.1.0** | 2026-05-14 | Unsaved-changes detection: `*` tab marker, Save/Discard/Cancel on close. Port type mismatch warning in log panel. Fixed F5/Shift+F5 shortcuts. Fixed false `*` on loaded workflows. |
| **v2.1.1** | 2026-05-14 | Scripting Console theme fix (all panels). Houdini plugin standalone LICENSE. Windows VERSIONINFO in exe (fixes "Unknown publisher" on Windows 11). Contact email and website cleanup. |
| **v2.2.0** | 2026-05-15 | Settings dialog (Edit → Preferences, Ctrl+,). EnvManager persists Python paths, node dirs, script dirs, and custom env vars. Import/Export settings to JSON file. Qt thread-violation crash fix when typing in wired nodes. 10 website example nodes. 142 tests. |
| **v2.2.1** | 2026-05-15 | Patch: About dialog crash fix (`QTextEdit` → `QTextBrowser`). LICENSE file now bundled in exe (`_internal/`). |
| **v2.3.0** | 2026-05-18 | HTTP Request node (bundled). Authenticode signing tools. Node Builder exec-port corruption fix. Node Builder default-value round-trip fix. Icon-path field isolation fix. Load-node/load-workflow cross-detection. Canvas drag trail fix. http_request UI freeze fix (run_in_executor). Linux packaging (pip, AppImage, .deb). |
| **v2.4.0** | 2026-05-26 | Complete AI orchestration MCP runtime (Tiers 1–6): transaction system, AI planning pipeline, distributed execution, Tier 5 analytics, Tier 6 MCP server. 26 new nodes (3 generic MCP + 23 Houdini AI). query_node_parameters tool. Node ID cleanup. Subprocess crash log. Bug fixes: build_node_chain ordering, review_execution scoring, preview_execution ImportError. |

---

## Documentation Map

### Primary Guides (root-level docs)

| Document | Audience | Contents |
|---|---|---|
| [USER_GUIDE.md](../USER_GUIDE.md) | All users | Interface, canvas, execution model, all features, keyboard shortcuts, troubleshooting |
| [NODE_BUILDER_API.md](../NODE_BUILDER_API.md) | Node authors | BaseNode class reference, port system, lifecycle hooks, JSON schema, distribution, DCC integration patterns |
| [AUTOMATION_API.md](../AUTOMATION_API.md) | Pipeline TDs | Scripting console, scene/app/registry API, automation script examples, headless execution |
| [DEVELOPER.md](../DEVELOPER.md) | Contributors | Execution engine internals, event loop, data flow, node registry, serialization, Qt threading, EnvManager, plugin architecture |
| [DOCUMENTATION.md](../DOCUMENTATION.md) | Reference lookup | Complete node index, BaseNode API table, port/serialization schemas, env vars, signals, shortcuts, error index |

### Portal Documentation (this site)

| Document | Contents |
|---|---|
| **01_introduction.md** (this file) | What Vibrante-Node is, philosophy, audiences, architecture, version history |
| **02_getting_started.md** | Installation, first launch, first workflow walkthrough |
| **03_user_guide.md** | Canvas navigation, execution flow, all UI features |
| **04_workflow_tutorials.md** | Step-by-step workflow build tutorials |
| **05_node_development.md** | Complete node development guide (1,000+ lines) |
| **06_backend_architecture.md** | Execution engine deep dive with flow diagrams |
| **07_frontend_architecture.md** | Qt canvas architecture — NodeScene, NodeWidget, Edge |
| **08_api_reference.md** | Full class/method API reference (1,500+ lines) |
| **09_advanced_topics.md** | GroupNode, autosave, wire inspector, canvas search internals |
| **10_contribution_guide.md** | Contributing, testing, code style |
| **11_troubleshooting.md** | Diagnostic checklist, known issues, log interpretation |
| **12_examples_library.md** | Curated examples from `node_examples/`, `website_examples/` |
| **13_general_purpose_automation.md** | Automation patterns from `examples/automation/` |
| **14_custom_nodes_api.md** | Custom node SDK — extended reference |

### Release Notes

| Version | Type | File |
|---|---|---|
| v2.4.0 | Minor | [RELEASE_v2.4.0.md](../RELEASE_v2.4.0.md) |
| v2.3.0 | Minor | [RELEASE_v2.3.0.md](../RELEASE_v2.3.0.md) |
| v2.2.1 | Patch | [RELEASE_v2.2.1.md](../RELEASE_v2.2.1.md) |
| v2.2.0 | Minor | [RELEASE_v2.2.0.md](../RELEASE_v2.2.0.md) |
| v2.1.1 | Patch | [RELEASE_v2.1.1.md](../RELEASE_v2.1.1.md) |
| v2.1.0 | Minor | [RELEASE_v2.1.0.md](../RELEASE_v2.1.0.md) |
| v2.0.0 | Major | [RELEASE_v2.0.0.md](../RELEASE_v2.0.0.md) |
| Earlier | — | [releases/](../releases/) |

---

*Vibrante-Node v2.4.0 — Released 2026-05-26*
