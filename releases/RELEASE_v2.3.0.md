# Release Notes — Vibrante-Node v2.3.0

**Released:** 2026-05-18
**Type:** Minor — new nodes, developer tooling, and bug fixes

---

## What's New

### HTTP Request Node (Network category)

A new bundled `http_request` node is now available in the **Network** category. It performs async GET or POST requests without blocking the UI:

- Inputs: `url`, `method` (default `"GET"`), `headers` (any), `body` (any), `timeout` (int, default 30 s)
- Outputs: `response_data` (parsed JSON or raw text), `status_code`, `response_text`, `success` (bool)
- Fully non-blocking — the entire HTTP stack (DNS, TCP, TLS, body) runs in a thread pool via `loop.run_in_executor`, keeping the Qt main thread free
- Uses stdlib `urllib.request` — no extra dependencies
- Icon: `icons/http.png`

### Authenticode Signing Scripts

Two new PowerShell scripts in `tools/` simplify code-signing the Windows exe:

- `tools/create_dev_cert.ps1` — creates a self-signed code-signing certificate and trusts it locally; changes "Unknown publisher" → "Vibrante-Node Dev" on the local machine for testing
- `tools/sign_release.ps1` — signs the built exe with the best available certificate in the current-user cert store; pass `-Thumbprint` to target a specific cert

See section 10.17 of CLAUDE.md for OV/EV cert guidance.

---

## Bug Fixes

### Canvas Drag Trail Artifact (CLAUDE.md 10.32)

Dragging a node left a persistent "trail" of port-connector ellipses on the canvas background.

**Root cause:** `NodeWidget.boundingRect()` returned only the body rect `(0, 0, width, height)`. Port connectors extend ±6 px beyond the node edges. Qt computes the dirty region from the declared `boundingRect()` — pixels outside this rect were never cleared on repaint, causing the trail.

**Fix (three-part):**
- `boundingRect()` expanded by 8 px on each side to cover port connectors
- `shape()` overridden to return the body-only rounded-rect path — preserves correct rubber-band selection and click hit-testing
- `paint()` uses a local `_r = QRectF(0, 0, width, height)` instead of `self.boundingRect()` — body is drawn at the correct size regardless of the expanded bounding rect

**File:** `src/ui/node_widget.py`

### HTTP Request UI Freeze (CLAUDE.md 10.31)

Running the `http_request` node froze the Qt UI for the duration of the network call.

**Root cause:** The project uses an `_EventLoopRunner` that drives asyncio on the Qt main thread via a zero-interval `QTimer`. Any synchronous OS call inside a coroutine (DNS, TCP connect, TLS handshake) blocked the timer and therefore the entire UI.

**Fix:** The complete HTTP transaction is offloaded to the OS thread pool via `await loop.run_in_executor(None, _sync_do)`. This is fully decoupled from the stepped event loop — Qt continues processing events normally while the network call runs in a background thread.

**Files:** `nodes/http_request.json`, `website_examples/http_request.json`

### Node Builder — Exec Port Type Corruption (CLAUDE.md 10.28)

Opening any hand-written node for editing via Node Builder then saving changed the type of `exec_in` / `exec_out` or added a duplicate port call.

**Fix:** `_load_existing_node()`, `_sync_code_to_ui()`, and `save_node()` now filter `exec_in` and `exec_out` from table rows. Exec ports are exclusively managed by the exec checkboxes.

**File:** `src/ui/node_builder.py`

### Node Builder — Default Value Loss (CLAUDE.md 10.29)

Editing any node via Node Builder reset every port's `default` to `null`.

**Fix:** Port tables expanded to 5 columns (added `Default`). `_update_table()` reads `p.default`; `save_node()` writes it back to `PortModel`.

**File:** `src/ui/node_builder.py`

### Node Builder — Icon Path Field Side Effects (CLAUDE.md 10.30)

Typing in the icon path field triggered a full code regeneration, corrupting `init_first`, `use_exec`, and exec port settings.

**Fix:** `icon_edit.textChanged` now connects to a dedicated `_sync_icon_to_code()` method that performs only a single `re.sub` on the `self.icon_path = …` assignment line.

**File:** `src/ui/node_builder.py`

### Load Node From JSON — Wrong Initial Directory / No Content Check (CLAUDE.md 10.26)

Selecting a workflow `.json` through Nodes → Load Node From JSON showed no error and the node didn't load.

**Fix:** Dialog now starts in `self.nodes_dir` (not the last-visited shell directory). A content pre-check detects workflow files and shows a specific error: "This is a workflow file, not a node definition."

**File:** `src/ui/window.py`

### Load Workflow — Silently Accepted Node JSON (CLAUDE.md 10.27)

Selecting a node definition `.json` through File → Load Workflow created an empty workflow tab with no error.

**Fix:** `_looks_like_node_json()` helper; both `load_workflow()` and `_load_workflow_from_path()` reject node JSONs with a clear message before calling `model_validate_json`.

**File:** `src/ui/window.py`

---

## Documentation

- Full HTML documentation portal regenerated to v2.3.0
- `docs_src/` markdown sources updated (titles, headers, footers, version history table)
- CLAUDE.md: sections 10.31 (http_request freeze) and 10.32 (canvas drag trail) added
- README: node library count updated (167+), Latest Release section updated

---

## Upgrade Notes

No breaking changes. All v2.2.x workflows load without modification.

The `http_request` node is now in `nodes/http_request.json`. If you previously loaded it via Nodes → Load Node From JSON from a local copy, uninstall the local copy to avoid duplicates in the Library.
