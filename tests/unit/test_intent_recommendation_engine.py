"""
Tests for src.runtime.semantic.recommendations.intent_recommendation_engine
No bridge, no LLM, no live databases. Pure unit tests.
"""
import pytest
import pytest_asyncio
from src.runtime.semantic.recommendations.intent_recommendation_engine import (
    IntentRecommendation,
    RecommendationResult,
    IntentRecommendationEngine,
    get_intent_recommendation_engine,
    reset_intent_recommendation_engine_for_tests,
    _get_default_recommendations,
)
from src.runtime.semantic.schema.scene_intent_schema import SceneIntent
from src.runtime.production_memory import ProductionMemory, reset_production_memory_for_tests
from src.runtime.pattern_library import reset_pattern_library_for_tests
from src.runtime.asset_knowledge_graph import reset_asset_knowledge_graph_for_tests
from src.runtime.storage.memory_backend import InMemoryBackend


@pytest.fixture(autouse=True)
def reset():
    reset_intent_recommendation_engine_for_tests()
    reset_production_memory_for_tests()
    reset_pattern_library_for_tests()
    reset_asset_knowledge_graph_for_tests()
    yield
    reset_intent_recommendation_engine_for_tests()
    reset_production_memory_for_tests()
    reset_pattern_library_for_tests()
    reset_asset_knowledge_graph_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_intent_recommendation_engine()
    b = get_intent_recommendation_engine()
    assert a is b


def test_reset_creates_new():
    a = get_intent_recommendation_engine()
    reset_intent_recommendation_engine_for_tests()
    b = get_intent_recommendation_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# IntentRecommendation model
# ---------------------------------------------------------------------------

def test_intent_recommendation_defaults():
    r = IntentRecommendation()
    assert r.recommendation_type == ""
    assert r.value == ""
    assert r.confidence == 0.0
    assert r.source == ""
    assert r.reason == ""
    assert r.metadata == {}


def test_intent_recommendation_to_dict():
    r = IntentRecommendation(
        recommendation_type="lighting",
        value="cinematic_industrial",
        confidence=0.95,
        source="memory",
        reason="Proven in industrial scenes",
        metadata={"scene_score": 0.91},
    )
    d = r.to_dict()
    assert d["recommendation_type"] == "lighting"
    assert d["value"] == "cinematic_industrial"
    assert d["confidence"] == 0.95
    assert d["source"] == "memory"
    assert d["reason"] == "Proven in industrial scenes"
    assert d["metadata"]["scene_score"] == 0.91


def test_intent_recommendation_from_dict_round_trip():
    r = IntentRecommendation(
        recommendation_type="camera",
        value="cinematic_push_in",
        confidence=0.80,
        source="pattern",
        reason="High-ranked pattern",
    )
    r2 = IntentRecommendation.from_dict(r.to_dict())
    assert r2.recommendation_type == r.recommendation_type
    assert r2.value == r.value
    assert r2.confidence == r.confidence
    assert r2.source == r.source


def test_intent_recommendation_from_dict_missing_fields():
    r = IntentRecommendation.from_dict({})
    assert r.recommendation_type == ""
    assert r.confidence == 0.0


# ---------------------------------------------------------------------------
# RecommendationResult model
# ---------------------------------------------------------------------------

def test_recommendation_result_defaults():
    result = RecommendationResult()
    assert result.recommendations == []
    assert result.source_counts == {}
    assert result.environment is None
    assert result.top_recommendation is None


def test_recommendation_result_top_recommendation():
    recs = [
        IntentRecommendation(recommendation_type="lighting", value="cinematic_industrial", confidence=0.95),
        IntentRecommendation(recommendation_type="camera", value="push_in", confidence=0.80),
    ]
    result = RecommendationResult(recommendations=recs)
    top = result.top_recommendation
    assert top is not None
    assert top.value == "cinematic_industrial"


def test_recommendation_result_to_dict_from_dict():
    recs = [IntentRecommendation(recommendation_type="lighting", value="noir", confidence=0.75, source="default")]
    result = RecommendationResult(recommendations=recs, source_counts={"default": 1}, environment="industrial")
    d = result.to_dict()
    r2 = RecommendationResult.from_dict(d)
    assert len(r2.recommendations) == 1
    assert r2.recommendations[0].value == "noir"
    assert r2.environment == "industrial"
    assert r2.source_counts == {"default": 1}


