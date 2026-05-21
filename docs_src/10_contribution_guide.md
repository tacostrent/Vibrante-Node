# Contribution Guide

This guide covers everything you need to contribute to Vibrante-Node — from setting up your environment to submitting a pull request. Read it fully before opening your first PR.

---

## 1. Project Philosophy

Vibrante-Node is built on three commitments:

**Extensibility first.** Every subsystem — nodes, the engine, the UI, the bridge integrations — is designed to be extended without modifying core files. New nodes should not require touching `engine.py`. New UI panels should not require editing `window.py` unless adding a menu entry.

**Backward compatibility is sacred.** A workflow saved with Vibrante-Node v1.0.0 must load and run correctly under v2.0.0. The JSON `WorkflowModel` format may gain new optional fields but must never remove or rename existing ones in a breaking way. The `BaseNode` API (especially `execute()` signature, port registration, and the `memory` dict) must remain stable across minor versions.

**No breaking changes without a major version bump.** If a change would break existing nodes, existing workflows, or existing user scripts that import from `src`, it requires a major version increment and a migration guide. Prefer additive changes: add new methods rather than changing existing signatures, add new optional parameters rather than reordering existing ones.

---

## 2. Repository Structure

```
node_based_app/
├── src/                        # Core application source
│   ├── core/
│   │   ├── engine.py           # Async execution engine (NetworkExecutor)
│   │   ├── graph.py            # GraphManager: build dependency graph from WorkflowModel
│   │   ├── models.py           # Pydantic models: WorkflowModel, NodeInstanceModel, etc.
│   │   └── registry.py         # NodeRegistry: load, register, look up node classes
│   ├── nodes/
│   │   ├── base.py             # BaseNode: the base class all nodes inherit
│   │   └── builtins/           # Built-in Python node classes (group_node.py, etc.)
│   └── ui/
│       ├── window.py           # MainWindow: the application shell
│       ├── canvas/
│       │   ├── scene.py        # NodeScene (QGraphicsScene subclass)
│       │   ├── view.py         # NodeView (QGraphicsView subclass)
│       │   ├── node_widget.py  # NodeWidget: visual representation of a node
│       │   ├── edge.py         # Edge: wire between ports
│       │   ├── port_widget.py  # PortWidget: individual port circle
│       │   ├── mini_map.py     # MiniMap overlay
│       │   └── canvas_search_bar.py  # Ctrl+F search overlay
│       ├── panels/
│       │   ├── library_panel.py       # Node library browser
│       │   └── log_panel.py           # Execution log
│       ├── dialogs/
│       │   ├── node_builder_dialog.py # Node Builder UI
│       │   └── script_editor_dialog.py
│       └── code_editor.py      # QScintilla-based Python editor (with fallback)
├── src/utils/
│   ├── hou_bridge.py           # HouBridge TCP client
│   ├── prism_core.py           # PrismCore resolver
│   ├── config_manager.py       # App settings, recent files
│   └── qt_compat.py            # PyQt5/PyQt6 compatibility shim
├── nodes/                      # JSON node definitions (user-visible)
├── plugins/
│   ├── houdini/                # Houdini plugin package
│   │   ├── vibrante_node.json  # Houdini package file
│   │   ├── v_nodes_houdini/    # Houdini-specific JSON nodes
│   │   ├── v_scripts_houdini/  # Scripts menu .py files
│   │   └── houdini/            # Added to HOUDINI_PATH
│   └── maya/                   # Maya headless plugin
├── tests/                      # pytest test suite
│   ├── unit/                   # Unit tests for individual nodes and utilities
│   ├── integration/            # Multi-node workflow tests
│   └── ui/                     # pytest-qt UI tests
├── docs_src/                   # Documentation source (Markdown)
├── examples/                   # Example workflows (.json files)
├── icons/                      # SVG/PNG icons for nodes
├── requirements.txt
├── pytest.ini
└── CLAUDE.md                   # AI developer guide (machine-readable)
```

---

## 3. Setting Up a Development Environment

### Prerequisites

- Python 3.10 or 3.11 (3.11 recommended)
- Git
- A virtual environment tool (`venv` is fine)

### Steps

```bash
# Clone the repository
git clone https://github.com/your-org/vibrante-node.git
cd vibrante-node/node_based_app

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Optional: install QScintilla for the full code editor
pip install QScintilla

# Run the application
python -m src.main

# Run the test suite
pytest
```

### requirements.txt Key Dependencies

