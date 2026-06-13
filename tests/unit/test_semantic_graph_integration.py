"""
Tests for Tier 6 semantic layer integration with Tier 5 AssetKnowledgeGraph.
No bridge, no LLM, no live databases. Pure unit tests.
"""
import pytest
import pytest_asyncio
from src.runtime.semantic.recommendations.intent_recommendation_engine import (
    IntentRecommendationEngine,
    reset_intent_recommendation_engine_for_tests,
)
from src.runtime.semantic.schema.scene_intent_schema import SceneIntent
from src.runtime.asset_knowledge_graph import (
    AssetKnowledgeGraph,
    get_asset_knowledge_graph,
    reset_asset_knowledge_graph_for_tests,
)
from src.runtime.production_memory import reset_production_memory_for_tests
from src.runtime.pattern_library import reset_pattern_library_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_intent_recommendation_engine_for_tests()
    reset_asset_knowledge_graph_for_tests()
    reset_production_memory_for_tests()
    reset_pattern_library_for_tests()
    yield
    reset_intent_recommendation_engine_for_tests()
    reset_asset_knowledge_graph_for_tests()
    reset_production_memory_for_tests()
    reset_pattern_library_for_tests()


@pytest.mark.asyncio
async def test_graph_recs_returned_for_known_scene_type():
    """AssetKnowledgeGraph is seeded with assets for industrial_hangar."""
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)
    graph_recs = [r for r in result.recommendations if r.source == "graph"]
    assert len(graph_recs) > 0


@pytest.mark.asyncio
async def test_graph_recs_confidence_is_0_65():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)
    for r in result.recommendations:
        if r.source == "graph":
            assert r.confidence == 0.65


@pytest.mark.asyncio
async def test_graph_recs_have_asset_type():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)
    graph_recs = [r for r in result.recommendations if r.source == "graph"]
    for r in graph_recs:
        assert r.recommendation_type == "asset"


@pytest.mark.asyncio
async def test_graph_recs_have_reason():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)
    for r in result.recommendations:
        if r.source == "graph":
            assert len(r.reason) > 0


@pytest.mark.asyncio
async def test_graph_recs_are_known_asset_ids():
    """Returned asset IDs should match what's seeded in the knowledge graph."""
    known_assets = {"industrial_pipe", "maintenance_robot", "storage_crate", "metal_platform"}
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)
    graph_values = {r.value for r in result.recommendations if r.source == "graph"}
    assert graph_values.issubset(known_assets), \
        f"Unexpected graph assets: {graph_values - known_assets}"


@pytest.mark.asyncio
async def test_unknown_scene_type_returns_no_graph_recs():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="completely_nonexistent_xyz_env_9999")
    result = await engine.get_recommendations(intent)
    graph_recs = [r for r in result.recommendations if r.source == "graph"]
    assert len(graph_recs) == 0


@pytest.mark.asyncio
async def test_graph_graceful_on_error(monkeypatch):
    """Engine falls back to defaults when AssetKnowledgeGraph raises."""
    import src.runtime.asset_knowledge_graph as graph_mod

    def _raise():
        raise RuntimeError("simulated graph error")

    monkeypatch.setattr(graph_mod, "get_asset_knowledge_graph", _raise)

    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)
    assert len(result.recommendations) > 0
    sources = {r.source for r in result.recommendations}
    assert "default" in sources


@pytest.mark.asyncio
async def test_graph_recs_ranked_below_memory_and_patterns():
    """Graph recs (0.65) should appear after memory (0.95) and pattern (0.80)."""
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)

    graph_confidences = [r.confidence for r in result.recommendations if r.source == "graph"]
    other_confidences = [r.confidence for r in result.recommendations
                         if r.source in ("memory", "pattern")]
    for gc in graph_confidences:
        for oc in other_confidences:
            assert gc <= oc, f"Graph rec (conf={gc}) should be <= memory/pattern (conf={oc})"
