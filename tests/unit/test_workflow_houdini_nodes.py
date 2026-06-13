"""
Tests for Tier 10 Houdini MCP node JSON files (§30).
Validates file existence, required fields, port structure, and python_code integrity.
"""
import json
import os
import pytest

_PLUGIN_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..",
                 "plugins", "houdini", "v_nodes_houdini")
)

_TIER10_NODES = [
    "hou_mcp_workflow_pack",
    "hou_mcp_workflow_execute",
    "hou_mcp_workflow_review",
    "hou_mcp_workflow_recommend",
    "hou_mcp_workflow_statistics",
]

_FORBIDDEN_TOOLS = {
    "create_node", "set_parm", "set_parms", "run_python",
    "run_code", "delete_node", "raw_houdini_execute",
}


def _load_node(node_id: str) -> dict:
    path = os.path.join(_PLUGIN_DIR, f"{node_id}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", _TIER10_NODES)
def test_node_file_exists(node_id):
    path = os.path.join(_PLUGIN_DIR, f"{node_id}.json")
    assert os.path.isfile(path), f"Missing node file: {path}"


# ---------------------------------------------------------------------------
# Required JSON fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", _TIER10_NODES)
def test_required_fields(node_id):
    node = _load_node(node_id)
    for key in ("node_id", "name", "description", "category",
                "use_exec", "inputs", "outputs", "python_code"):
        assert key in node, f"{node_id}: missing field '{key}'"


# ---------------------------------------------------------------------------
# node_id matches filename
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", _TIER10_NODES)
def test_node_id_matches_filename(node_id):
    node = _load_node(node_id)
    assert node["node_id"] == node_id


# ---------------------------------------------------------------------------
# Category is Houdini
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", _TIER10_NODES)
def test_category_is_houdini(node_id):
    node = _load_node(node_id)
    assert node["category"] == "Houdini"


# ---------------------------------------------------------------------------
# use_exec is true
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", _TIER10_NODES)
def test_use_exec_true(node_id):
    node = _load_node(node_id)
    assert node["use_exec"] is True


# ---------------------------------------------------------------------------
# python_code __init__ must not manually add exec ports (super().__init__() does it)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", _TIER10_NODES)
def test_python_code_no_manual_exec_ports(node_id):
    node = _load_node(node_id)
    code = node["python_code"]
    # The python_code must NOT manually call add_input("exec_in") or add_output("exec_out")
    assert 'add_input("exec_in"' not in code, \
        f"{node_id}: python_code must not manually add exec_in (super().__init__() does it)"
    assert 'add_output("exec_out"' not in code, \
        f"{node_id}: python_code must not manually add exec_out (super().__init__() does it)"


# ---------------------------------------------------------------------------
# python_code compiles without error
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", _TIER10_NODES)
def test_python_code_compiles(node_id):
    node = _load_node(node_id)
    code = node["python_code"]
    try:
        compile(code, f"<{node_id}>", "exec")
    except SyntaxError as e:
        pytest.fail(f"{node_id}: SyntaxError in python_code: {e}")


# ---------------------------------------------------------------------------
# python_code defines register_node
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", _TIER10_NODES)
def test_register_node_defined(node_id):
    node = _load_node(node_id)
    assert "register_node" in node["python_code"], \
        f"{node_id}: python_code must define register_node()"


# ---------------------------------------------------------------------------
# python_code defines async execute
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", _TIER10_NODES)
def test_async_execute_defined(node_id):
    node = _load_node(node_id)
    assert "async def execute" in node["python_code"], \
        f"{node_id}: python_code must define 'async def execute'"


# ---------------------------------------------------------------------------
# exec_out returned in python_code
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", _TIER10_NODES)
def test_exec_out_returned(node_id):
    node = _load_node(node_id)
    assert "'exec_out'" in node["python_code"] or '"exec_out"' in node["python_code"], \
        f"{node_id}: python_code must return 'exec_out'"


# ---------------------------------------------------------------------------
# Forbidden direct bridge tool names not present
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", _TIER10_NODES)
def test_no_forbidden_tools(node_id):
    node = _load_node(node_id)
    code = node["python_code"]
    for tool in _FORBIDDEN_TOOLS:
        # Allow "create_node" as a string in op dicts, but not direct bridge calls
        if tool == "create_node":
            # Must not appear as bridge.create_node(
            assert f"bridge.{tool}(" not in code, \
                f"{node_id}: forbidden bridge tool '{tool}' found in python_code"
        else:
            assert f"bridge.{tool}(" not in code, \
                f"{node_id}: forbidden bridge tool '{tool}' found in python_code"


# ---------------------------------------------------------------------------
# Node-specific port assertions
# ---------------------------------------------------------------------------

def test_workflow_pack_has_pack_json_output():
    node = _load_node("hou_mcp_workflow_pack")
    out_names = {p["name"] for p in node["outputs"]}
    assert "pack_json" in out_names


def test_workflow_execute_has_status_output():
    node = _load_node("hou_mcp_workflow_execute")
    out_names = {p["name"] for p in node["outputs"]}
    assert "status" in out_names
    assert "transaction_id" in out_names


def test_workflow_review_has_grade_and_score():
    node = _load_node("hou_mcp_workflow_review")
    out_names = {p["name"] for p in node["outputs"]}
    assert "grade"            in out_names
    assert "overall_score"    in out_names
    assert "production_ready" in out_names


def test_workflow_recommend_has_recommended_pack():
    node = _load_node("hou_mcp_workflow_recommend")
    out_names = {p["name"] for p in node["outputs"]}
    assert "recommended_pack"    in out_names
    assert "confidence"          in out_names
    assert "matched_environment" in out_names


def test_workflow_statistics_has_success_rate():
    node = _load_node("hou_mcp_workflow_statistics")
    out_names = {p["name"] for p in node["outputs"]}
    assert "success_rate"     in out_names
    assert "total_executions" in out_names
    assert "average_score"    in out_names
