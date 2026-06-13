"""
Vibrante Config Reader
======================
Reads Vibrante credentials and paths from the canonical Houdini package file
and applies them to os.environ so acquisition modules work without shell-level
environment variable setup.

Canonical source — the Houdini packages file:
  ~/Documents/houdini*/packages/vibrante_node.json  (Windows)
  ~/houdini*/packages/vibrante_node.json             (Linux/macOS)

  This is the file users configure when setting up the Houdini integration.
  It already contains VIBRANTE_MEGASCANS_TOKEN, VIBRANTE_MEGASCANS_LIBRARY,
  and all other credentials. The MCP server reads it directly from disk —
  no shell env setup required, no system env vars, no restart needed.

Lookup order (first file found with a non-placeholder value wins):
  1. VIBRANTE_CONFIG_PATH env var     — explicit override
  2. ~/Documents/houdini*/packages/   — Houdini user packages  ← primary
  3. ~/houdini*/packages/             — Linux/macOS equivalent
  4. VIBRANTE_NODE_APP/plugins/...    — subprocess path (when launched from Houdini)
  5. vibrante_node.local.json         — gitignored dev override
  6. source-tree vibrante_node.json   — placeholder fallback

  Additionally: if Houdini is running, bridge.run_code() reads env vars
  directly from the live Houdini process (covers vars set at runtime).

Only vars NOT already in os.environ are applied (shell settings win).

Usage:
    from src.utils.vibrante_config import apply_vibrante_config
    apply_vibrante_config()        # idempotent; safe to call from any module

    from src.utils.vibrante_config import read_from_houdini_session
    cfg = read_from_houdini_session()   # {} when Houdini not running (silent)
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional

_PACKAGE_FILE       = "vibrante_node.json"
_LOCAL_PACKAGE_FILE = "vibrante_node.local.json"
_APPLY_LOCK         = threading.Lock()
_applied            = False

_VIBRANTE_ENV_VARS = (
    "VIBRANTE_MEGASCANS_LIBRARY",
    "VIBRANTE_FAB_LIBRARY",
    "VIBRANTE_MEGASCANS_TOKEN",
    "VIBRANTE_MEGASCANS_APP_ID",
    "VIBRANTE_MEGASCANS_APP_KEY",
    "VIBRANTE_MEGASCANS_USERNAME",
    "VIBRANTE_MEGASCANS_PASSWORD",
    "VIBRANTE_ASSET_CACHE",
    "VIBRANTE_ASSET_STORAGE",
    "VIBRANTE_PROJECT_STAGING",
    "VIBRANTE_NODE_APP",
    "VIBRANTE_PYTHON_EXE",
)


# ---------------------------------------------------------------------------
# Path discovery — Houdini packages dirs come first
# ---------------------------------------------------------------------------

def _candidate_paths() -> List[Path]:
    """Return all candidate config file paths, most-specific first."""
    candidates: List[Path] = []

    # 0. Explicit override
    explicit = os.environ.get("VIBRANTE_CONFIG_PATH", "").strip()
    if explicit:
        candidates.append(Path(explicit))

    # 1. Houdini user packages directories — THE canonical source
    _houdini_pkg_dirs(candidates)

    # 2. VIBRANTE_NODE_APP — set when running as a Houdini subprocess
    app_root = os.environ.get("VIBRANTE_NODE_APP", "").strip()
    if app_root:
        candidates.append(Path(app_root) / "plugins" / "houdini" / _PACKAGE_FILE)

    # Source-tree location (used for .local.json and the placeholder fallback)
    try:
        pkg_dir = Path(__file__).resolve().parent.parent.parent / "plugins" / "houdini"
    except Exception:
        pkg_dir = Path.cwd() / "plugins" / "houdini"

    # 3. Gitignored dev override next to source copy
    candidates.append(pkg_dir / _LOCAL_PACKAGE_FILE)

    # 4. Source-tree copy (placeholder values — lowest priority)
    candidates.append(pkg_dir / _PACKAGE_FILE)

    # 5. CWD last resort
    candidates.append(Path.cwd() / "plugins" / "houdini" / _PACKAGE_FILE)

    seen:   set        = set()
    result: List[Path] = []
    for p in candidates:
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result


def _houdini_pkg_dirs(out: List[Path]) -> None:
    """Append all existing Houdini user packages paths to out, newest version first."""
    try:
        home = Path.home()
        dirs: List[Path] = []

        # Windows: ~/Documents/houdiniXX.Y/packages/
        docs = home / "Documents"
        if docs.exists():
            for entry in docs.iterdir():
                if entry.is_dir() and entry.name.lower().startswith("houdini"):
                    dirs.append(entry / "packages" / _PACKAGE_FILE)

        # Linux/macOS: ~/houdiniXX.Y/packages/
        for entry in home.iterdir():
            if entry.is_dir() and entry.name.lower().startswith("houdini"):
                dirs.append(entry / "packages" / _PACKAGE_FILE)

        # Sort newest version first so houdini20.5 beats houdini19.5
        dirs.sort(key=lambda p: p.parent.parent.name, reverse=True)
        out.extend(dirs)
    except Exception:
        pass


def find_vibrante_node_json() -> Optional[Path]:
    """Return the first existing config file, or None."""
    for candidate in _candidate_paths():
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Live Houdini session (bridge) — supplements file-based values
# ---------------------------------------------------------------------------

def read_from_houdini_session() -> Dict[str, str]:
    """
    Query the running Houdini process for Vibrante env vars via the bridge.

    Houdini loaded vibrante_node.json from its packages directory and set
    these vars in its own process.  Returns {} silently when Houdini is not
    reachable.  Never raises.
    """
    try:
        from src.utils.hou_bridge import get_bridge
        bridge = get_bridge()
        keys_repr = repr(list(_VIBRANTE_ENV_VARS))
        # run_code sandbox only provides hou; os must be imported inside the code.
        # Dict comprehensions in exec() don't close over exec-local imports, so
        # we use a plain for-loop which shares the same local namespace.
        code = (
            "import os\n"
            "result = {}\n"
            f"for _k in {keys_repr}:\n"
            "    result[_k] = os.environ.get(_k, '')"
        )
        result = bridge.run_code(code)
        env_dict = result.get("result") or {}
        if not isinstance(env_dict, dict):
            return {}
        return {k: str(v) for k, v in env_dict.items() if v}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def read_vibrante_config(path: Optional[Path] = None) -> Dict[str, str]:
    """Parse a vibrante_node.json and return its env entries as a flat dict."""
    try:
        target = path or find_vibrante_node_json()
        if not target or not target.exists():
            return {}
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        result: Dict[str, str] = {}
        for entry in (data.get("env") or []):
            if isinstance(entry, dict):
                for k, v in entry.items():
                    result[str(k)] = str(v)
        return result
    except Exception:
        return {}


def _is_placeholder(value: str) -> bool:
    v = value.strip()
    return not v or (v.startswith("<") and v.endswith(">")) or v.startswith("$")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def apply_vibrante_config(*, force: bool = False) -> Dict[str, str]:
    """
    Populate os.environ with Vibrante credentials/paths.

    Source priority:
      1. Live Houdini session (bridge.run_code) — ALWAYS wins, even over existing
         os.environ values.  The user explicitly configured vibrante_node.json;
         that is the authoritative source.  Stale system env vars are overridden.
      2. File-based fallback (packages dir / local.json) — only fills gaps where
         os.environ has no value yet.

    Skips placeholder / empty values.
    Idempotent after first call; pass force=True to re-read.

    Returns the set of var names actually applied (values omitted — may be tokens).
    """
    global _applied
    with _APPLY_LOCK:
        if _applied and not force:
            return {}

        applied: Dict[str, str] = {}

        # 1. Live Houdini session — authoritative; overrides stale os.environ values
        houdini_vals = read_from_houdini_session()
        for key, value in houdini_vals.items():
            if not _is_placeholder(value):
                os.environ[key] = value   # intentional override
                applied[key] = key

        # 2. File-based fallback — only fills vars not already in os.environ
        for key, value in read_vibrante_config().items():
            if key not in os.environ and not _is_placeholder(value):
                os.environ[key] = value
                applied[key] = key

        _applied = True
        return applied


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def reset_vibrante_config_for_tests() -> None:
    global _applied
    with _APPLY_LOCK:
        _applied = False
