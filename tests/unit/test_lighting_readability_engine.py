"""Tests for LightingReadabilityEngine (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_readability_engine,
    reset_lighting_readability_engine_for_tests,
    ReadabilityResult,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_lighting_readability_engine_for_tests()
    yield
    reset_lighting_readability_engine_for_tests()


def _good_plan():
    return {
        "key_light":  {"role": "key",  "intensity": 0.9, "color_temperature_k": 3200},
        "fill_light": {"role": "fill", "intensity": 0.2, "color_temperature_k": 5500},
        "rim_light":  {"role": "rim",  "intensity": 0.6, "color_temperature_k": 4000},
        "hierarchy_notes": {"hero": ["robot_hero"], "support": [], "background": [], "atmosphere": []},
        "exposure":   {"contrast_ratio": "high", "dynamic_range_stops": 12.0},
    }


class TestLightingReadabilityEngine:
    def test_good_plan_high_score(self):
        engine = get_lighting_readability_engine()
        result = engine.evaluate_readability(_good_plan())
        assert result.score >= 0.7

    def test_empty_plan_low_score(self):
        engine = get_lighting_readability_engine()
        result = engine.evaluate_readability({})
        assert result.score < 0.5

    def test_no_key_light_finding(self):
        engine = get_lighting_readability_engine()
        result = engine.evaluate_readability({"fill_light": {"intensity": 0.3}})
        assert any("key light" in f.lower() for f in result.findings)

    def test_no_rim_warning(self):
        engine = get_lighting_readability_engine()
        plan = {
            "key_light":  {"role": "key", "intensity": 0.9},
            "fill_light": {"role": "fill", "intensity": 0.2},
        }
        result = engine.evaluate_readability(plan)
        assert any("rim" in r.lower() for r in result.recommendations)

    def test_low_key_intensity_warning(self):
        engine = get_lighting_readability_engine()
        plan = {"key_light": {"intensity": 0.1}}
        result = engine.evaluate_readability(plan)
        assert result.subject_visibility < 0.7

    def test_recommend_adjustments_returns_list(self):
        engine = get_lighting_readability_engine()
        adjustments = engine.recommend_adjustments(_good_plan())
        assert isinstance(adjustments, list)

    def test_good_plan_adjustments_note(self):
        engine = get_lighting_readability_engine()
        adjustments = engine.recommend_adjustments(_good_plan())
        assert any("readability" in a.lower() for a in adjustments)

    def test_returns_readability_result(self):
        engine = get_lighting_readability_engine()
        result = engine.evaluate_readability(_good_plan())
        assert isinstance(result, ReadabilityResult)

    def test_to_from_dict(self):
        engine = get_lighting_readability_engine()
        result = engine.evaluate_readability(_good_plan())
        d = result.to_dict()
        r2 = ReadabilityResult.from_dict(d)
        assert abs(r2.score - result.score) < 0.001

    def test_never_raises_on_bad_input(self):
        engine = get_lighting_readability_engine()
        result = engine.evaluate_readability("not a dict")
        assert isinstance(result, ReadabilityResult)

    def test_singleton(self):
        assert get_lighting_readability_engine() is get_lighting_readability_engine()
