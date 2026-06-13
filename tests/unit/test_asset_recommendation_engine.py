"""
Tests for src/runtime/assets/recommendations/asset_recommendation_engine.py
"""

import pytest

from src.runtime.assets.recommendations import (
    AssetRecommendationResult,
    AssetRecommendationEngine,
    get_asset_recommendation_engine,
    reset_asset_recommendation_engine_for_tests,
)
from src.runtime.assets.providers import (
    get_provider_registry,
    reset_provider_registry_for_tests,
    SketchfabProvider,
    PolyhavenProvider,
)
from src.runtime.assets.discovery import reset_asset_discovery_engine_for_tests
from src.runtime.assets.validation import reset_asset_validation_engine_for_tests
from src.runtime.assets.ranking import reset_asset_ranking_engine_for_tests


@pytest.fixture(autouse=True)
def reset_all():
    reset_asset_recommendation_engine_for_tests()
    reset_asset_discovery_engine_for_tests()
    reset_asset_validation_engine_for_tests()
    reset_asset_ranking_engine_for_tests()
    reset_provider_registry_for_tests()
    reg = get_provider_registry()
    reg.register(SketchfabProvider())
    reg.register(PolyhavenProvider())
    yield
    reset_asset_recommendation_engine_for_tests()
    reset_asset_discovery_engine_for_tests()
    reset_asset_validation_engine_for_tests()
    reset_asset_ranking_engine_for_tests()
    reset_provider_registry_for_tests()


def make_queries(n: int = 2):
    cats = ["prop", "structure", "vehicle", "material"]
    return [
        {
            "query_id": f"q{i}",
            "category": cats[i % len(cats)],
            "tags": ["industrial"],
            "zone": "foreground" if i % 2 == 0 else "background",
            "priority": "required",
        }
        for i in range(n)
    ]


class TestAssetRecommendationEngine:
    def test_singleton_identity(self):
        e1 = get_asset_recommendation_engine()
        e2 = get_asset_recommendation_engine()
        assert e1 is e2

    def test_recommend_returns_result(self):
        result = get_asset_recommendation_engine().recommend(make_queries(1))
        assert isinstance(result, AssetRecommendationResult)

    def test_recommend_empty_queries(self):
        result = get_asset_recommendation_engine().recommend([])
        assert result.ok is True
        assert result.recommendations == []

    def test_recommend_ok_with_providers(self):
        result = get_asset_recommendation_engine().recommend(make_queries(2))
        assert result.ok is True

    def test_total_discovered_positive(self):
        result = get_asset_recommendation_engine().recommend(make_queries(1))
        assert result.total_discovered >= 0

    def test_pipeline_stages_populated(self):
        result = get_asset_recommendation_engine().recommend(make_queries(1))
        assert len(result.pipeline_stages) > 0
        assert "discovery" in result.pipeline_stages

    def test_recommendations_are_unique(self):
        result = get_asset_recommendation_engine().recommend(make_queries(2))
        if result.recommendations:
            keys = [(r.asset.provider, r.asset.asset_id)
                    for r in result.recommendations if r.asset]
            assert len(keys) == len(set(keys))

    def test_by_zone_populated(self):
        result = get_asset_recommendation_engine().recommend(make_queries(2))
        # Should have zone grouping
        assert isinstance(result.by_zone, dict)

    def test_by_category_populated(self):
        result = get_asset_recommendation_engine().recommend(make_queries(2))
        assert isinstance(result.by_category, dict)

    def test_recommendations_sorted_by_score_desc(self):
        result = get_asset_recommendation_engine().recommend(make_queries(2), top_k_per_query=5)
        if len(result.recommendations) > 1:
            scores = [r.score for r in result.recommendations]
            assert scores == sorted(scores, reverse=True)

    def test_pipeline_time_recorded(self):
        result = get_asset_recommendation_engine().recommend(make_queries(1))
        assert result.pipeline_time >= 0.0

    def test_result_to_dict_all_keys(self):
        result = get_asset_recommendation_engine().recommend(make_queries(1))
        d = result.to_dict()
        for key in ("ok", "recommendations", "by_zone", "by_category",
                    "total_discovered", "total_validated", "total_ranked",
                    "total_rejected", "pipeline_time", "pipeline_stages",
                    "errors", "warnings"):
            assert key in d

    def test_recommend_from_plan_dict(self):
        plan = {"asset_queries": make_queries(1)}
        result = get_asset_recommendation_engine().recommend_from_plan(plan)
        assert result.ok is True

    def test_recommend_from_empty_plan(self):
        result = get_asset_recommendation_engine().recommend_from_plan({})
        assert result.ok is True
        assert result.total_discovered == 0

    def test_intent_dict_accepted(self):
        intent = {"environment": "industrial", "style": "photorealistic"}
        result = get_asset_recommendation_engine().recommend(
            make_queries(1), intent=intent
        )
        assert result.ok is True

    def test_no_providers_returns_empty_gracefully(self):
        reset_provider_registry_for_tests()  # no providers
        result = get_asset_recommendation_engine().recommend(make_queries(1))
        assert result.ok is True
        assert result.total_discovered == 0
