# Release Notes — Vibrante-Node v2.1.0

**Release date:** 2026-05-14
**Build:** Python 3.10 / PyInstaller — Windows 64-bit
**Previous release:** v2.0.0 (2026-05-10)

---

## Overview

v2.1.0 is a UX quality-of-life release. It adds unsaved-changes tracking across all workflow tabs, a port type mismatch warning in the log panel, and fixes two regressions introduced in v2.0.0: the F5 / Shift+F5 execute shortcuts were wired to tooltips but never registered as actual key bindings, and loading a saved workflow incorrectly stamped a `*` dirty marker on its tab.

---

## New Features

### Unsaved Changes Detection

Every workflow tab now tracks whether it has been modified since the last save.

- A `*` prefix is prepended to the tab label as soon as the first edit is made (e.g. `my_graph.json` → `* my_graph.json`).
- The marker is removed automatically when the workflow is saved (Ctrl+S or File → Save).
- **Closing a dirty tab** (via the ✕ button) shows a **Save / Discard / Cancel** dialog before the tab is removed.
- **Closing the application** with one or more dirty tabs shows the same dialog for each dirty tab in order. Clicking Cancel on any tab aborts the close entirely.
- Loading a workflow from disk, opening via Recent Files, restoring from autosave, or opening a subgraph tab all start in a clean (unmarked) state.

### Port Type Mismatch Warning

Connecting two ports whose data types are incompatible now logs a `warning` in the log panel immediately after the connection is made:

```
Type mismatch: 'NodeA.result' (string) → 'NodeB.count' (int)
```

- The connection is **still allowed** — the warning is informational only.
- Ports typed `any` (including all exec flow pins) are always considered compatible and never trigger the warning.
- The warning respects the log panel's warning filter toggle.

---

## Bug Fixes

### F5 / Shift+F5 Keyboard Shortcuts Not Firing

The Execute and Stop toolbar buttons showed `F5` and `Shift+F5` in their tooltips, but `setShortcut()` was never called. Pressing F5 had no effect.

**Fix:** Added `self.execute_btn.setShortcut("F5")` and `self.stop_btn.setShortcut("Shift+F5")` in `_init_toolbar()`.  
**File:** `src/ui/window.py`

### Loaded Workflows Showing `*` Dirty Marker

Opening a previously saved workflow (via File → Open, Open Recent, or autosave restore) immediately stamped `*` on the tab label, making a clean file appear unsaved.

**Root cause:** `from_workflow_model()` internally calls `connect_nodes()`, `add_sticky_note()`, and `add_backdrop()`, each of which calls `push_history()`. The new dirty-tracking logic in `push_history()` fired `dirty_changed(True)` during the load, stamping `*` before the user touched anything.

**Fix:** `from_workflow_model()` now saves and restores `_undoing` around its entire body (`self._undoing = True`). While the flag is set, `push_history()` returns immediately (existing guard: `if self._undoing: return`), suppressing all nested history and dirty-state calls. `undo()` / `redo()` already set `_undoing = True` before calling `from_workflow_model()`, so this pattern nests correctly with no side effects.  
**File:** `src/ui/canvas/scene.py`

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+G` | Group / collapse selected nodes into a subgraph |
| `Ctrl+F` | Open canvas search bar |
| `Ctrl+M` | Toggle mini-map |
| `F5` | **Run workflow** *(was broken — now fixed)* |
| `Shift+F5` | **Stop workflow** *(was broken — now fixed)* |
| `Tab` | Open node-search popup |
| `Ctrl+E` | Edit selected node in Node Builder |
| `Ctrl+R` | Reload selected node from disk |
| `Ctrl+Shift+R` | Reload all nodes |
| `Ctrl+D` | Duplicate selected nodes in place |
| `Ctrl+B` | Toggle bypass on selected nodes |
| `Ctrl+G` | Wrap selection in backdrop |
| `Ctrl+C` / `Ctrl+V` | Copy / Paste nodes |
| `F` | Focus / fit selected nodes |
| `Delete` | Delete selected items |
| `Ctrl+Wheel` | Zoom canvas |

---

## Architecture Notes (for contributors)

### `NodeScene.dirty_changed` signal (`src/ui/canvas/scene.py`)
- `dirty_changed = Signal(bool)` — fires `True` on the first edit after a clean state; fires `False` when `mark_clean()` is called.
- `push_history()` emits `dirty_changed(True)` only on the clean→dirty transition (not on every edit).
- `mark_clean()` resets `_dirty` and emits `dirty_changed(False)` — called by `MainWindow` after every successful save.
- `from_workflow_model()` gates all nested `push_history()` calls with `_undoing = True` so loading never triggers the dirty signal.

### `MainWindow._update_tab_dirty_marker(view, dirty)` (`src/ui/window.py`)
- Connected to `scene.dirty_changed` for every new tab created by `add_new_workflow()`.
- Prepends `"* "` to the tab text when `dirty=True`; strips it when `dirty=False`.
- Uses identity comparison (`is`) to find the correct tab, guarding against name collisions.

### `NodeScene._get_port_data_type(port)` (`src/ui/canvas/scene.py`)
- Private helper that reads `.type` (PortModel) or `.data_type` (Port base class), falling back to `"any"`.
- Used by `mouseReleaseEvent()` to check compatibility before logging the type mismatch warning.

---

## Upgrade Notes

- No breaking changes for custom nodes or automation scripts.
- No new dependencies.
- Existing saved workflows open cleanly with no `*` marker.
- The `_dirty` and `_undoing` flags on `NodeScene` are internal — do not set them directly from node `python_code`.
