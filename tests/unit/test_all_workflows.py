"""
Comprehensive validation of every workflow and node-example file.

Workflow files (nodes / connections / sticky_notes / backdrops / metadata):
  workflows/        — 24 general-purpose workflows
  vfx_workflows/    — 6 production VFX pipeline workflows

For each workflow:
  1.  JSON parses without error
  2.  Not encoded with a non-UTF-8 byte order mark or corrupt bytes
  3.  Pydantic WorkflowModel schema validation passes
  4.  At least 1 node present
  5.  No duplicate instance_ids within the workflow
  6.  Every connection's from_node / to_node references an existing instance_id
  7.  Every node_id in the workflow is registered in NodeRegistry
  8.  Every connection's from_port / to_port exists on the live node instance
  9.  Node positions are valid 2-element numeric tuples
  10. No self-connections (from_node == to_node on the same port)

Node example files (node_id / python_code / inputs / outputs):
  node_examples/    — 15 installable reference node definitions
  website_examples/ — 10 curated showcase node definitions

For each node example:
  1.  JSON parses without error
  2.  Required fields present (node_id, name, python_code)
  3.  Pydantic NodeDefinitionJSON schema validation passes
  4.  Python code has no syntax errors
  5.  NodeRegistry.register_definition() succeeds
  6.  Class instantiates without error
  7.  All declared input ports appear on the live instance
  8.  All declared output ports appear on the live instance
"""

import json
import os
import uuid
import pytest
from pathlib import Path

from src.core.models import NodeDefinitionJSON, WorkflowModel
from src.core.registry import NodeRegistry
from src.nodes.base import BaseNode

# ---------------------------------------------------------------------------
# Registry bootstrap — load all bundled nodes once for the whole module
# ---------------------------------------------------------------------------

_REGISTRY_LOADED = False


def _discover_plugin_node_dirs() -> list[Path]:
    """Auto-discover every plugin node folder under plugins/.

    Convention: any directory matching `plugins/*/v_nodes_*` is treated as a
    plugin-scoped node folder loaded at runtime via the `v_nodes_dir` env var.
    Adding a new DCC plugin (e.g. plugins/maya/v_nodes_maya/) requires zero
    test changes — discovery is purely path-pattern driven, never hardcoded.
    """
    repo = Path(__file__).parent.parent.parent
    plugins_root = repo / "plugins"
    if not plugins_root.is_dir():
        return []
    found: list[Path] = []
    for plugin_dir in sorted(plugins_root.iterdir()):
        if not plugin_dir.is_dir():
            continue
        for child in sorted(plugin_dir.iterdir()):
            if child.is_dir() and child.name.startswith("v_nodes_"):
                found.append(child)
    return found


def _ensure_registry():
    global _REGISTRY_LOADED
    if not _REGISTRY_LOADED:
        repo = Path(__file__).parent.parent.parent
        NodeRegistry.load_all(str(repo / "nodes"))
        # Mirror the runtime environment when launched from a DCC plugin:
        # those folders are added to v_nodes_dir, so any workflow referencing
        # DCC-specific nodes (e.g. hou_mcp_*) must validate against them.
        # Discovery is path-agnostic — see _discover_plugin_node_dirs.
        for d in _discover_plugin_node_dirs():
            NodeRegistry._load_directory(str(d))
        _REGISTRY_LOADED = True


# ---------------------------------------------------------------------------
# Workflow discovery
# ---------------------------------------------------------------------------

_REPO = Path(__file__).parent.parent.parent

_WORKFLOW_DIRS = [
    _REPO / "workflows",
    _REPO / "vfx_workflows",
]

_NODE_EXAMPLE_DIRS = [
    _REPO / "node_examples",
    _REPO / "website_examples",
]


def _discover_workflows() -> list[tuple[Path, str]]:
    pairs = []
    for d in _WORKFLOW_DIRS:
        if not d.exists():
            continue
        for fname in sorted(os.listdir(d)):
            if fname.endswith(".json"):
                label = f"{d.name}/{fname[:-5]}"
                pairs.append((d / fname, label))
    return pairs


def _discover_node_examples() -> list[tuple[Path, str]]:
    pairs = []
    for d in _NODE_EXAMPLE_DIRS:
        if not d.exists():
            continue
        for fname in sorted(os.listdir(d)):
            if fname.endswith(".json"):
                label = f"{d.name}/{fname[:-5]}"
                pairs.append((d / fname, label))
    return pairs


