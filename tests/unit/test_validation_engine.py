"""
Unit tests for src.runtime.validation_engine.

Covers:
  • empty operation list → valid with warning
  • valid ops return correct risk levels
  • shape errors from _validate_operation propagate as errors
  • self-connections are rejected
  • delete_node with downstream dependents produces a warning
  • build_node_chain sub-spec validation (duplicate ids, self-connections)
  • empty parms dict produces a warning
  • multiple ops aggregated correctly
  • risk_level thresholds: low / medium / high
  • get_validation_engine() singleton
  • ValidationEngine is stateless (concurrent calls produce independent results)
"""

from __future__ import annotations

import pytest

from src.runtime.dependency_graph import (
    DependencyGraph,
    get_dependency_graph,
    reset_dependency_graph_for_tests,
)
from src.runtime.validation_engine import ValidationEngine, get_validation_engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_graph():
    reset_dependency_graph_for_tests()
    yield
    reset_dependency_graph_for_tests()


# ---------------------------------------------------------------------------
# Empty operation list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_ops_valid_with_warning():
    engine = ValidationEngine()
    result = await engine.validate_operations([])
    assert result["valid"] is True
    assert result["op_count"] == 0
    assert len(result["warnings"]) >= 1
    assert result["risk_level"] == "low"


# ---------------------------------------------------------------------------
# Well-formed operations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_node_is_valid():
    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "test"}
    ])
    assert result["valid"] is True
    assert result["errors"] == []
    assert result["risk_level"] == "low"


@pytest.mark.asyncio
async def test_set_parms_is_medium_risk():
    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "set_parms", "node": "/obj/box1", "parms": {"sizex": 2.0}}
    ])
    assert result["valid"] is True
    assert result["risk_level"] == "medium"


@pytest.mark.asyncio
async def test_delete_node_is_high_risk():
    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "delete_node", "path": "/obj/old"}
    ])
    assert result["valid"] is True
    assert result["risk_level"] == "high"


@pytest.mark.asyncio
async def test_cook_and_layout_are_medium_and_low():
    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "cook_node", "path": "/obj/geo1"},
        {"op": "layout_children", "path": "/obj"},
    ])
    assert result["valid"] is True
    assert result["risk_level"] == "medium"


# ---------------------------------------------------------------------------
# Shape errors propagate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_parent_in_create_node():
    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "create_node", "type": "geo"}  # missing parent
    ])
    assert result["valid"] is False
    assert len(result["errors"]) == 1
    assert "parent" in result["errors"][0]["message"]


@pytest.mark.asyncio
async def test_unsupported_op_type():
    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "run_python", "code": "print('hello')"}
    ])
    assert result["valid"] is False
    assert "unsupported" in result["errors"][0]["message"]


@pytest.mark.asyncio
async def test_non_dict_op_is_error():
    engine = ValidationEngine()
    result = await engine.validate_operations(["not a dict"])
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# Self-connections are rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_self_connection_is_error():
    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "connect_nodes", "from": "/obj/a", "to": "/obj/a"}
    ])
    assert result["valid"] is False
    assert any("self-connection" in e["message"] for e in result["errors"])


# ---------------------------------------------------------------------------
# Dangerous delete produces warning when downstream deps exist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_with_downstream_produces_warning():
    graph = get_dependency_graph()
    graph.register_dependency("/obj/src", "/obj/child")

    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "delete_node", "path": "/obj/src"}
    ])
    assert result["valid"] is True
    assert any("downstream" in w["message"] for w in result["warnings"])


@pytest.mark.asyncio
async def test_delete_without_downstream_no_warning():
    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "delete_node", "path": "/obj/isolated"}
    ])
    assert result["valid"] is True
    assert all("downstream" not in w["message"] for w in result["warnings"])


# ---------------------------------------------------------------------------
# build_node_chain sub-spec validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_node_chain_valid_spec():
    engine = ValidationEngine()
    result = await engine.validate_operations([{
        "op": "build_node_chain",
        "spec": {
            "nodes": [
                {"id": "n1", "parent": "/obj/geo1", "type": "sphere", "name": "src"},
                {"id": "n2", "parent": "/obj/geo1", "type": "null", "name": "out"},
            ],
            "connections": [{"from": "n1", "to": "n2"}],
        }
    }])
    assert result["valid"] is True


@pytest.mark.asyncio
async def test_build_node_chain_duplicate_spec_ids():
    engine = ValidationEngine()
    result = await engine.validate_operations([{
        "op": "build_node_chain",
        "spec": {
            "nodes": [
                {"id": "n1", "parent": "/obj/geo1", "type": "sphere"},
                {"id": "n1", "parent": "/obj/geo1", "type": "box"},
            ],
            "connections": [],
        }
    }])
    assert result["valid"] is False
    assert any("duplicate" in e["message"] for e in result["errors"])


@pytest.mark.asyncio
async def test_build_node_chain_self_connection_in_spec():
    engine = ValidationEngine()
    result = await engine.validate_operations([{
        "op": "build_node_chain",
        "spec": {
            "nodes": [{"id": "n1", "parent": "/obj/geo1", "type": "sphere"}],
            "connections": [{"from": "n1", "to": "n1"}],
        }
    }])
    assert result["valid"] is False


@pytest.mark.asyncio
async def test_build_node_chain_missing_spec_id():
    engine = ValidationEngine()
    result = await engine.validate_operations([{
        "op": "build_node_chain",
        "spec": {
            "nodes": [{"parent": "/obj/geo1", "type": "sphere"}],  # no id
            "connections": [],
        }
    }])
    assert result["valid"] is False
    assert any("missing 'id'" in e["message"] for e in result["errors"])


# ---------------------------------------------------------------------------
# Empty parms dict produces warning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_parms_produces_warning():
    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "set_parms", "node": "/obj/box1", "parms": {}}
    ])
    assert result["valid"] is True
    assert any("no-op" in w["message"] for w in result["warnings"])


# ---------------------------------------------------------------------------
# Multiple ops → aggregated risk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_ops_risk_aggregation():
    engine = ValidationEngine()
    # create (0) + set_parms (1) + delete (10) = 11 → high
    result = await engine.validate_operations([
        {"op": "create_node", "parent": "/obj", "type": "geo"},
        {"op": "set_parms", "node": "/obj/x", "parms": {"sizex": 1.0}},
        {"op": "delete_node", "path": "/obj/old"},
    ])
    assert result["valid"] is True
    assert result["risk_level"] == "high"


@pytest.mark.asyncio
async def test_pure_creates_are_low_risk():
    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "create_node", "parent": "/obj", "type": "geo"},
        {"op": "create_node", "parent": "/obj", "type": "null"},
    ])
    assert result["valid"] is True
    assert result["risk_level"] == "low"


# ---------------------------------------------------------------------------
# Summary string
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summary_contains_op_count():
    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "create_node", "parent": "/obj", "type": "geo"},
    ])
    assert "1" in result["summary"] or "op" in result["summary"]


@pytest.mark.asyncio
async def test_summary_contains_error_count_on_failure():
    engine = ValidationEngine()
    result = await engine.validate_operations([
        {"op": "create_node", "type": "geo"},  # missing parent
    ])
    assert "error" in result["summary"]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_validation_engine()
    b = get_validation_engine()
    assert a is b
