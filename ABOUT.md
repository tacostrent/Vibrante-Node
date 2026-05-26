# Vibrante-Node

**Vibrante-Node** is an open-source, node-based visual workflow framework written in Python, developed by Mahmoud Kamal (GitHub: [KamalTD](https://github.com/KamalTD)). It provides a graphical canvas on which users construct modular automation pipelines by connecting nodes that process and route data between each other. The project targets visual effects (VFX) and animation production pipelines, with native integrations for Autodesk Houdini, Autodesk Maya, Blender, the Prism Pipeline studio management system, and Thinkbox Deadline render management software.

---

## Contents

1. [Overview](#overview)
2. [History](#history)
3. [Features](#features)
4. [Architecture](#architecture)
5. [Integrations](#integrations)
6. [Persistence and Serialization](#persistence-and-serialization)
7. [Platform Support](#platform-support)
8. [Licensing](#licensing)
9. [See Also](#see-also)
10. [External Links](#external-links)

---

## Overview

Vibrante-Node presents a `QGraphicsScene`-based canvas in which node widgets, port items, and edge items represent computational units and the data connections between them. Execution is driven by an asyncio-based engine (`NetworkExecutor`) that resolves topological order and drives each node's asynchronous `execute()` coroutine. The UI remains responsive during pipeline execution via a zero-interval `QTimer`-stepped event loop (`_EventLoopRunner`) on the Qt main thread, without requiring a third-party async/Qt bridge library.

Nodes are defined as Python classes paired with JSON definition files. The framework ships 177 bundled node definitions across categories including Prism Pipeline, Maya, Blender, Houdini, control flow, data structures, string/math utilities, file system, and HTTP. Users can author and distribute custom nodes without modifying the core application. A built-in Node Builder GUI generates Python class stubs from a port configuration table and keeps the code editor and port definitions in bidirectional sync.

---

## History

Vibrante-Node was first released in 2024 under the GitHub username [KamalTD](https://github.com/KamalTD). The project uses semantic versioning. Key release milestones:

| Version | Release Date | Type | Key additions |
|---|---|---|---|
| v1.1.0 | 2024 | Initial public release | Core canvas, execution engine, Houdini live bridge |
| v1.6.1 | 2024–25 | Minor | Prism Pipeline integration (62 nodes) |
| v1.8.4 | 2025 | Minor | QScintilla code editor, hot-reload, Houdini bridge hardening |
| v2.0.0 | 2025 | Major | GroupNode/subgraphs, mini-map, canvas search, autosave, live wire inspector, per-node execution timing |
| v2.1.0 | 2026 | Minor | Unsaved-changes detection, port type-mismatch warnings |
| v2.2.0 | 2026-05-15 | Minor | Settings dialog (Preferences), EnvManager, reactive propagation thread-safety fix |
| v2.2.1 | 2026-05-15 | Patch | About dialog crash fix, LICENSE file bundled in Windows exe |
| v2.3.0 | 2026-05-18 | Minor | HTTP Request node, Authenticode signing scripts, Node Builder correctness fixes, canvas drag-trail fix |
| v2.4.0 | 2026-05-26 | Minor | Complete AI orchestration MCP runtime (Tiers 1–6), 26 new nodes, MCP server entry point, query_node_parameters tool, node ID cleanup |

---

## Features

### Canvas and Visualization

The canvas is built on a `QGraphicsScene` / `QGraphicsView` pair with the following capabilities:

- **Pan, zoom, and drag** via mouse-wheel and keyboard shortcuts
- **Type-coded ports** — ports and connecting wires are colored by data type (`int`, `string`, `float`, `bool`, `any`) for instant visual identification
- **Live wire inspector** — hovering a connected wire after execution displays the last value that flowed through it as a tooltip; values persist until the next run begins
- **Mini-map** — a 200×150 px canvas thumbnail with a viewport indicator rectangle; click or drag to pan the main view (Ctrl+M to toggle)
- **Canvas search** — a floating search bar (Ctrl+F) that filters all nodes by display name or node ID; Enter/Shift+Enter cycles forward and backward through matches
- **Backdrop and sticky notes** — annotate and group canvas regions visually without affecting execution
- **Subgraph display** — double-clicking a GroupNode opens its embedded workflow in a fully editable tab with real-time synchronization back to the parent graph

### Execution Engine

The `NetworkExecutor` resolves execution order via topological sort, then drives node coroutines using `asyncio`. Core engine behaviors include:

- **Exec flow pins** — `exec_in` / `exec_out` ports impose explicit sequential ordering; data-only nodes run reactively when upstream values change
- **Reactive propagation** — changing a widget value immediately propagates through all downstream nodes before a full execution run
- **Subgraph / GroupNode** — any selection of connected nodes can be collapsed into a single `GroupNode` (Ctrl+Shift+G); the embedded workflow executes as a nested graph and routes `exec_fail` only on unhandled exceptions
- **Bypass** — individual nodes can be bypassed; the engine skips them while preserving data flow continuity
- **Execution timing** — the log panel reports elapsed time per node (e.g. `Node 'Get Asset' finished in 0.34s`)
- **Init-first ordering** — `init_priority` ensures authentication or connection nodes are fully initialized before downstream consumers run

### Node Library (177 bundled nodes)

| Category | Count | Notes |
|---|---|---|
| Prism Pipeline | 62 | Projects, entities, assets, shots, products, USD, media |
| Maya | 24 | Headless subprocess operations via `mayapy` |
| Blender | 20 | Headless subprocess via Blender command-line interface |
| Houdini (headless) | 17 | Headless batch operations via `hbatch` / `hython` |
| Control flow | — | `if_condition`, `for_loop`, `while_loop`, `loop_body`, `sequencer` |
| Data structures | — | Lists, dictionaries, variable nodes, `get_dict_value`, `set_dict_value` |
| String utilities | — | Concat, split, replace, lowercase, uppercase |
| Math and logic | — | Add, subtract, multiply, divide, modulo, compare, logical gate |
| File system | — | Read, write, append, create folder, list directory |
| Network | 1 | HTTP GET/POST with JSON body, custom headers, and configurable timeout |

In addition, 19 Houdini live bridge nodes are available as a separate plugin in `plugins/houdini/v_nodes_houdini/` and are not counted in the 177 bundled total.

### Developer SDK

Nodes are defined as Python classes subclassing `BaseNode`, paired with JSON definitions that declare ports and embed the Python source:

```python
from src.nodes.base import BaseNode

class My_Node(BaseNode):
    name = "my_node"

    def __init__(self):
        super().__init__()  # automatically adds exec_in and exec_out
        self.add_input("text", "string", widget_type="text", default="hello")
        self.add_output("result", "string")

    async def execute(self, inputs):
        return {"result": inputs.get("text", "").upper(), "exec_out": True}

def register_node():
    return My_Node
```

The SDK provides:

- **Node Builder** — GUI editor with port configuration tables and automatic Python class generation; bidirectional sync between UI state and code
- **Hot-reload** — Ctrl+R recompiles a node class and rebinds live canvas instances without restarting the application
- **Registry source tracking** — `NodeRegistry.get_source_path()` and `reload_node_definition(node_id)` for programmatic node management
- **QScintilla editor** — syntax-highlighted Python editor with autocomplete in Node Builder, Script Editor, and Scripting Console; graceful fallback to `QPlainTextEdit` if QScintilla is not installed
- **Scripting Console** — full API access to the graph, scene, and registry for programmatic manipulation at runtime

---

## Architecture

Vibrante-Node is organized in three primary layers.

### Execution Engine (`src/core/`)

`NetworkExecutor` performs topological resolution of the node graph and drives each node's `async execute(inputs)` coroutine. Typed Qt signals — `node_started`, `node_finished`, `node_error`, `node_output` — deliver results to the UI layer without blocking execution. `NodeRegistry` loads node JSON definitions, compiles embedded Python source via `exec()`, and instantiates classes on demand. A `_source_paths` mapping enables targeted hot-reload by tracking the on-disk location of each definition.

### Event Loop (`_EventLoopRunner`)

The asyncio event loop is stepped by a zero-interval `QTimer` on the Qt main thread. Each timer tick calls `loop.call_soon(loop.stop)` and then `loop.run_forever()`, advancing the event loop by one step before returning control to Qt. This design keeps the UI responsive without the overhead of a separate thread and without requiring a third-party async/Qt bridge. As a consequence, HTTP clients that require a continuously running event loop (such as `aiohttp`) are not compatible; the correct pattern for network I/O is `urllib.request` executed in a thread pool via `loop.run_in_executor(None, sync_fn)`.

### Qt Frontend (`src/ui/`)

The canvas is a `QGraphicsScene` / `QGraphicsView` pair. Node widgets, port items, and edge items are all `QGraphicsItem` subclasses. A `_MainThreadDispatcher(QObject)` with a `Qt.QueuedConnection` signal ensures that reactive propagation and log output — emitted from the asyncio background thread — are always delivered on the Qt main thread.

---

## Integrations

### Houdini (Live Bridge)

A Houdini plugin ships in `plugins/houdini/`. It starts a JSON-RPC server (`vibrante_hou_server.py`) inside a running Houdini session; the `HouBridge` client communicates over a local TCP socket with `TCP_NODELAY` and per-call `threading.Lock` protection. The bridge exposes approximately 20 methods:

| Method | Description |
|---|---|
| `create_node`, `delete_node` | Create and delete Houdini nodes by path |
| `set_parm`, `get_parm`, `set_parms` | Read and write node parameters |
| `connect_nodes`, `cook_node` | Wire and evaluate node networks |
| `run_code` | Execute arbitrary Python code inside Houdini; return a value via `result` |
| `node_info`, `children`, `node_exists` | Query node tree structure |
| `set_expression`, `set_keyframe`, `set_frame` | Animate parameters |
| `scene_info`, `save_hip` | Scene metadata and persistence |
| `set_display_flag`, `set_render_flag`, `layout_children` | Visualization flags and layout |

Setup requires configuring `VIBRANTE_NODE_APP` (path to the application root) in `plugins/houdini/vibrante_node.json`, then registering the package in Houdini. The integration launches from the Vibrante-Node shelf tool or the **Vibrante-Node** menu added to the Houdini menu bar.

### Maya and Blender (Headless Batch)

Maya and Blender integrations follow an action-list pattern. `maya_action_*` and `blender_action_*` nodes append typed operation dictionaries to a list; the `maya_headless` and `blender_headless` nodes execute the accumulated list in a background DCC subprocess (`mayapy` or `blender --background`). No live DCC connection is required; operations are batched and replayed in the subprocess.

Supported Maya operations include: open/save scene, import/export Alembic and FBX, render, set frame range, assign materials, create render layers, playblast, reference management, and custom MEL/Python execution.

Supported Blender operations include: open/save .blend, import/export Alembic, FBX, glTF, OBJ, and USD, render, set frame range, and custom Python execution.

### Prism Pipeline

62 nodes cover the Prism v2 API for project, entity, asset, shot, product, and USD department layer management. `PrismCore` is initialized automatically before the graph executes — placing a `prism_core_init` node anywhere in the graph triggers auto-bootstrap on the Qt main thread before execution begins. All `prism_*` nodes resolve the shared `PrismCore` instance from a global cache; no explicit wiring between nodes is required.

### Thinkbox Deadline

Deadline render farm submission nodes (`deadline_maya_submit`, `deadline_houdini_submit`, `deadline_blender_submit`, `deadline_job_status`) are included in the bundled library. A reference workflow (`vfx_workflows/04_deadline_render_pipeline.json`) demonstrates render farm submission integrated with Prism asset management.

---

## Persistence and Serialization

Workflows and node definitions are stored as portable `.json` files. The workflow format (`WorkflowModel`, validated with Pydantic v2) embeds all node instances, port connections, widget values, and subgraph payloads. No binary formats, databases, or external services are required.

Features built on this format include:

- **Autosave and crash recovery** — all open tabs are written to `~/.vibrante_node_autosave.json` every two minutes; a restore dialog appears on the next launch if the application exited unexpectedly
- **Unsaved-changes detection** — dirty tabs are marked with a `*` prefix; closing a tab or the application prompts Save / Discard / Cancel per dirty tab
- **Recent files** — File → Open Recent lists the last 10 saved or loaded workflow files
- **Settings portability** — the full configuration profile (Python paths, node directories, environment variables) can be exported to a JSON file and restored on another machine

---

## Platform Support

| Platform | Distribution methods |
|---|---|
| Windows | Pre-built `.exe` with embedded Windows `VERSIONINFO` resource (no Python required); from source (Python 3.10+) |
| Linux | `pip install vibrante-node`; AppImage (self-contained binary, no Python required); `.deb` package for Ubuntu/Debian |

> **Wayland note:** PyQt5's Wayland backend is unstable on some distributions. If the application fails to start on a Wayland desktop, set `QT_QPA_PLATFORM=xcb` before launching.

---

## Licensing

Vibrante-Node uses an open-core hybrid licensing model:

| Component | License |
|---|---|
| Core runtime | GNU Affero General Public License v3 (AGPLv3) |
| SDK and public API | MIT License |
| Documentation and examples | Creative Commons Attribution 4.0 (CC BY 4.0) |
| Official plugins and commercial nodes | Commercial license |
| Enterprise integrations | Commercial license |

Free use is permitted for individuals, students, educational institutions, and open productions. Commercial studio deployment requires a paid commercial license.

Licensing inquiries: [contact@vibrante-node.com](mailto:contact@vibrante-node.com)

---

## See Also

- Node-based programming
- Visual programming language
- Digital content creation (DCC)
- Prism Pipeline
- Thinkbox Deadline

---

## External Links

- [Official website — vibrante-node.com](https://vibrante-node.com)
- [GitHub repository — github.com/KamalTD/Vibrante-Node](https://github.com/KamalTD/Vibrante-Node)
- [Documentation — vibrante-node.com/docs](https://vibrante-node.com/docs)
- [Release notes — vibrante-node.com/release-notes](https://vibrante-node.com/release-notes)
- [GitHub Releases — download page](https://github.com/KamalTD/Vibrante-Node/releases)

---

*© 2024–2026 Mahmoud Kamal (KamalTD). All rights reserved.*

