"""Tests for StudioMetrics (Tier 11 — §31)."""
import pytest
from src.runtime.studio.studio_metrics import (
    StudioMetrics,
    get_studio_metrics,
    reset_studio_metrics_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_studio_metrics_for_tests()
    yield
    reset_studio_metrics_for_tests()


def test_singleton():
    assert get_studio_metrics() is get_studio_metrics()


# ---------------------------------------------------------------------------
# record_metric
# ---------------------------------------------------------------------------

def test_record_metric_returns_id():
    sm = StudioMetrics()
    mid = sm.record_metric("execution_success", 1.0, workflow="pack_a")
    assert len(mid) == 36


def test_record_metric_stored():
    sm = StudioMetrics()
    sm.record_metric("review_score", 0.85, workflow="pack_a", environment="industrial_hangar")
    assert sm.stats()["total_metrics"] == 1
    assert sm.stats()["write_count"] == 1


# ---------------------------------------------------------------------------
# calculate_success_rate
# ---------------------------------------------------------------------------

def test_success_rate_empty():
    sm = StudioMetrics()
    assert sm.calculate_success_rate() == 0.0


def test_success_rate_all_success():
    sm = StudioMetrics()
    sm.record_metric("execution_success", 1.0, workflow="pack_a")
    sm.record_metric("execution_success", 1.0, workflow="pack_a")
    assert sm.calculate_success_rate() == 1.0


def test_success_rate_mixed():
    sm = StudioMetrics()
    sm.record_metric("execution_success", 1.0, workflow="pack_a")
    sm.record_metric("execution_failure", 0.0, workflow="pack_a")
    assert sm.calculate_success_rate() == 0.5


def test_success_rate_workflow_filter():
    sm = StudioMetrics()
    sm.record_metric("execution_success", 1.0, workflow="pack_a")
    sm.record_metric("execution_failure", 0.0, workflow="pack_b")
    assert sm.calculate_success_rate(workflow="pack_a") == 1.0
    assert sm.calculate_success_rate(workflow="pack_b") == 0.0


# ---------------------------------------------------------------------------
# calculate_quality_average
# ---------------------------------------------------------------------------

def test_quality_average_empty():
    sm = StudioMetrics()
    assert sm.calculate_quality_average() == 0.0


def test_quality_average_calculates():
    sm = StudioMetrics()
    sm.record_metric("review_score", 0.80, workflow="pack_a")
    sm.record_metric("review_score", 0.90, workflow="pack_a")
    assert abs(sm.calculate_quality_average() - 0.85) < 1e-3


def test_quality_average_workflow_filter():
    sm = StudioMetrics()
    sm.record_metric("review_score", 0.9, workflow="pack_a")
    sm.record_metric("review_score", 0.5, workflow="pack_b")
    assert sm.calculate_quality_average(workflow="pack_a") > sm.calculate_quality_average(workflow="pack_b")


# ---------------------------------------------------------------------------
# calculate_workflow_performance
# ---------------------------------------------------------------------------

def test_workflow_performance_no_data():
    sm = StudioMetrics()
    perf = sm.calculate_workflow_performance("nonexistent_pack")
    assert perf["total"] == 0
    assert perf["success_rate"] == 0.0


def test_workflow_performance_with_data():
    sm = StudioMetrics()
    sm.record_metric("execution_success", 1.0, workflow="pack_a")
    sm.record_metric("execution_success", 1.0, workflow="pack_a")
    sm.record_metric("execution_failure", 0.0, workflow="pack_a")
    sm.record_metric("review_score", 0.85, workflow="pack_a")
    perf = sm.calculate_workflow_performance("pack_a")
    assert perf["total"] == 4
    assert perf["successes"] == 2
    assert abs(perf["success_rate"] - 2 / 4) < 1e-3
    assert abs(perf["avg_score"] - 0.85) < 1e-3


# ---------------------------------------------------------------------------
# calculate_review_performance
# ---------------------------------------------------------------------------

def test_review_performance_empty():
    sm = StudioMetrics()
    perf = sm.calculate_review_performance()
    assert perf["total_reviews"] == 0
    assert perf["avg_score"] == 0.0
    assert perf["passing_rate"] == 0.0


def test_review_performance_passing_rate():
    sm = StudioMetrics()
    sm.record_metric("review_score", 0.8, workflow="pack_a")   # passing
    sm.record_metric("review_score", 0.9, workflow="pack_a")   # passing
    sm.record_metric("review_score", 0.5, workflow="pack_a")   # failing
    perf = sm.calculate_review_performance()
    assert perf["total_reviews"] == 3
    assert abs(perf["passing_rate"] - 2 / 3) < 1e-3


# ---------------------------------------------------------------------------
# generate_metrics_report
# ---------------------------------------------------------------------------

def test_generate_metrics_report_keys():
    sm = StudioMetrics()
    report = sm.generate_metrics_report()
    for key in ("total_metrics", "overall_success_rate", "overall_quality_average",
                "review_performance", "workflow_performance"):
        assert key in report


def test_generate_metrics_report_workflow_list():
    sm = StudioMetrics()
    sm.record_metric("execution_success", 1.0, workflow="pack_a")
    sm.record_metric("execution_success", 1.0, workflow="pack_b")
    report = sm.generate_metrics_report()
    wf_names = [p["workflow"] for p in report["workflow_performance"]]
    assert "pack_a" in wf_names
    assert "pack_b" in wf_names


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------

def test_stats_keys():
    sm = StudioMetrics()
    s = sm.stats()
    assert "total_metrics" in s
    assert "write_count" in s


def test_stats_increments():
    sm = StudioMetrics()
    sm.record_metric("review_score", 0.8)
    sm.record_metric("review_score", 0.9)
    assert sm.stats()["write_count"] == 2
    assert sm.stats()["total_metrics"] == 2
