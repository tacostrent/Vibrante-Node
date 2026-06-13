"""Tests for vector_search_engine.py (Tier 12.8)."""
from __future__ import annotations
import pytest
from src.runtime.assets.vector_search import (
    DeterministicEmbeddingProvider, VectorSearchResponse,
    get_vector_search_engine, reset_vector_search_engine_for_tests,
    get_asset_vector_store, reset_asset_vector_store_for_tests,
    get_asset_embedding_builder, reset_asset_embedding_builder_for_tests,
    set_embedding_provider, reset_embedding_provider_for_tests,
    get_retrieval_statistics, reset_retrieval_statistics_for_tests,
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
    reset_vector_search_engine_for_tests()
    reset_asset_catalog_for_tests()
    reset_semantic_asset_enricher_for_tests()
    reset_retrieval_statistics_for_tests()
    set_embedding_provider(DeterministicEmbeddingProvider())
    yield
    reset_vector_search_engine_for_tests()
    reset_asset_vector_store_for_tests()
    reset_asset_embedding_builder_for_tests()
    reset_asset_catalog_for_tests()
    reset_retrieval_statistics_for_tests()
    reset_embedding_provider_for_tests()


def _populate_store():
    catalog = get_asset_catalog()
    store   = get_asset_vector_store()
    builder = get_asset_embedding_builder()
    assets = [
        {"asset_id": "pipe001", "name": "Industrial Pipe", "category": "prop",
         "tags": ["pipe", "industrial"], "environments": ["industrial_hangar"],
         "roles": ["set_dressing"], "lookdev": ["industrial"], "semantic_tags": ["industrial_hangar"]},
        {"asset_id": "robot001", "name": "Robot Arm", "category": "machinery",
         "tags": ["robot", "arm"], "environments": ["robotics_lab"],
         "roles": ["support"], "lookdev": ["sci_fi"], "semantic_tags": ["robotics_lab"]},
    ]
    for a in assets:
        catalog.register_asset(a["asset_id"], a)
        ea = builder.build_embedding(a)
        store.add_vector(ea.asset_id, ea.vector)
    return assets


class TestVectorSearchEngine:
    def test_empty_store_returns_advisory(self):
        resp = get_vector_search_engine().search("industrial pipe")
        assert resp.ok is True
        assert resp.total == 0
        assert any("empty" in e.lower() for e in resp.errors)

    def test_search_returns_results(self):
        _populate_store()
        resp = get_vector_search_engine().search("industrial pipe")
        assert resp.ok is True
        assert resp.total > 0

    def test_search_environment_returns_results(self):
        _populate_store()
        resp = get_vector_search_engine().search_environment("robotics_lab")
        assert resp.ok is True

    def test_search_role_returns_results(self):
        _populate_store()
        resp = get_vector_search_engine().search_role("set_dressing")
        assert resp.ok is True

    def test_search_storytelling(self):
        _populate_store()
        resp = get_vector_search_engine().search_storytelling("context_builder")
        assert resp.ok is True

    def test_search_cinematic(self):
        _populate_store()
        resp = get_vector_search_engine().search_cinematic("depth_layer")
        assert resp.ok is True

    def test_search_top_k(self):
        _populate_store()
        ids = get_vector_search_engine().search_top_k("industrial", k=2)
        assert isinstance(ids, list)

    def test_index_asset(self):
        a = {"asset_id": "new_001", "name": "New Asset", "tags": ["new"]}
        get_asset_catalog().register_asset("new_001", a)
        ok = get_vector_search_engine().index_asset(a)
        assert ok is True
        assert get_asset_vector_store().contains("new_001")

    def test_response_to_dict(self):
        _populate_store()
        resp = get_vector_search_engine().search("robot")
        d = resp.to_dict()
        assert "ok" in d
        assert "results" in d
        assert "total" in d

    def test_statistics(self):
        _populate_store()
        before = get_vector_search_engine().get_statistics()["search_count"]
        get_vector_search_engine().search("pipe")
        assert get_vector_search_engine().get_statistics()["search_count"] == before + 1
