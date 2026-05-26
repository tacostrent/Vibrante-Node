<div align="center">
  <img src="icons/vibrante-node-resize_main_logo.png" width="300" alt="Vibrante-Node">

  <h3>Visual Workflow Orchestration Platform</h3>

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

**Vibrante-Node** is a Python node-based visual framework for building modular systems through connected nodes and data flows. It provides an intuitive graph interface where complex logic can be constructed visually by linking nodes together.

The platform focuses on flexibility, extensibility, and developer productivity — making it suitable for visual pipelines, automation workflows, and data-processing graphs across any domain. Node-based systems allow complex operations to be organized as interconnected components rather than traditional linear code structures, improving clarity and scalability in large workflows.

**Core capabilities:**

- **Visual canvas** — build workflows by wiring reusable node blocks on a PyQt5 graph canvas; execute via F5, inspect every wire value live
- **Extensible node system** — drop a `.json` file into `nodes/` and it is registered instantly; no recompile, no plugin manifest
- **Multi-DCC integration** — Houdini (live bridge), Maya (headless), Blender (headless), Prism Pipeline, Deadline
- **Automation API** — drive the engine programmatically from scripts, CI/CD jobs, or external tools
- **AI runtime integration (optional)** — connect Claude Desktop, Codex CLI, or Cursor via the built-in MCP server for natural-language orchestration

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

## Installation

### Requirements

| Dependency | Version | Notes |
|---|---|---|
| Python | 3.10+ | Required |
| PyQt5 | latest | Required for UI mode |
| pydantic | latest | Required |
| toposort | latest | Required |
| mcp | ≥ 1.0.0 | Required for MCP server mode |
| QScintilla | latest | Optional — full code editor |

### From Source

```bash
git clone https://github.com/KamalTD/Vibrante-Node.git
cd Vibrante-Node
pip install -r requirements.txt
python src/main.py
```

### Windows Executable

