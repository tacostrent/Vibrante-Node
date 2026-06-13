"""Tests for asset_embedding_builder.py (Tier 12.8)."""
from __future__ import annotations
import pytest
from src.runtime.assets.vector_search import (
    DeterministicEmbeddingProvider, EmbeddedAsset,
    get_asset_embedding_builder, reset_asset_embedding_builder_for_tests,
    set_embedding_provider, reset_embedding_provider_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_embedding_provider_for_tests()
    reset_asset_embedding_builder_for_tests()
    set_embedding_provider(DeterministicEmbeddingProvider())
    yield
    reset_asset_embedding_builder_for_tests()
    reset_embedding_provider_for_tests()


_ASSET = {
    "asset_id": "pipe001",
    "name": "Industrial Pipe",
    "category": "prop",
    "tags": ["pipe", "industrial"],
    "environments": ["industrial_hangar"],
    "roles": ["set_dressing"],
    "lookdev": ["industrial", "weathered"],
    "semantic_tags": ["industrial_hangar", "set_dressing"],
}


class TestAssetEmbeddingBuilder:
    def test_build_embedding_returns_embedded_asset(self):
        ea = get_asset_embedding_builder().build_embedding(_ASSET)
        assert isinstance(ea, EmbeddedAsset)
        assert ea.asset_id == "pipe001"

    def test_build_embedding_vector_128_dims(self):
        ea = get_asset_embedding_builder().build_embedding(_ASSET)
        assert len(ea.vector) == 128

    def test_build_embedding_empty_asset(self):
        ea = get_asset_embedding_builder().build_embedding({})
        assert isinstance(ea, EmbeddedAsset)
        assert len(ea.vector) == 128

    def test_build_embedding_none_no_exception(self):
        ea = get_asset_embedding_builder().build_embedding(None)
        assert isinstance(ea, EmbeddedAsset)

    def test_deterministic(self):
        b = get_asset_embedding_builder()
        e1 = b.build_embedding(_ASSET)
        e2 = b.build_embedding(_ASSET)
        assert e1.vector == e2.vector

    def test_different_assets_different_vectors(self):
        b = get_asset_embedding_builder()
        e1 = b.build_embedding(_ASSET)
        e2 = b.build_embedding({"asset_id": "robot01", "name": "Robot Arm",
                                  "category": "machinery", "tags": ["robot", "arm"]})
        assert e1.vector != e2.vector

    def test_build_catalog_embeddings(self):
        assets = [_ASSET, {**_ASSET, "asset_id": "pipe002", "name": "Pipe 2"}]
        results = get_asset_embedding_builder().build_catalog_embeddings(assets)
        assert len(results) == 2
        assert all(len(ea.vector) == 128 for ea in results)

    def test_build_catalog_embeddings_empty_list(self):
        results = get_asset_embedding_builder().build_catalog_embeddings([])
        assert results == []

    def test_update_embedding_same_as_build(self):
        b = get_asset_embedding_builder()
        e1 = b.build_embedding(_ASSET)
        e2 = b.update_embedding(_ASSET)
        assert e1.vector == e2.vector

    def test_rebuild_index_returns_count(self):
        assets = [_ASSET, {**_ASSET, "asset_id": "p2"}]
        count = get_asset_embedding_builder().rebuild_index(assets)
        assert count == 2

    def test_build_query_embedding(self):
        ev = get_asset_embedding_builder().build_query_embedding("industrial hangar hero")
        assert len(ev.vector) == 128

    def test_to_dict_from_dict(self):
        ea = get_asset_embedding_builder().build_embedding(_ASSET)
        d = ea.to_dict()
        r = EmbeddedAsset.from_dict(d)
        assert r.asset_id == ea.asset_id
        assert r.vector == ea.vector

    def test_statistics(self):
        b = get_asset_embedding_builder()
        before = b.get_statistics()["build_count"]
        b.build_embedding(_ASSET)
        assert b.get_statistics()["build_count"] == before + 1
