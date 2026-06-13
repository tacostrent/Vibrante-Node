"""
Tests for Tier 6 semantic layer integration with Tier 5 ProductionMemory.
No bridge, no LLM, no live databases. Pure unit tests.
"""
import pytest
import pytest_asyncio
from src.runtime.semantic.recommendations.intent_recommendation_engine import (
    IntentRecommendationEngine,
    get_intent_recommendation_engine,
    reset_intent_recommendation_engine_for_tests,
)
from src.runtime.semantic.schema.scene_intent_schema import SceneIntent
from src.runtime.production_memory import ProductionMemory, reset_production_memory_for_tests
from src.runtime.storage.memory_backend import InMemoryBackend


@pytest.fixture(autouse=True)
def reset():
    reset_intent_recommendation_engine_for_tests()
    reset_production_memory_for_tests()
    yield
    reset_intent_recommendation_engine_for_tests()
    reset_production_memory_for_tests()


@pytest.fixture
def mem_with_data():
    """A ProductionMemory (in-memory) pre-seeded with industrial scenes."""
    mem = ProductionMemory(backend=InMemoryBackend())
    mem.record_scene({
        "scene_type":      "industrial",
        "lighting_style":  "cinematic_industrial",
        "camera_style":    "cinematic_push_in",
        "atmosphere_type": "industrial_fog",
        "score":           0.91,
        "status":          "success",
    })
    mem.record_scene({
        "scene_type":      "industrial",
        "lighting_style":  "practical",
        "camera_style":    "orbital_reveal",
        "atmosphere_type": "dusty_hangar",
        "score":           0.78,
        "status":          "success",
    })
    return mem


@pytest.mark.asyncio
async def test_memory_recs_returned_when_available(mem_with_data, monkeypatch):
    import src.runtime.production_memory as pm_mod
    monkeypatch.setattr(pm_mod, "_INSTANCE", mem_with_data)

    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent)

    memory_recs = [r for r in result.recommendations if r.source == "memory"]
    assert len(memory_recs) > 0


@pytest.mark.asyncio
async def test_memory_recs_confidence_is_0_95(mem_with_data, monkeypatch):
    import src.runtime.production_memory as pm_mod
    monkeypatch.setattr(pm_mod, "_INSTANCE", mem_with_data)

    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent)

    for r in result.recommendations:
        if r.source == "memory":
            assert r.confidence == 0.95


@pytest.mark.asyncio
async def test_memory_recs_have_reason(mem_with_data, monkeypatch):
    import src.runtime.production_memory as pm_mod
    monkeypatch.setattr(pm_mod, "_INSTANCE", mem_with_data)

    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent)

    for r in result.recommendations:
        if r.source == "memory":
            assert len(r.reason) > 0, "Memory recommendation missing reason"


@pytest.mark.asyncio
async def test_memory_recs_ranked_above_defaults(mem_with_data, monkeypatch):
    import src.runtime.production_memory as pm_mod
    monkeypatch.setattr(pm_mod, "_INSTANCE", mem_with_data)

    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent)

    recs = result.recommendations
    assert len(recs) >= 2
    memory_indices = [i for i, r in enumerate(recs) if r.source == "memory"]
    default_indices = [i for i, r in enumerate(recs) if r.source == "default"]
    if memory_indices and default_indices:
        assert min(memory_indices) < max(default_indices), \
            "Memory recommendations should appear before defaults"


@pytest.mark.asyncio
async def test_empty_memory_falls_through_to_defaults():
    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent)
    sources = {r.source for r in result.recommendations}
    assert "default" in sources
    assert "memory" not in sources


@pytest.mark.asyncio
async def test_memory_lookup_only_returns_success_scenes(monkeypatch):
    """Failed scenes should not appear in recommendations."""
    mem = ProductionMemory(backend=InMemoryBackend())
    mem.record_scene({
        "scene_type":      "industrial",
        "lighting_style":  "broken_lights",
        "status":          "failure",
        "score":           0.1,
    })
    import src.runtime.production_memory as pm_mod
    monkeypatch.setattr(pm_mod, "_INSTANCE", mem)

    engine = IntentRecommendationEngine()
    intent = SceneIntent(environment="industrial")
    result = await engine.get_recommendations(intent)

    # broken_lights should NOT appear since it came from a failure scene
    values = {r.value for r in result.recommendations}
    assert "broken_lights" not in values
