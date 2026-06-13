# Release Notes — Vibrante-Node v2.0.0

**Release date:** 2026-05-10
**Build:** Python 3.10 / PyInstaller — Windows 64-bit

---

## Overview

v2.0.0 is a major feature release that introduces the Subgraph / Group Node system, Live Wire Inspector, Autosave & Crash Recovery, Canvas Search, Mini-map, Recent Files, Node Execution Timing, and a Ctrl+C crash fix. It consolidates all v1.8.6, v1.8.7, v1.9.0, and post-1.9.0 work into a single stable release with a clean version number reflecting the scope of the changes.

---

## New Features

### Subgraph / Group Node (Ctrl+Shift+G)
Select two or more connected nodes and press **Ctrl+Shift+G** (or Edit → Group Selection) to collapse them into a single **GroupNode** that stores the complete subgraph as an embedded workflow.

- The inner graph is preserved in full inside the collapsed node's parameters — saved and loaded transparently with the parent workflow.
- **Dynamic ports** are created automatically from the boundary edges: one input per external-to-group connection, one output per group-to-external connection.
- **Double-click** the GroupNode to open the subgraph in a new tab for live editing. Changes are written back to the parent GroupNode in real time (undo / redo included).
- `exec_out` fires when the inner graph finishes without an unhandled exception.
- `exec_fail` fires **only** on unhandled exceptions inside the inner graph — semantic failures (e.g. a DCC node returning `success=False`) are routed by the inner graph's own exec pins and do NOT trigger `exec_fail`.
- Inner node logs are forwarded through the GroupNode's logger so they appear in the main log panel.
- **Keyboard shortcut**: `Ctrl+Shift+G` (Ctrl+G is reserved for Wrap in Backdrop).

### Live Wire Value Inspector
Hover over any connected wire during or after execution to see the last value that flowed through it as a tooltip (`port_name: repr(value)`, capped at 300 characters).

- Values persist after execution ends — inspect the final state of every wire without re-running.
- Values are cleared automatically at the start of each new execution run.
- Wire hit area is 12 px wide (up from 2 px) so wires are easy to hover.

### Autosave & Crash Recovery
A `QTimer` fires every 2 minutes and writes all non-empty open tabs to `~/.vibrante_node_autosave.json`.

- On the next launch, if the autosave file exists, a restore dialog is offered.
- On a clean exit (`closeEvent`), the autosave file is deleted — the dialog only appears after a crash or force-close.
- Autosave is skipped during active execution to avoid capturing mid-run state.

### Recent Files (File → Open Recent)
The File menu now has an **Open Recent** submenu listing the last 10 saved or loaded workflows.

- Files that no longer exist on disk are shown grayed-out (disabled).
- **Clear Recent Files** wipes the list.
- The list is rebuilt each time the File menu opens so it is always current.

### Canvas Search Bar (Ctrl+F)
Press **Ctrl+F** (or Edit → Find in Canvas…) to open a floating search bar at the top of the canvas.

- Type to filter nodes by display name or `node_id`.
- The matched node is selected and the view pans to it.
- **Enter** / **▼** cycles forward; **Shift+Enter** / **▲** cycles backward.
- Match counter shows "X / N". **Escape** closes.

### Mini-map (Ctrl+M)
A 200×150 px thumbnail of the full canvas is always visible in the bottom-right corner of each NodeView.

- A blue semi-transparent rectangle shows the current viewport position.
- Click or drag on the mini-map to pan the main view.
- Toggle with **Ctrl+M** or Window → Toggle Mini-map.
- Respects dark / light theme.

### Node Execution Timing
The log panel now shows how long each node took to execute — e.g. `Node 'Get Asset' finished in 0.34s`.

---

## Bug Fixes

### GroupNode: `exec_fail` False Positive
`exec_fail` previously fired whenever any inner node returned a result that looked like a failure (e.g. `maya_headless` returning `success=False`). This caused false-positive "Group inner execution reported failure" errors even when the inner graph handled the failure correctly via its own exec routing.

**Fix**: `exec_fail` now fires **only** when an unhandled exception propagates out of an inner node (i.e. `node_error` signal is emitted by the sub-executor). Semantic outcomes are the inner graph's responsibility.

