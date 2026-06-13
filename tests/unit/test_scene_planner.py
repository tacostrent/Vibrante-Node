"""
Tests for ScenePlanner (Tier 7) — integration of the full planning pipeline.

Covers:
 - plan() returns PlanningResult with ok=True for valid intent
 - pipeline_stages recorded correctly
 - ScenePlan has zones, queries, cameras, composition_rules
 - planning_notes populated
 - estimated_complexity and estimated_asset_count set
 - plan_id and scene_intent_id populated
 - handles None environment gracefully (never raises)
 - singleton / reset
"""

import pytest

from src.runtime.planning.planners.scene_planner import (
    ScenePlanner,
    get_scene_planner,
    reset_scene_planner_for_tests,
)
from src.runtime.planning.planners.zone_planner import reset_zone_planner_for_tests
from src.runtime.planning.composition.composition_planner import reset_composition_planner_for_tests
from src.runtime.planning.camera.camera_planner import reset_camera_planner_for_tests
from src.runtime.planning.planners.asset_query_generator import reset_asset_query_generator_for_tests


@pytest.fixture(autouse=True)
def _reset():
    reset_scene_planner_for_tests()
    reset_zone_planner_for_tests()
    reset_composition_planner_for_tests()
    reset_camera_planner_for_tests()
    reset_asset_query_generator_for_tests()
    yield
    reset_scene_planner_for_tests()
    reset_zone_planner_for_tests()
    reset_composition_planner_for_tests()
    reset_camera_planner_for_tests()
    reset_asset_query_generator_for_tests()


def _make_intent(environment="urban", style="cinematic", mood="dramatic",
                 destruction_level=None, intent_id="test-intent-001"):
    class _Intent:
        pass
    i = _Intent()
    i.environment = environment
    i.style = style
    i.mood = mood
    i.destruction_level = destruction_level
    i.intent_id = intent_id
    return i


class TestScenePlannerSingleton:
    def test_singleton(self):
        assert get_scene_planner() is get_scene_planner()

    def test_reset_creates_new(self):
        a = get_scene_planner()
        reset_scene_planner_for_tests()
        assert a is not get_scene_planner()


class TestScenePlannerResult:
    def test_ok_true_for_valid_intent(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert result.ok is True

    def test_plan_is_not_none(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert result.plan is not None

    def test_pipeline_stages_include_zones(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert "zones" in result.pipeline_stages

    def test_pipeline_stages_include_composition(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert "composition" in result.pipeline_stages

    def test_pipeline_stages_include_cameras(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert "cameras" in result.pipeline_stages

    def test_pipeline_stages_include_asset_queries(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert "asset_queries" in result.pipeline_stages

    def test_planning_time_positive(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert result.planning_time >= 0.0


class TestScenePlannerPlanContent:
    def test_plan_has_zones(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert len(result.plan.zones) > 0

    def test_plan_has_asset_queries(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert len(result.plan.asset_queries) > 0

    def test_plan_has_camera_targets(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert len(result.plan.camera_targets) > 0

    def test_plan_has_composition_rules(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert len(result.plan.composition_rules) > 0

    def test_plan_inherits_environment(self):
        intent = _make_intent(environment="industrial")
        result = get_scene_planner().plan(intent)
        assert result.plan.environment == "industrial"

    def test_plan_inherits_style(self):
        intent = _make_intent(style="noir")
        result = get_scene_planner().plan(intent)
        assert result.plan.style == "noir"

    def test_plan_inherits_mood(self):
        intent = _make_intent(mood="tense")
        result = get_scene_planner().plan(intent)
        assert result.plan.mood == "tense"

    def test_plan_id_set(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert result.plan.plan_id

    def test_scene_intent_id_set(self):
        intent = _make_intent(intent_id="test-001")
        result = get_scene_planner().plan(intent)
        assert result.plan.scene_intent_id == "test-001"

    def test_planning_notes_populated(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert len(result.plan.planning_notes) > 0

    def test_estimated_complexity_set(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert result.plan.estimated_complexity in ("simple", "moderate", "complex", "epic")

    def test_estimated_asset_count_positive(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert result.plan.estimated_asset_count > 0

    def test_placement_hints_collected(self):
        intent = _make_intent()
        result = get_scene_planner().plan(intent)
        assert len(result.plan.placement_hints) > 0


class TestScenePlannerEdgeCases:
    def test_none_environment_does_not_raise(self):
        intent = _make_intent(environment=None)
        result = get_scene_planner().plan(intent)
        assert result.ok is True

    def test_all_none_fields_does_not_raise(self):
        class _Minimal:
            environment = None
            style = None
            mood = None
            destruction_level = None
            intent_id = ""
        result = get_scene_planner().plan(_Minimal())
        assert result.ok is True

    def test_never_raises(self):
        for _ in range(3):
            result = get_scene_planner().plan(_make_intent())
            assert result.ok is True
            assert result.errors == []


class TestScenePlannerDeterminism:
    def test_same_intent_same_plan(self):
        intent = _make_intent(environment="forest", style="fantasy", mood="peaceful")
        r_a = get_scene_planner().plan(intent)
        r_b = get_scene_planner().plan(intent)
        assert r_a.plan.environment == r_b.plan.environment
        assert len(r_a.plan.zones) == len(r_b.plan.zones)
        assert len(r_a.plan.asset_queries) == len(r_b.plan.asset_queries)