_ALL_WORKFLOWS = _discover_workflows()
_WF_LABELS = [label for _, label in _ALL_WORKFLOWS]
_WF_PATHS = [p for p, _ in _ALL_WORKFLOWS]

_ALL_NODE_EXAMPLES = _discover_node_examples()
_NE_LABELS = [label for _, label in _ALL_NODE_EXAMPLES]
_NE_PATHS = [p for p, _ in _ALL_NODE_EXAMPLES]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_workflow(path: Path) -> WorkflowModel:
    return WorkflowModel.model_validate(_load_json(path))


# ---------------------------------------------------------------------------
# ── WORKFLOW TESTS ──────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,label", _ALL_WORKFLOWS, ids=_WF_LABELS)
def test_wf_json_parses(path, label):
    data = _load_json(path)
    assert isinstance(data, dict)


@pytest.mark.parametrize("path,label", _ALL_WORKFLOWS, ids=_WF_LABELS)
def test_wf_schema_validates(path, label):
    wf = _load_workflow(path)
    assert isinstance(wf, WorkflowModel)


@pytest.mark.parametrize("path,label", _ALL_WORKFLOWS, ids=_WF_LABELS)
def test_wf_has_at_least_one_node(path, label):
    wf = _load_workflow(path)
    assert len(wf.nodes) >= 1, "Workflow contains no nodes"


@pytest.mark.parametrize("path,label", _ALL_WORKFLOWS, ids=_WF_LABELS)
def test_wf_no_duplicate_instance_ids(path, label):
    wf = _load_workflow(path)
    ids = [str(n.instance_id) for n in wf.nodes]
    dupes = [i for i in set(ids) if ids.count(i) > 1]
    assert not dupes, f"Duplicate instance_id(s): {dupes}"


@pytest.mark.parametrize("path,label", _ALL_WORKFLOWS, ids=_WF_LABELS)
def test_wf_connections_reference_valid_nodes(path, label):
    wf = _load_workflow(path)
    instance_ids = {str(n.instance_id) for n in wf.nodes}
    bad = []
    for conn in wf.connections:
        fn, tn = str(conn.from_node), str(conn.to_node)
        if fn not in instance_ids:
            bad.append(f"from_node {fn} not in workflow nodes")
        if tn not in instance_ids:
            bad.append(f"to_node {tn} not in workflow nodes")
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("path,label", _ALL_WORKFLOWS, ids=_WF_LABELS)
def test_wf_node_ids_are_registered(path, label):
    _ensure_registry()
    wf = _load_workflow(path)
    unknown = []
    for node in wf.nodes:
        if NodeRegistry.get_class(node.node_id) is None:
            unknown.append(node.node_id)
    assert not unknown, f"Unregistered node_id(s) used in workflow: {sorted(set(unknown))}"


@pytest.mark.parametrize("path,label", _ALL_WORKFLOWS, ids=_WF_LABELS)
def test_wf_connection_ports_exist_on_instances(path, label):
    _ensure_registry()
    wf = _load_workflow(path)

    # Build instance_id -> live node instance map
    id_to_instance: dict[str, BaseNode] = {}
    for node in wf.nodes:
        cls = NodeRegistry.get_class(node.node_id)
        if cls is None:
            continue
        try:
            inst = cls()
            if node.parameters:
                inst.restore_from_parameters(node.parameters)
        except Exception:
            continue
        id_to_instance[str(node.instance_id)] = inst

    bad = []
    for conn in wf.connections:
        fn, tn = str(conn.from_node), str(conn.to_node)
        src = id_to_instance.get(fn)
        dst = id_to_instance.get(tn)

        if src is not None and conn.from_port not in src.outputs:
            bad.append(
                f"Port '{conn.from_port}' not in outputs of "
                f"{wf.nodes[next(i for i,n in enumerate(wf.nodes) if str(n.instance_id)==fn)].node_id}"
            )
        if dst is not None and conn.to_port not in dst.inputs:
            bad.append(
                f"Port '{conn.to_port}' not in inputs of "
                f"{wf.nodes[next(i for i,n in enumerate(wf.nodes) if str(n.instance_id)==tn)].node_id}"
            )

    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("path,label", _ALL_WORKFLOWS, ids=_WF_LABELS)
