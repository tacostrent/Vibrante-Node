# Troubleshooting Guide

This guide covers the most common problems users and developers encounter with Vibrante-Node v2.5.0, organized by symptom. For each issue you will find: what causes it, how to diagnose it, and how to fix it.

---

## 1. Installation Issues

### PyQt5 not found

**Symptom:** `ModuleNotFoundError: No module named 'PyQt5'` at startup.

**Cause:** PyQt5 is not installed in the active Python environment.

**Fix:**
```bash
pip install PyQt5
```

If you are on Python 3.12 or newer and PyQt5 installation fails with a wheel error, use Python 3.11:
```bash
python3.11 -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

On Linux, also install the system Qt libraries:
```bash
sudo apt-get install python3-pyqt5
# or
pip install PyQt5 --config-settings --confirm-license=
```

---

### QScintilla missing — code editor shows plain text

**Symptom:** The Python editor in the Node Builder or Script Editor shows as a plain text box without syntax highlighting or autocompletion.

**Cause:** QScintilla (`PyQt5.Qsci`) is not installed. This is not an error — the app falls back to a `QPlainTextEdit`-based editor automatically.

**Fix (optional):**
```bash
pip install QScintilla
```

Restart the app after installing. If QScintilla is installed but the enhanced editor still doesn't appear, check that the version matches your PyQt5 version:
```bash
pip show QScintilla PyQt5
```

**Important:** This fallback is intentional. Never re-raise the `ImportError` in `code_editor.py`. If you see `ImportError: QScintilla is required` as a hard crash, someone has re-added the raise — revert that change.

---

### Pydantic version errors

**Symptom:** `ValidationError`, `AttributeError: model_fields`, or `TypeError: __init__() got an unexpected keyword argument` when loading workflows.

**Cause:** Vibrante-Node requires pydantic v2. Pydantic v1 has an incompatible API.

**Diagnosis:**
```bash
python -c "import pydantic; print(pydantic.VERSION)"
```

**Fix:**
```bash
pip install "pydantic>=2.0"
```

If another package in your environment pins pydantic v1, use a separate virtual environment for Vibrante-Node.

---

### `No module named 'src'`

**Symptom:** `ModuleNotFoundError: No module named 'src'` when running scripts or tests.

**Cause:** Python cannot find the `src` package because the working directory is not the project root, or the project root is not in `sys.path`.

**Fix for running the app:**
```bash
# Always run from the project root (node_based_app/)
cd /path/to/node_based_app
python -m src.main
```

**Fix for scripts:**
```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.engine import NetworkExecutor
```

**Fix for tests:** The `pytest.ini` at the project root sets `pythonpath = .` which handles this automatically. Always run pytest from the project root.

---

## 2. App Won't Start

### Qt platform plugin error on Windows

**Symptom:**
```
qt.qpa.plugin: Could not find the Qt platform plugin "windows" in ""
This application failed to start because no Qt platform plugin could be initialized.
```

**Cause:** Qt's DLLs are not in the path, or the virtual environment is missing Qt platform files.

**Fix:**
```bash
pip install --force-reinstall PyQt5 PyQt5-Qt5 PyQt5-sip
```

If using a PyInstaller build (the `.exe`), ensure the `platforms/` folder exists next to the executable:
```
vibrante_node.exe
platforms/
  qwindows.dll
```

---

### Linux: no display / cannot connect to X server

**Symptom:** `qt.qpa.xcb: could not connect to display` or `DISPLAY is not set`.

**Fix for headless servers:** Use a virtual display:
```bash
pip install pyqtgraph  # optional
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
python -m src.main
```

For running in CI or Docker, use `offscreen` platform:
```bash
QT_QPA_PLATFORM=offscreen python -m src.main
```

**Fix for desktop Linux:** Ensure `$DISPLAY` is set and the current user has access to the X session:
```bash
export DISPLAY=:0
xhost +local:
```

---

### Crash on startup with no error message

**Symptom:** App closes immediately with no dialog or log output.

**Check:** Look for `crash.log` in the project root:
```bash
cat crash.log
```

The crash log captures Python tracebacks that occur before the UI is ready. Common causes:
- Corrupt `settings.json` in `~/.vibrante_node/`
- A broken node JSON file in `nodes/` that crashes the registry loader
- A missing icon file referenced in a node JSON

**Fix for corrupt settings:**
```bash
# Delete user settings to reset to defaults
rm ~/.vibrante_node/settings.json   # Linux/macOS
del %USERPROFILE%\.vibrante_node\settings.json   # Windows
```

**Fix for broken node JSON:** Remove or fix the offending file in `nodes/`. The crash log will name the file.

---

## 3. Nodes Not Appearing in Library

### Node JSON file not loaded

**Symptom:** A `.json` file in `nodes/` is not appearing in the Node Library panel.

**Diagnosis checklist:**
1. Is the file valid JSON? Validate with: `python -m json.tool nodes/my_node.json`
2. Does the file have `"node_id"` and `"name"` fields?
3. Is `"python_code"` present and non-empty?
4. Does the `python_code` contain a `register_node()` function that returns the class?
5. Is there a syntax error in the `python_code` string?

**Checking for syntax errors in python_code:**
```python
import json, ast
with open("nodes/my_node.json") as f:
    data = json.load(f)
