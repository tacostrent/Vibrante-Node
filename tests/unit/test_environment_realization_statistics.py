"""Tests for EnvRealizationStatistics — §49 Structural Environment Realization."""
import pytest
from src.runtime.environment_realization import (
    get_env_realization_statistics,
    reset_env_realization_statistics_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_env_realization_statistics_for_tests()
    yield
    reset_env_realization_statistics_for_tests()


def test_record_and_total():
    s = get_env_realization_statistics()
    s.record("western_room", 4, 1, 1, 1, 4, 0.95, "A", True)
    assert s.total() == 1


def test_production_ready_rate_all_ready():
    s = get_env_realization_statistics()
    for _ in range(5):
        s.record("western_room", 4, 1, 1, 1, 4, 0.95, "A", True)
    assert s.production_ready_rate() == pytest.approx(1.0)


def test_production_ready_rate_mixed():
    s = get_env_realization_statistics()
    s.record("a", 4, 1, 1, 1, 4, 0.95, "A", True)
    s.record("b", 2, 0, 0, 0, 0, 0.30, "F", False)
    assert s.production_ready_rate() == pytest.approx(0.5)


def test_average_score():
    s = get_env_realization_statistics()
    s.record("a", 4, 1, 1, 1, 4, 0.80, "B", True)
    s.record("b", 4, 1, 1, 1, 4, 0.60, "C", False)
    assert s.average_score() == pytest.approx(0.70)


def test_recent():
    s = get_env_realization_statistics()
    for i in range(12):
        s.record(f"env_{i}", 4, 1, 1, 1, 4, 0.90, "A", True)
    recent = s.recent(5)
    assert len(recent) == 5
    assert recent[-1]["environment"] == "env_11"


def test_summary_keys():
    s = get_env_realization_statistics()
    s.record("x", 4, 1, 1, 1, 4, 0.90, "A", True)
    summary = s.summary()
    assert "total" in summary
    assert "production_ready_rate" in summary
    assert "average_score" in summary


def test_empty_defaults():
    s = get_env_realization_statistics()
    assert s.total() == 0
    assert s.production_ready_rate() == pytest.approx(0.0)
    assert s.average_score() == pytest.approx(0.0)
