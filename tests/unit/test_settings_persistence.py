"""Tests for Settings dialog save / apply / load-back cycle.

Three legs of the contract:
  SAVE       — clicking OK persists values to config immediately.
  APPLY      — accepting the dialog refreshes the live UI in the same session.
  LOAD BACK  — reopening the dialog (and on relaunch) shows the saved values.

Run: pytest tests/unit/test_settings_persistence.py -v
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock

from src.utils.config_manager import config
from src.utils.env_manager import env_manager


# ---------------------------------------------------------------------------
# Fixture: isolate config env.* keys and os.environ around each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    # Redirect the config file to a per-test temp path. Without this, any test
    # that goes through env_manager.set_*() / config.set() writes to the user's
    # real ~/.vibrante_node_config.json, leaving stale temp paths in their live
    # config after the suite runs.
    original_path = config._config_path
    original_data = {k: v for k, v in config._data.items()}
    original_env_nodes  = os.environ.get('v_nodes_dir', None)
    original_env_scripts = os.environ.get('v_scripts_path', None)
    original_init = env_manager._initialized

    monkeypatch.setattr(config, "_config_path", str(tmp_path / "vibrante_node_config.json"))
    config._data.clear()
    for k in ('v_nodes_dir', 'v_scripts_path'):
        os.environ.pop(k, None)
    env_manager._initialized = False

    yield

    # Restore in-memory state; on-disk state stays in tmp_path and is cleaned by pytest.
    config._data.clear()
    config._data.update(original_data)
    config._config_path = original_path
    if original_env_nodes is None:
        os.environ.pop('v_nodes_dir', None)
    else:
        os.environ['v_nodes_dir'] = original_env_nodes
    if original_env_scripts is None:
        os.environ.pop('v_scripts_path', None)
    else:
        os.environ['v_scripts_path'] = original_env_scripts
    env_manager._initialized = original_init


# ===========================================================================
# LEG 1 — SAVE  (config persistence)
# ===========================================================================

def test_save_v_nodes_dir_persists_to_config(tmp_path):
    """env_manager.set_v_nodes_dir() must write to config immediately."""
    d = str(tmp_path / "nodes")
    os.makedirs(d)
    env_manager.set_v_nodes_dir([d])
    assert config.get('env.v_nodes_dir') == [d]


def test_save_v_scripts_path_persists_to_config(tmp_path):
    d = str(tmp_path / "scripts")
    os.makedirs(d)
    env_manager.set_v_scripts_path([d])
    assert config.get('env.v_scripts_path') == [d]


def test_save_custom_variables_persists_to_config():
    env_manager.set_custom_variables({'MY_STUDIO': '/studio'})
    assert config.get('env.custom_variables') == {'MY_STUDIO': '/studio'}


def test_save_vibrante_pythonpath_persists_to_config(tmp_path):
    d = str(tmp_path / "pylib")
    os.makedirs(d)
    env_manager.set_vibrante_pythonpath([d])
    assert config.get('env.vibrante_pythonpath') == [d]


# ===========================================================================
# LEG 2 — APPLY  (live session refresh after dialog accept)
# ===========================================================================

def test_open_settings_refreshes_library_and_scripts_on_accept(qtbot):
    """After the Settings dialog is Accepted, _open_settings must reload
    the node registry and refresh the library panel and scripts menu.
    Before the fix, _open_settings ignored the dialog return value so
    these refreshes never happened."""
    import sys, os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

    from src.ui.window import MainWindow
    from src.utils.qt_compat import QtWidgets

    window = MainWindow()

    with (
        patch.object(window.library_panel, 'refresh') as mock_lib,
        patch.object(window, '_populate_scripts_menu') as mock_scripts,
        patch('src.ui.window.SettingsWindow') as MockSettings,
    ):
        # Simulate user clicking OK
        MockSettings.return_value.exec_.return_value = QtWidgets.QDialog.Accepted

        window._open_settings()

        mock_lib.assert_called_once(), \
            "library_panel.refresh() must be called after settings accepted"
        mock_scripts.assert_called_once(), \
            "_populate_scripts_menu() must be called after settings accepted"


def test_open_settings_no_refresh_on_cancel(qtbot):
    """If the dialog is Rejected (Cancel / X), no refresh should happen."""
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

    from src.ui.window import MainWindow
    from src.utils.qt_compat import QtWidgets

    window = MainWindow()

    with (
        patch.object(window.library_panel, 'refresh') as mock_lib,
        patch.object(window, '_populate_scripts_menu') as mock_scripts,
        patch('src.ui.window.SettingsWindow') as MockSettings,
    ):
        MockSettings.return_value.exec_.return_value = QtWidgets.QDialog.Rejected

        window._open_settings()

        mock_lib.assert_not_called()
        mock_scripts.assert_not_called()


def test_apply_loads_nodes_from_new_v_nodes_dir(tmp_path):
    """After settings are saved with a new v_nodes_dir, NodeRegistry must
    load nodes from that directory when load_all_with_extras is called
    (as _open_settings now does after accept)."""
    from src.core.registry import NodeRegistry
    from src.utils.paths import resource_path

    # Create a minimal node in a temp dir
    node_dir = tmp_path / "extra_nodes"
    node_dir.mkdir()
    node_def = {
        "node_id": "settings_persist_test_node",
        "name": "settings_persist_test_node",
        "description": "Temp node for settings test",
        "category": "Test",
        "inputs":  [{"name": "exec_in",  "type": "any"}],
        "outputs": [{"name": "exec_out", "type": "any"}],
        "python_code": "async def execute(self, inputs): return {'exec_out': True}"
    }
    (node_dir / "settings_persist_test_node.json").write_text(json.dumps(node_def))

    try:
        # Simulate: dialog accepted, reinitialize updated os.environ
        env_manager.set_v_nodes_dir([str(node_dir)])
        env_manager.reinitialize()

        # Simulate what _open_settings now does after accept
        NodeRegistry.load_all_with_extras(resource_path('nodes'))

        assert NodeRegistry.get_definition('settings_persist_test_node') is not None, \
            "Node from newly configured v_nodes_dir must load after settings accept"
    finally:
        NodeRegistry._definitions.pop('settings_persist_test_node', None)
        NodeRegistry._classes.pop('settings_persist_test_node', None)
        env_manager.set_v_nodes_dir([])


# ===========================================================================
# LEG 3 — LOAD BACK  (saved values appear in dialog on next open / relaunch)
# ===========================================================================

def test_load_back_v_nodes_dir_shown_in_dialog(tmp_path, qtbot):
    """After saving v_nodes_dir, opening a new SettingsWindow must display it."""
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

    from PyQt5.QtWidgets import QApplication
    _ = QApplication.instance() or QApplication([])

    d = str(tmp_path / "nodes")
    os.makedirs(d)
    env_manager.set_v_nodes_dir([d])

    from src.ui.settings_window import SettingsWindow
    dlg = SettingsWindow()
    assert d in dlg._v_nodes_dir_edit.toPlainText()


def test_load_back_custom_vars_shown_in_dialog(qtbot):
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

    from PyQt5.QtWidgets import QApplication
    _ = QApplication.instance() or QApplication([])

    env_manager.set_custom_variables({'STUDIO': '/vfx', 'SHOW': 'myshow'})

    from src.ui.settings_window import SettingsWindow
    dlg = SettingsWindow()
    rows = {
        dlg._var_table.item(r, 0).text(): dlg._var_table.item(r, 1).text()
        for r in range(dlg._var_table.rowCount())
    }
    assert rows.get('STUDIO') == '/vfx'
    assert rows.get('SHOW') == 'myshow'


def test_relaunch_applies_v_nodes_dir_to_environ(tmp_path):
    """Simulated relaunch: env_manager.initialize() must merge saved
    v_nodes_dir into os.environ so NodeRegistry.load_all_with_extras picks it up."""
    d = str(tmp_path / "nodes")
    os.makedirs(d)
    env_manager.set_v_nodes_dir([d])

    # Simulate fresh process: clear the env var then re-initialize
    os.environ.pop('v_nodes_dir', None)
    env_manager._initialized = False
    env_manager.initialize()

    assert d in os.environ.get('v_nodes_dir', ''), \
        "v_nodes_dir must be in os.environ after initialize() on relaunch"


def test_relaunch_applies_custom_variables_to_environ():
    """Custom variables saved in config must be set in os.environ after
    initialize() on the next launch."""
    env_manager.set_custom_variables({'RELAUNCH_TEST_VAR': 'rocket'})

    os.environ.pop('RELAUNCH_TEST_VAR', None)
    env_manager._initialized = False
    env_manager.initialize()

    assert os.environ.get('RELAUNCH_TEST_VAR') == 'rocket'
    os.environ.pop('RELAUNCH_TEST_VAR', None)


# ===========================================================================
# LEG 4 — IMPORT / EXPORT  (settings file round-trip)
# ===========================================================================

def test_export_settings_returns_all_required_keys():
    """export_settings() must return a dict containing all 4 managed groups."""
    data = env_manager.export_settings()
    for key in ("vibrante_pythonpath", "v_nodes_dir", "v_scripts_path", "custom_variables"):
        assert key in data, f"export_settings() missing key: '{key}'"


def test_export_settings_reflects_current_state(tmp_path):
    """export_settings() values must match what was set via the set_* methods."""
    d = str(tmp_path / "nodes")
    os.makedirs(d)
    env_manager.set_v_nodes_dir([d])
    env_manager.set_custom_variables({"EXPORT_TEST_VAR": "42"})

    data = env_manager.export_settings()
    assert d in data["v_nodes_dir"]
    assert data["custom_variables"].get("EXPORT_TEST_VAR") == "42"


def test_import_settings_applies_values(tmp_path):
    """import_settings() must persist all 4 setting groups via set_* methods."""
    d = str(tmp_path / "import_nodes")
    os.makedirs(d)
    payload = {
        "vibrante_pythonpath": [],
        "v_nodes_dir": [d],
        "v_scripts_path": [],
        "custom_variables": {"IMPORT_VAR": "hello"},
    }
    env_manager.import_settings(payload)
    assert config.get("env.v_nodes_dir") == [d]
    assert config.get("env.custom_variables") == {"IMPORT_VAR": "hello"}


def test_import_settings_ignores_unknown_keys():
    """import_settings() must not raise on unknown/future keys in the file."""
    payload = {
        "v_nodes_dir": [],
        "unknown_future_key": "should_be_ignored",
        "another_future_list": [1, 2, 3],
    }
    try:
        env_manager.import_settings(payload)
    except Exception as exc:
        pytest.fail(f"import_settings() raised on unknown keys: {exc}")


def test_settings_file_round_trip(tmp_path):
    """export then import must exactly restore the original state."""
    d = str(tmp_path / "roundtrip_nodes")
    os.makedirs(d)
    env_manager.set_v_nodes_dir([d])
    env_manager.set_custom_variables({"RT_VAR": "roundtrip"})

    # Export to file
    exported = env_manager.export_settings()
    export_file = str(tmp_path / "settings.json")
    with open(export_file, "w") as f:
        json.dump(exported, f)

    # Wipe state
    env_manager.set_v_nodes_dir([])
    env_manager.set_custom_variables({})

    # Import from file
    with open(export_file) as f:
        imported = json.load(f)
    env_manager.import_settings(imported)

    assert config.get("env.v_nodes_dir") == [d]
    assert config.get("env.custom_variables") == {"RT_VAR": "roundtrip"}
