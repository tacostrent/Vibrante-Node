# Changelog — Vibrante-Node

All notable changes to Vibrante-Node are documented in this file.

Format: **[vX.Y.Z]** — YYYY-MM-DD

Full release notes for each version: see `RELEASE_vX.Y.Z.md` / `releases/` directory.

---

## [v2.4.0] — 2026-05-26

**Type:** Minor — 26 new workflow nodes, runtime extensions layer (Tiers 1–6), bug fixes

### Added
- Complete `src/runtime/` module: AI orchestration runtime spanning Tiers 1–6 (40+ modules). MCP client sessions, transaction system, AI planning pipeline, distributed execution, Tier 5 advisory analytics, Tier 6 MCP server.
- `scripts/run_vibrante_mcp.py` — MCP stdio server entry point. Claude Desktop / Codex CLI / Cursor integration.
- 12 MCP semantic tools: `initialize_runtime_context`, `query_runtime_state`, `query_scene_context`, `query_capabilities`, `query_workflow_templates`, `query_examples`, `query_node_parameters`, `plan_scene`, `preview_execution`, `validate_execution_plan`, `execute_workflow_transaction`, `review_execution`.
- 3 generic MCP nodes in `nodes/`: `mcp_server_init`, `mcp_list_tools`, `mcp_call_tool`.
- 23 Houdini AI nodes in `plugins/houdini/v_nodes_houdini/`: `hou_mcp_scene_context`, `hou_mcp_build_node_chain`, `hou_mcp_transaction`, `hou_mcp_graph_diff`, and 19 more (see RELEASE_v2.4.0.md).
- New bridge methods: `bridge.get_selection()`, `bridge.network_summary(path)`.
- `list_images_recursive` utility node.
- Subprocess crash log (`~/.vibrante_node_subprocess.log`) in Houdini plugin launcher.
- MCP shutdown hook in `MainWindow.closeEvent` — prevents stdio subprocess leaks on app exit.
- Linux packaging: `pyproject.toml`, `setup.py`, `MANIFEST.in`, `linux/` directory (pip, AppImage, .deb).
- `ABOUT.md` — Wikipedia-style project overview.
- `vibrante_node` Python package (`vibrante_node/__init__.py`, `vibrante_node/app.py`).
- 70+ new unit test files covering the entire runtime layer.

### Fixed
- `build_node_chain`: topological sort ensures parent nodes are created before their children; `actual_by_expected` map handles Houdini name-collision renaming.
- `review_execution` (`execution_review.py`): `match_score` was always `0.0` when `operations_executed` was absent from the result dict; now falls back to `1.0` when `status == "committed"`.
- `preview_execution` MCP tool: `ImportError` — wrong import name (`get_predictive_execution` → `get_predictive_engine`).

### Changed
- Node ID renames for consistency: `add`→`math_add`, `subtract`→`math_subtract`, `divide`→`math_divide`, `modulo`→`math_modulo`, `lowercase`→`string_lowercase`, `uppercase`→`string_uppercase`, `replace`→`string_replace`, `split`→`string_split`, `append_file`→`file_append`, `write_file`→`file_write`, `random_float`→`example_random_float`.
- `test_all_workflows.py`: auto-discovers plugin node directories so new DCCs need zero test changes.
- `test_settings_persistence.py`: config writes now isolated to per-test temp path.

### Removed
- `concat` node (no direct replacement; use string manipulation nodes).
- `multiply` node (no direct replacement; use math nodes).

### Dependencies
- `mcp>=1.0.0` added to `requirements.txt`.

---

## [v2.3.0] — 2026-05-18

**Type:** Minor — new nodes, developer tooling, and bug fixes

### Added
- `http_request` node bundled in `nodes/` (Network category) — async GET/POST via `urllib.request` + `run_in_executor`; non-blocking; icon `icons/http.png`.
- `tools/create_dev_cert.ps1` — create and trust a self-signed Authenticode cert locally for testing.
- `tools/sign_release.ps1` — sign the built exe with the best available cert in the user's cert store.

### Fixed
- Canvas drag trail artifact — `NodeWidget.boundingRect()` expanded ±8 px to cover port connectors; `shape()` overridden for hit-test accuracy; `paint()` uses local `_r` for body drawing. (`src/ui/node_widget.py`)
- http_request UI freeze — HTTP stack moved to thread pool via `loop.run_in_executor`; Qt main thread stays responsive. (`nodes/http_request.json`, `website_examples/http_request.json`)
- Node Builder: exec port type corruption on edit round-trip — exec ports filtered from table rows in `_load_existing_node`, `_sync_code_to_ui`, `save_node`. (`src/ui/node_builder.py`)
- Node Builder: default value silently zeroed on edit — port tables expanded to 5 columns; `Default` column read/written through round-trips. (`src/ui/node_builder.py`)
- Node Builder: icon-path field triggered full code regeneration — dedicated `_sync_icon_to_code()` replaces only the `self.icon_path = …` line. (`src/ui/node_builder.py`)
- Load Node From JSON: wrong initial directory and no content pre-check — starts in `nodes_dir`; detects and rejects workflow files with a specific error. (`src/ui/window.py`)
- Load Workflow: silently accepted node JSON files — `_looks_like_node_json()` helper rejects node definitions before `model_validate_json`. (`src/ui/window.py`)

