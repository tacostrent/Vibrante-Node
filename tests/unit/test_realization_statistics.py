"""Tests for RealizationStatistics — §47 Layout Realization."""
import pytest
from src.runtime.layout_realization import (
    get_realization_statistics,
    reset_realization_statistics_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_realization_statistics_for_tests()
    yield
    reset_realization_statistics_for_tests()


def test_record_and_total():
    s = get_realization_statistics()
    s.record("western_room", 7, 0, 0, 0.92, "A", True)
    assert s.total() == 1


def test_production_ready_rate_all_ready():
    s = get_realization_statistics()
    for _ in range(5):
        s.record("western_room", 7, 0, 0, 0.90, "A", True)
    assert s.production_ready_rate() == pytest.approx(1.0)


def test_production_ready_rate_mixed():
    s = get_realization_statistics()
    s.record("env", 5, 0, 0, 0.90, "A", True)
    s.record("env", 5, 2, 1, 0.50, "C", False)
    assert s.production_ready_rate() == pytest.approx(0.5)


def test_average_score():
    s = get_realization_statistics()
    s.record("a", 5, 0, 0, 0.80, "B", True)
    s.record("b", 5, 0, 0, 0.60, "C", False)
    assert s.average_score() == pytest.approx(0.70)


def test_recent_returns_last_n():
    s = get_realization_statistics()
    for i in range(15):
        s.record(f"env_{i}", i, 0, 0, 0.80, "B", True)
    recent = s.recent(5)
    assert len(recent) == 5
    assert recent[-1]["environment"] == "env_14"


def test_summary_keys():
    s = get_realization_statistics()
    s.record("x", 3, 0, 0, 0.85, "A", True)
    summary = s.summary()
    for key in ("total", "production_ready_rate", "average_score", "average_collisions"):
        assert key in summary


def test_empty_statistics_defaults():
    s = get_realization_statistics()
    assert s.total() == 0
    assert s.production_ready_rate() == pytest.approx(0.0)
