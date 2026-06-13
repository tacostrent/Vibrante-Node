"""Tests for hybrid_ranking_engine.py (Tier 12.8)."""
from __future__ import annotations
import pytest
from src.runtime.assets.vector_search import (
    RankedAsset, HybridRankingEngine,
    get_hybrid_ranking_engine, reset_hybrid_ranking_engine_for_tests,
)
from src.runtime.assets.semantic import reset_asset_knowledge_graph_for_tests


@pytest.fixture(autouse=True)
def _reset():
    reset_hybrid_ranking_engine_for_tests()
    reset_asset_knowledge_graph_for_tests()
    yield
    reset_hybrid_ranking_engine_for_tests()
    reset_asset_knowledge_graph_for_tests()


_CANDIDATES = [
    {
        "asset_id": "hero_pipe",
        "name": "Hero Pipe",
        "environments": ["industrial_hangar"],
        "primary_env": "industrial_hangar",
        "roles": ["hero"],
        "primary_role": "hero",
        "storytelling": "hero_object",
        "lookdev": ["industrial"],
        "primary_lookdev": "industrial",
        "importance": "primary",
    },
    {
        "asset_id": "bg_arch",
        "name": "Background Architecture",
        "environments": ["abandoned_factory"],
        "primary_env": "abandoned_factory",
        "roles": ["background"],
        "primary_role": "background",
        "storytelling": "context_builder",
        "lookdev": ["aged"],
        "primary_lookdev": "aged",
        "importance": "tertiary",
    },
    {
        "asset_id": "support_gear",
        "name": "Support Gear",
        "environments": ["industrial_hangar"],
        "primary_env": "industrial_hangar",
        "roles": ["support"],
        "primary_role": "support",
        "storytelling": "context_builder",
        "lookdev": ["industrial", "weathered"],
        "primary_lookdev": "industrial",
        "importance": "secondary",
    },
]

_CTX = {
    "environment": "industrial_hangar",
    "role": "hero",
    "storytelling": "hero_object",
    "lookdev": "industrial",
}


class TestHybridRankingEngine:
    def test_rank_returns_ranked_assets(self):
        ranked = get_hybrid_ranking_engine().rank_assets(_CANDIDATES, _CTX)
        assert len(ranked) == 3
        assert all(isinstance(r, RankedAsset) for r in ranked)

    def test_hero_pipe_ranks_first(self):
        ranked = get_hybrid_ranking_engine().rank_assets(_CANDIDATES, _CTX)
        assert ranked[0].asset_id == "hero_pipe"

    def test_ranks_are_sequential(self):
        ranked = get_hybrid_ranking_engine().rank_assets(_CANDIDATES, _CTX)
        ranks = [r.rank for r in ranked]
        assert ranks == list(range(1, len(ranked) + 1))

    def test_scores_descending(self):
        ranked = get_hybrid_ranking_engine().rank_assets(_CANDIDATES, _CTX)
        scores = [r.total_score for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_score_breakdown_has_all_dimensions(self):
        ranked = get_hybrid_ranking_engine().rank_assets(_CANDIDATES, _CTX)
        for r in ranked:
            assert "vector_similarity" in r.score_breakdown
            assert "environment_fit" in r.score_breakdown
            assert "storytelling_match" in r.score_breakdown
            assert "lookdev_match" in r.score_breakdown

    def test_env_match_boosts_score(self):
        ranked = get_hybrid_ranking_engine().rank_assets(_CANDIDATES, _CTX)
        hero = next(r for r in ranked if r.asset_id == "hero_pipe")
        bg   = next(r for r in ranked if r.asset_id == "bg_arch")
        # hero_pipe matches industrial_hangar, bg_arch does not
        assert hero.score_breakdown["environment_fit"] > bg.score_breakdown["environment_fit"]

    def test_vector_scores_used(self):
        vs = {"hero_pipe": 0.9, "bg_arch": 0.1, "support_gear": 0.5}
        ranked = get_hybrid_ranking_engine().rank_assets(_CANDIDATES, _CTX, vs)
        hero = next(r for r in ranked if r.asset_id == "hero_pipe")
        assert hero.score_breakdown["vector_similarity"] > 0.5

    def test_empty_candidates(self):
        ranked = get_hybrid_ranking_engine().rank_assets([], _CTX)
        assert ranked == []

    def test_empty_context(self):
        ranked = get_hybrid_ranking_engine().rank_assets(_CANDIDATES, {})
        assert len(ranked) == 3
        assert all(r.total_score >= 0 for r in ranked)

    def test_deterministic(self):
        r1 = get_hybrid_ranking_engine().rank_assets(_CANDIDATES, _CTX)
        r2 = get_hybrid_ranking_engine().rank_assets(_CANDIDATES, _CTX)
        assert [r.asset_id for r in r1] == [r.asset_id for r in r2]

    def test_to_dict_from_dict(self):
        ranked = get_hybrid_ranking_engine().rank_assets(_CANDIDATES, _CTX)
        d = ranked[0].to_dict()
        r = RankedAsset.from_dict(d)
        assert r.asset_id == ranked[0].asset_id
        assert r.rank == ranked[0].rank

    def test_statistics(self):
        before = get_hybrid_ranking_engine().get_statistics()["rank_count"]
        get_hybrid_ranking_engine().rank_assets(_CANDIDATES, _CTX)
        assert get_hybrid_ranking_engine().get_statistics()["rank_count"] == before + 1
