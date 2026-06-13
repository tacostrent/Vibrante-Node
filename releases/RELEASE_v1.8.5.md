# Release Notes — Vibrante-Node v1.8.5

**Release date:** 2026-05-05
**Build:** Python 3.10 / PyInstaller — Windows 64-bit

---

## Overview

v1.8.5 is a polish and bugfix release focused on the code editor, Node Builder UX, and the node canvas widget layer.

---

## New Features

### Professional Code Editor (QScintilla)
All code editors across the application have been replaced with `QsciScintilla` (QScintilla), providing a full IDE-grade editing experience:

- Syntax highlighting with Dracula-dark and One-Light palettes
- Line numbers, code folding (boxed-tree style), and brace matching
- Auto-completion for Python keywords, builtins, and node API symbols
- Real-time syntax error markers in the gutter
- Ctrl+Wheel zoom
- Theme switches apply instantly to all open editors

### Node Builder UX Overhaul
- Window is now **maximizable** with full minimize / maximize / close buttons
- **Python Algorithm editor is the hero panel** — it takes all available horizontal space; configuration and AI chat panels are compact side panes
- Left configuration panel is scrollable so all fields remain accessible when narrow
- Exec port checkboxes now correctly add / remove `add_exec_input` / `add_exec_output` lines in generated code; `use_exec=True` when any exec port is active, `use_exec=False` only when both are off

### Theme System
- **Dracula Theme** (renamed from "Dark Theme") and One-Light theme now persist immediately on switch — no need to close the app
- Theme cascades to all open dialogs (Script Editor, Node Builder, Export dialog) via `QApplication.topLevelWidgets()`
- Global Fusion style applied for consistent QSS rendering on Windows (border-radius, custom scrollbars, etc.)
- Comprehensive dark stylesheet covers all widget types: `QCheckBox` with indicator, `QComboBox` with dropdown, `QSlider`, `QScrollBar`, `QTabBar`, `QMenuBar`, and more

---

## Bug Fixes

### Canvas Dropdown Menu
- Dropdown menus in canvas node widgets now close on the **first** outside click
- Fixed crash when selecting an item from the dropdown (C++ object destroyed mid-signal emission)
- Fixed dropdown arrow not rendering after theme stylesheet was applied
- Fixed multiple clicks required to dismiss — `_MenuCloser` app-level event filter intercepts mouse press events before QGraphicsView can consume them

### Canvas Slider Widget
- Slider groove, filled track, and handle are now visible with proper QSS (`::groove`, `::sub-page`, `::handle`)

### Node Search Popup (Tab)
- Single click now adds exactly one node — removed `itemDoubleClicked` + `itemActivated` dual-signal setup that caused double adds on double-click

### Code Editor Theme Init
- Editors in Script Editor and Node Builder now open with the correct saved theme on first show — palette is baked into the lexer before `setLexer()` is called so no black-on-white flash occurs

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Tab` | Open node-search popup |
| `Ctrl+E` | Edit selected node in Node Builder |
| `Ctrl+R` | Reload selected node from disk |
| `Ctrl+Shift+R` | Reload all nodes |
| `F5` | Run workflow |
| `F` | Focus selected nodes |
| `Ctrl+C` / `Ctrl+V` | Copy / Paste nodes |
| `Delete` | Delete selected items |
| `Ctrl+Wheel` | Zoom code editor font |

---

## Upgrade Notes

- `QScintilla` is now a required dependency (`pip install QScintilla`). It is bundled in the Windows release build.
- The `src/utils/highlighter.py` module (old QSyntaxHighlighter) is no longer used by any editor but is kept for backward compatibility with third-party scripts.
