"""Tests for ReviewAnalytics (Tier 11 — §31)."""
import time
import pytest
from src.runtime.studio.review_analytics import (
    ReviewAnalytics,
    get_review_analytics,
    reset_review_analytics_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_review_analytics_for_tests()
    yield
    reset_review_analytics_for_tests()


def test_singleton():
    assert get_review_analytics() is get_review_analytics()


# ---------------------------------------------------------------------------
# analyze_reviews — empty
# ---------------------------------------------------------------------------

def test_analyze_empty_reviews():
    ra = ReviewAnalytics()
    result = ra.analyze_reviews([])
    assert result["total_reviews"] == 0
    assert result["average_score"] == 0.0
    assert result["pass_rate"] == 0.0
    assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# analyze_reviews — with data
# ---------------------------------------------------------------------------

def _make_reviews(scores):
    t = time.time()
    return [
        {"score": s, "grade": "A" if s >= 0.9 else "B" if s >= 0.8 else "C" if s >= 0.7 else "F",
         "workflow": "pack_a", "findings": [], "timestamp": t + i}
        for i, s in enumerate(scores)
    ]


def test_analyze_average_score():
    ra = ReviewAnalytics()
    reviews = _make_reviews([0.8, 0.9, 0.7])
    result = ra.analyze_reviews(reviews)
    assert abs(result["average_score"] - 0.8) < 1e-3


def test_analyze_pass_rate():
    ra = ReviewAnalytics()
    reviews = _make_reviews([0.8, 0.6, 0.9])  # 2 passing (>=0.7)
    result = ra.analyze_reviews(reviews)
    assert abs(result["pass_rate"] - 2 / 3) < 1e-3


def test_analyze_grade_distribution():
    ra = ReviewAnalytics()
    reviews = _make_reviews([0.95, 0.85, 0.65])
    result = ra.analyze_reviews(reviews)
    assert "A" in result["grade_distribution"]
    assert "B" in result["grade_distribution"]


def test_analyze_increments_analysis_count():
    ra = ReviewAnalytics()
    ra.analyze_reviews([])
    ra.analyze_reviews([])
    assert ra.stats()["analysis_count"] == 2


# ---------------------------------------------------------------------------
# find_common_failures
# ---------------------------------------------------------------------------

def test_find_common_failures_empty():
    ra = ReviewAnalytics()
    assert ra.find_common_failures([]) == []


def test_find_common_failures_counts():
    ra = ReviewAnalytics()
    reviews = [
        {"findings": ["fog_too_dense", "no_hero"], "score": 0.5},
        {"findings": ["fog_too_dense"], "score": 0.6},
        {"findings": ["fog_too_dense"], "score": 0.55},
    ]
    failures = ra.find_common_failures(reviews)
    assert failures[0]["finding"] == "fog_too_dense"
    assert failures[0]["count"] == 3


def test_find_common_failures_top_k():
    ra = ReviewAnalytics()
    reviews = [
        {"findings": [f"issue_{i}" for i in range(10)], "score": 0.5}
        for _ in range(3)
    ]
    failures = ra.find_common_failures(reviews, top_k=3)
    assert len(failures) == 3


# ---------------------------------------------------------------------------
# find_common_successes
# ---------------------------------------------------------------------------

def test_find_common_successes_empty():
    ra = ReviewAnalytics()
    assert ra.find_common_successes([]) == []


def test_find_common_successes_only_passing():
    ra = ReviewAnalytics()
    reviews = [
        {"workflow": "good_pack", "score": 0.85, "findings": []},
        {"workflow": "good_pack", "score": 0.90, "findings": []},
        {"workflow": "bad_pack", "score": 0.50, "findings": []},  # failing — excluded
    ]
    successes = ra.find_common_successes(reviews)
    assert successes[0]["workflow"] == "good_pack"
    assert successes[0]["count"] == 2


# ---------------------------------------------------------------------------
# analyze_trends
# ---------------------------------------------------------------------------

def test_analyze_trends_insufficient_data():
    ra = ReviewAnalytics()
    result = ra.analyze_trends([])
    assert result["trend_direction"] == "insufficient_data"
    result2 = ra.analyze_trends([{"score": 0.8, "timestamp": 1.0}])
    assert result2["trend_direction"] == "insufficient_data"


def test_analyze_trends_improving():
    ra = ReviewAnalytics()
    t = time.time()
    old = [{"score": 0.5, "timestamp": t - 100 + i} for i in range(5)]
    recent = [{"score": 0.9, "timestamp": t + i} for i in range(5)]
    result = ra.analyze_trends(old + recent, window_size=5)
    assert result["trend_direction"] == "improving"
    assert result["trend_score"] > 0


def test_analyze_trends_declining():
    ra = ReviewAnalytics()
    t = time.time()
    old = [{"score": 0.9, "timestamp": t - 100 + i} for i in range(5)]
    recent = [{"score": 0.4, "timestamp": t + i} for i in range(5)]
    result = ra.analyze_trends(old + recent, window_size=5)
    assert result["trend_direction"] == "declining"


# ---------------------------------------------------------------------------
# generate_review_report
# ---------------------------------------------------------------------------

def test_generate_review_report_keys():
    ra = ReviewAnalytics()
    report = ra.generate_review_report(_make_reviews([0.9, 0.8, 0.5]))
    for key in ("most_common_failure", "most_common_success", "analysis", "trends", "recommendations"):
        assert key in report


def test_generate_review_report_recommendations_when_low_pass_rate():
    ra = ReviewAnalytics()
    reviews = _make_reviews([0.4, 0.3, 0.2])  # all failing
    report = ra.generate_review_report(reviews)
    assert any("Pass rate" in r or "below" in r for r in report["recommendations"])


def test_generate_review_report_positive_recommendation():
    ra = ReviewAnalytics()
    reviews = _make_reviews([0.9, 0.88, 0.92])
    report = ra.generate_review_report(reviews)
    assert any("above standard" in r or "maintain" in r for r in report["recommendations"])


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------

def test_stats_key():
    ra = ReviewAnalytics()
    assert "analysis_count" in ra.stats()
    assert ra.stats()["analysis_count"] == 0
