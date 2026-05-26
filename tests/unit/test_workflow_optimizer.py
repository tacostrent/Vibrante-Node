"""
Unit tests for src.runtime.workflow_optimizer.

Covers:
  • analyze_plan risk levels and tip generation
  • reorder_suggested detection
  • batch_suggested detection (duplicate set_parms on same node)
  • empty plan returns safe defaults
  • recommend_alternatives always includes dry_run_first
  • recommend_alternatives preferred set for medium/high risk
  • score_template unknown returns "unknown" recommendation
  • score_template preferred/acceptable/avoid thresholds
  • record_outcome valid/invalid values
  • get_optimization_history newest-first ordering
  • stats shape
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.workflow_optimizer import (
    WorkflowOptimizer,
    get_workflow_optimizer,
    reset_workflow_optimizer_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_workflow_optimizer_for_tests()
    yield
    reset_workflow_optimizer_for_tests()


# ---------------------------------------------------------------------------
# analyze_plan
# ---------------------------------------------------------------------------

def test_analyze_plan_empty_returns_low_risk():
    opt = get_workflow_optimizer()
    result = opt.analyze_plan([])
    assert result["risk_level"] == "low"
    assert result["op_count"] == 0


def test_analyze_plan_delete_heavy_high_risk():
    opt = get_workflow_optimizer()
    ops = [{"op": "delete_node", "path": f"/obj/n{i}"} for i in range(2)]
    result = opt.analyze_plan(ops)
    assert result["risk_level"] == "high"
    assert result["delete_count"] == 2


def test_analyze_plan_low_risk_creates_only():
    opt = get_workflow_optimizer()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": f"g{i}"} for i in range(4)]
    result = opt.analyze_plan(ops)
    assert result["risk_level"] == "low"
    assert result["delete_count"] == 0


def test_analyze_plan_medium_risk():
    opt = get_workflow_optimizer()
    ops = [{"op": "set_parms", "node": "/obj/geo1", "parms": {"tx": 1.0}},
           {"op": "connect_nodes", "from": "/obj/a", "to": "/obj/b"},
           {"op": "cook_node", "path": "/obj/b"}]
    result = opt.analyze_plan(ops)
    assert result["risk_level"] == "medium"


def test_analyze_plan_reorder_suggested():
    opt = get_workflow_optimizer()
    ops = [
        {"op": "cook_node", "path": "/obj/geo"},
        {"op": "delete_node", "path": "/obj/old"},
    ]
    result = opt.analyze_plan(ops)
    assert result["reorder_suggested"] is True


def test_analyze_plan_no_reorder_when_delete_first():
    opt = get_workflow_optimizer()
    ops = [
        {"op": "delete_node", "path": "/obj/old"},
        {"op": "cook_node", "path": "/obj/geo"},
    ]
    result = opt.analyze_plan(ops)
    assert result["reorder_suggested"] is False


def test_analyze_plan_batch_suggested():
    opt = get_workflow_optimizer()
    ops = [{"op": "set_parms", "node": "/obj/geo1", "parms": {"tx": i}} for i in range(4)]
    result = opt.analyze_plan(ops)
    assert result["batch_suggested"] is True


def test_analyze_plan_tips_nonempty_for_high_risk():
    opt = get_workflow_optimizer()
    ops = [{"op": "delete_node", "path": "/obj/x"}]
    result = opt.analyze_plan(ops)
    assert len(result["optimization_tips"]) > 0


# ---------------------------------------------------------------------------
# recommend_alternatives
# ---------------------------------------------------------------------------

def test_recommend_alternatives_always_has_dry_run():
    opt = get_workflow_optimizer()
    result = opt.recommend_alternatives("build_pyro_source", [])
    ids = {a["strategy"] for a in result["alternatives"]}
    assert "dry_run_first" in ids


def test_recommend_alternatives_preferred_for_high_risk():
    opt = get_workflow_optimizer()
    ops = [{"op": "delete_node", "path": "/obj/x"}]
    result = opt.recommend_alternatives("build_pyro_source", ops)
    assert result["preferred"] is not None


def test_recommend_alternatives_large_batch_split():
    opt = get_workflow_optimizer()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": f"g{i}"} for i in range(15)]
    result = opt.recommend_alternatives("test", ops)
    ids = {a["strategy"] for a in result["alternatives"]}
    assert "split_batch" in ids


def test_recommend_alternatives_has_reasoning():
    opt = get_workflow_optimizer()
    result = opt.recommend_alternatives("test", [])
    assert len(result["reasoning"]) >= 1


# ---------------------------------------------------------------------------
# score_template
# ---------------------------------------------------------------------------

def test_score_template_unknown_no_history():
    opt = get_workflow_optimizer()
    result = opt.score_template("nonexistent_template")
    assert result["uses"] == 0
    assert result["recommendation"] == "unknown"


def test_score_template_preferred():
    opt = get_workflow_optimizer()
    for _ in range(5):
        opt.record_outcome("plan1", "success", {"template_id": "karma_render"})
    result = opt.score_template("karma_render")
    assert result["recommendation"] == "preferred"
    assert result["uses"] == 5


def test_score_template_avoid():
    opt = get_workflow_optimizer()
    for _ in range(3):
        opt.record_outcome("plan1", "failure", {"template_id": "bad_template"})
    result = opt.score_template("bad_template")
    assert result["recommendation"] == "avoid"


# ---------------------------------------------------------------------------
# record_outcome
# ---------------------------------------------------------------------------

def test_record_outcome_valid_returns_id():
    opt = get_workflow_optimizer()
    rid = opt.record_outcome("plan-x", "success")
    assert isinstance(rid, str) and len(rid) == 36


def test_record_outcome_invalid_raises():
    opt = get_workflow_optimizer()
    with pytest.raises(ValueError):
        opt.record_outcome("plan-x", "invalid_outcome")


# ---------------------------------------------------------------------------
# get_optimization_history
# ---------------------------------------------------------------------------

def test_get_optimization_history_newest_first():
    opt = get_workflow_optimizer()
    opt.record_outcome("p1", "success")
    opt.record_outcome("p2", "failure")
    opt.record_outcome("p3", "partial")
    history = opt.get_optimization_history(limit=10)
    assert len(history) == 3
    # newest first
    ts = [r["timestamp"] for r in history]
    assert ts == sorted(ts, reverse=True)


def test_get_optimization_history_respects_limit():
    opt = get_workflow_optimizer()
    for i in range(5):
        opt.record_outcome(f"p{i}", "success")
    assert len(opt.get_optimization_history(limit=3)) == 3


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    opt = get_workflow_optimizer()
    opt.record_outcome("p1", "success")
    opt.record_outcome("p2", "failure")
    s = opt.stats()
    assert "total_records" in s
    assert "by_outcome" in s
    assert s["total_records"] == 2


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    assert get_workflow_optimizer() is get_workflow_optimizer()


def test_reset_creates_fresh():
    a = get_workflow_optimizer()
    reset_workflow_optimizer_for_tests()
    b = get_workflow_optimizer()
    assert a is not b
