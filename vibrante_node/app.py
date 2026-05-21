"""
CLI entry point for pip-installed vibrante-node.

When installed via pip, all data files (nodes/, icons/, docs/, etc.) are
bundled inside this package directory by the build hook in setup.py.
This module patches src.utils.paths.resource_path() to point at that
bundled data BEFORE importing anything from src/, so every downstream
import sees the correct paths.

In development (editable install / running from source), the nodes/
directory does NOT exist inside this package dir, so the patch is skipped
and resource_path() falls through to its normal repo-root resolution.
"""
import os
import sys


def main():
    _here = os.path.dirname(os.path.abspath(__file__))

    # Ensure the project root (parent of vibrante_node/) is on sys.path so
    # that 'from src.xxx import ...' works.  In a normal pip install,
    # site-packages/ is already on the path and src is installed there.
    # In an editable install, the repo root is linked; this is a no-op.
    _project_root = os.path.dirname(_here)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    # Detect pip-installed (non-editable) mode: the build hook copies
    # nodes/ into the vibrante_node package directory.
    if os.path.isdir(os.path.join(_here, 'nodes')):
        import types

        def _resource_path(*parts):
            return os.path.join(_here, *parts)

        def _app_dir():
            # XDG-compliant writable user data directory on Linux.
            xdg_data = os.environ.get(
                'XDG_DATA_HOME',
                os.path.join(os.path.expanduser('~'), '.local', 'share'),
            )
            return os.path.join(xdg_data, 'vibrante-node')

        def _frozen():
            return False

        _paths_mod = types.ModuleType('src.utils.paths')
        _paths_mod.__file__ = os.path.join(_here, '_paths_shim.py')
        _paths_mod.resource_path = _resource_path
        _paths_mod.app_dir = _app_dir
        _paths_mod._frozen = _frozen
        sys.modules['src.utils.paths'] = _paths_mod

    from src.main import main as _app_main
    _app_main()


if __name__ == '__main__':
    main()
