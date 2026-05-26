"""
Unit tests for src.runtime.predictive_execution.

Covers:
  • predict empty ops → low risk, 0.0 probability
  • predict unknown op types → high risk
  • predict large batch → includes risk factor
  • predict high delete count → high risk factor
  • predict cook-before-connect ordering factor
  • predict self-connection in ops → conflict detected
  • predict_resource_pressure: heavy node types → high memory/cook
  • predict_dependency_conflicts: self-connection found
  • predict_dependency_conflicts: no conflicts → safe=True
  • predict_scheduler_congestion: none / mild / severe thresholds
  • recommendations always present in predict output
  • confidence in [0.0, 1.0]
  • stats.prediction_count increments
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.predictive_execution import (
    PredictiveExecution,
    get_predictive_engine,
    reset_predictive_engine_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_predictive_engine_for_tests()
    yield
    reset_predictive_engine_for_tests()


# ---------------------------------------------------------------------------
# predict — basic cases
# ---------------------------------------------------------------------------

def test_predict_empty_low_risk():
    engine = get_predictive_engine()
    result = engine.predict([])
    assert result["predicted_risk"] == "low"
    assert result["failure_probability"] == 0.0


def test_predict_unknown_op_high_risk():
    engine = get_predictive_engine()
    result = engine.predict([{"op": "totally_unknown_operation"}])
    factor_types = {f["factor"] for f in result["risk_factors"]}
    assert "unknown_op_types" in factor_types
    assert result["predicted_risk"] == "high"


def test_predict_large_batch_includes_factor():
    engine = get_predictive_engine()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": f"g{i}"} for i in range(25)]
    result = engine.predict(ops)
    factor_types = {f["factor"] for f in result["risk_factors"]}
    assert "large_batch" in factor_types


def test_predict_high_delete_count():
    engine = get_predictive_engine()
    ops = [{"op": "delete_node", "path": f"/obj/n{i}"} for i in range(6)]
    result = engine.predict(ops)
    factor_types = {f["factor"] for f in result["risk_factors"]}
    assert "high_delete_count" in factor_types
    assert result["predicted_risk"] == "high"


def test_predict_cook_before_connect_factor():
    engine = get_predictive_engine()
    ops = [
        {"op": "cook_node", "path": "/obj/geo"},
        {"op": "connect_nodes", "from": "/obj/a", "to": "/obj/b"},
    ]
    result = engine.predict(ops)
    factor_types = {f["factor"] for f in result["risk_factors"]}
    assert "cook_before_connect" in factor_types


def test_predict_recommendations_always_present():
    engine = get_predictive_engine()
    result = engine.predict([{"op": "delete_node", "path": "/obj/x"}])
    assert isinstance(result["recommendations"], list)


def test_predict_confidence_in_range():
    engine = get_predictive_engine()
    result = engine.predict([{"op": "create_node", "parent": "/obj", "type": "geo", "name": "g1"}])
    assert 0.0 <= result["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# predict — high risk score
# ---------------------------------------------------------------------------

def test_predict_high_risk_score_factor():
    engine = get_predictive_engine()
    # single delete_node = risk 10 → triggers high_risk_score factor
    ops = [{"op": "delete_node", "path": "/obj/x"}]
    result = engine.predict(ops)
    factor_types = {f["factor"] for f in result["risk_factors"]}
    assert "high_risk_score" in factor_types


# ---------------------------------------------------------------------------
# predict_resource_pressure
# ---------------------------------------------------------------------------

def test_predict_resource_pressure_normal():
    engine = get_predictive_engine()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": "g1"}]
    result = engine.predict_resource_pressure(ops)
    assert "memory_pressure" in result
    assert "cook_pressure" in result
    assert "estimated_cooks" in result


def test_predict_resource_pressure_heavy_type():
    engine = get_predictive_engine()
    ops = [{"op": "create_node", "parent": "/obj", "type": "pyro", "name": "fire"}]
    result = engine.predict_resource_pressure(ops)
    assert result["memory_pressure"] == "high"
    assert "pyro" in result["heavy_ops"]


def test_predict_resource_pressure_cook_count():
    engine = get_predictive_engine()
    ops = [{"op": "cook_node", "path": f"/obj/g{i}"} for i in range(5)]
    result = engine.predict_resource_pressure(ops)
    assert result["estimated_cooks"] == 5
    assert result["cook_pressure"] == "high"


# ---------------------------------------------------------------------------
# predict_dependency_conflicts
# ---------------------------------------------------------------------------

def test_predict_dependency_conflicts_self_connection():
    engine = get_predictive_engine()
    ops = [{"op": "connect_nodes", "from": "/obj/same", "to": "/obj/same"}]
    result = engine.predict_dependency_conflicts(ops)
    assert result["conflict_count"] >= 1
    assert result["safe"] is False
    assert any(c["type"] == "self_connection" for c in result["conflicts"])


def test_predict_dependency_conflicts_no_conflicts():
    engine = get_predictive_engine()
    ops = [
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "a"},
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "b"},
    ]
    result = engine.predict_dependency_conflicts(ops)
    assert result["safe"] is True
    assert result["conflict_count"] == 0


# ---------------------------------------------------------------------------
# predict_scheduler_congestion
# ---------------------------------------------------------------------------

def test_predict_scheduler_congestion_none():
    engine = get_predictive_engine()
    result = engine.predict_scheduler_congestion(0)
    assert result["congested"] is False
    assert result["severity"] == "none"


def test_predict_scheduler_congestion_mild():
    engine = get_predictive_engine()
    result = engine.predict_scheduler_congestion(5)
    assert result["congested"] is True
    assert result["severity"] == "mild"


def test_predict_scheduler_congestion_severe():
    engine = get_predictive_engine()
    result = engine.predict_scheduler_congestion(15)
    assert result["congested"] is True
    assert result["severity"] == "severe"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_prediction_count():
    engine = get_predictive_engine()
    engine.predict([])
    engine.predict([])
    assert engine.stats()["prediction_count"] == 2


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    assert get_predictive_engine() is get_predictive_engine()


def test_reset_creates_fresh():
    a = get_predictive_engine()
    reset_predictive_engine_for_tests()
    b = get_predictive_engine()
    assert a is not b
