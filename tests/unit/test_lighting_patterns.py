"""Tests for LightingPatterns (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_patterns,
    reset_lighting_patterns_for_tests,
    LightingPattern,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_lighting_patterns_for_tests()
    yield
    reset_lighting_patterns_for_tests()


class TestLightingPatterns:
    def test_builtins_loaded(self):
        lib = get_lighting_patterns()
        patterns = lib.search_patterns()
        assert len(patterns) >= 8

    def test_builtin_environments(self):
        lib = get_lighting_patterns()
        envs = {p.environment for p in lib.search_patterns()}
        assert "industrial_hangar" in envs
        assert "sci_fi_corridor" in envs
        assert "abandoned_factory" in envs

    def test_search_by_environment(self):
        lib = get_lighting_patterns()
        results = lib.search_patterns(environment="robotics_lab")
        assert len(results) >= 1
        assert all(p.environment == "robotics_lab" for p in results)

    def test_search_by_mood(self):
        lib = get_lighting_patterns()
        results = lib.search_patterns(mood="dramatic")
        assert len(results) >= 1
        assert all(p.mood == "dramatic" for p in results)

    def test_search_by_query(self):
        lib = get_lighting_patterns()
        results = lib.search_patterns(query="neon")
        assert any("neon" in p.tags or "neon" in p.description.lower() for p in results)

    def test_rank_patterns_by_environment(self):
        lib = get_lighting_patterns()
        ranked = lib.rank_patterns({"environment": "industrial_hangar"})
        assert len(ranked) >= 1
        assert ranked[0].environment == "industrial_hangar"

    def test_recommend_pattern(self):
        lib = get_lighting_patterns()
        p = lib.recommend_pattern(environment="control_room")
        assert p is not None
        assert p.environment == "control_room"

    def test_recommend_none_returns_fallback(self):
        lib = get_lighting_patterns()
        p = lib.recommend_pattern(environment="unknown_xyz")
        # Should return something or None without raising
        assert p is None or isinstance(p, LightingPattern)

    def test_get_by_id(self):
        lib = get_lighting_patterns()
        p = lib.get_pattern("builtin_industrial_hangar")
        assert p is not None
        assert p.environment == "industrial_hangar"

    def test_register_custom(self):
        lib = get_lighting_patterns()
        before = len(lib.search_patterns())
        lib.register_pattern("my_pattern", "night_exterior", mood="cinematic")
        after = len(lib.search_patterns())
        assert after == before + 1

    def test_volumetrics_flag(self):
        lib = get_lighting_patterns()
        p = lib.recommend_pattern(environment="sci_fi_corridor")
        assert p is not None
        assert p.volumetrics is True

    def test_to_from_dict(self):
        lib = get_lighting_patterns()
        p = lib.get_pattern("builtin_hero_reveal")
        assert p is not None
        d = p.to_dict()
        p2 = LightingPattern.from_dict(d)
        assert p2.name == p.name

    def test_singleton(self):
        assert get_lighting_patterns() is get_lighting_patterns()
