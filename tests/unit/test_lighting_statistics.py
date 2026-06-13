"""Tests for LightingStatistics (Tier 15)."""
import pytest
from src.runtime.lighting import (
    get_lighting_statistics,
    reset_lighting_statistics_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_lighting_statistics_for_tests()
    yield
    reset_lighting_statistics_for_tests()


class TestLightingStatistics:
    def test_initial_empty(self):
        stats = get_lighting_statistics()
        s = stats.generate_statistics()
        assert s["total_reviews"] == 0
        assert s["total_plans"] == 0

    def test_record_review(self):
        stats = get_lighting_statistics()
        stats.record_review({"score": 0.85, "grade": "A", "production_ready": True})
        s = stats.generate_statistics()
        assert s["total_reviews"] == 1
        assert s["average_review_score"] == 0.85

    def test_record_pattern_usage(self):
        stats = get_lighting_statistics()
        stats.record_pattern_usage("builtin_industrial_hangar")
        stats.record_pattern_usage("builtin_industrial_hangar")
        s = stats.generate_statistics()
        assert any(p["pattern_id"] == "builtin_industrial_hangar" and p["count"] == 2 for p in s["top_patterns"])

    def test_record_mood_usage(self):
        stats = get_lighting_statistics()
        stats.record_mood_usage("dramatic")
        s = stats.generate_statistics()
        assert any(m["mood"] == "dramatic" for m in s["top_moods"])

    def test_record_environment_usage(self):
        stats = get_lighting_statistics()
        stats.record_environment_usage("industrial_hangar")
        s = stats.generate_statistics()
        assert any(e["environment"] == "industrial_hangar" for e in s["top_environments"])

    def test_record_plan(self):
        stats = get_lighting_statistics()
        stats.record_plan({"plan_id": "p1", "environment": "sci_fi_corridor", "mood": "dramatic"})
        s = stats.generate_statistics()
        assert s["total_plans"] == 1

    def test_cap_at_2000(self):
        stats = get_lighting_statistics()
        for i in range(2100):
            stats.record_review({"score": 0.7, "grade": "B"})
        s = stats.generate_statistics()
        assert s["total_reviews"] <= 2000

    def test_average_score(self):
        stats = get_lighting_statistics()
        stats.record_review({"score": 0.8})
        stats.record_review({"score": 0.6})
        s = stats.generate_statistics()
        assert abs(s["average_review_score"] - 0.7) < 0.01

    def test_top_patterns_sorted(self):
        stats = get_lighting_statistics()
        stats.record_pattern_usage("pattern_a")
        stats.record_pattern_usage("pattern_b")
        stats.record_pattern_usage("pattern_b")
        s = stats.generate_statistics()
        assert s["top_patterns"][0]["pattern_id"] == "pattern_b"

    def test_ignores_empty_strings(self):
        stats = get_lighting_statistics()
        stats.record_mood_usage("")
        stats.record_environment_usage("")
        s = stats.generate_statistics()
        assert s["top_moods"] == []

    def test_singleton(self):
        assert get_lighting_statistics() is get_lighting_statistics()
