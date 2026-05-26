# Vibrante-Node — Technical Reference

**Version:** v2.4.0 | [User Guide](USER_GUIDE.md) | [Node Builder API](NODE_BUILDER_API.md) | [Automation API](AUTOMATION_API.md) | [Developer Guide](DEVELOPER.md)

This is the complete technical reference for Vibrante-Node. Use it as a quick-lookup companion to the other guides. For narrative explanations and examples, refer to the guide documents linked above.

---

## Contents

1. [Node Library — Full Index](#1-node-library)
2. [BaseNode API Reference](#2-basenode-api-reference)
3. [Port Schema Reference](#3-port-schema-reference)
4. [Serialization Schema Reference](#4-serialization-schema-reference)
5. [Environment Variables Reference](#5-environment-variables-reference)
6. [Scripting Console API Reference](#6-scripting-console-api-reference)
7. [HouBridge API Reference](#7-houbridge-api-reference)
8. [Engine Signals Reference](#8-engine-signals-reference)
9. [Keyboard Shortcuts — Complete Table](#9-keyboard-shortcuts)
10. [Log Levels and Node States Reference](#10-log-and-state-reference)
11. [Error Codes and Troubleshooting Index](#11-error-index)

---

## 1. Node Library — Full Index

### General / IO

| Node ID | Category | Description |
|---------|----------|-------------|
| `console_print` | General | Print any value to the Log Panel |
| `message_node` | General | Hold and pass a string value |
| `delay_timer` | General | Async delay (await asyncio.sleep) |
| `file_reader` | IO | Read a file to a string |
| `append_file` | IO | Append text to a file |
| `create_folder` | IO | Create a directory (exist_ok) |
| `http_request` | IO | HTTP GET/POST via aiohttp |
| `json_parser` | IO | Parse JSON string to dict/list |
| `list_images_recursive` | IO | Recursively list images in a folder |

### Control Flow

| Node ID | Category | Description |
|---------|----------|-------------|
| `if_condition` | Logic | Route exec to true or false branch |
| `branch` | Logic | Named multi-branch exec routing |
| `for_loop` | Control Flow | Generate index list; exec_out fires once |
| `loop_body` | Control Flow | Iterate over list; exec_out fires per item |
| `loop_break` | Control Flow | Stop loop iteration on condition |
| `while_loop` | Control Flow | Repeat while condition is True |
| `python_script` | Scripting | Inline Python code node |

### Math

| Node ID | Category | Description |
|---------|----------|-------------|
| `add` | Math | Add two numbers |
| `math_add` | Math | Add with float inputs |
| `add_integers` | Math | Add two integers |
| `math_abs` | Math | Absolute value |
| `compare` | Math | Compare two values; returns bool |

### Logic

| Node ID | Category | Description |
|---------|----------|-------------|
| `logic_and` | Logic | AND two booleans |
| `logic_compare` | Logic | Comparison operator (==, !=, <, >, <=, >=) |

### String

| Node ID | Category | Description |
|---------|----------|-------------|
| `concat` | String | Concatenate two strings |
| `split` | String | Split string by delimiter |
| `replace` | String | String replacement |
| `lowercase` | String | Convert to lowercase |
| `uppercase` | String | Convert to uppercase |
| `string_length` | String | Character count |

### Data Structures

| Node ID | Category | Description |
|---------|----------|-------------|
| `create_list` | Data | Create a Python list from items |
| `get_list_item` | Data | Get item at index |
| `list_length` | Data | List item count |
| `list_append` | Data | Append item to list |
| `create_dictionary` | Data | Create a dict from key/value inputs |
| `get_dict_value` | Data | Get dict value by key |
| `set_dict_value` | Data | Set dict value by key |

### Houdini

| Node ID | Category | Description |
|---------|----------|-------------|
| `hou_create_geo` | Houdini | Create Object-level geo container |
| `hou_set_parm` | Houdini | Set a single Houdini parameter |
| `hou_get_parm` | Houdini | Get a Houdini parameter value |
| `hou_cook` | Houdini | Cook a node |
| `hou_connect` | Houdini | Wire two Houdini nodes |
| `hou_run_code` | Houdini | Execute Python inside Houdini |
| `hou_scene_info` | Houdini | Get HIP file, FPS, frame range |
| `hou_save_hip` | Houdini | Save the Houdini scene |
| `hou_sop_chain` | Houdini | Build and cook a SOP chain |

### Maya (25 nodes — headless action pattern)

| Node ID | Description |
|---------|-------------|
| `maya_action_open_scene` | Open a Maya scene file |
| `maya_action_save_scene` | Save the current scene |
| `maya_action_render` | Render with specified camera and frame range |
| `maya_action_import_alembic` | Import Alembic cache |
| `maya_action_export_alembic` | Export selection as Alembic |
| `maya_action_import_fbx` | Import FBX file |
| `maya_action_export_fbx` | Export selection as FBX |
| `maya_action_set_frame_range` | Set timeline start/end |
| `maya_action_run_python` | Execute Python inside Maya |
| `maya_action_run_mel` | Execute MEL script |
| `maya_action_scene_info` | Get scene path, FPS, frame range |
| `maya_action_create_node` | Create a Maya DG/DAG node |
| `maya_action_custom` | Custom MEL/Python action |
| `maya_headless` | Execute action list in batch Maya |
| `blender_get_action_result` | Read result from headless run |

### Blender (21 nodes — headless action pattern)

| Node ID | Description |
|---------|-------------|
| `blender_action_open_blend` | Open a .blend file |
| `blender_action_save_blend` | Save the current .blend |
| `blender_action_render` | Render to output path |
| `blender_action_export_alembic` | Export Alembic |
| `blender_action_import_alembic` | Import Alembic |
| `blender_action_export_fbx` | Export FBX |
| `blender_action_import_fbx` | Import FBX |
| `blender_action_export_gltf` | Export glTF |
| `blender_action_import_gltf` | Import glTF |
| `blender_action_export_obj` | Export OBJ |
| `blender_action_import_obj` | Import OBJ |
| `blender_action_export_usd` | Export USD |
| `blender_action_new_blend` | Create a new .blend |
| `blender_action_set_frame_range` | Set render frame range |
| `blender_action_set_render_settings` | Configure render output |
| `blender_action_bake_animation` | Bake animation |
| `blender_action_scene_info` | Get scene metadata |
| `blender_action_custom` | Custom Python action |
| `blender_headless` | Execute action list in background Blender |

### Prism Pipeline (62 nodes)

| Group | Node IDs |
|-------|----------|
| Core | `prism_core_init`, `prism_core_info` |
| Entities | `prism_get_assets`, `prism_get_shots`, `prism_build_entity`, `prism_create_entity`, `prism_get_asset_types_by_project`, `prism_get_assets_by_type`, `prism_get_asset_type_by_name` |
| Products | `prism_get_products`, `prism_get_product_versions`, `prism_create_product_version`, `prism_get_latest_product_path`, `prism_import_product` |
| Media | `prism_get_media`, `prism_get_media_versions`, `prism_create_playblast` |
| Scenes | `prism_get_current_scene`, `prism_get_scene_files`, `prism_get_preset_scenes`, `prism_open_scene`, `prism_save_scene_version`, `prism_create_scene_from_preset`, `prism_get_scene_path`, `prism_get_export_path` |
| Config | `prism_get_config`, `prism_set_config`, `prism_get_project_config_path` |
| Projects | `prism_list_projects`, `prism_create_project`, `prism_change_project` |
| Departments | `prism_get_departments`, `prism_get_tasks`, `prism_create_category`, `prism_get_shot_by_sequence` |
| Plugins | `prism_list_plugins`, `prism_get_plugin`, `prism_add_integration` |
| USD | `prism_usd_entity_path`, `prism_usd_department_layer_path`, `prism_usd_sublayer_path`, `prism_usd_update_department_layer`, `prism_usd_update_sublayer` |
| Advanced | `prism_eval`, `prism_monkey_patch`, `prism_register_callback`, `prism_trigger_callback`, `prism_popup`, `prism_send_cmd`, `prism_login_token`, `prism_studio_assign_project` |

---

## 2. BaseNode API Reference

**Module:** `src.nodes.base`

### Class Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"BaseNode"` | Registry key. Must match `node_id`. |
| `node_id` | `str` | injected by registry | Same as `name` for JSON nodes. |
| `display_name` | `str` | `""` | Canvas header label. Falls back to `name`. |
| `description` | `str` | `""` | Library tooltip. |
| `category` | `str` | `"General"` | Library grouping. |
| `icon_path` | `str \| None` | `None` | Relative path to icon. |
| `init_priority` | `int` | `0` | `> 0` = created before other nodes on load. |
| `memory` | `dict` | `{}` | Class-level shared state, cleared each run. |

### Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `inputs` | `dict[str, Port]` | Input ports keyed by name. |
| `outputs` | `dict[str, Port]` | Output ports keyed by name. |
| `parameters` | `dict[str, Any]` | Widget values, output cache, internal state. |
| `bypassed` | `bool` | True when node is user-bypassed. |

### Methods — Complete Table

| Method | Returns | Description |
|--------|---------|-------------|
| `__init__(use_exec=True)` | — | Adds exec_in/exec_out when use_exec=True |
| `add_input(name, type="any", widget_type=None, options=None, default=None)` | None | Add input port and initialize parameter |
| `add_output(name, type="any", default=None)` | None | Add output port and initialize parameter |
| `add_exec_input(name="exec_in")` | None | Add exec-type input (called by __init__) |
| `add_exec_output(name="exec_out")` | None | Add exec-type output (called by __init__) |
| `add_parameter(name, param_type, default=None)` | None | Add internal non-port parameter |
| `set_parameter(name, value)` | None | Set widget value; dropdown list update supported |
| `get_parameter(name, default=None)` | `Any` | Safe read; returns default if key absent |
| `rebuild_ports()` | None | Signal canvas to refresh port layout |
| `is_port_connected(name, is_input)` | `bool` | True if port has a wire |
| `is_stopped()` | `bool` | True if user pressed Stop |
| `async set_output(name, value)` | None | Reactive push before exec_out fires |
| `clear_outputs()` | None | Reset outputs to defaults |
| `log_info(msg)` | None | Info log; white in Log Panel |
| `log_success(msg)` | None | Success log; green |
| `log_error(msg)` | None | Error log; red; sets node error state |
| `restore_from_parameters(params)` | None | Override to rebuild dynamic ports on load |
| `async on_parameter_changed(name, value)` | None | Override for reactive parameter response |
| `on_plug_sync(port, is_input, node, port)` | None | Override for sync connection event |
| `on_unplug_sync(port, is_input)` | None | Override for sync disconnect event |
| `async on_plug(port, is_input, node, port)` | None | Override for async connection event |
| `async on_unplug(port, is_input)` | None | Override for async disconnect event |
| `async execute(inputs)` | `dict` | **Abstract** — implement in every node |

---

## 3. Port Schema Reference

### Port Type — Complete Table

| type | Meaning | Python runtime type |
|------|---------|---------------------|
| `"string"` | Text | `str` |
| `"int"` | Integer | `int` |
| `"float"` | Float | `float` |
| `"bool"` | Boolean | `bool` |
| `"list"` | Python list | `list` |
| `"dict"` | Python dict | `dict` |
| `"any"` | Generic / exec flow | any |

### Widget Type — Complete Table

| widget_type | Renders as | Applicable port types |
|-------------|-----------|----------------------|
| `"text"` | Single-line text input | `string`, `any` |
| `"text_area"` | Multi-line text area | `string`, `any` |
| `"int"` | Integer spinbox | `int` |
| `"float"` | Float spinbox | `float` |
| `"bool"` | Checkbox | `bool` |
| `"checkbox"` | Checkbox (alias) | `bool` |
| `"dropdown"` | Drop-down list | `string` |
| `"slider"` | Horizontal slider | `float`, `int` |
| `"file"` | Text + open-file dialog | `string` |
| `"file_save"` | Text + save-file dialog | `string` |
| `null` | No widget | any |

### Port Object (src.nodes.base.Port)

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Port identifier |
| `data_type` | `str` | One of the port types above |
| `widget_type` | `str \| None` | One of the widget types above |
| `options` | `list[str] \| None` | Dropdown options |
| `default` | `Any` | Default value |

---

## 4. Serialization Schema Reference

### WorkflowModel

```json
{
  "nodes": [NodeInstanceModel, ...],
  "connections": [ConnectionModel, ...],
  "sticky_notes": [StickyNoteModel, ...],
  "backdrops": [BackdropModel, ...]
}
```

All arrays default to `[]` if absent.

### NodeInstanceModel

```json
{
  "node_id": "string — registry key",
  "instance_id": "string — UUID",
  "display_name": "string — canvas label",
  "position": {"x": 0.0, "y": 0.0},
  "parameters": {"port_name": value, ...}
}
```

### ConnectionModel

```json
{
  "from_node": "source instance_id",
  "from_port": "output port name",
  "to_node":   "destination instance_id",
  "to_port":   "input port name"
}
```

### StickyNoteModel

```json
{
  "text": "annotation text",
  "position": {"x": 0.0, "y": 0.0},
  "width": 200.0,
  "height": 100.0,
  "color": "#f5a623"
}
```

### BackdropModel

```json
{
  "title": "label text",
  "position": {"x": 0.0, "y": 0.0},
  "width": 400.0,
  "height": 300.0,
  "color": "#2e2e2e"
}
```

### Node Definition JSON Schema

```json
{
  "node_id":      "string (required)",
  "name":         "string (required)",
  "display_name": "string (optional)",
  "description":  "string (optional)",
  "category":     "string (required)",
  "icon_path":    "string | null",
  "use_exec":     "bool (required)",
  "init_priority":"int (default 0)",
  "inputs": [
    {
      "name":        "string (required)",
      "type":        "string (required)",
      "widget_type": "string | null",
      "options":     "list[string] | null",
      "default":     "any | null"
    }
  ],
  "outputs": [ ... ],
  "python_code":  "string (required)"
}
```

---

## 5. Environment Variables Reference

### Built-in Variables

| Variable | Set by | Consumed by | Description |
|----------|--------|-------------|-------------|
| `VIBRANTE_NODE_APP` | `vibrante_node.json` | `vibrante_node_houdini.py` | Absolute path to the app root |
| `VIBRANTE_PYTHON_EXE` | `vibrante_node.json` | `vibrante_node_houdini.py` | System Python path for subprocess |
| `VIBRANTE_HOUDINI_MODE` | `setup_env()` | `qt_compat.py` | `"subprocess"` forces PyQt5 selection |
| `VIBRANTE_HOU_PORT` | `setup_env()` | `hou_bridge.py` | TCP port for Houdini bridge (default 18811) |
| `VIBRANTE_HIP_FILE` | `setup_env()` | node code via `os.environ` | Path to the current Houdini HIP file |
| `v_nodes_dir` | `setup_env()` / EnvManager | `NodeRegistry.load_all_with_extras()` | Extra node definition directories (colon-separated) |
| `v_scripts_path` | `setup_env()` / EnvManager | `MainWindow._populate_scripts_menu()` | Extra script directories (colon-separated) |

### User-Configurable Variables (EnvManager)

| Config key | `os.environ` key | Description |
|------------|-----------------|-------------|
| `env.vibrante_pythonpath` | (injected to `sys.path`) | Extra Python import paths |
| `env.v_nodes_dir` | `v_nodes_dir` | Merged with any existing value |
| `env.v_scripts_path` | `v_scripts_path` | Merged with any existing value |
| `env.custom_variables` | each key directly | Studio-specific variables (STUDIO_ROOT, PROJECT, etc.) |

### Accessing Variables in Nodes

```python
import os, sys

# Custom env var set in Preferences
studio_root = os.environ.get("STUDIO_ROOT", "")

# VIBRANTE_PYTHONPATH packages (already in sys.path after initialize())
import my_studio_lib

# HIP file path when launched from Houdini
hip_path = os.environ.get("VIBRANTE_HIP_FILE", "")
```

---

## 6. Scripting Console API Reference

### Global Objects

| Object | Type | Description |
|--------|------|-------------|
| `app` | `MainWindow` | Application window |
| `scene` | `NodeScene` | Active canvas |
| `registry` | `NodeRegistry` | Node type database |
| `git` | `GitWrapper` | Source control |

### NodeScene Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `add_node_by_name(node_id, pos=(x,y))` | `NodeWidget` | Add node to canvas |
| `find_node_by_name(name)` | `NodeWidget \| None` | Find first node by display name |
| `connect_nodes(a, port_a, b, port_b)` | None | Wire two nodes |
| `clear()` | None | Remove all canvas items |
| `.nodes` | `list[NodeWidget]` | All nodes on canvas |

### MainWindow Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `add_new_workflow(name)` | None | Open new tab |
| `save_workflow()` | None | Save current tab |
| `execute_pipeline()` | None | Run current workflow |
| `get_current_workflow_path()` | `str \| None` | Path to current file |

### NodeWidget Methods

| Method / Property | Type | Description |
|-------------------|------|-------------|
| `set_parameter(name, value)` | None | Set widget value |
| `get_parameter(name, default=None)` | `Any` | Read parameter |
| `.node_definition` | `BaseNode` | Underlying logic instance |
| `.instance_id` | `UUID \| str` | Unique canvas instance ID |
| `setPos(x, y)` | None | Move node on canvas |
| `scenePos()` | `QPointF` | Current canvas position |

### NodeRegistry Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_definition(node_id)` | `NodeDefinitionJSON \| None` | Get port/metadata schema |
| `get_source_path(node_id)` | `str \| None` | On-disk JSON path |
| `reload_node_definition(node_id)` | `bool` | Recompile class from disk |

### GitWrapper Methods

| Method | Description |
|--------|-------------|
| `status()` | Print working tree status |
| `commit(msg)` | Stage all and commit |
| `push()` | Push to remote |
| `pull()` | Pull from remote |
| `log(n=10)` | Print last N commits |

---

## 7. HouBridge API Reference

**Module:** `src.utils.hou_bridge`  
**Access:** `from src.utils.hou_bridge import get_bridge; bridge = get_bridge()`

| Method | Parameters | Returns | Notes |
|--------|-----------|---------|-------|
| `ping()` | — | `{"status": "ok", "version": str}` | |
| `create_node(parent, type, name="")` | str, str, str | `{"path", "name", "type"}` | |
| `delete_node(path)` | str | `{"deleted": path}` | |
| `set_parm(node, parm, value)` | str, str, any | `{"set": True}` | |
| `get_parm(node, parm)` | str, str | `{"value": any}` | |
| `set_parms(node, parms)` | str, dict | `{"set": True, "count": int}` | |
| `get_parms(node)` | str | `dict[str, any]` | All parameters |
| `connect_nodes(from, to, output=0, input_idx=0)` | str, str, int, int | `{"connected": True}` | |
| `cook_node(path, force=False)` | str, bool | `{"cooked": True}` | |
| `run_code(code)` | str | `{"result": any}` | `result` var in code → return value |
| `node_info(path)` | str | info dict | path, name, type, category, children |
| `node_exists(path)` | str | `{"exists": bool}` | |
| `children(path="/obj")` | str | `list[{"name", "type", "path"}]` | |
| `set_display_flag(path, on=True)` | str, bool | `{"set": True}` | |
| `set_render_flag(path, on=True)` | str, bool | `{"set": True}` | |
| `layout_children(path)` | str | `{"done": True}` | |
| `save_hip(path="")` | str | `{"saved": str}` | |
| `set_expression(node, parm, expr, language="hscript")` | str, str, str, str | `{"set": True}` | language: "hscript" or "python" |
| `set_keyframe(node, parm, frame, value)` | str, str, int, any | `{"set": True}` | |
| `set_frame(frame)` | int | `{"frame": int}` | |
| `set_playback_range(start, end)` | int, int | `{"start", "end"}` | |
| `scene_info()` | — | `{"hip_file", "houdini_version", "fps", "frame", "frame_range"}` | |

**Behavior notes:**
- Each call acquires a `threading.Lock` — thread-safe.
- `TCP_NODELAY` set on connect — no Nagle buffering.
- 30-second `socket.timeout` — raises `ConnectionError` if Houdini hangs.
- Auto-reconnect on `BrokenPipeError` / `ConnectionResetError`.

---

## 8. Engine Signals Reference

**Class:** `NetworkExecutor` (inherits `QObject`)

| Signal | Signature | Emitted when |
|--------|-----------|-------------|
| `execution_started` | `()` | `run()` begins |
| `execution_finished` | `()` | All entry tasks complete |
| `node_started` | `(instance_id: str)` | Before `execute()` is called |
| `node_finished` | `(instance_id: str, results: dict)` | After `execute()` returns successfully |
| `node_error` | `(instance_id: str, error: str)` | Unhandled exception in `execute()` |
| `node_output` | `(instance_id: str, results: dict)` | Same as `node_finished`; consumed by UI |

**Connected in MainWindow:**

| Signal | MainWindow handler | Effect |
|--------|--------------------|--------|
| `node_started` | `_on_node_started` | Records start time for timing |
| `node_finished` | `_on_node_finished` | Logs timing; calls `scene.update_edge_value()` |
| `node_error` | `_on_node_error` | Logs error; sets node to error visual state |
| `execution_finished` | `_on_execution_finished` | Re-enables toolbar buttons |

---

## 9. Keyboard Shortcuts — Complete Table

| Shortcut | Context | Action |
|----------|---------|--------|
| `F5` | Global | Execute current workflow |
| `Shift+F5` | Global | Stop execution |
| `Tab` | Canvas | Open "Add Node" popup at cursor |
| `Delete` | Canvas | Delete selected nodes or wires |
| `F` | Canvas | Focus view on selection or canvas center |
| `Ctrl+A` | Canvas | Select all nodes |
| `Ctrl+C` | Canvas | Copy selected nodes |
| `Ctrl+V` | Canvas | Paste at cursor |
| `Ctrl+Z` | Canvas | Undo |
| `Ctrl+Y` | Canvas | Redo |
| `Ctrl+G` | Canvas | Wrap selection in Backdrop |
| `Ctrl+Shift+G` | Canvas | Collapse selection into Group Node |
| `Ctrl+E` | Canvas | Edit selected node in Node Builder |
| `Ctrl+R` | Canvas | Reload selected node from disk |
| `Ctrl+Shift+R` | Canvas | Reload all node types from disk |
| `Ctrl+F` | Canvas | Open canvas search bar |
| `Ctrl+M` | Canvas | Toggle mini-map |
| `Ctrl+S` | Global | Save workflow |
| `Ctrl+Shift+S` | Global | Save workflow as |
| `Ctrl+O` | Global | Open workflow |
| `Ctrl+N` | Global | New workflow tab |
| `Ctrl+W` | Global | Close current tab |
| `Ctrl+,` | Global | Open Preferences (Settings) |
| `Ctrl+Wheel` | Code editor | Zoom in/out |
| Middle-mouse drag | Canvas | Pan |
| Mouse wheel | Canvas | Zoom |

> All canvas shortcuts are suppressed when a text input widget has keyboard focus.

---

## 10. Log and State Reference

### Log Levels

| Level | Method | Color | Behavior |
|-------|--------|-------|----------|
| Info | `self.log_info(msg)` | White | Appears in Log Panel |
| Success | `self.log_success(msg)` | Green | Appears in Log Panel |
| Error | `self.log_error(msg)` | Red | Appears in Log Panel; sets node border red |
| Warning | (engine / connection system) | Yellow | Type-mismatch warnings; connection events |

### Node Execution States

| State | How set | Visual |
|-------|---------|--------|
| Idle | Default | Normal border |
| Running | `node_started` signal | Highlighted border (theme-dependent) |
| Success | `node_finished` signal | Brief green flash |
| Error | `node_error` signal | Persistent red border |
| Bypassed | User right-click → Bypass | Faded appearance |

### Execution Timing

`MainWindow._on_node_started` records `time.perf_counter()` per `instance_id`. `_on_node_finished` pops the start time and logs: `Node 'X' finished in {elapsed:.2f}s`. The `dict.pop(key, None)` guard handles any race where finish fires without a matching start.

---

## 11. Error Index

| Error message / symptom | Cause | Resolution |
|-------------------------|-------|-----------|
| Node red border | Unhandled exception in `execute()` | Check Log Panel for traceback |
| `"PrismCore not initialized"` | Missing `prism_core_init` node | Add `prism_core_init`; set valid `prism_root` |
| `"No display SOP found inside: /obj/..."` | Houdini geo has no display node | Ensure geo SOP chain has `set_display_flag(True)` |
| `ConnectionError: Houdini did not respond in 30s` | Houdini is cooking / blocked | Wait for Houdini to finish; check Houdini console |
| `"Wrong File Type"` on node load | Workflow JSON selected as node | Use Nodes → Load Node From JSON for node files |
| `"Wrong File Type"` on workflow load | Node JSON selected as workflow | Use Nodes → Load Node From JSON for node files |
| `"[Errno 2] No such file or directory: '...nodes/...' "` | Nodes directory absent | Fixed in v2.2.x; `os.makedirs(exist_ok=True)` now called automatically |
| `AttributeError: 'QTextEdit' has no 'setOpenExternalLinks'` | Pre-v2.2.1 exe | Update to v2.2.1+ |
| Stale ports after editing a node | JSON definition changed on disk | Select node → `Ctrl+R` |
| "Unknown publisher" on exe launch | Unsigned binary | Dev builds are unsigned; see `tools/sign_release.ps1` |
| App shows session restore dialog | Crash or forced kill previously | Choose Restore or Discard |
| Loop appears to hang | `while_loop` condition never False | Check condition logic; Stop button (`Shift+F5`) still works |
| Widget grayed out | Port is connected | Normal — widget is a live value monitor |
| Type mismatch warning | Connected ports of different types | Informational only; connection still works |
| `crash.log` in project root | Unhandled top-level exception | Read the traceback; report as issue if unexpected |

---

**Documentation map:**

| Document | Audience | Focus |
|----------|----------|-------|
| [User Guide](USER_GUIDE.md) | All users | Interface, execution, shortcuts, integrations |
| [Node Builder API](NODE_BUILDER_API.md) | Node authors | BaseNode, ports, lifecycle, distribution |
| [Automation API](AUTOMATION_API.md) | Pipeline TDs | Scripting console, graph API, automation examples |
| [Developer Guide](DEVELOPER.md) | Contributors | Engine internals, architecture, thread model |
| [Portal Docs](docs/portal/) | All audiences | Full navigable HTML documentation |
| [CHANGELOG](CHANGELOG.md) | All | Version history |

**Deep reference (docs_src/):**

| File | Contents |
|------|----------|
| `docs_src/06_backend_architecture.md` | Execution engine in full detail |
| `docs_src/07_frontend_architecture.md` | Qt canvas architecture |
| `docs_src/08_api_reference.md` | Full class / method reference (1,500 lines) |
| `docs_src/05_node_development.md` | Node development guide (1,000 lines) |
| `docs_src/09_advanced_topics.md` | GroupNode, autosave, wire inspector internals |
