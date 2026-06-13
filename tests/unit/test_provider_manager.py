"""Tests for src/runtime/assets/providers/provider_manager.py"""
import pytest

from src.runtime.assets.providers.base import get_provider_registry, reset_provider_registry_for_tests
from src.runtime.assets.providers.provider_manager import (
    ProviderManager,
    get_provider_manager,
    reset_provider_manager_for_tests,
)
from src.runtime.assets.providers.sketchfab_provider import SketchfabProvider
from src.runtime.assets.providers.polyhaven_provider import PolyhavenProvider
from src.runtime.assets.schema import AssetDescriptor, AssetProviderResult


@pytest.fixture(autouse=True)
def reset():
    reset_provider_manager_for_tests()
    reset_provider_registry_for_tests()
    yield
    reset_provider_manager_for_tests()
    reset_provider_registry_for_tests()


class TestProviderManagerSingleton:
    def test_singleton_identity(self):
        m1 = get_provider_manager()
        m2 = get_provider_manager()
        assert m1 is m2

    def test_reset_creates_new_instance(self):
        m1 = get_provider_manager()
        reset_provider_manager_for_tests()
        m2 = get_provider_manager()
        assert m1 is not m2


class TestProviderRegistration:
    def test_register_and_list(self):
        mgr = get_provider_manager()
        mgr.register_provider(SketchfabProvider())
        providers = mgr.list_providers()
        names = [p["name"] for p in providers]
        assert "sketchfab" in names

    def test_unregister(self):
        mgr = get_provider_manager()
        mgr.register_provider(SketchfabProvider())
        result = mgr.unregister_provider("sketchfab")
        assert result is True
        providers = mgr.list_providers()
        assert all(p["name"] != "sketchfab" for p in providers)

    def test_unregister_nonexistent(self):
        mgr = get_provider_manager()
        assert mgr.unregister_provider("nonexistent") is False

    def test_list_providers_sorted(self):
        mgr = get_provider_manager()
        mgr.register_provider(SketchfabProvider())
        mgr.register_provider(PolyhavenProvider())
        providers = mgr.list_providers()
        names = [p["name"] for p in providers]
        assert names == sorted(names)

    def test_list_includes_availability(self):
        mgr = get_provider_manager()
        mgr.register_provider(SketchfabProvider())
        providers = mgr.list_providers()
        p = next(p for p in providers if p["name"] == "sketchfab")
        assert "available" in p
        assert p["available"] is True


class TestQueryProviders:
    def test_query_returns_assets(self):
        mgr = get_provider_manager()
        mgr.register_provider(SketchfabProvider())
        assets = mgr.query_providers(category="prop")
        assert isinstance(assets, list)
        assert len(assets) > 0
        assert all(isinstance(a, AssetDescriptor) for a in assets)

    def test_query_empty_providers(self):
        mgr = get_provider_manager()
        assets = mgr.query_providers(category="vehicle")
        assert assets == []

    def test_query_deduplication(self):
        mgr = get_provider_manager()
        # Register same provider twice
        mgr.register_provider(SketchfabProvider())
        mgr.register_provider(PolyhavenProvider())
        assets = mgr.query_providers(category="")
        # Check no duplicates
        keys = [(a.provider, a.asset_id) for a in assets]
        assert len(keys) == len(set(keys))

    def test_query_provider_single(self):
        mgr = get_provider_manager()
        mgr.register_provider(SketchfabProvider())
        result = mgr.query_provider("sketchfab", category="prop")
        assert isinstance(result, AssetProviderResult)
        assert result.success is True

    def test_query_provider_unknown(self):
        mgr = get_provider_manager()
        result = mgr.query_provider("nonexistent", category="prop")
        assert result.success is False
        assert len(result.errors) > 0


class TestMergeResults:
    def test_merge_empty(self):
        mgr = get_provider_manager()
        result = mgr.merge_results([])
        assert result == []

    def test_merge_deduplicates(self):
        mgr = get_provider_manager()
        p = SketchfabProvider()
        r1 = p.search(category="prop", limit=5)
        r2 = p.search(category="prop", limit=5)  # Same results
        merged = mgr.merge_results([r1, r2])
        keys = [(a.provider, a.asset_id) for a in merged]
        assert len(keys) == len(set(keys))

    def test_merge_sorted_deterministic(self):
        mgr = get_provider_manager()
        p = SketchfabProvider()
        r1 = p.search(category="", limit=10)
        merged1 = mgr.merge_results([r1])
        merged2 = mgr.merge_results([r1])
        assert [a.asset_id for a in merged1] == [a.asset_id for a in merged2]

    def test_deduplicate_results(self):
        mgr = get_provider_manager()
        p = SketchfabProvider()
        assets = p.search(category="prop", limit=5).normalized_assets
        # Double the list
        doubled = assets + assets
        deduped = mgr.deduplicate_results(doubled)
        assert len(deduped) == len(assets)


class TestStatistics:
    def test_statistics_structure(self):
        mgr = get_provider_manager()
        s = mgr.get_statistics()
        assert "total_providers" in s
        assert "available_providers" in s
        assert "query_count" in s
        assert "merge_count" in s

    def test_query_count_increments(self):
        mgr = get_provider_manager()
        mgr.register_provider(SketchfabProvider())
        initial = mgr.get_statistics()["query_count"]
        mgr.query_providers(category="prop")
        assert mgr.get_statistics()["query_count"] == initial + 1

    def test_merge_count_increments(self):
        mgr = get_provider_manager()
        initial = mgr.get_statistics()["merge_count"]
        p = SketchfabProvider()
        mgr.merge_results([p.search(category="prop")])
        assert mgr.get_statistics()["merge_count"] == initial + 1
