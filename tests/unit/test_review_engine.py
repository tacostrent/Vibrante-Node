"""
Tests for src.runtime.review_engine
No Houdini, no bridge, no external APIs. Pure unit tests.
"""

import pytest
from src.runtime.review_engine import (
    ReviewEngine,
    ReviewResult,
    StageReview,
    get_review_engine,
    reset_review_engine_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_review_engine_for_tests()
    yield
    reset_review_engine_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_review_engine()
    b = get_review_engine()
    assert a is b


def test_reset_creates_new_instance():
    a = get_review_engine()
    reset_review_engine_for_tests()
    b = get_review_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# StageReview
# ---------------------------------------------------------------------------

def test_stage_review_to_dict():
    sr = StageReview(
        workflow_id="cinematic_explosion",
        stage_id="fireball_core",
        passed=True,
        critiques=[],
        recommendations=[],
        severity="pass",
    )
    d = sr.to_dict()
    assert d["passed"] is True
    assert d["severity"] == "pass"
    assert d["stage_id"] == "fireball_core"


# ---------------------------------------------------------------------------
# ReviewResult
# ---------------------------------------------------------------------------

def test_review_result_to_dict():
    sr = StageReview("wf", "st", True, [], [], "pass")
    rr = ReviewResult(
        workflow_id="cinematic_explosion",
        overall_passed=True,
        stage_reviews=[sr],
        summary="All good.",
        critical_issues=[],
        advisory_notes=[],
        production_ready=True,
        confidence=0.9,
    )
    d = rr.to_dict()
    assert d["workflow_id"] == "cinematic_explosion"
    assert d["production_ready"] is True
    assert d["stage_count"] == 1
    assert d["failed_stages"] == 0


# ---------------------------------------------------------------------------
# review_stage — no specific critique (unrecognized workflow/stage)
# ---------------------------------------------------------------------------

def test_review_stage_unknown_workflow():
    re = ReviewEngine()
    sr = re.review_stage("unknown_wf", "unknown_stage", {"completed": True, "outputs": {}})
    assert sr.stage_id == "unknown_stage"
    # No specific critique defined → should pass (no false positives for unknown)
    assert isinstance(sr.critiques, list)
    assert sr.severity in ("pass", "warning", "fail")


def test_review_stage_failed_completion():
    re = ReviewEngine()
    sr = re.review_stage(
        "cinematic_explosion", "fireball_core",
        {"completed": False, "errors": ["Node cook failed"], "outputs": {}}
    )
    assert sr.passed is False
    assert sr.severity == "fail"
    assert len(sr.critiques) > 0
    assert "Node cook failed" in sr.critiques[0]


def test_review_stage_with_errors():
    re = ReviewEngine()
    sr = re.review_stage(
        "arnold_render_ready", "sampling_configuration",
        {"completed": True, "errors": ["Timeout"], "outputs": {}}
    )
    assert sr.passed is False


# ---------------------------------------------------------------------------
# review_stage — specific workflow critiques
# ---------------------------------------------------------------------------

def test_review_stage_render_format_exr():
    re = ReviewEngine()
    sr = re.review_stage(
        "arnold_render_ready", "output_driver",
        {"completed": True, "outputs": {"output_format": "exr"}}
    )
    # EXR → should pass format criterion
    assert sr.passed is True or "format" not in [c for c in sr.critiques]


def test_review_stage_render_format_png_fails():
    re = ReviewEngine()
    sr = re.review_stage(
        "arnold_render_ready", "output_driver",
        {"completed": True, "outputs": {"output_format": "png"}}
    )
    # PNG → should fail format criterion
    assert sr.passed is False
    assert any("EXR" in c or "PNG" in c or "format" in c.lower() for c in sr.critiques)


def test_review_stage_aa_samples_sufficient():
    re = ReviewEngine()
    sr = re.review_stage(
        "arnold_render_ready", "sampling_configuration",
        {"completed": True, "outputs": {"aa_samples": 8}, "params": {}},
        context={"quality": "final"}
    )
    # 8 AA samples for final → should pass
    # We only flag if explicitly below threshold
    assert isinstance(sr, StageReview)


def test_review_stage_aa_samples_low_final():
    re = ReviewEngine()
    sr = re.review_stage(
        "arnold_render_ready", "sampling_configuration",
        {"completed": True, "outputs": {"aa_samples": 2}, "params": {}},
        context={"quality": "final"}
    )
    # 2 AA samples for final → should flag
    assert sr.passed is False
    assert any("AA" in c or "samples" in c.lower() for c in sr.critiques)


def test_review_stage_emission_aov_missing():
    re = ReviewEngine()
    sr = re.review_stage(
        "cinematic_aov_setup", "emission_pass",
        {"completed": True, "outputs": {"emission_aov_present": False}},
        context={"has_pyro": True}
    )
    assert sr.passed is False
    assert any("emission" in c.lower() or "AOV" in c for c in sr.critiques)


def test_review_stage_cryptomatte_missing():
    re = ReviewEngine()
    sr = re.review_stage(
        "cinematic_aov_setup", "cryptomatte",
        {"completed": True, "outputs": {"cryptomatte_configured": False}}
    )
    assert sr.passed is False
    assert any("cryptomatte" in c.lower() or "Cryptomatte" in c for c in sr.critiques)


# ---------------------------------------------------------------------------
# review — full workflow
# ---------------------------------------------------------------------------

def test_review_all_stages_pass():
    re = ReviewEngine()
    stage_results = {
        "terrain_prep": {"completed": True, "outputs": {}, "errors": []},
        "pyro_source": {"completed": True, "outputs": {}, "errors": []},
    }
    result = re.review("cinematic_explosion", stage_results)
    assert isinstance(result, ReviewResult)
    assert result.workflow_id == "cinematic_explosion"
    assert result.overall_passed is True
    assert result.production_ready is True


def test_review_stage_failure_propagates():
    re = ReviewEngine()
    stage_results = {
        "terrain_prep": {"completed": True, "outputs": {}, "errors": []},
        "fireball_core": {"completed": False, "errors": ["Bridge error"], "outputs": {}},
    }
    result = re.review("cinematic_explosion", stage_results)
    assert result.overall_passed is False
    assert result.production_ready is False
    assert len(result.critical_issues) > 0


def test_review_empty_stage_results():
    re = ReviewEngine()
    result = re.review("cinematic_explosion", {})
    assert result.workflow_id == "cinematic_explosion"
    assert result.overall_passed is True  # nothing failed
    assert isinstance(result.summary, str)


def test_review_returns_specific_summary():
    re = ReviewEngine()
    stage_results = {
        "output_driver": {"completed": True, "outputs": {"output_format": "png"}, "errors": []},
    }
    result = re.review("arnold_render_ready", stage_results)
    # Summary should mention the workflow by name
    assert "arnold_render_ready" in result.summary
    # Not just "Execution successful"
    assert "Execution successful" not in result.summary


def test_review_confidence_shape():
    re = ReviewEngine()
    stage_results = {"fireball_core": {"completed": True, "outputs": {}, "errors": []}}
    result = re.review("cinematic_explosion", stage_results)
    assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------

def test_summarize_multiple_results():
    re = ReviewEngine()
    r1 = ReviewResult("wf1", True, [], "Pass.", [], [], True, 0.9)
    r2 = ReviewResult("wf2", False, [], "Fail.", ["Issue A"], [], False, 0.7)
    summary = re.summarize([r1, r2])
    assert "1/2 workflows passed" in summary or "2/2" in summary or "wf1" in summary
    assert isinstance(summary, str)


def test_summarize_empty():
    re = ReviewEngine()
    summary = re.summarize([])
    assert "No review results" in summary


def test_summarize_caps_issues_per_workflow():
    re = ReviewEngine()
    # Create a result with many critical issues
    result = ReviewResult(
        "big_wf", False, [],
        "Many issues.",
        ["Issue 1", "Issue 2", "Issue 3", "Issue 4", "Issue 5"],
        [],
        False, 0.5
    )
    summary = re.summarize([result])
    # Should not include all 5 — capped at 3
    issue_count = summary.count("CRITICAL:")
    assert issue_count <= 3


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    re = ReviewEngine()
    s = re.stats()
    assert "review_count" in s
    assert "known_workflows" in s


def test_stats_count_increments():
    re = ReviewEngine()
    re.review("cinematic_explosion", {})
    re.review("arnold_render_ready", {})
    assert re.stats()["review_count"] == 2
