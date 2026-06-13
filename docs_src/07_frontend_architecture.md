# 07 — Frontend Architecture

**Vibrante-Node v2.5.0 — Technical Reference**

This document describes the Qt5 widget hierarchy, rendering pipeline, event model, history system, and all supporting UI subsystems. It targets contributors who need to understand the canvas, add new UI panels, create custom graphics items, or modify how nodes and edges are drawn.

> **Architecture note:** The UI Layer described in this document is the primary interface for Vibrante-Node users. The execution engine (`src/core/engine.py`) and Runtime Layer (`src/runtime/`) are designed to be fully decoupled from Qt — they can additionally be used headlessly from `scripts/run_vibrante_mcp.py` for advanced automation without a display server. The frontend and backend are decoupled at the `NetworkExecutor` boundary: the executor calls node `execute()` coroutines; the UI listens to its Qt signals. Nothing in `src/runtime/` or `src/core/engine.py` imports from `src/ui/`.

---

## Table of Contents

1. [Widget Hierarchy](#1-widget-hierarchy)
2. [MainWindow](#2-mainwindow)
3. [NodeScene (QGraphicsScene)](#3-nodescene-qgraphicsscene)
4. [NodeView (QGraphicsView)](#4-nodeview-qgraphicsview)
5. [NodeWidget Rendering](#5-nodewidget-rendering)
6. [PortWidget](#6-portwidget)
7. [Edge (Wire) Rendering](#7-edge-wire-rendering)
8. [MiniMap](#8-minimap)
9. [CanvasSearchBar](#9-canvassearchbar)
10. [NodeSearchPopup](#10-nodesearchpopup)
11. [Event Flow: Creating a Connection](#11-event-flow-creating-a-connection)
12. [History (Undo/Redo)](#12-history-undoredo)
13. [Serialization (Scene to/from WorkflowModel)](#13-serialization-scene-tofrom-workflowmodel)
14. [Theme System](#14-theme-system)
15. [LibraryPanel](#15-librarypanel)
16. [LogPanel](#16-logpanel)
17. [ScriptingConsole](#17-scriptingconsole)
18. [NodeBuilderDialog](#18-nodebuilderdialog)
19. [CodeEditor](#19-codeeditor)
20. [How to Add a New UI Panel](#20-how-to-add-a-new-ui-panel)
21. [Custom Graphics Items](#21-custom-graphics-items)
22. [Stylesheet Architecture](#22-stylesheet-architecture)
23. [StickyNote and Backdrop](#23-stickynote-and-backdrop)

---

## 1. Widget Hierarchy

The complete Qt widget tree for one open tab:

```
QMainWindow (MainWindow)
│
├── QTabWidget (self.tabs)                   [central widget]
│   │
│   └── [per tab] QWidget → QVBoxLayout
│         └── NodeView (QGraphicsView)
│               │
│               ├── [child widget] CanvasSearchBar (QFrame)
│               │     └── QHBoxLayout
│               │           ├── QLineEdit  (search input)
│               │           ├── QLabel     (match counter)
│               │           ├── QToolButton ▲ prev
│               │           ├── QToolButton ▼ next
│               │           └── QToolButton ✕ close
│               │
│               └── [child widget] MiniMap (QGraphicsView)
│                     shares the same QGraphicsScene as NodeView
│
│   QGraphicsScene (NodeScene)              [not a widget; managed by NodeView]
│         │
│         ├── NodeWidget items              [QGraphicsItem]
│         │     ├── header rect (QPainter)
│         │     ├── PortWidget items (QGraphicsEllipseItem)
│         │     └── QGraphicsProxyWidget   [per input parameter]
│         │           └── QLineEdit / QSpinBox / QCheckBox / QComboBox / ...
│         │
│         ├── Edge items                   [QGraphicsPathItem]
│         │
│         ├── StickyNote items             [QGraphicsItem]
│         │
│         └── Backdrop items               [QGraphicsRectItem]
│
├── QDockWidget "Node Library" (LibraryPanel)   [left dock]
│     └── QVBoxLayout
│           ├── QLineEdit (search filter)
│           └── DraggableTreeWidget (QTreeWidget)
│
├── QDockWidget "Log" (LogPanel)                [bottom dock]
│     └── QTextEdit
│
├── QDockWidget "Scripting Console"             [bottom dock, tabbed with Log]
│     └── QVBoxLayout
│           ├── QPlainTextEdit (output)
│           └── QLineEdit (input)
│
└── QStatusBar
```

---

## 2. MainWindow

`MainWindow` (`src/ui/window.py`) is the application's top-level window. It owns:

- The `QTabWidget` with one tab per open workflow.
- The `LibraryPanel`, `LogPanel`, and `ScriptingConsole` dockable panels.
- The main menu bar and toolbar.
- The `_EventLoopRunner` that drives execution.
- The autosave timer (`QTimer`, 2-minute interval).
- `_node_start_times` — a `Dict[UUID, float]` that records `time.perf_counter()` when each node starts, enabling elapsed-time logging.

### Tab management

Each tab wraps a `NodeView → NodeScene` pair. The tab label is the workflow filename (or "Untitled N" for new workflows). Tabs are closable; `_close_tab()` prompts for unsaved changes.

`add_new_workflow(name)` creates a new `NodeScene`, wraps it in a `NodeView`, adds the pair to the `QTabWidget`, and connects the necessary signals. It is also called by `_open_subgraph_tab()` when the user double-clicks a `GroupNode`.

### Signal connections (engine → UI)

```python
executor.node_started.connect(self._on_node_started)
executor.node_finished.connect(self._on_node_finished)
executor.node_error.connect(self._on_node_error)
executor.node_output.connect(self._on_node_output)
executor.node_log.connect(self._on_node_log)
executor.execution_finished.connect(self._on_execution_finished)
```

`_on_node_started` records start time and calls `widget.set_executing(True)` to highlight the node on canvas.
`_on_node_finished` computes elapsed time, logs it, calls `widget.set_executing(False)`.
`_on_node_output` calls `widget.set_parameter(port_name, value)` for each output key, and calls `scene.update_edge_value(widget, port_name, value)` for wire inspector tooltips.

### Autosave

`_autosave()` is called every 2 minutes. It serialises all non-empty tabs to `~/.vibrante_node_autosave.json`:

```json
{
  "version": 1,
  "tabs": [
    {"name": "tab label", "file_path": "/path/or/empty", "workflow": {}}
  ]
}
```
<!-- `workflow` contains the full WorkflowModel dict serialized to JSON -->

Empty tabs and the `_is_executing` guard prevent spurious writes. On next startup, `_try_restore_autosave()` checks for this file and shows a restore dialog. On clean exit (`closeEvent`), the file is deleted so the dialog never appears unnecessarily.

### Recent files

`MainWindow._add_recent_file(path)` is called after every successful save or load. It delegates to `config.add_recent_file(path)` in `src/utils/config_manager.py`, which keeps a JSON list of up to 10 absolute paths (newest first). The **Open Recent** submenu is rebuilt dynamically by `_rebuild_recent_menu()` on `file_menu.aboutToShow`. Files that no longer exist on disk are shown grayed-out (disabled actions).

---

## 3. NodeScene (QGraphicsScene)

`NodeScene` (`src/ui/canvas/scene.py`) is the model for a single workflow tab. It manages all graphics items and owns the history stack.

### Key attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `nodes` | `List[NodeWidget]` | All node items in scene order |
| `edges` | `List[Edge]` | All wire items |
| `sticky_notes` | `List[StickyNote]` | All sticky note items |
| `backdrops` | `List[Backdrop]` | All backdrop items |
| `history` | `List[dict]` | Undo stack (snapshots, max 50) |
| `redo_stack` | `List[dict]` | Redo stack |
| `_undoing` | `bool` | Guard to prevent history writes during undo/redo |
| `_sync_callback` | `Callable` or `None` | Set by MainWindow for subgraph tab two-way sync |
| `file_path` | `str` or `None` | Last saved path for this tab |

### Background grid

`NodeScene.drawBackground()` paints a dot-grid using `grid_pen` (color `#555555`, width 0.5). The grid spacing is `grid_size = 20` scene units. The grid is drawn in scene coordinates, so it scales with zoom automatically.

### History (undo/redo)

`push_history()` snapshots the entire scene to a `WorkflowModel.model_dump()` dict and appends it to `history`. It also clears `redo_stack` and, if `_sync_callback` is set, calls it with the new snapshot.

`undo()` pops the last snapshot, pushes the current state to `redo_stack`, and calls `from_workflow_model(model)` to restore.

`redo()` does the reverse.

The maximum history depth is 50 snapshots. Older entries are discarded from the front of the list.

### Scene communication: _sync_callback

When `MainWindow._open_subgraph_tab()` opens a `GroupNode`'s inner graph in a new tab, it sets `scene._sync_callback` to a closure that writes every change back to the parent `GroupNode`'s `parameters["__workflow__"]` and pushes the parent scene's history. This makes subgraph tabs fully editable with two-way sync to the parent workflow.

### Node search from scene

`NodeScene.add_node_by_name(node_id, scene_pos)` looks up the definition in `NodeRegistry`, creates a `NodeWidget`, positions it at `scene_pos`, and adds it to the scene. Returns the created widget or `None` on failure.

### Grouping

`NodeScene.group_selection()` (triggered by Ctrl+Shift+G) collapses selected nodes into a `GroupNode`. The algorithm:

1. Classify edges incident on selected nodes as internal, boundary_in, boundary_out, boundary_exec_in, or boundary_exec_out.
2. Build a `WorkflowModel` containing the selected nodes plus synthetic `GroupInNode` and `GroupOutNode` instances for each boundary port.
3. Remove selected nodes and their edges.
4. Create a `GroupNode` widget at the centroid; populate `__workflow__`, `__port_defs__`, `__name__` parameters; call `rebuild_ports()`.
5. Reconnect external edges to the new `GroupNode`'s ports.

---

## 4. NodeView (QGraphicsView)

`NodeView` (`src/ui/canvas/view.py`) is the viewport for one workflow tab. It handles all user interaction at the canvas level.

### Rendering hints

```python
self.setRenderHint(QPainter.Antialiasing)
self.setRenderHint(QPainter.SmoothPixmapTransform)
self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
```

`AnchorUnderMouse` means zoom (Ctrl+Wheel) keeps the point under the cursor fixed in scene space.

### Pan

Middle-mouse button or Alt+Left drag initiates panning. Pan is implemented by directly adjusting horizontal and vertical scrollbar values rather than using `QGraphicsView.ScrollHandDrag`, to avoid interfering with rubber-band selection.

Spacebar shows an `OpenHandCursor` as a visual hint; actual panning starts on the next mouse press while space is held.

### Zoom

Ctrl+Wheel scales the view by `1.25` (in) or `0.8` (out). After each zoom, `mini_map.refresh()` is called to redraw the viewport indicator.

### Keyboard shortcuts (handled in NodeView.keyPressEvent)

| Key | Action |
|-----|--------|
| Tab | Open `NodeSearchPopup` |
| F | `focus_on_selection()` — fit selected items (or all items) in view |
| Ctrl+B | Toggle bypass on selected nodes |
| Ctrl+G | Wrap selected nodes in a Backdrop |
| Ctrl+Shift+G | Group selected nodes into a `GroupNode` (scene.group_selection) |
| Ctrl+F | Show `CanvasSearchBar` (via `MainWindow._find_in_canvas`) |
| Delete / Backspace | Delete selected items (handled in NodeScene) |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z / Ctrl+Y | Redo |
| Ctrl+C / Ctrl+V | Copy / Paste selected nodes |
| Escape | Clear selection |

### Drag-and-drop from LibraryPanel

`NodeView.dropEvent()` reads `application/x-node-id` from the MIME data (set by `DraggableTreeWidget`), maps the drop position to scene coordinates via `mapToScene()`, and calls `scene.add_node_by_name(node_id, pos)`.

### Mini-map hosting

`NodeView.__init__` creates one `MiniMap` child widget and attaches it to the scene. The mini-map is repositioned in `resizeEvent` via `_mini_map.reposition()`. Scrollbar `valueChanged` signals connect to `_mini_map.refresh()` so the viewport indicator redraws whenever the user pans.

---

## 5. NodeWidget Rendering

`NodeWidget` (`src/ui/node_widget.py`) is a `QGraphicsItem` subclass. It renders the node box using `QPainter` calls in `paint()` rather than Qt's built-in rectangle items, giving full control over the visual style.

### Structure

```
NodeWidget (QGraphicsItem)
│
├── Header rect  (painted via QPainter.fillRect + QPainter.drawText)
│     background: category color (configurable per node category)
│     text: node.name + optional icon (SVG loaded via QSvgRenderer)
│
├── Body rect    (painted via QPainter.fillRect)
│     background: dark gray (#2a2a2a dark, lighter in light theme)
│
├── PortWidget items (QGraphicsEllipseItem, added as child items)
│     left side: input ports
│     right side: output ports
│
└── QGraphicsProxyWidget items (one per input port with a widget_type)
      embedded QWidget (QLineEdit, QSpinBox, QDoubleSpinBox,
                        QCheckBox, QComboBox, QSlider, QTextEdit, QPushButton)
```

### Proxy widgets and z-ordering

`QGraphicsProxyWidget` items embed regular Qt widgets into the scene. A custom `QComboBox` subclass (`node_widget.py`) overrides `showPopup()` to display the dropdown as a `QMenu` (a native OS window) instead of a popup inside the proxy, because composite layers from other proxy widgets would otherwise paint on top of the dropdown.

### Bypassed rendering

When `node.bypassed` is `True`, `NodeWidget.paint()` draws the header with reduced opacity and a diagonal strikethrough line, and the body background uses a distinct "bypassed" color. `set_bypassed(value)` toggles this flag and calls `update()` to trigger a repaint.

### Execution state highlighting

`set_executing(True)` draws a colored border around the node (typically orange/amber). `set_executing(False)` removes it. This is driven by `MainWindow._on_node_started` and `_on_node_finished`.

### Parameter synchronization

`set_parameter(port_name, value)` updates the in-scene widget to reflect a new value. For dropdowns, if `value` is a list, it updates the dropdown options. This is called by `MainWindow._on_node_output` to show live output values in the node's own UI as execution proceeds.

---

## 6. PortWidget

`PortWidget` (`src/ui/port_widget.py`) is a `QGraphicsEllipseItem` that represents one input or output port. It stores a reference to the `Port` definition and knows its parent `NodeWidget`.

### Colors

Port color is determined by `data_type`:

| data_type | Color |
|-----------|-------|
| `exec` | White (light mode: black) |
| `string` | Green |
| `int` | Cyan |
| `float` | Yellow |
| `bool` | Orange |
| `list` | Purple |
| `any` | Gray |

The color is applied as the ellipse fill brush. Edge (`Edge._refresh_color()`) reads the color from `from_port.brush().color()` to match the wire to its source port.

### Hit area

The port ellipse is typically 10×10 scene units. Port detection during wire dragging uses `scene.itemAt()` with a small tolerance rectangle.

### get_scene_pos()

`PortWidget.get_scene_pos()` returns the center of the port ellipse in scene coordinates. `Edge.update_path()` calls this on both endpoints to compute the bezier control points.

---

## 7. Edge (Wire) Rendering

`Edge` (`src/ui/canvas/edge.py`) is a `QGraphicsPathItem` that renders as a cubic bezier curve from one `PortWidget` to another.

### Bezier geometry

```python
pos_start = self.from_port.get_scene_pos()
pos_end   = self.to_port.get_scene_pos() if self.to_port else self.pos_end

dx   = pos_end.x() - pos_start.x()
dist = max(abs(dx) * 0.5, 20)   # ensures minimum curvature even for vertical wires

ctrl1 = QPointF(pos_start.x() + dist, pos_start.y())
ctrl2 = QPointF(pos_end.x()   - dist, pos_end.y())

path = QPainterPath()
path.moveTo(pos_start)
path.cubicTo(ctrl1, ctrl2, pos_end)
self.setPath(path)
```

The horizontal offset of the control points scales with the horizontal distance between ports. Ports directly above/below each other produce a gentle S-curve (dist = 20); ports far apart produce a wide arc.

### Color

The wire inherits the color of `from_port.brush().color()`. In light theme, if the color is near-white (lightness > 200), it is overridden to black for visibility.

### 12-pixel hit area

`Edge.shape()` overrides the default shape (which is the path itself, only 2 px wide) to return a 12-pixel stroked version:

```python
def shape(self):
    stroker = QPainterPathStroker()
    stroker.setWidth(12)
    return stroker.createStroke(self.path())
```

This widens the hover and selection zone to 12 screen pixels, making it easy to click or hover over thin wires in a dense graph.

### Live value tooltip

`set_live_value(value)` stores the value and sets a Qt tooltip:

```python
s = repr(value)
if len(s) > 300:
    s = s[:297] + "..."
self.setToolTip(f"{port_name}: {s}" if port_name else s)
```

Qt automatically shows the tooltip when the user hovers over the edge's hit area. Values persist after execution ends and are cleared only when the next run starts (by `NodeScene.clear_edge_values()`).

### Temporary edge during drag

While the user drags a new wire from a port, `NodeScene.active_edge` holds an `Edge` instance with `to_port=None`. `NodeScene.mouseMoveEvent` calls `active_edge.set_end_pos(scene_pos)` on every move. On release over a compatible port, `to_port` is set and the connection is registered. On release over empty space, the temporary edge is removed.

---

## 8. MiniMap

`MiniMap` (`src/ui/canvas/mini_map.py`) is a secondary `QGraphicsView` that shares the same `QGraphicsScene` as the parent `NodeView`. Qt renders the full scene into both views automatically.

### Fixed size and position

The mini-map is always 200×150 pixels (constants `_W`, `_H`). It is positioned 8 pixels from the bottom-right corner of its parent `NodeView` via `reposition()`:

```python
def reposition(self):
    pv = self._main_view
    self.move(pv.width() - self.width() - 8,
              pv.height() - self.height() - 8)
```

`reposition()` is called in `NodeView.resizeEvent`.

### Scene fit with debouncing

When scene items change (nodes added, moved, deleted), `scene.changed` fires. `_schedule_fit` starts an 80 ms single-shot `QTimer`. When the timer fires, `_do_fit()` calls `fitInView(scene.itemsBoundingRect() + _PAD, Qt.KeepAspectRatio)`. The debounce prevents the mini-map from re-fitting on every tiny move during a drag, which would cause visible flickering.

### Viewport indicator

`drawForeground()` is called by Qt after the scene thumbnail is painted. It converts the main view's viewport rectangle into scene coordinates and draws a semi-transparent blue rectangle:

```python
def drawForeground(self, painter, rect):
    mv = self._main_view
    vp = mv.viewport().rect()
    scene_rect = QRectF(mv.mapToScene(vp.topLeft()),
                        mv.mapToScene(vp.bottomRight()))
    painter.setBrush(QBrush(QColor(100, 180, 255, 35)))   # very light fill
    painter.setPen(QPen(QColor(100, 180, 255, 200), 1.5)) # visible outline
    painter.drawRect(scene_rect)
```

### Click-to-pan

`setInteractive(False)` prevents any mouse event from reaching the scene items through the mini-map. Instead, `mousePressEvent` and `mouseMoveEvent` are overridden to call `_pan_to(mini_pos)`:

```python
def _pan_to(self, mini_pos):
    scene_pos = self.mapToScene(mini_pos)
    self._main_view.centerOn(scene_pos)
    self.update()
```

This pans the main view so that `scene_pos` is centred in the main viewport. The viewport indicator redraws immediately via `update()`.

**Do not** set `setInteractive(True)` on the mini-map — it would allow users to accidentally move nodes by clicking the thumbnail.

---

## 9. CanvasSearchBar

`CanvasSearchBar` (`src/ui/canvas/canvas_search_bar.py`) is a floating `QFrame` that is a child widget of `NodeView`, positioned at the top-centre via `move(x, 8)`.

### Show / hide

`show_bar()` repositions the bar, shows it, gives focus to the `QLineEdit`, and immediately runs a search with the current text (in case the bar was hidden with text still in it). `hide_bar()` hides the bar, clears all state, and returns focus to `NodeView`.

### Search logic

`_on_text_changed()` is connected to `QLineEdit.textChanged`. It filters `scene.nodes` by matching the query against `node_definition.name.lower()` and `node_definition.node_id.lower()`:

```python
self._matches = [
    w for w in scene.nodes
    if t in w.node_definition.name.lower()
    or t in getattr(w.node_definition, 'node_id', '').lower()
]
```

### Navigation

`_go_next()` and `_go_prev()` increment/decrement `_current_idx` (modulo `len(_matches)`). Each call updates the match counter label and pans the main view to the matched node via `self._view.centerOn(node)`. The matched node is also selected so it is visually highlighted.

### Keyboard handling

`keyPressEvent` intercepts:
- `Escape` → `hide_bar()`
- `Enter` / `Return` → `_go_next()` (or `_go_prev()` with Shift)

Other keys propagate to the `QLineEdit` normally.

---

## 10. NodeSearchPopup

`NodeSearchPopup` (`src/ui/canvas/node_search_popup.py`) is a `QDialog` that appears when the user presses Tab on the canvas. It displays a filterable list of all registered nodes (from `NodeRegistry._definitions`, which excludes group_in / group_out / group_node). Selecting an entry creates that node at the last tracked mouse position in the scene.

The popup position is calculated from `NodeView._last_mouse_scene_pos`, which `NodeView.mouseMoveEvent` updates on every mouse movement. This means the node spawns near where the user was pointing.

Theme detection uses:
```python
is_dark = scene.backgroundBrush().color().lightness() < 128
```

---

## 11. Event Flow: Creating a Connection

This is the sequence of events from the moment a user starts dragging from a port to when the wire is committed:

```
1. User presses left button on PortWidget
         │
         ▼
   NodeScene.mousePressEvent
         ├─ itemAt() → finds PortWidget under cursor
         └─ creates Edge(from_port=port, to_port=None)
            adds to scene as active_edge

2. User moves mouse
         │
         ▼
   NodeScene.mouseMoveEvent
         └─ active_edge.set_end_pos(scene_mouse_pos)
            → Edge.update_path() recomputes bezier
            → scene repaints

   [optional] hover snapping:
         ├─ itemAt() → finds PortWidget under cursor
         └─ if compatible port found: highlight it, set _snapped_port

3. User releases mouse
         │
         ▼
   NodeScene.mouseReleaseEvent
         ├─ if _snapped_port is a compatible port:
         │     to_port = _snapped_port
         │     active_edge.to_port = to_port
         │     scene.active_edge = None
         │
         │     validate: no duplicate connection, compatible types
         │     graph_manager.add_connection(ConnectionModel(...))
         │       └─ is_dag() check — reverts if cycle created
         │
         │     trigger on_plug_sync / on_plug callbacks on both nodes
         │     push_history()
         │     update LibraryPanel / parameter widgets
         │
         └─ else:
               remove active_edge from scene
               active_edge = None
```

### Port compatibility

Any connection between two ports is allowed unless one of them is already connected to the other (no duplicate edges). There is no strict data-type enforcement in the engine — `any` ports accept all types, and the node's `execute()` is responsible for handling type mismatches gracefully. The UI does color-code ports by type as a visual hint.

### Exec-port connections

If `from_port.port_definition.data_type == 'exec'`, the created `ConnectionModel` has `is_exec=True`. The engine uses this flag to distinguish exec-chain wires from data wires.

---

## 12. History (Undo/Redo)

The history system uses full-scene snapshots rather than incremental diffs. This is simple to implement and correct, but it has a memory cost proportional to graph size.

### Snapshot format

Each snapshot is a `dict` returned by `WorkflowModel.model_dump(mode='json')`. This includes all nodes, connections, sticky notes, and backdrops. GroupNode subgraphs are stored inside `parameters["__workflow__"]` recursively.

### Push

`push_history()` is called after every user action that mutates the scene:
- Adding / removing a node
- Adding / removing a connection
- Moving nodes (on mouse release)
- Editing a parameter widget value (on change)
- Grouping / ungrouping
- Adding / removing sticky notes and backdrops

The `_undoing` guard prevents recursive push during undo/redo restoration.

### Undo

```python
def undo(self):
    if not self.history: return
    self._undoing = True
    current = self.to_workflow_model().model_dump()
    self.redo_stack.append(current)
    last_state = self.history.pop()
    model = WorkflowModel.model_validate(last_state)
    self.from_workflow_model(model)
    self._undoing = False
    if self._sync_callback:
        self._sync_callback(last_state)
```

`from_workflow_model()` completely rebuilds the scene from the snapshot. All existing items are removed and new ones are created. This is an O(n) operation but visually instant for typical graph sizes.

### Max depth

The history list is capped at 50 entries:
```python
if len(self.history) > 50:
    self.history.pop(0)
```

---

## 13. Serialization (Scene to/from WorkflowModel)

### Scene → WorkflowModel

`NodeScene.to_workflow_model()` collects:

- `nodes`: one `NodeInstanceModel` per `NodeWidget`, preserving `instance_id`, `node_id`, position, parameters, `bypassed`, and `init_priority`.
- `connections`: one `ConnectionModel` per `Edge` with a committed `to_port`.
- `sticky_notes`: one `StickyNoteModel` per `StickyNote`.
- `backdrops`: one `BackdropModel` per `Backdrop`.

Parameters are serialized by calling `NodeWidget.get_serializable_parameters()`, which merges the node's `instance.parameters` dict with the current widget values.

### WorkflowModel → Scene

`NodeScene.from_workflow_model(model)` clears all items from the scene, then:

1. For each `NodeInstanceModel`: looks up `NodeRegistry.get_definition()` and `NodeRegistry.get_class()`, creates a `NodeWidget`, sets its position and parameters.
2. For each `ConnectionModel`: finds the matching `PortWidget` items by `instance_id` and `port_name`, creates an `Edge`, and adds it.
3. For each `StickyNoteModel` / `BackdropModel`: creates the corresponding item and positions it.

### File I/O

`MainWindow.save_workflow_as()`:
```python
model = scene.to_workflow_model()
json_str = model.model_dump_json(indent=2)
with open(path, "w") as f:
    f.write(json_str)
```

`MainWindow.load_workflow()`:
```python
with open(path, "r") as f:
    data = json.load(f)
model = WorkflowModel.model_validate(data)
scene.from_workflow_model(model)
```

---

## 14. Theme System

Vibrante-Node supports dark and light themes. Theme state is tracked by `MainWindow._is_dark_theme`.

### Application stylesheet

`MainWindow._apply_dark_theme()` and `_apply_light_theme()` call `QApplication.instance().setStyleSheet(css)` with a comprehensive CSS string that styles all standard Qt widgets (`QMainWindow`, `QDockWidget`, `QTabWidget`, `QMenuBar`, `QPushButton`, etc.).

The Fusion style (`QApplication.setStyle("Fusion")`) is applied globally at startup to ensure consistent QSS rendering across platforms. Without Fusion, QSS rendering differs between Windows, macOS, and Linux.

### Cascade to canvas items

After applying the application stylesheet, the theme methods call `apply_theme()` on items that manage their own appearance independently of QSS:

```python
scene.setBackgroundBrush(QColor(40, 40, 40))   # dark
# or
scene.setBackgroundBrush(QColor(220, 220, 220)) # light

for node in scene.nodes:
    node.apply_theme(is_dark)

for edge in scene.edges:
    edge.apply_theme(is_dark)

view._mini_map.apply_theme(is_dark)
```

### Adding a themeable component

When creating a new graphics item or custom widget that cannot be styled purely via QSS:

1. Add `apply_theme(is_dark: bool)` method.
2. Set initial theme in `__init__` with `self.apply_theme(True)`.
3. Connect to the theme cascade in `_apply_dark_theme()` / `_apply_light_theme()` in `MainWindow`.

---

## 15. LibraryPanel

`LibraryPanel` (`src/ui/library_panel.py`) is a `QDockWidget` that displays all registered nodes grouped by category. It provides drag-to-canvas, double-click-to-add, and right-click context menus for edit and delete.

### Tree structure

The `DraggableTreeWidget` (a `QTreeWidget` subclass) has top-level items for each category and child items for each node. Each child item stores `node_id` in `Qt.UserRole`.

### Drag-to-canvas

`DraggableTreeWidget.mouseMoveEvent` starts a `QDrag` when the user moves more than `startDragDistance()` pixels from the press point. The `QMimeData` carries:

- `application/x-node-id` — the `node_id` bytes (used by `NodeView.dropEvent`)
- plain text — the `node_id` string (fallback for external drops)

### Signals

| Signal | When |
|--------|------|
| `node_selected(str)` | Double-click on a node item |
| `edit_requested(str)` | Right-click → Edit |
| `delete_requested(str)` | Right-click → Delete |

`MainWindow` connects `node_selected` to `_on_node_selected()` which calls `scene.add_node_by_name()` at the current scene centre.

---

## 16. LogPanel

`LogPanel` (`src/ui/log_panel.py`) is a `QDockWidget` wrapping a `QTextEdit`. It displays messages with color-coded HTML:

| Level | Color |
|-------|-------|
| `info` | Default text color (white/black per theme) |
| `success` | Green (`#4CAF50`) |
| `error` | Red (`#F44336`) |
| `warning` | Orange (`#FF9800`) |

Each message is prefixed with a timestamp (`HH:MM:SS`) and, when a `node_id` is known, the node name.

Execution timing messages (logged by `MainWindow._on_node_finished`) appear as `info` level: `Node 'X' finished in 0.34s`.

The `QTextEdit` is read-only. A **Clear** button calls `clear()`. Log entries are appended with `append(html)` which scrolls to the bottom automatically via `scrollContentsBy`.

---

## 17. ScriptingConsole

`ScriptingConsole` (`src/ui/scripting_console.py`) is a `QDockWidget` with:
- A `QPlainTextEdit` (output area, read-only).
- A `QLineEdit` (input area).

When the user presses Enter in the input area, the text is executed via `exec(code, context)` where `context = {'window': self._main_window, 'scene': current_scene}`. Standard output is captured and appended to the output area. Exceptions are displayed in red.

Scripts have full access to `window` (`MainWindow`) and `scene` (`NodeScene`), so they can add nodes, read parameters, trigger execution, and modify the workflow programmatically.

---

## 18. NodeBuilderDialog

`NodeBuilderDialog` (`src/ui/node_builder.py`) is a `QDialog` for creating and editing node definitions. It provides:

- **Metadata fields**: name, category, description, icon path, `use_exec` checkbox.
- **Input ports table** (`QTableWidget`): port name, data type, widget type columns; add/remove rows.
- **Output ports table**: same structure.
- **Code editor** (`CodeEditor`): Python source with syntax highlighting and autocomplete.
- **AI assistant** (`GeminiChatWidget`): chat interface for generating node code with Gemini.
- **Test bridge button**: calls `bridge.ping()` to verify Houdini connectivity.

### Code-to-ports sync

A `QTimer` (debounced 300 ms) triggers `_sync_code_to_ui()` after each keystroke. This parses the code with `ast` and extracts `add_input()`/`add_output()` calls to populate the port tables. This is one-directional (code → tables); editing the tables does not modify the code.

### Save

On **Save**, `NodeBuilderDialog` assembles a `NodeDefinitionJSON`, calls `NodeRegistry.register_definition()`, and writes the JSON file to `nodes/{node_id}.json`. It then calls `NodeRegistry.reload_node_definition()` and refreshes the `LibraryPanel`.

---

## 19. CodeEditor

`CodeEditor` (`src/ui/code_editor.py`) provides Python-aware editing. It has two implementations selected at import time:

```python
try:
    from PyQt5.Qsci import QsciScintilla, QsciLexerPython, QsciAPIs
    _QSCINTILLA_AVAILABLE = True
except ImportError:
    _QSCINTILLA_AVAILABLE = False
    # fallback class uses QPlainTextEdit + QSyntaxHighlighter
```

Both implementations expose an identical public API:

| Method / attribute | Notes |
|--------------------|-------|
| `setPlainText(text)` | Set editor content |
| `toPlainText()` | Get editor content |
| `textChanged` signal | Emitted on every keystroke |
| `apply_theme(is_dark)` | Switch Dracula-dark / One-Light color scheme |
| `set_completer_list(words)` | Replace autocomplete word list |
| `append_completer_list(words)` | Add words to autocomplete list |
| `error_line` | Line number of last syntax error (-1 if none) |
| Ctrl+Wheel | Zoom in/out |

Do not re-raise `ImportError` if QScintilla is missing. The fallback implementation keeps the application functional on systems without the optional dependency.

To install the full editor:
```
pip install QScintilla
```

---

## 20. How to Add a New UI Panel

This is the step-by-step pattern for adding a new dockable panel to the application.

### Step 1: Create the panel class

```python
# src/ui/my_panel.py
from PyQt5.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QLabel

class MyPanel(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("My Panel", parent)
        self.setObjectName("MyPanelDock")   # must be unique for geometry save/restore
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        container = QWidget()
        layout = QVBoxLayout(container)
        self._label = QLabel("Hello from MyPanel")
        layout.addWidget(self._label)
        self.setWidget(container)

    def update_content(self, data):
        self._label.setText(str(data))
```

### Step 2: Instantiate in MainWindow

```python
# In MainWindow.__init__, after the existing dock panels:
from src.ui.my_panel import MyPanel

self.my_panel = MyPanel(self)
self.addDockWidget(Qt.RightDockWidgetArea, self.my_panel)
```

### Step 3: Connect to engine signals (if needed)

```python
executor.node_output.connect(self._on_node_output_for_my_panel)

def _on_node_output_for_my_panel(self, node_id, output_data):
    if "my_output" in output_data:
        self.my_panel.update_content(output_data["my_output"])
```

### Step 4: Add to the View menu

```python
# In MainWindow._init_menu():
view_menu.addAction(self.my_panel.toggleViewAction())
```

The `toggleViewAction()` is provided by `QDockWidget` and shows/hides the panel.

### Step 5: Geometry persistence

Dock panel positions and sizes are saved/restored by `_save_user_settings()` / `_load_user_settings()` via `self.saveState()` / `self.restoreState()`. Any panel whose `objectName` was set before `restoreState()` is called will have its position restored automatically.

---

## 21. Custom Graphics Items

### Inheriting QGraphicsItem

```python
from PyQt5.QtWidgets import QGraphicsItem
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPainter, QPen, QColor

class MyItem(QGraphicsItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self._width = 100
        self._height = 60

    def boundingRect(self) -> QRectF:
        # Must be exact or Qt will artifact during painting
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(QPen(QColor("#888888"), 1))
        painter.drawRect(self.boundingRect())
```

### Required methods

- `boundingRect()` — must return the exact bounding box in item-local coordinates. Qt uses this for culling (not painting items outside the viewport) and hit testing.
- `paint(painter, option, widget)` — all drawing happens here. Use the provided `painter`; do not create a new `QPainter`.

### Z-order

Z-value controls paint order. Higher Z-values paint on top:

| Item | Z-value |
|------|---------|
| Backdrop | -3 |
| Edge (wire) | -1 |
| NodeWidget | 0 |
| StickyNote | 1 |
| Active edge (during drag) | 2 |

Set z-value in `__init__`:
```python
self.setZValue(-1)  # paint behind nodes
```

### Adding to the scene

```python
item = MyItem()
item.setPos(scene_x, scene_y)
scene.addItem(item)
```

### Custom hit area (shape())

To make a thin or irregular item easier to click, override `shape()`:

```python
def shape(self):
    stroker = QPainterPathStroker()
    stroker.setWidth(12)
    path = QPainterPath()
    path.addRect(self.boundingRect())
    return stroker.createStroke(path)
```

This is the same technique `Edge` uses to widen wire hit areas.

---

## 22. Stylesheet Architecture

The application uses Qt Style Sheets (QSS) applied to `QApplication`. There is one large CSS string for dark theme and one for light theme.

### Where stylesheets live

The CSS strings are defined inline in `MainWindow._apply_dark_theme()` and `MainWindow._apply_light_theme()`. They are not loaded from files; embedding them avoids file-not-found issues in bundled deployments.

### CSS variable pattern

Qt 5's QSS does not support CSS variables. The pattern used here is Python string templating at the call site:

```python
PRIMARY = "#4a90d9"
BACKGROUND = "#2b2b2b"

css = f"""
QMainWindow {{
    background-color: {BACKGROUND};
}}
QPushButton {{
    background-color: {PRIMARY};
    color: white;
}}
"""
QApplication.instance().setStyleSheet(css)
```

### Per-widget overrides

To override the global stylesheet for a specific widget, call `widget.setStyleSheet(local_css)`. Local styles take precedence over the global stylesheet for that widget and its children. Example:

```python
self.my_button.setStyleSheet("""
    QPushButton {
        background-color: #c0392b;   /* red override */
        color: white;
    }
""")
```

### Selectors for custom items

Custom `QWidget` subclasses can be styled by their Python class name only if they are also registered with Qt's meta-object system. To use `objectName` as a CSS ID:

```python
self.setObjectName("MiniMapView")
# CSS:
# QGraphicsView#MiniMapView { border: 1px solid #555; }
```

### What QSS cannot style

- `QGraphicsItem` subclasses (e.g. `NodeWidget`, `Edge`). These must be styled via `QPainter` in `paint()` or via `apply_theme()` methods.
- `QGraphicsScene` background — use `scene.setBackgroundBrush()`.

---

## 23. StickyNote and Backdrop

`StickyNote` (`src/ui/canvas/sticky_note.py`) and `Backdrop` (`src/ui/canvas/backdrop.py`) are annotation items that do not participate in execution.

### StickyNote

A `QGraphicsItem` with:
- A colored rectangle background (user-configurable color via right-click).
- A `QGraphicsProxyWidget` embedding a `QTextEdit` for multi-line text.
- Resize handles at the corners and edges.
- Z-value `1` (above nodes and edges so notes are always readable).

`StickyNoteModel` is serialized as part of `WorkflowModel.sticky_notes`.

### Backdrop (Network Box)

A `QGraphicsRectItem` with:
- A semi-transparent colored fill.
- A title text rendered in the header area.
- Resize handles.
- Z-value `-3` (behind all other items so it acts as a visual grouping frame).
- Moving a Backdrop does **not** move contained nodes — the backdrop is purely cosmetic.

`BackdropModel` is serialized as part of `WorkflowModel.backdrops`.

### Creating programmatically

```python
scene.add_sticky_note(pos=(100, 200), text="Initial text", color="#ffffcc")
scene.add_backdrop(title="My Group", pos=(50, 150), size=(400, 300), color="#444444")
```

Both methods push history after creation so they can be undone.
