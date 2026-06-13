# Release Notes — Vibrante-Node v1.8.4

**Release date:** 2026-05-01
**Build:** Python 3.10 / PyInstaller — Windows 64-bit

---

## Overview

v1.8.4 bundles the post-v1.8.3 feature work that landed on the main branch: node reload-from-disk, init-first scene ordering, edit/add toolbar shortcuts, and a new in-app HTML help system. It also corrects the `for_loop` execution model and introduces an additional output port on `list_item_picker`.

---

## New Features

### Node Reload from Disk
Edit a node's JSON definition file, then reload all live canvas instances without re-adding the node.

- **`Ctrl+R`** — Reload selected node from disk. Ports are rebuilt, saved parameter values are re-applied, and connections whose port names still exist are preserved. Connections to removed ports are dropped.
- **`Ctrl+Shift+R`** — Reload All Nodes: re-reads every registered JSON node from disk and refreshes all live instances in every open scene.
- **Right-click → "Reload Node"** — same as `Ctrl+R` for the selected node.
- **`NodeRegistry.get_source_path(node_id)`** — returns the on-disk JSON path the node was loaded from.
- **`NodeRegistry.reload_node_definition(node_id)`** — re-reads and re-registers the definition from disk.
- **`NodeWidget.reload_definition(new_definition)`** — swaps the definition in-place and rebuilds the widget.
- **`NodeScene.reload_node_type(node_id)`** — orchestrates reload for all instances in the scene.

### Edit Node Shortcut
- **`Ctrl+E`** — Opens the Node Builder pre-loaded with the selected node's definition. After the builder closes, the node is automatically reloaded so canvas instances reflect any saved changes immediately.
- **Right-click → "Edit Node"** — same action from the context menu.

### Toolbar Additions
Five new toolbar buttons added to the main toolbar:
- **Add Node** — opens the node-search popup at the canvas centre (same as `Tab`).
- **Add Sticky Note** — adds a sticky note at the canvas centre.
- **Add Network Box** — adds a backdrop/network box at the canvas centre.
- **Edit Selected Node** — opens Node Builder (`Ctrl+E`).
- **Reload Selected Node** — reloads from disk (`Ctrl+R`).

### Init-First Scene Ordering
When loading a workflow, nodes with `init_priority > 0` (marked as Init First) are now created and wired up **before** all other nodes. This guarantees authentication or server-connect nodes are fully initialized before any downstream node is instantiated.

### HTML Help System
All documentation is now shipped as styled HTML files in the `docs/` folder. The Help menu opens these HTML files directly in the system browser, providing properly rendered headings, tables, and code blocks instead of raw Markdown text.

---

## Bug Fixes

### `for_loop` — exec_out Now Fires Once
`for_loop` previously fired `exec_out` once per index (acting as its own loop body). This caused issues when the downstream chain had side effects. `for_loop` now fires `exec_out` **once** after the full `indices` list is ready. Use a `loop_body` node connected to `indices` + `exec_out` to iterate per item.

### `on_parameter_changed` — Reactive Execution Propagation
When a node's `execute` produces an output that propagates to a downstream node mid-run, `on_parameter_changed` is now correctly called on the target instance. This allows reactive nodes (e.g. `TwoWaySwitchNode`, `GetVariable`) to update their own outputs when upstream data changes during execution — without the double-propagation bug fixed in v1.8.3.

### `list_item_picker` — Added `port_1` Output
A second output port `port_1` of type `any` has been added to `list_item_picker`.

---

## Keyboard Shortcuts Summary

| Shortcut | Action |
|---|---|
| `Tab` | Open node-search popup at canvas centre |
| `Ctrl+E` | Edit selected node in Node Builder |
| `Ctrl+R` | Reload selected node from disk |
| `Ctrl+Shift+R` | Reload all nodes from disk |
| `F5` | Run workflow |
| `F` | Focus on selected nodes |
| `Ctrl+C` / `Ctrl+V` | Copy / Paste selected nodes |
| `Delete` | Delete selected items |

---

## Upgrade Notes

- **`for_loop` users**: If your graph relied on `for_loop` firing `exec_out` per iteration, insert a `loop_body` node between `for_loop.exec_out` → `loop_body.exec_in` and connect `for_loop.indices` → `loop_body.items`. The `loop_body` fires `exec_out` once per item.
- The `docs/` folder is now required alongside the executable. It is included automatically in the PyInstaller build.