Pre-built Windows executables are available on the [Releases](https://github.com/KamalTD/Vibrante-Node/releases) page. No Python installation required.

### Linux

Three installation methods available. See **[linux/README.md](linux/README.md)** for full instructions.

**pip (recommended):**

```bash
pip install vibrante-node
vibrante-node
```

**AppImage (self-contained, no Python required):**

```bash
chmod +x Vibrante-Node-2.4.0-x86_64.AppImage
./Vibrante-Node-2.4.0-x86_64.AppImage
```

**Ubuntu/Debian .deb:**

```bash
sudo dpkg -i vibrante-node_2.4.0_amd64.deb
vibrante-node
```

> **Wayland note:** If the app fails to start, run with `QT_QPA_PLATFORM=xcb vibrante-node`.

---

## Quick Start — Visual Mode

```bash
git clone https://github.com/KamalTD/Vibrante-Node.git
cd Vibrante-Node
pip install -r requirements.txt
python src/main.py
```

1. Press **F5** to execute the active workflow.
2. Hover any wire to inspect the last value that flowed through it.
3. Open **File → Load Workflow** and pick any `.json` from `workflows/` to explore prebuilt pipelines.
4. Press **Ctrl+Shift+G** on any selected group of nodes to collapse them into a reusable Subgraph — the foundation of composable workflow design.
4. Open **Nodes → Node Builder** to create a custom node with a GUI editor.

---

## Features

### Canvas & Visualization

- **Interactive Canvas** — pan, zoom, and arrange node graphs on a full-featured Qt canvas
- **Live Wire Inspector** — hover any connected wire after execution to see the last value that flowed through it
- **Type-Coded Ports** — ports are colored by data type for instant visual identification
- **Mini-map** — 200×150 px canvas thumbnail with viewport indicator (Ctrl+M)
- **Canvas Search** — Ctrl+F filters all nodes by name or node ID; Enter/Shift+Enter cycles matches
- **Backdrop / Sticky Notes** — annotate and group canvas regions visually

### Execution Engine

- **Async Runtime** — `asyncio`-based `NetworkExecutor` keeps the UI fully responsive during execution
- **Exec Flow Pins** — `exec_in` / `exec_out` pins control execution order explicitly
- **Reactive Data Propagation** — changing a node value immediately propagates to all connected downstream nodes
- **Subgraph / Group Node** — collapse any selection into a `GroupNode`; double-click to open and edit (Ctrl+Shift+G)
- **Node Execution Timing** — log panel reports elapsed time for each node

### Node Library (200+ Bundled Nodes)

| Category | Count | Examples |
|---|---|---|
| Prism Pipeline | 62 | entities, assets, shots, products, USD, configs |
| Maya | 24 | open/save scene, import/export, render, custom Python |
| Blender | 20 | Alembic, FBX, glTF, OBJ, USD, render |
| Houdini (headless) | 17 | open/save HIP, Alembic/FBX import-export, headless executor |
| Houdini AI (MCP) | 23 | scene context, AI planning, transaction, diff, graph builder |
| Generic MCP | 3 | `mcp_server_init`, `mcp_list_tools`, `mcp_call_tool` |
| Network | 1 | `http_request` — async GET/POST with headers, timeout |
| Control Flow | — | `if_condition`, `for_loop`, `while_loop`, `branch` |
| Data Structures | — | `create_list`, `create_dictionary`, `get_dict_value` |
| String Utilities | — | `string_concat`, `string_split`, `string_lowercase` |
| Math & Logic | — | `math_add`, `compare`, `math_abs`, `logic_and` |
| File System | — | `file_reader`, `append_file`, `create_folder` |

### Developer Experience

- **Node Builder** — GUI editor: port tables, type dropdowns, automatic Python class generation, bi-directional code sync
- **Hot Reload** — Ctrl+R rebuilds live canvas instances without restarting
- **Python Script Node** — inline QScintilla code editor; scripts persisted inside the workflow JSON
- **Scripting Console** — full API access for programmatic graph manipulation at runtime

### AI Orchestration Runtime *(Advanced, v2.4.0)*

- **MCP Server Mode** — run `scripts/run_vibrante_mcp.py`; Claude Desktop, Codex CLI, and Cursor connect via stdio and receive 12 tools for scene inspection, planning, validation, and execution
- **Safe Transactional Mutations** — all operations are validated, recorded, and reversible; high-risk plans require explicit approval before execution
- **AI Planning Pipeline** — natural language → plan → preview → approved execution; no arbitrary scene mutation
- **26 New Nodes** — 3 generic MCP client nodes + 23 Houdini AI nodes (`hou_mcp_scene_context`, `hou_mcp_transaction`, `hou_mcp_ai_plan`, `hou_mcp_ai_execute`, and more)

---

## Execution Modes

### Mode 1 — Visual Workflow Authoring

Open the canvas, drag nodes from the Library panel, connect them, and press **F5**. Data flows left-to-right through typed data pins; execution order is controlled by exec pins (the white square connectors). Every wire is inspectable after a run — hover to see the last value.

```
[Source Node] ──data──→ [Transform Node] ──data──→ [Output Node]
  exec_out ─────────────→  exec_out ─────────────→  exec_out
```

> **Build Once → Reuse Everywhere:** group any sub-workflow into a named Subgraph (Ctrl+Shift+G). Subgraphs appear as a single reusable node — duplicate, share, or nest them across projects. Workflow files are plain JSON: diff-friendly and version-control-ready.

Suited for: general automation pipelines, file processing, data transformation, DCC scene setup, Prism Pipeline integration, Deadline submission, API orchestration, and any multi-step task you want to build visually and iterate on interactively.

Workflows scale naturally — a small 3-node graph and a 50-node production pipeline use the same execution model. Group nodes let you collapse subsystems into reusable components, keeping large graphs readable without losing any functionality.

### Mode 2 — Direct AI Orchestration *(Advanced)*

Run `scripts/run_vibrante_mcp.py` to start a headless MCP server. Claude Desktop, Codex CLI, and Cursor connect via stdio and receive 12 semantic tools covering scene inspection, planning, validation, and transactional Houdini execution — no visual canvas required. See [AI Runtime & MCP Integration](#ai-runtime--mcp-integration-advanced) for setup instructions.

---

## Project Layout

```
Vibrante-Node/
├── src/
│   ├── core/               # Execution engine, GraphManager, NodeRegistry, WorkflowModel
│   │   ├── executor.py     # NetworkExecutor — asyncio coroutine orchestration
│   │   ├── graph.py        # GraphManager — DAG, topological sort, cycle detection
│   │   ├── registry.py     # NodeRegistry — auto-discovery, hot-reload
│   │   └── models.py       # WorkflowModel, PortModel, NodeInstanceModel (Pydantic)
│   ├── ui/                 # Qt frontend — canvas, panels, dialogs
│   │   ├── canvas/         # NodeScene, NodeView, MiniMap, CanvasSearchBar
│   │   ├── node_widget.py  # Node rendering and reactive propagation
│   │   ├── node_builder.py # GUI node authoring tool
│   │   └── window.py       # MainWindow, menus, toolbar, dock layout
│   ├── nodes/
│   │   └── builtins/       # Built-in node implementations (GroupNode, loops, variables)
│   ├── utils/              # Integrations and shared utilities
│   │   ├── hou_bridge.py   # Houdini TCP/JSON-RPC client (port 18811)
│   │   ├── prism_core.py   # PrismCore singleton and auto-bootstrap
│   │   ├── env_manager.py  # Environment variable and path management
│   │   └── qt_compat.py    # Qt5/Qt6 compatibility layer
│   ├── runtime/            # Advanced runtime extensions (Tiers 1–6, optional)
│   │   └── ...             # MCP server, AI planning, transactions, analytics (40+ modules)
│   └── main.py             # Application entry point (UI mode)
│
├── nodes/                  # 200+ bundled node definitions (JSON + Python)
├── plugins/                # DCC plugins — houdini/, maya/, blender/
│   └── houdini/
│       ├── v_nodes_houdini/          # Houdini-specific nodes (bridge + AI runtime)
│       └── houdini/scripts/python/   # In-Houdini server + launch scripts
├── scripts/
│   └── run_vibrante_mcp.py           # Headless MCP server entry point (advanced)
│
├── workflows/              # General-purpose workflow JSON files
├── vfx_workflows/          # Production VFX pipeline workflows
├── examples/               # Automation scripts and custom node examples
├── docs/                   # Generated HTML documentation
├── docs_src/               # Markdown source for documentation
└── tests/                  # pytest unit and integration tests
```

---

## Architecture

Vibrante-Node is a layered execution platform. The workflow graph drives the execution engine, which runs nodes, which call integrations. The advanced runtime layer is an optional extension used by `hou_mcp_*` and MCP client nodes.

```
┌─────────────────────────────────────────────────────────────┐
│  Visual Canvas  (src/ui/)                                    │
│  Qt canvas · panels · node widgets · workflow authoring      │
├─────────────────────────────────────────────────────────────┤
│  Execution Engine  (src/core/)                               │
│  WorkflowModel → GraphManager (DAG) → NetworkExecutor        │
│  asyncio coroutines · topological order · GroupNode recursion│
├─────────────────────────────────────────────────────────────┤
│  Node Library  (src/nodes/ + plugins/)                       │
│  200+ nodes: General · Houdini · Maya · Blender · Prism · MCP│
├─────────────────────────────────────────────────────────────┤
│  Utils & Integrations  (src/utils/)                          │
│  HouBridge (TCP) · PrismCore · EnvManager · qt_compat        │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤
│  Advanced Runtime Extensions  (src/runtime/)  ← optional    │
│  MCP server · AI planning · transactions · analytics         │
│  40+ modules across Tiers 1–6; no Qt dependency             │
└─────────────────────────────────────────────────────────────┘
```

**Execution Engine** (`src/core/`) resolves a topological execution order from the node graph, drives each node's `async def execute()` via `asyncio`, and emits Qt signals for live wire inspection and log output. `GroupNode` execution recurses into embedded sub-workflows.

**Node Library** (`src/nodes/`) manages node definitions (JSON + compiled Python), the `NodeRegistry` (auto-discovery, hot-reload), and the `BaseNode` contract. Adding a node requires exactly one `.json` file — drop it in `nodes/` and it registers automatically.

**Visual Canvas** (`src/ui/`) is a `QGraphicsScene`/`QGraphicsView` pair with thread-safe reactive propagation, mini-map, canvas search, live wire inspector, and the Node Builder authoring tool.

**Advanced Runtime Extensions** (`src/runtime/`) is an optional standalone Python module — MCP server, AI planning, transaction management, validation, and analytics (Tiers 1–6). It has no Qt dependency and can run headlessly. Used by `hou_mcp_*` nodes and the `scripts/run_vibrante_mcp.py` entry point.

---

## Integrations

### Houdini

A full Houdini plugin ships in `plugins/houdini/`. It starts a JSON-RPC server (`vibrante_hou_server.py`) inside a live Houdini session. The `HouBridge` client communicates over TCP with `TCP_NODELAY` and 30-second timeout, automatic reconnect, and per-call thread locking.

**v2.4.0 additions:** `get_selection()` (selected node paths), `network_summary(path)` (children with type+category in one round-trip).

**Setup:** configure `VIBRANTE_NODE_APP` in `plugins/houdini/vibrante_node.json`, install the package in Houdini, then launch from the Vibrante-Node shelf or menu.

### Maya

`maya_action_*` nodes append operation dictionaries to a list; a `maya_headless` node executes the full list in a batch Maya session. Supports open/save, import/export (Alembic, FBX), render, MEL/Python, node creation.

### Blender

Same action-list pattern as Maya. `blender_action_*` nodes + `blender_headless` executor. Supports Alembic, FBX, glTF, OBJ, USD, render.

### Prism Pipeline

62 nodes covering the full Prism v2 API. `PrismCore` bootstraps automatically before graph execution — place a `prism_core_init` node anywhere in the graph; no wiring required.

### Deadline

`vfx_workflows/04_deadline_render_pipeline.json` demonstrates render farm submission integrated with Prism asset management.

---

## AI Runtime & MCP Integration *(Advanced)*

Vibrante-Node can run as a headless MCP server, letting Claude Desktop, Codex CLI, and Cursor plan, validate, and execute Houdini operations through 12 structured tools. No Qt or display server required.

**Start the MCP server:**

```bash
pip install "mcp>=1.0.0" pydantic toposort
python scripts/run_vibrante_mcp.py
```

**Configure Claude Desktop** (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "vibrante": {
      "command": "python",
      "args": ["/path/to/Vibrante-Node/scripts/run_vibrante_mcp.py"],
      "env": { "VIBRANTE_HOU_PORT": "18811" }
    }
  }
}
```

The server exposes 12 semantic tools across four categories — Runtime, Knowledge, Planning, and Execution. Planning and knowledge tools work without Houdini; only `execute_workflow_transaction` touches the scene, and only after validation passes. All 40+ runtime modules run headlessly without Qt — CI/CD pipelines can import `src.runtime` directly.

For the full tool reference, Codex CLI / Cursor configuration, and safety model, see [Getting Started § 11](docs_src/02_getting_started.md#11-direct-runtime-orchestration--mcp-quick-start-advanced).

---

## End-to-End Examples

### General Automation — File Processing

A simple workflow that requires no integrations. Runs on any machine.

```
file_reader          ── read source file
    ↓
python_script        ── parse and transform data
    ↓
if_condition         ── check record_count > 0
    ↓ (true)              ↓ (false)
append_file          console_print "no records"
    ↓
console_print        ── "report saved"
```

Load `workflows/file_processing_example.json` and press F5.

### Multi-DCC Pipeline — Prism + Houdini

```
prism_core_init         ── initialise project management
    ↓
prism_get_assets        ── list assets for the current shot
    ↓
for_loop                ── iterate each asset
    ↓
hou_create_geo          ── build geo container in /obj
    ↓
hou_import_alembic      ── import Alembic cache
    ↓
console_print           ── log result per asset
```

### VFX — AI-Assisted Houdini Setup *(Advanced)*

Uses the AI planning pipeline inside the visual canvas.

```
prism_core_init
    ↓
hou_mcp_scene_context       ── read current Houdini state
    ↓
hou_mcp_ai_plan             ── "build a cinematic pyro explosion at /obj/geo1"
    ↓
hou_mcp_ai_preview          ── validate risk, check dependencies
    ↓
if_condition                ── check risk_level == "low"
    ↓ (true)
hou_mcp_ai_execute          ── execute with approver="td_lead"
    ↓
hou_mcp_ai_review           ── verify intent matched execution
    ↓
console_print               ── log outcome
```

### Claude Direct Session *(Advanced)*

Without the visual canvas — Claude Desktop connected to the MCP server.

```
initialize_runtime_context      ── bootstrap and get system prompt
    ↓
query_scene_context             ── read current Houdini scene state
    ↓
plan_scene("build a pyro sim")  ── natural language → validated plan
    ↓
preview_execution(operations)   ── validate risk before touching the scene
    ↓
execute_workflow_transaction    ── commit; auto-rollback on failure
    ↓
review_execution(plan, result)  ── verify intent matched execution
```

---

## Custom Node SDK

Every node is a Python class paired with a JSON definition. The class inherits `BaseNode` and implements an `async execute(inputs)` coroutine.

```python
from src.nodes.base import BaseNode

class My_Node(BaseNode):
    name = "my_node"

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

For the complete authoring reference, including Houdini bridge usage, headless action patterns, and Prism integration, see [NODE_BUILDER_API.md](NODE_BUILDER_API.md).

---

## Troubleshooting

**Houdini nodes not appearing in the Library**
```
Ensure v_nodes_dir points to plugins/houdini/v_nodes_houdini/
Set it in Edit → Preferences → Application Paths (requires restart)
```

**AppImage fails to start on Linux**
```bash
QT_QPA_PLATFORM=xcb ./Vibrante-Node-2.4.0-x86_64.AppImage
```

**Node Builder corrupts exec ports on edit**
```
This was fixed in v2.3.0. Update to the latest release.
```

**MCP server won't start** *(Advanced)*
```bash
# Verify mcp is installed
python -c "import mcp; print(mcp.__version__)"
# If missing: pip install "mcp>=1.0.0"
```

**`query_scene_context` returns "bridge not available"** *(Advanced)*
```
1. Open Houdini with the Vibrante-Node plugin installed
2. Click Vibrante-Node → Launch Vibrante-Node from the Houdini menu bar
3. Check VIBRANTE_HOU_PORT matches the port shown in the Houdini Python console
```

**`execute_workflow_transaction` returns `status: "pending_approval"`** *(Advanced)*
```
The plan has requires_approval=True (high risk or delete_node ops).
Pass approver="your_name" to authorize execution.
```

---

## Documentation

| Resource | Description |
|---|---|
| [User Guide](USER_GUIDE.md) | Interface, canvas, execution, keyboard shortcuts |
| [Node Builder API](NODE_BUILDER_API.md) | Creating and distributing custom nodes |
| [Automation & Scripting API](AUTOMATION_API.md) | Scripting Console and programmatic graph control |
| [Developer Guide](DEVELOPER.md) | Architecture, engine internals, runtime layer |
| [Technical Reference](DOCUMENTATION.md) | Complete feature and API reference |
| [Portal Docs](docs/portal/) | Full HTML documentation portal |
| [Changelog](CHANGELOG.md) | Version history and migration notes |

**Release Notes:**

| Version | Type | Highlights |
|---|---|---|
| [v2.4.0](RELEASE_v2.4.0.md) | Minor | 26 new nodes (3 generic MCP client + 23 Houdini AI); runtime extensions layer (Tiers 1–6): MCP server, AI planning, transactions; node ID cleanup; 3 bug fixes |
| [v2.3.0](RELEASE_v2.3.0.md) | Minor | HTTP Request node; Authenticode signing tools; Node Builder fixes; canvas drag-trail fix |
| [v2.2.1](RELEASE_v2.2.1.md) | Patch | About dialog crash fix; LICENSE bundled in exe |
| [v2.2.0](RELEASE_v2.2.0.md) | Minor | Settings dialog; EnvManager; reactive propagation fix; 10 new website examples |
| [v2.1.1](RELEASE_v2.1.1.md) | Patch | Scripting Console theme fix; Windows VERSIONINFO in exe |
| [v2.1.0](RELEASE_v2.1.0.md) | Minor | Unsaved-changes detection; type-mismatch warning; F5 shortcut fix |
| [v2.0.0](RELEASE_v2.0.0.md) | Major | GroupNode; mini-map; canvas search; autosave; wire inspector; execution timing |
| [v1.8.x](releases/) | — | QScintilla editor; hot-reload; init-first ordering; Houdini bridge hardening |

---

## Contributing

Contributions are welcome. The project is under active development; new integrations, nodes, and runtime improvements are ongoing priorities.

1. Fork the repository and create a feature branch from `main`
2. Run the test suite before submitting: `pytest tests/`
3. Follow the node authoring conventions documented in [NODE_BUILDER_API.md](NODE_BUILDER_API.md)
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
