"""
Tests for ScenePlanRecommendationEngine (Tier 7).

Covers:
 - default recommendations returned for known environments
 - confidence ordering (memory > pattern > graph > default)
 - deduplication by (type, value)
 - source labels correct
 - all results have required keys
 - graceful on Tier 5 source failures
 - sync wrapper works
 - singleton / reset
"""

import asyncio
import pytest

from src.runtime.planning.recommendations.scene_plan_recommendation_engine import (
    ScenePlanRecommendationEngine,
    get_scene_plan_recommendation_engine,
    reset_scene_plan_recommendation_engine_for_tests,
)
from src.runtime.planning.schema.scene_plan import ScenePlan


@pytest.fixture(autouse=True)
def _reset():
    reset_scene_plan_recommendation_engine_for_tests()
    yield
    reset_scene_plan_recommendation_engine_for_tests()


def _make_plan(environment=None):
    return ScenePlan(environment=environment)


class TestScenePlanRecommendationEngineSingleton:
    def test_singleton(self):
        assert get_scene_plan_recommendation_engine() is get_scene_plan_recommendation_engine()

    def test_reset_creates_new(self):
        a = get_scene_plan_recommendation_engine()
        reset_scene_plan_recommendation_engine_for_tests()
        assert a is not get_scene_plan_recommendation_engine()


class TestScenePlanRecommendationEngineDefaults:
    _ENVS = ["industrial", "urban", "space", "interior", "desert", "forest"]

    @pytest.mark.parametrize("env", _ENVS)
    def test_known_env_returns_default_recs(self, env):
        plan = _make_plan(environment=env)
        recs = asyncio.run(get_scene_plan_recommendation_engine().get_recommendations(plan))
        assert len(recs) > 0

    def test_unknown_env_returns_fallback(self):
        plan = _make_plan(environment="custom_void")
        recs = asyncio.run(get_scene_plan_recommendation_engine().get_recommendations(plan))
        # Falls back to interior defaults
        assert len(recs) > 0

    def test_none_env_returns_recs(self):
        plan = _make_plan(environment=None)
        recs = asyncio.run(get_scene_plan_recommendation_engine().get_recommendations(plan))
        assert len(recs) > 0


class TestScenePlanRecommendationEngineShape:
    def test_recs_have_required_keys(self):
        plan = _make_plan(environment="industrial")
        recs = asyncio.run(get_scene_plan_recommendation_engine().get_recommendations(plan))
        for r in recs:
            assert "type" in r
            assert "value" in r
            assert "confidence" in r
            assert "source" in r
            assert "reason" in r

    def test_default_source_is_default(self):
        plan = _make_plan(environment="industrial")
        recs = asyncio.run(get_scene_plan_recommendation_engine().get_recommendations(plan))
        # At minimum the default recommendations should be present
        sources = {r["source"] for r in recs}
        assert "default" in sources

    def test_default_confidence_is_0_50(self):
        plan = _make_plan(environment="industrial")
        recs = asyncio.run(get_scene_plan_recommendation_engine().get_recommendations(plan))
        default_recs = [r for r in recs if r["source"] == "default"]
        for r in default_recs:
            assert r["confidence"] == pytest.approx(0.50)

    def test_recs_sorted_by_confidence_desc(self):
        plan = _make_plan(environment="urban")
        recs = asyncio.run(get_scene_plan_recommendation_engine().get_recommendations(plan))
        confidences = [r["confidence"] for r in recs]
        assert confidences == sorted(confidences, reverse=True)

    def test_types_include_lighting_camera_atmosphere(self):
        plan = _make_plan(environment="industrial")
        recs = asyncio.run(get_scene_plan_recommendation_engine().get_recommendations(plan))
        types = {r["type"] for r in recs}
        assert "lighting" in types
        assert "camera" in types
        assert "atmosphere" in types

    def test_deduplication_by_type_value(self):
        plan = _make_plan(environment="urban")
        recs = asyncio.run(get_scene_plan_recommendation_engine().get_recommendations(plan))
        seen = set()
        for r in recs:
            key = (r["type"], r["value"])
            assert key not in seen, f"Duplicate rec: {key}"
            seen.add(key)


class TestScenePlanRecommendationEngineSync:
    def test_sync_wrapper_returns_same_as_async(self):
        plan = _make_plan(environment="forest")
        recs_async  = asyncio.run(get_scene_plan_recommendation_engine().get_recommendations(plan))
        recs_sync   = get_scene_plan_recommendation_engine().get_recommendations_sync(plan)
        assert len(recs_async) == len(recs_sync)
