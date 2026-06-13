# Release Notes — Vibrante-Node v2.1.1

**Release date:** 2026-05-14
**Build:** Python 3.10 / PyInstaller — Windows 64-bit
**Previous release:** v2.1.0 (2026-05-14)

---

## Overview

v2.1.1 is a patch release that fixes the Scripting Console theme not applying on theme switch, ships the Houdini plugin's standalone LICENSE file, adds proper Windows VERSIONINFO metadata to the exe (fixes "Unknown publisher" on Windows 11), and cleans up contact information throughout the codebase.

---

## Bug Fixes

### Scripting Console — Theme Not Applied on Switch

Switching to the light theme previously left the Scripting Console's code editor, debug output panel, and Git status panel still rendering with the dark palette.

**Root causes fixed:**
- `debug_output` and `git_status` `QTextEdit` widgets had hardcoded dark-theme stylesheets set at construction time and were never updated when the theme changed.
- `_cascade_editor_theme()` in `window.py` only searched for `QsciScintilla` children; on systems without QScintilla installed it returned early, leaving the fallback `QPlainTextEdit`-based `CodeEditor` untouched.

**Fix:** `ScriptingConsole.apply_theme(is_dark)` now updates all three widgets. `MainWindow._apply_dark_theme()` and `_apply_light_theme()` call `scripting_console.apply_theme()` before cascading to other panels.

### Windows 11 — "Unknown publisher" on Exe Launch

The built `Vibrante-Node.exe` showed "Unknown publisher" in file Properties and Windows security prompts because no Windows `VERSIONINFO` resource was embedded.

**Fix:** Added `file_version_info.txt` (PyInstaller `VSVersionInfo` format) and wired it into `vibrante_node.spec` via `version='file_version_info.txt'`. The exe now embeds company name, product name, version `2.1.1.0`, and copyright metadata readable by Windows Explorer and security dialogs.

> **Note:** Windows SmartScreen and UAC elevation dialogs ("orange shield") still require a trusted code-signing certificate. This fix addresses the metadata layer only.

---

## Changes

### Houdini Plugin
- Added `plugins/houdini/LICENSE` — standalone commercial license for the Houdini integration plugin, separate from the core open-source LICENSE.
- About Vibrante-Node Integration dialog now shows the Houdini plugin license text.

### Contact & Legal
- Replaced personal email addresses throughout the codebase with the official `contact@vibrante-node.com` address.
- Added official website (`https://vibrante-node.com`) to all relevant locations.

---

## Developer Notes

- `file_version_info.txt` — new file at project root; must be kept in sync with the version shown in `src/ui/window.py` (About dialog). Update both `filevers`/`prodvers` tuples and `FileVersion`/`ProductVersion` strings on every version bump.
- `CLAUDE.md` — developer guide updated with section 10.17 documenting the VERSIONINFO fix and the maintenance rule.

---

## Upgrade Notes

No workflow format changes. Existing `.json` workflow files are fully compatible with v2.1.1.
