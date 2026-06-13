"""
Tests for src.runtime.review_feedback
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.review_feedback import (
    ReviewFeedbackEngine,
    get_review_feedback_engine,
    reset_review_feedback_engine_for_tests,
    _FAILURE_KEYWORD_MAP,
    _STRENGTH_KEYWORD_MAP,
    _IMPROVEMENT_ACTIONS,
)
from src.runtime.production_memory import reset_production_memory_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_review_feedback_engine_for_tests()
    reset_production_memory_for_tests()
    yield
    reset_review_feedback_engine_for_tests()
    reset_production_memory_for_tests()


def _good_review():
    return {
        "overall_score": 0.88,
        "grade": "B",
        "production_ready": True,
        "findings": ["Cinematic depth separation is strong."],
        "strengths": ["Hero asset readability is excellent — focal point is clear and lit."],
        "recommendations": [],
        "review_summary": "Scene meets cinematic production standards.",
    }


def _bad_review():
    return {
        "overall_score": 0.35,
        "grade": "F",
        "production_ready": False,
        "findings": [
            "No hero asset present — scene has no narrative focal point.",
            "Depth layering is absent — scene reads as flat.",
            "Key light absent — primary illumination undefined.",
        ],
        "critical_findings": [
            "No hero asset present — scene has no narrative focal point.",
        ],
        "strengths": [],
        "recommendations": ["Add hero assets to hero_area zone."],
        "review_summary": "Scene is not production-ready. No hero present.",
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_review_feedback_engine()
    b = get_review_feedback_engine()
    assert a is b


def test_reset_creates_new():
    a = get_review_feedback_engine()
    reset_review_feedback_engine_for_tests()
    b = get_review_feedback_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# extract_feedback
# ---------------------------------------------------------------------------

def test_extract_feedback_returns_dict():
    e = ReviewFeedbackEngine()
    result = e.extract_feedback(_good_review())
    assert isinstance(result, dict)


def test_extract_feedback_has_required_keys():
    e = ReviewFeedbackEngine()
    result = e.extract_feedback(_good_review())
    for key in ("failures", "strengths", "issues", "recommendations",
                "overall_score", "production_ready", "grade"):
        assert key in result, f"Missing key: {key}"


def test_extract_feedback_preserves_score():
    e = ReviewFeedbackEngine()
    result = e.extract_feedback(_good_review())
    assert result["overall_score"] == pytest.approx(0.88)


def test_extract_feedback_preserves_production_ready():
    e = ReviewFeedbackEngine()
    assert e.extract_feedback(_good_review())["production_ready"] is True
    assert e.extract_feedback(_bad_review())["production_ready"] is False


def test_extract_feedback_increments_count():
    e = ReviewFeedbackEngine()
    e.extract_feedback(_good_review())
    e.extract_feedback(_bad_review())
    assert e.stats()["extraction_count"] == 2


# ---------------------------------------------------------------------------
# extract_failures
# ---------------------------------------------------------------------------

def test_extract_failures_from_bad_review():
    e = ReviewFeedbackEngine()
    failures = e.extract_failures(_bad_review())
    assert "hero_absent" in failures or "hero_focus_low" in failures
    assert "depth_flat" in failures
    assert "key_light_missing" in failures


def test_extract_failures_empty_on_good_review():
    e = ReviewFeedbackEngine()
    # Good review has no failure keywords
    failures = e.extract_failures({
        "overall_score": 0.9,
        "production_ready": True,
        "findings": [],
    })
    assert failures == []


def test_extract_failures_returns_list():
    e = ReviewFeedbackEngine()
    failures = e.extract_failures(_bad_review())
    assert isinstance(failures, list)


def test_extract_failures_deduplication():
    e = ReviewFeedbackEngine()
    review = {
        "findings": [
            "No hero asset present — scene has no narrative focal point.",
            "No hero asset present again.",  # same keyword
        ],
        "critical_findings": ["no hero seen anywhere"],
    }
    failures = e.extract_failures(review)
    hero_failures = [f for f in failures if "hero" in f]
    assert len(hero_failures) == len(set(hero_failures))


def test_extract_failures_fog_density():
    e = ReviewFeedbackEngine()
    review = {"findings": ["fog too dense — assets obscured"]}
    assert "fog_density_high" in e.extract_failures(review)


def test_extract_failures_rim_light():
    e = ReviewFeedbackEngine()
    review = {"findings": ["rim light absent — hero and background merge"]}
    assert "rim_light_missing" in e.extract_failures(review)


def test_extract_failures_from_review_summary():
    e = ReviewFeedbackEngine()
    review = {"review_summary": "Key light absent in scene."}
    assert "key_light_missing" in e.extract_failures(review)


# ---------------------------------------------------------------------------
# extract_strengths
# ---------------------------------------------------------------------------

def test_extract_strengths_from_good_review():
    e = ReviewFeedbackEngine()
    strengths = e.extract_strengths(_good_review())
    assert len(strengths) > 0


def test_extract_strengths_returns_list():
    e = ReviewFeedbackEngine()
    assert isinstance(e.extract_strengths(_bad_review()), list)


def test_extract_strengths_hero_excellent():
    e = ReviewFeedbackEngine()
    review = {"strengths": ["Hero asset readability is excellent."]}
    strengths = e.extract_strengths(review)
    assert "hero_focus_strong" in strengths


def test_extract_strengths_depth_strong():
    e = ReviewFeedbackEngine()
    review = {"strengths": ["Cinematic depth separation is strong."]}
    strengths = e.extract_strengths(review)
    assert "depth_strong" in strengths


# ---------------------------------------------------------------------------
# build_improvement_actions
# ---------------------------------------------------------------------------

def test_build_improvement_actions_returns_list():
    e = ReviewFeedbackEngine()
    feedback = e.extract_feedback(_bad_review())
    actions = e.build_improvement_actions(feedback)
    assert isinstance(actions, list)


def test_build_improvement_actions_not_empty_on_failure():
    e = ReviewFeedbackEngine()
    feedback = e.extract_feedback(_bad_review())
    actions = e.build_improvement_actions(feedback)
    assert len(actions) > 0


def test_build_improvement_actions_critical_first():
    e = ReviewFeedbackEngine()
    feedback = {"failures": ["hero_absent", "fog_density_high"]}
    actions = e.build_improvement_actions(feedback)
    # hero_absent is critical, fog_density_high is high
    priorities = [a.get("priority") for a in actions]
    assert priorities[0] == "critical"


def test_build_improvement_actions_has_required_fields():
    e = ReviewFeedbackEngine()
    feedback = {"failures": ["key_light_missing"]}
    actions = e.build_improvement_actions(feedback)
    assert len(actions) == 1
    a = actions[0]
    assert "action" in a
    assert "target" in a
    assert "priority" in a
    assert "failure_category" in a


def test_build_improvement_actions_no_duplicates():
    e = ReviewFeedbackEngine()
    feedback = {"failures": ["hero_absent", "hero_absent"]}
    actions = e.build_improvement_actions(feedback)
    action_names = [a["action"] for a in actions]
    assert len(action_names) == len(set(action_names))


def test_build_improvement_actions_empty_on_no_failures():
    e = ReviewFeedbackEngine()
    actions = e.build_improvement_actions({"failures": []})
    assert actions == []


# ---------------------------------------------------------------------------
# update_production_memory
# ---------------------------------------------------------------------------

def test_update_production_memory_returns_dict():
    e = ReviewFeedbackEngine()
    result = e.update_production_memory(_good_review(), scene_type="industrial_hangar")
    assert isinstance(result, dict)


def test_update_production_memory_has_required_keys():
    e = ReviewFeedbackEngine()
    result = e.update_production_memory(_good_review())
    for key in ("feedback", "actions", "memory_updated", "scene_record_id", "review_record_id"):
        assert key in result


def test_update_production_memory_good_review():
    e = ReviewFeedbackEngine()
    result = e.update_production_memory(
        _good_review(),
        scene_type="industrial_hangar",
        lighting_style="cold_scifi",
        camera_style="hero_focus",
    )
    assert result["memory_updated"] is True
    assert result["scene_record_id"] is not None
    assert result["review_record_id"] is not None


def test_update_production_memory_records_failure_scene():
    e = ReviewFeedbackEngine()
    result = e.update_production_memory(_bad_review(), scene_type="robotics_lab")
    assert result["memory_updated"] is True
    # Check that failures were recorded in memory
    from src.runtime.production_memory import get_production_memory
    mem = get_production_memory()
    failures = mem.get_failure_patterns(scene_type="robotics_lab")
    assert len(failures) > 0


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_has_extraction_count():
    e = ReviewFeedbackEngine()
    assert "extraction_count" in e.stats()


def test_stats_starts_zero():
    e = ReviewFeedbackEngine()
    assert e.stats()["extraction_count"] == 0
