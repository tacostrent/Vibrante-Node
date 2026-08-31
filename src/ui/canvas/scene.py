from src.utils.qt_compat import QtWidgets, QtCore, QtGui, exec_dialog, Signal
import asyncio

QGraphicsScene = QtWidgets.QGraphicsScene
QGraphicsItem = QtWidgets.QGraphicsItem
QMenu = QtWidgets.QMenu
QAction = QtWidgets.QAction
Qt = QtCore.Qt
QPointF = QtCore.QPointF
QColor = QtGui.QColor
QPen = QtGui.QPen
from src.core.registry import NodeRegistry
from src.ui.node_widget import NodeWidget
from src.ui.canvas.edge import Edge
from src.ui.port_widget import PortWidget
from src.core.models import WorkflowModel, NodeInstanceModel, ConnectionModel, StickyNoteModel, BackdropModel
from src.utils.runtime import AsyncRuntime
from src.ui.canvas.sticky_note import StickyNote
from src.ui.canvas.backdrop import Backdrop
from uuid import uuid4, UUID

# Simple global clipboard for cross-tab copy/paste
global_clipboard = {"nodes": None}

class NodeScene(QGraphicsScene):
    dirty_changed = Signal(bool)  # emitted when unsaved-state changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QColor(40, 40, 40)) # Darker background
        self.setSceneRect(-5000, -5000, 10000, 10000)
        
        self.nodes = [] # List of NodeWidget
        self.edges = []
        self.sticky_notes = []
        self.backdrops = []
        self.active_edge = None
        self.file_path = None
        
        # Snap target state
        self._snapped_port = None

        self.history = []
        self.redo_stack = []
        self._undoing = False
        self._dirty = False
        self._sync_callback = None  # Set by MainWindow when this scene is a subgraph tab

        self.grid_size = 20
        self.grid_pen = QPen(QColor("#555555"), 0.5)

    def push_history(self):
        if self._undoing: return
        snapshot = self.to_workflow_model().model_dump()
        self.history.append(snapshot)
        self.redo_stack.clear()
        if len(self.history) > 50: # Limit history
            self.history.pop(0)
        if not self._dirty:
            self._dirty = True
            self.dirty_changed.emit(True)
        if self._sync_callback:
            self._sync_callback(snapshot)

    def mark_clean(self):
        if self._dirty:
            self._dirty = False
            self.dirty_changed.emit(False)

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

    def redo(self):
        if not self.redo_stack: return
        self._undoing = True
        current = self.to_workflow_model().model_dump()
        self.history.append(current)

        next_state = self.redo_stack.pop()
        model = WorkflowModel.model_validate(next_state)
        self.from_workflow_model(model)
        self._undoing = False
        if self._sync_callback:
            self._sync_callback(next_state)

    def _safe_async_call(self, coro):
        """Helper to call async methods from the UI thread using a background loop."""
        AsyncRuntime.run_coroutine(coro)

    def _get_port_data_type(self, port):
        """Returns the data type string for a port widget."""
        pd = port.port_definition
        if hasattr(pd, "type"):
            return pd.type.lower()
        if hasattr(pd, "data_type"):
            return pd.data_type.lower()
        return "any"

    def _trigger_unplug(self, from_port, to_port):
        """Triggers sync and async unplug events."""
        if not from_port or not to_port: return
        fn_widget = from_port.parentItem()
        tn_widget = to_port.parentItem()
        fn = fn_widget.node_definition
        tn = tn_widget.node_definition
        
        try:
            fn.on_unplug_sync(from_port.port_definition.name, False)
        except Exception as e:
            print(f"Error in {fn.name} on_unplug_sync: {e}")
            
        try:
            tn.on_unplug_sync(to_port.port_definition.name, True)
        except Exception as e:
            print(f"Error in {tn.name} on_unplug_sync: {e}")
        
        fn_widget._refresh_widget_states()
        tn_widget._refresh_widget_states()
        
        self._safe_async_call(fn.on_unplug(from_port.port_definition.name, False))
        self._safe_async_call(tn.on_unplug(to_port.port_definition.name, True))

    def _trigger_plug(self, from_port, to_port):
        """Triggers sync and async plug events."""
        if not from_port or not to_port: return
        fn_widget = from_port.parentItem()
        tn_widget = to_port.parentItem()
        fn = fn_widget.node_definition
        tn = tn_widget.node_definition
        
        source_val = fn.get_parameter(from_port.port_definition.name)
        if source_val is not None:
            tn_widget.set_parameter(to_port.port_definition.name, source_val)

        try:
            fn.on_plug_sync(from_port.port_definition.name, False, tn, to_port.port_definition.name)
        except Exception as e:
            print(f"Error in {fn.name} on_plug_sync: {e}")
            
        try:
            tn.on_plug_sync(to_port.port_definition.name, True, fn, from_port.port_definition.name)
        except Exception as e:
            print(f"Error in {tn.name} on_plug_sync: {e}")
        
        fn_widget._refresh_widget_states()
        tn_widget._refresh_widget_states()
        
        self._safe_async_call(fn.on_plug(from_port.port_definition.name, False, tn, to_port.port_definition.name))
        self._safe_async_call(tn.on_plug(to_port.port_definition.name, True, fn, from_port.port_definition.name))

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        left = int(rect.left())
        right = int(rect.right())
        top = int(rect.top())
        bottom = int(rect.bottom())
        first_left = left - (left % self.grid_size)
        first_top = top - (top % self.grid_size)
        painter.setPen(self.grid_pen)
        for x in range(first_left, right, self.grid_size):
            painter.drawLine(x, top, x, bottom)
        for y in range(first_top, bottom, self.grid_size):
            painter.drawLine(left, y, right, y)

    def copy_selection(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return None
        
        # Serialize only selected nodes, notes, backdrops and internal connections
        model = WorkflowModel()
        node_ids = set()
        
        for item in selected_items:
            if isinstance(item, NodeWidget):
                node_ids.add(item.instance_id)
                node_model = NodeInstanceModel(
                    instance_id=item.instance_id,
                    node_id=getattr(item.node_definition, 'node_id', item.node_definition.name),
                    position=(item.pos().x(), item.pos().y()),
                    parameters=item.node_definition.parameters.copy()
                )
                model.nodes.append(node_model)
            elif isinstance(item, StickyNote):
                model.sticky_notes.append(StickyNoteModel(
                    id=item.instance_id,
                    position=(item.pos().x(), item.pos().y()),
                    size=(item.rect().width(), item.rect().height()),
                    text=item.get_text(),
                    color=item.bg_color.name()
                ))
            elif isinstance(item, Backdrop):
                model.backdrops.append(BackdropModel(
                    id=item.instance_id,
                    position=(item.pos().x(), item.pos().y()),
                    size=(item.rect().width(), item.rect().height()),
                    title=item.title_item.toPlainText(),
                    color=item.bg_color.name()
                ))
            
        for edge in self.edges:
            if edge.from_port and edge.to_port:
                f_id = edge.from_port.parentItem().instance_id
                t_id = edge.to_port.parentItem().instance_id
                if f_id in node_ids and t_id in node_ids:
                    conn_model = ConnectionModel(
                        from_node=f_id,
                        from_port=edge.from_port.port_definition.name,
                        to_node=t_id,
                        to_port=edge.to_port.port_definition.name
                    )
                    model.connections.append(conn_model)
        
        global_clipboard["nodes"] = model.model_dump()
        return global_clipboard["nodes"]

    def paste_selection(self, target_pos: QPointF = None, pos_offset: QPointF = None):
        data = global_clipboard.get("nodes")
        if not data:
            return
            
        model = WorkflowModel.model_validate(data)
        
        # Calculate offset if target_pos is provided
        if target_pos is not None:
            # Find the top-left of the copied group as reference
            all_positions = []
            for n in model.nodes: all_positions.append(n.position)
            for n in model.sticky_notes: all_positions.append(n.position)
            for n in model.backdrops: all_positions.append(n.position)
            
            if all_positions:
                min_x = min(p[0] for p in all_positions)
                min_y = min(p[1] for p in all_positions)
                pos_offset = target_pos - QPointF(min_x, min_y)
        
        # Default offset if neither target_pos nor pos_offset is provided
        if pos_offset is None:
            pos_offset = QPointF(30, 30)

        # Map old IDs to new IDs to maintain connections
        import uuid
        id_map = {}
        new_items = []
        
        self.clearSelection()
        
        # Paste Nodes
        for node_model in model.nodes:
            new_pos = QPointF(node_model.position[0], node_model.position[1]) + pos_offset
            widget = self.add_node_by_name(node_model.node_id, new_pos)
            if widget:
                new_id = str(uuid.uuid4())
                id_map[node_model.instance_id] = new_id
                widget.instance_id = new_id
                for p_name, p_val in node_model.parameters.items():
                    widget.set_parameter(p_name, p_val, propagate=False)
                widget.setSelected(True)
                new_items.append(widget)
                
        # Paste Connections
        for conn in model.connections:
            from_id = id_map.get(conn.from_node)
            to_id = id_map.get(conn.to_node)
            if from_id and to_id:
                from_w = next((n for n in self.nodes if n.instance_id == from_id), None)
                to_w = next((n for n in self.nodes if n.instance_id == to_id), None)
                if from_w and to_w:
                    self.connect_nodes(from_w, conn.from_port, to_w, conn.to_port)

        # Paste Sticky Notes
        for note_model in model.sticky_notes:
            new_pos = QPointF(note_model.position[0], note_model.position[1]) + pos_offset
            note = self.add_sticky_note(note_model.text, (new_pos.x(), new_pos.y()), 
                                      note_model.size, note_model.color)
            note.setSelected(True)
            new_items.append(note)

        # Paste Backdrops
        for bd_model in model.backdrops:
            new_pos = QPointF(bd_model.position[0], bd_model.position[1]) + pos_offset
            box = self.add_backdrop(bd_model.title, (new_pos.x(), new_pos.y()), 
                                   bd_model.size, bd_model.color)
            box.setSelected(True)
            new_items.append(box)
        
        return new_items

    def duplicate_selection(self):
        """Duplicate selected items in place at a +20 px offset. Leaves duplicates selected."""
        if not self.copy_selection():
            return
        self.paste_selection(pos_offset=QPointF(20, 20))

    def group_selection(self):
        """Collapse selected nodes into a single GroupNode with an embedded sub-workflow.

        Boundary data connections are analysed automatically:
        - External → internal becomes a group input port + group_in node inside.
        - Internal → external becomes a group output port + group_out node inside.
        Exec connections crossing the boundary are rewired to the GroupNode's
        exec_in / exec_out pins.
        """
        selected = [i for i in self.selectedItems() if isinstance(i, NodeWidget)]
        if not selected:
            return

        selected_str_ids = {str(w.instance_id) for w in selected}

        # Capture current workflow (parameters already serializable)
        workflow = self.to_workflow_model()
        conn_list = workflow.connections

        boundary_in = []     # data: external → internal
        boundary_out = []    # data: internal → external
        boundary_exec_in = []  # exec: external → internal
        boundary_exec_out = []  # exec: internal → external
        internal_conns = []  # connections fully inside the selection

        for conn in conn_list:
            fi = str(conn.from_node) in selected_str_ids
            ti = str(conn.to_node) in selected_str_ids
            if fi and ti:
                internal_conns.append(conn)
            elif not fi and ti:
                (boundary_exec_in if conn.is_exec else boundary_in).append(conn)
            elif fi and not ti:
                (boundary_exec_out if conn.is_exec else boundary_out).append(conn)

        # Build group input port list (deduplicated by target port name)
        group_inputs = []    # [(group_port_name, conn), ...]
        seen_in = set()
        in_port_map = {}     # conn → group_port_name

        for conn in boundary_in:
            base = conn.to_port
            name = base
            idx = 1
            while name in seen_in:
                name = f"{base}_{idx}"
                idx += 1
            seen_in.add(name)
            group_inputs.append((name, conn))
            in_port_map[id(conn)] = name

        # Build group output port list (deduplicated by source port name)
        group_outputs = []   # [(group_port_name, conn), ...]
        seen_out = set()
        out_port_map = {}    # conn → group_port_name

        for conn in boundary_out:
            base = conn.from_port
            name = base
            idx = 1
            while name in seen_out:
                name = f"{base}_{idx}"
                idx += 1
            seen_out.add(name)
            group_outputs.append((name, conn))
            out_port_map[id(conn)] = name

        # --- Build internal WorkflowModel ---
        from src.core.models import WorkflowModel, NodeInstanceModel, ConnectionModel
        from uuid import uuid4

        selected_models = [
            m for m in workflow.nodes
            if str(m.instance_id) in selected_str_ids
        ]

        internal_nodes = list(selected_models)
        internal_conns_list = list(internal_conns)

        # Compute bounding rect for positioning boundary nodes
        min_x = min(w.pos().x() for w in selected)
        max_x = max(w.pos().x() for w in selected)
        avg_y = sum(w.pos().y() for w in selected) / len(selected)

        # Add group_in nodes (left of selection)
        gin_id_map = {}  # group_port_name → internal UUID
        for i, (port_name, conn) in enumerate(group_inputs):
            gin_id = uuid4()
            gin_id_map[port_name] = gin_id
            internal_nodes.append(NodeInstanceModel(
                instance_id=gin_id,
                node_id="group_in",
                position=(min_x - 250, avg_y + i * 80),
                parameters={"port_name": port_name, "value": None}
            ))
            # Wire group_in.value → original target node's port
            internal_conns_list.append(ConnectionModel(
                from_node=gin_id,
                from_port="value",
                to_node=conn.to_node,
                to_port=conn.to_port,
                is_exec=False
            ))

        # Add group_out nodes (right of selection)
        gout_id_map = {}  # group_port_name → internal UUID
        for i, (port_name, conn) in enumerate(group_outputs):
            gout_id = uuid4()
            gout_id_map[port_name] = gout_id
            internal_nodes.append(NodeInstanceModel(
                instance_id=gout_id,
                node_id="group_out",
                position=(max_x + 250, avg_y + i * 80),
                parameters={"port_name": port_name, "value": None}
            ))
            # Wire original source node's port → group_out.value
            internal_conns_list.append(ConnectionModel(
                from_node=conn.from_node,
                from_port=conn.from_port,
                to_node=gout_id,
                to_port="value",
                is_exec=False
            ))

        internal_workflow = WorkflowModel(
            nodes=internal_nodes,
            connections=internal_conns_list
        )

        # --- Port definitions for serialization / restore ---
        port_defs = []
        for port_name, _ in group_inputs:
            port_defs.append({"name": port_name, "type": "any", "is_input": True})
        for port_name, _ in group_outputs:
            port_defs.append({"name": port_name, "type": "any", "is_input": False})

        self.push_history()

        # --- Remove selected nodes and their edges from the scene ---
        for edge in list(self.edges):
            fp = edge.from_port.parentItem() if edge.from_port else None
            tp = edge.to_port.parentItem() if edge.to_port else None
            if fp in selected or tp in selected:
                self.removeItem(edge)
                self.edges.remove(edge)
        for widget in selected:
            self.removeItem(widget)
            if widget in self.nodes:
                self.nodes.remove(widget)

        # --- Create GroupNode on canvas ---
        center_x = sum(w.pos().x() for w in selected) / len(selected)
        center_y = avg_y
        group_widget = self.add_node_by_name("group_node", QPointF(center_x, center_y))
        if not group_widget:
            return

        # Store embedded workflow and port definitions
        group_widget.node_definition.parameters["__workflow__"] = internal_workflow.model_dump(mode='json')
        group_widget.node_definition.parameters["__port_defs__"] = port_defs
        group_widget.node_definition.parameters["__name__"] = "Group"

        # Add dynamic ports to the node definition, then rebuild the widget
        for pd in port_defs:
            if pd["is_input"]:
                group_widget.node_definition.add_input(pd["name"], pd["type"])
            else:
                group_widget.node_definition.add_output(pd["name"], pd["type"])
        group_widget.rebuild_ports()

        # --- Reconnect external connections to the GroupNode ---
        for port_name, conn in group_inputs:
            from_w = next((n for n in self.nodes if str(n.instance_id) == str(conn.from_node)), None)
            if from_w:
                self.connect_nodes(from_w, conn.from_port, group_widget, port_name)

        for port_name, conn in group_outputs:
            to_w = next((n for n in self.nodes if str(n.instance_id) == str(conn.to_node)), None)
            if to_w:
                self.connect_nodes(group_widget, port_name, to_w, conn.to_port)

        # Reconnect exec boundary connections to the GroupNode's exec pins
        for conn in boundary_exec_in:
            from_w = next((n for n in self.nodes if str(n.instance_id) == str(conn.from_node)), None)
            if from_w:
                self.connect_nodes(from_w, conn.from_port, group_widget, "exec_in")

        for conn in boundary_exec_out:
            to_w = next((n for n in self.nodes if str(n.instance_id) == str(conn.to_node)), None)
            if to_w:
                self.connect_nodes(group_widget, "exec_out", to_w, conn.to_port)

        self.clearSelection()
        group_widget.setSelected(True)

    @staticmethod
    def _serializable_params(params: dict) -> dict:
        import json
        result = {}
        for k, v in params.items():
            try:
                json.dumps(v)
                result[k] = v
            except (TypeError, ValueError):
                pass
        return result

    def to_workflow_model(self) -> WorkflowModel:
        model = WorkflowModel()
        for node_widget in self.nodes:
            # SYNC: Ensure the latest parameters from the UI are captured
            # Many parameters might have changed via widgets without triggering a full sync

            node_model = NodeInstanceModel(
                instance_id=node_widget.instance_id,
                node_id=getattr(node_widget.node_definition, 'node_id', node_widget.node_definition.name),
                position=(node_widget.pos().x(), node_widget.pos().y()),
                parameters=self._serializable_params(node_widget.node_definition.parameters),
                bypassed=node_widget.bypassed,
                init_priority=node_widget.init_priority
            )
            model.nodes.append(node_model)
        for edge in self.edges:
            if edge.from_port and edge.to_port:
                f_parent = edge.from_port.parentItem()
                t_parent = edge.to_port.parentItem()
                
                if not f_parent or not t_parent:
                    continue # Skip partially detached edges
                    
                conn_model = ConnectionModel(
                    from_node=f_parent.instance_id,
                    from_port=edge.from_port.port_definition.name,
                    to_node=t_parent.instance_id,
                    to_port=edge.to_port.port_definition.name,
                    is_exec=edge.from_port.port_type == "exec"
                )
                model.connections.append(conn_model)
        for note in self.sticky_notes:
            model.sticky_notes.append(StickyNoteModel(
                id=note.instance_id,
                position=(note.pos().x(), note.pos().y()),
                size=(note.rect().width(), note.rect().height()),
                text=note.get_text(),
                color=note.bg_color.name()
            ))
        for box in self.backdrops:
            model.backdrops.append(BackdropModel(
                id=box.instance_id,
                position=(box.pos().x(), box.pos().y()),
                size=(box.rect().width(), box.rect().height()),
                title=box.title_item.toPlainText(),
                color=box.bg_color.name()
            ))
        return model

    def from_workflow_model(self, model: WorkflowModel):
        _prev_undoing = self._undoing
        self._undoing = True  # suppress push_history (and dirty marking) during load
        self.clear()
        self.nodes = []
        self.edges = []
        self.sticky_notes = []
        self.backdrops = []
        id_to_widget = {}

        # Sort nodes so init-first nodes (init_priority > 0) are created BEFORE
        # any other node. Higher init_priority is created earlier so the very
        # first thing on the canvas is the highest-priority init node.
        # This ensures init nodes (e.g. "connect to server", "auth login") are
        # present in the scene before any downstream node tries to render or
        # request data from them.
        ordered_nodes = sorted(
            model.nodes,
            key=lambda n: -getattr(n, 'init_priority', 0),
        )

        for node_model in ordered_nodes:
            widget = self.add_node_by_name(node_model.node_id, QPointF(node_model.position[0], node_model.position[1]))
            if widget:
                widget.instance_id = node_model.instance_id
                widget.set_bypassed(node_model.bypassed)
                widget.set_init_priority(getattr(node_model, 'init_priority', 0))
                # SYNC: Apply parameters to UI widgets and node definition
                for p_name, p_val in node_model.parameters.items():
                    widget.set_parameter(p_name, p_val, propagate=False)

                # Restore dynamic ports from saved parameters (e.g. GroupNode data
                # ports, Sequencer step ports). Mirrors what the engine does before
                # each execution — without this, dynamic ports are lost on reload.
                widget.node_definition.restore_from_parameters(node_model.parameters)
                widget.rebuild_ports()

                id_to_widget[node_model.instance_id] = widget

        # Create connections involving init-first nodes BEFORE all others so
        # the init nodes are fully wired up before any non-init connection
        # is established.
        init_ids = {n.instance_id for n in model.nodes if getattr(n, 'init_priority', 0) > 0}
        ordered_conns = sorted(
            model.connections,
            key=lambda c: 0 if (c.from_node in init_ids or c.to_node in init_ids) else 1,
        )

        for conn in ordered_conns:
            from_widget = id_to_widget.get(conn.from_node)
            to_widget = id_to_widget.get(conn.to_node)
            if from_widget and to_widget:
                self.connect_nodes(from_widget, conn.from_port, to_widget, conn.to_port)
                
        for note_model in model.sticky_notes:
            self.add_sticky_note(note_model.text, note_model.position, note_model.size, note_model.color, note_model.id)
            
        for bd_model in model.backdrops:
            self.add_backdrop(bd_model.title, bd_model.position, bd_model.size, bd_model.color, bd_model.id)

        self._undoing = _prev_undoing

    def add_sticky_note(self, text="New Note", pos=(0, 0), size=(200, 150), color="#ffffcc", instance_id=None):
        self.push_history()
        note = StickyNote(text, pos, size, color, instance_id)
        self.addItem(note)
        self.sticky_notes.append(note)
        return note

    def add_backdrop(self, title="Network Box", pos=(0, 0), size=(400, 300), color="#444444", instance_id=None):
        self.push_history()
        box = Backdrop(title, pos, size, color, instance_id)
        self.addItem(box)
        self.backdrops.append(box)
        return box

    def mousePressEvent(self, event):
        # Snap history before potential move or connection change
        if event.button() == Qt.LeftButton:
            self.push_history()
            
        view = self.views()[0] if self.views() else None
        transform = view.transform() if view else None
        item = self.itemAt(event.scenePos(), transform) if transform else self.itemAt(event.scenePos())
        is_dark = self.backgroundBrush().color().lightness() < 128
        if event.button() == Qt.LeftButton:
            if isinstance(item, PortWidget):
                if item.is_input:
                    existing_edge = next((e for e in self.edges if e.to_port == item), None)
                    if existing_edge:
                        from_p = existing_edge.from_port
                        to_p = existing_edge.to_port
                        self.edges.remove(existing_edge)
                        self.active_edge = existing_edge
                        self.active_edge.to_port = None
                        self._trigger_unplug(from_p, to_p)
                    else:
                        self.active_edge = Edge(item)
                        self.active_edge.apply_theme(is_dark)
                        self.addItem(self.active_edge)
                else:
                    self.active_edge = Edge(item)
                    self.active_edge.apply_theme(is_dark)
                    self.addItem(self.active_edge)
                self.active_edge.set_end_pos(event.scenePos())
                event.accept()
                return
            elif isinstance(item, Edge):
                item.setSelected(True)
                super().mousePressEvent(event)
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.active_edge:
            pos = event.scenePos()
            
            # SNAP LOGIC
            snap_radius = 35
            nearest_port = None
            min_dist = snap_radius
            
            # Find nearest compatible port
            for item in self.items(QtCore.QRectF(pos.x() - snap_radius, pos.y() - snap_radius, snap_radius*2, snap_radius*2)):
                if isinstance(item, PortWidget):
                    # Compatibility check
                    if item.parentItem() != self.active_edge.from_port.parentItem() and \
                       item.is_input != self.active_edge.from_port.is_input:
                        
                        dist = (item.scenePos() - pos).manhattanLength()
                        if dist < min_dist:
                            min_dist = dist
                            nearest_port = item
            
            if nearest_port:
                # Snap to port center
                self.active_edge.set_end_pos(nearest_port.scenePos())
                
                # Trigger animation on the target port
                if self._snapped_port != nearest_port:
                    if self._snapped_port: 
                        self._snapped_port.hoverLeaveEvent(None)
                    self._snapped_port = nearest_port
                    self._snapped_port.hoverEnterEvent(None)
            else:
                # No snap, follow mouse
                self.active_edge.set_end_pos(pos)
                if self._snapped_port:
                    self._snapped_port.hoverLeaveEvent(None)
                    self._snapped_port = None
                    
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.active_edge and event.button() == Qt.LeftButton:
            view = self.views()[0] if self.views() else None
            transform = view.transform() if view else None
            
            # Use the snapped port if it exists, otherwise check under mouse
            item = self._snapped_port
            if not item:
                item = self.itemAt(event.scenePos(), transform) if transform else self.itemAt(event.scenePos())
            
            if isinstance(item, PortWidget):
                if item != self.active_edge.from_port and \
                   item.parentItem() != self.active_edge.from_port.parentItem() and \
                   item.is_input != self.active_edge.from_port.is_input:
                    target_input = item if item.is_input else self.active_edge.from_port
                    target_output = item if not item.is_input else self.active_edge.from_port
                    
                    old_edge = next((e for e in self.edges if e.to_port == target_input), None)
                    if old_edge:
                        from_p = old_edge.from_port
                        to_p = old_edge.to_port
                        self.removeItem(old_edge)
                        self.edges.remove(old_edge)
                        self._trigger_unplug(from_p, to_p)

                    self.active_edge.from_port = target_output
                    self.active_edge.to_port = target_input
                    self.active_edge.update_path()
                    if self.active_edge not in self.edges:
                        self.edges.append(self.active_edge)
                    self._trigger_plug(target_output, target_input)

                    out_type = self._get_port_data_type(target_output)
                    in_type = self._get_port_data_type(target_input)
                    if out_type != "any" and in_type != "any" and out_type != in_type:
                        from_name = target_output.parentItem().node_definition.name
                        to_name = target_input.parentItem().node_definition.name
                        msg = (
                            f"Type mismatch: '{from_name}.{target_output.port_definition.name}' "
                            f"({out_type}) → '{to_name}.{target_input.port_definition.name}' ({in_type})"
                        )
                        if self.parent() and hasattr(self.parent(), 'log_panel'):
                            self.parent().log_panel.log(msg, "warning")

                    self.active_edge = None
                else:
                    self.removeItem(self.active_edge)
                    self.active_edge = None
            else:
                self.removeItem(self.active_edge)
                self.active_edge = None
            
            # Reset snapped state
            if self._snapped_port:
                self._snapped_port.hoverLeaveEvent(None)
                self._snapped_port = None
                
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        for item in self.items(event.scenePos()):
            target = item
            while target is not None and not isinstance(target, NodeWidget):
                target = target.parentItem()
            if isinstance(target, NodeWidget) and getattr(target.node_definition, 'node_id', '') == 'group_node':
                parent = self.parent()
                if parent and hasattr(parent, '_open_subgraph_tab'):
                    parent._open_subgraph_tab(target)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        from PyQt5.QtWidgets import QApplication, QLineEdit, QTextEdit, QPlainTextEdit
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key_Delete:
            self.push_history()
            for item in self.selectedItems():
                if isinstance(item, Edge):
                    if item in self.edges:
                        from_p = item.from_port
                        to_p = item.to_port
                        self.edges.remove(item)
                        self._trigger_unplug(from_p, to_p)
                    self.removeItem(item)
                elif isinstance(item, NodeWidget):
                    self._remove_node_widget(item)
                elif isinstance(item, StickyNote):
                    if item in self.sticky_notes: self.sticky_notes.remove(item)
                    self.removeItem(item)
                elif isinstance(item, Backdrop):
                    if item in self.backdrops: self.backdrops.remove(item)
                    self.removeItem(item)
        super().keyPressEvent(event)

    def _remove_node_widget(self, node_widget):
        edges_to_remove = [e for e in self.edges if e.from_port.parentItem() == node_widget or e.to_port.parentItem() == node_widget]
        for e in edges_to_remove:
            from_p = e.from_port
            to_p = e.to_port
            self.edges.remove(e)
            self.removeItem(e)
            self._trigger_unplug(from_p, to_p)
        if node_widget in self.nodes:
            self.nodes.remove(node_widget)
        self.removeItem(node_widget)

    def contextMenuEvent(self, event):
        # Delegate to item-level context menus first
        for item in self.items(event.scenePos()):
            if isinstance(item, (StickyNote, Backdrop)):
                item.contextMenuEvent(event)
                return

        menu = QMenu()
        pos = event.scenePos()
        
        selected_items = self.selectedItems()
        selected_nodes = [i for i in selected_items if isinstance(i, NodeWidget)]
        
        # 1. Option to wrap selection in Backdrop
        if selected_nodes:
            # EDIT NODE (open Node Builder for the first selected node's definition)
            editable_ids = [
                n.node_definition.node_id
                for n in selected_nodes
                if NodeRegistry.get_source_path(getattr(n.node_definition, 'node_id', '')) is not None
            ]
            if editable_ids:
                first_id = editable_ids[0]
                edit_label = f"Edit Node ('{first_id}')" if len(editable_ids) == 1 else f"Edit Node ('{first_id}')..."
                edit_act = QAction(edit_label, self.parent())
                def do_edit(_checked=False, nid=first_id):
                    parent = self.parent()
                    if parent and hasattr(parent, '_on_edit_requested'):
                        parent._on_edit_requested(nid)
                edit_act.triggered.connect(do_edit)
                menu.addAction(edit_act)
                menu.addSeparator()

            copy_act = QAction(f"Copy {len(selected_nodes)} Nodes", self.parent())
            copy_act.triggered.connect(self.copy_selection)
            menu.addAction(copy_act)

            # BYPASS Options
            any_bypassed = any(n.bypassed for n in selected_nodes)
            any_not_bypassed = any(not n.bypassed for n in selected_nodes)
            
            if any_not_bypassed:
                bypass_act = QAction("Bypass Selected Nodes", self.parent())
                def do_bypass():
                    self.push_history()
                    for n in selected_nodes: n.set_bypassed(True)
                bypass_act.triggered.connect(do_bypass)
                menu.addAction(bypass_act)
                
            if any_bypassed:
                unbypass_act = QAction("Unbypass Selected Nodes", self.parent())
                def do_unbypass():
                    self.push_history()
                    for n in selected_nodes: n.set_bypassed(False)
                unbypass_act.triggered.connect(do_unbypass)
                menu.addAction(unbypass_act)

            any_init = any(n.init_priority > 0 for n in selected_nodes)
            any_not_init = any(n.init_priority == 0 for n in selected_nodes)

            if any_not_init:
                init_act = QAction("Mark as Init Node (runs first)", self.parent())
                def do_mark_init():
                    self.push_history()
                    for n in selected_nodes: n.set_init_priority(1)
                init_act.triggered.connect(do_mark_init)
                menu.addAction(init_act)

            if any_init:
                uninit_act = QAction("Remove Init Priority", self.parent())
                def do_remove_init():
                    self.push_history()
                    for n in selected_nodes: n.set_init_priority(0)
                uninit_act.triggered.connect(do_remove_init)
                menu.addAction(uninit_act)

            # RELOAD node from disk — refresh ports / code without re-adding
            reloadable_ids = sorted({
                n.node_definition.node_id
                for n in selected_nodes
                if NodeRegistry.get_source_path(getattr(n.node_definition, 'node_id', '')) is not None
            })
            if reloadable_ids:
                if len(reloadable_ids) == 1:
                    reload_act = QAction(f"Reload Node ('{reloadable_ids[0]}')", self.parent())
                else:
                    reload_act = QAction(f"Reload {len(reloadable_ids)} Node Types from Disk", self.parent())
                def do_reload(_checked=False, ids=reloadable_ids):
                    self.push_history()
                    for nid in ids:
                        self.reload_node_type(nid)
                reload_act.triggered.connect(do_reload)
                menu.addAction(reload_act)

            menu.addSeparator()
            
            wrap_act = QAction(f"Wrap {len(selected_nodes)} Nodes in Box", self.parent())
            def wrap_selection():
                self.push_history()
                # Calculate bounding rect of all selected nodes
                rect = selected_nodes[0].sceneBoundingRect()
                for node in selected_nodes[1:]:
                    rect = rect.united(node.sceneBoundingRect())
                
                # Add padding
                padding = 40
                box_pos = (rect.x() - padding, rect.y() - padding - 20) # Extra top for title
                box_size = (rect.width() + padding*2, rect.height() + padding*2 + 20)
                
                self.add_backdrop(title="Grouped Nodes", pos=box_pos, size=box_size)
            
            wrap_act.triggered.connect(wrap_selection)
            menu.addAction(wrap_act)
            menu.addSeparator()

        if global_clipboard.get("nodes"):
            paste_act = QAction("Paste Nodes", self.parent())
            paste_act.triggered.connect(lambda: self.paste_selection(target_pos=pos))
            menu.addAction(paste_act)
            menu.addSeparator()

        # Core Items
        add_note_act = QAction("Add Sticky Note", self.parent())
        add_note_act.triggered.connect(lambda: self.add_sticky_note(pos=(pos.x(), pos.y())))
        menu.addAction(add_note_act)
        
        add_bd_act = QAction("Add Network Box (Backdrop)", self.parent())
        add_bd_act.triggered.connect(lambda: self.add_backdrop(pos=(pos.x(), pos.y())))
        menu.addAction(add_bd_act)
        
        menu.addSeparator()
        
        # Search Nodes option (Tab shortcut)
        search_act = QAction("Search Nodes...  (Tab)", self.parent())
        def show_search():
            view = self.views()[0] if self.views() else None
            if view and hasattr(view, 'show_node_search_popup'):
                view.show_node_search_popup(pos)
        search_act.triggered.connect(show_search)
        menu.addAction(search_act)
        
        # Nodes Submenu
        node_menu = menu.addMenu("Add Node")
        for node_id in NodeRegistry.list_node_ids():
            action = QAction(f"{node_id}", self.parent())
            def spawn_node(nid=node_id, p=pos):
                result = self.add_node_by_name(nid, p)
                if result:
                    self.push_history()
            action.triggered.connect(spawn_node)
            node_menu.addAction(action)
            
        if not menu.isEmpty(): exec_dialog(menu, event.screenPos())
        else: super().contextMenuEvent(event)

    def add_node_by_name(self, node_id, pos):
        if isinstance(pos, tuple): pos = QPointF(pos[0], pos[1])
        node_class = NodeRegistry.get_class(node_id)
        if not node_class:
            from src.nodes.base import NodeRegistry as BaseRegistry
            node_class = BaseRegistry.get_node_class(node_id)
        if node_class:
            try:
                node_definition = node_class()
            except Exception as e:
                msg = f"Failed to create node '{node_id}': {e}"
                print(msg)
                if self.parent() and hasattr(self.parent(), 'log_panel'):
                    self.parent().log_panel.log(msg, "error")
                return None
            if self.parent() and hasattr(self.parent(), 'log_panel'):
                lp = self.parent().log_panel
                node_definition._on_log = lambda msg, level: lp.log(f"[{node_definition.name}] {msg}", level)
            node_widget = NodeWidget(node_definition)
            node_definition._on_ports_changed = node_widget.rebuild_ports
            node_definition._is_port_connected = node_widget.is_port_connected
            node_definition._on_dropdown_options_changed = node_widget.update_dropdown_options
            node_widget.setPos(pos)
            self.addItem(node_widget)
            self.nodes.append(node_widget)

            # Inherit theme
            is_dark = self.backgroundBrush().color().lightness() < 128
            node_widget.apply_theme(is_dark)

            # Ensure states are initialized correctly (all enabled)
            node_widget._refresh_widget_states()

            # Honor class-level init_first flag from the node builder
            if getattr(node_definition, 'init_first', False) or getattr(node_class, 'init_first', False):
                node_widget.set_init_priority(1)
            return node_widget
        return None

    def find_node_by_name(self, name: str):
        for node in self.nodes:
            if node.node_definition.name == name: return node
        return None

    def reload_node_type(self, node_id: str) -> int:
        """Re-read this node's JSON definition from disk and refresh every
        live instance of it in the scene.

        Existing connections are preserved where the port name still exists
        on the new definition; connections to removed ports are dropped.
        Saved parameter values are re-applied where the port still exists.

        Returns the number of widgets that were refreshed.
        """
        ok = NodeRegistry.reload_node_definition(node_id)
        if not ok:
            err = NodeRegistry.last_error or f"Reload failed for '{node_id}'"
            if self.parent() and hasattr(self.parent(), 'log_panel'):
                self.parent().log_panel.log(err, "error")
            return 0

        node_class = NodeRegistry.get_class(node_id)
        if not node_class:
            return 0

        refreshed = 0
        for node_widget in list(self.nodes):
            inst_id = getattr(node_widget.node_definition, 'node_id', None)
            if inst_id != node_id:
                continue
            try:
                new_definition = node_class()
            except Exception as e:
                if self.parent() and hasattr(self.parent(), 'log_panel'):
                    self.parent().log_panel.log(
                        f"Reload: failed to instantiate '{node_id}': {e}", "error"
                    )
                continue

            # Re-wire engine/UI hooks so the rebuilt instance behaves like a
            # freshly added node.
            if self.parent() and hasattr(self.parent(), 'log_panel'):
                lp = self.parent().log_panel
                new_definition._on_log = lambda msg, level, name=new_definition.name: lp.log(
                    f"[{name}] {msg}", level
                )
            new_definition._on_ports_changed = node_widget.rebuild_ports
            new_definition._is_port_connected = node_widget.is_port_connected
            new_definition._on_dropdown_options_changed = node_widget.update_dropdown_options

            node_widget.reload_definition(new_definition)
            refreshed += 1

        if self.parent() and hasattr(self.parent(), 'log_panel'):
            self.parent().log_panel.log(
                f"Reloaded '{node_id}' — {refreshed} instance(s) updated.", "success"
            )
        return refreshed

    def connect_nodes(self, from_node, from_port_name, to_node, to_port_name):
        self.push_history()
        if isinstance(from_node, str): from_node = self.find_node_by_name(from_node)
        if isinstance(to_node, str): to_node = self.find_node_by_name(to_node)
        if not from_node or not to_node: return None
        from_port = next((p for p in from_node.output_widgets if p.port_definition.name == from_port_name), None)
        to_port = next((p for p in to_node.input_widgets if p.port_definition.name == to_port_name), None)
        if from_port and to_port:
            old_edge = next((e for e in self.edges if e.to_port == to_port), None)
            if old_edge:
                from_p = old_edge.from_port
                to_p = old_edge.to_port
                self.removeItem(old_edge)
                self.edges.remove(old_edge)
                self._trigger_unplug(from_p, to_p)
            edge = Edge(from_port, to_port)
            is_dark = self.backgroundBrush().color().lightness() < 128
            edge.apply_theme(is_dark)
            self.addItem(edge)
            self.edges.append(edge)
            edge.update_path()
            self._trigger_plug(from_port, to_port)
            return edge
        return None

    def update_edge_value(self, node_widget, port_name, value):
        """Push a live execution value to edges and destination canvas widgets."""
        for edge in self.edges:
            if (edge.from_port is not None
                    and edge.to_port is not None
                    and edge.from_port.parentItem() is node_widget
                    and edge.from_port.port_definition.name == port_name):

                # Update the live value shown on the wire.
                edge.set_live_value(value)

                # Mirror data values into the destination widget.
                # Execution pins should not become normal parameters.
                if edge.to_port.port_definition.data_type != "exec":
                    target_widget = edge.to_port.parentItem()
                    target_port_name = edge.to_port.port_definition.name

                    target_widget.set_parameter(
                        target_port_name,
                        value,
                        propagate=False,
                    )

    def clear_edge_values(self):
        """Clear all live value tooltips from every edge (call at execution start)."""
        for edge in self.edges:
            edge.clear_live_value()

    def apply_theme(self, is_dark=True):
        if is_dark:
            self.setBackgroundBrush(QColor(40, 40, 40))
            self.grid_pen = QPen(QColor("#555555"), 0.5)
        else:
            self.setBackgroundBrush(QColor(255, 255, 255))
            self.grid_pen = QPen(QColor("#d0d0d0"), 0.5)
        
        for node in self.nodes:
            node.apply_theme(is_dark)
        for edge in self.edges:
            edge.apply_theme(is_dark)
        self.update()