try:
    ast.parse(data["python_code"])
    print("Syntax OK")
except SyntaxError as e:
    print(f"Syntax error: {e}")
```

---

### Houdini nodes missing from library

**Symptom:** Houdini-specific nodes from `plugins/houdini/v_nodes_houdini/` do not appear after launching from Houdini.

**Cause:** `v_nodes_dir` environment variable is not set, or `NodeRegistry.load_all()` was called instead of `load_all_with_extras()`.

**Diagnosis:** In the app, open the Python console (if available) and run:
```python
import os
print(os.environ.get("v_nodes_dir", "NOT SET"))
```

**Fix:**
- Ensure you launched the app from Houdini via **Vibrante-Node → Launch** (not by running `python -m src.main` directly).
- In `src/ui/window.py`, confirm `load_all_with_extras(bundled_nodes)` is called, not `load_all(bundled_nodes)`.

---

### `register_node()` missing

**Symptom:** Node file loads without error but class is not accessible.

**Cause:** The `python_code` string is missing the `register_node()` function at the module level.

**Required:**
```python
def register_node():
    return MyNodeClass
```

This function must be at module level (not inside the class) and must return the class itself, not an instance.

---

## 4. Workflow Won't Run

### No entry node / nothing executes

**Symptom:** Click Run — nothing happens. Log panel is empty.

**Cause:** The engine cannot find a starting node. The execution engine starts from nodes that have no `exec_in` connection (their `exec_in` port is unconnected).

**Fix:** Ensure at least one node in your workflow has no incoming `exec_in` connection. That node is the entry point.

If all nodes have `exec_in` wired (a closed loop), the engine has no starting point. Break the loop by disconnecting one `exec_in`.

---

### Circular dependency error

**Symptom:** `CyclicDependencyError` or `RecursionError` in the log.

**Cause:** A data connection creates a cycle (Node A output → Node B input → Node A input).

**Fix:** Inspect the data connections (non-exec wires). Cycles in exec flow are handled differently than data cycles. A cycle in data connections is always an error — restructure your workflow to use `SetVariable` / `GetVariable` to break the cycle.

---

### All nodes are bypassed

**Symptom:** Run completes instantly, no output, log says nodes were skipped.

**Fix:** Right-click each node and check if **Bypass** is checked. Bypassed nodes appear dimmed. Un-bypass them via right-click → Bypass (toggle off).

---

## 5. Node Produces Wrong Output

### `None` values flowing through wires

**Symptom:** A downstream node receives `None` where it expects a string or list.

**Diagnosis:**
1. Hover the wire from the upstream node — the tooltip shows the last value.
2. Check the upstream node's `execute()` return dict. Is the output key present?
3. Check for an exception in the upstream node: look for red entries in the log panel.

**Common cause:** The upstream node raised an exception, its `except` block returned `{"exec_out": True}` without the expected output key, so downstream receives `None` from `.get()`.

**Fix:** Ensure every code path in `execute()` returns all expected output keys:
```python
return {
    "result": result_value,   # always present, even on error
    "exec_out": True
}
```

---

### Values not updating between runs

**Symptom:** A node seems to remember values from the previous run.

**Cause:** State is stored in `self.parameters` (persisted to the workflow JSON) instead of `self.memory` (cleared each run).

**Fix:** Use `self.memory` for per-run transient state:
```python
# Wrong: persists across runs
self.parameters["count"] = self.parameters.get("count", 0) + 1

