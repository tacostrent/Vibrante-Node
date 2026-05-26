"""
Unit tests for src.runtime.resource_optimizer.

Covers:
  • recommend_worker_allocation: returns best worker
  • recommend_worker_allocation: no workers → None
  • recommend_worker_allocation: should_split for large batches
  • recommend_worker_allocation: projected load in result
  • recommend_transaction_sizing: single group for small batch
  • recommend_transaction_sizing: split at delete_node
  • recommend_transaction_sizing: empty → group_count 0
  • recommend_scheduling_order: higher priority first
  • recommend_scheduling_order: FIFO tiebreaker
  • recommend_scheduling_order: empty → []
  • recommend_load_balancing: healthy pool
  • recommend_load_balancing: overloaded pool → scale_up action
  • recommend_load_balancing: offline worker → revive_or_remove
  • recommend_load_balancing: empty → healthy
  • stats.call_count increments
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.resource_optimizer import (
    ResourceOptimizer,
    get_resource_optimizer,
    reset_resource_optimizer_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_resource_optimizer_for_tests()
    yield
    reset_resource_optimizer_for_tests()


def _worker(wid, load=0, max_load=4, status="idle"):
    return {"id": wid, "current_load": load, "max_load": max_load, "status": status}


# ---------------------------------------------------------------------------
# recommend_worker_allocation
# ---------------------------------------------------------------------------

def test_recommend_worker_allocation_returns_best():
    opt = get_resource_optimizer()
    workers = [_worker("w1", load=3), _worker("w2", load=1)]
    ops = [{"op": "create_node"}]
    result = opt.recommend_worker_allocation(ops, workers)
    assert result["recommended_worker"] == "w2"


def test_recommend_worker_allocation_no_workers():
    opt = get_resource_optimizer()
    result = opt.recommend_worker_allocation([{"op": "create_node"}], [])
    assert result["recommended_worker"] is None


def test_recommend_worker_allocation_should_split_large_batch():
    opt = get_resource_optimizer()
    workers = [_worker("w1")]
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": f"g{i}"} for i in range(20)]
    result = opt.recommend_worker_allocation(ops, workers)
    assert result["should_split"] is True


def test_recommend_worker_allocation_load_after():
    opt = get_resource_optimizer()
    workers = [_worker("w1", load=0, max_load=4)]
    result = opt.recommend_worker_allocation([{"op": "create_node"}], workers)
    assert result["load_after"] == 0.25   # 1/4


# ---------------------------------------------------------------------------
# recommend_transaction_sizing
# ---------------------------------------------------------------------------

def test_recommend_transaction_sizing_empty():
    opt = get_resource_optimizer()
    result = opt.recommend_transaction_sizing([])
    assert result["group_count"] == 0
    assert result["split_points"] == []


def test_recommend_transaction_sizing_single_group():
    opt = get_resource_optimizer()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": f"g{i}"} for i in range(5)]
    result = opt.recommend_transaction_sizing(ops)
    assert result["group_count"] == 1


def test_recommend_transaction_sizing_delete_split():
    opt = get_resource_optimizer()
    ops = [
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "g1"},
        {"op": "delete_node", "path": "/obj/old"},
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "g2"},
    ]
    result = opt.recommend_transaction_sizing(ops)
    assert result["group_count"] >= 2


def test_recommend_transaction_sizing_recommended_size_positive():
    opt = get_resource_optimizer()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": f"g{i}"} for i in range(10)]
    result = opt.recommend_transaction_sizing(ops)
    assert result["recommended_size"] >= 1


# ---------------------------------------------------------------------------
# recommend_scheduling_order
# ---------------------------------------------------------------------------

def test_recommend_scheduling_order_empty():
    opt = get_resource_optimizer()
    result = opt.recommend_scheduling_order([])
    assert result["ordered_ids"] == []


def test_recommend_scheduling_order_priority():
    opt = get_resource_optimizer()
    items = [
        {"id": "a", "priority": 20, "risk_level": "low", "op_count": 5, "timestamp": 1.0},
        {"id": "b", "priority": 80, "risk_level": "low", "op_count": 5, "timestamp": 1.0},
    ]
    result = opt.recommend_scheduling_order(items)
    assert result["ordered_ids"][0] == "b"


def test_recommend_scheduling_order_fifo_tiebreaker():
    opt = get_resource_optimizer()
    items = [
        {"id": "a", "priority": 50, "risk_level": "low", "op_count": 5, "timestamp": 2.0},
        {"id": "b", "priority": 50, "risk_level": "low", "op_count": 5, "timestamp": 1.0},
    ]
    result = opt.recommend_scheduling_order(items)
    assert result["ordered_ids"][0] == "b"


# ---------------------------------------------------------------------------
# recommend_load_balancing
# ---------------------------------------------------------------------------

def test_recommend_load_balancing_healthy():
    opt = get_resource_optimizer()
    workers = [_worker("w1", load=1), _worker("w2", load=1)]
    result = opt.recommend_load_balancing(workers)
    assert result["pool_health"] == "healthy"


def test_recommend_load_balancing_overloaded():
    opt = get_resource_optimizer()
    workers = [_worker("w1", load=4, max_load=4)]
    result = opt.recommend_load_balancing(workers)
    assert result["pool_health"] == "overloaded"
    action_types = {a["action"] for a in result["actions"]}
    assert "scale_up" in action_types


def test_recommend_load_balancing_offline_worker():
    opt = get_resource_optimizer()
    workers = [_worker("w1", load=0, status="offline")]
    result = opt.recommend_load_balancing(workers)
    action_types = {a["action"] for a in result["actions"]}
    assert "revive_or_remove" in action_types


def test_recommend_load_balancing_empty():
    opt = get_resource_optimizer()
    result = opt.recommend_load_balancing([])
    assert result["pool_health"] == "healthy"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_call_count():
    opt = get_resource_optimizer()
    opt.recommend_worker_allocation([], [])
    opt.recommend_transaction_sizing([])
    assert opt.stats()["call_count"] == 2


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    assert get_resource_optimizer() is get_resource_optimizer()


def test_reset_creates_fresh():
    a = get_resource_optimizer()
    reset_resource_optimizer_for_tests()
    b = get_resource_optimizer()
    assert a is not b
