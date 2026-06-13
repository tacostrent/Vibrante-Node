# Release Notes — Vibrante-Node v2.2.0

**Release date:** 2026-05-15
**Type:** Minor — new features + bug fixes
**Previous release:** v2.1.1

---

## Highlights

- **Full Settings Dialog** — Edit → Preferences (Ctrl+,) opens a persistent, multi-page settings dialog with live apply on OK.
- **Environment Manager** — Centralized `EnvManager` singleton persists Python paths, extra node directories, extra script directories, and custom environment variables across relaunches.
- **Import / Export Settings** — Save your full settings profile to a portable JSON file; restore it on any machine.
- **Reactive Propagation Crash Fix** — Typing in a node text input while wired downstream no longer crashes the application.

---

## New Features

### Settings Dialog — Edit → Preferences (Ctrl+,)
A full, persistent settings dialog accessible via **Edit → Preferences** (keyboard shortcut `Ctrl+,`).

Four pages:

| Page | Contents |
|------|----------|
| **Python Runtime** | `VIBRANTE_PYTHONPATH` — extra `sys.path` entries, one path per line. Browse button. Current `sys.path` preview for applied entries. |
| **Application Paths** | `v_nodes_dir` — extra node directories. `v_scripts_path` — extra script directories. Both support multiple paths (one per line) and a Browse button. |
| **Environment Variables** | Custom `os.environ` key/value pairs, editable table. Add/Remove buttons. Variable names validated (alphanumeric + underscore). |
| **Vibrante Variables** | Read-only display of all built-in Vibrante-Node runtime variables (`VIBRANTE_NODE_APP`, `VIBRANTE_PYTHON_EXE`, etc.) with their current `os.environ` values. Refresh button. |

Clicking **OK** persists all values to `~/.vibrante_node_config.json`, immediately applies them to the running session (reloads node registry, rebuilds Scripts menu), and logs `[Settings] Settings saved and applied.` to the log panel.

### Import / Export Settings
Two buttons at the bottom-left of the Settings dialog:

- **Import Settings…** — Opens a file dialog for a `.json` file. Loads all settings into the dialog's UI widgets. The user reviews before clicking OK. Unknown keys in the file are silently ignored for forward-compatibility.
- **Export Settings…** — Opens a save-file dialog. Writes the **current UI state** (including unsaved edits) to a JSON file with `indent=2`.

**File format:**
```json
{
  "vibrante_pythonpath": ["C:/MyLibs/python"],
  "v_nodes_dir": ["C:/MyStudio/nodes"],
  "v_scripts_path": ["C:/MyStudio/scripts"],
  "custom_variables": {"STUDIO_ROOT": "/studio"}
}
```

### EnvManager (`src/utils/env_manager.py`)
New singleton that manages all user-configurable environment settings:

```python
from src.utils.env_manager import env_manager
env_manager.initialize()   # called once at startup in main.py
```

- **`get/set_vibrante_pythonpath()`** — extra `sys.path` entries
- **`get/set_v_nodes_dir()`** — extra node directories (merged with Houdini-injected values)
- **`get/set_v_scripts_path()`** — extra script directories (merged with Houdini-injected values)
- **`get/set_custom_variables()`** — user-defined `os.environ` entries
- **`export_settings()` / `import_settings(data)`** — serialization helpers
- **`reinitialize()`** — re-apply settings after runtime changes
- **`apply_to_subprocess_env()`** — returns a subprocess-safe copy; never mutates `os.environ`

### Website Example Nodes (`website_examples/`)
Ten production-quality example node JSON files for website demonstrations:

| File | Category | Description |
|------|----------|-------------|
| `regex_replace.json` | String | Regex substitution with match count |
| `http_request.json` | Network | Full HTTP client (GET/POST/etc) |
| `file_batch_processor.json` | Files | Batch-process files matching a glob |
| `email_notification.json` | Network | SMTP email with TLS |
| `database_query.json` | Data | SQLite query with parameterized inputs |
| `image_resizer.json` | Image | PIL-based resize with aspect ratio control |
| `llm_text_generation.json` | AI | Anthropic/OpenAI-compatible text generation |
| `folder_monitor.json` | Files | Watch a folder for new files |
| `hou_sop_chain.json` | Houdini | Box → Extrude SOP chain |
| `prism_multi_asset_publisher.json` | Prism | Batch Prism asset publisher |

