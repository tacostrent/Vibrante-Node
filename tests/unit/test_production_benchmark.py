"""Tests for ProductionBenchmark (Tier 11 — §31)."""
import pytest
from src.runtime.studio.production_benchmark import (
    ProductionBenchmark,
    get_production_benchmark,
    reset_production_benchmark_for_tests,
    _STUDIO_AVERAGE_FALLBACK,
)
from src.runtime.studio.studio_knowledge import reset_studio_knowledge_db_for_tests
from src.runtime.studio.studio_metrics import reset_studio_metrics_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_production_benchmark_for_tests()
    reset_studio_knowledge_db_for_tests()
    reset_studio_metrics_for_tests()
    yield
    reset_production_benchmark_for_tests()
    reset_studio_knowledge_db_for_tests()
    reset_studio_metrics_for_tests()


def test_singleton():
    assert get_production_benchmark() is get_production_benchmark()


# ---------------------------------------------------------------------------
# benchmark_project
# ---------------------------------------------------------------------------

def test_benchmark_project_above_average():
    bench = ProductionBenchmark()
    result = bench.benchmark_project("proj_1", _STUDIO_AVERAGE_FALLBACK + 0.10)
    assert result["performance"] == "above_average"
    assert result["difference"] > 0
    assert result["percentile"] >= 65


def test_benchmark_project_below_average():
    bench = ProductionBenchmark()
    result = bench.benchmark_project("proj_2", _STUDIO_AVERAGE_FALLBACK - 0.10)
    assert result["performance"] == "below_average"
    assert result["difference"] < 0


def test_benchmark_project_average():
    bench = ProductionBenchmark()
    result = bench.benchmark_project("proj_3", _STUDIO_AVERAGE_FALLBACK)
    assert result["performance"] == "average"


def test_benchmark_project_required_keys():
    bench = ProductionBenchmark()
    result = bench.benchmark_project("p", 0.80)
    for key in ("project_id", "project_score", "studio_average", "difference",
                "performance", "percentile", "recommendations"):
        assert key in result


def test_benchmark_project_recommendations_above():
    bench = ProductionBenchmark()
    result = bench.benchmark_project("p", _STUDIO_AVERAGE_FALLBACK + 0.20)
    assert any("pattern" in r.lower() or "capture" in r.lower()
               for r in result["recommendations"])


def test_benchmark_project_recommendations_below():
    bench = ProductionBenchmark()
    result = bench.benchmark_project("p", _STUDIO_AVERAGE_FALLBACK - 0.20)
    assert any("below" in r.lower() or "review" in r.lower()
               for r in result["recommendations"])


# ---------------------------------------------------------------------------
# benchmark_workflow
# ---------------------------------------------------------------------------

def test_benchmark_workflow_no_history():
    bench = ProductionBenchmark()
    result = bench.benchmark_workflow("unknown_pack", 0.80)
    assert result["workflow"] == "unknown_pack"
    assert result["sample_count"] == 0
    assert result["historical_average"] == _STUDIO_AVERAGE_FALLBACK


def test_benchmark_workflow_with_history():
    from src.runtime.studio.studio_knowledge import get_studio_knowledge_db
    sk = get_studio_knowledge_db()
    sk.record_success("pack_a", "industrial_hangar", score=0.85)
    sk.record_success("pack_a", "industrial_hangar", score=0.90)

    bench = ProductionBenchmark()
    result = bench.benchmark_workflow("pack_a", 0.92)
    assert result["sample_count"] == 2
    assert result["historical_average"] > 0
    assert "performance" in result


def test_benchmark_workflow_required_keys():
    bench = ProductionBenchmark()
    result = bench.benchmark_workflow("pack_x", 0.80)
    for key in ("workflow", "workflow_score", "historical_average", "difference",
                "performance", "sample_count"):
        assert key in result


# ---------------------------------------------------------------------------
# benchmark_review
# ---------------------------------------------------------------------------

def test_benchmark_review_required_keys():
    bench = ProductionBenchmark()
    result = bench.benchmark_review("B", 0.82)
    for key in ("grade", "score", "studio_review_average", "difference", "performance"):
        assert key in result


def test_benchmark_review_score_range():
    bench = ProductionBenchmark()
    result = bench.benchmark_review("A", 0.95)
    assert 0.0 <= result["studio_review_average"] <= 1.0


# ---------------------------------------------------------------------------
# benchmark_environment
# ---------------------------------------------------------------------------

def test_benchmark_environment_required_keys():
    bench = ProductionBenchmark()
    result = bench.benchmark_environment("industrial_hangar", 0.85)
    for key in ("environment", "score", "environment_average", "difference", "performance"):
        assert key in result


def test_benchmark_environment_performance_values():
    bench = ProductionBenchmark()
    result = bench.benchmark_environment("robotics_lab", 0.5)
    assert result["performance"] in ("above_average", "below_average", "average")


# ---------------------------------------------------------------------------
# generate_benchmark_report
# ---------------------------------------------------------------------------

def test_generate_benchmark_report_required_keys():
    bench = ProductionBenchmark()
    report = bench.generate_benchmark_report("proj_1", 0.85)
    for key in ("project_id", "project_score", "studio_average", "project_benchmark", "summary"):
        assert key in report


def test_generate_benchmark_report_summary_string():
    bench = ProductionBenchmark()
    report = bench.generate_benchmark_report("proj_1", 0.85)
    assert "proj_1" in report["summary"]
    assert "0.85" in report["summary"]


def test_generate_benchmark_report_with_workflow_and_env():
    bench = ProductionBenchmark()
    report = bench.generate_benchmark_report(
        "proj_1", 0.88,
        workflow="industrial_hangar_pack",
        environment="industrial_hangar",
    )
    assert "workflow_benchmark" in report
    assert "environment_benchmark" in report


def test_generate_benchmark_report_with_reviews():
    bench = ProductionBenchmark()
    reviews = [{"score": 0.85}, {"score": 0.90}, {"score": 0.78}]
    report = bench.generate_benchmark_report("proj_1", 0.85, reviews=reviews)
    assert "review_benchmark" in report


# ---------------------------------------------------------------------------
# _estimate_percentile
# ---------------------------------------------------------------------------

def test_percentile_high_diff():
    bench = ProductionBenchmark()
    assert bench._estimate_percentile(0.15) == 90


def test_percentile_negative_diff():
    bench = ProductionBenchmark()
    assert bench._estimate_percentile(-0.15) == 10


def test_percentile_zero_diff():
    bench = ProductionBenchmark()
    assert bench._estimate_percentile(0.0) == 55


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------

def test_stats_key():
    bench = ProductionBenchmark()
    assert "benchmark_count" in bench.stats()


def test_stats_increments():
    bench = ProductionBenchmark()
    bench.benchmark_project("p", 0.8)
    bench.benchmark_project("p", 0.9)
    assert bench.stats()["benchmark_count"] >= 2
