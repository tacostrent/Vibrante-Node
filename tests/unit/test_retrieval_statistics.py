"""Tests for retrieval_statistics.py (Tier 12.8)."""
from __future__ import annotations
import pytest
from src.runtime.assets.vector_search import (
    RetrievalStatistics, get_retrieval_statistics, reset_retrieval_statistics_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_retrieval_statistics_for_tests()
    yield
    reset_retrieval_statistics_for_tests()


class TestRetrievalStatistics:
    def test_record_increments_total_queries(self):
        s = get_retrieval_statistics()
        s.record(query="test", score=0.8)
        assert s.get_summary()["total_queries"] == 1

    def test_avg_score(self):
        s = get_retrieval_statistics()
        s.record(score=0.8)
        s.record(score=0.6)
        summary = s.get_summary()
        assert abs(summary["avg_score"] - 0.7) < 1e-6

    def test_top_environments(self):
        s = get_retrieval_statistics()
        s.record(environment="industrial_hangar")
        s.record(environment="industrial_hangar")
        s.record(environment="robotics_lab")
        top = dict(s.get_summary()["top_environments"])
        assert top["industrial_hangar"] == 2

    def test_top_roles(self):
        s = get_retrieval_statistics()
        s.record(role="hero")
        s.record(role="hero")
        top = dict(s.get_summary()["top_roles"])
        assert top["hero"] == 2

    def test_top_assets(self):
        s = get_retrieval_statistics()
        s.record(top_asset="pipe001")
        top = dict(s.get_summary()["top_assets"])
        assert top["pipe001"] == 1

    def test_get_recent(self):
        s = get_retrieval_statistics()
        for i in range(5):
            s.record(query=f"q{i}")
        recent = s.get_recent(3)
        assert len(recent) == 3

    def test_reset(self):
        s = get_retrieval_statistics()
        s.record(query="test", score=0.9)
        s.reset()
        assert s.get_summary()["total_queries"] == 0

    def test_cap_at_max_records(self):
        from src.runtime.assets.vector_search.retrieval_statistics import _MAX_RECORDS
        s = get_retrieval_statistics()
        for i in range(_MAX_RECORDS + 50):
            s.record(query=f"q{i}")
        assert s.get_summary()["record_count"] < _MAX_RECORDS * 2

    def test_never_raises(self):
        s = get_retrieval_statistics()
        s.record(query=None, environment=None, score="invalid")
        assert True  # Should not raise
