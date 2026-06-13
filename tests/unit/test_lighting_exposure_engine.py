"""Tests for LightingExposureEngine (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_exposure_engine,
    reset_lighting_exposure_engine_for_tests,
    ExposureStrategy,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_lighting_exposure_engine_for_tests()
    yield
    reset_lighting_exposure_engine_for_tests()


class TestLightingExposureEngine:
    def test_recommend_dramatic(self):
        engine = get_lighting_exposure_engine()
        s = engine.recommend_exposure(mood="dramatic")
        assert isinstance(s, ExposureStrategy)
        assert s.contrast_ratio == "high"
        assert s.shadow_detail == "low"

    def test_recommend_clinical(self):
        engine = get_lighting_exposure_engine()
        s = engine.recommend_exposure(mood="clinical")
        assert s.contrast_ratio == "low"
        assert s.ev_target > 0

    def test_recommend_dangerous(self):
        engine = get_lighting_exposure_engine()
        s = engine.recommend_exposure(mood="dangerous")
        assert s.ev_target < -1.0
        assert s.shadow_detail == "none"

    def test_recommend_unknown_returns_default(self):
        engine = get_lighting_exposure_engine()
        s = engine.recommend_exposure(mood="unknown_xyz")
        assert isinstance(s, ExposureStrategy)

    def test_recommend_contrast_high(self):
        engine = get_lighting_exposure_engine()
        c = engine.recommend_contrast(mood="dramatic")
        assert c["contrast_ratio"] == "high"
        assert c["stop_ratio"] >= 8

    def test_recommend_contrast_low(self):
        engine = get_lighting_exposure_engine()
        c = engine.recommend_contrast(mood="clinical")
        assert c["contrast_ratio"] == "low"

    def test_recommend_dynamic_range(self):
        engine = get_lighting_exposure_engine()
        dr = engine.recommend_dynamic_range(mood="dramatic")
        assert "dynamic_range_stops" in dr
        assert dr["dynamic_range_stops"] > 8.0

    def test_to_from_dict(self):
        engine = get_lighting_exposure_engine()
        s = engine.recommend_exposure(mood="cinematic")
        d = s.to_dict()
        s2 = ExposureStrategy.from_dict(d)
        assert s2.contrast_ratio == s.contrast_ratio

    def test_singleton(self):
        assert get_lighting_exposure_engine() is get_lighting_exposure_engine()

    def test_never_raises_on_empty(self):
        engine = get_lighting_exposure_engine()
        s = engine.recommend_exposure(mood="")
        assert isinstance(s, ExposureStrategy)
