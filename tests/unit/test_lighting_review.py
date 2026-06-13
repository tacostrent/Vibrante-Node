"""Tests for LightingReview (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_review,
    reset_lighting_review_for_tests,
    reset_lighting_readability_engine_for_tests,
    reset_lighting_mood_engine_for_tests,
    reset_lighting_color_engine_for_tests,
    reset_lighting_exposure_engine_for_tests,
    LightingReviewResult,
)


@pytest.fixture(autouse=True)
def _reset():
    for fn in [
        reset_lighting_review_for_tests,
        reset_lighting_readability_engine_for_tests,
        reset_lighting_mood_engine_for_tests,
        reset_lighting_color_engine_for_tests,
        reset_lighting_exposure_engine_for_tests,
    ]:
        fn()
    yield
    for fn in [
        reset_lighting_review_for_tests,
        reset_lighting_readability_engine_for_tests,
        reset_lighting_mood_engine_for_tests,
        reset_lighting_color_engine_for_tests,
        reset_lighting_exposure_engine_for_tests,
    ]:
        fn()


def _good_plan():
    return {
        "intent":     "dramatic industrial scene",
        "mood":       "dramatic",
        "environment": "industrial_hangar",
        "key_light":  {"role": "key",  "intensity": 0.9, "color_temperature_k": 3200},
        "fill_light": {"role": "fill", "intensity": 0.2, "color_temperature_k": 5500},
        "rim_light":  {"role": "rim",  "intensity": 0.6, "color_temperature_k": 4000},
        "hierarchy_notes": {"hero": ["hero_robot"], "support": [], "background": [], "atmosphere": []},
        "color_strategy": {
            "primary_color": [0.95, 0.70, 0.30],
            "accent_color":  [0.25, 0.40, 0.70],
            "temperature":   "warm",
        },
        "exposure": {"ev_target": 0.0, "contrast_ratio": "high"},
    }


class TestLightingReview:
    def test_good_plan_high_score(self):
        engine = get_lighting_review()
        result = engine.review_plan(_good_plan())
        assert isinstance(result, LightingReviewResult)
        assert result.score >= 0.6

    def test_empty_plan_low_score(self):
        engine = get_lighting_review()
        result = engine.review_plan({})
        assert result.score < 0.5

    def test_empty_plan_not_production_ready(self):
        engine = get_lighting_review()
        result = engine.review_plan({})
        assert result.production_ready is False

    def test_no_key_light_blocking(self):
        engine = get_lighting_review()
        plan = {"mood": "dramatic", "fill_light": {"intensity": 0.2}}
        result = engine.review_plan(plan)
        assert any("key" in f.lower() for f in result.findings)

    def test_grade_f_for_empty(self):
        engine = get_lighting_review()
        result = engine.review_plan({})
        assert result.grade in ("F", "D")

    def test_grade_thresholds(self):
        engine = get_lighting_review()
        result = engine.review_plan(_good_plan())
        assert result.grade in ("A", "B", "C", "D", "F")

    def test_six_dimensions_present(self):
        engine = get_lighting_review()
        result = engine.review_plan(_good_plan())
        assert result.readability >= 0.0
        assert result.mood_accuracy >= 0.0
        assert result.story_support >= 0.0
        assert result.visual_hierarchy >= 0.0
        assert result.color_harmony >= 0.0
        assert result.exposure_quality >= 0.0

    def test_to_from_dict(self):
        engine = get_lighting_review()
        result = engine.review_plan(_good_plan())
        d = result.to_dict()
        r2 = LightingReviewResult.from_dict(d)
        assert abs(r2.score - result.score) < 0.001

    def test_never_raises_on_bad_input(self):
        engine = get_lighting_review()
        result = engine.review_plan("not a dict")
        assert isinstance(result, LightingReviewResult)

    def test_singleton(self):
        assert get_lighting_review() is get_lighting_review()
