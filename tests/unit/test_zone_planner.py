"""
Tests for ZonePlanner (Tier 7).

Covers:
 - plan_zones returns 3 zones for all built-in environments
 - zone_types include foreground/midground/background for standard envs
 - fallback template used for unknown environments
 - mood modifies population level
 - destruction adds extra asset categories
 - each zone has non-empty asset_categories
 - placement hints are generated
 - deterministic: same intent → same zones
 - singleton / reset
"""

import pytest

from src.runtime.planning.planners.zone_planner import (
    ZonePlanner,
    get_zone_planner,
    reset_zone_planner_for_tests,
)
from src.runtime.planning.schema.scene_plan import SceneZonePlan


@pytest.fixture(autouse=True)
def _reset():
    reset_zone_planner_for_tests()
    yield
    reset_zone_planner_for_tests()


def _make_intent(environment=None, mood=None, destruction_level=None, **kwargs):
    class _Intent:
        pass
    i = _Intent()
    i.environment = environment
    i.mood = mood
    i.destruction_level = destruction_level
    for k, v in kwargs.items():
        setattr(i, k, v)
    return i


class TestZonePlannerSingleton:
    def test_singleton(self):
        a = get_zone_planner()
        b = get_zone_planner()
        assert a is b

    def test_reset_creates_new(self):
        a = get_zone_planner()
        reset_zone_planner_for_tests()
        b = get_zone_planner()
        assert a is not b


class TestZonePlannerEnvironments:
    _ENVS = ["urban", "industrial", "desert", "forest", "ocean", "mountain",
             "arctic", "space", "underground", "interior", "abstract"]

    @pytest.mark.parametrize("env", _ENVS)
    def test_known_env_returns_three_zones(self, env):
        intent = _make_intent(environment=env)
        zones = get_zone_planner().plan_zones(intent)
        assert len(zones) == 3

    @pytest.mark.parametrize("env", _ENVS)
    def test_zone_types_canonical(self, env):
        intent = _make_intent(environment=env)
        zones = get_zone_planner().plan_zones(intent)
        zone_types = [z.zone_type for z in zones]
        assert "foreground" in zone_types
        assert "midground" in zone_types
        assert "background" in zone_types

    def test_unknown_env_returns_default_template(self):
        intent = _make_intent(environment="custom_alien_world")
        zones = get_zone_planner().plan_zones(intent)
        assert len(zones) == 3
        zone_types = [z.zone_type for z in zones]
        assert "foreground" in zone_types

    def test_none_env_returns_default_template(self):
        intent = _make_intent(environment=None)
        zones = get_zone_planner().plan_zones(intent)
        assert len(zones) == 3


class TestZonePlannerZoneContent:
    def test_zones_have_asset_categories(self):
        intent = _make_intent(environment="urban")
        zones = get_zone_planner().plan_zones(intent)
        for z in zones:
            assert len(z.asset_categories) > 0, f"{z.zone_type} has no asset categories"

    def test_zones_have_descriptions(self):
        intent = _make_intent(environment="industrial")
        zones = get_zone_planner().plan_zones(intent)
        for z in zones:
            assert z.description, f"{z.zone_type} has no description"

    def test_foreground_has_highest_priority(self):
        intent = _make_intent(environment="urban")
        zones = get_zone_planner().plan_zones(intent)
        fg = next(z for z in zones if z.zone_type == "foreground")
        bg = next(z for z in zones if z.zone_type == "background")
        assert fg.priority > bg.priority

    def test_zones_have_placement_hints(self):
        intent = _make_intent(environment="urban")
        zones = get_zone_planner().plan_zones(intent)
        total_hints = sum(len(z.placement_hints) for z in zones)
        assert total_hints > 0


class TestZonePlannerMoodAndDestruction:
    def test_peaceful_mood_sets_sparse(self):
        intent = _make_intent(environment="forest", mood="peaceful")
        zones = get_zone_planner().plan_zones(intent)
        # peaceful mood → sparse population
        populations = {z.population for z in zones}
        assert "sparse" in populations

    def test_chaotic_mood_sets_dense(self):
        intent = _make_intent(environment="urban", mood="chaotic")
        zones = get_zone_planner().plan_zones(intent)
        populations = {z.population for z in zones}
        assert "dense" in populations

    def test_heavy_destruction_adds_extra_categories(self):
        intent = _make_intent(environment="urban", destruction_level="heavy")
        zones = get_zone_planner().plan_zones(intent)
        all_cats = [cat for z in zones for cat in z.asset_categories]
        assert "ruin" in all_cats or "collapsed_section" in all_cats

    def test_catastrophic_destruction(self):
        intent = _make_intent(environment="urban", destruction_level="catastrophic")
        zones = get_zone_planner().plan_zones(intent)
        all_cats = [cat for z in zones for cat in z.asset_categories]
        assert "catastrophic_ruin" in all_cats or "debris_field" in all_cats

    def test_none_destruction_no_extra_categories(self):
        intent = _make_intent(environment="desert", destruction_level="none")
        zones_base = get_zone_planner().plan_zones(_make_intent(environment="desert"))
        zones_none = get_zone_planner().plan_zones(intent)
        # No extra categories added for "none"
        fg_base = next(z for z in zones_base if z.zone_type == "foreground")
        fg_none = next(z for z in zones_none if z.zone_type == "foreground")
        assert set(fg_base.asset_categories) == set(fg_none.asset_categories)


class TestZonePlannerDeterminism:
    def test_same_intent_produces_same_zones(self):
        intent = _make_intent(environment="urban", mood="dramatic")
        zones_a = get_zone_planner().plan_zones(intent)
        zones_b = get_zone_planner().plan_zones(intent)
        assert [z.zone_type for z in zones_a] == [z.zone_type for z in zones_b]
        assert [z.asset_categories for z in zones_a] == [z.asset_categories for z in zones_b]
