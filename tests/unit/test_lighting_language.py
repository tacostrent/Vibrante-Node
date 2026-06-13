"""Tests for LightingLanguage (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_language,
    reset_lighting_language_for_tests,
    LightingIntent,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_lighting_language_for_tests()
    yield
    reset_lighting_language_for_tests()


class TestLightingLanguage:
    def test_parse_industrial(self):
        lang = get_lighting_language()
        intent = lang.parse_lighting_intent("dark industrial facility with harsh shadows")
        assert intent.mood == "industrial"
        assert intent.contrast == "high"

    def test_parse_dramatic(self):
        lang = get_lighting_language()
        intent = lang.parse_lighting_intent("dramatic high contrast cinematic scene")
        assert intent.mood == "dramatic"
        assert intent.contrast == "high"

    def test_parse_clinical(self):
        lang = get_lighting_language()
        intent = lang.parse_lighting_intent("clean sterile lab environment")
        assert intent.mood == "clinical"

    def test_parse_tense(self):
        lang = get_lighting_language()
        intent = lang.parse_lighting_intent("tense thriller suspense scene")
        assert intent.mood == "tense"

    def test_extract_mood_dangerous(self):
        lang = get_lighting_language()
        mood = lang.extract_mood("danger alarm red warning lights")
        assert mood == "dangerous"

    def test_extract_contrast_low(self):
        lang = get_lighting_language()
        contrast = lang.extract_contrast("soft diffuse overcast light")
        assert contrast == "low"

    def test_extract_contrast_default(self):
        lang = get_lighting_language()
        contrast = lang.extract_contrast("some scene")
        assert contrast in ("medium", "high", "low")

    def test_extract_style_low_key(self):
        lang = get_lighting_language()
        style = lang.extract_style("dark noir night low key")
        assert style == "low_key"

    def test_extract_temperature_warm(self):
        lang = get_lighting_language()
        temp = lang.extract_temperature("golden warm sunset amber light")
        assert temp == "warm"

    def test_extract_temperature_cool(self):
        lang = get_lighting_language()
        temp = lang.extract_temperature("cold blue moonlight")
        assert temp == "cool"

    def test_parse_environments(self):
        lang = get_lighting_language()
        intent = lang.parse_lighting_intent("sci-fi corridor with neon lights")
        assert "sci_fi_corridor" in intent.environments

    def test_parse_empty_text(self):
        lang = get_lighting_language()
        intent = lang.parse_lighting_intent("")
        assert isinstance(intent, LightingIntent)
        assert intent.intent_text == ""

    def test_parse_returns_lighting_intent(self):
        lang = get_lighting_language()
        intent = lang.parse_lighting_intent("any text")
        assert isinstance(intent, LightingIntent)

    def test_to_from_dict(self):
        lang = get_lighting_language()
        intent = lang.parse_lighting_intent("dramatic industrial scene")
        d = intent.to_dict()
        intent2 = LightingIntent.from_dict(d)
        assert intent2.mood == intent.mood
        assert intent2.contrast == intent.contrast

    def test_singleton(self):
        assert get_lighting_language() is get_lighting_language()
