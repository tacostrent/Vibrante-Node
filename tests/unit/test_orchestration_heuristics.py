"""
Unit tests for src.runtime.orchestration_heuristics.

Covers:
  • order_operations: create before cook, delete last
  • order_operations: empty → empty
  • order_operations: already ordered → changed=False
  • select_worker: returns least-loaded idle
  • select_worker: no matching caps → None
  • select_worker: no idle workers → None
  • select_worker: alternatives list populated
  • group_for_batching: delete starts new batch
  • group_for_batching: max_batch_size respected
  • group_for_batching: empty → no batches
  • route_operation: hint_dcc explicit
  • route_operation: houdini op → houdini DCC
  • route_operation: no DCC → None
  • route_operation: first fallback when no rule
  • prioritize_queue: higher priority first
  • prioritize_queue: FIFO tiebreaker
  • prioritize_queue: empty → []
  • list_heuristics: returns 5 entries
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.orchestration_heuristics import (
    OrchestrationHeuristics,
    get_orchestration_heuristics,
    reset_orchestration_heuristics_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_orchestration_heuristics_for_tests()
    yield
    reset_orchestration_heuristics_for_tests()


# ---------------------------------------------------------------------------
# order_operations
# ---------------------------------------------------------------------------

def test_order_operations_empty():
    h = get_orchestration_heuristics()
    r = h.order_operations([])
    assert r["ordered_indices"] == []
    assert r["changed"] is False


def test_order_operations_create_before_cook():
    h = get_orchestration_heuristics()
    ops = [
        {"op": "cook_node", "path": "/obj/geo"},
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "g1"},
    ]
    r = h.order_operations(ops)
    # create (weight 1) should come before cook (weight 7)
    assert r["ordered_indices"][0] == 1   # create
    assert r["ordered_indices"][1] == 0   # cook
    assert r["changed"] is True


def test_order_operations_delete_last():
    h = get_orchestration_heuristics()
    ops = [
        {"op": "delete_node", "path": "/obj/old"},
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "g1"},
    ]
    r = h.order_operations(ops)
    assert r["ordered_indices"][-1] == 0   # delete at end


def test_order_operations_already_ordered_unchanged():
    h = get_orchestration_heuristics()
    ops = [
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "g1"},
        {"op": "cook_node", "path": "/obj/geo"},
    ]
    r = h.order_operations(ops)
    assert r["changed"] is False
    assert r["ordered_indices"] == [0, 1]


# ---------------------------------------------------------------------------
# select_worker
# ---------------------------------------------------------------------------

def _worker(wid, caps, load, max_load=4, status="idle"):
    return {"id": wid, "capabilities": caps, "current_load": load, "max_load": max_load, "status": status}


def test_select_worker_least_loaded():
    h = get_orchestration_heuristics()
    workers = [
        _worker("w1", ["houdini"], 3),
        _worker("w2", ["houdini"], 1),
    ]
    r = h.select_worker(workers, ["houdini"])
    assert r["selected_id"] == "w2"


def test_select_worker_no_matching_caps():
    h = get_orchestration_heuristics()
    workers = [_worker("w1", ["maya"], 0)]
    r = h.select_worker(workers, ["houdini"])
    assert r["selected_id"] is None


def test_select_worker_no_idle():
    h = get_orchestration_heuristics()
    workers = [_worker("w1", ["houdini"], 4, 4, "busy")]
    r = h.select_worker(workers, ["houdini"])
    # max load == current load but still "busy" — idle filter blocks it
    # (status != "idle")
    assert r["selected_id"] is None


def test_select_worker_alternatives_populated():
    h = get_orchestration_heuristics()
    workers = [
        _worker("w1", ["houdini"], 0),
        _worker("w2", ["houdini"], 1),
        _worker("w3", ["houdini"], 2),
    ]
    r = h.select_worker(workers, ["houdini"])
    assert r["selected_id"] == "w1"
    assert len(r["alternatives"]) == 2


def test_select_worker_empty_list():
    h = get_orchestration_heuristics()
    r = h.select_worker([], ["houdini"])
    assert r["selected_id"] is None


# ---------------------------------------------------------------------------
# group_for_batching
# ---------------------------------------------------------------------------

def test_group_for_batching_empty():
    h = get_orchestration_heuristics()
    r = h.group_for_batching([])
    assert r["batches"] == []
    assert r["batch_count"] == 0


def test_group_for_batching_delete_splits():
    h = get_orchestration_heuristics()
    ops = [
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "g1"},
        {"op": "delete_node", "path": "/obj/old"},
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "g2"},
    ]
    r = h.group_for_batching(ops)
    # delete at index 1 with prior ops → splits into 2 batches
    assert r["batch_count"] >= 2


def test_group_for_batching_max_size():
    h = get_orchestration_heuristics()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": f"g{i}"} for i in range(12)]
    r = h.group_for_batching(ops, max_batch_size=5)
    # 12 ops, size 5 → 3 batches
    assert r["batch_count"] == 3


def test_group_for_batching_single_batch():
    h = get_orchestration_heuristics()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": "g1"}]
    r = h.group_for_batching(ops)
    assert r["batch_count"] == 1
    assert r["batches"] == [[0]]


# ---------------------------------------------------------------------------
# route_operation
# ---------------------------------------------------------------------------

def test_route_operation_explicit_hint():
    h = get_orchestration_heuristics()
    op = {"op": "create_node", "hint_dcc": "blender"}
    r = h.route_operation(op, ["houdini", "blender"])
    assert r["recommended_dcc"] == "blender"
    assert r["confidence"] == 1.0


def test_route_operation_houdini_op():
    h = get_orchestration_heuristics()
    op = {"op": "create_node"}
    r = h.route_operation(op, ["houdini", "maya"])
    assert r["recommended_dcc"] == "houdini"
    assert r["confidence"] > 0.9


def test_route_operation_no_dccs():
    h = get_orchestration_heuristics()
    op = {"op": "create_node"}
    r = h.route_operation(op, [])
    assert r["recommended_dcc"] is None


def test_route_operation_fallback():
    h = get_orchestration_heuristics()
    op = {"op": "custom_op_xyz"}
    r = h.route_operation(op, ["my_dcc"])
    assert r["recommended_dcc"] == "my_dcc"
    assert r["confidence"] < 0.9


# ---------------------------------------------------------------------------
# prioritize_queue
# ---------------------------------------------------------------------------

def test_prioritize_queue_empty():
    h = get_orchestration_heuristics()
    r = h.prioritize_queue([])
    assert r["ordered_ids"] == []


def test_prioritize_queue_higher_priority_first():
    h = get_orchestration_heuristics()
    items = [
        {"id": "a", "priority": 10, "risk_level": "low",  "op_count": 5, "timestamp": 1.0},
        {"id": "b", "priority": 90, "risk_level": "low",  "op_count": 5, "timestamp": 1.0},
    ]
    r = h.prioritize_queue(items)
    assert r["ordered_ids"][0] == "b"


def test_prioritize_queue_fifo_tiebreaker():
    h = get_orchestration_heuristics()
    items = [
        {"id": "a", "priority": 50, "risk_level": "low", "op_count": 5, "timestamp": 2.0},
        {"id": "b", "priority": 50, "risk_level": "low", "op_count": 5, "timestamp": 1.0},
    ]
    r = h.prioritize_queue(items)
    assert r["ordered_ids"][0] == "b"   # older timestamp first


# ---------------------------------------------------------------------------
# list_heuristics
# ---------------------------------------------------------------------------

def test_list_heuristics_returns_five():
    h = get_orchestration_heuristics()
    heuristics = h.list_heuristics()
    assert len(heuristics) == 5
    names = {h_["name"] for h_ in heuristics}
    assert "order_operations" in names
    assert "select_worker"    in names
    assert "group_for_batching" in names
    assert "route_operation"  in names
    assert "prioritize_queue" in names


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    assert get_orchestration_heuristics() is get_orchestration_heuristics()


def test_reset_creates_fresh():
    a = get_orchestration_heuristics()
    reset_orchestration_heuristics_for_tests()
    b = get_orchestration_heuristics()
    assert a is not b
