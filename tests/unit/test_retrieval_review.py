"""Tests for retrieval_review.py (Tier 12.8)."""
from __future__ import annotations
import pytest
from src.runtime.assets.vector_search import (
    DeterministicEmbeddingProvider, RetrievalReviewResult,
    get_retrieval_review, reset_retrieval_review_for_tests,
    get_retrieval_statistics, reset_retrieval_statistics_for_tests,
    set_embedding_provider, reset_embedding_provider_for_tests,
    reset_retrieval_pipeline_for_tests, reset_hybrid_ranking_engine_for_tests,
    reset_vector_search_engine_for_tests, reset_asset_vector_store_for_tests,
    reset_asset_embedding_builder_for_tests, reset_intent_parser_for_tests,
    reset_intent_embedding_engine_for_tests,
)
from src.runtime.assets.semantic import (
    reset_asset_catalog_for_tests, reset_semantic_asset_enricher_for_tests,
    reset_asset_environment_mapper_for_tests, reset_asset_role_classifier_for_tests,
    reset_asset_storytelling_mapper_for_tests, reset_asset_lookdev_mapper_for_tests,
    reset_asset_cinematic_mapper_for_tests, reset_asset_knowledge_graph_for_tests,
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
    reset_retrieval_review_for_tests()
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
    reset_retrieval_review_for_tests()
    reset_retrieval_statistics_for_tests()
    reset_embedding_provider_for_tests()
    reset_asset_catalog_for_tests()


_ENV_RESULTS = [
    {"asset_id": f"a{i}", "environments": ["industrial_hangar"],
     "roles": ["hero"], "total_score": 0.8 - i * 0.1}
    for i in range(5)
]


class TestRetrievalReview:
    def test_review_results_good(self):
        ctx = {"environment": "industrial_hangar", "role": "hero"}
        rev = get_retrieval_review().review_results(ctx, _ENV_RESULTS)
        assert rev.ok is True
        assert rev.score >= 0

    def test_review_results_empty_returns_zero_score(self):
        rev = get_retrieval_review().review_results({}, [])
        assert rev.ok is True
        assert rev.score == 0.0
        assert any("no results" in f for f in rev.findings)

    def test_env_accuracy_perfect_match(self):
        ctx = {"environment": "industrial_hangar"}
        results = [
            {"asset_id": f"a{i}", "environments": ["industrial_hangar"],
             "primary_env": "industrial_hangar", "total_score": 0.8}
            for i in range(5)
        ]
        rev = get_retrieval_review().review_results(ctx, results)
        assert rev.environment_accuracy == 1.0

    def test_env_accuracy_no_match(self):
        ctx = {"environment": "robotics_lab"}
        results = [
            {"asset_id": f"a{i}", "environments": ["industrial_hangar"], "total_score": 0.5}
            for i in range(5)
        ]
        rev = get_retrieval_review().review_results(ctx, results)
        assert rev.environment_accuracy == 0.0

    def test_grade_a_for_high_score(self):
        ctx = {"environment": "industrial_hangar", "role": "hero"}
        results = [
            {"asset_id": f"a{i}", "environments": ["industrial_hangar"],
             "roles": ["hero"], "total_score": 0.9}
            for i in range(10)
        ]
        rev = get_retrieval_review().review_results(ctx, results)
        assert rev.grade in ("A", "B")

    def test_production_ready_requires_score_07(self):
        # With empty results, score is 0 → not production ready
        rev = get_retrieval_review().review_results({}, [])
        assert rev.production_ready is False

    def test_review_pipeline_no_queries(self):
        rev = get_retrieval_review().review_pipeline()
        assert rev.ok is True
        assert rev.production_ready is False
        assert any("no queries" in f for f in rev.findings)

    def test_review_pipeline_after_queries(self):
        stats = get_retrieval_statistics()
        stats.record(query="test", score=0.8, result_count=5)
        stats.record(query="test2", score=0.7, result_count=3)
        rev = get_retrieval_review().review_pipeline()
        assert rev.ok is True
        assert rev.score > 0.0

    def test_to_dict_from_dict(self):
        ctx = {"environment": "industrial_hangar"}
        rev = get_retrieval_review().review_results(ctx, _ENV_RESULTS)
        d = rev.to_dict()
        r2 = RetrievalReviewResult.from_dict(d)
        assert r2.score == rev.score
        assert r2.grade == rev.grade

    def test_grade_mapping(self):
        from src.runtime.assets.vector_search.retrieval_review import _grade
        assert _grade(0.9) == "A"
        assert _grade(0.75) == "B"
        assert _grade(0.6) == "C"
        assert _grade(0.45) == "D"
        assert _grade(0.1) == "F"

    def test_statistics_increments(self):
        before = get_retrieval_review().get_statistics()["review_count"]
        get_retrieval_review().review_results({}, _ENV_RESULTS)
        assert get_retrieval_review().get_statistics()["review_count"] == before + 1
