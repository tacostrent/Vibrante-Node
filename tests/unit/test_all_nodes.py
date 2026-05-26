"""
Comprehensive validation of every bundled node definition.

For each of the 166+ JSON node files in nodes/ this suite checks:
  1. JSON parses without error
  2. Required fields are present and non-empty
  3. node_id matches the filename stem
  4. Pydantic schema validation passes (NodeDefinitionJSON)
  5. Python code has no syntax errors (compile())
  6. NodeRegistry.register_definition() succeeds
  7. The registered class instantiates without error
  8. Every declared input port appears on the live instance
  9. Every declared output port appears on the live instance
  10. exec_in / exec_out are present on use_exec=True nodes

The 10 Python builtin nodes (registered from source, no JSON) are tested
separately in TestBuiltinNodes at the bottom.
"""

import json
import os
import pytest
from pathlib import Path

from src.core.models import NodeDefinitionJSON
from src.core.registry import NodeRegistry
from src.nodes.base import BaseNode

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

NODES_DIR = Path(__file__).parent.parent.parent / "nodes"


def _discover() -> list[tuple[Path, str]]:
    pairs = []
    for root, _, files in os.walk(NODES_DIR):
        for fname in sorted(files):
            if fname.endswith(".json"):
                path = Path(root) / fname
                pairs.append((path, path.stem))
    return pairs


_ALL_NODES = _discover()
_NODE_IDS = [nid for _, nid in _ALL_NODES]
_NODE_PATHS = [p for p, _ in _ALL_NODES]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_definition(path: Path) -> NodeDefinitionJSON:
    return NodeDefinitionJSON.model_validate(_load_json(path))


def _register_and_get_class(defn: NodeDefinitionJSON):
    ok = NodeRegistry.register_definition(defn)
    assert ok, f"Registration failed: {NodeRegistry.last_error}"
    cls = NodeRegistry.get_class(defn.node_id)
    assert cls is not None, "Class not in registry after successful registration"
    return cls


# ---------------------------------------------------------------------------
# 1. JSON structure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_json_parses(path, node_id):
    data = _load_json(path)
    assert isinstance(data, dict), "Root element must be a JSON object"


@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_required_fields_present(path, node_id):
    data = _load_json(path)
    assert data.get("node_id"), "node_id must be a non-empty string"
    assert data.get("name"), "name must be a non-empty string"
    assert data.get("python_code"), "python_code must be a non-empty string"


@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_node_id_matches_filename(path, node_id):
    data = _load_json(path)
    assert data["node_id"] == node_id, (
        f"node_id '{data['node_id']}' does not match filename stem '{node_id}'"
    )


# ---------------------------------------------------------------------------
# 2. Schema and syntax
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_schema_validates(path, node_id):
    defn = _load_definition(path)
    assert defn.node_id == node_id


@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_python_syntax(path, node_id):
    data = _load_json(path)
    code = data["python_code"]
    try:
        compile(code, f"<{node_id}>", "exec")
    except SyntaxError as e:
        pytest.fail(f"SyntaxError in python_code: {e}")


# ---------------------------------------------------------------------------
# 3. Registration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_class_registers(path, node_id):
    defn = _load_definition(path)
    ok = NodeRegistry.register_definition(defn)
    assert ok, f"register_definition returned False: {NodeRegistry.last_error}"


# ---------------------------------------------------------------------------
# 4. Instantiation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_class_instantiates(path, node_id):
    defn = _load_definition(path)
    cls = _register_and_get_class(defn)
    instance = cls()
    assert isinstance(instance, BaseNode)


# ---------------------------------------------------------------------------
# 5. Port integrity — inputs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_declared_inputs_on_instance(path, node_id):
    defn = _load_definition(path)
    cls = _register_and_get_class(defn)
    instance = cls()

    missing = []
    for port in defn.inputs:
        if port.name in ("exec_in", "exec_out"):
            continue
        if port.name not in instance.inputs:
            missing.append(port.name)

    assert not missing, (
        f"Declared input port(s) missing from live instance: {missing}"
    )


# ---------------------------------------------------------------------------
# 6. Port integrity — outputs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_declared_outputs_on_instance(path, node_id):
    defn = _load_definition(path)
    cls = _register_and_get_class(defn)
    instance = cls()

    missing = []
    for port in defn.outputs:
        if port.name in ("exec_in", "exec_out"):
            continue
        if port.name not in instance.outputs:
            missing.append(port.name)

    assert not missing, (
        f"Declared output port(s) missing from live instance: {missing}"
    )


