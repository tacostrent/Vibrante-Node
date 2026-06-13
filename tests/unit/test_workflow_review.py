"""Tests for WorkflowReview (Tier 10 — §30)."""
import pytest
from src.runtime.workflows.workflow_review import (
    WorkflowReviewResult,
    WorkflowReview,
    get_workflow_review,
    reset_workflow_review_for_tests,
    _WEIGHTS,
)
from src.runtime.workflows.workflow_pack import (
    get_builtin_packs,
    reset_workflow_pack_for_tests,
)
from src.runtime.workflows.workflow_blueprint import (
    get_workflow_blueprint,
    reset_workflow_blueprint_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_workflow_review_for_tests()
    reset_workflow_pack_for_tests()
    reset_workflow_blueprint_for_tests()
    yield
    reset_workflow_review_for_tests()
    reset_workflow_pack_for_tests()
    reset_workflow_blueprint_for_tests()


def _hangar_pack():
    return next(p for p in get_builtin_packs() if p.name == "industrial_hangar_pack")


def _good_execution():
    return {
        "ok":            True,
        "status":        "committed",
        "operations":    [{"op": "create_node"}] * 5,
        "phase_results": [{"status": "ok"}] * 5,
        "errors":        [],
    }


def _failed_execution():
    return {
        "ok":            False,
        "status":        "rolled_back",
        "operations":    [],
        "phase_results": [],
        "errors":        ["bridge error"],
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_workflow_review() is get_workflow_review()


# ---------------------------------------------------------------------------
# Weight sanity
# ---------------------------------------------------------------------------

def test_weights_sum():
    total = sum(_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# review_execution
# ---------------------------------------------------------------------------

def test_review_execution_good():
    r = get_workflow_review().review_execution(_good_execution())
    assert r["score"] > 0.5
    assert r["status"] == "committed"
    assert r["findings"] == []


def test_review_execution_rolled_back():
    r = get_workflow_review().review_execution(_failed_execution())
    assert any("rolled" in f for f in r["findings"])


def test_review_execution_no_ops():
    r = get_workflow_review().review_execution({"status": "committed", "operations": []})
    assert any("empty" in f.lower() or "no" in f.lower() for f in r["findings"])


def test_review_execution_score_range():
    for exec_data in (_good_execution(), _failed_execution()):
        r = get_workflow_review().review_execution(exec_data)
        assert 0.0 <= r["score"] <= 1.0


# ---------------------------------------------------------------------------
# review_environment
# ---------------------------------------------------------------------------

def test_review_environment_good():
    pack      = _hangar_pack()
    blueprint = get_workflow_blueprint().build_blueprint(pack)
    r         = get_workflow_review().review_environment(blueprint)
    assert r["score"] > 0.0
    assert r["phase_count"] == 7


def test_review_environment_empty_blueprint():
    r = get_workflow_review().review_environment({"ok": False, "phases": [], "phase_details": []})
    assert r["score"] < 1.0
    assert r["findings"]


# ---------------------------------------------------------------------------
# review_cinematic_quality
# ---------------------------------------------------------------------------

def test_review_cinematic_hangar_pack():
    r = get_workflow_review().review_cinematic_quality(_hangar_pack())
    assert 0.0 <= r["score"] <= 1.0


def test_review_cinematic_heavy_fog_finding():
    pack = _hangar_pack()
    pack.atmosphere_strategy["fog_density"] = "heavy"
    r = get_workflow_review().review_cinematic_quality(pack)
    assert any("fog" in f.lower() or "heavy" in f.lower() for f in r["findings"])


def test_review_cinematic_no_volumetric_finding():
    pack = _hangar_pack()
    pack.lighting_strategy["volumetric"] = False
    r = get_workflow_review().review_cinematic_quality(pack)
    assert any("flat" in f.lower() or "volumetric" in f.lower() for f in r["findings"])


# ---------------------------------------------------------------------------
# review_production_quality
# ---------------------------------------------------------------------------

def test_review_production_passes():
    r = get_workflow_review().review_production_quality(_hangar_pack(), overall_score=0.85)
    assert r["passed"] is True
    assert r["findings"] == []


def test_review_production_fails():
    r = get_workflow_review().review_production_quality(_hangar_pack(), overall_score=0.50)
    assert r["passed"] is False
    assert r["findings"]


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------

def test_generate_report_structure():
    pack      = _hangar_pack()
    blueprint = get_workflow_blueprint().build_blueprint(pack)
    report    = get_workflow_review().generate_report(pack, blueprint, _good_execution())
    assert report.ok              is True
    assert report.grade           in ("A", "B", "C", "D", "F")
    assert 0.0 <= report.overall_score <= 1.0
    assert isinstance(report.dimensions, dict)
    assert len(report.dimensions) == 4


def test_generate_report_dimensions_keys():
    pack      = _hangar_pack()
    blueprint = get_workflow_blueprint().build_blueprint(pack)
    report    = get_workflow_review().generate_report(pack, blueprint, _good_execution())
    for dim in ("execution", "environment", "cinematic", "production"):
        assert dim in report.dimensions


def test_generate_report_summary_specific():
    pack      = _hangar_pack()
    blueprint = get_workflow_blueprint().build_blueprint(pack)
    report    = get_workflow_review().generate_report(pack, blueprint, _good_execution())
    # Must never be generic "Execution successful"
    assert "execution successful" not in report.review_summary.lower()
    assert pack.name in report.review_summary


def test_generate_report_failed_exec():
    pack      = _hangar_pack()
    blueprint = get_workflow_blueprint().build_blueprint(pack)
    report    = get_workflow_review().generate_report(pack, blueprint, _failed_execution())
    assert report.findings


def test_generate_report_to_dict():
    pack      = _hangar_pack()
    blueprint = get_workflow_blueprint().build_blueprint(pack)
    report    = get_workflow_review().generate_report(pack, blueprint, {})
    d         = report.to_dict()
    for key in ("ok", "workflow", "grade", "overall_score", "production_ready",
                "dimensions", "findings", "review_summary"):
        assert key in d


# ---------------------------------------------------------------------------
# WorkflowReviewResult
# ---------------------------------------------------------------------------

def test_review_result_grade():
    scores = [(0.95, "A"), (0.85, "B"), (0.75, "C"), (0.65, "D"), (0.50, "F")]
    for score, expected in scores:
        assert WorkflowReview._grade(score) == expected


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_increments():
    rev       = get_workflow_review()
    pack      = _hangar_pack()
    blueprint = get_workflow_blueprint().build_blueprint(pack)
    rev.generate_report(pack, blueprint, {})
    assert rev.stats()["review_count"] >= 1
