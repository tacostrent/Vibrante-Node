"""
Tests for src/runtime/assets/ranking/asset_ranking_engine.py
"""

import pytest

from src.runtime.assets.ranking import (
    RankingResult,
    AssetRankingEngine,
    get_asset_ranking_engine,
    reset_asset_ranking_engine_for_tests,
)
from src.runtime.assets.schema import AssetDescriptor, AssetRecommendation


@pytest.fixture(autouse=True)
def reset():
    reset_asset_ranking_engine_for_tests()
    yield
    reset_asset_ranking_engine_for_tests()


def make_assets(n: int = 5) -> list:
    cats = ["prop", "vehicle", "character", "structure", "machinery"]
    return [
        AssetDescriptor(
            asset_id=f"a{i}",
            provider="test",
            name=f"Asset {i}",
            category=cats[i % len(cats)],
            tags=["industrial", "metal"] if i % 2 == 0 else ["sci_fi", "futuristic"],
            formats=["fbx", "gltf"],
            rating=float(i % 5),
            popularity=i * 1000,
            style="photorealistic",
            environment_suitability=["industrial"] if i % 2 == 0 else ["sci_fi"],
        )
        for i in range(n)
    ]


class TestAssetRankingEngine:
    def test_singleton_identity(self):
        r1 = get_asset_ranking_engine()
        r2 = get_asset_ranking_engine()
        assert r1 is r2

    def test_rank_returns_result(self):
        result = get_asset_ranking_engine().rank(make_assets())
        assert isinstance(result, RankingResult)
        assert result.ok is True

    def test_rank_empty_assets(self):
        result = get_asset_ranking_engine().rank([])
        assert result.ok is True
        assert result.ranked_count == 0
        assert result.recommendations == []

    def test_top_k_respected(self):
        result = get_asset_ranking_engine().rank(make_assets(10), top_k=3)
        assert result.ranked_count <= 3

    def test_top_k_greater_than_input(self):
        result = get_asset_ranking_engine().rank(make_assets(2), top_k=10)
        assert result.ranked_count == 2

    def test_recommendations_sorted_by_score_desc(self):
        result = get_asset_ranking_engine().rank(make_assets(5))
        scores = [r.score for r in result.recommendations]
        assert scores == sorted(scores, reverse=True)

    def test_recommendation_has_required_fields(self):
        result = get_asset_ranking_engine().rank(make_assets(1))
        rec = result.recommendations[0]
        assert isinstance(rec, AssetRecommendation)
        assert rec.asset is not None
        assert 0.0 <= rec.score <= 1.0
        assert rec.rank == 1
        assert isinstance(rec.score_breakdown, dict)
        assert isinstance(rec.boost_reasons, list)

    def test_score_breakdown_has_all_factors(self):
        result = get_asset_ranking_engine().rank(make_assets(1))
        bd = result.recommendations[0].score_breakdown
        for factor in ("intent_match", "plan_match", "pattern_match",
                       "graph_match", "history_score", "provider_score"):
            assert factor in bd

    def test_score_breakdown_values_in_range(self):
        result = get_asset_ranking_engine().rank(make_assets(3))
        for rec in result.recommendations:
            for v in rec.score_breakdown.values():
                assert 0.0 <= v <= 1.0

    def test_rank_numbers_sequential(self):
        result = get_asset_ranking_engine().rank(make_assets(3))
        ranks = [r.rank for r in result.recommendations]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_zone_and_category_propagated(self):
        result = get_asset_ranking_engine().rank(
            make_assets(1), zone="foreground", category="prop"
        )
        assert result.recommendations[0].zone == "foreground"
        assert result.recommendations[0].category == "prop"

    def test_intent_dict_used_for_scoring(self):
        intent = {"environment": "industrial", "style": "photorealistic", "keywords": ["metal"]}
        result = get_asset_ranking_engine().rank(make_assets(3), intent=intent)
        # Industrial + metal assets should score higher — just verify no crash
        assert result.ok is True

    def test_determinism(self):
        assets = make_assets(5)
        r1 = get_asset_ranking_engine().rank(assets, zone="foreground", category="prop", top_k=5)
        r2 = get_asset_ranking_engine().rank(assets, zone="foreground", category="prop", top_k=5)
        ids1 = [r.asset.asset_id for r in r1.recommendations]
        ids2 = [r.asset.asset_id for r in r2.recommendations]
        assert ids1 == ids2

    def test_provider_score_uses_rating_and_popularity(self):
        engine = get_asset_ranking_engine()
        high = AssetDescriptor(asset_id="h", provider="t", name="H", category="prop",
                               rating=5.0, popularity=50000, formats=["fbx"])
        low  = AssetDescriptor(asset_id="l", provider="t", name="L", category="prop",
                               rating=0.0, popularity=0, formats=["fbx"])
        result = engine.rank([high, low], top_k=2)
        assert result.recommendations[0].asset.asset_id == "h"

    def test_ranking_time_recorded(self):
        result = get_asset_ranking_engine().rank(make_assets(3))
        assert result.ranking_time >= 0.0

    def test_result_to_dict_structure(self):
        result = get_asset_ranking_engine().rank(make_assets(2))
        d = result.to_dict()
        assert "ok" in d
        assert "recommendations" in d
        assert "ranked_count" in d