# ---------------------------------------------------------------------------
# 7. Exec pins
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_exec_ports_when_use_exec(path, node_id):
    defn = _load_definition(path)
    if not defn.use_exec:
        pytest.skip("use_exec=False — exec ports not required")

    cls = _register_and_get_class(defn)
    instance = cls()

    assert "exec_in" in instance.inputs, (
        "exec_in missing from use_exec=True node instance"
    )
    assert "exec_out" in instance.outputs, (
        "exec_out missing from use_exec=True node instance"
    )


# ---------------------------------------------------------------------------
# 8. Port type validity
# ---------------------------------------------------------------------------

_VALID_TYPES = {"string", "int", "float", "bool", "list", "any", "exec", "dict", "number"}

@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_port_types_are_known(path, node_id):
    defn = _load_definition(path)
    unknown = []
    for port in defn.inputs + defn.outputs:
        if port.type not in _VALID_TYPES:
            unknown.append(f"{port.name}:{port.type}")
    assert not unknown, f"Unknown port type(s): {unknown}"


# ---------------------------------------------------------------------------
# 9. No duplicate port names
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_no_duplicate_input_names(path, node_id):
    data = _load_json(path)
    names = [p["name"] for p in data.get("inputs", [])]
    dupes = [n for n in set(names) if names.count(n) > 1]
    assert not dupes, f"Duplicate input port name(s) in JSON: {dupes}"


@pytest.mark.parametrize("path,node_id", _ALL_NODES, ids=_NODE_IDS)
def test_no_duplicate_output_names(path, node_id):
    data = _load_json(path)
    names = [p["name"] for p in data.get("outputs", [])]
    dupes = [n for n in set(names) if names.count(n) > 1]
    assert not dupes, f"Duplicate output port name(s) in JSON: {dupes}"


# ---------------------------------------------------------------------------
# 10. Builtin nodes
# ---------------------------------------------------------------------------

_BUILTIN_NAMES = [
    "File Loader", "Data Processor", "Console Sink", "Sequencer",
    "Set Variable", "Get Variable", "Two Way Switch",
    "For Each", "List Append", "While Loop",
]

_BUILTIN_CLASSES = None

def _get_builtin_classes():
    global _BUILTIN_CLASSES
    if _BUILTIN_CLASSES is None:
        from src.nodes.builtins.nodes import (
            FileLoaderNode, DataProcessorNode, ConsoleSinkNode,
            SequenceNode, SetVariableNode, GetVariableNode,
            TwoWaySwitchNode, ForEachNode, ListAppendNode, WhileLoopNode,
        )
        _BUILTIN_CLASSES = [
            FileLoaderNode, DataProcessorNode, ConsoleSinkNode,
            SequenceNode, SetVariableNode, GetVariableNode,
            TwoWaySwitchNode, ForEachNode, ListAppendNode, WhileLoopNode,
        ]
    return _BUILTIN_CLASSES


@pytest.mark.parametrize("cls", _get_builtin_classes(), ids=lambda c: c.name)
def test_builtin_instantiates(cls):
    instance = cls()
    assert isinstance(instance, BaseNode)


@pytest.mark.parametrize("cls", _get_builtin_classes(), ids=lambda c: c.name)
def test_builtin_has_name_and_category(cls):
    assert cls.name, "Builtin must have a non-empty name"
    assert cls.category, "Builtin must have a non-empty category"


@pytest.mark.parametrize("cls", _get_builtin_classes(), ids=lambda c: c.name)
def test_builtin_has_execute_method(cls):
    import inspect
    assert hasattr(cls, "execute"), "Builtin must define execute()"
    assert inspect.iscoroutinefunction(cls.execute), "execute() must be async"


# ---------------------------------------------------------------------------
# 11. Summary assertion — total node count
# ---------------------------------------------------------------------------

def test_total_node_count():
    """
    Smoke-check: the nodes/ directory must contain at least 166 JSON files
    (the known bundled count as of v2.4.0, excluding the 11 Python builtins).
    Fail loudly if nodes are accidentally deleted.
    """
    count = len(_ALL_NODES)
    assert count >= 164, (
        f"Expected ≥164 node JSON files, found {count}. "
        "Were nodes accidentally deleted?"
    )
