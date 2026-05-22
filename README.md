<div align="center">
  <img src="icons/vibrante-node-resize_main_logo.png" width="300" alt="Vibrante-Node">

  <h3>Visual Workflow Orchestration for Python Developers and Production Pipelines</h3>

  <p>
    <a href="https://vibrante-node.com">Website</a> ·
    <a href="https://vibrante-node.com/docs">Docs</a> ·
    <a href="examples/">Examples</a> ·
    <a href="workflows/">Workflows</a> ·
    <a href="https://github.com/KamalTD/Vibrante-Node/releases">Releases</a> ·
    <a href="https://github.com/KamalTD/Vibrante-Node/discussions">Discussions</a> ·
    <a href="https://discord.gg/YzqtJgHkgH">Discord</a>
  </p>

  <p>
    <a href="https://github.com/KamalTD/Vibrante-Node/releases/latest">
      <img src="https://img.shields.io/github/v/release/KamalTD/Vibrante-Node?style=flat-square&label=release&color=5c6bc0" alt="Latest Release">
    </a>
    <a href="https://www.python.org/downloads/">
      <img src="https://img.shields.io/badge/python-3.10%2B-3776ab?style=flat-square" alt="Python 3.10+">
    </a>
    <a href="LICENSE">
      <img src="https://img.shields.io/github/license/KamalTD/Vibrante-Node?style=flat-square&color=43a047" alt="License">
    </a>
    <a href="https://github.com/KamalTD/Vibrante-Node/releases">
      <img src="https://img.shields.io/github/downloads/KamalTD/Vibrante-Node/total?style=flat-square&color=0288d1" alt="Downloads">
    </a>
    <a href="https://github.com/KamalTD/Vibrante-Node/stargazers">
      <img src="https://img.shields.io/github/stars/KamalTD/Vibrante-Node?style=flat-square&color=f9a825" alt="GitHub Stars">
    </a>
    <a href="https://github.com/KamalTD/Vibrante-Node/issues">
      <img src="https://img.shields.io/github/issues/KamalTD/Vibrante-Node?style=flat-square&color=e53935" alt="Open Issues">
    </a>
    <a href="https://github.com/KamalTD/Vibrante-Node/commits/main">
      <img src="https://img.shields.io/github/last-commit/KamalTD/Vibrante-Node?style=flat-square&color=00897b" alt="Last Commit">
    </a>
    <a href="https://vibrante-node.com/docs">
      <img src="https://img.shields.io/badge/docs-online-0288d1?style=flat-square" alt="Documentation">
    </a>
    <a href="https://discord.gg/YzqtJgHkgH">
      <img src="https://img.shields.io/badge/discord-join%20server-5865F2?style=flat-square&logo=discord&logoColor=white" alt="Discord">
    </a>
    <a href="https://www.youtube.com/@Vibrante-Node">
      <img src="https://img.shields.io/badge/youtube-%40Vibrante--Node-FF0000?style=flat-square&logo=youtube&logoColor=white" alt="YouTube">
    </a>
  </p>
</div>

---

## Overview

**Vibrante-Node** is a Python-node-based visual framework for building modular systems through connected nodes and data flows. It provides an intuitive graph interface where complex logic can be constructed visually by linking nodes together.

The project focuses on flexibility, extensibility, and developer productivity, making it suitable for building tools such as visual pipelines, automation workflows, and data-processing graphs. Node-based systems allow complex operations to be organized as interconnected components rather than traditional linear code structures, improving clarity and scalability in large workflows.

---

<details>
<summary><strong>Screenshots</strong></summary>
<br>

![Vibrante-Node — Canvas](shots/04.PNG)
![Vibrante-Node — Workflow](shots/05.PNG)
![Vibrante-Node — Node Builder](shots/06.PNG)
![Vibrante-Node — Execution](shots/07.PNG)
![Vibrante-Node — Panels](shots/08.PNG)

</details>

---

## Features

### Canvas & Visualization

