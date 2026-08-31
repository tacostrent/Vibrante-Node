from src.utils.qt_compat import QtWidgets, QtCore, QtGui, exec_dialog

QGraphicsItem = QtWidgets.QGraphicsItem
QGraphicsRectItem = QtWidgets.QGraphicsRectItem
QGraphicsTextItem = QtWidgets.QGraphicsTextItem
QGraphicsProxyWidget = QtWidgets.QGraphicsProxyWidget
QLineEdit = QtWidgets.QLineEdit
QSpinBox = QtWidgets.QSpinBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QCheckBox = QtWidgets.QCheckBox
QLabel = QtWidgets.QLabel
_QComboBox = QtWidgets.QComboBox
QSlider = QtWidgets.QSlider
QTextEdit = QtWidgets.QTextEdit
QWidget = QtWidgets.QWidget
QHBoxLayout = QtWidgets.QHBoxLayout
QPushButton = QtWidgets.QPushButton
QVBoxLayout = QtWidgets.QVBoxLayout

Qt = QtCore.Qt
QRectF = QtCore.QRectF

QColor = QtGui.QColor
QPen = QtGui.QPen
QBrush = QtGui.QBrush
QPixmap = QtGui.QPixmap
QPainterPath = QtGui.QPainterPath
class _MenuCloser(QtCore.QObject):
    """App-level event filter that closes a popup QMenu on the first mouse
    press outside it.  Needed because QGraphicsView consumes press events
    before Qt's built-in popup-dismiss logic can see them."""

    def __init__(self, menu):
        super().__init__(menu)
        self._menu = menu
        QtWidgets.QApplication.instance().installEventFilter(self)
        menu.aboutToHide.connect(self._remove)

    def _remove(self):
        QtWidgets.QApplication.instance().removeEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            menu_rect = QtCore.QRect(
                self._menu.mapToGlobal(QtCore.QPoint(0, 0)),
                self._menu.size()
            )
            if not menu_rect.contains(QtGui.QCursor.pos()):
                self._menu.close()
        return False


class _MainThreadDispatcher(QtCore.QObject):
    """Routes callables from background threads onto the Qt main thread.

    Emitting a pyqtSignal from a non-main thread with a QueuedConnection
    (Qt's default when receiver and sender live in different threads) posts
    the call to the receiver's thread event loop.  NodeWidget uses this to
    dispatch _propagate_all_outputs back to the main thread after
    on_parameter_changed completes in the AsyncRuntime background thread.
    """
    _dispatch = QtCore.pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._dispatch.connect(self._run, QtCore.Qt.QueuedConnection)

    def post(self, fn):
        """Schedule fn() on the main thread from any thread."""
        self._dispatch.emit(fn)

    def _run(self, fn):
        fn()


_main_dispatcher = _MainThreadDispatcher()


class QComboBox(_QComboBox):
    """QComboBox that works correctly inside a QGraphicsProxyWidget.

    Qt's default popup is rendered within the proxy's composite layer, so
    sibling proxy widgets that were added later (higher paint order) appear
    on top of it.  This override replaces the popup with a QMenu, which is
    always a native OS window and therefore renders above all scene items.
    Position is calculated through the full proxy→scene→view→global chain so
    it lands correctly regardless of zoom or pan.
    """

    def showPopup(self):
        proxy = self._proxy()
        if proxy is None:
            super().showPopup()
            return

        scene = proxy.scene()
        if not scene or not scene.views():
            super().showPopup()
            return

        view = scene.views()[0]

        # Walk from self up to the proxy container to accumulate the
        # combobox's offset within the proxy's item-local coordinate space.
        offset = QtCore.QPoint(0, 0)
        w = self
        container = proxy.widget()
        while w is not None and w is not container:
            offset += w.pos()
            w = w.parentWidget()

        # Map the combobox bottom-left through scene→viewport→global.
        combo_bl = QtCore.QPointF(offset.x(), offset.y() + self.height())
        global_pt = view.viewport().mapToGlobal(
            view.mapFromScene(proxy.mapToScene(combo_bl))
        )

        # Build menu. Stored on self to survive past showPopup() returning
        # (popup() is non-blocking so the local ref would be GC'd immediately).
        self._active_menu = QtWidgets.QMenu()
        self._active_menu.setMinimumWidth(self.width())
        self._active_menu.setStyleSheet(
            "QMenu { background-color: #2b2b2b; color: #ddd;"
            "        border: 1px solid #555; }"
            "QMenu::item { padding: 4px 16px; }"
            "QMenu::item:selected { background-color: #4a90d9; color: white; }"
        )
        for i in range(self.count()):
            action = self._active_menu.addAction(self.itemText(i))
            action.setData(i)

        def _on_triggered(action):
            self.setCurrentIndex(action.data())

        self._active_menu.triggered.connect(_on_triggered)
        # Defer ref-clear so Qt finishes all signal emission before C++ teardown.
        self._active_menu.aboutToHide.connect(
            lambda: QtCore.QTimer.singleShot(0, lambda: setattr(self, '_active_menu', None))
        )

        # Install app-level closer so one outside click always dismisses the menu
        # even when QGraphicsView would otherwise consume the press event.
        _MenuCloser(self._active_menu)

        self._active_menu.popup(global_pt)
        self._active_menu.activateWindow()

    def _proxy(self):
        w = self
        while w is not None:
            p = w.graphicsProxyWidget()
            if p is not None:
                return p
            w = w.parentWidget()
        return None


