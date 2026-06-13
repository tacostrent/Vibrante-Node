"""
Tests for src/runtime/assets/cache/asset_cache.py
"""

import pytest
import time

from src.runtime.assets.cache import (
    AssetCache,
    get_asset_cache,
    reset_asset_cache_for_tests,
)
from src.runtime.assets.schema import AssetDescriptor


@pytest.fixture(autouse=True)
def reset():
    reset_asset_cache_for_tests()
    yield
    reset_asset_cache_for_tests()


def make_asset(asset_id: str = "test_001", provider: str = "sketchfab") -> AssetDescriptor:
    return AssetDescriptor(
        asset_id=asset_id, provider=provider, name=f"Asset {asset_id}",
        category="prop", tags=["test"], formats=["fbx"],
    )


class TestAssetCache:
    def test_singleton_identity(self):
        c1 = get_asset_cache()
        c2 = get_asset_cache()
        assert c1 is c2

    def test_in_memory_cache_used_when_no_path(self):
        cache = AssetCache(path=None)
        assert cache._path is None

    def test_asset_miss_initially(self):
        cache = AssetCache()
        result = cache.get_asset("sketchfab", "does_not_exist")
        assert result is None

    def test_asset_set_and_get(self):
        cache = AssetCache()
        asset = make_asset()
        cache.set_asset(asset)
        retrieved = cache.get_asset("sketchfab", "test_001")
        assert retrieved is not None
        assert retrieved.asset_id == "test_001"

    def test_asset_round_trip_preserves_name(self):
        cache = AssetCache()
        asset = make_asset(asset_id="r1")
        asset.name = "Special Name"
        cache.set_asset(asset)
        retrieved = cache.get_asset(asset.provider, asset.asset_id)
        assert retrieved.name == "Special Name"

    def test_query_miss_initially(self):
        cache = AssetCache()
        result = cache.get_query("sketchfab", "prop", ["industrial"])
        assert result is None

    def test_query_set_and_get(self):
        cache = AssetCache()
        data = [{"name": "Asset 1"}, {"name": "Asset 2"}]
        cache.set_query("sketchfab", "prop", ["industrial"], data)
        result = cache.get_query("sketchfab", "prop", ["industrial"])
        assert result is not None
        assert len(result) == 2

    def test_query_different_tags_is_different_key(self):
        cache = AssetCache()
        cache.set_query("sketchfab", "prop", ["industrial"], [{"name": "A"}])
        result = cache.get_query("sketchfab", "prop", ["urban"])
        assert result is None

    def test_ranking_miss_initially(self):
        cache = AssetCache()
        result = cache.get_ranking("intent_1", "plan_1", "prop")
        assert result is None

    def test_ranking_set_and_get(self):
        cache = AssetCache()
        data = [{"rank": 1, "score": 0.9}]
        cache.set_ranking("intent_1", "plan_1", "prop", data)
        result = cache.get_ranking("intent_1", "plan_1", "prop")
        assert result is not None
        assert result[0]["rank"] == 1

    def test_ttl_expiry(self):
        cache = AssetCache()
        asset = make_asset()
        cache.set_asset(asset, ttl=0.0)  # immediate expiry
        time.sleep(0.01)
        retrieved = cache.get_asset("sketchfab", "test_001")
        assert retrieved is None

    def test_invalidate_all_clears_cache(self):
        cache = AssetCache()
        asset = make_asset()
        cache.set_asset(asset)
        cache.set_query("sketchfab", "prop", [], [{"x": 1}])
        cache.invalidate_all()
        assert cache.get_asset("sketchfab", "test_001") is None
        assert cache.get_query("sketchfab", "prop", []) is None

    def test_stats_structure(self):
        cache = AssetCache()
        s = cache.stats()
        assert "hits" in s
        assert "misses" in s
        assert "writes" in s
        assert "hit_rate" in s
        assert "persistent" in s

    def test_hit_count_increments(self):
        cache = AssetCache()
        cache.set_asset(make_asset())
        cache.get_asset("sketchfab", "test_001")
        cache.get_asset("sketchfab", "test_001")
        assert cache.stats()["hits"] == 2

    def test_miss_count_increments(self):
        cache = AssetCache()
        cache.get_asset("sketchfab", "nonexistent")
        assert cache.stats()["misses"] == 1

    def test_write_count_increments(self):
        cache = AssetCache()
        cache.set_asset(make_asset(asset_id="w1"))
        cache.set_asset(make_asset(asset_id="w2"))
        assert cache.stats()["writes"] == 2

    def test_hit_rate_correct(self):
        cache = AssetCache()
        cache.set_asset(make_asset())
        cache.get_asset("sketchfab", "test_001")  # hit
        cache.get_asset("sketchfab", "unknown")   # miss
        s = cache.stats()
        assert s["hit_rate"] == pytest.approx(0.5)

    def test_persistent_false_for_in_memory(self):
        cache = AssetCache(path=None)
        assert cache.stats()["persistent"] is False

    def test_tags_order_independent_key(self):
        cache = AssetCache()
        cache.set_query("sketchfab", "prop", ["b", "a"], [{"name": "Z"}])
        result = cache.get_query("sketchfab", "prop", ["a", "b"])
        assert result is not None