# Correct: fresh each run
count = self.memory.get("count", 0) + 1
self.memory["count"] = count
```

---

## 6. Houdini Bridge Not Connecting

### `ConnectionRefusedError` or `ConnectionError: Houdini bridge not connected`

**Symptom:** Any Houdini node fails with a connection error.

**Checklist:**

1. **Is the Vibrante-Node server running inside Houdini?**
   In Houdini, open the Python Shell and run:
   ```python
   import vibrante_hou_server
   print(vibrante_hou_server._server_thread)
   ```
   If it prints `None`, the server is not running. Start it:
   ```python
   vibrante_hou_server.start()
   ```

2. **Is the port correct?**
   Default port is `18811`. Check:
   ```python
   import os
   print(os.environ.get("VIBRANTE_HOU_PORT", "18811 (default)"))
   ```
   In Houdini:
   ```python
   print(vibrante_hou_server._port)
   ```
   Both must match.

3. **Is a firewall blocking localhost?**
   The bridge uses `127.0.0.1` (loopback). Windows Defender or corporate firewalls may block local socket connections. Add an exception for Python on localhost port 18811.

4. **Did Houdini launch the app, or did you launch it manually?**
   `VIBRANTE_HOU_PORT` is only set in the subprocess environment when launched from Houdini via **Vibrante-Node → Launch**. Running `python -m src.main` directly will use the default port, which only works if the Houdini server is also on the default port.

---

### 30-second timeout then `ConnectionError`

**Symptom:** A Houdini node hangs for 30 seconds then fails with `ConnectionError: Houdini did not respond within 30s`.

**Cause:** Houdini is busy (e.g., cooking a heavy SOP network) and cannot respond to the JSON-RPC server.

**Fix:**
- Wait for the Houdini cook to finish before running Vibrante-Node.
- For long-running operations, consider using `bridge.run_code()` to start a background cook and poll for completion, rather than calling `bridge.cook_node()` synchronously.

---

## 7. Maya Headless Failing

### `FileNotFoundError` for Maya executable

**Symptom:** Maya headless executor fails immediately with a path error.

**Fix:** Set `VIBRANTE_MAYA_EXE` in your environment to the full path of `mayapy.exe`:
```bash
# Windows
set VIBRANTE_MAYA_EXE=C:\Program Files\Autodesk\Maya2024\bin\mayapy.exe

# macOS
export VIBRANTE_MAYA_EXE=/Applications/Autodesk/maya2024/Maya.app/Contents/bin/mayapy
```

---

### Scene not found error

**Symptom:** `open_scene` action fails with "file not found" even though the path looks correct.

**Cause:** The path may contain backslashes that Maya's Python interpreter interprets incorrectly, or the file doesn't exist at the given path from the Maya subprocess's working directory.

**Fix:** Always use forward slashes in scene paths:
```python
scene_path = scene_path.replace("\\", "/")
```

---

### Action handler missing

**Symptom:** `KeyError: 'my_action_type'` or `Unknown action type: my_action_type` in the Maya runner log.

**Cause:** The action `type` string in the action dict does not have a corresponding handler in the Maya runner script.

**Fix:** Open `plugins/maya/maya_runner.py` (or equivalent) and add:
```python
def handle_my_action_type(action: dict, scene_info: dict):
    # Implementation
    pass

