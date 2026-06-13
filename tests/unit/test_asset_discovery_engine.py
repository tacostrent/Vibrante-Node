"""
Tests for src/runtime/assets/discovery/asset_discovery_engine.py
"""

import pytest

from src.runtime.assets.discovery import (
    AssetDiscoveryEngine,
    DiscoveryResult,
    get_asset_discovery_engine,
    reset_asset_discovery_engine_for_tests,
)
from src.runtime.assets.providers import (
    get_provider_registry,
    reset_provider_registry_for_tests,
    SketchfabProvider,
    PolyhavenProvider,
)


@pytest.fixture(autouse=True)
def reset_all():
    reset_asset_discovery_engine_for_tests()
    reset_provider_registry_for_tests()
    # Register default providers
    reg = get_provider_registry()
    reg.register(SketchfabProvider())
    reg.register(PolyhavenProvider())
    yield
    reset_asset_discovery_engine_for_tests()
    reset_provider_registry_for_tests()


class TestAssetDiscoveryEngine:
    def test_singleton_identity(self):
        e1 = get_asset_discovery_engine()
        e2 = get_asset_discovery_engine()
        assert e1 is e2

    def test_discover_returns_result(self):
        queries = [{"query_id": "q1", "category": "prop", "tags": ["industrial"], "zone": "foreground"}]
        result = get_asset_discovery_engine().discover(queries)
        assert isinstance(result, DiscoveryResult)
        assert result.ok is True

    def test_discover_empty_queries(self):
        result = get_asset_discovery_engine().discover([])
        assert result.ok is True
        assert result.total_assets == 0
        assert result.query_results == []

    def test_discover_returns_assets(self):
        queries = [{"query_id": "q1", "category": "prop", "tags": [], "zone": "foreground"}]
        result = get_asset_discovery_engine().discover(queries)
        assert result.total_assets > 0
        assert len(result.query_results) == 1

    def test_providers_queried_populated(self):
        queries = [{"query_id": "q1", "category": "prop", "tags": [], "zone": "foreground"}]
        result = get_asset_discovery_engine().discover(queries)
        assert len(result.providers_queried) > 0
        assert "sketchfab" in result.providers_queried

    def test_no_duplicates_across_providers(self):
        queries = [{"query_id": "q1", "category": "", "tags": [], "zone": "foreground"}]
        result = get_asset_discovery_engine().discover(queries)
        if result.query_results:
            assets = result.query_results[0].assets
            keys = [(a.provider, a.asset_id) for a in assets]
            assert len(keys) == len(set(keys))

    def test_multiple_queries(self):
        queries = [
            {"query_id": "q1", "category": "prop",    "tags": [], "zone": "foreground"},
            {"query_id": "q2", "category": "material", "tags": [], "zone": "background"},
        ]
        result = get_asset_discovery_engine().discover(queries)
        assert len(result.query_results) == 2

    def test_pipeline_stages_populated(self):
        queries = [{"query_id": "q1", "category": "prop", "tags": [], "zone": "foreground"}]
        result = get_asset_discovery_engine().discover(queries)
        assert "providers_resolved" in result.pipeline_stages
        assert "discovery_complete" in result.pipeline_stages

    def test_discovery_time_recorded(self):
        queries = [{"query_id": "q1", "category": "prop", "tags": [], "zone": "foreground"}]
        result = get_asset_discovery_engine().discover(queries)
        assert result.discovery_time >= 0.0

    def test_discover_from_plan_dict(self):
        plan = {
            "asset_queries": [
                {"query_id": "q1", "category": "prop", "tags": [], "zone": "foreground"}
            ]
        }
        result = get_asset_discovery_engine().discover_from_plan(plan)
        assert result.ok is True
        assert len(result.query_results) == 1

    def test_discover_from_empty_plan(self):
        result = get_asset_discovery_engine().discover_from_plan({})
        assert result.ok is True
        assert result.total_assets == 0

    def test_zone_preserved_in_result(self):
        queries = [{"query_id": "q1", "category": "prop", "tags": [], "zone": "midground"}]
        result = get_asset_discovery_engine().discover(queries)
        assert result.query_results[0].zone == "midground"

    def test_category_preserved_in_result(self):
        queries = [{"query_id": "q1", "category": "vehicle", "tags": [], "zone": "foreground"}]
        result = get_asset_discovery_engine().discover(queries)
        assert result.query_results[0].category == "vehicle"

    def test_result_to_dict(self):
        queries = [{"query_id": "q1", "category": "prop", "tags": [], "zone": "foreground"}]
        result = get_asset_discovery_engine().discover(queries)
        d = result.to_dict()
        assert "ok" in d
        assert "total_assets" in d
        assert "query_results" in d
        assert "providers_queried" in d

    def test_no_providers_returns_empty(self):
        reset_provider_registry_for_tests()
        queries = [{"query_id": "q1", "category": "prop", "tags": [], "zone": "foreground"}]
        result = get_asset_discovery_engine().discover(queries)
        assert result.ok is True
        assert result.total_assets == 0