- **Interactive Canvas** — pan, zoom, and arrange node graphs on a full-featured Qt canvas
- **Live Wire Inspector** — hover any connected wire after execution to see the last value that flowed through it as a tooltip; values persist until the next run
- **Type-Coded Ports** — ports are colored by data type (`int`, `string`, `float`, `bool`, `any`) for instant visual identification
- **Wire Type Coloring** — wires reflect the output port's data type; light theme uses black wires for readability
- **Mini-map** — 200×150 px canvas thumbnail with a viewport indicator rectangle; click or drag to pan (Ctrl+M)
- **Canvas Search** — Ctrl+F opens a floating search bar filtering all nodes by display name or node ID; Enter/Shift+Enter cycles matches
- **Backdrop / Sticky Notes** — annotate and group canvas regions visually

### Execution Engine

- **Async Runtime** — `asyncio`-based `NetworkExecutor` keeps the UI fully responsive during execution
- **Exec Flow Pins** — `exec_in` / `exec_out` pins control execution order explicitly; data-only nodes run in reactive mode
- **Reactive Data Propagation** — changing a node value immediately propagates through all connected downstream nodes before a full run
- **Subgraph / Group Node** — collapse any selection of connected nodes into a `GroupNode`; double-click to open the subgraph in a fully editable tab with real-time sync back to the parent (Ctrl+Shift+G)
- **Bypass Support** — individual nodes can be bypassed; the engine skips them during execution
- **Node Execution Timing** — log panel reports elapsed time for each node (e.g. `Node 'Get Asset' finished in 0.34s`)
- **Init-First Ordering** — `init_priority` ensures authentication or server-connect nodes are fully wired before downstream consumers are instantiated

### Node Library (177+ Bundled Nodes)

| Category | Count | Examples |
|---|---|---|
| Prism Pipeline | 62 | entities, assets, shots, products, USD, configs |
| Maya | 24 | open/save scene, import/export, render, custom Python |
| Blender | 20 | Alembic, FBX, glTF, OBJ, USD, render |
| Houdini (headless) | 17 | open/save HIP, Alembic/FBX import-export, headless executor |
| Network | 1 | `http_request` — async GET/POST with JSON body, headers, timeout |
| Control Flow | — | `if_condition`, `for_loop`, `while_loop`, `loop_body`, `branch` |
| Data Structures | — | `create_list`, `create_dictionary`, `get_dict_value`, `set_dict_value` |
| String Utilities | — | `concat`, `split`, `replace`, `lowercase`, `uppercase` |
| Math & Logic | — | `add`, `compare`, `math_abs`, `logic_and` |
| File System | — | `file_reader`, `append_file`, `create_folder`, `list_images_recursive` |

### Developer Experience

- **Node Builder** — GUI editor: port tables, type dropdowns, automatic Python class generation, bi-directional code sync
- **Hot Reload** — edit any node's JSON definition, press Ctrl+R to rebuild live canvas instances without restarting
- **Registry Source Tracking** — `NodeRegistry.get_source_path()` / `reload_node_definition()` for programmatic node management
- **Python Script Node** — inline QScintilla code editor; scripts are persisted inside the workflow JSON
- **QScintilla Editor** — syntax-highlighted Python editor with autocomplete in Node Builder, Script Editor, and Scripting Console; graceful fallback to `QPlainTextEdit` when QScintilla is not installed
- **Scripting Console** — full API access for programmatic graph manipulation at runtime

### Persistence & Session Management

- **JSON Serialization** — workflows and node definitions are portable `.json` files; no binary formats or databases
- **Autosave & Crash Recovery** — all open tabs are autosaved every 2 minutes to `~/.vibrante_node_autosave.json`; a restore dialog appears on next launch after a crash
- **Unsaved-Changes Detection** — dirty tabs are marked with `*`; closing prompts Save / Discard / Cancel per tab
- **Recent Files** — File → Open Recent lists the last 10 saved or loaded workflows
- **Settings Persistence** — theme, window geometry, and dock layout persist between sessions

### Settings & Environment

