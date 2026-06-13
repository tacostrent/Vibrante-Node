# Release Notes — Vibrante-Node v2.2.1

**Release date:** 2026-05-15
**Type:** Patch — exe build bug fixes
**Previous release:** v2.2.0

---

## Summary

Two bugs that only manifested in the frozen Windows exe (not in dev mode) are fixed in this release.

---

## Bug Fixes

### About Dialog crash — `AttributeError: 'QTextEdit' object has no attribute 'setOpenExternalLinks'`

**Symptom:** Opening **Help → About Vibrante-Node** in the exe build crashed with:
```
AttributeError: 'QTextEdit' object has no attribute 'setOpenExternalLinks'
```

**Root cause:** The `_show_about()` fallback branch (shown when the LICENSE file cannot be found) called `text_edit.setOpenExternalLinks(True)` on a `QTextEdit` instance. `setOpenExternalLinks` is a method of `QLabel` and `QTextBrowser`, not `QTextEdit`.

**Fix:** Changed the license display widget from `QTextEdit` to `QTextBrowser`. `QTextBrowser` is a subclass of `QTextEdit` with identical API plus full support for `setOpenExternalLinks(True)`. All existing calls (`setReadOnly`, `setFont`, `setLineWrapMode`, `setPlainText`, `setHtml`) continue to work unchanged.

**File:** `src/ui/window.py`

---

### About Dialog always showed "LICENSE file not found" fallback in exe build

**Symptom:** Even after installing the exe, the About dialog displayed:
> "LICENSE file not found. See https://vibrante-node.com for full license terms."

instead of the actual license text.

**Root cause:** The `LICENSE` file was not included in the PyInstaller `datas` list in `vibrante_node.spec`. When `resource_path('LICENSE')` was called at runtime, it looked for the file at `sys._MEIPASS/LICENSE` (`_internal/LICENSE`) — but the file was never bundled there.

**Fix:** Added `('LICENSE', '.')` to the `datas` list in `vibrante_node.spec`. PyInstaller now copies `LICENSE` into `_internal/` alongside `splash.png`, `logo.png`, and the other bundled assets. `resource_path('LICENSE')` finds it correctly in the frozen exe.

**File:** `vibrante_node.spec`

---

## Migration Notes

No breaking changes. No configuration changes required.

Both fixes are transparent to the user — the About dialog now opens correctly and shows the full license text. No workflow, node, or settings files are affected.

---

## Files Modified

| File | Change |
|------|--------|
| `src/ui/window.py` | `QTextEdit` → `QTextBrowser` in `_show_about()`; added `QTextBrowser` to local import |
| `vibrante_node.spec` | Added `('LICENSE', '.')` to `datas`; version comment updated to v2.2.1 |
| `file_version_info.txt` | Version `2.2.1.0` |
| `src/main.py` | Version bump to v2.2.1 |