HANDLERS = {
    # ... existing handlers ...
    "my_action_type": handle_my_action_type,
}
```

---

## 8. Prism Nodes Not Working

### `PrismCore not initialized`

**Symptom:** All `prism_*` nodes log `"PrismCore not initialized. Add a prism_core_init node to the graph."` and produce empty output.

**Cause:** The `prism_core_init` node is missing from the workflow graph.

**Fix:** Drag a `prism_core_init` node onto the canvas. It does not need to be wired into the exec chain — the engine detects its presence before execution and bootstraps PrismCore automatically. However, it must be present (not bypassed).

---

### Prism import error

**Symptom:** `ModuleNotFoundError: No module named 'PrismCore'` or `No module named 'Prism_Core'`.

**Cause:** Prism Pipeline is not installed, or its Python path is not set.

**Fix:** Ensure the Prism Python scripts directory is in `sys.path`. Check your Prism installation for the correct path and add:
```python
# In src/utils/prism_core.py or your launch script
sys.path.insert(0, "/path/to/Prism2/Scripts")
```

---

## 9. GroupNode Issues

### "No internal workflow" error

**Symptom:** Double-clicking a GroupNode shows an error: "This group node has no internal workflow."

**Cause:** The GroupNode's `__workflow__` parameter is empty or was not saved correctly. This was a known issue in early versions caused by UUID serialization — fixed in v2.0.0.

**Diagnosis:** Right-click the GroupNode → Inspect Parameters. Check if `__workflow__` contains a valid workflow dict or is empty/null.

**Fix:** If the GroupNode is empty and you still have the original nodes in another tab or workflow:
1. Re-create the subgraph in a new tab.
2. Select those nodes.
3. Ctrl+Shift+G to create a fresh GroupNode.
4. The new GroupNode will serialize correctly.

If upgrading from a pre-v2.0.0 workflow with broken GroupNodes, the only recovery path is to re-create the groups. The bug was in serialization, so the internal logic cannot be recovered from the corrupt file.

---

### Exec flow not propagating out of GroupNode

**Symptom:** Nodes downstream of a GroupNode never execute.

**Cause:** The GroupNode's internal `GroupOut` node is not connected in the exec chain, or `GroupOut` is not wired to `exec_in`.

**Fix:** Double-click the GroupNode to open the subgraph. Verify that the exec chain inside runs through to a `GroupOut` node. GroupOut must have `exec_in` connected from the last node in the inner chain.

Also verify `GroupOut`'s `port_name` matches the expected output port name on the outer GroupNode.

---

## 10. Exec Flow Not Progressing

### Workflow stops mid-execution silently

**Symptom:** Some nodes run, then execution stops with no error.

**Cause:** A node returned a dict without `"exec_out": True`, or returned `exec_out: False`.

**Diagnosis:**
1. Check the log panel — the last node listed is where execution stopped.
2. Open that node's `execute()` code and check every return statement.

**Fix:** Ensure every code path returns `"exec_out": True`:
```python
async def execute(self, inputs):
    if something_failed:
        self.log_error("Something failed")
        return {"result": None, "exec_out": True}   # exec_out still True — chain continues
    return {"result": value, "exec_out": True}
```

If you want to intentionally stop the exec chain (rare), return `"exec_out": False`.

---

### TwoWaySwitch not routing correctly

**Symptom:** TwoWaySwitch always routes to `exec_true` even when condition should be False.

**Cause:** The `condition` input is receiving a truthy non-boolean value (e.g., the string `"False"` is truthy in Python).

**Fix:** Ensure the condition value is a Python `bool`. In a Python Script node:
```python
# Wrong: string "False" is truthy
result = "False"

# Correct
result = False
result = some_value > threshold       # bool expression
result = bool(int(inputs.get("data", 0)))  # explicit cast
```

---

## 11. Autosave Restore Dialog Always Showing

**Symptom:** Every time the app starts, the "Restore unsaved sessions?" dialog appears, even after accepting or declining.

**Cause:** The autosave file (`~/.vibrante_node_autosave.json`) is being written but not deleted on clean exit. This happens if the app is force-closed, crashes, or if `closeEvent` is not being called.

**Manual fix:** Delete the autosave file:
```bash
# Windows
del %USERPROFILE%\.vibrante_node_autosave.json

# Linux / macOS
rm ~/.vibrante_node_autosave.json
```

**Permanent fix:** Ensure you close the app via the window's X button or File → Exit, not via Task Manager or `kill`. The close event cleans up the autosave file on normal exit.

If the dialog appears after a crash: this is by design. Accept the restore to recover unsaved work, or decline to start fresh.

---

## 12. Async Deadlock / UI Freezing

**Symptom:** The UI becomes unresponsive during execution. The progress indicator spins but nothing moves.

**Cause:** A blocking call inside `execute()` is holding the event loop:
- `time.sleep()` — freezes the event loop thread
- `requests.get()` — synchronous HTTP blocks
- `subprocess.run(capture_output=True)` without timeout — hangs waiting for subprocess

**Fix:** Wrap blocking calls in `asyncio.to_thread()`:
```python
import asyncio