### GroupNode: Injected Input Values Lost on Exec Ports
Group input values were injected into `GroupInNode.parameters["value"]`, but `"value"` is an output port — the engine's `clear_outputs()` call resets all output-port-named parameters to `None` before `execute()` runs. Input values were therefore always `None` by the time the inner node ran.

**Fix**: Injection now uses `parameters["_injected_value"]` (not a port name, immune to `clear_outputs()`). `GroupInNode.execute()` reads from this key.

### GroupNode: Inner Node Logs Discarded
All log messages from nodes inside a GroupNode were silently dropped — `sub_executor.node_log` was never connected.

**Fix**: `node_log` is connected to `_forward_log` which routes inner messages through the GroupNode's own logger with a `[node_label]` prefix.

### GroupNode: `exec_out` Not Forwarded Through GroupOutNode
`GroupOutNode` was `use_exec=False`, meaning the inner exec chain could not route through it. If an inner exec chain needed to flow node-A → group_out → (end), the exec pin on group_out was ignored.

**Fix**: `GroupOutNode` is now `use_exec=True` with `exec_in` / `exec_out` ports. It calls `set_output("exec_out", True)` so the inner exec chain routes correctly. Legacy subgraphs without exec wiring on group_out still work — the node runs as a data entry node when no exec connection is present.

### GroupNode: Subgraph Edits Not Persisted
Opening a subgraph in a new tab and editing it (adding nodes, changing connections) did not update the parent GroupNode. The `__workflow__` parameter was never written back.

**Fix**: `_open_subgraph_tab` sets a `_sync_callback` on the subgraph `NodeScene`. The callback fires on every `push_history()`, `undo()`, and `redo()` call and writes the current workflow dict back to `group_widget.node_definition.parameters["__workflow__"]`, then pushes the parent scene's history so the parent workflow is also saved correctly.

### GroupNode: `[ERROR] Group node has no internal workflow.` After Save/Load
After editing a subgraph and saving the parent workflow, reloading it produced "Group node has no internal workflow." The `__workflow__` key was silently dropped from the JSON file.

**Root cause**: `push_history()` uses `model_dump()` which returns Python `UUID` objects. `_serializable_params()` calls `json.dumps()` internally — UUID objects raise `TypeError` and the entire `__workflow__` key is dropped silently.

**Fix**: `_sync_back` now calls `WorkflowModel.model_validate(workflow_dict).model_dump(mode='json')` before storing, converting all UUID objects to strings — matching the format `group_selection()` uses when first creating the GroupNode.

### KeyboardInterrupt Crash (Ctrl+C in Terminal)
Pressing Ctrl+C in the terminal while the app was running caused a traceback crash through `NodeView.event()` at the C++/Python boundary of Qt's event loop.

**Fix** (two layers):
1. `signal.signal(signal.SIGINT, lambda *_: app.quit())` in `main()` intercepts SIGINT before it reaches Qt's event loop.
2. A 200 ms `QTimer` wakes the Python interpreter periodically so the signal is processed promptly.
3. `NodeView.event()` wraps `super().event(event)` in `try/except KeyboardInterrupt` as a safety net, calling `app.quit()` for a clean shutdown.
4. `sys.excepthook` now exits cleanly on `KeyboardInterrupt` instead of writing a crash log.

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+G` | Group / collapse selected nodes into a subgraph |
| `Ctrl+F` | Open canvas search bar |
| `Ctrl+M` | Toggle mini-map |
| `Tab` | Open node-search popup |
| `Ctrl+E` | Edit selected node in Node Builder |
| `Ctrl+R` | Reload selected node from disk |
| `Ctrl+Shift+R` | Reload all nodes |
| `F5` | Run workflow |
| `F` | Focus selected nodes |
| `Ctrl+B` | Toggle bypass on selected nodes |
| `Ctrl+G` | Wrap selection in backdrop |
| `Ctrl+C` / `Ctrl+V` | Copy / Paste nodes |
| `Delete` | Delete selected items |
| `Ctrl+Wheel` | Zoom canvas |

---

## Upgrade Notes

- Existing workflows containing GroupNodes saved before v2.0.0 may need to be re-grouped if the `__workflow__` key was previously lost due to the UUID serialization bug.
- `QScintilla` remains a required dependency (`pip install QScintilla`). It is bundled in the Windows release build.
- No breaking API changes for custom nodes or automation scripts.
