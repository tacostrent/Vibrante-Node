# Node Development Guide — Vibrante-Node v2.5.0

This guide walks through everything you need to know to build custom nodes for
Vibrante-Node, from the simplest string transformer to a fully-async HTTP client
node with error branches and dynamic ports.

---

## Table of Contents

1. [Node Architecture Overview](#1-node-architecture-overview)
2. [Two Ways to Create Nodes](#2-two-ways-to-create-nodes)
3. [Step-by-Step: Your First Node](#3-step-by-step-your-first-node)
4. [Port System Deep-Dive](#4-port-system-deep-dive)
5. [The execute() Method](#5-the-execute-method)
6. [Logging](#6-logging)
7. [Reactive Output with set_output()](#7-reactive-output-with-set_output)
8. [State Persistence with self.parameters](#8-state-persistence-with-selfparameters)
9. [Shared State with BaseNode.memory](#9-shared-state-with-basenodemory)
10. [Dynamic Ports](#10-dynamic-ports)
11. [Dropdown Options](#11-dropdown-options)
12. [File and File-Save Widgets](#12-file-and-file-save-widgets)
13. [Data-Only Nodes (use_exec=False)](#13-data-only-nodes-use_execfalse)
14. [Registering Your Node](#14-registering-your-node)
15. [Node Categories and the Library Panel](#15-node-categories-and-the-library-panel)
16. [Custom Icons](#16-custom-icons)
17. [Testing and Debugging](#17-testing-and-debugging)
18. [Performance Considerations](#18-performance-considerations)
19. [Common Mistakes](#19-common-mistakes)
20. [Complete Example: File Rename Node](#20-complete-example-file-rename-node)
21. [Complete Example: HTTP API Request Node](#21-complete-example-http-api-request-node)

---

## 1. Node Architecture Overview

A **node** in Vibrante-Node is a unit of work. Visually it appears as a box on
the canvas with named connection points (ports) on its left (inputs) and right
(outputs) sides. Internally it is a Python class that inherits from `BaseNode`
and implements a single `async def execute(self, inputs)` method.

### What a node contains

| Component | Purpose |
|-----------|---------|
| `inputs` dict | Named `Port` objects describing data the node receives |
| `outputs` dict | Named `Port` objects describing data the node produces |
| `parameters` dict | Persistent key/value store — widget values live here |
| `execute()` | The async method the engine calls when the node runs |
| logging methods | `log_info`, `log_error`, `log_success` — appear in the log panel |
| `set_output()` | Push a value to downstream nodes *before* exec_out fires |

### Lifecycle of a node during a pipeline run

```
Engine starts
    │
    ▼
restore_from_parameters(saved_params)   ← rebuild dynamic ports from saved state
    │
    ▼
clear_outputs()                         ← reset all output port values to defaults
    │
    ▼
sync parameters from upstream results   ← values from connected edges arrive
    │
    ▼
execute(inputs)                         ← your code runs here
    │
    ├── await self.set_output(...)       ← push values reactively mid-execution
    │
    └── return {port: value, ...}       ← final output dict sent to engine
```

The engine handles all wiring automatically. Your node never needs to reach
into other nodes — you receive values through the `inputs` dict and send values
back through the return dict or `set_output()`.

---

## 2. Two Ways to Create Nodes

### Method A — JSON file with embedded Python (recommended)

Place a `.json` file anywhere inside the `nodes/` directory (or a directory
listed in the `v_nodes_dir` environment variable). The file bundles the node's
metadata, port definitions, and Python code into a single self-contained unit.

This is the preferred approach because:
- The Node Builder UI can read and write these files directly.
- Node hot-reload works (Edit → Reload Node Definition).
- The file is trivially portable — drop it in any project's `nodes/` folder.

### Method B — Pure Python class (advanced)

Write a `.py` file with a class that inherits from `BaseNode` and a
`register_node()` function. The registry compiles either format identically at
runtime; the difference is purely organizational.

Pure Python is useful when:
- The node has complex helper functions you want in separate methods.
- You are writing a built-in node bundled with the application itself.
- You want full IDE autocomplete and static analysis during development.

---

## 3. Step-by-Step: Your First Node

We will build a simple node that receives a string and outputs it in uppercase.

### Step 1 — Create the JSON file

Create `nodes/text_upper.json`:

```json
{
    "node_id": "text_upper",
    "name": "text_upper",
    "description": "Converts a string to uppercase.",
    "category": "Text",
    "icon_path": null,
    "use_exec": true,
    "inputs": [
        { "name": "text",     "type": "string", "widget_type": "text", "options": null, "default": "" },
        { "name": "exec_in",  "type": "any",    "widget_type": null,   "options": null, "default": null }
    ],
    "outputs": [
        { "name": "result",   "type": "string", "widget_type": null, "options": null, "default": null },
        { "name": "exec_out", "type": "any",    "widget_type": null, "options": null, "default": null }
    ],
    "python_code": "from src.nodes.base import BaseNode\n\nclass Text_Upper(BaseNode):\n    name = 'text_upper'\n\n    def __init__(self):\n        super().__init__()\n        # [AUTO-GENERATED-PORTS-START]\n        self.add_input('text', 'string', widget_type='text')\n        self.add_output('result', 'string')\n        # [AUTO-GENERATED-PORTS-END]\n\n    async def execute(self, inputs):\n        text = inputs.get('text', '')\n        return {'result': text.upper(), 'exec_out': True}\n\ndef register_node():\n    return Text_Upper"
}
```

### Step 2 — Restart or hot-reload

If the app is already running, open the Node Builder (or use
Edit → Reload Node Definitions). The "text_upper" node now appears in the
library under the "Text" category.

### Step 3 — Place the node on canvas

Open the node search popup (Tab key or right-click → Add Node), type "upper",
and click the result. A node appears on the canvas.

### Step 4 — Wire it up

Connect a String Literal node's output to `text_upper.text`. Connect
`text_upper.exec_out` to a Console Sink. Run the pipeline — the console shows
the uppercased string.

---

## 4. Port System Deep-Dive

### Inputs vs. outputs

Input ports appear on the **left** side of the node widget. They receive values
from upstream nodes or display an inline widget when unconnected.

Output ports appear on the **right** side. They carry results to downstream
nodes.

### Exec pins

When `use_exec=True` (the default), `super().__init__()` automatically creates:
- `exec_in` — an input of type `exec`. The node does not run until this fires.
- `exec_out` — an output of type `exec`. Triggers the next node in the chain.

**Do not** add `exec_in` or `exec_out` manually inside `__init__`. They are
already there.

You can add **additional** exec outputs (e.g., a failure branch) using
`self.add_exec_output("exec_fail")`.

### Data types

| Type | Python equivalent | Notes |
|------|------------------|-------|
| `string` | `str` | Default value `""` |
| `int` | `int` | Default value `0` |
| `float` | `float` | Default value `0` |
| `bool` | `bool` | Default value `False` |
| `list` | `list` | Default value `[]` |
| `dict` | `dict` | Default value `{}` |
| `any` | any | No type coercion; used for exec pins and generic data |

The engine does not coerce types automatically. If you declare a port as `int`
but receive a string `"42"`, convert it yourself inside `execute()`.

### Widget types

Widget types control the inline editor shown on an unconnected input port.

| `widget_type` | Appearance | Best for |
|---------------|------------|---------|
| `text` | Single-line text box | Short strings, names, paths |
| `text_area` | Multi-line text box | Code, JSON, long text |
| `int` | Integer spinner | Integer parameters |
| `float` | Float spinner | Numeric parameters |
| `bool` | Checkbox | Toggles |
| `dropdown` | Combo box | Enumerated choices |
| `slider` | Horizontal slider | 0–100 range values |
| `file` | Path box + Browse button | Input file selection |
| `file_save` | Path box + Save dialog button | Output file selection |

Specifying `widget_type=None` (the default) means the port has no inline
widget — it only accepts data through a connected wire.

### Adding ports in __init__

```python
def __init__(self):
    super().__init__()   # adds exec_in + exec_out automatically
    # [AUTO-GENERATED-PORTS-START]
    self.add_input("name",    "string", widget_type="text",     default="World")
    self.add_input("count",   "int",    widget_type="int",      default=1)
    self.add_input("enabled", "bool",   widget_type="bool",     default=True)
    self.add_input("items",   "list")                           # no widget
    self.add_output("result", "string")
    self.add_output("count",  "int")
    # [AUTO-GENERATED-PORTS-END]
```

The `# [AUTO-GENERATED-PORTS-START]` / `# [AUTO-GENERATED-PORTS-END]` comments
are markers the Node Builder uses to identify the auto-managed port block. Keep
your custom ports inside these markers when using the JSON format.

---

## 5. The execute() Method

`execute()` is the only method you must implement. It is declared `async def`
so you can use `await` for I/O, sleep, or other coroutines without blocking the
Qt event loop.

### Signature

```python
async def execute(self, inputs: dict) -> dict:
```

### The `inputs` dict

`inputs` is a snapshot of `self.parameters` at the moment the node is about to
run, with values from connected upstream nodes already merged in. Access inputs
with:

```python
value = inputs.get("port_name", default_if_missing)
```

Prefer `inputs.get()` over `self.parameters.get()` — the engine may update
`self.parameters` between now and the end of your method if reactive propagation
fires, so reading from the frozen `inputs` snapshot is safer.

### The return dict

Return a dict whose keys are output port names. Always include `exec_out: True`
for exec-flow nodes:

```python
return {
    "result":   computed_value,
    "exec_out": True,
}
```

Returning `None` or an empty dict is safe (the engine treats it as no outputs).
Returning `exec_out: False` means the exec chain is **not** continued — use
this if you want to halt execution conditionally.

### Async behavior

Because `execute()` is `async def` you can:
- `await asyncio.sleep(0)` to yield control to the event loop (e.g., inside loops)
- `await asyncio.sleep(seconds)` to pause without freezing the UI
- `await some_http_client.get(url)` to make non-blocking network calls
- `await self.set_output("port", value)` to push values reactively mid-execution

You **cannot** use blocking calls (like `requests.get()` or `time.sleep()`)
without wrapping them in `asyncio.to_thread()` or the UI will freeze.

### Checking for cancellation

If the user clicks Stop, `self.is_stopped()` returns `True`. Check it inside
long loops:

```python
for item in big_list:
    if self.is_stopped():
        break
    process(item)
```

---

## 6. Logging

Three logging helpers are available. Messages appear in the log panel with
color-coded styling.

```python
self.log_info("Starting operation...")       # white/grey — informational
self.log_success("Done! Wrote 42 files.")    # green — positive outcome
self.log_error("File not found: /tmp/x.y")  # red — error or warning
```

All three accept a plain string. They are non-blocking — messages are queued if
the engine log hook is not yet wired (which can happen in `__init__`; the queue
is flushed at execution start).

Log messages are prefixed with the node's display name in the log panel so the
user can identify which node produced each message.

---

## 7. Reactive Output with set_output()

Normally, downstream nodes receive your output values only after `execute()`
returns. `set_output()` lets you push a value to downstream nodes *immediately*,
before the method returns — this is called **reactive output**.

```python
async def execute(self, inputs):
    for i in range(10):
        await self.set_output("current_index", i)
        await self.set_output("exec_step", True)   # triggers downstream exec chain
        await asyncio.sleep(0)                     # yield so downstream can run

    return {"current_index": 9, "exec_out": True}
```

When `set_output("exec_step", True)` fires and `exec_step` is an exec-type
port, the engine immediately kicks off every node connected to `exec_step`,
waits for them to finish, and then returns control to your loop.

This is the foundation of `ForEachNode`, `SequenceNode`, and `WhileLoopNode`.

### set_output for data ports

You can also push data reactively:

```python
await self.set_output("progress", i / total)
```

Downstream data nodes that read `progress` will receive the new value the next
time they execute.

### Important: set_output is awaitable

Always `await self.set_output(...)`. Omitting `await` creates a coroutine
object that is silently discarded — the value never propagates.

---

## 8. State Persistence with self.parameters

`self.parameters` is a plain dict that persists across runs **for the lifetime
of the node instance** (i.e., as long as the canvas contains this node). It is
**not** cleared between pipeline runs.

The engine syncs widget values and incoming connection values into
`self.parameters` before calling `execute()`. After `execute()`, the results
dict is merged back into `self.parameters` as well, so you can read the last
known output value of any port via:

```python
last_result = self.parameters.get("result")
```

### Using parameters for internal state

You can store arbitrary keys:

```python
async def execute(self, inputs):
    run_count = self.parameters.get("_run_count", 0) + 1
    self.parameters["_run_count"] = run_count
    self.log_info(f"This node has run {run_count} times.")
    return {"exec_out": True}
```

By convention, internal-only keys are prefixed with `_` to distinguish them
from port names.

### restore_from_parameters

When a workflow is loaded from disk, `restore_from_parameters(saved_params)` is
called before any execution. Override it to recreate dynamic ports from saved
state:

```python
def restore_from_parameters(self, parameters):
    count = parameters.get("_port_count", 1)
    for i in range(count):
        name = f"input_{i}"
        if name not in self.inputs:
            self.add_input(name, "any")
```

The base implementation does nothing (`pass`). You only need to override this
if your node adds or removes ports dynamically at runtime.

---

## 9. Shared State with BaseNode.memory

`BaseNode.memory` is a **class-level dict** shared by every node instance
during a single pipeline run. It is cleared to `{}` at the start of each run by
the engine.

Use it for values that multiple nodes need to communicate without explicit
wiring:

```python
# In SetVariableNode:
BaseNode.memory["my_key"] = some_value

# In GetVariableNode (elsewhere in the graph):
value = BaseNode.memory.get("my_key")
```

This is also how `SetVariableNode` and `GetVariableNode` work internally.

### When to use memory vs. wired connections

| Scenario | Use |
|----------|-----|
| Normal data flow between connected nodes | Wired connections |
| Conditional data shared across branches | `BaseNode.memory` |
| Accumulating a list across loop iterations | `BaseNode.memory` |
| Long-lived state that must survive across runs | `self.parameters` |

---

## 10. Dynamic Ports

Sometimes you don't know the number or names of ports at design time. You can
add or remove ports during execution or in response to connections.

### Adding ports at runtime

```python
def on_plug_sync(self, port_name, is_input, other_node, other_port_name):
    """Called synchronously when a wire is connected."""
    if is_input and port_name == f"input_{self._count - 1}":
        new_name = f"input_{self._count}"
        self.add_input(new_name, "any")
        self._count += 1
        self.rebuild_ports()   # tells the UI to refresh the port list
```

`rebuild_ports()` triggers `_on_ports_changed`, which the UI listens to. Call
it once after all add/remove operations — not once per port.

### Removing ports

```python
if port_name in self.inputs:
    del self.inputs[port_name]
if port_name in self.parameters:
    del self.parameters[port_name]
self.rebuild_ports()
```

### Persisting dynamic ports across save/load

Override `restore_from_parameters()` to recreate ports from saved parameters:

```python
def restore_from_parameters(self, parameters):
    for key in parameters:
        if key.startswith("step_") and key not in self.inputs:
            self.add_input(key, "any")
```

See `SequenceNode` in `src/nodes/builtins/nodes.py` for a complete example.

### Checking connection status

```python
if self.is_port_connected("my_port", is_input=True):
    # port has a wire attached
    pass
```

This queries the UI via the `_is_port_connected` hook set by the canvas.

---

## 11. Dropdown Options

Use `widget_type="dropdown"` with a static or dynamic options list.

### Static options (defined in __init__)

```python
self.add_input(
    "mode", "string",
    widget_type="dropdown",
    options=["fast", "balanced", "slow"],
    default="balanced"
)
```

### Dynamic options (updated at runtime)

Call `self.set_parameter(name, list_of_strings)` to replace the dropdown's
option list. The current selection is preserved if it still exists in the new
list; otherwise the first item becomes selected.

```python
async def on_parameter_changed(self, name, value):
    """Called when the user changes a widget value."""
    if name == "category":
        new_options = self._get_items_for_category(value)
        self.set_parameter("item", new_options)  # pass list → updates dropdown
```

### Reading the dropdown value in execute

```python
mode = inputs.get("mode", "balanced")
```

The dropdown always yields a string matching one of the options.

---

## 12. File and File-Save Widgets

Use `widget_type="file"` for inputs where the user selects an existing file:

```python
self.add_input("input_file", "string", widget_type="file", default="")
```

Use `widget_type="file_save"` for outputs/save paths:

```python
self.add_input("output_path", "string", widget_type="file_save", default="")
```

Both widgets display a text box with a Browse/Save button. The value is always
a plain string file path.

Read the value in `execute()` as usual:

```python
path = inputs.get("input_file", "")
if not path:
    self.log_error("No file selected.")
    return {"exec_out": True}
```

---

## 13. Data-Only Nodes (use_exec=False)

Nodes with `use_exec=False` have no exec pins. They participate in **data-flow
execution** — the engine pulls them automatically whenever a downstream
exec-flow node needs their output, without waiting for an exec trigger.

```python
class Current_Time(BaseNode):
    name = "current_time"
    category = "Utilities"

    def __init__(self):
        super().__init__(use_exec=False)   # no exec pins
        self.add_output("timestamp", "string")
        self.add_output("unix_epoch", "float")

    async def execute(self, inputs):
        from datetime import datetime
        now = datetime.now()
        return {
            "timestamp": now.isoformat(),
            "unix_epoch": now.timestamp(),
        }
```

**When to use `use_exec=False`:**
- The node is a pure function — same inputs always yield same outputs.
- The node produces a value that multiple downstream nodes consume.
- The node has no side effects (does not write files, call APIs, etc.).

**When not to use `use_exec=False`:**
- The node writes to disk, calls an API, or has any side effect.
- The order of execution matters relative to other nodes.
- You want explicit control over when the node runs.

Data-only nodes can still use `self.log_info()` and return values normally.
They simply cannot trigger the exec chain because they have no exec ports.

---

## 14. Registering Your Node

### JSON format (automatic)

Drop a `.json` file in `nodes/` or any directory listed in the `v_nodes_dir`
environment variable. The registry scans for `.json` files recursively.

### Python file format

Write a `.py` file with a `register_node()` function:

```python
from src.nodes.base import BaseNode

class My_Node(BaseNode):
    name = "my_node"
    category = "MyCategory"

    def __init__(self):
        super().__init__()
        self.add_input("value", "string", widget_type="text")
        self.add_output("result", "string")

    async def execute(self, inputs):
        return {"result": inputs.get("value", "").strip(), "exec_out": True}

def register_node():
    return My_Node
```

Place the file anywhere inside `nodes/` or an extra directory. The registry
will find and compile it the same way as a JSON node.

### Simplified format (execute function only)

For very small nodes you can provide just an `execute` function without a class:

```python
async def execute(self, inputs):
    return {"result": inputs.get("value", "").upper(), "exec_out": True}
```

The registry wraps this in a generated `DynamicNode` class automatically. The
downside is you cannot override lifecycle hooks like `restore_from_parameters`
or `on_parameter_changed`.

---

## 15. Node Categories and the Library Panel

The `category` field groups nodes in the library search panel. Use concise,
consistent names:

| Category | Purpose |
|----------|---------|
| `General` | Catch-all for uncategorized nodes |
| `IO` | File reading, writing, network |
| `Text` | String manipulation |
| `Math` | Arithmetic, statistics |
| `Flow` | Execution control (loops, branches) |
| `Logic` | Boolean operations |
| `Memory` | Variables, accumulators |
| `Houdini` | Houdini integration |
| `Maya` | Maya integration |
| `Blender` | Blender integration |
| `Prism` | Prism Pipeline integration |

You may define any category string you like — a new category appears
automatically in the library panel when at least one node uses it.

---

## 16. Custom Icons

Set `icon_path` to a path relative to the app root (e.g.,
`"icons/my_icon.svg"`). SVG and PNG are both supported. The icon appears on
the node header in the canvas.

```text
"icon_path": "icons/houdini.svg"
```

If `icon_path` is `null`, no icon is shown.

To add a new icon, place the file in `icons/` and reference it by filename.

---

## 17. Testing and Debugging

### Running a node in isolation

You can instantiate and call any node class directly in a Python script or the
Scripting Console:

```python
import asyncio
from src.nodes.base import BaseNode

# Import your node file (or paste the class here)
from nodes.text_upper import Text_Upper   # hypothetical import path

node = Text_Upper()
result = asyncio.run(node.execute({"text": "hello world"}))
print(result)  # {'result': 'HELLO WORLD', 'exec_out': True}
```

### Using the Scripting Console

Open the Scripting Console (View → Scripting Console) and write:

```python
from src.core.registry import NodeRegistry
cls = NodeRegistry.get_class("text_upper")
if cls:
    import asyncio
    node = cls()
    result = asyncio.run(node.execute({"text": "test"}))
    print(result)
```

### Live log inspection

Add `self.log_info()` calls at key points. The log panel (bottom of the main
window) shows all messages with timestamps and node names.

### Wire value inspector

After a pipeline run, hover over any wire in the canvas. A tooltip shows the
last value that flowed through it (capped at 300 characters). This is the
fastest way to pinpoint where data goes wrong.

---

## 18. Performance Considerations

### Blocking vs. async calls

Any blocking call inside `execute()` freezes the Qt UI. Convert blocking code
to async using `asyncio.to_thread()`:

```python
import asyncio

async def execute(self, inputs):
    path = inputs.get("file_path", "")

    # Bad: blocks the event loop
    # data = open(path).read()

    # Good: runs in a thread pool
    data = await asyncio.to_thread(open(path).read)
    return {"data": data, "exec_out": True}
```

For HTTP requests, use `urllib.request` in a thread executor. Vibrante-Node's event loop is QTimer-stepped, not continuously running, so `aiohttp` and `httpx` are not compatible. Use the thread pool pattern instead:

```python
import asyncio
import urllib.request

async def execute(self, inputs):
    url = inputs.get("url", "")
    loop = asyncio.get_running_loop()

    def _sync_request():
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read().decode("utf-8")

    text = await loop.run_in_executor(None, _sync_request)
```

### Yielding inside loops

When a loop iterates thousands of times, yield control periodically so the UI
remains responsive:

```python
for i, item in enumerate(items):
    process(item)
    if i % 100 == 0:
        await asyncio.sleep(0)   # yield to event loop every 100 items
```

### Caching expensive operations

Use `self.parameters` to cache results across runs (if the input hasn't
changed):

```python
async def execute(self, inputs):
    key = inputs.get("key", "")
    cached = self.parameters.get("_cached_key")
    if cached == key:
        return {"result": self.parameters.get("_cached_result"), "exec_out": True}

    result = expensive_operation(key)
    self.parameters["_cached_key"] = key
    self.parameters["_cached_result"] = result
    return {"result": result, "exec_out": True}
```

---

## 19. Common Mistakes

### Adding exec_in / exec_out manually

`super().__init__()` already adds them. Adding them again creates duplicate
ports visible in the UI.

```python
# Wrong
def __init__(self):
    super().__init__()
    self.add_input("exec_in", "any")   # duplicate!
    self.add_output("exec_out", "any") # duplicate!

# Correct
def __init__(self):
    super().__init__()   # exec_in + exec_out are already here
    self.add_input("my_data", "string", widget_type="text")
```

### Forgetting exec_out in the return dict

Without `exec_out: True`, the exec chain stops at this node.

```python
# Wrong — downstream nodes never run
async def execute(self, inputs):
    return {"result": "done"}

# Correct
async def execute(self, inputs):
    return {"result": "done", "exec_out": True}
```

### Not awaiting set_output

```python
# Wrong — value never propagates
self.set_output("result", value)

# Correct
await self.set_output("result", value)
```

### Using blocking I/O

```python
# Wrong — freezes UI
import time
time.sleep(5)

# Correct
await asyncio.sleep(5)
```

### Mutating the default list

```python
# Wrong — all instances share the same list object
class My_Node(BaseNode):
    my_list = []   # class-level mutable default

# Correct — use self.parameters or a local variable
async def execute(self, inputs):
    items = list(inputs.get("items") or [])
```

### Mismatched node name and node_id

The `name` class attribute, `node_id` in the JSON, and the class name used in
`register_node()` must all be consistent:

```json
{ "node_id": "text_upper", "name": "text_upper" }
```

```python
class Text_Upper(BaseNode):
    name = "text_upper"          # must match node_id
```

---

## 20. Complete Example: File Rename Node

This node takes an input file path and a new base name, renames the file on
disk, and emits either `exec_out` (success) or `exec_fail` (failure).

```json
{
    "node_id": "file_rename",
    "name": "file_rename",
    "description": "Renames a file on disk. Fires exec_fail if the operation fails.",
    "category": "IO",
    "icon_path": "icons/file-input.svg",
    "use_exec": true,
    "inputs": [
        { "name": "file_path",  "type": "string", "widget_type": "file",  "options": null, "default": "" },
        { "name": "new_name",   "type": "string", "widget_type": "text",  "options": null, "default": "" },
        { "name": "exec_in",    "type": "any",    "widget_type": null,    "options": null, "default": null }
    ],
    "outputs": [
        { "name": "new_path",  "type": "string", "widget_type": null, "options": null, "default": null },
        { "name": "exec_out",  "type": "any",    "widget_type": null, "options": null, "default": null },
        { "name": "exec_fail", "type": "any",    "widget_type": null, "options": null, "default": null }
    ],
    "python_code": "import os\nfrom src.nodes.base import BaseNode\n\nclass File_Rename(BaseNode):\n    name = 'file_rename'\n\n    def __init__(self):\n        super().__init__()\n        # [AUTO-GENERATED-PORTS-START]\n        self.add_input('file_path', 'string', widget_type='file')\n        self.add_input('new_name', 'string', widget_type='text')\n        self.add_output('new_path', 'string')\n        self.add_exec_output('exec_fail')\n        # [AUTO-GENERATED-PORTS-END]\n\n    async def execute(self, inputs):\n        src = inputs.get('file_path', '').strip()\n        new_name = inputs.get('new_name', '').strip()\n\n        if not src or not os.path.isfile(src):\n            self.log_error(f'Source file not found: {src}')\n            await self.set_output('exec_fail', True)\n            return {'new_path': '', 'exec_out': False, 'exec_fail': True}\n\n        if not new_name:\n            self.log_error('New name is empty.')\n            await self.set_output('exec_fail', True)\n            return {'new_path': '', 'exec_out': False, 'exec_fail': True}\n\n        ext = os.path.splitext(src)[1]\n        dest = os.path.join(os.path.dirname(src), new_name + ext)\n\n        try:\n            os.rename(src, dest)\n            self.log_success(f'Renamed to: {dest}')\n            await self.set_output('new_path', dest)\n            await self.set_output('exec_out', True)\n            return {'new_path': dest, 'exec_out': True, 'exec_fail': False}\n        except OSError as e:\n            self.log_error(f'Rename failed: {e}')\n            await self.set_output('exec_fail', True)\n            return {'new_path': '', 'exec_out': False, 'exec_fail': True}\n\ndef register_node():\n    return File_Rename"
}
```

Key patterns in this example:
- Two exec output branches: `exec_out` (success) and `exec_fail` (failure).
- Early guard clauses return immediately with the failure branch.
- `await self.set_output()` pushes the new path before the exec chain fires.
- Every code path returns a complete dict with all output keys.

---

## 21. Complete Example: HTTP API Request Node

This node makes an async HTTP GET request and returns the JSON body. It uses
`urllib.request` in a thread executor (`loop.run_in_executor`) for non-blocking I/O.

```python
# nodes/http_get.py
import asyncio
from src.nodes.base import BaseNode

class Http_Get(BaseNode):
    name = "http_get"
    description = "Makes an async HTTP GET request and returns the JSON response."
    category = "Network"
    icon_path = None

    def __init__(self):
        super().__init__()
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("url",     "string", widget_type="text",  default="https://")
        self.add_input("timeout", "int",    widget_type="int",   default=30)
        self.add_input("headers", "dict")
        self.add_output("response_json", "dict")
        self.add_output("status_code",   "int")
        self.add_output("error_message", "string")
        self.add_exec_output("exec_fail")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        url     = inputs.get("url", "").strip()
        timeout = int(inputs.get("timeout", 30))
        headers = inputs.get("headers") or {}

        if not url:
            self.log_error("URL is empty.")
            await self.set_output("exec_fail", True)
            return {
                "response_json": {}, "status_code": 0,
                "error_message": "URL is empty",
                "exec_out": False, "exec_fail": True,
            }

        import urllib.request
        import urllib.error

        # HTTP requests must use run_in_executor — aiohttp is not compatible
        # with Vibrante-Node's QTimer-stepped event loop
        self.log_info(f"GET {url} (timeout={timeout}s)")

        def _sync_do():
            req = urllib.request.Request(url, headers=headers or {}, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.status, resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode("utf-8", errors="replace")

        loop = asyncio.get_running_loop()
        try:
            status, text = await loop.run_in_executor(None, _sync_do)
            import json as _json
            try:
                body = _json.loads(text)
            except (_json.JSONDecodeError, ValueError):
                body = {"text": text}

            self.log_info(f"Response {status}: {len(text)} chars")
            await self.set_output("response_json", body)
            await self.set_output("status_code", status)
            await self.set_output("exec_out", True)
            return {
                "response_json": body, "status_code": status,
                "error_message": "",
                "exec_out": True, "exec_fail": False,
            }

        except Exception as e:
            msg = str(e)
            self.log_error(f"HTTP error: {msg}")
            await self.set_output("error_message", msg)
            await self.set_output("exec_fail", True)
            return {
                "response_json": {}, "status_code": 0,
                "error_message": msg,
                "exec_out": False, "exec_fail": True,
            }

def register_node():
    return Http_Get
```

Key patterns in this example:
- Use `loop.run_in_executor(None, sync_fn)` for any blocking I/O — HTTP, database, subprocess.
- `asyncio.TimeoutError` caught separately from generic exceptions.
- `await self.set_output("status_code", status)` pushes partial data before the
  rest of the response is read, so the wire value inspector shows it even if
  parsing fails afterward.
- All failure paths include `"exec_out": False` so the exec chain is not
  accidentally continued.

---

*For the complete API reference covering every BaseNode method and attribute,
see [14_custom_nodes_api.md](14_custom_nodes_api.md).*

*For integration with Houdini via HouBridge, see [08_api_reference.md](08_api_reference.md).*
