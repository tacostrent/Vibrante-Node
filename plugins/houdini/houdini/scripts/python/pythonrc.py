"""
Vibrante-Node Houdini startup script.
Automatically runs when Houdini starts with the Vibrante-Node package installed.
"""

import os
import sys


def _check_env():
    """Validate required environment variables and print a diagnostic summary."""
    app_root = os.environ.get("VIBRANTE_NODE_APP", "")
    python_exe = os.environ.get("VIBRANTE_PYTHON_EXE", "")

    ok = True

    if not app_root or not os.path.isdir(app_root):
        print(
            "[Vibrante-Node] ERROR: VIBRANTE_NODE_APP is not set or invalid.\n"
            f"  Current value: '{app_root}'\n"
            "  Edit vibrante_node.json and set VIBRANTE_NODE_APP to the\n"
            "  Vibrante-Node installation folder (where src/main.py lives)."
        )
        ok = False
    else:
        print(f"[Vibrante-Node] VIBRANTE_NODE_APP   = {app_root}  OK")

    if not python_exe:
        print(
            "[Vibrante-Node] WARNING: VIBRANTE_PYTHON_EXE is not set.\n"
            "  The plugin will auto-detect a system Python with PyQt5.\n"
            "  Set VIBRANTE_PYTHON_EXE in vibrante_node.json to avoid\n"
            "  the detection delay on each launch."
        )
    elif not os.path.isfile(python_exe):
        print(
            f"[Vibrante-Node] WARNING: VIBRANTE_PYTHON_EXE path not found:\n"
            f"  '{python_exe}'\n"
            "  Update vibrante_node.json with the correct path."
        )
        ok = False
    else:
        print(f"[Vibrante-Node] VIBRANTE_PYTHON_EXE = {python_exe}  OK")

    # v_nodes_dir and v_scripts_path are computed at launch time by setup_env().
    # Show what will be passed to the subprocess so users can verify paths.
    if app_root and os.path.isdir(app_root):
        nodes_dir = os.path.join(app_root, "plugins", "houdini", "v_nodes_houdini")
        scripts_dir = os.path.join(app_root, "plugins", "houdini", "v_scripts_houdini")

        nodes_ok = os.path.isdir(nodes_dir)
        scripts_ok = os.path.isdir(scripts_dir)

        print(
            f"[Vibrante-Node] v_nodes_dir (subprocess) = {nodes_dir}"
            f"  {'OK' if nodes_ok else 'MISSING — folder not found'}"
        )
        print(
            f"[Vibrante-Node] v_scripts_path (subprocess) = {scripts_dir}"
            f"  {'OK' if scripts_ok else 'MISSING — folder not found'}"
        )

    # Asset acquisition paths — print so users can verify at a glance
    lib = os.environ.get("VIBRANTE_MEGASCANS_LIBRARY", "")
    cache = os.environ.get("VIBRANTE_ASSET_CACHE", "")
    if lib:
        exists = os.path.isdir(lib)
        print(
            f"[Vibrante-Node] VIBRANTE_MEGASCANS_LIBRARY = {lib}"
            f"  {'OK' if exists else 'WARNING: path does not exist'}"
        )
    if cache:
        print(f"[Vibrante-Node] VIBRANTE_ASSET_CACHE       = {cache}")

    return ok


# Add the bundled venv site-packages (pydantic, google-generativeai, etc.).
# This venv intentionally has NO Qt packages to avoid conflicts with
# Houdini's built-in PySide2/shiboken2.
_app_root = os.environ.get("VIBRANTE_NODE_APP", "")
if _app_root:
    _venv_sp = os.path.join(
        _app_root, "plugins", "houdini", "houdini",
        "scripts", "python", "env", "Lib", "site-packages"
    )
    if os.path.isdir(_venv_sp) and _venv_sp not in sys.path:
        sys.path.append(_venv_sp)

_check_env()
print("[Vibrante-Node] Plugin ready. Use the Vibrante-Node menu or shelf to launch.")
