"""Tests for KnowledgeStatistics (Tier 11 — §31)."""
import pytest
from src.runtime.studio.knowledge_statistics import (
    KnowledgeStatistics,
    get_knowledge_statistics,
    reset_knowledge_statistics_for_tests,
)
from src.runtime.studio.studio_knowledge import reset_studio_knowledge_db_for_tests
from src.runtime.studio.studio_standards import reset_studio_standards_for_tests
from src.runtime.studio.studio_metrics import reset_studio_metrics_for_tests
from src.runtime.studio.project_memory import reset_project_memory_for_tests
from src.runtime.studio.knowledge_recommendation import reset_knowledge_recommendation_engine_for_tests
from src.runtime.studio.production_benchmark import reset_production_benchmark_for_tests
from src.runtime.studio.cross_project_learning import reset_cross_project_learning_for_tests
from src.runtime.studio.review_analytics import reset_review_analytics_for_tests
from src.runtime.studio.knowledge_serializer import reset_knowledge_serializer_for_tests


@pytest.fixture(autouse=True)
def reset_all():
    reset_knowledge_statistics_for_tests()
    reset_studio_knowledge_db_for_tests()
    reset_studio_standards_for_tests()
    reset_studio_metrics_for_tests()
    reset_project_memory_for_tests()
    reset_knowledge_recommendation_engine_for_tests()
    reset_production_benchmark_for_tests()
    reset_cross_project_learning_for_tests()
    reset_review_analytics_for_tests()
    reset_knowledge_serializer_for_tests()
    yield
    reset_knowledge_statistics_for_tests()


def test_singleton():
    assert get_knowledge_statistics() is get_knowledge_statistics()


# ---------------------------------------------------------------------------
# get_statistics
# ---------------------------------------------------------------------------

def test_get_statistics_returns_dict():
    ks = KnowledgeStatistics()
    stats = ks.get_statistics()
    assert isinstance(stats, dict)


def test_get_statistics_has_query_count():
    ks = KnowledgeStatistics()
    ks.get_statistics()
    assert ks.stats()["query_count"] == 1


def test_get_statistics_module_keys():
    ks = KnowledgeStatistics()
    stats = ks.get_statistics()
    # All studio modules should appear
    for key in ("studio_knowledge", "project_memory", "studio_standards",
                "studio_metrics", "knowledge_recommendation",
                "production_benchmark", "cross_project_learning",
                "review_analytics", "knowledge_serializer"):
        assert key in stats, f"Missing module key: {key}"


def test_get_statistics_no_crash_with_empty_modules():
    ks = KnowledgeStatistics()
    stats = ks.get_statistics()
    # Even with empty modules, no errors should propagate
    for key, val in stats.items():
        if isinstance(val, dict):
            assert "error" not in val or isinstance(val["error"], str)


def test_get_statistics_increments_query_count():
    ks = KnowledgeStatistics()
    ks.get_statistics()
    ks.get_statistics()
    ks.get_statistics()
    assert ks.stats()["query_count"] >= 3


# ---------------------------------------------------------------------------
# get_pattern_statistics
# ---------------------------------------------------------------------------

def test_get_pattern_statistics_returns_dict():
    ks = KnowledgeStatistics()
    result = ks.get_pattern_statistics()
    assert isinstance(result, dict)
    assert "total_patterns" in result
    assert "by_type" in result


def test_get_pattern_statistics_increments_count():
    ks = KnowledgeStatistics()
    ks.get_pattern_statistics()
    assert ks.stats()["query_count"] == 1


# ---------------------------------------------------------------------------
# get_workflow_statistics
# ---------------------------------------------------------------------------

def test_get_workflow_statistics_returns_dict():
    ks = KnowledgeStatistics()
    result = ks.get_workflow_statistics()
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# get_review_statistics
# ---------------------------------------------------------------------------

def test_get_review_statistics_returns_dict():
    ks = KnowledgeStatistics()
    result = ks.get_review_statistics()
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------

def test_stats_structure():
    ks = KnowledgeStatistics()
    s = ks.stats()
    assert "query_count" in s
    assert s["query_count"] == 0


def test_stats_counts_all_query_types():
    ks = KnowledgeStatistics()
    ks.get_statistics()
    ks.get_pattern_statistics()
    ks.get_workflow_statistics()
    ks.get_review_statistics()
    assert ks.stats()["query_count"] == 4
