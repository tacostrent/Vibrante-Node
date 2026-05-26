"""
Unit tests for the hou_mcp_execution_preview node.

Verifies that the node:
  • loads and registers correctly via NodeRegistry
  • NEVER mutates scene (no bridge calls)
  • classifies ops into correct output categories
  • returns correct risk_level from ValidationEngine
  • handles invalid JSON input gracefully
  • handles non-list operations gracefully
  • returns dependency_impact when include_dependencies=True
  • returns empty preview_json round-trip
  • exec_out is always True
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.registry import NodeRegistry
from src.runtime.dependency_graph import (
    get_dependency_graph,
    reset_dependency_graph_for_tests,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _ensure_registry():
    repo = Path(__file__).parent.parent.parent
    NodeRegistry.load_all(str(repo / "nodes"))
    NodeRegistry._load_directory(str(repo / "plugins" / "houdini" / "v_nodes_houdini"))


@pytest.fixture(autouse=True)
def _reset_graph():
    reset_dependency_graph_for_tests()
    yield
    reset_dependency_graph_for_tests()


def _node():
    cls = NodeRegistry.get_class("hou_mcp_execution_preview")
    assert cls is not None, "hou_mcp_execution_preview not registered"
    return cls()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_node_registers():
    cls = NodeRegistry.get_class("hou_mcp_execution_preview")
    assert cls is not None


def test_node_has_expected_ports():
    node = _node()
    assert "operations" in node.inputs
    assert "include_dependencies" in node.inputs
    assert "estimate_cooks" in node.inputs
    assert "nodes_to_create" in node.outputs
    assert "nodes_to_modify" in node.outputs
    assert "nodes_to_delete" in node.outputs
    assert "affected_nodes" in node.outputs
    assert "estimated_cooks" in node.outputs
    assert "risk_level" in node.outputs
    assert "warnings" in node.outputs
    assert "errors" in node.outputs
    assert "dependency_impact" in node.outputs
    assert "preview_json" in node.outputs


# ---------------------------------------------------------------------------
# No mutation — bridge is never called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_bridge_calls_on_create_op(monkeypatch):
    """The preview node must never touch the bridge."""
    import src.utils.hou_bridge as bridge_mod

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("bridge should not be called from execution preview")

    monkeypatch.setattr(bridge_mod, "get_bridge", _should_not_be_called)

    node = _node()
    ops = json.dumps([
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "test"}
    ])
    result = await node.execute({"operations": ops, "include_dependencies": False})
    assert result["exec_out"] is True
    # No AssertionError means bridge was never called


# ---------------------------------------------------------------------------
# Op classification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_op_classified():
    node = _node()
    ops = json.dumps([{"op": "create_node", "parent": "/obj", "type": "geo", "name": "ball"}])
    result = await node.execute({"operations": ops, "include_dependencies": False})
    assert any("ball" in p for p in result["nodes_to_create"])


@pytest.mark.asyncio
async def test_set_parms_classified_as_modify():
    node = _node()
    ops = json.dumps([{"op": "set_parms", "node": "/obj/box1", "parms": {"sizex": 2.0}}])
    result = await node.execute({"operations": ops, "include_dependencies": False})
    assert "/obj/box1" in result["nodes_to_modify"]


@pytest.mark.asyncio
async def test_set_keyframe_classified_as_modify():
    node = _node()
    ops = json.dumps([{"op": "set_keyframe", "node": "/obj/cam1", "parm": "tx", "frame": 1, "value": 0.0}])
    result = await node.execute({"operations": ops, "include_dependencies": False})
    assert "/obj/cam1" in result["nodes_to_modify"]


@pytest.mark.asyncio
async def test_delete_op_classified():
    node = _node()
    ops = json.dumps([{"op": "delete_node", "path": "/obj/old"}])
    result = await node.execute({"operations": ops, "include_dependencies": False})
    assert "/obj/old" in result["nodes_to_delete"]


@pytest.mark.asyncio
async def test_build_node_chain_creates_classified():
    node = _node()
    ops = json.dumps([{
        "op": "build_node_chain",
        "spec": {
            "nodes": [
                {"id": "n1", "parent": "/obj/geo1", "type": "sphere", "name": "ball"},
            ],
            "connections": [],
        }
    }])
    result = await node.execute({"operations": ops, "include_dependencies": False})
    assert any("ball" in p for p in result["nodes_to_create"])


# ---------------------------------------------------------------------------
# Risk levels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_risk_level_low_for_creates():
    node = _node()
    ops = json.dumps([{"op": "create_node", "parent": "/obj", "type": "geo"}])
    result = await node.execute({"operations": ops, "include_dependencies": False})
    assert result["risk_level"] == "low"


@pytest.mark.asyncio
async def test_risk_level_high_for_delete():
    node = _node()
    ops = json.dumps([{"op": "delete_node", "path": "/obj/old"}])
    result = await node.execute({"operations": ops, "include_dependencies": False})
    assert result["risk_level"] == "high"


@pytest.mark.asyncio
async def test_risk_level_medium_for_set_parms():
    node = _node()
    ops = json.dumps([{"op": "set_parms", "node": "/obj/x", "parms": {"tx": 1.0}}])
    result = await node.execute({"operations": ops, "include_dependencies": False})
    assert result["risk_level"] == "medium"


# ---------------------------------------------------------------------------
# Validation errors surface in output
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_op_surfaces_in_errors():
    node = _node()
    ops = json.dumps([{"op": "create_node", "type": "geo"}])  # missing parent
    result = await node.execute({"operations": ops, "include_dependencies": False})
    assert len(result["errors"]) >= 1


# ---------------------------------------------------------------------------
# Invalid JSON input
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_json_returns_error():
    node = _node()
    result = await node.execute({"operations": "NOT VALID JSON", "include_dependencies": False})
    assert result["exec_out"] is True
    assert len(result["errors"]) >= 1


@pytest.mark.asyncio
async def test_non_list_json_returns_error():
    node = _node()
    result = await node.execute({"operations": '{"not": "a list"}', "include_dependencies": False})
    assert len(result["errors"]) >= 1


# ---------------------------------------------------------------------------
# Dependency impact
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dependency_impact_populated():
    graph = get_dependency_graph()
    graph.register_dependency("/obj/box1", "/obj/mountain1")

    node = _node()
    ops = json.dumps([{"op": "set_parms", "node": "/obj/box1", "parms": {"tx": 1.0}}])
    result = await node.execute({"operations": ops, "include_dependencies": True})
    assert "/obj/mountain1" in result["affected_nodes"]


@pytest.mark.asyncio
async def test_dependency_impact_empty_when_disabled():
    graph = get_dependency_graph()
    graph.register_dependency("/obj/box1", "/obj/mountain1")

    node = _node()
    ops = json.dumps([{"op": "set_parms", "node": "/obj/box1", "parms": {"tx": 1.0}}])
    result = await node.execute({"operations": ops, "include_dependencies": False})
    assert result["affected_nodes"] == []


# ---------------------------------------------------------------------------
# preview_json is round-trip safe
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_json_round_trips():
    node = _node()
    ops = json.dumps([{"op": "create_node", "parent": "/obj", "type": "geo"}])
    result = await node.execute({"operations": ops, "include_dependencies": False})
    parsed = json.loads(result["preview_json"])
    assert "nodes_to_create" in parsed
    assert "risk_level" in parsed


# ---------------------------------------------------------------------------
# exec_out always True
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exec_out_always_true_on_invalid_input():
    node = _node()
    result = await node.execute({"operations": "BROKEN JSON", "include_dependencies": False})
    assert result.get("exec_out") is True


@pytest.mark.asyncio
async def test_exec_out_true_on_success():
    node = _node()
    ops = json.dumps([{"op": "create_node", "parent": "/obj", "type": "geo"}])
    result = await node.execute({"operations": ops, "include_dependencies": False})
    assert result.get("exec_out") is True