| Package | Purpose |
|---------|---------|
| `PyQt5` | UI framework |
| `pydantic>=2.0` | Data models and validation |
| `urllib.request` | HTTP (stdlib, no install required) |
| `Pillow` | PIL image processing node |
| `pytest` | Test runner |
| `pytest-qt` | Qt widget testing |
| `pytest-asyncio` | Async test support |

### IDE Configuration

If using VS Code, add to `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": ".venv/Scripts/python.exe",
    "python.analysis.extraPaths": ["${workspaceFolder}"]
}
```

This ensures `from src.core.engine import NetworkExecutor` resolves correctly.

---

## 4. Coding Standards

### Python Style

- Follow PEP 8. Line length limit: 100 characters.
- Use f-strings for string formatting. Avoid `%`-style or `.format()` where f-strings work.
- One blank line between methods. Two blank lines between top-level classes and functions.
- Imports ordered: stdlib → third-party → local (`src.*`). Separate groups with a blank line.

### Type Hints

Type hints are preferred in all new code, mandatory in `src/core/` and `src/utils/`. Use `from __future__ import annotations` at the top of files with complex forward references.

```python
# Good
def get_node(self, node_id: str) -> BaseNode | None:
    ...

# Acceptable in node python_code (brevity wins there)
def execute(self, inputs):
    ...
```

### Async Patterns

**Never block the event loop inside `execute()`.** Any blocking I/O (file read, network request, subprocess) must be wrapped:

```python
import asyncio

# File I/O
content = await asyncio.to_thread(open(path).read)

# Subprocess
proc = await asyncio.create_subprocess_exec(
    "ffmpeg", "-i", input_path, output_path,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
stdout, stderr = await proc.communicate()
```

- `asyncio.sleep()` is fine for delays.
- `time.sleep()` inside `execute()` is never acceptable — it freezes the UI.
- Long CPU-bound tasks: `await asyncio.to_thread(my_cpu_fn, args)`.

### Error Handling in Nodes

Use `self.log_error()` for recoverable errors. Raise exceptions only for truly unrecoverable states. Always return a valid dict with `exec_out`:

```python
async def execute(self, inputs):
    try:
        result = do_work(inputs)
        return {"output": result, "exec_out": True}
    except Exception as e:
        self.log_error(f"Failed: {e}")
        return {"output": None, "exec_out": True}  # exec continues; downstream handles None
```

### Signal Naming Conventions (UI)

Qt signals in `src/ui/` follow this pattern:

- `noun_past_tense` for completed events: `node_started`, `node_finished`, `node_error`
- `action_request` for user-initiated requests: `save_requested`, `run_requested`
- Never expose `pyqtSignal` objects from non-widget classes.

---

## 5. How to Add a New Built-in Node

Built-in nodes are Python classes in `src/nodes/builtins/`. They are registered in `src/core/registry.py`.

### Step 1: Create the class file

Create `src/nodes/builtins/my_new_node.py`:

```python
from src.nodes.base import BaseNode


class MyNewNode(BaseNode):
    name = "my_new_node"           # Must be unique; used as the node_id

    def __init__(self):
        super().__init__()         # Adds exec_in and exec_out automatically
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("input_value", "string", widget_type="text", default="")
        self.add_output("output_value", "string")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs: dict) -> dict:
        value = inputs.get("input_value", "")
        result = value.strip()   # example transform
        return {
            "output_value": result,
            "exec_out": True,
        }


def register_node():
    return MyNewNode
```

### Step 2: Register in registry.py

Open `src/core/registry.py`. Find the block where other builtins are registered and add:

```python
from src.nodes.builtins.my_new_node import MyNewNode

# In NodeRegistry._register_builtins():
for _cls in (..., MyNewNode):
    _cls.node_id = _cls.name
    cls._classes[_cls.name] = _cls
```

Built-in nodes registered in `_classes` only (not `_definitions`) do not appear in the search popup. To make a node visible in the library, also add it to `_definitions` with a `NodeDefinition` object, or define it as a JSON node instead.

### Step 3: Write a test

See section 9 (Testing) for the test pattern.

---

## 6. How to Add a New JSON Node to `nodes/`

JSON nodes live in `nodes/` (or `plugins/houdini/v_nodes_houdini/` for Houdini-specific nodes). They appear automatically in the Node Library when the app starts.

### File format

Create `nodes/my_node.json`:

```json
{
    "node_id": "my_node",
    "name": "my_node",
    "description": "One sentence description.",
    "category": "Utilities",
    "icon_path": null,
    "use_exec": true,
    "inputs": [
        { "name": "exec_in",   "type": "any",    "widget_type": null, "options": null, "default": null },
        { "name": "value",     "type": "string", "widget_type": "text", "options": null, "default": "" }
    ],
    "outputs": [
        { "name": "result",   "type": "string", "widget_type": null, "options": null, "default": null },
        { "name": "exec_out", "type": "any",    "widget_type": null, "options": null, "default": null }
    ],
    "python_code": "class My_Node(BaseNode):\n    name = \"my_node\"\n\n    def __init__(self):\n        super().__init__()\n        # [AUTO-GENERATED-PORTS-START]\n        self.add_input(\"value\", \"string\", widget_type=\"text\")\n        self.add_output(\"result\", \"string\")\n        # [AUTO-GENERATED-PORTS-END]\n\n    async def execute(self, inputs):\n        v = inputs.get(\"value\", \"\")\n        return {\"result\": v.upper(), \"exec_out\": True}\n\ndef register_node():\n    return My_Node\n"
}
```

### Formatting `python_code`

The `python_code` field is a JSON string. All newlines must be `\n`, all double-quotes must be `\"`. Use the Node Builder dialog (accessible from the app) to build nodes visually and export the JSON — it handles escaping automatically.

### Categories

Use established categories to keep the library organized:

| Category | Use for |
|----------|---------|
| `Utilities` | General-purpose data manipulation |
| `String` | String operations |
| `Math` | Numeric operations |
| `List` | List operations |
| `Dict` | Dictionary operations |
| `File` | File I/O |
| `Control` | Execution flow (loops, switches) |
| `Houdini` | Houdini bridge nodes |
| `Maya` | Maya headless action nodes |
| `Prism` | Prism Pipeline nodes |

### Testing JSON nodes

Load the JSON node through the registry and verify it loads without errors:

```python
from src.core.registry import NodeRegistry

def test_my_node_loads():
    registry = NodeRegistry()
    registry._load_file("nodes/my_node.json")
    cls = registry.get_class("my_node")
    assert cls is not None
    instance = cls()
    assert hasattr(instance, "execute")
```

---

## 7. How to Add a New UI Feature

### Small changes (new action, new dialog trigger)

Most small UI features only require changes to `src/ui/window.py`:

1. Add a menu action in `_init_menu()`.
2. Connect the action to a slot method on `MainWindow`.
3. Implement the slot. Keep slots thin — delegate heavy logic to scene, engine, or a utility function.
4. If the action modifies the scene, call `scene.push_history("Description of change")` so it is undoable.

### Canvas features (new overlay widget)

Canvas overlay widgets (like `MiniMap` and `CanvasSearchBar`) are child widgets of `NodeView`:

1. Create `src/ui/canvas/my_overlay.py` with a `QWidget` or `QFrame` subclass.
2. Instantiate in `NodeView.__init__`: `self._my_overlay = MyOverlay(self)`.
3. Position in `NodeView.resizeEvent` using `self._my_overlay.move(x, y)`.
4. Expose a `show_my_overlay()` method on `NodeView`.
5. Call from `MainWindow` via `view.show_my_overlay()`.
6. Apply theme in `NodeView.apply_theme(is_dark)` → `self._my_overlay.apply_theme(is_dark)`.

### New scene interactions

For features that respond to scene events (new context menu items, drag behaviors):

1. Override the relevant `QGraphicsScene` event method in `NodeScene`.
2. Emit a custom signal if `MainWindow` needs to respond.
3. Never import `MainWindow` from inside `scene.py` — use signals only.

### History push rules

Any action that modifies the workflow must push history:

```python
# Correct: push history after the change
scene.remove_node(widget)
scene.push_history("Delete node")

# Wrong: push history before the change
scene.push_history("Delete node")  # the history snapshot won't have the change
scene.remove_node(widget)
```

---

## 8. How to Add a New Engine Feature

`src/core/engine.py` contains `NetworkExecutor`. Keep changes here minimal and targeted.

### Signal naming

Add new signals at the class level:

```python
class NetworkExecutor(QObject):
    node_started = pyqtSignal(str)          # node instance_id
    node_finished = pyqtSignal(str, dict)   # instance_id, results
    node_error = pyqtSignal(str, str)       # instance_id, error message
    my_new_signal = pyqtSignal(str, object) # follow existing pattern
```

### Execution order

