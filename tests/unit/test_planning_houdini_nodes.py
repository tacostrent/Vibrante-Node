"""
Tests for Tier 7 Houdini nodes (hou_mcp_scene_plan_*).

Verifies:
 - All 4 node JSON files exist
 - Required JSON keys present
 - node_id matches filename
 - category == "Houdini"
 - use_exec == True
 - exec ports NOT listed in inputs/outputs JSON arrays
 - python_code compiles without error
 - register_node() present
 - async execute() present and returns exec_out
 - no FORBIDDEN_TOOLS names registered

Node locations: plugins/houdini/v_nodes_houdini/
"""

import ast
import json
import os
import types
import importlib.util
import sys
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_PLUGIN_DIR = os.path.join(_ROOT, "plugins", "houdini", "v_nodes_houdini")

_NODE_PATHS = {
    "hou_mcp_scene_plan_create":           os.path.join(_PLUGIN_DIR, "hou_mcp_scene_plan_create.json"),
    "hou_mcp_scene_plan_validate":         os.path.join(_PLUGIN_DIR, "hou_mcp_scene_plan_validate.json"),
    "hou_mcp_scene_plan_recommend":        os.path.join(_PLUGIN_DIR, "hou_mcp_scene_plan_recommend.json"),
    "hou_mcp_scene_asset_query_generate":  os.path.join(_PLUGIN_DIR, "hou_mcp_scene_asset_query_generate.json"),
}

_REQUIRED_FIELDS = {"node_id", "name", "description", "category", "icon_path",
                    "use_exec", "inputs", "outputs", "python_code"}

_EXEC_NAMES = {"exec_in", "exec_out"}

FORBIDDEN_TOOLS = {
    "create_node", "set_parm", "set_parms", "run_python",
    "run_code", "delete_node", "raw_houdini_execute",
    "connect_nodes", "cook_node",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_node(node_id: str):
    path = _NODE_PATHS[node_id]
    assert os.path.isfile(path), f"Node file missing: {path}"
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------

class TestNodeFilesExist:
    @pytest.mark.parametrize("node_id", list(_NODE_PATHS.keys()))
    def test_file_exists(self, node_id):
        assert os.path.isfile(_NODE_PATHS[node_id]), f"Missing: {_NODE_PATHS[node_id]}"


class TestNodeStructure:
    @pytest.mark.parametrize("node_id", list(_NODE_PATHS.keys()))
    def test_required_fields_present(self, node_id):
        data = _load_node(node_id)
        for field in _REQUIRED_FIELDS:
            assert field in data, f"{node_id}: missing {field!r}"

    @pytest.mark.parametrize("node_id", list(_NODE_PATHS.keys()))
    def test_node_id_matches_filename(self, node_id):
        data = _load_node(node_id)
        assert data["node_id"] == node_id

    @pytest.mark.parametrize("node_id", list(_NODE_PATHS.keys()))
    def test_category_is_houdini(self, node_id):
        data = _load_node(node_id)
        assert data["category"] == "Houdini"

    @pytest.mark.parametrize("node_id", list(_NODE_PATHS.keys()))
    def test_use_exec_true(self, node_id):
        data = _load_node(node_id)
        assert data["use_exec"] is True

    @pytest.mark.parametrize("node_id", list(_NODE_PATHS.keys()))
    def test_exec_ports_not_in_json_arrays(self, node_id):
        data = _load_node(node_id)
        for port in data.get("inputs", []):
            assert port["name"] not in _EXEC_NAMES, \
                f"{node_id}: exec port {port['name']!r} in inputs array"
        for port in data.get("outputs", []):
            assert port["name"] not in _EXEC_NAMES, \
                f"{node_id}: exec port {port['name']!r} in outputs array"


# ---------------------------------------------------------------------------
# Python code tests
# ---------------------------------------------------------------------------

class TestNodePythonCode:
    @pytest.mark.parametrize("node_id", list(_NODE_PATHS.keys()))
    def test_python_code_compiles(self, node_id):
        data = _load_node(node_id)
        code = data["python_code"]
        try:
            compile(code, f"<{node_id}>", "exec")
        except SyntaxError as exc:
            pytest.fail(f"{node_id}: syntax error in python_code — {exc}")

    @pytest.mark.parametrize("node_id", list(_NODE_PATHS.keys()))
    def test_register_node_function_present(self, node_id):
        data = _load_node(node_id)
        code = data["python_code"]
        assert "def register_node" in code or "register_node" in code

    @pytest.mark.parametrize("node_id", list(_NODE_PATHS.keys()))
    def test_async_execute_present(self, node_id):
        data = _load_node(node_id)
        code = data["python_code"]
        assert "async def execute" in code

    @pytest.mark.parametrize("node_id", list(_NODE_PATHS.keys()))
    def test_exec_out_returned(self, node_id):
        data = _load_node(node_id)
        code = data["python_code"]
        assert '"exec_out"' in code or "'exec_out'" in code

    @pytest.mark.parametrize("node_id", list(_NODE_PATHS.keys()))
    def test_no_forbidden_tools(self, node_id):
        data = _load_node(node_id)
        code = data["python_code"]
        for forbidden in FORBIDDEN_TOOLS:
            assert f'"{forbidden}"' not in code and f"'{forbidden}'" not in code, \
                f"{node_id}: found forbidden tool reference {forbidden!r}"


# ---------------------------------------------------------------------------
# Port-specific tests
# ---------------------------------------------------------------------------

class TestNodePorts:
    def test_create_node_has_scene_intent_json_input(self):
        data = _load_node("hou_mcp_scene_plan_create")
        input_names = [p["name"] for p in data["inputs"]]
        assert "scene_intent_json" in input_names

    def test_create_node_has_scene_plan_json_output(self):
        data = _load_node("hou_mcp_scene_plan_create")
        output_names = [p["name"] for p in data["outputs"]]
        assert "scene_plan_json" in output_names

    def test_validate_node_has_valid_output(self):
        data = _load_node("hou_mcp_scene_plan_validate")
        output_names = [p["name"] for p in data["outputs"]]
        assert "valid" in output_names

    def test_validate_node_has_errors_json_output(self):
        data = _load_node("hou_mcp_scene_plan_validate")
        output_names = [p["name"] for p in data["outputs"]]
        assert "errors_json" in output_names

    def test_recommend_node_has_enriched_plan_output(self):
        data = _load_node("hou_mcp_scene_plan_recommend")
        output_names = [p["name"] for p in data["outputs"]]
        assert "enriched_plan_json" in output_names

    def test_recommend_node_has_max_per_source_input(self):
        data = _load_node("hou_mcp_scene_plan_recommend")
        input_names = [p["name"] for p in data["inputs"]]
        assert "max_per_source" in input_names

    def test_asset_query_node_has_queries_json_output(self):
        data = _load_node("hou_mcp_scene_asset_query_generate")
        output_names = [p["name"] for p in data["outputs"]]
        assert "queries_json" in output_names

    def test_asset_query_node_has_zone_filter_input(self):
        data = _load_node("hou_mcp_scene_asset_query_generate")
        input_names = [p["name"] for p in data["inputs"]]
        assert "zone_filter" in input_names

    def test_asset_query_node_has_required_only_input(self):
        data = _load_node("hou_mcp_scene_asset_query_generate")
        input_names = [p["name"] for p in data["inputs"]]
        assert "required_only" in input_names
