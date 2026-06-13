"""Tests for retrieval_pipeline.py (Tier 12.8)."""
from __future__ import annotations
import pytest
from src.runtime.assets.vector_search import (
    DeterministicEmbeddingProvider, RetrievalResult,
    get_retrieval_pipeline, reset_retrieval_pipeline_for_tests,
    get_asset_vector_store, reset_asset_vector_store_for_tests,
    get_asset_embedding_builder, reset_asset_embedding_builder_for_tests,
    set_embedding_provider, reset_embedding_provider_for_tests,
    get_retrieval_statistics, reset_retrieval_statistics_for_tests,
    reset_vector_search_engine_for_tests,
    reset_hybrid_ranking_engine_for_tests,
    reset_intent_parser_for_tests,
    reset_intent_embedding_engine_for_tests,
)
from src.runtime.assets.semantic import (
    get_asset_catalog, reset_asset_catalog_for_tests,
    reset_semantic_asset_enricher_for_tests,
    reset_asset_environment_mapper_for_tests,
    reset_asset_role_classifier_for_tests,
    reset_asset_storytelling_mapper_for_tests,
    reset_asset_lookdev_mapper_for_tests,
    reset_asset_cinematic_mapper_for_tests,
    reset_asset_knowledge_graph_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_embedding_provider_for_tests()
    reset_asset_embedding_builder_for_tests()
    reset_asset_vector_store_for_tests()
    reset_vector_search_engine_for_tests()
    reset_intent_parser_for_tests()
    reset_intent_embedding_engine_for_tests()
    reset_hybrid_ranking_engine_for_tests()
    reset_retrieval_pipeline_for_tests()
    reset_asset_catalog_for_tests()
    reset_semantic_asset_enricher_for_tests()
    reset_asset_environment_mapper_for_tests()
    reset_asset_role_classifier_for_tests()
    reset_asset_storytelling_mapper_for_tests()
    reset_asset_lookdev_mapper_for_tests()
    reset_asset_cinematic_mapper_for_tests()
    reset_asset_knowledge_graph_for_tests()
    reset_retrieval_statistics_for_tests()
    set_embedding_provider(DeterministicEmbeddingProvider())
    yield
    reset_retrieval_pipeline_for_tests()
    reset_asset_catalog_for_tests()
    reset_asset_vector_store_for_tests()
    reset_embedding_provider_for_tests()
    reset_retrieval_statistics_for_tests()


def _populate_catalog():
    catalog = get_asset_catalog()
    assets = [
        {"asset_id": "pipe001", "name": "Industrial Pipe", "category": "prop",
         "tags": ["pipe", "industrial"], "environments": ["industrial_hangar"],
         "primary_env": "industrial_hangar", "roles": ["set_dressing"],
         "primary_role": "set_dressing", "lookdev": ["industrial"],
         "storytelling": "context_builder", "cinematic_usage": ["depth_layer"],
         "importance": "ambient", "semantic_tags": ["industrial_hangar", "set_dressing"]},
        {"asset_id": "robot001", "name": "Robot Arm", "category": "machinery",
         "tags": ["robot", "arm"], "environments": ["robotics_lab"],
         "primary_env": "robotics_lab", "roles": ["hero"],
         "primary_role": "hero", "lookdev": ["sci_fi"],
         "storytelling": "hero_object", "cinematic_usage": ["hero_focus"],
         "importance": "primary", "semantic_tags": ["robotics_lab", "hero"]},
    ]
    for a in assets:
        catalog.register_asset(a["asset_id"], a)
        ea = get_asset_embedding_builder().build_embedding(a)
        get_asset_vector_store().add_vector(ea.asset_id, ea.vector)


class TestRetrievalPipeline:
    def test_retrieve_empty_catalog_returns_ok(self):
        result = get_retrieval_pipeline().retrieve("industrial hangar machinery")
        assert isinstance(result, RetrievalResult)
        assert result.ok is True

    def test_retrieve_with_catalog(self):
        _populate_catalog()
        result = get_retrieval_pipeline().retrieve("industrial hangar")
        assert result.ok is True
        assert isinstance(result.assets, list)

    def test_retrieve_includes_parsed_intent(self):
        _populate_catalog()
        result = get_retrieval_pipeline().retrieve("industrial hangar hero machinery")
        assert result.parsed_intent is not None
        assert isinstance(result.parsed_intent, dict)

    def test_retrieve_strategy_set(self):
        _populate_catalog()
        result = get_retrieval_pipeline().retrieve("robotics lab sensor")
        assert result.strategy in ("vector+hybrid", "catalog_fallback")

    def test_retrieve_environment_assets(self):
        _populate_catalog()
        result = get_retrieval_pipeline().retrieve_environment_assets("industrial_hangar")
        assert result.ok is True

    def test_retrieve_hero_assets(self):
        _populate_catalog()
        result = get_retrieval_pipeline().retrieve_hero_assets()
        assert result.ok is True

    def test_retrieve_storytelling_assets(self):
        _populate_catalog()
        result = get_retrieval_pipeline().retrieve_storytelling_assets("hero_object")
        assert result.ok is True

    def test_retrieve_no_vector_search(self):
        _populate_catalog()
        result = get_retrieval_pipeline().retrieve("industrial hangar", use_vector_search=False)
        assert result.ok is True
        assert result.strategy == "catalog_fallback"

    def test_to_dict_from_dict(self):
        result = get_retrieval_pipeline().retrieve("test")
        d = result.to_dict()
        r2 = RetrievalResult.from_dict(d)
        assert r2.ok == result.ok

    def test_duration_ms_non_negative(self):
        result = get_retrieval_pipeline().retrieve("test")
        assert result.duration_ms >= 0.0

    def test_statistics_increments(self):
        before = get_retrieval_pipeline().get_statistics()["retrieve_count"]
        get_retrieval_pipeline().retrieve("test")
        assert get_retrieval_pipeline().get_statistics()["retrieve_count"] == before + 1
