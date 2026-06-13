"""
Tests for Tier 6 Houdini node JSON files.
Validates schema, class registration, port presence, and Python code compileability.
No bridge, no LLM, no live Houdini.
"""
import importlib
import json
import os
import py_compile
import tempfile
import textwrap
import pytest

_PLUGIN_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "plugins", "houdini", "v_nodes_houdini",
)

_NODE_FILES = {
    "hou_mcp_scene_intent_extract":   "hou_mcp_scene_intent_extract.json",
    "hou_mcp_scene_intent_validate":  "hou_mcp_scene_intent_validate.json",
    "hou_mcp_scene_intent_enrich":    "hou_mcp_scene_intent_enrich.json",
    "hou_mcp_scene_intent_recommend": "hou_mcp_scene_intent_recommend.json",
}

_REQUIRED_TOP_KEYS = {"node_id", "name", "description", "category", "use_exec", "inputs", "outputs", "python_code"}


def _load_node(filename: str) -> dict:
    path = os.path.normpath(os.path.join(_PLUGIN_DIR, filename))
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.parametrize("node_id,filename", list(_NODE_FILES.items()))
def test_node_file_exists(node_id, filename):
    path = os.path.normpath(os.path.join(_PLUGIN_DIR, filename))
    assert os.path.isfile(path), f"Missing node file: {path}"


@pytest.mark.parametrize("node_id,filename", list(_NODE_FILES.items()))
def test_node_has_required_keys(node_id, filename):
    defn = _load_node(filename)
    missing = _REQUIRED_TOP_KEYS - defn.keys()
    assert not missing, f"{filename}: missing keys {missing}"


@pytest.mark.parametrize("node_id,filename", list(_NODE_FILES.items()))
def test_node_id_matches_filename(node_id, filename):
    defn = _load_node(filename)
    assert defn["node_id"] == node_id, (
        f"node_id {defn['node_id']!r} does not match expected {node_id!r}"
    )


@pytest.mark.parametrize("node_id,filename", list(_NODE_FILES.items()))
def test_node_category_is_houdini(node_id, filename):
    defn = _load_node(filename)
    assert defn["category"] == "Houdini", f"{node_id}: category should be 'Houdini'"


@pytest.mark.parametrize("node_id,filename", list(_NODE_FILES.items()))
def test_node_use_exec_is_true(node_id, filename):
    defn = _load_node(filename)
    assert defn["use_exec"] is True, f"{node_id}: use_exec must be True"


@pytest.mark.parametrize("node_id,filename", list(_NODE_FILES.items()))
def test_node_exec_ports_not_in_inputs_list(node_id, filename):
    """exec_in / exec_out are added by super().__init__() — must not appear in JSON arrays."""
    defn = _load_node(filename)
    exec_names = {"exec_in", "exec_out"}
    for port in defn.get("inputs", []):
        assert port["name"] not in exec_names, (
            f"{node_id}: exec_in/exec_out must not appear in inputs array"
        )
    for port in defn.get("outputs", []):
        assert port["name"] not in exec_names, (
            f"{node_id}: exec_in/exec_out must not appear in outputs array"
        )


@pytest.mark.parametrize("node_id,filename", list(_NODE_FILES.items()))
def test_node_has_at_least_one_input_and_output(node_id, filename):
    defn = _load_node(filename)
    assert len(defn["inputs"]) >= 1, f"{node_id}: must have at least one input"
    assert len(defn["outputs"]) >= 1, f"{node_id}: must have at least one output"


@pytest.mark.parametrize("node_id,filename", list(_NODE_FILES.items()))
def test_python_code_is_non_empty(node_id, filename):
    defn = _load_node(filename)
    assert defn["python_code"].strip(), f"{node_id}: python_code must not be empty"


@pytest.mark.parametrize("node_id,filename", list(_NODE_FILES.items()))
def test_python_code_compiles(node_id, filename):
    defn = _load_node(filename)
    code = defn["python_code"]
    try:
        compile(code, f"<{node_id}>", "exec")
    except SyntaxError as exc:
        pytest.fail(f"{node_id}: python_code has syntax error: {exc}")


@pytest.mark.parametrize("node_id,filename", list(_NODE_FILES.items()))
def test_python_code_has_register_node(node_id, filename):
    defn = _load_node(filename)
    assert "def register_node" in defn["python_code"], (
        f"{node_id}: python_code must define register_node()"
    )


@pytest.mark.parametrize("node_id,filename", list(_NODE_FILES.items()))
def test_python_code_has_async_execute(node_id, filename):
    defn = _load_node(filename)
    assert "async def execute" in defn["python_code"], (
        f"{node_id}: python_code must have async def execute()"
    )


@pytest.mark.parametrize("node_id,filename", list(_NODE_FILES.items()))
def test_python_code_returns_exec_out(node_id, filename):
    defn = _load_node(filename)
    assert '"exec_out": True' in defn["python_code"] or "'exec_out': True" in defn["python_code"], (
        f"{node_id}: python_code must return exec_out: True"
    )


# --- Extract node specific ---

def test_extract_node_has_scene_intent_json_output():
    defn = _load_node(_NODE_FILES["hou_mcp_scene_intent_extract"])
    output_names = [p["name"] for p in defn["outputs"]]
    assert "scene_intent_json" in output_names


def test_extract_node_has_prompt_input():
    defn = _load_node(_NODE_FILES["hou_mcp_scene_intent_extract"])
    input_names = [p["name"] for p in defn["inputs"]]
    assert "prompt" in input_names


# --- Validate node specific ---

def test_validate_node_has_valid_output():
    defn = _load_node(_NODE_FILES["hou_mcp_scene_intent_validate"])
    output_names = [p["name"] for p in defn["outputs"]]
    assert "valid" in output_names
    assert "normalized_intent_json" in output_names


# --- Enrich node specific ---

def test_enrich_node_has_enrichment_count_output():
    defn = _load_node(_NODE_FILES["hou_mcp_scene_intent_enrich"])
    output_names = [p["name"] for p in defn["outputs"]]
    assert "enrichment_count" in output_names
    assert "enriched_intent_json" in output_names


# --- Recommend node specific ---

def test_recommend_node_has_recommendations_json_output():
    defn = _load_node(_NODE_FILES["hou_mcp_scene_intent_recommend"])
    output_names = [p["name"] for p in defn["outputs"]]
    assert "recommendations_json" in output_names
    assert "top_recommendation" in output_names


def test_recommend_node_has_max_per_source_input():
    defn = _load_node(_NODE_FILES["hou_mcp_scene_intent_recommend"])
    input_names = [p["name"] for p in defn["inputs"]]
    assert "max_per_source" in input_names
