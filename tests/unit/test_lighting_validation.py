"""Tests for LightingValidation (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_validation,
    reset_lighting_validation_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_lighting_validation_for_tests()
    yield
    reset_lighting_validation_for_tests()


class TestLightingValidation:
    def test_valid_light_spec(self):
        v = get_lighting_validation()
        r = v.validate_light_spec({"role": "key", "intensity": 0.9, "color_temperature_k": 3200})
        assert r["ok"] is True
        assert r["errors"] == []

    def test_missing_role_error(self):
        v = get_lighting_validation()
        r = v.validate_light_spec({"intensity": 0.5})
        assert r["ok"] is False
        assert any("role" in e for e in r["errors"])

    def test_unknown_role_warning(self):
        v = get_lighting_validation()
        r = v.validate_light_spec({"role": "unknown_xyz", "intensity": 0.5})
        assert r["ok"] is True
        assert any("unknown_xyz" in w for w in r["warnings"])

    def test_intensity_out_of_range_warning(self):
        v = get_lighting_validation()
        r = v.validate_light_spec({"role": "key", "intensity": 2.5})
        assert any("2.5" in w or "intensity" in w.lower() for w in r["warnings"])

    def test_valid_plan(self):
        v = get_lighting_validation()
        plan = {
            "key_light":  {"role": "key",  "intensity": 0.9},
            "fill_light": {"role": "fill", "intensity": 0.2},
            "rim_light":  {"role": "rim",  "intensity": 0.5},
            "mood":       "dramatic",
        }
        r = v.validate_plan(plan)
        assert r["ok"] is True

    def test_plan_no_key_light_error(self):
        v = get_lighting_validation()
        r = v.validate_plan({})
        assert r["ok"] is False
        assert any("key_light" in e for e in r["errors"])

    def test_plan_no_fill_warning(self):
        v = get_lighting_validation()
        r = v.validate_plan({"key_light": {"role": "key", "intensity": 0.9}})
        assert any("fill" in w.lower() for w in r["warnings"])

    def test_valid_strategy(self):
        v = get_lighting_validation()
        r = v.validate_strategy({"key_concept": "key_light", "mood": "dramatic", "environment": "industrial_hangar"})
        assert r["ok"] is True

    def test_strategy_no_key_concept_error(self):
        v = get_lighting_validation()
        r = v.validate_strategy({"mood": "dramatic"})
        assert r["ok"] is False

    def test_strategy_unknown_mood_warning(self):
        v = get_lighting_validation()
        r = v.validate_strategy({"key_concept": "key_light", "mood": "unknown_xyz"})
        assert r["ok"] is True
        assert any("unknown_xyz" in w for w in r["warnings"])

    def test_validate_review_threshold_pass(self):
        v = get_lighting_validation()
        r = v.validate_review_threshold(0.85, 0.70)
        assert r["production_ready"] is True
        assert r["gap"] == 0.0

    def test_validate_review_threshold_fail(self):
        v = get_lighting_validation()
        r = v.validate_review_threshold(0.60, 0.70)
        assert r["production_ready"] is False
        assert r["gap"] > 0.0

    def test_never_raises_on_bad_input(self):
        v = get_lighting_validation()
        r = v.validate_plan("not a dict")
        assert isinstance(r, dict)
        assert "ok" in r

    def test_singleton(self):
        assert get_lighting_validation() is get_lighting_validation()