---

## [v2.2.1] — 2026-05-15

**Type:** Patch — exe build bug fixes

### Fixed
- About dialog crash (`AttributeError: 'QTextEdit' object has no attribute 'setOpenExternalLinks'`) — changed license display widget from `QTextEdit` to `QTextBrowser` in `src/ui/window.py`.
- LICENSE file not displayed in exe About dialog — added `('LICENSE', '.')` to PyInstaller `datas` in `vibrante_node.spec` so the file is bundled in `_internal/`.

---

## [v2.2.0] — 2026-05-15

**Type:** Minor — new features + bug fixes

### Added
- Settings dialog (`src/ui/settings_window.py`) — Edit → Preferences (Ctrl+,). Four pages: Python Runtime, Application Paths, Environment Variables, Vibrante Variables (read-only). Persists to `~/.vibrante_node_config.json`. Applies changes immediately on OK (node registry reload, library panel refresh, scripts menu rebuild).
- EnvManager singleton (`src/utils/env_manager.py`) — centralized manager for `VIBRANTE_PYTHONPATH`, `v_nodes_dir`, `v_scripts_path`, and custom `os.environ` variables. `initialize()` called at startup in `main.py`.
- Import/Export settings to JSON file — **Import Settings…** / **Export Settings…** buttons in the Settings dialog. Round-trip portable format.
- `website_examples/` — 10 production-quality example node JSON files for website demos (regex_replace, http_request, file_batch_processor, email_notification, database_query, image_resizer, llm_text_generation, folder_monitor, hou_sop_chain, prism_multi_asset_publisher).
- 4 new test files: `test_env_manager.py`, `test_reactive_propagation.py`, `test_settings_persistence.py`, `test_website_examples.py`. Total: 142 tests.

### Fixed
- Qt thread-violation crash when typing in a node text input wired to a downstream node — `_propagate_all_outputs()` was called from the `AsyncRuntime` background thread. Fixed with `_MainThreadDispatcher(QObject)` + `pyqtSignal(object)` + `Qt.QueuedConnection` in `src/ui/node_widget.py`.
- Settings changes not applied in the same session — `_open_settings()` discarded the `exec_()` return value. Now checks `QDialog.Accepted` and triggers node registry reload + library panel refresh + scripts menu rebuild in `src/ui/window.py`.

---

## [v2.1.1] — 2026-05-14

**Type:** Patch

### Fixed
- Scripting Console theme not applied on switch — code editor, debug output, and Git status panels now correctly transition between dark and light themes via new `ScriptingConsole.apply_theme(is_dark)` method.
- Windows 11 "Unknown publisher" on exe launch — added `file_version_info.txt` (PyInstaller `VSVersionInfo` format) embedded via `version=` in `vibrante_node.spec`, stamping company name, product name, version `2.1.1.0`, and copyright into the exe's `VERSIONINFO` resource.

### Changed
- `plugins/houdini/LICENSE` added — standalone commercial license for the Houdini integration plugin, separate from the core open-source LICENSE.
- About Vibrante-Node Integration dialog in Houdini now displays the plugin license text.
- Contact email standardised to `contact@vibrante-node.com` across all files.
- Official website `https://vibrante-node.com` added to relevant locations.

### Documentation
- All HTML docs (`docs/`) regenerated to v2.1.1.
- All portal HTML docs (`docs/portal/`) regenerated to v2.1.1.
- `docs_src/` markdown sources updated to v2.1.1 titles, headers, and footers.
- `RELEASE_v2.1.1.html` and `RELEASE_v2.1.0.html` added to the docs index.
- `tools/build_docs.py` — added v2.1.1 & v2.1.0 to RELEASE_DOCS; fixed `releases/` path prefix for v1.0.5–v1.8.3 source files; bumped template to v2.1.1.
- `tools/build_docs_portal.py` — bumped all template version strings to v2.1.1.
- `CLAUDE.md` — section 10.17 added documenting the VERSIONINFO fix and maintenance rules.

---

## [v2.1.0] — 2026-05-14

**Type:** Minor (UX quality-of-life)

### New Features
- **Unsaved Changes Detection** — every workflow tab tracks dirty state. A `*` prefix marks modified tabs; closing a dirty tab or the application shows Save / Discard / Cancel.
- **Port Type Mismatch Warning** — connecting incompatible port types logs a `warning` to the log panel. Connection is still allowed; `any`-typed ports are always compatible.

