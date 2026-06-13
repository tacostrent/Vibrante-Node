"""Tests for CrossProjectLearning (Tier 11 — §31)."""
import pytest
from src.runtime.studio.cross_project_learning import (
    CrossProjectLearning,
    get_cross_project_learning,
    reset_cross_project_learning_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_cross_project_learning_for_tests()
    yield
    reset_cross_project_learning_for_tests()


def test_singleton():
    assert get_cross_project_learning() is get_cross_project_learning()


# ---------------------------------------------------------------------------
# identify_successful_patterns
# ---------------------------------------------------------------------------

def test_successful_patterns_empty():
    cpl = CrossProjectLearning()
    assert cpl.identify_successful_patterns([]) == []


def test_successful_patterns_requires_2_occurrences():
    cpl = CrossProjectLearning()
    records = [{"workflow": "pack_a", "score": 0.9, "environment": "industrial_hangar"}]
    patterns = cpl.identify_successful_patterns(records)
    assert patterns == []


def test_successful_patterns_requires_score_07():
    cpl = CrossProjectLearning()
    records = [
        {"workflow": "low_pack", "score": 0.5, "environment": "e"},
        {"workflow": "low_pack", "score": 0.5, "environment": "e"},
    ]
    patterns = cpl.identify_successful_patterns(records)
    assert patterns == []


def test_successful_patterns_found():
    cpl = CrossProjectLearning()
    records = [
        {"workflow": "pack_a", "score": 0.88, "environment": "industrial_hangar"},
        {"workflow": "pack_a", "score": 0.92, "environment": "industrial_hangar"},
        {"workflow": "pack_b", "score": 0.85, "environment": "robotics_lab"},
        {"workflow": "pack_b", "score": 0.87, "environment": "robotics_lab"},
    ]
    patterns = cpl.identify_successful_patterns(records)
    assert len(patterns) == 2
    assert patterns[0]["pattern_type"] == "successful_workflow"
    # sorted by avg_score desc — pack_a has higher avg
    assert patterns[0]["workflow"] == "pack_a"


def test_successful_patterns_excludes_failures():
    cpl = CrossProjectLearning()
    records = [
        {"record_type": "failure", "workflow": "bad_pack", "score": 0.0},
        {"record_type": "failure", "workflow": "bad_pack", "score": 0.0},
        {"workflow": "good_pack", "score": 0.85},
        {"workflow": "good_pack", "score": 0.90},
    ]
    patterns = cpl.identify_successful_patterns(records)
    workflows = [p["workflow"] for p in patterns]
    assert "bad_pack" not in workflows
    assert "good_pack" in workflows


# ---------------------------------------------------------------------------
# identify_failed_patterns
# ---------------------------------------------------------------------------

def test_failed_patterns_empty():
    cpl = CrossProjectLearning()
    assert cpl.identify_failed_patterns([]) == []


def test_failed_patterns_requires_2():
    cpl = CrossProjectLearning()
    records = [{"record_type": "failure", "failure_type": "fog_high", "environment": "e"}]
    patterns = cpl.identify_failed_patterns(records)
    assert patterns == []


def test_failed_patterns_found():
    cpl = CrossProjectLearning()
    records = [
        {"record_type": "failure", "failure_type": "fog_high", "environment": "industrial_hangar"},
        {"record_type": "failure", "failure_type": "fog_high", "environment": "industrial_hangar"},
        {"record_type": "failure", "failure_type": "fog_high", "environment": "industrial_hangar"},
    ]
    patterns = cpl.identify_failed_patterns(records)
    assert len(patterns) == 1
    assert patterns[0]["failure_type"] == "fog_high"
    assert patterns[0]["risk_level"] == "medium"


def test_failed_patterns_risk_levels():
    cpl = CrossProjectLearning()
    records = [{"record_type": "failure", "failure_type": "x", "environment": "e"}] * 6
    patterns = cpl.identify_failed_patterns(records)
    assert patterns[0]["risk_level"] == "high"


# ---------------------------------------------------------------------------
# extract_best_workflows
# ---------------------------------------------------------------------------

def test_extract_best_workflows_empty():
    cpl = CrossProjectLearning()
    assert cpl.extract_best_workflows([]) == []


def test_extract_best_workflows_top_k():
    cpl = CrossProjectLearning()
    records = [{"workflow": f"pack_{i}", "score": float(i) / 10} for i in range(1, 8)]
    best = cpl.extract_best_workflows(records, top_k=3)
    assert len(best) == 3
    assert best[0]["average_score"] >= best[1]["average_score"]


def test_extract_best_workflows_recommended_flag():
    cpl = CrossProjectLearning()
    records = [
        {"workflow": "good", "score": 0.85},
        {"workflow": "bad", "score": 0.5},
    ]
    best = cpl.extract_best_workflows(records, top_k=5)
    good = next(w for w in best if w["workflow"] == "good")
    bad = next(w for w in best if w["workflow"] == "bad")
    assert good["recommended"] is True
    assert bad["recommended"] is False


# ---------------------------------------------------------------------------
# extract_best_lighting / camera / atmosphere
# ---------------------------------------------------------------------------

def test_extract_best_lighting_none_when_empty():
    cpl = CrossProjectLearning()
    assert cpl.extract_best_lighting([]) is None


def test_extract_best_lighting_found():
    cpl = CrossProjectLearning()
    records = [
        {"lighting_style": "cinematic_industrial", "score": 0.9},
        {"lighting_style": "cinematic_industrial", "score": 0.85},
        {"lighting_style": "cold_scifi", "score": 0.6},
    ]
    best = cpl.extract_best_lighting(records)
    assert best == "cinematic_industrial"


def test_extract_best_camera_found():
    cpl = CrossProjectLearning()
    records = [
        {"camera_mode": "cinematic_push_in", "score": 0.88},
        {"camera_mode": "orbital_reveal", "score": 0.7},
    ]
    assert cpl.extract_best_camera(records) == "cinematic_push_in"


def test_extract_best_atmosphere_found():
    cpl = CrossProjectLearning()
    records = [
        {"atmosphere_type": "industrial_fog", "score": 0.9},
        {"atmosphere_type": "dusty_hangar", "score": 0.65},
    ]
    assert cpl.extract_best_atmosphere(records) == "industrial_fog"


# ---------------------------------------------------------------------------
# build_learning_report
# ---------------------------------------------------------------------------

def test_build_learning_report_empty():
    cpl = CrossProjectLearning()
    report = cpl.build_learning_report([])
    assert report["record_count"] == 0
    assert report["best_workflow"] is None
    assert isinstance(report["recommendations"], list)


def test_build_learning_report_required_keys():
    cpl = CrossProjectLearning()
    records = [
        {"workflow": "pack_a", "score": 0.9, "lighting_style": "cinematic_industrial",
         "camera_mode": "cinematic_push_in", "atmosphere_type": "industrial_fog"},
        {"workflow": "pack_a", "score": 0.88, "lighting_style": "cinematic_industrial",
         "camera_mode": "cinematic_push_in", "atmosphere_type": "industrial_fog"},
    ]
    report = cpl.build_learning_report(records)
    for key in ("record_count", "best_workflow", "best_lighting", "best_camera",
                "best_atmosphere", "successful_patterns", "failed_patterns",
                "top_workflows", "recommendations"):
        assert key in report, f"Missing key: {key}"


def test_build_learning_report_increments_analysis_count():
    cpl = CrossProjectLearning()
    cpl.build_learning_report([])
    cpl.build_learning_report([])
    assert cpl.stats()["analysis_count"] == 2


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------

def test_stats_key():
    cpl = CrossProjectLearning()
    assert "analysis_count" in cpl.stats()
