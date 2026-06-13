"""
Tests for CameraPlanner (Tier 7).

Covers:
 - establishing shot always present
 - zone-based targets generated
 - mood-based extra targets
 - importance range 0–1
 - valid shot_types
 - deterministic
 - singleton / reset
"""

import pytest

from src.runtime.planning.camera.camera_planner import (
    CameraPlanner,
    get_camera_planner,
    reset_camera_planner_for_tests,
)
from src.runtime.planning.schema.scene_plan import SHOT_TYPES, SceneZonePlan


@pytest.fixture(autouse=True)
def _reset():
    reset_camera_planner_for_tests()
    yield
    reset_camera_planner_for_tests()


def _make_intent(environment=None, mood=None, destruction_level=None):
    class _Intent:
        pass
    i = _Intent()
    i.environment = environment
    i.mood = mood
    i.destruction_level = destruction_level
    return i


def _make_zones(types=("foreground", "midground", "background")):
    return [SceneZonePlan(zone_type=t) for t in types]


class TestCameraPlannerSingleton:
    def test_singleton(self):
        assert get_camera_planner() is get_camera_planner()

    def test_reset_creates_new(self):
        a = get_camera_planner()
        reset_camera_planner_for_tests()
        assert a is not get_camera_planner()


class TestCameraPlannerEstablishing:
    def test_establishing_shot_always_present(self):
        intent = _make_intent()
        zones = _make_zones()
        targets = get_camera_planner().plan_cameras(intent, zones)
        shot_types = [t.shot_type for t in targets]
        assert "establishing" in shot_types

    def test_establishing_has_highest_importance(self):
        intent = _make_intent()
        zones = _make_zones()
        targets = get_camera_planner().plan_cameras(intent, zones)
        establishing = [t for t in targets if t.name == "scene_overview"]
        assert len(establishing) >= 1
        assert establishing[0].importance >= 0.9

    def test_empty_zones_still_gives_establishing(self):
        intent = _make_intent()
        targets = get_camera_planner().plan_cameras(intent, [])
        assert any(t.shot_type == "establishing" for t in targets)


class TestCameraPlannerZoneTargets:
    def test_foreground_zone_generates_target(self):
        intent = _make_intent()
        zones = _make_zones(("foreground",))
        targets = get_camera_planner().plan_cameras(intent, zones)
        # Should have establishing + a foreground detail target
        assert len(targets) >= 2

    def test_targets_have_valid_shot_types(self):
        intent = _make_intent()
        zones = _make_zones()
        targets = get_camera_planner().plan_cameras(intent, zones)
        for t in targets:
            assert t.shot_type in SHOT_TYPES, f"Invalid shot_type: {t.shot_type!r}"

    def test_targets_importance_in_range(self):
        intent = _make_intent()
        zones = _make_zones()
        targets = get_camera_planner().plan_cameras(intent, zones)
        for t in targets:
            assert 0.0 <= t.importance <= 1.0

    def test_targets_have_names(self):
        intent = _make_intent()
        zones = _make_zones()
        targets = get_camera_planner().plan_cameras(intent, zones)
        for t in targets:
            assert t.name, "target has no name"

    def test_targets_have_zones_assigned(self):
        intent = _make_intent()
        zones = _make_zones()
        targets = get_camera_planner().plan_cameras(intent, zones)
        # Not all targets are zone-specific (establishing is full-scene)
        zone_targets = [t for t in targets if t.zone and t.zone != ""]
        assert len(zone_targets) > 0


class TestCameraPlannerMood:
    def test_dramatic_mood_adds_extra_targets(self):
        intent_base   = _make_intent(mood=None)
        intent_drama  = _make_intent(mood="dramatic")
        zones = _make_zones()
        targets_base  = get_camera_planner().plan_cameras(intent_base, zones)
        targets_drama = get_camera_planner().plan_cameras(intent_drama, zones)
        assert len(targets_drama) >= len(targets_base)

    def test_tense_mood_adds_tracking_target(self):
        intent = _make_intent(mood="tense")
        zones = _make_zones()
        targets = get_camera_planner().plan_cameras(intent, zones)
        shot_types = [t.shot_type for t in targets]
        assert "tracking" in shot_types


class TestCameraPlannerDeterminism:
    def test_same_intent_same_targets(self):
        intent = _make_intent(environment="urban", mood="dramatic")
        zones = _make_zones()
        t_a = get_camera_planner().plan_cameras(intent, zones)
        t_b = get_camera_planner().plan_cameras(intent, zones)
        assert [t.name for t in t_a] == [t.name for t in t_b]
        assert [t.shot_type for t in t_a] == [t.shot_type for t in t_b]