- **Preferences Dialog** — Edit → Preferences (Ctrl+,): four pages — Python Runtime, Application Paths, Environment Variables, Vibrante Variables (read-only diagnostics)
- **EnvManager** — centralized singleton managing `VIBRANTE_PYTHONPATH`, `v_nodes_dir`, `v_scripts_path`, and custom `os.environ` pairs; applies changes immediately on OK with no restart required
- **Import / Export Settings** — save your full configuration profile to a portable JSON file; restore it on any machine
- **Qt5 / Qt6 Compatibility** — `qt_compat.py` ensures the app runs under both PyQt5 and PyQt6 without branching in node code

---

## Installation

### Requirements

| Dependency | Version | Notes |
|---|---|---|
| Python | 3.10+ | Required |
| PyQt5 | latest | Required |
| pydantic | latest | Required |
| toposort | latest | Required |
| QScintilla | latest | Optional — full code editor |

### From Source

```bash
git clone https://github.com/KamalTD/Vibrante-Node.git
cd Vibrante-Node
pip install -r requirements.txt
python src/main.py
```

### Windows Executable

Pre-built Windows executables are available on the [Releases](https://github.com/KamalTD/Vibrante-Node/releases) page. No Python installation required. The `.exe` embeds a Windows `VERSIONINFO` resource so Properties → Details shows publisher metadata correctly.

### Linux

Three installation methods are available for Linux (Ubuntu, Rocky Linux, Fedora, Debian, and more). See **[linux/README.md](linux/README.md)** for full instructions and troubleshooting.

**pip (recommended — works on any distro with Python 3.10+):**

```bash
pip install vibrante-node
vibrante-node
```

**AppImage (no Python required — single self-contained file):**

```bash
chmod +x Vibrante-Node-2.3.0-x86_64.AppImage
./Vibrante-Node-2.3.0-x86_64.AppImage
```

**Ubuntu/Debian .deb package:**

```bash
sudo dpkg -i vibrante-node_2.3.0_amd64.deb
vibrante-node
```

> **Wayland note:** PyQt5's Wayland backend is fragile on some distros. If the app fails to start, run with `QT_QPA_PLATFORM=xcb vibrante-node`.

---

## Quick Start

**1. Install**

```bash
git clone https://github.com/KamalTD/Vibrante-Node.git
cd Vibrante-Node
pip install -r requirements.txt
```

**2. Launch**

```bash
python src/main.py
```

**3. Open an example workflow**

Use **File → Load Workflow** and select any `.json` file from the `workflows/` directory. For VFX pipeline examples, open a file from `vfx_workflows/`.

**4. Run the graph**

Press **F5** to execute. Watch the log panel for per-node output and timing. Hover any wire to inspect the value that flowed through it.

**5. Create a custom node**

Open **Nodes → Node Builder**, define your ports and Python logic, and click Save. The node appears in the library immediately. Or drop a `.json` definition into `nodes/` and press **Ctrl+Shift+R** to reload the full registry.

---

## Project Layout

```
Vibrante-Node/
├── src/
│   ├── core/               # Execution engine, NodeRegistry, graph models
│   ├── ui/
│   │   ├── canvas/         # NodeScene, NodeView, MiniMap, CanvasSearchBar
│   │   ├── node_widget.py  # Node rendering and reactive propagation
│   │   ├── node_builder.py # GUI node authoring tool
│   │   └── window.py       # MainWindow, menus, toolbar, dock layout
│   ├── nodes/
│   │   └── builtins/       # Built-in node implementations (GroupNode, etc.)
│   ├── utils/
│   │   ├── hou_bridge.py   # Houdini TCP/JSON-RPC client
│   │   ├── prism_core.py   # PrismCore singleton and auto-bootstrap
│   │   ├── env_manager.py  # Environment variable and path management
│   │   └── qt_compat.py    # Qt5/Qt6 compatibility layer
│   └── main.py             # Application entry point
│
├── nodes/                  # 177+ bundled node definitions
│   ├── prism_*/            # 62 Prism Pipeline nodes
│   ├── maya_*/             # 24 Maya headless action nodes
│   ├── blender_*/          # 20 Blender headless action nodes
│   └── houdini_*/          # 17 Houdini headless action nodes
│
├── plugins/
│   └── houdini/            # Houdini integration plugin (package, server, shelf, menu)
│
├── examples/
│   ├── automation/         # Python scripts that automate Vibrante-Node via the Scripting Console API
│   └── nodes/              # Custom node Python source examples
│
├── node_examples/          # Reference node JSON definitions (install via Nodes → Load Node From JSON)
├── workflows/              # General-purpose workflow JSON files (loops, data flow, control flow)
├── vfx_workflows/          # Production VFX pipeline workflows (Prism, Maya, Houdini, Blender, Deadline)
├── website_examples/       # Polished showcase workflows used on vibrante-node.com
│
├── docs/                   # Generated HTML documentation
├── docs_src/               # Markdown source for documentation
└── tests/                  # pytest unit and integration tests (142 tests)
```

### Example Directory Reference

| Directory | Purpose |
|---|---|
| `examples/automation/` | Python scripts driving the canvas programmatically — batch processing, scene summaries, stress tests |
| `examples/nodes/` | Python class source files for custom nodes — useful as reference when writing your own |
| `node_examples/` | Ready-to-install node JSON definitions — loops, conditions, file ops, reactive configs |
| `workflows/` | General workflow JSON files — control flow, data structures, loop patterns, Maya/Prism demos |
| `vfx_workflows/` | Production-oriented pipeline workflows — multi-shot Alembic export, Deadline submission, Houdini FX, Blender multi-format export |
| `website_examples/` | Curated showcase workflows — HTTP requests, regex, image resizing, LLM generation, database queries, Prism publishing |

---

## Architecture

Vibrante-Node is built in three primary layers.

**Execution Engine** (`src/core/`)  
`NetworkExecutor` resolves a topological execution order from the node graph, then drives each node's `execute()` coroutine via `asyncio`. Exec flow pins impose explicit sequencing; data-only nodes operate reactively. The engine emits typed Qt signals (`node_started`, `node_finished`, `node_error`, `node_output`) that the UI consumes without blocking the execution thread. Subgraph execution recurses into `GroupNode` instances, forwarding log output to the parent panel and routing `exec_fail` only on unhandled exceptions.

**Node Runtime** (`src/nodes/`)  
Each node is a Python class inheriting `BaseNode` and bundled with its port definitions in a `.json` file. `NodeRegistry` loads definitions, compiles the embedded Python source, and instantiates classes on demand. Hot-reload (`Ctrl+R`) recompiles the class and rebinds live canvas instances. The `_source_paths` map tracks where each definition lives on disk, enabling programmatic reload via `reload_node_definition(node_id)`.

**Qt Frontend** (`src/ui/`)  
The canvas is a `QGraphicsScene` / `QGraphicsView` pair. Node widgets, port items, and edge items are all `QGraphicsItem` subclasses. A `_MainThreadDispatcher(QObject)` with a `Qt.QueuedConnection` signal ensures reactive propagation and log output are always delivered on the Qt main thread — required because nodes execute on the `asyncio` background thread.

---

## Integrations

### Houdini

A full Houdini plugin ships in `plugins/houdini/`. It starts a JSON-RPC server (`vibrante_hou_server.py`) inside a live Houdini session; the `HouBridge` client communicates over a local TCP socket with `TCP_NODELAY` and a 30-second timeout. Includes automatic reconnect, per-call thread locking, and graceful degradation in headless Houdini (hbatch/hython).

**Capabilities:** create/delete nodes, get/set parameters, connect nodes, cook geometry, run arbitrary Houdini Python (`run_code`), set expressions and keyframes, set display/render flags, scene info, SOP chain construction.

**Setup:** configure `VIBRANTE_NODE_APP` and optionally `VIBRANTE_PYTHON_EXE` in `plugins/houdini/vibrante_node.json`, then install the package in Houdini. Launch from the Vibrante-Node shelf or menu.

### Maya

Maya integration uses a headless action-list pattern. `maya_action_*` nodes append operation dictionaries to a list; a `maya_headless` node executes the full list in a batch Maya session. No live Maya connection is required.

**Supported:** open/save scene, import/export (Alembic, FBX), render, set frame range, MEL/Python execution, node creation and modification, scene info.

### Blender

Same pattern as Maya. `blender_action_*` nodes build an action list; `blender_headless` runs it in a background Blender process.

**Supported formats:** Alembic, FBX, glTF, OBJ, USD. Render output, scene info, frame range.

### Prism Pipeline

62 nodes covering the full Prism v2 API. `PrismCore` is initialized automatically before graph execution — place a `prism_core_init` node anywhere in the graph; no wiring required. All `prism_*` nodes resolve the shared instance from a global cache.

**Coverage:** projects, entities, assets, shots, products, versions, USD workflows, media, export paths, department configs.

### Deadline

`vfx_workflows/04_deadline_render_pipeline.json` demonstrates render farm submission integrated into a full pipeline workflow alongside Prism asset management.

---

## Custom Node SDK

Every node is a Python class paired with a JSON definition. The class inherits `BaseNode`, declares ports in `__init__`, and implements an `async execute(inputs)` coroutine.

```python
from src.nodes.base import BaseNode

class My_Node(BaseNode):
    name = "my_node"          # must match node_id in the JSON definition

    def __init__(self):
        super().__init__()    # adds exec_in and exec_out automatically
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("text",   "string", widget_type="text",  default="hello")
        self.add_input("repeat", "int",    widget_type="int",   default=1)
        self.add_output("result", "string")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        text   = inputs.get("text", "")
        n      = int(inputs.get("repeat", 1))
        return {
            "result":   (text + " ") * n,
            "exec_out": True,
        }

def register_node():
    return My_Node
```

**Port types:**

| Type | Widget | Notes |
|---|---|---|
| `string` | `"text"` | text input widget |
| `int` | `"int"` | integer spinbox |
| `float` | `"float"` | float spinbox |
| `bool` | `"checkbox"` | checkbox toggle |
| `list` | `null` | Python list — no widget |
| `any` | `null` | exec flow or generic data |

**`execute()` contract:** always return a dict whose keys match your output port names. Include `"exec_out": True` for exec-flow nodes. Any unhandled exception routes to `exec_fail` on `GroupNode` parents.

**Distribution:** ship the `.json` definition (with `python_code` embedded as a string). Users install it via **Nodes → Load Node From JSON** — no package manager or restart required.

For the complete authoring reference, including Houdini bridge usage, headless action patterns, and Prism integration, see [NODE_BUILDER_API.md](NODE_BUILDER_API.md) and [CLAUDE.md](CLAUDE.md).

---

## Documentation

| Resource | Description |
|---|---|
| [User Guide](USER_GUIDE.md) | Interface, canvas, execution, keyboard shortcuts |
| [Node Builder API](NODE_BUILDER_API.md) | Creating and distributing custom nodes |
| [Automation & Scripting API](AUTOMATION_API.md) | Scripting Console and programmatic graph control |
| [Developer Guide](DEVELOPER.md) | Architecture, engine internals, data flow |
| [Technical Reference](DOCUMENTATION.md) | Complete feature and API reference |
| [Portal Docs](docs/portal/) | Full HTML documentation portal |
| [Changelog](CHANGELOG.md) | Version history and migration notes |

**Release Notes:**

| Version | Type | Highlights |
|---|---|---|
| [v2.3.0](RELEASE_v2.3.0.md) | Minor | HTTP Request node; Authenticode signing tools; Node Builder fixes; canvas drag-trail fix |
| [v2.2.1](RELEASE_v2.2.1.md) | Patch | About dialog crash fix; LICENSE bundled in exe |
| [v2.2.0](RELEASE_v2.2.0.md) | Minor | Settings dialog; EnvManager; reactive propagation fix; 10 new website examples |
| [v2.1.1](RELEASE_v2.1.1.md) | Patch | Scripting Console theme fix; Windows VERSIONINFO in exe |
| [v2.1.0](RELEASE_v2.1.0.md) | Minor | Unsaved-changes detection; type-mismatch warning; F5 shortcut fix |
| [v2.0.0](RELEASE_v2.0.0.md) | Major | GroupNode; mini-map; canvas search; autosave; wire inspector; execution timing |
| [v1.8.x](releases/) | — | QScintilla editor; hot-reload; init-first ordering; Houdini bridge hardening |

---

## Latest Release — v2.3.0

**Released:** 2026-05-18 · [Full Release Notes](RELEASE_v2.3.0.md)

**v2.3.0 — Minor**
- New bundled **HTTP Request** node — async GET/POST with headers, body, and timeout; uses `run_in_executor` so the UI stays responsive during network calls
- Authenticode signing scripts (`tools/create_dev_cert.ps1`, `tools/sign_release.ps1`) — remove "Unknown publisher" warning from Windows security dialogs
- Fixed canvas drag trail — `NodeWidget.boundingRect()` now covers port connectors; `shape()` overridden for correct hit-testing
- Fixed http_request UI freeze — moved HTTP execution entirely to thread pool via `loop.run_in_executor`
- Fixed Node Builder: exec port type corruption, default-value loss, and icon-path field triggering full code regeneration
- Fixed Load Node From JSON / Load Workflow cross-file-type detection — each dialog now rejects the other's file type with a clear error message

**v2.2.1 — Patch (included in this release)**
- Fixed About dialog crash (`QTextEdit` → `QTextBrowser`)
- Fixed LICENSE file not shown in exe About dialog

---

## Contributing

Contributions are welcome. The project is under active development; new integrations, nodes, and runtime improvements are ongoing priorities.

1. Fork the repository and create a feature branch from `main`
2. Run the test suite before submitting: `pytest tests/`
3. Follow the node authoring conventions documented in [CLAUDE.md](CLAUDE.md)
4. Open a pull request with a concise description of the change and motivation

**Bug reports and feature requests:** [GitHub Issues](https://github.com/KamalTD/Vibrante-Node/issues)

**Questions and general discussion:** [GitHub Discussions](https://github.com/KamalTD/Vibrante-Node/discussions)

By contributing you agree to the terms of the [Contributor License Agreement](CLA.md).

---

## License

Vibrante-Node uses an open-core hybrid licensing model.

| Component | License |
|---|---|
| Core Runtime | [AGPLv3](LICENSE) |
| SDK / Public API | [MIT](LICENSE) |
| Documentation & Examples | [CC BY 4.0](LICENSE) |
| Official Plugins & Nodes | [Commercial](COMMERCIAL_LICENSE.md) |
| Enterprise Integrations | [Commercial](COMMERCIAL_LICENSE.md) |

Free for individuals, students, education, and open productions.  
Commercial studio deployment requires a [commercial license](COMMERCIAL_LICENSE.md).

- [LICENSE](LICENSE) — AGPLv3 runtime + MIT SDK + CC BY 4.0 docs
- [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) — Studio, SaaS, and enterprise terms
- [TRADEMARK_POLICY.md](TRADEMARK_POLICY.md) — Vibrante-Node branding guidelines
- [CLA.md](CLA.md) — Contributor License Agreement

Licensing inquiries: [contact@vibrante-node.com](mailto:contact@vibrante-node.com)

---

<div align="center">
  <sub>
    <a href="https://vibrante-node.com">vibrante-node.com</a> ·
    <a href="https://github.com/KamalTD/Vibrante-Node">GitHub</a> ·
    <a href="https://vibrante-node.com/docs">Documentation</a> ·
    <a href="mailto:contact@vibrante-node.com">contact@vibrante-node.com</a>
  </sub>
  <br>
  <sub>© 2024–2026 Mahmoud Kamal (KamalTD). All rights reserved.</sub>
</div>
