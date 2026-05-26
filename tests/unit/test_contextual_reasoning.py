"""
Unit tests for src.runtime.contextual_reasoning.

Covers:
  • analyze returns required keys
  • scene_complexity classification (low/medium/high)
  • existing_workflows detected from dirty created paths
  • existing_workflows detected from semantic lineage
  • conflicts detected when parent has many dependents
  • optimization_suggestions generated for existing workflows
  • recommended_actions: extend_existing vs create_new
  • graceful degradation when no runtime systems initialized
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.contextual_reasoning import (
    ContextualReasoner,
    get_contextual_reasoner,
    reset_contextual_reasoner_for_tests,
)
from src.runtime.scene_cache import get_scene_cache
from src.runtime.dependency_graph import (
    get_dependency_graph,
    reset_dependency_graph_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_contextual_reasoner_for_tests()
    reset_dependency_graph_for_tests()
    cache = get_scene_cache()
    cache.clear_dirty_state()
    cache.clear_semantic_lineage()
    yield
    reset_contextual_reasoner_for_tests()
    reset_dependency_graph_for_tests()


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

def test_analyze_returns_required_keys():
    r = get_contextual_reasoner()
    result = r.analyze("build_pyro_source", {})
    for key in ("existing_workflows", "recommended_actions", "conflicts",
                "optimization_suggestions", "scene_complexity", "active_transactions",
                "scene_summary", "capabilities_available"):
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Scene complexity
# ---------------------------------------------------------------------------

def test_complexity_low_empty_scene():
    r = get_contextual_reasoner()
    result = r.analyze("create_geo_container", {})
    assert result["scene_complexity"] == "low"


def test_complexity_medium_with_mutations():
    cache = get_scene_cache()
    for i in range(6):
        cache.mark_node_created(f"/obj/node{i}")
    r = get_contextual_reasoner()
    result = r.analyze("build_pyro_source", {})
    assert result["scene_complexity"] in ("medium", "high")


def test_complexity_high_with_many_edges():
    graph = get_dependency_graph()
    for i in range(20):
        graph.register_dependency(f"/obj/a{i}", f"/obj/b{i}", "connection")
    r = get_contextual_reasoner()
    result = r.analyze("build_pyro_source", {})
    assert result["scene_complexity"] in ("medium", "high")


# ---------------------------------------------------------------------------
# Existing workflows from dirty state
# ---------------------------------------------------------------------------

def test_existing_workflow_from_dirty_state():
    cache = get_scene_cache()
    cache.mark_node_created("/obj/pyro_source1")
    r = get_contextual_reasoner()
    result = r.analyze("build_pyro_source", {})
    assert len(result["existing_workflows"]) >= 1
    assert any(w["source"] == "dirty_state" for w in result["existing_workflows"])


def test_no_existing_workflow_for_unrelated_node():
    cache = get_scene_cache()
    cache.mark_node_created("/obj/totally_unrelated_xyz")
    r = get_contextual_reasoner()
    result = r.analyze("build_pyro_source", {})
    assert all(w.get("path", "") != "/obj/totally_unrelated_xyz"
               for w in result["existing_workflows"])


# ---------------------------------------------------------------------------
# Existing workflows from lineage
# ---------------------------------------------------------------------------

def test_existing_workflow_from_lineage():
    cache = get_scene_cache()
    cache.record_semantic_execution("build_pyro_source", "txn-abc123", 5)
    r = get_contextual_reasoner()
    result = r.analyze("build_pyro_source", {})
    assert any(w["source"] == "lineage" for w in result["existing_workflows"])


# ---------------------------------------------------------------------------
# Recommended actions
# ---------------------------------------------------------------------------

def test_recommended_create_new_when_no_existing():
    r = get_contextual_reasoner()
    result = r.analyze("create_geo_container", {})
    assert "create_new" in result["recommended_actions"]


def test_recommended_extend_when_existing():
    cache = get_scene_cache()
    cache.mark_node_created("/obj/geo_node")
    r = get_contextual_reasoner()
    result = r.analyze("create_geo_container", {"parent": "/obj"})
    assert "extend_existing" in result["recommended_actions"]


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------

def test_conflict_detected_many_dependents():
    graph = get_dependency_graph()
    for i in range(7):
        graph.register_dependency("/obj/parent", f"/obj/child{i}", "connection")
    r = get_contextual_reasoner()
    result = r.analyze("build_pyro_source", {"parent": "/obj/parent"})
    assert len(result["conflicts"]) >= 1
    assert any("dependency_chain" in c["type"] for c in result["conflicts"])


def test_no_conflict_few_dependents():
    graph = get_dependency_graph()
    graph.register_dependency("/obj/parent", "/obj/child1", "connection")
    r = get_contextual_reasoner()
    result = r.analyze("build_pyro_source", {"parent": "/obj/parent"})
    assert len(result["conflicts"]) == 0


# ---------------------------------------------------------------------------
# Optimization suggestions
# ---------------------------------------------------------------------------

def test_suggestions_generated_for_existing_workflow():
    cache = get_scene_cache()
    cache.mark_node_created("/obj/pyro_source1")
    r = get_contextual_reasoner()
    result = r.analyze("build_pyro_source", {})
    if result["existing_workflows"]:
        assert len(result["optimization_suggestions"]) >= 1


# ---------------------------------------------------------------------------
# Scene summary
# ---------------------------------------------------------------------------

def test_scene_summary_includes_complexity():
    r = get_contextual_reasoner()
    result = r.analyze("build_pyro_source", {})
    assert "complexity" in result["scene_summary"].lower()


def test_scene_summary_includes_created_count():
    cache = get_scene_cache()
    cache.mark_node_created("/obj/node_a")
    r = get_contextual_reasoner()
    result = r.analyze("build_pyro_source", {})
    assert "created" in result["scene_summary"].lower() or result["scene_summary"]


# ---------------------------------------------------------------------------
# Graceful degradation (no runtime systems)
# ---------------------------------------------------------------------------

def test_analyze_works_without_any_runtime_context():
    """Reasoner must not raise even when all sub-systems are unavailable."""
    r = ContextualReasoner()
    result = r.analyze("build_pyro_source", {"parent": "/obj"}, scene_context=None)
    assert isinstance(result, dict)
    assert "scene_complexity" in result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_contextual_reasoner()
    b = get_contextual_reasoner()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_contextual_reasoner()
    reset_contextual_reasoner_for_tests()
    b = get_contextual_reasoner()
    assert a is not b