The executor uses a dependency graph (topological sort) to determine execution order. Do not hardcode execution order in new features — always derive from graph connectivity.

### Thread safety

`NetworkExecutor.run()` runs in an `asyncio` event loop on the Qt main thread (via `QEventLoop` integration). Do not spawn threads inside `run()`. Use `asyncio.to_thread()` for blocking I/O.

---

## 9. Testing

### Test infrastructure

```
tests/
├── unit/
│   ├── test_nodes.py           # Per-node execute() tests
│   ├── test_registry.py        # Registry load tests
│   ├── test_models.py          # Pydantic model validation
│   └── test_engine.py          # Execution engine tests
├── integration/
│   └── test_workflows.py       # End-to-end workflow execution
└── ui/
    └── test_canvas.py          # pytest-qt widget tests
```

### Writing a node test

```python
import pytest
import asyncio
from src.nodes.builtins.my_new_node import MyNewNode


def test_my_node_init():
    node = MyNewNode()
    port_names = [p.name for p in node.inputs]
    assert "exec_in" in port_names
    assert "input_value" in port_names


def test_my_node_execute():
    node = MyNewNode()
    result = asyncio.run(node.execute({"input_value": "  hello world  "}))
    assert result["output_value"] == "hello world"
    assert result["exec_out"] is True


def test_my_node_empty_input():
    node = MyNewNode()
    result = asyncio.run(node.execute({}))
    assert result["output_value"] == ""
    assert result["exec_out"] is True
```

### Writing an integration test

```python
import asyncio
import pytest
from src.core.models import WorkflowModel
from src.core.graph import GraphManager
from src.core.engine import NetworkExecutor


def test_two_node_pipeline():
    workflow_dict = {
        "nodes": [...],   # minimal workflow JSON
        "edges": [...]
    }
    workflow = WorkflowModel.model_validate(workflow_dict)
    gm = GraphManager()
    gm.from_model(workflow)
    executor = NetworkExecutor(gm)

    results = {}
    executor.node_finished.connect(lambda nid, r: results.update({nid: r}))

    asyncio.run(executor.run())
    assert len(results) == 2
```

### Writing a UI test

```python
import pytest
from PyQt5.QtCore import Qt
from src.ui.window import MainWindow


@pytest.fixture
def main_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    return window


def test_canvas_search_opens(main_window, qtbot):
    qtbot.keyClick(main_window, Qt.Key_F, Qt.ControlModifier)
    assert main_window._current_view()._canvas_search_bar.isVisible()
```

### Running tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific file
pytest tests/unit/test_nodes.py

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run only UI tests (requires display)
pytest tests/ui/ -v
```

All tests in `tests/unit/` and `tests/integration/` must pass before a PR is merged. UI tests are optional in headless CI environments but must pass locally.

---

## 10. Pull Request Process

### Branch naming

```
feature/short-description       # new feature
fix/short-description           # bug fix
refactor/short-description      # internal refactor (no behavior change)
docs/short-description          # documentation only
```

Always branch from `main`. Never commit directly to `main`.

### Commit messages

Use the imperative mood. Keep the subject line under 72 characters:

```
Add async HTTP request node with JSON parsing

feat: add canvas search bar (Ctrl+F)
fix: prevent duplicate exec_in port when use_exec=True
refactor: extract edge tooltip logic into Edge.set_live_value()
docs: add GroupNode subgraph tutorial
```

Reference issue numbers where applicable: `Fixes #42`.

### What reviewers check

1. **Does it break existing tests?** Run `pytest` and confirm all pass.
2. **Does it break existing workflows?** Load the sample workflows in `examples/` and verify they still run.
3. **Is the API additive?** No removed or renamed public methods or signals.
4. **Is the JSON format backward-compatible?** New fields must be optional with defaults.
5. **No blocking calls in `execute()`?** Check for `time.sleep`, `requests.get`, `open()` without `asyncio.to_thread`.
6. **Are new nodes tested?** At least `test_init` and `test_execute` with normal and edge-case inputs.
7. **Is `CLAUDE.md` updated?** Any new bridge methods, node patterns, or bug fixes that future AI contributors need to know about.

---

## 11. Versioning

Vibrante-Node uses semantic versioning: `MAJOR.MINOR.PATCH`.

| Change type | Version bump |
|-------------|-------------|
| Breaking API change | MAJOR (e.g., 2.x.x → 3.0.0) |
| New feature, backward compatible | MINOR (e.g., 2.0.x → 2.1.0) |
| Bug fix | PATCH (e.g., 2.0.0 → 2.0.1) |

