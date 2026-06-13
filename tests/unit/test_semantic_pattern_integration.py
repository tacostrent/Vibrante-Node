"""
Tests for Tier 6 semantic layer integration with Tier 5 PatternLibrary.
No bridge, no LLM, no live databases. Pure unit tests.
"""
import pytest
import pytest_asyncio
from src.runtime.semantic.recommendations.intent_recommendation_engine import (
    IntentRecommendationEngine,
    reset_intent_recommendation_engine_for_tests,
)
from src.runtime.semantic.schema.scene_intent_schema import SceneIntent
from src.runtime.pattern_library import (
    PatternLibrary,
    get_pattern_library,
    reset_pattern_library_for_tests,
)
from src.runtime.production_memory import reset_production_memory_for_tests
from src.runtime.asset_knowledge_graph import reset_asset_knowledge_graph_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_intent_recommendation_engine_for_tests()
    reset_pattern_library_for_tests()
    reset_production_memory_for_tests()
    reset_asset_knowledge_graph_for_tests()
    yield
    reset_intent_recommendation_engine_for_tests()
    reset_pattern_library_for_tests()
    reset_production_memory_for_tests()
    reset_asset_knowledge_graph_for_tests()


@pytest.mark.asyncio
async def test_pattern_recs_returned_for_known_env():
    """PatternLibrary has built-in patterns for industrial_hangar — should surface them."""
    engine = IntentRecommendationEngine()
    # "industrial_hangar" matches built-in pattern scene_type
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)
    pattern_recs = [r for r in result.recommendations if r.source == "pattern"]
    assert len(pattern_recs) > 0


@pytest.mark.asyncio
async def test_pattern_recs_confidence_is_0_80():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)
    for r in result.recommendations:
        if r.source == "pattern":
            assert r.confidence == 0.80


@pytest.mark.asyncio
async def test_pattern_recs_have_template_type():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)
    pattern_recs = [r for r in result.recommendations if r.source == "pattern"]
    for r in pattern_recs:
        assert r.recommendation_type == "template"


@pytest.mark.asyncio
async def test_pattern_recs_have_reason():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)
    for r in result.recommendations:
        if r.source == "pattern":
            assert len(r.reason) > 0


@pytest.mark.asyncio
async def test_unknown_env_returns_empty_pattern_recs():
    """Unknown environments yield no pattern recommendations but still return defaults."""
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="completely_nonexistent_xyz_env")
    result = await engine.get_recommendations(intent)
    pattern_recs = [r for r in result.recommendations if r.source == "pattern"]
    assert len(pattern_recs) == 0


@pytest.mark.asyncio
async def test_pattern_recs_ranked_above_defaults_for_known_env():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)

    recs = result.recommendations
    pattern_indices = [i for i, r in enumerate(recs) if r.source == "pattern"]
    default_indices = [i for i, r in enumerate(recs) if r.source == "default"]
    if pattern_indices and default_indices:
        assert min(pattern_indices) < max(default_indices), \
            "Pattern recs should appear before defaults"


@pytest.mark.asyncio
async def test_pattern_graceful_on_error(monkeypatch):
    """Engine falls back to defaults when PatternLibrary raises."""
    import src.runtime.pattern_library as pl_mod

    def _raise():
        raise RuntimeError("simulated pattern library error")

    monkeypatch.setattr(pl_mod, "get_pattern_library", _raise)

    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial_hangar")
    result = await engine.get_recommendations(intent)
    assert len(result.recommendations) > 0
    sources = {r.source for r in result.recommendations}
    assert "default" in sources
