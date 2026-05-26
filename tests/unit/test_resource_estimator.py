"""
Unit tests for src.runtime.resource_estimator.

Covers:
  • estimate_operation returns correct shape
  • risk_level matches op type (create=low, set_parms=medium, delete=high)
  • memory/cook bump for simulation node types
  • estimate_transaction aggregates correctly
  • estimate_graph_complexity thresholds
  • invalid op shape handled gracefully
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.resource_estimator import (
    ResourceEstimator,
    get_resource_estimator,
    reset_resource_estimator_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_resource_estimator_for_tests()
    yield
    reset_resource_estimator_for_tests()


# ---------------------------------------------------------------------------
# estimate_operation — shape
# ---------------------------------------------------------------------------

def test_estimate_operation_required_keys():
    est = get_resource_estimator()
    result = est.estimate_operation({"op": "create_node", "parent": "/obj", "type": "geo"})
    assert "op" in result
    assert "memory_impact" in result
    assert "cook_cost" in result
    assert "risk_level" in result
    assert "notes" in result


def test_estimate_operation_values_in_range():
    est = get_resource_estimator()
    result = est.estimate_operation({"op": "create_node", "parent": "/obj", "type": "geo"})
    assert 0.0 <= result["memory_impact"] <= 1.0
    assert 0.0 <= result["cook_cost"] <= 1.0
    assert result["risk_level"] in ("low", "medium", "high")


# ---------------------------------------------------------------------------
# Risk levels by op type
# ---------------------------------------------------------------------------

def test_create_node_is_low_risk():
    est = get_resource_estimator()
    r = est.estimate_operation({"op": "create_node", "parent": "/obj", "type": "geo"})
    assert r["risk_level"] == "low"


def test_set_parms_is_medium_risk():
    est = get_resource_estimator()
    r = est.estimate_operation({"op": "set_parms", "node": "/obj/geo1", "parms": {"tx": 1.0}})
    assert r["risk_level"] == "medium"


def test_delete_node_is_high_risk():
    est = get_resource_estimator()
    r = est.estimate_operation({"op": "delete_node", "path": "/obj/geo1"})
    assert r["risk_level"] == "high"
    assert any("irreversible" in n for n in r["notes"])


def test_connect_nodes_is_medium_risk():
    est = get_resource_estimator()
    r = est.estimate_operation({"op": "connect_nodes", "from_node": "/a", "to_node": "/b"})
    assert r["risk_level"] == "medium"


def test_layout_children_is_low_risk():
    est = get_resource_estimator()
    r = est.estimate_operation({"op": "layout_children", "path": "/obj"})
    assert r["risk_level"] == "low"


# ---------------------------------------------------------------------------
# Node-type bumps
# ---------------------------------------------------------------------------

def test_pyro_node_type_bumps_memory_and_cook():
    est = get_resource_estimator()
    r = est.estimate_operation({"op": "create_node", "parent": "/obj/geo1", "type": "pyro"})
    assert r["memory_impact"] >= 0.7
    assert r["cook_cost"] >= 0.7


def test_flip_simulation_bumps_memory():
    est = get_resource_estimator()
    r = est.estimate_operation({"op": "create_node", "parent": "/obj/geo1", "type": "flip"})
    assert r["memory_impact"] >= 0.7


def test_plain_geo_has_low_memory():
    est = get_resource_estimator()
    r = est.estimate_operation({"op": "create_node", "parent": "/obj", "type": "geo"})
    assert r["memory_impact"] < 0.5


# ---------------------------------------------------------------------------
# estimate_transaction
# ---------------------------------------------------------------------------

def test_estimate_transaction_shape():
    est = get_resource_estimator()
    ops = [
        {"op": "create_node", "parent": "/obj", "type": "geo"},
        {"op": "set_parms", "node": "/obj/geo1", "parms": {"tx": 1.0}},
    ]
    result = est.estimate_transaction(ops)
    assert "op_count" in result
    assert "estimated_memory" in result
    assert "estimated_cook_cost" in result
    assert "risk_level" in result
    assert "graph_complexity" in result
    assert "per_op" in result


def test_estimate_transaction_op_count():
    est = get_resource_estimator()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo"}] * 5
    r = est.estimate_transaction(ops)
    assert r["op_count"] == 5


def test_estimate_transaction_delete_makes_high_risk():
    est = get_resource_estimator()
    ops = [{"op": "delete_node", "path": "/obj/geo1"}]
    r = est.estimate_transaction(ops)
    assert r["risk_level"] == "high"


def test_estimate_transaction_empty_ops():
    est = get_resource_estimator()
    r = est.estimate_transaction([])
    assert r["op_count"] == 0
    assert r["risk_level"] == "low"


def test_estimate_transaction_non_list_returns_safe_default():
    est = get_resource_estimator()
    r = est.estimate_transaction("not a list")
    assert r["op_count"] == 0
    assert r["estimated_memory"] == 0.0


# ---------------------------------------------------------------------------
# estimate_graph_complexity
# ---------------------------------------------------------------------------

def test_complexity_low_for_small_graph():
    est = get_resource_estimator()
    assert est.estimate_graph_complexity(2, 1) == "low"


def test_complexity_medium_for_medium_graph():
    est = get_resource_estimator()
    assert est.estimate_graph_complexity(8, 4) == "medium"


def test_complexity_high_for_large_graph():
    est = get_resource_estimator()
    assert est.estimate_graph_complexity(25, 20) == "high"


def test_complexity_zero_nodes():
    est = get_resource_estimator()
    assert est.estimate_graph_complexity(0, 0) == "low"


# ---------------------------------------------------------------------------
# Invalid op shape
# ---------------------------------------------------------------------------

def test_estimate_non_dict_op_does_not_raise():
    est = get_resource_estimator()
    r = est.estimate_operation("not a dict")
    assert r["risk_level"] == "low"
    assert "invalid" in r["notes"][0]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_resource_estimator()
    b = get_resource_estimator()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_resource_estimator()
    reset_resource_estimator_for_tests()
    b = get_resource_estimator()
    assert a is not b