---

## Bug Fixes

### Typing Crash — Qt Thread Violation in Reactive Propagation
**Symptom:** App crashed (or produced silent corruption) when typing in a node text input (e.g. Message Node) while it was wired to a downstream node (e.g. Console Print).

**Root cause:** `_propagate_all_outputs()` was called directly from the `AsyncRuntime` background thread. It accessed `scene().edges` and called Qt widget methods (`blockSignals()`, `setText()`, `setValue()`) — all Qt thread-affinity violations when called from a non-main thread.

**Fix:** Added `_MainThreadDispatcher(QObject)` at module level in `src/ui/node_widget.py`. A `pyqtSignal(object)` with `Qt.QueuedConnection` is used to schedule `_propagate_all_outputs` on the Qt main thread from any thread. The `_is_propagating` re-entry guard is now inside `_propagate_all_outputs` itself (with `try/finally`).

**File:** `src/ui/node_widget.py`

### Settings Changes Not Applied in Same Session
**Symptom:** After clicking OK in the Settings dialog, changes to `v_nodes_dir`, `v_scripts_path`, and custom variables only took effect after restarting the application. The Library panel and Scripts menu were not updated.

**Root cause:** `_open_settings()` discarded the return value of `dialog.exec_()`, so it never detected that the user clicked OK.

**Fix:** `_open_settings()` now checks `dialog.exec_() == QDialog.Accepted`. On accept: reloads the node registry (`NodeRegistry.load_all_with_extras`), reloads the user node directory, refreshes the Library panel, and rebuilds the Scripts menu.

**File:** `src/ui/window.py`

---

## Improvements

### Startup Environment Initialization
`main.py` now calls `env_manager.initialize()` at startup (before `MainWindow` is created). This ensures:
- Custom variables are in `os.environ` before any node `execute()` runs
- `VIBRANTE_PYTHONPATH` entries are in `sys.path` before the library panel is built
- `v_nodes_dir` and `v_scripts_path` are merged into `os.environ` before `NodeRegistry.load_all_with_extras` is called

---

## Testing

New test files added; all 142 tests pass:

| File | Coverage |
|------|----------|
| `tests/unit/test_env_manager.py` | EnvManager initialize, path merging, custom variables, subprocess env |
| `tests/unit/test_reactive_propagation.py` | Thread check on `_propagate_all_outputs`, propagation value delivery, rapid typing |
| `tests/unit/test_settings_persistence.py` | Save/persist, apply-on-accept, load-back in dialog, relaunch, import/export round-trip |
| `tests/unit/test_website_examples.py` | All 10 example nodes: existence, load, registration, category, ports, instantiation |

---

## Migration Notes

No breaking changes. Existing workflows, nodes, and configurations are fully compatible.

**If upgrading from v2.1.x:**
- The new Settings dialog automatically reads any values previously set in `~/.vibrante_node_config.json` (the config file is backward-compatible).
- `env_manager.initialize()` is now called at startup. If you have custom startup scripts that set environment variables early, ensure they run before `main.py` is imported or that they use the `env_manager.set_custom_variables()` API.
- No changes to node JSON format.
- No changes to workflow JSON format.

---

## Files Modified

| File | Change |
|------|--------|
| `src/main.py` | Version bump to v2.2.0; `env_manager.initialize()` at startup |
| `src/ui/window.py` | `_open_settings()` applies changes on accept; `QDialog` import; v2.2.0 in About dialog |
| `src/ui/node_widget.py` | `_MainThreadDispatcher` for safe cross-thread propagation |
| `src/ui/settings_window.py` | **New** — full Settings dialog |
| `src/utils/env_manager.py` | **New** — EnvManager singleton |
| `file_version_info.txt` | Version `2.2.0.0` |
| `vibrante_node.spec` | Version comment updated |
| `website_examples/` | **New** — 10 example node JSON files |
| `tests/unit/test_env_manager.py` | **New** |
| `tests/unit/test_reactive_propagation.py` | **New** |
| `tests/unit/test_settings_persistence.py` | **New** (with import/export tests added) |
| `tests/unit/test_website_examples.py` | **New** |
