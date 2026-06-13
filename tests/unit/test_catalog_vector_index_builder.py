"""Tests for catalog_vector_index_builder.py (Tier 12.8)."""
from __future__ import annotations
import pytest
from src.runtime.assets.vector_search import (
    DeterministicEmbeddingProvider, IndexBuildResult,
    get_catalog_vector_index_builder, reset_catalog_vector_index_builder_for_tests,
    get_asset_vector_store, reset_asset_vector_store_for_tests,
    get_asset_embedding_builder, reset_asset_embedding_builder_for_tests,
    set_embedding_provider, reset_embedding_provider_for_tests,
)
from src.runtime.assets.semantic import (
    get_asset_catalog, reset_asset_catalog_for_tests,
    reset_semantic_asset_enricher_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_embedding_provider_for_tests()
    reset_asset_embedding_builder_for_tests()
    reset_asset_vector_store_for_tests()
    reset_catalog_vector_index_builder_for_tests()
    reset_asset_catalog_for_tests()
    reset_semantic_asset_enricher_for_tests()
    set_embedding_provider(DeterministicEmbeddingProvider())
    yield
    reset_catalog_vector_index_builder_for_tests()
    reset_asset_vector_store_for_tests()
    reset_asset_catalog_for_tests()
    reset_embedding_provider_for_tests()


_ASSETS = [
    {"asset_id": f"a{i:02d}", "name": f"Asset {i}", "category": "prop",
     "tags": ["industrial"], "environments": ["industrial_hangar"],
     "semantic_tags": ["industrial_hangar"], "roles": ["set_dressing"]}
    for i in range(5)
]


class TestCatalogVectorIndexBuilder:
    def test_build_full_empty_catalog(self):
        result = get_catalog_vector_index_builder().build_full_index()
        assert isinstance(result, IndexBuildResult)
        assert result.ok is True
        assert result.indexed == 0

    def test_build_full_indexes_catalog(self):
        catalog = get_asset_catalog()
        for a in _ASSETS:
            catalog.register_asset(a["asset_id"], a)
        result = get_catalog_vector_index_builder().build_full_index()
        assert result.ok is True
        assert result.indexed == 5
        assert get_asset_vector_store().size() == 5

    def test_build_full_skips_existing(self):
        catalog = get_asset_catalog()
        for a in _ASSETS:
            catalog.register_asset(a["asset_id"], a)
        get_catalog_vector_index_builder().build_full_index()
        # Second call should skip existing
        result2 = get_catalog_vector_index_builder().build_full_index()
        assert result2.skipped == 5
        assert result2.indexed == 0

    def test_rebuild_index_clears_and_rebuilds(self):
        catalog = get_asset_catalog()
        for a in _ASSETS:
            catalog.register_asset(a["asset_id"], a)
        get_catalog_vector_index_builder().build_full_index()
        result = get_catalog_vector_index_builder().rebuild_index()
        assert result.ok is True
        assert result.indexed == 5
        assert result.strategy == "rebuild"

    def test_update_asset_index_existing(self):
        catalog = get_asset_catalog()
        catalog.register_asset("a00", _ASSETS[0])
        ok = get_catalog_vector_index_builder().update_asset_index("a00")
        assert ok is True
        assert get_asset_vector_store().contains("a00")

    def test_update_asset_index_missing(self):
        ok = get_catalog_vector_index_builder().update_asset_index("ghost_001")
        assert ok is False

    def test_statistics(self):
        stats = get_catalog_vector_index_builder().get_statistics()
        assert "build_count" in stats
        assert "store_size" in stats

    def test_to_dict_from_dict(self):
        result = get_catalog_vector_index_builder().build_full_index()
        d = result.to_dict()
        r2 = IndexBuildResult.from_dict(d)
        assert r2.ok == result.ok
        assert r2.indexed == result.indexed

    def test_duration_ms_non_negative(self):
        result = get_catalog_vector_index_builder().build_full_index()
        assert result.duration_ms >= 0.0