The version string lives in `src/__init__.py`:

```python
__version__ = "2.1.0"
```

Update this, `RELEASE_vX.Y.Z.md`, and `README.md` version badge in the same commit.

---

## 12. Backward Compatibility Rules

### JSON format (WorkflowModel)

- Never remove a field from `WorkflowModel`, `NodeInstanceModel`, or `EdgeModel`.
- New fields must have a default value (`Optional[X] = None` or `list[X] = []`).
- If a field's semantics change, add a new field and deprecate (but keep) the old one for at least one major version.
- The `node_id` of any built-in node must never change. It is embedded in every saved workflow.

### BaseNode API

- `execute(self, inputs: dict) -> dict` signature is frozen.
- `self.memory`, `self.parameters`, `self.log_info()`, `self.log_error()` must remain accessible.
- `add_input()` and `add_output()` parameter order must not change (new optional kwargs are fine).
- `register_node()` convention must remain supported.

### Engine signals

Signal signatures (`node_started`, `node_finished`, `node_error`) must remain stable. Downstream code (`window.py`, tests, user scripts) connects to these signals by name.

---

## 13. Documentation

### Where documentation lives

- `docs_src/` — Markdown source files (this is what you edit).
- `docs/` — Built HTML output (generated; do not edit manually).

### Building the docs

```bash
python scripts/build_docs_portal.py
```

This runs MkDocs (or a custom builder) and writes output to `docs/`.

### What to document

- Every new node: add to the relevant section in `docs_src/05_node_reference.md`.
- Every new keyboard shortcut: add to `docs_src/03_ui_guide.md`.
- Every new engine feature or signal: add to `docs_src/06_engine_api.md`.
- Bug fixes that change user-visible behavior: add a note to `docs_src/11_troubleshooting.md`.

### Documentation style

- Use present tense: "The ForEach node fires…" not "The ForEach node will fire…".
- Prefer concrete examples over abstract descriptions.
- Every code block must be runnable as written. Test it.
- Tables over lists when comparing multiple options.

---

## 14. Adding to CLAUDE.md

`CLAUDE.md` is the AI developer guide — it tells Claude (and other AI contributors) how this codebase works. Update it when you:

- Add a new bridge method to `hou_bridge.py`.
- Add a new node pattern that future nodes should follow.
- Fix a significant bug that an AI might otherwise reintroduce.
- Add a new file or module that changes the architecture.

Keep entries concise. CLAUDE.md is a reference document, not a tutorial.

---

## 15. Common Pitfalls for New Contributors

**Adding exec_in/exec_out manually in `__init__`**
`super().__init__()` already adds them. Adding them again creates duplicates. Only add ports that are specific to your node.

**Calling `asyncio.run()` inside `execute()`**
`execute()` is already running inside an event loop. Use `await` directly:
```python
# Wrong
result = asyncio.run(some_coroutine())

# Correct
result = await some_coroutine()
```

**Storing mutable state in class attributes**
Class attributes are shared across all instances. Use `self.parameters` for persisted state and `self.memory` for per-run state:
```python
# Wrong: shared across all instances
class MyNode(BaseNode):
    results = []   # BUG: shared state

# Correct
async def execute(self, inputs):
    results = list(self.memory.get("results", []))
```

**Hardcoding the port list in `inputs` dict**
The `inputs` dict only contains ports that have a connected wire or a widget value. Always use `.get()` with a default:
```python
# Fragile
value = inputs["my_port"]

# Correct
value = inputs.get("my_port", "default")
```

**Forgetting `exec_out` in the return dict**
Nodes that omit `exec_out` silently stop the execution chain. All exec-flow nodes must include `"exec_out": True` in their return dict.

**Importing Qt modules directly**
Use `from src.utils.qt_compat import QtWidgets, QtGui, QtCore` to ensure PyQt5/PyQt6 compatibility. Never `from PyQt5 import ...` in shared code.

**Modifying the scene outside the main thread**
All Qt widget operations must happen on the main thread. If your `execute()` uses `asyncio.to_thread()`, do not touch any Qt object from inside the thread callback.

**Using `load_all()` instead of `load_all_with_extras()`**
`load_all_with_extras()` is the correct entry point — it loads bundled nodes plus the `v_nodes_dir` extras. Plain `load_all()` silently skips Houdini nodes. Always use `load_all_with_extras()` in `window.py`.
