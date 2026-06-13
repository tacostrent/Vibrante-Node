"""Tests for Tier 11 Houdini MCP nodes (§31).

Verifies JSON structure, python_code compiles, register_node defined,
exec_in/exec_out conventions, no forbidden bridge tools.
"""
import json
import os
import pytest

_PLUGIN_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "plugins", "houdini", "v_nodes_houdini"
)

_NODE_FILES = {
    "hou_mcp_studio_knowledge":        "hou_mcp_studio_knowledge.json",
    "hou_mcp_cross_project_learning":  "hou_mcp_cross_project_learning.json",
    "hou_mcp_review_analytics":        "hou_mcp_review_analytics.json",
    "hou_mcp_studio_standards":        "hou_mcp_studio_standards.json",
    "hou_mcp_production_benchmark":    "hou_mcp_production_benchmark.json",
    "hou_mcp_knowledge_recommendation":"hou_mcp_knowledge_recommendation.json",
}

_FORBIDDEN_TOOLS = frozenset({
    "create_node", "set_parm", "set_parms", "run_python",
    "run_code", "delete_node", "connect_nodes", "cook_node",
    "raw_houdini_execute",
})

_REQUIRED_FIELDS = frozenset({"node_id", "name", "description", "category",
                               "use_exec", "inputs", "outputs", "python_code"})


def _load(filename: str) -> dict:
    path = os.path.join(_PLUGIN_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("node_id,filename", _NODE_FILES.items())
def test_file_exists(node_id, filename):
    path = os.path.join(_PLUGIN_DIR, filename)
    assert os.path.exists(path), f"Node file not found: {path}"


@pytest.mark.parametrize("node_id,filename", _NODE_FILES.items())
def test_required_fields(node_id, filename):
    data = _load(filename)
    for field in _REQUIRED_FIELDS:
        assert field in data, f"Missing field {field!r} in {filename}"


@pytest.mark.parametrize("node_id,filename", _NODE_FILES.items())
def test_node_id_matches_filename(node_id, filename):
    data = _load(filename)
    assert data["node_id"] == node_id, (
        f"node_id {data['node_id']!r} does not match expected {node_id!r}"
    )


@pytest.mark.parametrize("node_id,filename", _NODE_FILES.items())
def test_category_is_houdini(node_id, filename):
    data = _load(filename)
    assert data["category"] == "Houdini"


@pytest.mark.parametrize("node_id,filename", _NODE_FILES.items())
def test_use_exec_true(node_id, filename):
    data = _load(filename)
    assert data["use_exec"] is True


@pytest.mark.parametrize("node_id,filename", _NODE_FILES.items())
def test_exec_ports_not_in_json_arrays(node_id, filename):
    """exec_in and exec_out must appear in inputs/outputs JSON arrays
    (they're required by use_exec=True), but the python_code must NOT
    manually call add_input('exec_in') — that's done by super().__init__().
    Here we just confirm exec ports ARE listed in the JSON definition."""
    data = _load(filename)
    input_names = [p["name"] for p in data["inputs"]]
    output_names = [p["name"] for p in data["outputs"]]
    assert "exec_in" in input_names, f"exec_in missing from inputs in {filename}"
    assert "exec_out" in output_names, f"exec_out missing from outputs in {filename}"


@pytest.mark.parametrize("node_id,filename", _NODE_FILES.items())
def test_python_code_compiles(node_id, filename):
    data = _load(filename)
    code = data["python_code"]
    try:
        compile(code, f"<{filename}>", "exec")
    except SyntaxError as e:
        pytest.fail(f"SyntaxError in {filename}: {e}")


@pytest.mark.parametrize("node_id,filename", _NODE_FILES.items())
def test_register_node_defined(node_id, filename):
    data = _load(filename)
    assert "register_node" in data["python_code"], f"register_node missing in {filename}"


@pytest.mark.parametrize("node_id,filename", _NODE_FILES.items())
def test_async_execute_defined(node_id, filename):
    data = _load(filename)
    assert "async def execute" in data["python_code"], f"async execute missing in {filename}"


@pytest.mark.parametrize("node_id,filename", _NODE_FILES.items())
def test_exec_out_returned(node_id, filename):
    data = _load(filename)
    assert "'exec_out'" in data["python_code"] or '"exec_out"' in data["python_code"], (
        f"exec_out not returned in {filename}"
    )


@pytest.mark.parametrize("node_id,filename", _NODE_FILES.items())
def test_no_forbidden_tools(node_id, filename):
    data = _load(filename)
    code = data["python_code"]
    for forbidden in _FORBIDDEN_TOOLS:
        assert f"bridge.{forbidden}" not in code, (
            f"Forbidden bridge call {forbidden!r} found in {filename}"
        )


@pytest.mark.parametrize("node_id,filename", _NODE_FILES.items())
def test_no_get_bridge_import(node_id, filename):
    data = _load(filename)
    code = data["python_code"]
    # These nodes are advisory — no bridge mutations allowed
    assert "get_bridge" not in code, (
        f"get_bridge found in Tier 11 advisory node {filename}"
    )


# ---------------------------------------------------------------------------
# Node-specific port assertions
# ---------------------------------------------------------------------------

def test_studio_knowledge_has_success_rate_output():
    data = _load(_NODE_FILES["hou_mcp_studio_knowledge"])
    output_names = [p["name"] for p in data["outputs"]]
    assert "success_rate" in output_names
    assert "success_count" in output_names
    assert "failure_count" in output_names


def test_cross_project_learning_has_best_fields():
    data = _load(_NODE_FILES["hou_mcp_cross_project_learning"])
    output_names = [p["name"] for p in data["outputs"]]
    assert "best_workflow" in output_names
    assert "best_lighting" in output_names
    assert "best_camera" in output_names
    assert "best_atmosphere" in output_names


def test_production_benchmark_has_performance_output():
    data = _load(_NODE_FILES["hou_mcp_production_benchmark"])
    output_names = [p["name"] for p in data["outputs"]]
    assert "performance" in output_names
    assert "studio_average" in output_names
    assert "difference" in output_names


def test_knowledge_recommendation_has_all_strategy_outputs():
    data = _load(_NODE_FILES["hou_mcp_knowledge_recommendation"])
    output_names = [p["name"] for p in data["outputs"]]
    assert "recommended_workflow" in output_names
    assert "recommended_lighting" in output_names
    assert "recommended_camera" in output_names
    assert "recommended_atmosphere" in output_names
    assert "overall_confidence" in output_names
    assert "production_ready" in output_names


def test_studio_standards_has_is_approved_output():
    data = _load(_NODE_FILES["hou_mcp_studio_standards"])
    output_names = [p["name"] for p in data["outputs"]]
    assert "is_approved" in output_names
    assert "ok" in output_names


def test_review_analytics_has_trend_output():
    data = _load(_NODE_FILES["hou_mcp_review_analytics"])
    output_names = [p["name"] for p in data["outputs"]]
    assert "trend_direction" in output_names
    assert "pass_rate" in output_names