async def execute(self, inputs):
    # Wrong: blocks the event loop
    import time
    time.sleep(5)

    # Correct: offloads to a thread, event loop stays responsive
    await asyncio.sleep(5)   # for delays

    # Wrong: synchronous HTTP
    import requests
    response = requests.get(url)

    # Correct: async HTTP
    import urllib.request, asyncio
    loop = asyncio.get_running_loop()
    text = await loop.run_in_executor(None, lambda: urllib.request.urlopen(url).read().decode())

    # Wrong: blocking subprocess
    import subprocess
    result = subprocess.run(["cmd"], capture_output=True)

    # Correct: async subprocess
    proc = await asyncio.create_subprocess_exec(
        "cmd", stdout=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
```

---

## 13. Memory Growing Over Multiple Runs

**Symptom:** The app uses more RAM each time you click Run.

**Cause 1: Storing large data in `self.parameters`**
`self.parameters` is persisted in the workflow JSON. If you store large binary data or giant lists there, they accumulate and are serialized to disk on save.

**Fix:** Never store large transient data in `self.parameters`. Use `self.memory` for per-run state — it is cleared before each run.

**Cause 2: Circular references in the graph's node_results**
If nodes hold references to large objects and those objects reference back to the node, Python's garbage collector may not reclaim them.

**Fix:** In `execute()`, return primitive types (strings, numbers, lists of primitives) where possible. Avoid returning the entire input dict as an output.

---

## 14. PyInstaller Build Fails

**Symptom:** `ModuleNotFoundError` at runtime when using the built `.exe`, even though the app works fine when running from source.

**Cause:** PyInstaller's static analysis misses dynamically-imported modules (like node classes loaded from JSON files at runtime).

**Fix — add hidden imports to `vibrante_node.spec`:**
```python
hiddenimports=[
    "src.nodes.builtins.group_node",
    "src.nodes.builtins.my_new_node",
    "src.utils.hou_bridge",
    "src.utils.prism_core",
    "PyQt5.sip",
    "pydantic.v1.validators",  # if using pydantic v2 compatibility layer
],
```

**Fix — include data files:**
```python
datas=[
    ("nodes/", "nodes/"),
    ("icons/", "icons/"),
    ("plugins/", "plugins/"),
],
```

After updating the spec file:
```bash
pyinstaller vibrante_node.spec --clean
```

---

## 15. Reading crash.log

When the app crashes before the UI is ready, a `crash.log` file is written to the project root. Its format:

```
=== Vibrante-Node Crash Log ===
Version: 2.0.0
Time: 2026-05-10 14:32:01
Python: 3.11.4
Platform: win32

Traceback (most recent call last):
  File "src/main.py", line 42, in main
    window = MainWindow()
  File "src/ui/window.py", line 88, in __init__
    self._load_nodes()
  ...
SyntaxError: invalid syntax (<string>, line 7)
```

**Common crash causes from crash.log:**

| Error in log | Cause | Fix |
|-------------|-------|-----|
| `SyntaxError` in `<string>` | Broken `python_code` in a JSON node | Fix the node JSON in `nodes/` |
| `ValidationError` from pydantic | Corrupt `settings.json` | Delete settings file |
| `ImportError: No module named 'X'` | Missing dependency | `pip install X` |
| `FileNotFoundError: icons/X.svg` | Node JSON references a missing icon | Add the icon or set `"icon_path": null` |
| `AttributeError: 'NoneType'` in `_init_menu` | Settings returned None for a required value | Delete settings file |

---

## 16. Performance: Too Many Nodes Causing Slowness

**Symptom:** The canvas becomes sluggish with 100+ nodes. Workflow execution is slower than expected.

**Canvas performance:**
- Reduce the number of visible nodes by collapsing related nodes into GroupNodes (Ctrl+Shift+G).
- Disable the mini-map (Ctrl+M) if you have a large number of nodes — the mini-map re-renders the full scene.
- Use backdrop nodes to organize without adding execution overhead.

**Execution performance:**
- Identify slow nodes using the timing log: `Node 'X' finished in 12.34s`.
- Move heavy I/O operations to `asyncio.to_thread()` so they run concurrently.
- For batch operations, prefer a single Python Script node that processes a list internally, rather than a ForEach loop with many individual nodes — the loop overhead adds up.
- Cache results using `SetVariable` / `GetVariable` rather than re-computing on every iteration.

**Profiling a slow workflow:**
```python
# Temporary: add to a Python Script node to profile a specific operation
import cProfile
import pstats
import io

pr = cProfile.Profile()
pr.enable()

# ... your code here ...

pr.disable()
s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
ps.print_stats(20)
self.log_info(s.getvalue())
```