### Fixed
- F5 / Shift+F5 keyboard shortcuts were wired to tooltips but never registered as key bindings — now correctly registered via `setShortcut()`.
- Loading a saved workflow incorrectly set `_dirty = True`, marking tabs with `*` on open — now suppressed via `_undoing` guard in `from_workflow_model()`.
- Autosave tab name now strips `"* "` dirty prefix before writing, preventing restored tabs from showing `[Recovered] * name`.
- Autosave-restored tabs now correctly start as dirty (`_dirty = True`, `dirty_changed(True)` emitted) since recovered content is unsaved crash data.

---

## [v2.0.0] — 2026-05-10

**Type:** Major

### New Features
- **Subgraph / Group Node** (Ctrl+Shift+G) — collapse selected nodes into a GroupNode. Double-click to open in a fully editable subgraph tab with real-time sync-back via `_sync_callback`.
- **Live Wire Value Inspector** — hover over connected wires to see the last value that flowed through, capped at 300 chars.
- **Autosave & Crash Recovery** — 2-minute autosave to `~/.vibrante_node_autosave.json`; restore dialog on next launch.
- **Recent Files** — File → Open Recent submenu, last 10 workflows, grayed-out if file deleted.
- **Canvas Search Bar** (Ctrl+F) — floating search over node names/IDs; Enter/▼ cycles matches.
- **Mini-map** (Ctrl+M) — 200×150 thumbnail in canvas corner; click/drag to pan; viewport indicator.
- **Node Execution Timing** — log panel shows `Node 'X' finished in Y.XXs` after each node.
- **Export / Import Python** — convert workflows to executable Python scripts and back.
- **Script Editor dialog** — standalone code editor for quick scripting outside the console.

### Fixed
- GroupNode `exec_fail` port fires only on unhandled exceptions, not on semantic failures.
- GroupIn injection uses `parameters["_injected_value"]` not `parameters["value"]` to avoid race with engine `clear_outputs()`.
- UUID comparison in group collapse uses `str(instance_id)` consistently.
- `KeyboardInterrupt` no longer crashes the app on Ctrl+C during execution.

---

## [v1.8.5] — 2026 Q2

**Type:** Patch

### Fixed
- `code_editor.py` — `ImportError` on missing QScintilla no longer crashes startup; fallback `QPlainTextEdit`-based `CodeEditor` used instead.
- `hou_bridge.py` — socket fixes: `TCP_NODELAY` (removes ~40 ms Nagle delay on Windows), `threading.Lock` per instance, 30 s `socket.timeout`, auto-reconnect on `BrokenPipeError`.
- `vibrante_hou_server.py` — `AttributeError` on `hou.playbar.frameRange()` in headless Houdini caught; `OperationFailed` on unsupported display/render flags caught; `threading.Lock` prevents double-bind.
- `window.py` — Houdini nodes and scripts now load correctly; `load_all_with_extras` replaces `load_all`; `_populate_scripts_menu()` reads `v_scripts_path`.

---

## [v1.8.4] — 2026 Q2

**Type:** Minor

### New Features
- **Node Builder GUI** — visual interface for creating node JSON definitions without writing JSON by hand.
- **Scripting Console** — interactive Python REPL with full access to the window and scene context.
- **Script Editor dialog** — full-featured code editor with QScintilla (Python syntax, autocomplete).
- **Export to Python / Import from Python** — round-trip workflow ↔ Python script conversion.

---

## [v1.7.0] — 2026 Q2

**Type:** Minor

### New Features
- **Prism Pipeline overhaul** — 40+ Prism nodes covering assets, shots, sequences, products, media, scenes, and export paths.
- `prism_core_init` auto-bootstrap — place anywhere in the graph; engine detects and calls before execution.
- `resolve_prism_core()` utility — auto-wires `PrismCore` to all `prism_*` nodes from shared memory.
- Prism v2.1.0 API compatibility — `getShots()` flat-list handling, corrected `createProduct` signature.

---

## [v1.6.0] — 2026 Q2

**Type:** Minor

### New Features
- **Prism Pipeline Integration** — initial Prism node set.
- **Python Script Node** — embed arbitrary async Python logic directly in a workflow.
- **While Loop Node** — conditional looping with max-iterations guard.
- **Utility Node Library** — string, math, list, dict, file, HTTP, JSON, timer, and random nodes.

---

## [v1.5.0] — 2026 Q1

**Type:** Minor

### New Features
- **Headless Action Nodes** — Maya, Houdini, and Blender action-list builder nodes for offline DCC execution.
- Headless executor dispatches action lists to DCC runner scripts.

---

## [v1.0.5] — 2026 Q1

**Type:** Patch

### Fixed
- Recursive data pulling — nodes automatically pull latest values from upstream data-only nodes before execution, ensuring loop iterations use fresh data.
- Topological execution engine introduced; replaced naive sequential execution.

---

*For older versions see `releases/` directory.*