def test_wf_node_positions_are_valid(path, label):
    wf = _load_workflow(path)
    bad = []
    for node in wf.nodes:
        pos = node.position
        if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
            bad.append(f"{node.node_id} ({node.instance_id}): position is not a 2-element sequence: {pos!r}")
            continue
        if not all(isinstance(v, (int, float)) for v in pos):
            bad.append(f"{node.node_id}: position values are not numeric: {pos!r}")
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("path,label", _ALL_WORKFLOWS, ids=_WF_LABELS)
def test_wf_no_self_connections(path, label):
    wf = _load_workflow(path)
    bad = [
        f"{conn.from_node}.{conn.from_port} -> {conn.to_port} (self-loop)"
        for conn in wf.connections
        if str(conn.from_node) == str(conn.to_node)
    ]
    assert not bad, f"Self-connection(s) found: {bad}"


# ---------------------------------------------------------------------------
# ── NODE EXAMPLE TESTS ──────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,label", _ALL_NODE_EXAMPLES, ids=_NE_LABELS)
def test_ne_json_parses(path, label):
    data = _load_json(path)
    assert isinstance(data, dict)


@pytest.mark.parametrize("path,label", _ALL_NODE_EXAMPLES, ids=_NE_LABELS)
def test_ne_required_fields(path, label):
    data = _load_json(path)
    assert data.get("node_id"), "node_id must be non-empty"
    assert data.get("name"), "name must be non-empty"
    assert data.get("python_code"), "python_code must be non-empty"


@pytest.mark.parametrize("path,label", _ALL_NODE_EXAMPLES, ids=_NE_LABELS)
def test_ne_schema_validates(path, label):
    defn = NodeDefinitionJSON.model_validate(_load_json(path))
    assert defn.node_id


@pytest.mark.parametrize("path,label", _ALL_NODE_EXAMPLES, ids=_NE_LABELS)
def test_ne_python_syntax(path, label):
    data = _load_json(path)
    try:
        compile(data["python_code"], f"<{label}>", "exec")
    except SyntaxError as e:
        pytest.fail(f"SyntaxError: {e}")


@pytest.mark.parametrize("path,label", _ALL_NODE_EXAMPLES, ids=_NE_LABELS)
def test_ne_class_registers(path, label):
    defn = NodeDefinitionJSON.model_validate(_load_json(path))
    ok = NodeRegistry.register_definition(defn)
    assert ok, f"Registration failed: {NodeRegistry.last_error}"


@pytest.mark.parametrize("path,label", _ALL_NODE_EXAMPLES, ids=_NE_LABELS)
def test_ne_class_instantiates(path, label):
    defn = NodeDefinitionJSON.model_validate(_load_json(path))
    NodeRegistry.register_definition(defn)
    cls = NodeRegistry.get_class(defn.node_id)
    assert cls is not None
    instance = cls()
    assert isinstance(instance, BaseNode)


@pytest.mark.parametrize("path,label", _ALL_NODE_EXAMPLES, ids=_NE_LABELS)
def test_ne_declared_inputs_on_instance(path, label):
    defn = NodeDefinitionJSON.model_validate(_load_json(path))
    NodeRegistry.register_definition(defn)
    cls = NodeRegistry.get_class(defn.node_id)
    instance = cls()
    missing = [
        p.name for p in defn.inputs
        if p.name not in ("exec_in", "exec_out") and p.name not in instance.inputs
    ]
    assert not missing, f"Missing declared input(s): {missing}"


@pytest.mark.parametrize("path,label", _ALL_NODE_EXAMPLES, ids=_NE_LABELS)
def test_ne_declared_outputs_on_instance(path, label):
    defn = NodeDefinitionJSON.model_validate(_load_json(path))
    NodeRegistry.register_definition(defn)
    cls = NodeRegistry.get_class(defn.node_id)
    instance = cls()
    missing = [
        p.name for p in defn.outputs
        if p.name not in ("exec_in", "exec_out") and p.name not in instance.outputs
    ]
    assert not missing, f"Missing declared output(s): {missing}"


# ---------------------------------------------------------------------------
# Summary count assertions
# ---------------------------------------------------------------------------

def test_workflow_directory_counts():
    counts = {}
    for d in _WORKFLOW_DIRS:
        if d.exists():
            counts[d.name] = len([f for f in os.listdir(d) if f.endswith(".json")])
    assert counts.get("workflows", 0) >= 20, f"Expected ≥20 general workflows, found {counts.get('workflows', 0)}"
    assert counts.get("vfx_workflows", 0) >= 6, f"Expected ≥6 VFX workflows, found {counts.get('vfx_workflows', 0)}"


def test_node_examples_count():
    count = len(_ALL_NODE_EXAMPLES)
    assert count >= 25, f"Expected ≥25 node examples (node_examples/ + website_examples/), found {count}"