from src.ui.port_widget import PortWidget
from src.ui.script_editor import ScriptEditorDialog
from src.utils.runtime import AsyncRuntime
from src.utils.paths import resource_path
from uuid import uuid4

class NodeWidget(QGraphicsItem):
    def __init__(self, node_definition, instance_id=None, parent=None):
        super().__init__(parent)
        self.node_definition = node_definition
        self.instance_id = instance_id or uuid4()
        self.width = 220
        self.height = 140 # Initial minimum
        
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        
        self.input_widgets = []
        self.output_widgets = []
        self.input_labels = []
        self.output_labels = []
        self.param_widgets = {} # name -> proxy_widget (QGraphicsProxyWidget)
        self._param_raw_widgets = {} # name -> raw Qt widget (QLineEdit, QComboBox, etc.)
        self.status = "idle" # idle, running, success, failed
        self.is_dark = True
        self.bypassed = False
        self.init_priority = 0
        self._is_propagating = False # Recursion guard

        # Default rects so hoverMoveEvent is safe before _auto_size runs
        self.bypass_rect = QRectF(0, 0, 0, 0)
        self.init_rect = QRectF(0, 0, 0, 0)
        self._active_tooltip_region = None  # tracks which button tooltip is visible

        self.setAcceptHoverEvents(True)
        self._init_ui()

    def apply_theme(self, is_dark=True):
        self.is_dark = is_dark
        q_text_color = QColor(Qt.white) if is_dark else QColor(Qt.black)
        
        if hasattr(self, 'title_text') and self.title_text:
            self.title_text.setDefaultTextColor(q_text_color)
            
        for label in self.input_labels + self.output_labels:
            label.setDefaultTextColor(q_text_color)
            
        # Update parameter labels and widgets via stylesheet
        bg_color = "#333" if is_dark else "#eee"
        border_color = "#555" if is_dark else "#ccc"
        label_color = "#aaa" if is_dark else "#555"
        text_color_name = q_text_color.name()
        
        for proxy in self.param_widgets.values():
            container = proxy.widget()
            if not container: continue

            param_label = container.findChild(QLabel)
            if param_label:
                param_label.setStyleSheet(f"color: {label_color}; font-size: 9px; font-weight: bold; background: transparent;")

            for w in container.findChildren((QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit)):
                w.setStyleSheet(f"background-color: {bg_color}; color: {text_color_name}; border: 1px solid {border_color};")

            for w in container.findChildren(QCheckBox):
                w.setStyleSheet(f"color: {text_color_name}; background: transparent;")

            # QComboBox: only style the box itself — no ::drop-down or ::down-arrow
            # overrides so Fusion keeps drawing the native arrow icon.
            for w in container.findChildren(QComboBox):
                w.setStyleSheet(
                    f"QComboBox {{ background-color: {bg_color}; color: {text_color_name};"
                    f" border: 1px solid {border_color}; padding: 1px 4px; }}"
                )

            # QSlider: provide groove + handle so the track and thumb are visible.
            handle_color = "#6699cc" if is_dark else "#4a90d9"
            groove_bg    = "#555555" if is_dark else "#cccccc"
            for w in container.findChildren(QSlider):
                w.setStyleSheet(f"""
                    QSlider::groove:horizontal {{
                        height: 4px; background: {groove_bg};
                        border-radius: 2px; margin: 0px;
                    }}
                    QSlider::sub-page:horizontal {{
                        background: {handle_color}; border-radius: 2px;
                    }}
                    QSlider::handle:horizontal {{
                        background: {handle_color}; border: none;
                        width: 12px; height: 12px;
                        margin: -4px 0; border-radius: 6px;
                    }}
                """)

            # QsciScintilla-based code editors (text_area widgets) use their own theme API
            try:
                from PyQt5.Qsci import QsciScintilla
                for w in container.findChildren(QsciScintilla):
                    if hasattr(w, 'apply_theme'):
                        w.apply_theme(is_dark)
            except ImportError:
                pass
        
        self.update()

    def _init_ui(self):
        # Header
        self.title_text = QGraphicsTextItem(self.node_definition.name, self)
        self.title_text.setDefaultTextColor(Qt.white)
        self.title_text.setPos(10, 5)
        
        self.rebuild_ports()

    def rebuild_ports(self):
        """Dynamic port reconstruction."""
        # 1. Identify affected edges BEFORE detaching old ports
        affected_edges_out = [] # (edge, port_name)
        affected_edges_in = [] # (edge, port_name)
        
        if self.scene():
            for edge in self.scene().edges:
                if edge.from_port in self.output_widgets:
                    affected_edges_out.append((edge, edge.from_port.port_definition.name))
                if edge.to_port in self.input_widgets:
                    affected_edges_in.append((edge, edge.to_port.port_definition.name))

        # 2. Clear old port widgets and labels
        for w in self.input_widgets + self.output_widgets + self.input_labels + self.output_labels:
            if self.scene() and w.scene(): 
                self.scene().removeItem(w)
            else:
                w.setParentItem(None)
                
        self.input_widgets.clear()
        self.output_widgets.clear()
        self.input_labels.clear()
        self.output_labels.clear()

        # 3. Create Ports (Sorted: exec first)
        y_in = 45
        inputs = self.node_definition.inputs
        input_list = inputs if isinstance(inputs, list) else inputs.values()
        
        # Sort so 'exec' type comes first
        sorted_inputs = sorted(input_list, key=lambda x: 0 if getattr(x, 'type', 'any').lower() == 'exec' or getattr(x, 'data_type', 'any').lower() == 'exec' else 1)
        
        for p_model in sorted_inputs:
            p = PortWidget(p_model, is_input=True, parent=self)
            p.setPos(0, y_in)
            self.input_widgets.append(p)
            
            label_text = p_model.name
            if p.port_type == "exec" and label_text in ["in", "exec_in", "trigger"]:
                label_text = ""
                
            label = QGraphicsTextItem(label_text, self)
            label.setDefaultTextColor(Qt.white if self.is_dark else Qt.black)
            label.setFont(self._get_port_font())
            label.setPos(12, y_in - 10)
            self.input_labels.append(label)
            y_in += 25
            
        y_out = 45
        outputs = self.node_definition.outputs
        output_list = outputs if isinstance(outputs, list) else outputs.values()
        
        # Sort so 'exec' type comes first
        sorted_outputs = sorted(output_list, key=lambda x: 0 if getattr(x, 'type', 'any').lower() == 'exec' or getattr(x, 'data_type', 'any').lower() == 'exec' else 1)

        for p_model in sorted_outputs:
            p = PortWidget(p_model, is_input=False, parent=self)
            p.setPos(self.width, y_out)
            self.output_widgets.append(p)
            
            label_text = p_model.name
            if p.port_type == "exec" and label_text in ["out", "exec_out", "then", "exit"]:
                label_text = ""
                
            label = QGraphicsTextItem(label_text, self)
            label.setDefaultTextColor(Qt.white if self.is_dark else Qt.black)
            label.setFont(self._get_port_font())
            self.output_labels.append(label)
            y_out += 25

        # 4. Parameter Widgets (Only create if not already exists)
        for p_model in input_list:
            if hasattr(p_model, 'widget_type') and p_model.widget_type:
                if p_model.name not in self.param_widgets:
                    self._create_param_widget(p_model)

        # If this is a python_script node, add an "Edit Script" button proxy
        try:
            if getattr(self.node_definition, 'node_id', None) in ('python_script', 'maya_action_custom', 'houdini_action_custom') and '_script_btn' not in self.param_widgets:
                proxy = QGraphicsProxyWidget(self)
                container = QWidget()
                lay = QVBoxLayout(container)
                lay.setContentsMargins(0, 0, 0, 0)
                btn = QPushButton('Edit Script')
                btn.clicked.connect(self._open_script_editor)
                lay.addWidget(btn)
                proxy.setWidget(container)
                self.param_widgets['_script_btn'] = proxy
        except Exception:
            pass

        # 5. Calculate Dynamic Height
        proxies = list(self.param_widgets.values())
        params_total_height = 0
        for p in proxies:
            params_total_height += p.widget().sizeHint().height() + 10
            
        ports_max_y = max(y_in, y_out)
        self.height = max(140, ports_max_y + params_total_height + 20)
        
        self._auto_size(ports_max_y)
        
        # 6. Reconnect Edges to new PortWidgets
        for edge, name in affected_edges_out:
            new_p = next((p for p in self.output_widgets if p.port_definition.name == name), None)
            if new_p: 
                edge.from_port = new_p
                edge.update_path()
            else:
                # Port gone? Remove edge
                if self.scene() and edge in self.scene().edges:
                    self.scene().removeItem(edge)
                    self.scene().edges.remove(edge)

        for edge, name in affected_edges_in:
            new_p = next((p for p in self.input_widgets if p.port_definition.name == name), None)
            if new_p: 
                edge.to_port = new_p
                edge.update_path()
            else:
                if self.scene() and edge in self.scene().edges:
                    self.scene().removeItem(edge)
                    self.scene().edges.remove(edge)

    def _auto_size(self, ports_bottom_y):
        """Dynamically scales the node width and centers children."""
        self.prepareGeometryChange()
        
        # 1. Width Calculation
        # Reset text width so we measure the natural (unconstrained) text width.
        if hasattr(self, 'title_text') and self.title_text:
            self.title_text.setTextWidth(-1)

        min_width = 220
        content_width = 0
        if hasattr(self, 'title_text') and self.title_text:
            # Reserve room for both header buttons (I + B = 58px) plus margins.
            # Use 32px as the conservative title-start offset (icon case).
            content_width = max(content_width, self.title_text.boundingRect().width() + 95)
        for proxy in self.param_widgets.values():
            w = proxy.widget()
            if w:
                content_width = max(content_width, w.sizeHint().width() + 100)
        for i in range(max(len(self.input_labels), len(self.output_labels))):
            w_row = 80
            if i < len(self.input_labels): w_row += self.input_labels[i].boundingRect().width()
            if i < len(self.output_labels): w_row += self.output_labels[i].boundingRect().width()
            content_width = max(content_width, w_row + 20)
        self.width = max(min_width, content_width)
        
        # Bypass Button Position (Top Right); Init button sits to its left
        self.bypass_rect = QRectF(self.width - 30, 5, 25, 25)
        self.init_rect = QRectF(self.width - 58, 5, 25, 25)

        # Clamp title text so it never bleeds into the button area.
        # 10 = left margin; 5 = gap before init button.
        if hasattr(self, 'title_text') and self.title_text:
            max_title_w = max(30, int(self.init_rect.x()) - 10 - 5)
            self.title_text.setTextWidth(max_title_w)
            self.title_text.setFlag(QGraphicsItem.ItemClipsToShape, True)

        # 2. Vertical Centering for params
        body_top = ports_bottom_y + 10
        body_bottom = self.height - 10
        proxies = list(self.param_widgets.values())
        if proxies:
            total_h = sum([p.widget().sizeHint().height() for p in proxies])
            spacing = max(5, (body_bottom - body_top - total_h) / (len(proxies) + 1))
            current_y = body_top + spacing
            for proxy in proxies:
                w = proxy.widget()
                if w:
                    w.setFixedWidth(int(self.width - 100)) 
                    proxy.setPos(50, int(current_y))
                    current_y += w.sizeHint().height() + spacing

        # 3. Reposition Outputs
        for i, p in enumerate(self.output_widgets):
            p.setPos(self.width, p.pos().y())
            if i < len(self.output_labels):
                label = self.output_labels[i]
                label.setPos(self.width - label.boundingRect().width() - 12, p.pos().y() - 10)
        
        self._refresh_widget_states()

    def _refresh_widget_states(self):
        """Disables widgets if their input port has a connection."""
        if not self.scene(): return
        for p_name, proxy in self.param_widgets.items():
            port_widget = next((pw for pw in self.input_widgets if pw.port_definition.name == p_name), None)
            if port_widget:
                is_connected = any(e.to_port == port_widget for e in self.scene().edges)
                container = proxy.widget()
                container.setEnabled(not is_connected)
                for child in container.findChildren(QWidget):
                    child.setEnabled(not is_connected)

    def _get_port_font(self):
        QFont = QtGui.QFont
        f = QFont("Arial", 8)
        return f

    def _create_param_widget(self, p_model):
        proxy = QGraphicsProxyWidget(self)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        param_label = QLabel(p_model.name)
        param_label.setStyleSheet("color: #aaa; font-size: 9px; font-weight: bold; background: transparent;")
        layout.addWidget(param_label)
        
        w = None
        if p_model.widget_type == 'text':
            w = QLineEdit()
            val = self.node_definition.parameters.get(p_model.name)
            w.setText(str(val) if val is not None else "")
            w.textChanged.connect(lambda val: self._update_param(p_model.name, val))
        elif p_model.widget_type == 'text_area':
            from src.ui.code_editor import CodeEditor
            w = CodeEditor()
            # HACK: Disable line numbers for small widget
            w.lineNumberArea.hide()
            w.setViewportMargins(0, 0, 0, 0)
            w.setMaximumHeight(80)
            w.setMinimumWidth(150)
            
            # Fetch Houdini completions if this is a Houdini node
            if self.node_definition.category == "Houdini":
                from src.utils.hou_bridge import is_available, get_bridge
                if is_available():
                    try:
                        bridge = get_bridge()
                        w.append_completer_list(bridge.get_completions())
                    except: pass

            val = self.node_definition.parameters.get(p_model.name)
            w.setPlainText(str(val) if val is not None else "")
            w.textChanged.connect(lambda: self._update_param(p_model.name, w.toPlainText()))
        elif p_model.widget_type == 'int':
            w = QSpinBox()
            w.setRange(-999999, 999999)
            val = self.node_definition.parameters.get(p_model.name)
            w.setValue(int(val) if val is not None else 0)
            w.valueChanged.connect(lambda val: self._update_param(p_model.name, val))
        elif p_model.widget_type == 'float':
            w = QDoubleSpinBox()
            w.setRange(-999999.0, 999999.0)
            val = self.node_definition.parameters.get(p_model.name)
            w.setValue(float(val) if val is not None else 0.0)
            w.valueChanged.connect(lambda val: self._update_param(p_model.name, val))
        elif p_model.widget_type == 'bool':
            w = QCheckBox()
            val = self.node_definition.parameters.get(p_model.name)
            w.setChecked(bool(val) if val is not None else False)
            w.stateChanged.connect(lambda val: self._update_param(p_model.name, bool(val)))
        elif p_model.widget_type == 'dropdown':
            w = QComboBox()
            if hasattr(p_model, 'options') and p_model.options:
                w.addItems(p_model.options)
            val = self.node_definition.parameters.get(p_model.name)
            if val is not None:
                w.setCurrentText(str(val))
            elif hasattr(p_model, 'default') and p_model.default is not None:
                w.setCurrentText(str(p_model.default))
            # Always sync parameters to what the combobox actually shows — setCurrentText("")
            # on a non-empty list leaves the widget at index 0 but keeps parameters as "",
            # causing execute to receive "" instead of the displayed item.
            self.node_definition.parameters[p_model.name] = w.currentText()
            w.currentTextChanged.connect(lambda val: self._update_param(p_model.name, val))
        elif p_model.widget_type == 'slider':
            w = QSlider(Qt.Horizontal)
            w.setRange(0, 100)
            val = self.node_definition.parameters.get(p_model.name)
            w.setValue(int(val) if val is not None else 0)
            w.valueChanged.connect(lambda val: self._update_param(p_model.name, val))
        elif p_model.widget_type in ('file', 'file_save'):
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(2)
            path_edit = QLineEdit()
            val = self.node_definition.parameters.get(p_model.name)
            path_edit.setText(str(val) if val is not None else "")
            btn = QPushButton("...")
            btn.setFixedWidth(25)
            is_save = p_model.widget_type == 'file_save'
            def select_file(_checked=None, save=is_save):
                QFileDialog = QtWidgets.QFileDialog
                curr = self.scene().views()[0] if self.scene() and self.scene().views() else None
                if save:
                    path, _ = QFileDialog.getSaveFileName(curr, "Save File")
                else:
                    path, _ = QFileDialog.getOpenFileName(curr, "Select File")
                if path:
                    path_edit.setText(path)
                    self._update_param(p_model.name, path)
            btn.clicked.connect(select_file)
            path_edit.textChanged.connect(lambda val: self._update_param(p_model.name, val))
            l.addWidget(path_edit)
            l.addWidget(btn)
            # For file widgets the editable part is path_edit, not the outer QWidget wrapper
            self._param_raw_widgets[p_model.name] = path_edit

        if w is not None:
            w.setStyleSheet("background-color: #333; color: white; border: 1px solid #555;")
            layout.addWidget(w)
            # Store direct reference; file widgets already stored path_edit above
            if p_model.name not in self._param_raw_widgets:
                self._param_raw_widgets[p_model.name] = w

        container.setStyleSheet("background: transparent;")
        proxy.setWidget(container)
        self.param_widgets[p_model.name] = proxy

    def set_parameter(self, name, value, propagate=True):
        """Programmatically set a parameter and update its UI widget."""
        if self._is_propagating: return # Guard against cycles
        
        # Type Conversion attempt based on port definition
        inputs = self.node_definition.inputs
        input_list = inputs if isinstance(inputs, list) else inputs.values()
        outputs = self.node_definition.outputs
        output_list = outputs if isinstance(outputs, list) else outputs.values()
        
        port_def = next((p for p in input_list if p.name == name), None)
        if not port_def:
             port_def = next((p for p in output_list if p.name == name), None)
        
        target_value = value
        if port_def and not isinstance(value, list):  # never coerce a list — it may be dropdown options
            try:
                data_type = getattr(port_def, 'data_type', getattr(port_def, 'type', 'any')).lower()
                if data_type == 'int': target_value = int(value)
                elif data_type in ['float', 'number']: target_value = float(value)
                elif data_type == 'string': target_value = str(value)
                elif data_type == 'bool':
                    if isinstance(value, str): target_value = value.lower() in ['true', '1', 'yes']
                    else: target_value = bool(value)
            except (ValueError, TypeError):
                pass

        if self.node_definition.parameters.get(name) == target_value:
            return # No change
            
        self.node_definition.parameters[name] = target_value
        
        # 1. Update UI — use direct widget reference (never findChild)
        w = self._param_raw_widgets.get(name)
        if w is not None:
            w.blockSignals(True)
            if isinstance(w, QLineEdit):
                if isinstance(target_value, float):
                    display_value = f"{target_value:.6g}"
                else:
                    display_value = str(target_value) if target_value is not None else ""

                w.setText(display_value)
            elif isinstance(w, (QSpinBox, QDoubleSpinBox, QSlider)):
                if target_value is not None:
                    try:
                        w.setValue(target_value)
                    except TypeError:
                        pass
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(target_value))
            elif isinstance(w, QComboBox):
                if isinstance(target_value, list):
                    w.clear()
                    w.addItems([str(i) for i in target_value])
                    if target_value:
                        w.setCurrentIndex(0)
                else:
                    w.setCurrentText(str(target_value) if target_value is not None else "")
            elif isinstance(w, QTextEdit):
                w.setPlainText(str(target_value) if target_value is not None else "")
            w.blockSignals(False)

        # 2. Trigger node logic, then push downstream so on_parameter_changed
        #    (which may update output ports via set_output) runs before propagation.
        if propagate:
            async def _run_on_change():
                await self.node_definition.on_parameter_changed(name, target_value)
                # Dispatch Qt widget operations to the main thread — accessing
                # scene().edges and calling w.blockSignals/setText from the
                # background AsyncRuntime thread causes a Qt threading crash.
                _main_dispatcher.post(self._propagate_all_outputs)
            AsyncRuntime.run_coroutine(_run_on_change())
        else:
            AsyncRuntime.run_coroutine(self.node_definition.on_parameter_changed(name, target_value))

    def _update_param(self, name, value):
        """Internal handler for widget value changes."""
        self.node_definition.parameters[name] = value

        async def _run_on_change():
            await self.node_definition.on_parameter_changed(name, value)
            _main_dispatcher.post(self._propagate_all_outputs)

        AsyncRuntime.run_coroutine(_run_on_change())

    def _propagate_all_outputs(self):
        """Pushes all current output port values to connected downstream nodes.
        Must only run on the Qt main thread (always dispatched via QTimer.singleShot).
        """
        if self._is_propagating: return
        if not self.scene(): return

        self._is_propagating = True
        try:
            for edge in self.scene().edges:
                if edge.from_port.parentItem() == self:
                    out_port_name = edge.from_port.port_definition.name
                    current_val = self.node_definition.get_parameter(out_port_name)

                    target_node = edge.to_port.parentItem()
                    target_port_name = edge.to_port.port_definition.name

                    target_node.set_parameter(target_port_name, current_val, propagate=True)
        finally:
            self._is_propagating = False

    def update_dropdown_options(self, name: str, options: list):
        """Update the items of a dropdown (QComboBox) widget for the given parameter name."""
        w = self._param_raw_widgets.get(name)
        if not isinstance(w, QComboBox):
            return
        current = w.currentText()
        w.blockSignals(True)
        w.clear()
        w.addItems([str(o) for o in options])
        idx = w.findText(current)
        w.setCurrentIndex(idx if idx >= 0 else 0)
        w.blockSignals(False)
        self.node_definition.parameters[name] = w.currentText()

    def set_status(self, status: str):
        self.status = status
        self.update()

    def set_bypassed(self, bypassed: bool):
        if self.bypassed == bypassed:
            return
        self.bypassed = bypassed
        if self.scene():
            self.scene().push_history()
        self.update()

    def set_init_priority(self, priority: int):
        if self.init_priority == priority:
            return
        self.init_priority = priority
        if self.scene():
            self.scene().push_history()
        self.update()

    def reload_definition(self, new_definition):
        """Swap this widget's node_definition for a freshly loaded one and
        rebuild the visual ports / parameter widgets in place.

        Existing edges are preserved when their port names still exist on the
        new definition; edges to removed ports are dropped (rebuild_ports
        already handles this). Saved parameter values are re-applied where
        the port still exists with the same name.
        """
        # Snapshot current parameter values so we can re-apply them after the
        # ports/widgets are rebuilt against the new definition.
        old_params = dict(getattr(self.node_definition, 'parameters', {}) or {})

        # Swap the definition reference.
        self.node_definition = new_definition

        # Clear cached parameter widgets — _create_param_widget only creates
        # a widget when the name isn't already in self.param_widgets, so we
        # must drop the old ones for the new definition's widget_types to
        # take effect.
        for name, proxy in list(self.param_widgets.items()):
            try:
                if self.scene() and proxy.scene():
                    self.scene().removeItem(proxy)
                else:
                    proxy.setParentItem(None)
            except Exception:
                pass
        self.param_widgets.clear()
        self._param_raw_widgets.clear()

        # Update the title text with the new definition's name.
        try:
            if hasattr(self, 'title_text') and self.title_text:
                self.title_text.setPlainText(new_definition.name)
        except Exception:
            pass

        # rebuild_ports() handles port reconstruction AND edge preservation
        # for ports that still exist; edges to removed ports are removed.
        self.rebuild_ports()

        # Re-apply saved parameter values for ports that still exist on the
        # new definition (set_parameter handles missing ports gracefully).
        for p_name, p_val in old_params.items():
            try:
                self.set_parameter(p_name, p_val, propagate=False)
            except Exception:
                pass

        if self.scene():
            self.scene().push_history()
        self.update()

    def is_port_connected(self, port_name, is_input):
        """Checks if a port has any active connections in the scene."""
        if not self.scene(): return False
        for edge in self.scene().edges:
            if is_input:
                if edge.to_port and edge.to_port.parentItem() == self and edge.to_port.port_definition.name == port_name:
                    return True
            else:
                if edge.from_port and edge.from_port.parentItem() == self and edge.from_port.port_definition.name == port_name:
                    return True
        return False

    def boundingRect(self):
        margin = 8  # port connectors extend 6px past node edges; +2 for pen and safety
        return QRectF(-margin, 0, self.width + margin * 2, self.height)

    def shape(self):
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width, self.height), 10, 10)
        return path

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            if self.scene():
                for edge in self.scene().edges:
                    if edge.from_port in self.input_widgets or \
                       edge.from_port in self.output_widgets or \
                       edge.to_port in self.input_widgets or \
                       edge.to_port in self.output_widgets:
                        edge.update_path()
        return super().itemChange(change, value)

    def _open_script_editor(self):
        try:
            parent = None
            if self.scene() and self.scene().views():
                parent = self.scene().views()[0]
            current_code = self.node_definition.get_parameter('python_code', '')
            dlg = ScriptEditorDialog(parent=parent, initial_code=current_code)
            if exec_dialog(dlg) == dlg.Accepted:
                code = dlg.get_code()
                if self.scene():
                    self.scene().push_history()
                self.set_parameter('python_code', code, propagate=False)
        except Exception:
            pass

    def paint(self, painter, option, widget):
        if self.bypassed:
            painter.setOpacity(0.4)
        else:
            painter.setOpacity(1.0)

        from src.utils.color_manager import ColorManager
        base_color = QColor(40, 40, 40) if self.is_dark else QColor(220, 220, 220)
        if self.status == "running": base_color = QColor(100, 100, 0)
        elif self.status == "success": base_color = QColor(0, 80, 0)
        elif self.status == "failed": base_color = QColor(100, 0, 0)

        # 1. DRAW BODY
        _r = QRectF(0, 0, self.width, self.height)
        painter.setPen(QPen(Qt.black, 1))
        painter.setBrush(QBrush(base_color))
        painter.drawRoundedRect(_r, 10, 10)

        # 2. DRAW HEADER
        # Use Category Color from ColorManager
        header_color = ColorManager.get_category_color(self.node_definition.category)
        
        painter.setBrush(QBrush(header_color))
        path = QPainterPath()
        path.addRoundedRect(_r, 10, 10)
        painter.save()
        painter.setClipPath(path)
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, int(self.width), 35)
        
        # Draw text contrast (black or white)
        if header_color.lightness() > 150:
            self.title_text.setDefaultTextColor(Qt.black)
        else:
            self.title_text.setDefaultTextColor(Qt.white)
            
        painter.restore()
        
        painter.setPen(QPen(QColor(30, 30, 30), 1))
        painter.drawLine(0, 35, int(self.width), 35)

        # 3. DRAW BYPASS BUTTON (B)
        painter.save()
        if self.bypassed:
            painter.setBrush(QBrush(QColor(255, 165, 0))) # Orange when bypassed
            painter.setPen(QPen(Qt.black, 1))
        else:
            painter.setBrush(QBrush(QColor(60, 60, 60)))
            painter.setPen(QPen(QColor(200, 200, 200), 1))

        painter.drawRoundedRect(self.bypass_rect, 4, 4)
        painter.setPen(QPen(Qt.white if not self.bypassed else Qt.black))
        painter.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        painter.drawText(self.bypass_rect, Qt.AlignCenter, "B")
        painter.restore()

        # 4. DRAW INIT BUTTON (I) — teal when active
        painter.save()
        if self.init_priority > 0:
            painter.setBrush(QBrush(QColor(0, 180, 180)))
            painter.setPen(QPen(Qt.black, 1))
        else:
            painter.setBrush(QBrush(QColor(60, 60, 60)))
            painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRoundedRect(self.init_rect, 4, 4)
        painter.setPen(QPen(Qt.black if self.init_priority > 0 else Qt.white))
        painter.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        painter.drawText(self.init_rect, Qt.AlignCenter, "I")
        painter.restore()

        icon_path = self.node_definition.icon_path or getattr(type(self.node_definition), 'icon_path', None)
        if icon_path:
            pixmap = QPixmap(resource_path(icon_path))
            if not pixmap.isNull():
                painter.drawPixmap(8, 8, 20, 20, pixmap)
                self.title_text.setPos(32, 5)
            else: self.title_text.setPos(10, 5)
        else: self.title_text.setPos(10, 5)

        if self.isSelected():
            painter.setPen(QPen(QColor(255, 165, 0), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(_r, 10, 10)

    def _get_custom_tooltip(self):
        """Lazy-create a shared frameless QLabel acting as a custom tooltip.
        Stored on the QApplication so all NodeWidgets share one instance."""
        app = QtWidgets.QApplication.instance()
        tip = getattr(app, '_node_custom_tooltip', None)
        if tip is None:
            tip = QLabel(
                None,
                Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            )
            tip.setAttribute(Qt.WA_ShowWithoutActivating, True)
            tip.setTextFormat(Qt.RichText)
            tip.setWordWrap(False)
            tip.setMargin(8)
            tip.setStyleSheet(
                "QLabel { background-color: #2b2b2b; color: #ddd;"
                " border: 1px solid #555; }"
            )
            app._node_custom_tooltip = tip
        return tip

    def _show_button_tooltip(self, screen_pos, text):
        tip = self._get_custom_tooltip()
        tip.setText(text)
        tip.adjustSize()
        # Offset slightly so it doesn't sit under the cursor
        tip.move(int(screen_pos.x()) + 16, int(screen_pos.y()) + 18)
        tip.show()
        tip.raise_()

    def _hide_button_tooltip(self):
        app = QtWidgets.QApplication.instance()
        tip = getattr(app, '_node_custom_tooltip', None)
        if tip is not None:
            tip.hide()

    _BYPASS_TOOLTIP_HTML = (
        "<b>Bypass Node</b><br><br>"
        "Skips this node's execution but keeps the exec flow connected,<br>"
        "so all downstream nodes still run normally.<br><br>"
        "Useful for temporarily disabling a node without breaking the graph.<br><br>"
        "<i>Click to toggle &nbsp;|&nbsp; Orange = bypassed</i>"
    )
    _INIT_TOOLTIP_HTML = (
        "<b>Init First Node</b><br><br>"
        "Marks this node to run <i>before</i> the rest of the workflow.<br>"
        "Use this for login, authentication, or data-initialization nodes<br>"
        "that must complete before any dependent node can execute.<br><br>"
        "Init nodes run in descending priority order (highest first),<br>"
        "and their full exec chain completes before the main graph starts.<br><br>"
        "<i>Click to toggle &nbsp;|&nbsp; Teal = active</i>"
    )

    def _update_button_tooltip(self, item_pos, screen_pos):
        if self.bypass_rect.contains(item_pos):
            region = 'bypass'
        elif self.init_rect.contains(item_pos):
            region = 'init'
        else:
            region = None

        # Always re-show when over a button — covers the case where the
        # tooltip was hidden by the OS and the region tracker still says
        # we're "in" that region.
        if region == 'bypass':
            if self._active_tooltip_region != 'bypass':
                self._active_tooltip_region = 'bypass'
            self._show_button_tooltip(screen_pos, self._BYPASS_TOOLTIP_HTML)
        elif region == 'init':
            if self._active_tooltip_region != 'init':
                self._active_tooltip_region = 'init'
            self._show_button_tooltip(screen_pos, self._INIT_TOOLTIP_HTML)
        else:
            if self._active_tooltip_region is not None:
                self._active_tooltip_region = None
                self._hide_button_tooltip()

    def hoverEnterEvent(self, event):
        self._update_button_tooltip(event.pos(), event.screenPos())
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event):
        self._update_button_tooltip(event.pos(), event.screenPos())
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self._active_tooltip_region = None
        self._hide_button_tooltip()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if self.bypass_rect.contains(event.pos()):
            self.set_bypassed(not self.bypassed)
            event.accept()
            return
        if self.init_rect.contains(event.pos()):
            self.set_init_priority(0 if self.init_priority > 0 else 1)
            event.accept()
            return
        super().mousePressEvent(event)
