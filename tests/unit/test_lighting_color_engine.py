"""Tests for LightingColorEngine (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_color_engine,
    reset_lighting_color_engine_for_tests,
    ColorStrategy,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_lighting_color_engine_for_tests()
    yield
    reset_lighting_color_engine_for_tests()


class TestLightingColorEngine:
    def test_recommend_industrial(self):
        engine = get_lighting_color_engine()
        cs = engine.recommend_palette(mood="industrial")
        assert isinstance(cs, ColorStrategy)
        assert cs.temperature == "cool"

    def test_recommend_dramatic(self):
        engine = get_lighting_color_engine()
        cs = engine.recommend_palette(mood="dramatic")
        assert cs.temperature == "warm"

    def test_recommend_fallback(self):
        engine = get_lighting_color_engine()
        cs = engine.recommend_palette(mood="unknown_xyz")
        assert isinstance(cs, ColorStrategy)

    def test_recommend_temperature_warm(self):
        engine = get_lighting_color_engine()
        temp = engine.recommend_temperature(mood="dramatic")
        assert temp["temperature"] == "warm"
        assert temp["temperature_k"] >= 3000

    def test_recommend_temperature_cool(self):
        engine = get_lighting_color_engine()
        temp = engine.recommend_temperature(mood="industrial")
        assert temp["temperature"] == "cool"

    def test_evaluate_harmony_good(self):
        engine = get_lighting_color_engine()
        # High luminance primary vs low luminance accent for clear contrast
        result = engine.evaluate_harmony([0.9, 0.8, 0.7], [0.1, 0.2, 0.1])
        assert result["harmony_ok"] is True

    def test_evaluate_harmony_low_contrast(self):
        engine = get_lighting_color_engine()
        result = engine.evaluate_harmony([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        assert result["harmony_ok"] is False

    def test_list_palettes(self):
        engine = get_lighting_color_engine()
        palettes = engine.list_palettes()
        assert "industrial" in palettes
        assert "dramatic" in palettes

    def test_color_rgb_length(self):
        engine = get_lighting_color_engine()
        cs = engine.recommend_palette(mood="cinematic")
        assert len(cs.primary_color) == 3
        assert len(cs.accent_color) == 3

    def test_to_from_dict(self):
        engine = get_lighting_color_engine()
        cs = engine.recommend_palette(mood="cinematic")
        d = cs.to_dict()
        cs2 = ColorStrategy.from_dict(d)
        assert cs2.palette_name == cs.palette_name

    def test_singleton(self):
        assert get_lighting_color_engine() is get_lighting_color_engine()
