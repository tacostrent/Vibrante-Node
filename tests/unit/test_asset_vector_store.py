"""Tests for asset_vector_store.py (Tier 12.8)."""
from __future__ import annotations
import pytest
from src.runtime.assets.vector_search import (
    AssetVectorStore, VectorSearchResult,
    get_asset_vector_store, reset_asset_vector_store_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_asset_vector_store_for_tests()
    yield
    reset_asset_vector_store_for_tests()


_V128 = [0.0] * 128


def _unit(dim: int, n: int = 128) -> list:
    v = [0.0] * n
    v[dim] = 1.0
    return v


class TestAssetVectorStore:
    def test_add_and_contains(self):
        s = get_asset_vector_store()
        assert s.add_vector("a1", _unit(0)) is True
        assert s.contains("a1")

    def test_size_increments(self):
        s = get_asset_vector_store()
        assert s.size() == 0
        s.add_vector("a1", _unit(0))
        assert s.size() == 1

    def test_add_empty_id_rejected(self):
        assert get_asset_vector_store().add_vector("", _unit(0)) is False

    def test_add_empty_vector_rejected(self):
        assert get_asset_vector_store().add_vector("a1", []) is False

    def test_dimension_mismatch_rejected(self):
        s = get_asset_vector_store()
        s.add_vector("a1", _unit(0, 128))
        # 64-dim vector rejected when store expects 128
        result = s.add_vector("a2", _unit(0, 64))
        assert result is False

    def test_update_vector(self):
        s = get_asset_vector_store()
        s.add_vector("a1", _unit(0))
        s.update_vector("a1", _unit(1))
        assert s.contains("a1")

    def test_delete_vector(self):
        s = get_asset_vector_store()
        s.add_vector("a1", _unit(0))
        assert s.delete_vector("a1") is True
        assert not s.contains("a1")

    def test_delete_nonexistent_returns_false(self):
        assert get_asset_vector_store().delete_vector("ghost") is False

    def test_query_returns_results(self):
        s = get_asset_vector_store()
        s.add_vector("a1", _unit(0))
        s.add_vector("a2", _unit(1))
        results = s.query(_unit(0), top_k=2)
        assert len(results) > 0
        assert isinstance(results[0], VectorSearchResult)

    def test_query_top_1_returns_best(self):
        s = get_asset_vector_store()
        s.add_vector("match", _unit(5))
        s.add_vector("other", _unit(6))
        results = s.query(_unit(5), top_k=1)
        assert results[0].asset_id == "match"
        assert abs(results[0].score - 1.0) < 1e-6

    def test_query_scores_sorted_descending(self):
        s = get_asset_vector_store()
        for i in range(5):
            s.add_vector(f"a{i}", _unit(i))
        results = s.query(_unit(2), top_k=5)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_query_empty_store(self):
        results = get_asset_vector_store().query(_unit(0))
        assert results == []

    def test_query_excludes_ids(self):
        s = get_asset_vector_store()
        s.add_vector("a1", _unit(0))
        s.add_vector("a2", _unit(0))
        results = s.query(_unit(0), top_k=5, exclude_ids=["a1"])
        assert all(r.asset_id != "a1" for r in results)

    def test_clear(self):
        s = get_asset_vector_store()
        s.add_vector("a1", _unit(0))
        s.clear()
        assert s.size() == 0

    def test_get_all_ids(self):
        s = get_asset_vector_store()
        s.add_vector("x1", _unit(0))
        s.add_vector("x2", _unit(1))
        ids = s.get_all_ids()
        assert "x1" in ids
        assert "x2" in ids

    def test_statistics(self):
        s = get_asset_vector_store()
        s.add_vector("a1", _unit(0))
        s.query(_unit(0))
        stats = s.get_statistics()
        assert stats["size"] == 1
        assert stats["dimensions"] == 128
        assert stats["add_count"] >= 1
        assert stats["query_count"] >= 1

    def test_vsr_to_dict_from_dict(self):
        r = VectorSearchResult(asset_id="a1", score=0.95, rank=1)
        d = r.to_dict()
        r2 = VectorSearchResult.from_dict(d)
        assert r2.asset_id == "a1"
        assert abs(r2.score - 0.95) < 1e-9
