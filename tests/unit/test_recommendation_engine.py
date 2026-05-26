"""
Unit tests for src.runtime.recommendation_engine.

Covers:
  • recommend_workflow: known intent → recommended_op set
  • recommend_workflow: unknown intent → confidence 0
  • recommend_workflow: missing capability → confidence reduced
  • recommend_template: built-in mapping → candidate returned
  • recommend_template: unknown intent → recommended_template None
  • recommend_strategy: always includes dry_run_first
  • recommend_strategy: delete ops → wrap_transaction present
  • recommend_strategy: large batch → split_batch present
  • recommend_dependency_resolution: self_connection → resolution present
  • recommend_dependency_resolution: missing_source_node → resolution present
  • recommend_dependency_resolution: all_resolvable for known types
  • recommend_dependency_resolution: cycle → all_resolvable False
  • stats.recommendation_count increments
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.recommendation_engine import (
    RecommendationEngine,
    get_recommendation_engine,
    reset_recommendation_engine_for_tests,
)
from src.runtime.capability_registry import reset_capability_registry_for_tests
from src.runtime.workflow_templates import reset_workflow_templates_for_tests
from src.runtime.semantic_registry import reset_semantic_registry_for_tests


@pytest.fixture(autouse=True)
def _reset():
    reset_recommendation_engine_for_tests()
    reset_capability_registry_for_tests()
    reset_workflow_templates_for_tests()
    reset_semantic_registry_for_tests()
    yield
    reset_recommendation_engine_for_tests()
    reset_capability_registry_for_tests()
    reset_workflow_templates_for_tests()
    reset_semantic_registry_for_tests()


# ---------------------------------------------------------------------------
# recommend_workflow
# ---------------------------------------------------------------------------

def test_recommend_workflow_known_intent():
    engine = get_recommendation_engine()
    result = engine.recommend_workflow("build_pyro_source")
    assert result["recommended_op"] is not None
    assert result["confidence"] > 0.0


def test_recommend_workflow_unknown_intent():
    engine = get_recommendation_engine()
    result = engine.recommend_workflow("completely_unknown_xyz")
    assert result["confidence"] == 0.0


def test_recommend_workflow_missing_karma_cap():
    engine = get_recommendation_engine()
    result = engine.recommend_workflow("setup_karma_renderer",
                                       context={"available_capabilities": []})
    assert result["confidence"] < 0.9   # degraded due to missing capability


def test_recommend_workflow_has_reasoning():
    engine = get_recommendation_engine()
    result = engine.recommend_workflow("build_pyro_source")
    assert len(result["reasoning"]) >= 1


# ---------------------------------------------------------------------------
# recommend_template
# ---------------------------------------------------------------------------

def test_recommend_template_known_intent():
    engine = get_recommendation_engine()
    result = engine.recommend_template("build_pyro_source")
    assert result["recommended_template"] is not None
    assert len(result["all_candidates"]) >= 1


def test_recommend_template_unknown_intent():
    engine = get_recommendation_engine()
    result = engine.recommend_template("xyz_totally_unknown_2938")
    assert result["recommended_template"] is None


def test_recommend_template_has_reasoning():
    engine = get_recommendation_engine()
    result = engine.recommend_template("build_pyro_source")
    assert len(result["reasoning"]) >= 1


# ---------------------------------------------------------------------------
# recommend_strategy
# ---------------------------------------------------------------------------

def test_recommend_strategy_includes_dry_run():
    engine = get_recommendation_engine()
    result = engine.recommend_strategy([])
    ids = {s["id"] for s in result["strategies"]}
    assert "dry_run_first" in ids


def test_recommend_strategy_delete_adds_transaction():
    engine = get_recommendation_engine()
    ops = [{"op": "delete_node", "path": "/obj/x"}]
    result = engine.recommend_strategy(ops)
    ids = {s["id"] for s in result["strategies"]}
    assert "wrap_transaction" in ids


def test_recommend_strategy_large_batch_splits():
    engine = get_recommendation_engine()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": f"g{i}"}
           for i in range(15)]
    result = engine.recommend_strategy(ops)
    ids = {s["id"] for s in result["strategies"]}
    assert "split_batch" in ids


def test_recommend_strategy_primary_is_set():
    engine = get_recommendation_engine()
    result = engine.recommend_strategy([])
    assert result["primary"] is not None


# ---------------------------------------------------------------------------
# recommend_dependency_resolution
# ---------------------------------------------------------------------------

def test_recommend_dependency_resolution_self_connection():
    engine = get_recommendation_engine()
    conflicts = [{"type": "self_connection", "op_index": 0,
                  "explanation": "node connects to itself"}]
    result = engine.recommend_dependency_resolution(conflicts)
    assert len(result["resolutions"]) == 1
    assert "self" in result["resolutions"][0]["resolution"].lower()


def test_recommend_dependency_resolution_missing_source():
    engine = get_recommendation_engine()
    conflicts = [{"type": "missing_source_node", "op_index": 1,
                  "explanation": "source node not found"}]
    result = engine.recommend_dependency_resolution(conflicts)
    assert result["all_resolvable"] is True


def test_recommend_dependency_resolution_cycle_not_resolvable():
    engine = get_recommendation_engine()
    conflicts = [{"type": "cycle", "op_index": 2,
                  "explanation": "circular dependency"}]
    result = engine.recommend_dependency_resolution(conflicts)
    assert result["all_resolvable"] is False


def test_recommend_dependency_resolution_empty():
    engine = get_recommendation_engine()
    result = engine.recommend_dependency_resolution([])
    assert result["resolutions"] == []
    assert result["all_resolvable"] is True


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_recommendation_count():
    engine = get_recommendation_engine()
    engine.recommend_workflow("build_pyro_source")
    engine.recommend_template("build_pyro_source")
    engine.recommend_strategy([])
    assert engine.stats()["recommendation_count"] == 3


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    assert get_recommendation_engine() is get_recommendation_engine()


def test_reset_creates_fresh():
    a = get_recommendation_engine()
    reset_recommendation_engine_for_tests()
    b = get_recommendation_engine()
    assert a is not b
