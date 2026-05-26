"""
Unit tests for src.runtime.plan_validator.

Covers:
  • validate returns required keys
  • valid plan → valid=True
  • missing 'op' field → error
  • create_node missing parent → error
  • create_node missing type → error
  • set_parms missing node → error
  • set_parms non-dict parms → error
  • connect_nodes missing from/to → error
  • delete_node missing path → error
  • build_node_chain duplicate ids → error
  • missing capability surfaces in capability_gaps
  • delete_node with dependents → dependency_impact warning
  • self-connection → safety warning
  • many delete_node ops → safety warning
  • constraint violation (protected path) → error
  • resource threshold: cook cost exceeded → error
  • resource threshold: op count exceeded → error
  • risk_level in result
  • summary string non-empty
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.plan_validator import (
    PlanValidator,
    get_plan_validator,
    reset_plan_validator_for_tests,
)
from src.runtime.capability_registry import (
    get_capability_registry,
    reset_capability_registry_for_tests,
)
from src.runtime.runtime_constraints import (
    get_runtime_constraints,
    reset_runtime_constraints_for_tests,
)
from src.runtime.dependency_graph import (
    get_dependency_graph,
    reset_dependency_graph_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_plan_validator_for_tests()
    reset_capability_registry_for_tests()
    reset_runtime_constraints_for_tests()
    reset_dependency_graph_for_tests()
    yield
    reset_plan_validator_for_tests()
    reset_capability_registry_for_tests()
    reset_runtime_constraints_for_tests()
    reset_dependency_graph_for_tests()


def _make_plan(ops):
    return {"operations": ops, "ok": True, "intent": "test_intent", "metadata": {}}


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_returns_required_keys():
    v = get_plan_validator()
    result = await v.validate(_make_plan([
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "n1"}
    ]))
    for key in ("valid", "errors", "warnings", "capability_gaps", "safety_warnings",
                "dependency_impact", "constraint_result", "resource_result",
                "risk_level", "summary"):
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Valid plan
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_plan_passes():
    v = get_plan_validator()
    result = await v.validate(_make_plan([
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "n1"},
        {"op": "set_parms", "node": "/obj/n1", "parms": {"tx": 1.0}},
    ]))
    assert result["valid"] is True
    assert result["errors"] == []


# ---------------------------------------------------------------------------
# Structural errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_op_field_is_error():
    v = get_plan_validator()
    result = await v.validate(_make_plan([{"parent": "/obj", "type": "geo"}]))
    assert not result["valid"]
    assert any("op" in e["message"].lower() for e in result["errors"])


@pytest.mark.asyncio
async def test_create_node_missing_parent_is_error():
    v = get_plan_validator()
    result = await v.validate(_make_plan([{"op": "create_node", "type": "geo"}]))
    assert not result["valid"]


@pytest.mark.asyncio
async def test_create_node_missing_type_is_error():
    v = get_plan_validator()
    result = await v.validate(_make_plan([{"op": "create_node", "parent": "/obj"}]))
    assert not result["valid"]


@pytest.mark.asyncio
async def test_set_parms_missing_node_is_error():
    v = get_plan_validator()
    result = await v.validate(_make_plan([{"op": "set_parms", "parms": {"tx": 1.0}}]))
    assert not result["valid"]


@pytest.mark.asyncio
async def test_set_parms_non_dict_parms_is_error():
    v = get_plan_validator()
    result = await v.validate(_make_plan([{"op": "set_parms", "node": "/obj/n1", "parms": "bad"}]))
    assert not result["valid"]


@pytest.mark.asyncio
async def test_connect_nodes_missing_from_is_error():
    v = get_plan_validator()
    result = await v.validate(_make_plan([{"op": "connect_nodes", "to_node": "/obj/n2"}]))
    assert not result["valid"]


@pytest.mark.asyncio
async def test_connect_nodes_missing_to_is_error():
    v = get_plan_validator()
    result = await v.validate(_make_plan([{"op": "connect_nodes", "from_node": "/obj/n1"}]))
    assert not result["valid"]


@pytest.mark.asyncio
async def test_delete_node_missing_path_is_error():
    v = get_plan_validator()
    result = await v.validate(_make_plan([{"op": "delete_node"}]))
    assert not result["valid"]


@pytest.mark.asyncio
async def test_build_node_chain_duplicate_ids_is_error():
    v = get_plan_validator()
    spec = {
        "nodes": [
            {"id": "n1", "parent": "/obj", "type": "geo"},
            {"id": "n1", "parent": "/obj", "type": "null"},  # duplicate
        ],
        "connections": [],
    }
    result = await v.validate(_make_plan([{"op": "build_node_chain", "spec": spec}]))
    assert not result["valid"]


# ---------------------------------------------------------------------------
# Capability gaps
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_required_capability_in_gaps():
    v = get_plan_validator()
    result = await v.validate(
        _make_plan([{"op": "create_node", "parent": "/obj", "type": "geo"}]),
        intent_metadata={"required_capabilities": ["my_missing_cap"]},
    )
    assert any(c["capability"] == "my_missing_cap" for c in result["capability_gaps"])


# ---------------------------------------------------------------------------
# Dependency impact
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_with_dependents_is_dependency_warning():
    graph = get_dependency_graph()
    graph.register_dependency("/obj/to_delete", "/obj/child1", "connection")
    graph.register_dependency("/obj/to_delete", "/obj/child2", "connection")

    v = get_plan_validator()
    result = await v.validate(_make_plan([{"op": "delete_node", "path": "/obj/to_delete"}]))
    assert len(result["dependency_impact"]) >= 1


# ---------------------------------------------------------------------------
# Safety warnings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_self_connection_safety_warning():
    v = get_plan_validator()
    result = await v.validate(_make_plan([
        {"op": "connect_nodes", "from_node": "/obj/n1", "to_node": "/obj/n1"}
    ]))
    assert any("self" in w["message"].lower() for w in result["safety_warnings"])


@pytest.mark.asyncio
async def test_many_deletes_safety_warning():
    v = get_plan_validator()
    ops = [{"op": "delete_node", "path": f"/obj/n{i}"} for i in range(6)]
    result = await v.validate(_make_plan(ops))
    assert any("delete" in w["message"].lower() for w in result["safety_warnings"])


# ---------------------------------------------------------------------------
# Constraint violation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_protected_path_constraint_is_error():
    v = get_plan_validator()
    result = await v.validate(_make_plan([
        {"op": "create_node", "parent": "/stage", "type": "geo"}
    ]))
    assert not result["valid"]
    assert any("stage" in e["message"].lower() or "protect" in e["message"].lower()
               for e in result["errors"])


# ---------------------------------------------------------------------------
# Resource thresholds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cook_cost_threshold():
    v = get_plan_validator()
    # cook_node ops have a non-zero cook cost; set threshold below any real cost
    ops = [{"op": "cook_node", "path": f"/obj/n{i}"} for i in range(20)]
    result = await v.validate(_make_plan(ops), max_cook_cost=0.0)
    assert not result["valid"]


@pytest.mark.asyncio
async def test_op_count_threshold():
    v = get_plan_validator()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": f"n{i}"} for i in range(10)]
    result = await v.validate(_make_plan(ops), max_op_count=5)
    assert not result["valid"]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summary_non_empty():
    v = get_plan_validator()
    result = await v.validate(_make_plan([]))
    assert isinstance(result["summary"], str) and len(result["summary"]) > 0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_plan_validator()
    b = get_plan_validator()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_plan_validator()
    reset_plan_validator_for_tests()
    b = get_plan_validator()
    assert a is not b
