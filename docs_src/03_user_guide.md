# Vibrante-Node v2.4.0 — User Guide

This guide is the comprehensive reference for working with Vibrante-Node. It covers every UI element, interaction, and workflow concept in depth — from beginner navigation to advanced features like subgraphs, bypass mode, and live inspection.

---

## Table of Contents

1. [Canvas Navigation](#canvas-navigation)
2. [Node Widget Anatomy](#node-widget-anatomy)
3. [Port Types and Colors](#port-types-and-colors)
4. [Connecting Nodes](#connecting-nodes)
5. [Exec Flow Pins](#exec-flow-pins)
6. [Data-Only Nodes](#data-only-nodes)
7. [Node Search Popup](#node-search-popup)
8. [Right-Click Context Menu](#right-click-context-menu)
9. [Bypass Mode](#bypass-mode)
10. [Group Node / Subgraph](#group-node--subgraph)
11. [Sticky Notes](#sticky-notes)
12. [Backdrops / Network Boxes](#backdrops--network-boxes)
13. [Canvas Search Bar](#canvas-search-bar)
14. [Mini-map](#mini-map)
15. [Live Wire Value Inspector](#live-wire-value-inspector)
16. [Log Panel](#log-panel)
17. [Toolbar Reference](#toolbar-reference)
18. [Keyboard Shortcuts Reference](#keyboard-shortcuts-reference)
19. [Workflow Execution](#workflow-execution)
20. [Autosave and Crash Recovery](#autosave-and-crash-recovery)
21. [Recent Files](#recent-files)

---

## Canvas Navigation

The canvas is a `NodeView` (QGraphicsView) that renders a `NodeScene` (QGraphicsScene). You can navigate a canvas of any size smoothly with the following controls.

### Panning

| Method | Description |
|---|---|
| **Middle Mouse Button drag** | Pan in any direction |
| **Alt + Left Mouse Button drag** | Alternative pan (Houdini-style) |
| **Scroll wheel** | Pan vertically |
| **Shift + Scroll wheel** | Pan horizontally |

### Zooming

| Method | Description |
|---|---|
| **Ctrl + Scroll wheel** | Zoom in / out centred on cursor |
| **+** / **-** keys | Zoom in / out |

There is no fixed minimum or maximum zoom. You can zoom out far enough to see the entire workflow, or zoom in to individual port labels.

### Focus and Fitting

| Shortcut | Description |
|---|---|
| **F** | Fit selected nodes to the viewport. If nothing is selected, fit all nodes. |
| **Home** | Reset the view to the origin (0, 0) at 100% zoom |

### Rubber-Band Selection

Click and drag on an empty area of the canvas to draw a selection rectangle. All node widgets (and other items) whose bounding boxes intersect the rectangle are selected when you release the mouse button. Hold **Shift** while rubber-banding to add to the current selection without deselecting previously selected items.

### Scroll Bars

Standard scroll bars appear at the edges of the view when content extends beyond the visible area. They can be used alongside mouse-based navigation.

---

## Node Widget Anatomy

Every node on the canvas is a `NodeWidget` — a `QGraphicsItem` with a card-like appearance. Understanding its structure is essential for using the platform effectively.

```
+------------------------------------------------------+
|  [icon]  display_name                    [=] bypass  |  <- Header
+----------+------------------------------------------+
|  exec_in |                              | exec_out   |  <- Exec ports
|  string  |  [text widget____________]  | exec_out   |  <- Data port + widget
|  int     |  [0___________________]     |            |  <- Int widget
|  float   |  [0.0_________________]     | result     |  <- Output port
|  bool    |  [ ] checkbox label         |            |  <- Bool widget
|  list    |  (no widget, input only)    | list_out   |  <- List port
+----------+------------------------------------------+
```

### Header

The **header** is the top band of the node card. It shows:

- An optional icon (16x16 px) loaded from the `icon_path` field in the node definition.
- The node's **display name** — by default the `name` from the definition, but can be renamed by double-clicking the header text.
- A small **bypass toggle** button on the right (labelled `=`). Clicking it toggles bypass mode for this node.

The header background colour reflects the node's current execution state:

| State | Header Colour |
|---|---|
| Idle | Category-dependent (dark blue, purple, teal, etc.) |
| Running | Bright orange / amber |
| Finished (success) | Fades back to idle colour |
| Finished (error) | Red |
| Bypassed | Grey / dimmed |

### Input Ports (Left Side)

Input ports appear on the left edge of the node. Each port has:

- A **connector** — a circle (data) or square (exec). Click and drag from another node's output onto this to create a connection.
- A **label** — the port name.
- An optional **parameter widget** — rendered inside the node body to the right of the connector. Widgets appear only on input ports with a `widget_type` defined.

#### Parameter Widgets

| widget_type | Appearance | When to Use |
|---|---|---|
| `text` | Single-line text field | Short string values, paths, names |
| `text_area` | Multi-line text area | Code blocks, long descriptions |
| `int` | Integer spin box | Whole number values |
| `float` | Float spin box | Decimal number values |
| `checkbox` | Toggle checkbox | True / false values |
| `dropdown` | Dropdown combobox | Enumerated choices |
| `slider` | Slider with numeric readout | Clamped numeric ranges |
| `file` | Text field + browse button | File open paths |
| `file_save` | Text field + browse button | File save paths |

When an input port has an incoming data connection, **the widget is disabled** — the value comes from the wire, not from manual input.

### Output Ports (Right Side)

Output ports appear on the right edge of the node. They have a connector and a label but no editable widget — they display values set by `execute()`. After execution, hovering over a wire from an output port shows the last value via the live wire inspector.

### Resize Handle

Some node types that contain large text areas or multi-line code blocks have a resize handle at the bottom-right corner of the card. Drag it to make the node taller.

---

## Port Types and Colors

Port type determines what kind of data flows through a connection. The connector colour identifies the type at a glance.

| Type | Connector Shape | Colour | Widget Types Available | Description |
|---|---|---|---|---|
| `exec` | Square | White | None | Execution flow signal. True fires the downstream node. |
| `string` | Circle | Purple | text, text_area, dropdown, file, file_save | Text values of any length |
| `int` | Circle | Cyan | int, slider | Integer numbers |
| `float` | Circle | Orange | float, slider | Floating-point numbers |
| `bool` | Circle | Green | checkbox | Boolean True / False |
| `list` | Circle | Yellow | None | Python list of any content |
| `dict` | Circle | Tan/Brown | None | Python dict of any content |
| `any` | Circle | Light Grey | None | Untyped — accepts any value |

### Type Compatibility

The connection system enforces basic type compatibility when dragging wires:

- An output of type `string` can connect to an input of type `string` or `any`.
- An output of type `any` can connect to any input type.
- An output of type `exec` can only connect to an input of type `exec`.
- Mismatched typed connections (e.g. `float` output to `bool` input) show a warning cursor but are permitted — the value is passed as-is and the receiving node is responsible for handling the type.

If you need to convert between types, use a conversion node (e.g. pass an `int` output through a `string_concat` node to get a string representation) or handle the conversion in the receiving node's `execute()` code.

---

## Connecting Nodes

### Creating a Connection

1. **Hover** over an output port (right side of a node). The cursor changes to a crosshair.
2. **Click and drag** from the output port. A temporary preview wire follows the cursor.
3. **Release** over a compatible input port on another node. The connection is established and the wire snaps into place.

A curved Bezier wire appears between the two ports. The wire colour matches the data type of the source port.

### Single-Input Enforcement

Each data input port accepts **at most one incoming connection**. If you drag a new wire onto an input port that already has a connection, the old connection is removed and replaced by the new one. This prevents ambiguous data values.

Exec input ports follow the same rule — only one node can trigger a given `exec_in`.

### Disconnecting a Wire

- **Click and drag an existing wire** near its input end. The wire detaches and follows the cursor as a preview. Release on a new port to reconnect, or release on empty canvas to delete.
- **Right-click a port** and select "Disconnect" to remove all wires from that port.
- **Select a wire** by clicking near it (the 12 px wide hit area makes this easy) and press **Delete**.

### Fan-Out (Multiple Outputs from One Port)

A single **output** port can connect to **multiple** input ports. This is called a fan-out. Drag additional wires from the same output port to different destinations. All connected inputs receive the same value when the node executes.

---

## Exec Flow Pins

Exec pins are the white square connectors that appear on nodes with `use_exec: true` in their definition. They are the mechanism by which Vibrante-Node enforces execution order.

### What Exec Pins Do

- `exec_in` — a trigger input. When a connected upstream node fires its `exec_out`, this node's `execute()` method is called.
- `exec_out` — a trigger output. When a node's `execute()` returns `{"exec_out": True}` (or calls `await self.set_output("exec_out", True)`), every node connected to this `exec_out` is scheduled for execution.

### How Execution Chains Work

```
[Node A] --exec_out--> [exec_in Node B] --exec_out--> [exec_in Node C]
```

1. Node A runs. Its `execute()` returns `{"exec_out": True}`.
2. The engine follows the exec wire to Node B and runs it.
3. Node B runs. Its `execute()` returns `{"exec_out": True}`.
4. The engine follows the exec wire to Node C and runs it.

If Node A returns `{"exec_out": False}` (or does not include `exec_out` in its return dict), the chain stops. No downstream exec nodes run.

### Multiple Exec Outputs

Some nodes have more than one exec output pin to implement branching:

```
[if_condition]
    |-- true_out  --> [run if true]
    |-- false_out --> [run if false]
```

Only the output whose value is `True` fires. The other chain does not run.

The `GroupNode` has two exec outputs:

- `exec_out` — fires when the inner subgraph completes without an unhandled exception.
- `exec_fail` — fires only when an unhandled Python exception propagates out of the inner graph.

### Sequence Node

The `sequence` builtin node fires `out_1`, `out_2`, and so on sequentially — it waits for each downstream chain to complete before firing the next. Use it to enforce order among otherwise-independent branches.

### What Fires First — Entry Nodes

If a node has an `exec_in` port but nothing is connected to it, the engine treats it as an **entry node** and fires it automatically at the start of execution. This lets you run a workflow without needing a dedicated "Start" trigger node.

---

## Data-Only Nodes

Some nodes have no exec pins at all (their JSON definition has `use_exec: false`). Examples: `variable_node`, `add`, `string_length`, `random_float`, `get_dict_value`.

These nodes are **evaluated lazily**: they do not appear in the initial execution schedule. Instead, when an exec-driven node needs a value from a data-only node, the engine automatically runs the upstream data node first (the "pull" mechanism).

This means:

- Data-only nodes never need to be wired into an exec chain.
- They can be reused — if multiple exec nodes read the same data-only node's output, the data node runs once per exec node that needs it (subject to caching rules).
- They can be wired together in chains: the engine follows data connections backward until it reaches a node with no unfulfilled data inputs.

### Loop Invalidation

Inside a `for_each` or `while_loop`, the engine **invalidates** cached data node results each iteration. This ensures that nodes like `get_list_item` (whose output depends on the current loop index) produce fresh results each time, not a stale cached value from the first iteration.

---

## Node Search Popup

Press **Tab** anywhere on the canvas to open the node search popup. The popup is a floating panel that appears at the current cursor position.

### Searching

Type any part of the node's name or `node_id`. The list updates in real time, filtering to matches. The search is case-insensitive and matches substrings, so typing `geo` shows `create_geo`, `delete_geo`, `node_geo_info`, etc.

### Adding a Node

- **Click** a result to add it at the cursor position.
- **Press Enter** to add the first result.
- **Arrow keys** navigate the list.

The node is placed on the canvas at the position where you pressed Tab, then the popup closes.

### Closing Without Adding

Press **Escape** or click anywhere outside the popup to close it without adding a node.

---

## Right-Click Context Menu

Right-clicking a **node widget** opens its context menu. Right-clicking **empty canvas** opens a different menu.

### Node Context Menu

| Item | Action | Shortcut |
|---|---|---|
| **Edit Node** | Open this node in the Node Builder dialog | Ctrl+E |
| **Reload Node** | Re-read this node's JSON from disk and apply changes | Ctrl+R |
| **Bypass Node** | Toggle bypass on this node | Ctrl+B |
| **Duplicate** | Copy this node and paste it at an offset position | |
| **Group Selection** | Collapse selected nodes into a GroupNode | Ctrl+Shift+G |
| **Wrap in Backdrop** | Wrap selected nodes in a labelled backdrop | Ctrl+G |
| **Set as Init Node** | Mark this node as an init-priority node (runs before the main graph) | |
| **Delete** | Remove this node and all its connections | Delete |

### Canvas Context Menu (Empty Area)

| Item | Action |
|---|---|
| **Add Node** | Open the node search popup |
| **Add Sticky Note** | Place a new sticky note at this position |
| **Add Backdrop** | Place a new backdrop at this position |
| **Paste** | Paste the clipboard contents at this position |

---

## Bypass Mode

Bypass mode makes the engine skip a node entirely, as if it were not there, while still passing execution along. This is useful for temporarily disabling a step without deleting it.

### Activating Bypass

- Select one or more nodes and press **Ctrl+B**.
- Click the **bypass toggle button** (`=`) in the node's header.
- Right-click a node and choose **Bypass Node**.

A bypassed node is visually dimmed (grey header). The `bypassed` flag is saved with the workflow.

### What Bypass Does During Execution

When the engine encounters a bypassed node:

1. It emits `node_started` and immediately `node_finished(success)` without calling `execute()`.
2. It fires all exec output connections, so the exec chain continues to downstream nodes.
3. Data output ports remain at their default values (empty string, 0, empty list, etc.). Downstream nodes that read data from a bypassed node receive the default value.

This means bypass is safe for exec chain nodes — the flow continues — but may produce incorrect data values if downstream nodes depend on a bypassed node's data output. For data-only nodes, bypassing them causes their consumers to receive default values.

---

## Group Node / Subgraph

The Group Node feature lets you collapse any selection of connected nodes into a single reusable **GroupNode** widget. The inner graph is fully preserved and editable.

### Creating a GroupNode

1. Select two or more nodes on the canvas (rubber-band or Shift+click).
2. Press **Ctrl+Shift+G** (or right-click > Group Selection, or Edit > Group Selection).

The engine analyses the connections crossing the boundary of the selection:

- Each **incoming data connection** (from an unselected node into the selection) becomes an **input port** on the GroupNode.
- Each **outgoing data connection** (from the selection to an unselected node) becomes an **output port** on the GroupNode.
- Exec connections are similarly mapped.

The selected nodes are removed from the canvas and a single **GroupNode** card appears at their centroid. External connections are rewired to the GroupNode's new ports.

```
Before grouping:
  [Node A] --str--> [Node B] --str--> [Node C] --> (external)

After grouping (B is inside the group):
  [Node A] --str--> [GroupNode] --str--> [Node C] --> (external)
                        ^
                    contains Node B
```

### Naming the Group

After creating a GroupNode, you can rename it by double-clicking its header text and typing a new name. This name appears as the tab label when you open the subgraph.

### Opening the Subgraph

**Double-click** the GroupNode to open its inner workflow in a new tab. The tab is labelled `[GroupName]`. The subgraph contains:

- The original inner nodes you selected.
- One `group_in` node per input port — this node injects the incoming value into the inner graph.
- One `group_out` node per output port — this node collects the inner result and routes it out.

### Editing the Subgraph

The subgraph tab is fully editable. You can:

- Add, delete, or move nodes.
- Create new connections.
- Change parameter values.
- Undo / redo changes.

Every edit is **automatically synchronised back** to the parent GroupNode. The parent workflow's history is also updated so that Ctrl+Z in the parent tab undoes subgraph edits.

### GroupNode Ports

A GroupNode always has these fixed exec ports:

| Port | Side | Description |
|---|---|---|
| `exec_in` | Input | Triggers the inner graph |
| `exec_out` | Output | Fires when the inner graph completes without error |
| `exec_fail` | Output | Fires only when an unhandled Python exception occurs inside |

Additional data ports are created dynamically from the boundary edges at grouping time.

### Execution Semantics

When a GroupNode executes:

1. The engine creates a sub-executor for the inner `WorkflowModel`.
2. It injects the GroupNode's input port values into the corresponding `group_in` nodes inside the subgraph.
3. The sub-executor runs the inner graph exactly like a top-level workflow.
4. When the inner graph finishes cleanly, `exec_out` fires.
5. If a node inside the inner graph raises an unhandled exception, `exec_fail` fires.
6. Data values from `group_out` nodes are mapped to the GroupNode's output ports and made available to external connections.

Note: `exec_fail` is for catastrophic failures only. If an inner node returns a "soft failure" (e.g. `success: False` without raising an exception), that is handled by the inner graph's own exec routing — `exec_fail` does not fire.

### Saving and Loading

GroupNodes are serialised transparently with the parent workflow. The inner `WorkflowModel` dict is stored in the `__workflow__` parameter of the GroupNode's `NodeInstanceModel`. Dynamic port definitions are stored in `__port_defs__`. The node name is stored in `__name__`. Everything is round-tripped correctly through JSON save/load.

---

## Sticky Notes

Sticky notes are free-floating text annotations on the canvas. They do not participate in execution.

### Adding a Sticky Note

- Right-click empty canvas and select **Add Sticky Note**.
- The note appears at the right-click position with default text "New Note".

### Editing

Double-click a sticky note to enter edit mode. Type your text. Click outside the note to confirm.

### Resizing

Drag the bottom-right resize handle to change the note dimensions.

### Moving

Drag the note by its header / body to reposition it.

### Deleting

Select the sticky note and press **Delete**, or right-click and choose **Delete**.

### Colour

Right-click a sticky note and choose a colour from the palette. Colours help visually distinguish note categories (e.g. yellow for warnings, green for completed sections, blue for links).

---

## Backdrops / Network Boxes

Backdrops are labelled rectangular regions that group and visually annotate areas of the canvas. Like sticky notes, they are annotations only — they do not affect execution.

### Adding a Backdrop

- Select nodes you want to wrap, then press **Ctrl+G** (or right-click > Wrap in Backdrop).
- Right-click empty canvas and select **Add Backdrop** to place an empty one.

### Labeling

The backdrop has a title bar at the top. Double-click the title to rename it.

### Resizing

Drag the bottom-right resize handle. Nodes inside the backdrop do not move automatically when the backdrop is resized — they are independent items that happen to be visually enclosed.

### Moving

Drag the backdrop title bar to move it. When you drag a backdrop, nodes that are fully contained within its bounds move with it.

### Colour

Right-click the backdrop and choose a background colour. Semi-transparent fill lets you see the nodes inside.

### Deleting

Select the backdrop and press **Delete**. The nodes inside are not deleted — only the backdrop frame is removed.

---

## Canvas Search Bar

The canvas search bar lets you locate any node on the canvas by name without having to scroll.

### Opening

Press **Ctrl+F** or go to **Edit > Find in Canvas**.

A floating panel appears at the top centre of the canvas:

```
+--------------------------------------------------+
|  [search text__________________]  3 / 12  [x]   |
+--------------------------------------------------+
```

### Searching

Type any part of a node's display name or `node_id`. The search updates as you type. The match counter shows "current / total" matches.

The first matching node is selected and the canvas pans to centre it in the viewport.

### Navigating Matches

| Action | Result |
|---|---|
| **Enter** or **Down Arrow** | Move to the next match |
| **Shift+Enter** or **Up Arrow** | Move to the previous match |

Each navigation step selects the matched node and pans the view.

### Closing

Press **Escape** or click the X button to close the search bar.

---

## Mini-map

The mini-map is a 200x150 pixel thumbnail of the entire canvas, always visible in the bottom-right corner of the `NodeView`.

```
+----------------------------+
|                            |
|   canvas (large)           |
|                            |
|               +----------+ |
|               | mini-map | |
|               | [  view  ]| |
|               | [  rect  ]| |
|               +----------+ |
+----------------------------+
```

### Viewport Indicator

A blue semi-transparent rectangle inside the mini-map shows the current viewport area. As you pan or zoom the main view, the rectangle updates.

### Navigating via Mini-map

Click or drag on the mini-map to pan the main view. The main view centres on the point you clicked in scene coordinates. This is useful for quickly jumping between distant parts of a large workflow.

### Toggling

Press **Ctrl+M** or go to **Window > Toggle Mini-map** to show or hide the mini-map. The toggle state is per-tab — different workflow tabs can have the mini-map in different states.

### Theme

The mini-map respects the current dark / light theme. Its background colour and viewport indicator match the active theme.

---

## Live Wire Value Inspector

After execution, the last value that flowed through every connected wire is stored and available for inspection.

### How to Use

**Hover your mouse over any connected wire.** A tooltip appears showing:

```
port_name: repr(value)
```

For example:

```
message: 'Hello, Vibrante-Node!'
```

```
result_path: '/obj/my_geo'
```

```
items: ['asset_A', 'asset_B', 'asset_C']
```

Long values are truncated at 300 characters to keep the tooltip readable.

### When Values Are Available

Values are stored immediately when a node calls `set_output()` or returns from `execute()`. They persist after execution completes. You can inspect any wire at any time after a run without needing to re-run.

### When Values Are Cleared

Values are cleared at the **start of each new execution run**. This ensures that stale values from a previous run do not appear alongside fresh values from the current run.

### Hit Area

The wire has a 12 px wide invisible hit zone (expanded from the visual 2 px line) so that hovering is easy even on closely-spaced wires.

---

## Log Panel

The log panel at the bottom of the window displays execution output in chronological order.

### Message Types

| Type | Colour | Source |
|---|---|---|
| `info` | Light grey | `self.log_info("msg")` in node code, or engine status messages |
| `success` | Green | `self.log_success("msg")` in node code |
| `error` | Red | `self.log_error("msg")` in node code, or unhandled exceptions |

### Execution Timing

After each node finishes, the engine automatically logs:

```
Node 'my_node_name' finished in 0.34s
```

This appears at `info` level. The time is measured with `time.perf_counter()` from when the engine calls `execute()` to when it returns.

### Inner Node Logs (GroupNode)

When a node runs inside a GroupNode, its log messages are forwarded to the main log panel with a prefix showing the GroupNode's display name:

```
[my_group] inner_node: operation complete
```

### Clearing the Log

Click the **Clear** button in the log panel toolbar (if present) or right-click the log area and select **Clear**.

### Error Details

When a node raises an unhandled exception, the engine logs the full traceback at `error` level. The node widget's header turns red. The exec chain stops at that node — downstream nodes do not run.

---

## Toolbar Reference

The toolbar below the menu bar provides quick access to the most common actions.

| Button | Action | Shortcut |
|---|---|---|
| **New** | Create a new empty workflow in a new tab | Ctrl+N |
| **Open** | Open a file picker to load a workflow | Ctrl+O |
| **Save** | Save the current workflow | Ctrl+S |
| **Run** | Execute the current workflow | F5 |
| **Stop** | Cancel a running execution | (toolbar only) |
| **Add Node** | Open the node search popup at the centre of the canvas | Tab |
| **Edit Node** | Open the selected node in the Node Builder | Ctrl+E |
| **Theme Toggle** | Switch between dark and light themes | (toolbar) |

---

## Keyboard Shortcuts Reference

### Global Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | New workflow tab |
| `Ctrl+O` | Open workflow |
| `Ctrl+S` | Save workflow |
| `Ctrl+Shift+S` | Save workflow as |
| `Ctrl+W` | Close current tab |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+C` | Copy selected nodes |
| `Ctrl+V` | Paste nodes |
| `F5` | Run workflow |

### Canvas Shortcuts

| Shortcut | Action |
|---|---|
| `Tab` | Open node search popup at cursor |
| `F` | Focus / fit selected nodes (or all if none selected) |
| `Delete` | Delete selected nodes and connections |
| `Ctrl+A` | Select all nodes |
| `Ctrl+D` | Deselect all |
| `Ctrl+B` | Toggle bypass on selected nodes |
| `Ctrl+E` | Edit selected node in Node Builder |
| `Ctrl+R` | Reload selected node from disk |
| `Ctrl+Shift+R` | Reload all nodes from disk |
| `Ctrl+G` | Wrap selection in backdrop |
| `Ctrl+Shift+G` | Group / collapse selection into GroupNode |
| `Ctrl+F` | Open canvas search bar |
| `Ctrl+M` | Toggle mini-map |
| `Ctrl+Wheel` | Zoom canvas |
| `Middle Mouse drag` | Pan canvas |
| `Alt+Left Mouse drag` | Pan canvas (Houdini-style) |

### Node Builder Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+S` | Save node definition |
| `Ctrl+Z` | Undo in code editor |
| `Ctrl+Y` | Redo in code editor |
| `Ctrl+Space` | Trigger autocomplete (QScintilla) |
| `Ctrl+Wheel` | Zoom code editor font |

---

## Workflow Execution

### Starting Execution

Press **F5** or click the **Run** button in the toolbar. The engine serialises the scene, builds the graph, instantiates all nodes, and begins executing.

### Async Behaviour

Execution is fully asynchronous. The Qt event loop remains active throughout, so:

- The UI remains interactive (you can scroll, inspect wires, read log messages).
- The Stop button works immediately.
- Long-running nodes (DCC calls, file I/O, network requests) do not freeze the application.

### What "Running" Means

While the engine is running:

- The **Run** button is disabled.
- The **Stop** button is enabled.
- Node widgets that are currently executing show an animated highlight.
- The log panel receives messages in real time.
- Live wire values update as each node completes.

### Parallel Execution

Multiple independent exec branches (entry nodes with no connections between them) run concurrently as separate `asyncio.Task` objects. Branches that depend on each other (through data connections or exec chains) are sequenced correctly by the engine.

### Stopping Mid-Execution

Click the **Stop** button or press the Stop shortcut. The engine sets an internal `_is_stopped` flag. All active `asyncio.Task` objects are cancelled. Nodes that check `self.is_stopped()` return `True`, allowing them to clean up gracefully. Nodes that are in the middle of awaiting a DCC operation may take a moment to notice the cancellation — `asyncio.CancelledError` is raised in their coroutine.

After stopping, `execution_finished(success=False)` is emitted and the UI is re-enabled.

### Init-Priority Nodes

Nodes can be marked as "init nodes" by setting a non-zero `init_priority` in their model (right-click node > Set as Init Node). Init nodes run **before** the main graph, in descending priority order. Higher numbers run first. The `prism_core_init` node uses this mechanism to initialise PrismCore before any `prism_*` nodes run.

Use init nodes for authentication, login, environment setup, or any one-time setup that all subsequent nodes depend on.

### Re-running

After a successful or failed execution, press **F5** again to re-run. The engine re-instantiates all nodes fresh — no state carries over between runs. The `BaseNode.memory` dict (shared between all nodes during a run) is cleared at the start of each run.

---

## Autosave and Crash Recovery

### Autosave

A background `QTimer` fires every **2 minutes** while the application is open. It writes all non-empty open workflow tabs to:

```
~/.vibrante_node_autosave.json
```

On Windows, `~` resolves to `C:\Users\<username>\.vibrante_node_autosave.json`.

The autosave file has this structure:

```json
{
    "version": 1,
    "tabs": [
        {
            "name": "tab_label",
            "file_path": "/path/to/saved/file.json",
            "workflow": {}
        }
    ]
}
```
<!-- `workflow` contains the full WorkflowModel dict serialized to JSON -->

Autosave is skipped during active execution (`_is_executing` flag prevents saving a mid-run state). Failures during autosave are printed to the Python console only — the application never crashes due to a failed autosave.

### Clean Exit

When you close the application normally (`Alt+F4`, File > Exit, or the window X button), `closeEvent` deletes the autosave file before exiting. This ensures the crash recovery dialog does not appear on the next normal launch.

### Crash Recovery

If the application crashes or is killed without calling `closeEvent` (e.g. a Python exception outside the event loop, OS-level kill, power loss), the autosave file is left on disk.

On the **next launch**, if the autosave file exists, a dialog box appears:

```
Unsaved session detected

The previous session ended unexpectedly.
Would you like to restore your open workflows?

  [ Restore ]  [ Discard ]
```

- **Restore** — opens all tabs from the autosave, using the saved `workflow` dict. Tabs that had been saved to disk are also correctly labelled with their file path.
- **Discard** — deletes the autosave file and opens fresh.

The autosave file is always deleted after the dialog, regardless of the user's choice.

---

## Recent Files

### Accessing Recent Files

**File > Open Recent** shows a submenu listing the last 10 workflow files you saved or loaded, newest first.

Each entry shows the full file path. Clicking an entry loads that workflow in a new tab — no file picker dialog appears.

### Greyed-Out Entries

If a file in the recent list no longer exists on disk (moved, renamed, deleted), its menu entry appears greyed out (disabled). You cannot click it. The entry remains in the list until you use **Clear Recent Files** or until it ages out as newer files push it off the bottom of the 10-item list.

### Clearing the List

**File > Open Recent > Clear Recent Files** empties the list immediately.

### When the List Updates

The recent files list is rebuilt every time the **File** menu opens. This ensures the list always reflects the current state of the filesystem and recent file history without requiring an app restart.

### Storage

Recent file paths are stored in the application config managed by `src/utils/config_manager.py` under the key `"recent_files"` as a JSON list of absolute path strings, capped at 10 entries, newest first.

---

## Advanced Topics

### Node Init Priority

When you right-click a node and choose **Set as Init Node**, the node is given an `init_priority` greater than zero. This causes the engine to run it before the main graph, as a setup step. You can set a specific priority value (higher values run earlier) to control the order of multiple init nodes.

Example use: a `prism_core_init` node with `init_priority: 10` runs before a `prism_login_token` node with `init_priority: 5`, which runs before all `prism_*` data nodes with `init_priority: 0`.

### Shared Memory Between Nodes

All nodes within a single execution run share a class-level `BaseNode.memory` dictionary:

```python
# Node A:
BaseNode.memory["my_key"] = "some_value"

# Node B (same run):
value = BaseNode.memory.get("my_key")  # "some_value"
```

This memory is cleared at the start of each run. It is intended for lightweight inter-node communication that does not warrant explicit data wires — for example, a login node storing an auth token that many downstream nodes read without each needing an explicit `token` input wire.

The `SetVariableNode` and `GetVariableNode` builtins use this mechanism to implement named variables accessible anywhere in the graph.

### The Python Script Node

The `python_script` node contains a text area where you write arbitrary Python code. It has:

- `exec_in` / `exec_out`
- `code` — a text area for your Python code
- `result` — an `any` output port

Your code runs via `exec()`. Assign to a local variable called `result` to pass a value to the output:

```python
import os
files = os.listdir("C:/assets")
result = [f for f in files if f.endswith(".abc")]
```

The `result` value is available on the `result` output port after execution.

### Exporting a Workflow as Python

**File > Export > Export as Python Script** converts the entire workflow into a standalone Python script that can run without the Vibrante-Node UI. This is useful for deploying a tested workflow on a render farm or server without installing the full application.

The exported script instantiates each node class, wires inputs manually, and calls `execute()` in topological order.

### Reloading Nodes from Disk

During development, you often modify a node's JSON file externally and want to see the changes without restarting the app.

- **Ctrl+R** — reload the selected node's definition from disk. Existing instances in the scene are updated.
- **Ctrl+Shift+R** — reload all node definitions. Useful after adding a new `.json` file to the `nodes/` directory.

The node registry re-reads the file, regenerates the Python class, and signals all matching `NodeWidget` instances to rebuild their ports.

---

*Vibrante-Node v2.4.0 — Released 2026-05-26*
