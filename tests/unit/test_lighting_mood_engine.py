"""Tests for LightingMoodEngine (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_mood_engine,
    reset_lighting_mood_engine_for_tests,
    MoodProfile,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_lighting_mood_engine_for_tests()
    yield
    reset_lighting_mood_engine_for_tests()


class TestLightingMoodEngine:
    def test_infer_industrial(self):
        engine = get_lighting_mood_engine()
        assert engine.infer_mood("industrial factory harsh gritty") == "industrial"

    def test_infer_dramatic(self):
        engine = get_lighting_mood_engine()
        assert engine.infer_mood("dramatic intense powerful contrast") == "dramatic"

    def test_infer_clinical(self):
        engine = get_lighting_mood_engine()
        assert engine.infer_mood("clean sterile lab clinical white") == "clinical"

    def test_infer_tense(self):
        engine = get_lighting_mood_engine()
        assert engine.infer_mood("tense thriller anxious suspense") == "tense"

    def test_infer_hopeful(self):
        engine = get_lighting_mood_engine()
        assert engine.infer_mood("hope bright golden warm optimistic") == "hopeful"

    def test_infer_dangerous(self):
        engine = get_lighting_mood_engine()
        assert engine.infer_mood("danger threat alarm warning menace") == "dangerous"

    def test_infer_empty(self):
        engine = get_lighting_mood_engine()
        result = engine.infer_mood("")
        assert result == "" or isinstance(result, str)

    def test_build_profile_dramatic(self):
        engine = get_lighting_mood_engine()
        p = engine.build_mood_profile("dramatic")
        assert isinstance(p, MoodProfile)
        assert p.mood == "dramatic"
        assert p.contrast == "high"
        assert p.fill_ratio < 0.3

    def test_build_profile_clinical(self):
        engine = get_lighting_mood_engine()
        p = engine.build_mood_profile("clinical")
        assert p.contrast == "low"
        assert p.fill_ratio > 0.5

    def test_build_profile_unknown_returns_default(self):
        engine = get_lighting_mood_engine()
        p = engine.build_mood_profile("unknown_xyz")
        assert isinstance(p, MoodProfile)
        assert p.mood == "unknown_xyz"

    def test_list_moods(self):
        engine = get_lighting_mood_engine()
        moods = engine.list_moods()
        assert "dramatic" in moods
        assert "industrial" in moods
        assert len(moods) == 8

    def test_to_from_dict(self):
        engine = get_lighting_mood_engine()
        p = engine.build_mood_profile("cinematic")
        d = p.to_dict()
        p2 = MoodProfile.from_dict(d)
        assert p2.mood == p.mood
        assert p2.contrast == p.contrast

    def test_singleton(self):
        assert get_lighting_mood_engine() is get_lighting_mood_engine()
