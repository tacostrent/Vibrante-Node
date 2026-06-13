"""Tests for LightingRecommendationEngine (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_recommendation_engine,
    reset_lighting_recommendation_engine_for_tests,
    reset_lighting_patterns_for_tests,
    reset_lighting_strategy_engine_for_tests,
    reset_lighting_mood_engine_for_tests,
    reset_lighting_environment_mapper_for_tests,
    reset_lighting_color_engine_for_tests,
    reset_lighting_exposure_engine_for_tests,
    LightingRecommendation,
)


@pytest.fixture(autouse=True)
def _reset():
    for fn in [
        reset_lighting_recommendation_engine_for_tests,
        reset_lighting_patterns_for_tests,
        reset_lighting_strategy_engine_for_tests,
        reset_lighting_mood_engine_for_tests,
        reset_lighting_environment_mapper_for_tests,
        reset_lighting_color_engine_for_tests,
        reset_lighting_exposure_engine_for_tests,
    ]:
        fn()
    yield
    for fn in [
        reset_lighting_recommendation_engine_for_tests,
        reset_lighting_patterns_for_tests,
        reset_lighting_strategy_engine_for_tests,
        reset_lighting_mood_engine_for_tests,
        reset_lighting_environment_mapper_for_tests,
        reset_lighting_color_engine_for_tests,
        reset_lighting_exposure_engine_for_tests,
    ]:
        fn()


class TestLightingRecommendationEngine:
    def test_recommend_industrial(self):
        engine = get_lighting_recommendation_engine()
        rec = engine.recommend_setup(environment="industrial_hangar", mood="industrial")
        assert isinstance(rec, LightingRecommendation)
        assert rec.confidence > 0.0
        assert rec.key_concept != ""

    def test_recommend_sci_fi_corridor(self):
        engine = get_lighting_recommendation_engine()
        rec = engine.recommend_setup(environment="sci_fi_corridor")
        assert rec.pattern_id != "" or rec.pattern_name != ""

    def test_recommend_from_intent_text(self):
        engine = get_lighting_recommendation_engine()
        rec = engine.recommend_setup(intent_text="dramatic intense cinematic scene")
        assert isinstance(rec, LightingRecommendation)

    def test_recommend_pattern_returns_dict(self):
        engine = get_lighting_recommendation_engine()
        p = engine.recommend_pattern(environment="control_room")
        assert p is None or isinstance(p, dict)
        if p:
            assert "name" in p

    def test_recommend_adjustments_returns_list(self):
        engine = get_lighting_recommendation_engine()
        rec = engine.recommend_setup(environment="industrial_hangar")
        adj = engine.recommend_adjustments(rec)
        assert isinstance(adj, list)

    def test_low_confidence_warns(self):
        engine = get_lighting_recommendation_engine()
        rec = LightingRecommendation(confidence=0.4, key_concept="key_light")
        adj = engine.recommend_adjustments(rec)
        assert any("confidence" in a.lower() for a in adj)

    def test_to_from_dict(self):
        engine = get_lighting_recommendation_engine()
        rec = engine.recommend_setup(environment="hero_reveal")
        d = rec.to_dict()
        rec2 = LightingRecommendation.from_dict(d)
        assert abs(rec2.confidence - rec.confidence) < 0.001

    def test_singleton(self):
        assert get_lighting_recommendation_engine() is get_lighting_recommendation_engine()

    def test_never_raises_on_empty(self):
        engine = get_lighting_recommendation_engine()
        rec = engine.recommend_setup()
        assert isinstance(rec, LightingRecommendation)
