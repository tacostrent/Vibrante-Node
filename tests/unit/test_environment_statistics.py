"""
Tests for EnvironmentStatistics (§39 — Environment Expansion Pack)
"""
import pytest

from src.runtime.environments.environment_statistics import (
    EnvironmentStatRecord,
    EnvironmentStatistics,
    get_environment_statistics,
    reset_environment_statistics_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_environment_statistics_for_tests()
    yield
    reset_environment_statistics_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    s1 = get_environment_statistics()
    s2 = get_environment_statistics()
    assert s1 is s2


def test_starts_empty():
    stats = get_environment_statistics()
    assert stats.record_count() == 0


# ---------------------------------------------------------------------------
# record_usage
# ---------------------------------------------------------------------------

def test_record_usage_increments_count():
    stats = get_environment_statistics()
    stats.record_usage("forest", asset_count=5)
    assert stats.usage_count("forest") == 1


def test_record_usage_multiple():
    stats = get_environment_statistics()
    for _ in range(3):
        stats.record_usage("industrial_hangar", asset_count=3)
    assert stats.usage_count("industrial_hangar") == 3


def test_record_usage_does_not_affect_other_env():
    stats = get_environment_statistics()
    stats.record_usage("forest")
    assert stats.usage_count("desert") == 0


# ---------------------------------------------------------------------------
# record_success / record_failure / success_rate
# ---------------------------------------------------------------------------

def test_success_rate_all_successes():
    stats = get_environment_statistics()
    stats.record_success("western_room", score=0.85)
    stats.record_success("western_room", score=0.90)
    assert stats.success_rate("western_room") == 1.0


def test_success_rate_mixed():
    stats = get_environment_statistics()
    stats.record_success("western_room", score=0.85)
    stats.record_failure("western_room")
    rate = stats.success_rate("western_room")
    assert abs(rate - 0.5) < 0.01


def test_success_rate_no_data_returns_zero():
    stats = get_environment_statistics()
    assert stats.success_rate("jungle") == 0.0


# ---------------------------------------------------------------------------
# record_review / review_average
# ---------------------------------------------------------------------------

def test_review_average_single():
    stats = get_environment_statistics()
    stats.record_review("castle_hall", score=0.80)
    assert stats.review_average("castle_hall") == 0.80


def test_review_average_multiple():
    stats = get_environment_statistics()
    stats.record_review("space_station", score=0.70)
    stats.record_review("space_station", score=0.90)
    avg = stats.review_average("space_station")
    assert abs(avg - 0.80) < 0.01


def test_review_average_no_data_returns_zero():
    stats = get_environment_statistics()
    assert stats.review_average("dungeon") == 0.0


# ---------------------------------------------------------------------------
# asset_count_average
# ---------------------------------------------------------------------------

def test_asset_count_average():
    stats = get_environment_statistics()
    stats.record_usage("military_base", asset_count=4)
    stats.record_usage("military_base", asset_count=6)
    avg = stats.asset_count_average("military_base")
    assert abs(avg - 5.0) < 0.01


def test_asset_count_average_no_data():
    stats = get_environment_statistics()
    assert stats.asset_count_average("forest") == 0.0


# ---------------------------------------------------------------------------
# record_lighting_pattern / lighting_pattern_usage
# ---------------------------------------------------------------------------

def test_lighting_pattern_usage():
    stats = get_environment_statistics()
    stats.record_lighting_pattern("cyberpunk_city", "neon_rain")
    stats.record_lighting_pattern("cyberpunk_city", "neon_rain")
    stats.record_lighting_pattern("cyberpunk_city", "dramatic")
    usage = stats.lighting_pattern_usage("cyberpunk_city")
    assert usage["neon_rain"] == 2
    assert usage["dramatic"] == 1


def test_lighting_pattern_usage_empty():
    stats = get_environment_statistics()
    assert stats.lighting_pattern_usage("forest") == {}


# ---------------------------------------------------------------------------
# top_environments
# ---------------------------------------------------------------------------

def test_top_environments():
    stats = get_environment_statistics()
    for _ in range(5):
        stats.record_usage("forest")
    for _ in range(3):
        stats.record_usage("desert")
    stats.record_usage("canyon")
    top = stats.top_environments(n=2)
    assert top[0]["environment"] == "forest"
    assert top[0]["usage_count"] == 5
    assert top[1]["environment"] == "desert"


def test_top_environments_empty():
    stats = get_environment_statistics()
    top = stats.top_environments()
    assert top == []


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

def test_summary_returns_all_fields():
    stats = get_environment_statistics()
    stats.record_usage("survival_camp", asset_count=3)
    stats.record_success("survival_camp", score=0.75)
    stats.record_review("survival_camp", score=0.72)
    stats.record_lighting_pattern("survival_camp", "campfire_warm")
    s = stats.summary("survival_camp")
    assert s["environment"] == "survival_camp"
    assert s["usage_count"] == 1
    assert s["success_rate"] == 1.0
    assert abs(s["review_average"] - 0.72) < 0.01
    assert s["asset_count_avg"] == 3.0
    assert s["lighting_patterns"]["campfire_warm"] == 1


# ---------------------------------------------------------------------------
# Cap at 2000 records
# ---------------------------------------------------------------------------

def test_cap_at_2000():
    stats = get_environment_statistics()
    for i in range(2100):
        stats.record_usage(f"env_{i % 10}")
    assert stats.record_count() == 2000


# ---------------------------------------------------------------------------
# EnvironmentStatRecord to_dict / from_dict
# ---------------------------------------------------------------------------

def test_stat_record_roundtrip():
    rec = EnvironmentStatRecord(
        environment="forest",
        event_type="review",
        score=0.85,
        lighting_pattern="natural",
        asset_count=7,
    )
    d = rec.to_dict()
    restored = EnvironmentStatRecord.from_dict(d)
    assert restored.environment == "forest"
    assert restored.event_type == "review"
    assert abs(restored.score - 0.85) < 0.001
    assert restored.asset_count == 7


def test_stat_record_from_empty_dict():
    rec = EnvironmentStatRecord.from_dict({})
    assert rec.environment == ""
    assert rec.score == 0.0
    assert rec.asset_count == 0


# ---------------------------------------------------------------------------
# Never raises
# ---------------------------------------------------------------------------

def test_record_usage_never_raises_on_bad_input():
    stats = get_environment_statistics()
    stats.record_usage(None)  # type: ignore
    stats.record_success(None)  # type: ignore
    stats.record_failure(None)  # type: ignore
    stats.record_review(None)  # type: ignore
    stats.record_lighting_pattern(None, None)  # type: ignore
