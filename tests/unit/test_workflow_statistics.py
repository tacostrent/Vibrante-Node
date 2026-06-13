"""Tests for WorkflowStatistics (Tier 10 — §30)."""
import pytest
from src.runtime.workflows.workflow_statistics import (
    WorkflowStatistics,
    get_workflow_statistics,
    reset_workflow_statistics_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_workflow_statistics_for_tests()
    yield
    reset_workflow_statistics_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_workflow_statistics() is get_workflow_statistics()


# ---------------------------------------------------------------------------
# record_execution / record_success / record_failure
# ---------------------------------------------------------------------------

def test_record_execution():
    stats = get_workflow_statistics()
    stats.record_execution("my_pack", "committed", score=0.85, grade="B")
    data = stats.get_pack_statistics("my_pack")
    assert data["executions"] == 1


def test_record_success():
    stats = get_workflow_statistics()
    stats.record_success("my_pack", score=0.90, grade="A")
    data = stats.get_pack_statistics("my_pack")
    assert data["successes"] == 1
    assert data["success_rate"] == 1.0


def test_record_failure():
    stats = get_workflow_statistics()
    stats.record_failure("my_pack")
    data = stats.get_pack_statistics("my_pack")
    assert data["failures"] == 1


def test_multiple_records():
    stats = get_workflow_statistics()
    stats.record_success("my_pack", score=0.90, grade="A")
    stats.record_success("my_pack", score=0.80, grade="B")
    stats.record_failure("my_pack")
    data = stats.get_pack_statistics("my_pack")
    assert data["executions"]  == 3
    assert data["successes"]   == 2
    assert data["failures"]    == 1
    assert abs(data["success_rate"] - 2/3) < 1e-6


# ---------------------------------------------------------------------------
# get_pack_statistics
# ---------------------------------------------------------------------------

def test_pack_statistics_no_records():
    data = get_workflow_statistics().get_pack_statistics("nonexistent")
    assert data["executions"]  == 0
    assert data["success_rate"] == 0.0
    assert data["average_score"] == 0.0


def test_pack_statistics_keys():
    stats = get_workflow_statistics()
    stats.record_success("my_pack", score=0.88, grade="B")
    data = stats.get_pack_statistics("my_pack")
    for key in ("workflow", "executions", "successes", "failures",
                "success_rate", "average_score", "average_duration",
                "grade_distribution"):
        assert key in data


def test_pack_statistics_average_score():
    stats = get_workflow_statistics()
    stats.record_success("p", score=0.80)
    stats.record_success("p", score=0.90)
    data  = stats.get_pack_statistics("p")
    assert abs(data["average_score"] - 0.85) < 1e-6


def test_pack_statistics_grade_distribution():
    stats = get_workflow_statistics()
    stats.record_success("p", score=0.90, grade="A")
    stats.record_success("p", score=0.80, grade="B")
    data  = stats.get_pack_statistics("p")
    dist  = data["grade_distribution"]
    assert dist.get("A") == 1
    assert dist.get("B") == 1


def test_dry_run_excluded_from_pack_stats():
    stats = get_workflow_statistics()
    stats.record_execution("p", "previewed", score=0.0, dry_run=True)
    stats.record_success("p", score=0.90)
    data = stats.get_pack_statistics("p")
    assert data["executions"] == 1   # dry_run excluded


# ---------------------------------------------------------------------------
# get_runtime_statistics
# ---------------------------------------------------------------------------

def test_runtime_statistics_empty():
    data = get_workflow_statistics().get_runtime_statistics()
    assert data["total_executions"] == 0
    assert data["success_rate"]     == 0.0


def test_runtime_statistics_keys():
    stats = get_workflow_statistics()
    stats.record_success("p", score=0.90)
    data  = stats.get_runtime_statistics()
    for key in ("total_executions", "total_previews", "success_rate",
                "average_score", "rollback_rate", "top_workflows", "write_count"):
        assert key in data


def test_runtime_statistics_top_workflows():
    stats = get_workflow_statistics()
    stats.record_success("a_pack", score=0.90)
    stats.record_success("a_pack", score=0.85)
    stats.record_success("b_pack", score=0.75)
    data  = stats.get_runtime_statistics()
    tops  = data["top_workflows"]
    assert len(tops) >= 1
    assert tops[0]["workflow"] == "a_pack"
    assert tops[0]["count"]    == 2


def test_runtime_statistics_rollback_rate():
    stats = get_workflow_statistics()
    stats.record_execution("p", "committed")
    stats.record_execution("p", "rolled_back")
    data  = stats.get_runtime_statistics()
    assert abs(data["rollback_rate"] - 0.5) < 1e-6


def test_runtime_statistics_previews_counted():
    stats = get_workflow_statistics()
    stats.record_execution("p", "previewed", dry_run=True)
    data  = stats.get_runtime_statistics()
    assert data["total_previews"] == 1


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

def test_clear():
    stats = get_workflow_statistics()
    stats.record_success("p", score=0.9)
    stats.clear()
    data = stats.get_runtime_statistics()
    assert data["total_executions"] == 0


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_write_count():
    s = get_workflow_statistics()
    s.record_success("p")
    s.record_failure("p")
    assert s.stats()["write_count"] == 2


def test_stats_record_count():
    s = get_workflow_statistics()
    s.record_success("p")
    assert s.stats()["record_count"] == 1