# ---------------------------------------------------------------------------
# Default recommendations
# ---------------------------------------------------------------------------

def test_default_recs_industrial():
    recs = _get_default_recommendations("industrial")
    types = {r.recommendation_type for r in recs}
    assert "lighting" in types
    assert "camera" in types
    assert "atmosphere" in types
    assert all(r.source == "default" for r in recs)
    assert all(r.confidence == 0.50 for r in recs)


def test_default_recs_unknown_env():
    recs = _get_default_recommendations("completely_unknown_env_xyz")
    assert len(recs) > 0
    assert all(r.confidence == 0.50 for r in recs)


def test_default_recs_none_env():
    recs = _get_default_recommendations(None)
    assert len(recs) > 0


def test_default_recs_space_env():
    recs = _get_default_recommendations("space")
    values = {r.value for r in recs}
    assert "orbital_reveal" in values


# ---------------------------------------------------------------------------
# Async get_recommendations — empty state (falls through to defaults)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_recommendations_returns_result():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial", style="cinematic")
    result = await engine.get_recommendations(intent)
    assert isinstance(result, RecommendationResult)
    assert isinstance(result.recommendations, list)
    assert result.environment == "industrial"


@pytest.mark.asyncio
async def test_get_recommendations_sorted_by_confidence_desc():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent)
    confidences = [r.confidence for r in result.recommendations]
    assert confidences == sorted(confidences, reverse=True)


@pytest.mark.asyncio
async def test_get_recommendations_no_duplicates():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent)
    pairs = [(r.recommendation_type, r.value) for r in result.recommendations]
    assert len(pairs) == len(set(pairs)), "Duplicate (type, value) pairs found"


@pytest.mark.asyncio
async def test_get_recommendations_no_empty_values():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="urban")
    result = await engine.get_recommendations(intent)
    for r in result.recommendations:
        assert r.value, f"Empty value in recommendation: {r.to_dict()}"


@pytest.mark.asyncio
async def test_get_recommendations_source_counts_populated():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent)
    total_from_counts = sum(result.source_counts.values())
    assert total_from_counts == len(result.recommendations)


@pytest.mark.asyncio
async def test_get_recommendations_defaults_always_present():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent)
    sources = {r.source for r in result.recommendations}
    assert "default" in sources


@pytest.mark.asyncio
async def test_get_recommendations_max_per_source_respected():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent, max_per_source=2)
    assert isinstance(result, RecommendationResult)
    for source in ("memory", "pattern", "graph"):
        count = sum(1 for r in result.recommendations if r.source == source)
        assert count <= 2, f"Source {source!r} exceeded max_per_source=2: got {count}"


# ---------------------------------------------------------------------------
# Memory integration: inject a ProductionMemory with known data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_recommendations_have_high_confidence(monkeypatch):
    """When ProductionMemory has matching scenes, recs have confidence 0.95."""
    mem = ProductionMemory(backend=InMemoryBackend())
    mem.record_scene({
        "scene_type":      "industrial",
        "lighting_style":  "cinematic_industrial",
        "camera_style":    "cinematic_push_in",
        "atmosphere_type": "industrial_fog",
        "score":           0.92,
        "status":          "success",
    })

    import src.runtime.production_memory as pm_mod
    monkeypatch.setattr(pm_mod, "_INSTANCE", mem)

    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent)

    memory_recs = [r for r in result.recommendations if r.source == "memory"]
    assert len(memory_recs) > 0, "Expected at least one memory recommendation"
    for r in memory_recs:
        assert r.confidence == 0.95


@pytest.mark.asyncio
async def test_memory_graceful_on_error(monkeypatch):
    """Engine returns defaults even if ProductionMemory raises."""
    import src.runtime.production_memory as pm_mod

    def _raise():
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(pm_mod, "get_production_memory", _raise)

    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent)
    assert len(result.recommendations) > 0
    sources = {r.source for r in result.recommendations}
    assert "default" in sources


# ---------------------------------------------------------------------------
# Sync wrapper
# ---------------------------------------------------------------------------

def test_get_recommendations_sync_returns_result():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial", style="cinematic")
    result = engine.get_recommendations_sync(intent)
    assert isinstance(result, RecommendationResult)
    assert len(result.recommendations) > 0
