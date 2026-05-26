"""
Per-node validation tests for the Tier 1–4 MCP + Houdini-MCP nodes.

The 3 generic MCP client nodes live in `nodes/` (DCC-agnostic, bundled by
default). The Houdini-specific nodes live in `plugins/houdini/v_nodes_houdini/`
because they require the Houdini bridge and only make sense when the Houdini
plugin is installed (loaded into the registry via `v_nodes_dir` at startup).

Each node is validated as JSON → schema → registered class → instantiated
instance with the declared ports.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.models import NodeDefinitionJSON
from src.core.registry import NodeRegistry

_REPO = Path(__file__).parent.parent.parent
_NODES_DIR = _REPO / "nodes"
_HOU_PLUGIN_DIR = _REPO / "plugins" / "houdini" / "v_nodes_houdini"

# Map node_id → on-disk JSON file. The 3 generic MCP nodes ship in nodes/;
# the 2 hou_mcp_* nodes ship under the Houdini plugin.
_NODE_PATHS = {
    "mcp_server_init":                  _NODES_DIR / "mcp_server_init.json",
    "mcp_list_tools":                   _NODES_DIR / "mcp_list_tools.json",
    "mcp_call_tool":                    _NODES_DIR / "mcp_call_tool.json",
    "hou_mcp_scene_context":            _HOU_PLUGIN_DIR / "hou_mcp_scene_context.json",
    "hou_mcp_build_node_chain":         _HOU_PLUGIN_DIR / "hou_mcp_build_node_chain.json",
    "hou_mcp_graph_diff":               _HOU_PLUGIN_DIR / "hou_mcp_graph_diff.json",
    "hou_mcp_transaction":              _HOU_PLUGIN_DIR / "hou_mcp_transaction.json",
    "hou_mcp_execution_preview":        _HOU_PLUGIN_DIR / "hou_mcp_execution_preview.json",
    "hou_mcp_replay_transaction":       _HOU_PLUGIN_DIR / "hou_mcp_replay_transaction.json",
    "hou_mcp_semantic_execute":         _HOU_PLUGIN_DIR / "hou_mcp_semantic_execute.json",
    "hou_mcp_runtime_capabilities":     _HOU_PLUGIN_DIR / "hou_mcp_runtime_capabilities.json",
    "hou_mcp_workflow_templates":       _HOU_PLUGIN_DIR / "hou_mcp_workflow_templates.json",
    # Tier 3 — AI planning nodes
    "hou_mcp_ai_plan":                  _HOU_PLUGIN_DIR / "hou_mcp_ai_plan.json",
    "hou_mcp_ai_preview":               _HOU_PLUGIN_DIR / "hou_mcp_ai_preview.json",
    "hou_mcp_ai_execute":               _HOU_PLUGIN_DIR / "hou_mcp_ai_execute.json",
    "hou_mcp_ai_review":                _HOU_PLUGIN_DIR / "hou_mcp_ai_review.json",
    # Tier 4 — Distributed autonomous orchestration nodes
    "hou_mcp_runtime_federation":       _HOU_PLUGIN_DIR / "hou_mcp_runtime_federation.json",
    "hou_mcp_distributed_execute":      _HOU_PLUGIN_DIR / "hou_mcp_distributed_execute.json",
    "hou_mcp_agent_plan":               _HOU_PLUGIN_DIR / "hou_mcp_agent_plan.json",
    "hou_mcp_remote_worker":            _HOU_PLUGIN_DIR / "hou_mcp_remote_worker.json",
    "hou_mcp_knowledge_query":          _HOU_PLUGIN_DIR / "hou_mcp_knowledge_query.json",
    # Tier 5 — Adaptive procedural intelligence nodes
    "hou_mcp_runtime_analytics":        _HOU_PLUGIN_DIR / "hou_mcp_runtime_analytics.json",
    "hou_mcp_predictive_execution":     _HOU_PLUGIN_DIR / "hou_mcp_predictive_execution.json",
    "hou_mcp_workflow_optimizer":       _HOU_PLUGIN_DIR / "hou_mcp_workflow_optimizer.json",
    "hou_mcp_recommendation_engine":    _HOU_PLUGIN_DIR / "hou_mcp_recommendation_engine.json",
    "hou_mcp_execution_quality":        _HOU_PLUGIN_DIR / "hou_mcp_execution_quality.json",
}

_NODE_FILES = [p for p in _NODE_PATHS.values()]
_NODE_IDS = list(_NODE_PATHS.keys())

_EXPECTED_NODES = set(_NODE_PATHS.keys())


@pytest.fixture(scope="module", autouse=True)
def _ensure_registry():
    # Load bundled nodes/ first, then the Houdini plugin folder so the
    # hou_mcp_* nodes register too. Mirrors how MainWindow boots when the
    # Houdini plugin sets v_nodes_dir to v_nodes_houdini.
    NodeRegistry.load_all(str(_NODES_DIR))
    NodeRegistry._load_directory(str(_HOU_PLUGIN_DIR))


def test_expected_node_files_exist():
    missing = [nid for nid, p in _NODE_PATHS.items() if not p.is_file()]
    assert not missing, f"Missing Tier 1 node files on disk: {sorted(missing)}"


def test_generic_mcp_nodes_in_bundled_dir():
    """The 3 DCC-agnostic MCP client nodes must ship in nodes/, not in a plugin folder."""
    for nid in ("mcp_server_init", "mcp_list_tools", "mcp_call_tool"):
        assert _NODE_PATHS[nid].parent == _NODES_DIR, (
            f"{nid} should live in nodes/ (DCC-agnostic), found at {_NODE_PATHS[nid]}"
        )


def test_houdini_mcp_nodes_in_plugin_dir():
    """Houdini-specific AI nodes must ship under the Houdini plugin folder."""
    for nid in (
        "hou_mcp_scene_context",
        "hou_mcp_build_node_chain",
        "hou_mcp_graph_diff",
        "hou_mcp_transaction",
        "hou_mcp_execution_preview",
        "hou_mcp_replay_transaction",
        "hou_mcp_semantic_execute",
        "hou_mcp_runtime_capabilities",
        "hou_mcp_workflow_templates",
        "hou_mcp_ai_plan",
        "hou_mcp_ai_preview",
        "hou_mcp_ai_execute",
        "hou_mcp_ai_review",
        # Tier 4
        "hou_mcp_runtime_federation",
        "hou_mcp_distributed_execute",
        "hou_mcp_agent_plan",
        "hou_mcp_remote_worker",
        "hou_mcp_knowledge_query",
        # Tier 5
        "hou_mcp_runtime_analytics",
        "hou_mcp_predictive_execution",
        "hou_mcp_workflow_optimizer",
        "hou_mcp_recommendation_engine",
        "hou_mcp_execution_quality",
    ):
        assert _NODE_PATHS[nid].parent == _HOU_PLUGIN_DIR, (
            f"{nid} should live in plugins/houdini/v_nodes_houdini/ "
            f"(loaded via v_nodes_dir when the Houdini plugin is installed), "
            f"found at {_NODE_PATHS[nid]}"
        )


@pytest.mark.parametrize("path", _NODE_FILES, ids=_NODE_IDS)
def test_node_json_parses(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert data.get("node_id") == path.stem


@pytest.mark.parametrize("path", _NODE_FILES, ids=_NODE_IDS)
def test_node_schema_validates(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    defn = NodeDefinitionJSON.model_validate(data)
    assert defn.node_id == data["node_id"]
    assert defn.python_code, "python_code must not be empty"


@pytest.mark.parametrize("path", _NODE_FILES, ids=_NODE_IDS)
def test_node_class_registers(path):
    cls = NodeRegistry.get_class(path.stem)
    assert cls is not None, f"NodeRegistry has no class for {path.stem}; last_error={NodeRegistry.last_error}"


@pytest.mark.parametrize("path", _NODE_FILES, ids=_NODE_IDS)
def test_node_instantiates_with_declared_ports(path):
    with open(path, "r", encoding="utf-8") as f:
        defn = NodeDefinitionJSON.model_validate(json.load(f))

    cls = NodeRegistry.get_class(path.stem)
    inst = cls()

    declared_inputs = {p.name for p in defn.inputs} | {"exec_in"} if defn.use_exec else {p.name for p in defn.inputs}
    declared_outputs = {p.name for p in defn.outputs} | {"exec_out"} if defn.use_exec else {p.name for p in defn.outputs}

    actual_inputs = set(inst.inputs.keys())
    actual_outputs = set(inst.outputs.keys())

    missing_in = declared_inputs - actual_inputs
    missing_out = declared_outputs - actual_outputs
    assert not missing_in, f"{path.stem} missing input ports: {missing_in}"
    assert not missing_out, f"{path.stem} missing output ports: {missing_out}"


@pytest.mark.parametrize("path", _NODE_FILES, ids=_NODE_IDS)
def test_node_category_correct(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data["node_id"].startswith("mcp_"):
        assert data["category"] == "MCP", f"{data['node_id']} must use category 'MCP'"
    elif data["node_id"].startswith("hou_mcp_") or data["node_id"].startswith("hou_mcp_"):
        assert data["category"] == "Houdini", f"{data['node_id']} must use category 'Houdini'"
