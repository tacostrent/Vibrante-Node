"""Tests for the §54 Support Rule Engine (Tier 15.0+)."""

import pytest

from src.runtime.reality.support_rule_engine import (
    SUPPORT_REQUIREMENTS,
    get_support_rule_engine,
    reset_support_rule_engine_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_support_rule_engine_for_tests()
    yield
    reset_support_rule_engine_for_tests()


def _scene(transforms, env="western_room", **extra):
    d = {"environment": env, "transforms": transforms}
    d.update(extra)
    return d


class TestSupportTable:
    def test_spec_table(self):
        assert SUPPORT_REQUIREMENTS["bottle"] == frozenset({"table", "shelf", "bar"})
        assert SUPPORT_REQUIREMENTS["cup"] == frozenset({"table", "shelf"})
        assert SUPPORT_REQUIREMENTS["plate"] == frozenset({"table"})
        assert SUPPORT_REQUIREMENTS["lantern"] == frozenset({"table", "wall", "ceiling"})
        assert SUPPORT_REQUIREMENTS["chair"] == frozenset({"table", "desk", "fireplace", "bar"})
        assert SUPPORT_REQUIREMENTS["stool"] == frozenset({"bar"})
        assert SUPPORT_REQUIREMENTS["fireplace"] == frozenset({"wall"})
        assert SUPPORT_REQUIREMENTS["window"] == frozenset({"wall_opening"})
        assert SUPPORT_REQUIREMENTS["door"] == frozenset({"wall_opening"})


class TestSupportChecks:
    def test_bottle_on_table_ok(self):
        result = get_support_rule_engine().check_scene(_scene([
            {"asset_id": "t", "asset_name": "Table", "tx": 0, "ty": 0.375, "tz": 0,
             "bbox_half_x": 1.1, "bbox_half_y": 0.375, "bbox_half_z": 0.65},
            {"asset_id": "b", "asset_name": "Whiskey Bottle", "tx": 0.3, "ty": 0.90,
             "tz": 0.2, "bbox_half_x": 0.05, "bbox_half_y": 0.15, "bbox_half_z": 0.05},
        ]))
        assert result.ok
        bottle_check = [c for c in result.checks if c.asset_id == "b"][0]
        assert bottle_check.satisfied_by == "t"
        assert bottle_check.support_kind == "table"

    def test_bottle_without_any_support_rejected(self):
        result = get_support_rule_engine().check_scene(_scene([
            {"asset_id": "b", "asset_name": "Whiskey Bottle", "tx": 0, "ty": 0.15,
             "tz": 0, "bbox_half_x": 0.05, "bbox_half_y": 0.15, "bbox_half_z": 0.05},
        ]))
        assert not result.ok
        assert result.violations[0].asset_id == "b"
        assert "reject placement" in result.violations[0].detail

    def test_bottle_on_floor_with_table_elsewhere_rejected(self):
        result = get_support_rule_engine().check_scene(_scene([
            {"asset_id": "t", "asset_name": "Table", "tx": 3.0, "ty": 0.375, "tz": 3.0,
             "bbox_half_x": 1.1, "bbox_half_y": 0.375, "bbox_half_z": 0.65},
            {"asset_id": "b", "asset_name": "Whiskey Bottle", "tx": 0, "ty": 0.15,
             "tz": 0, "bbox_half_x": 0.05, "bbox_half_y": 0.15, "bbox_half_z": 0.05},
        ]))
        assert not result.ok

    def test_chair_near_table_ok(self):
        result = get_support_rule_engine().check_scene(_scene([
            {"asset_id": "t", "asset_name": "Table", "tx": 0, "ty": 0.375, "tz": 0,
             "bbox_half_x": 1.1, "bbox_half_y": 0.375, "bbox_half_z": 0.65},
            {"asset_id": "c", "asset_name": "Wooden Chair", "tx": 0, "ty": 0.45,
             "tz": 1.55, "bbox_half_x": 0.25, "bbox_half_y": 0.45, "bbox_half_z": 0.25},
        ]))
        assert result.ok

    def test_isolated_chair_rejected(self):
        result = get_support_rule_engine().check_scene(_scene([
            {"asset_id": "c", "asset_name": "Wooden Chair", "tx": 0, "ty": 0.45,
             "tz": 0, "bbox_half_x": 0.25, "bbox_half_y": 0.45, "bbox_half_z": 0.25},
        ]))
        assert not result.ok

    def test_stool_requires_bar(self):
        engine = get_support_rule_engine()
        no_bar = engine.check_scene(_scene([
            {"asset_id": "s", "asset_name": "Bar Stool", "tx": 0, "ty": 0.35, "tz": 0,
             "bbox_half_x": 0.2, "bbox_half_y": 0.35, "bbox_half_z": 0.2},
        ]))
        assert not no_bar.ok
        with_bar = engine.check_scene(_scene([
            {"asset_id": "bar", "asset_name": "Bar Counter", "tx": 0, "ty": 0.525,
             "tz": 1.0, "bbox_half_x": 1.5, "bbox_half_y": 0.525, "bbox_half_z": 0.4},
            {"asset_id": "s", "asset_name": "Bar Stool", "tx": 0, "ty": 0.35, "tz": 0,
             "bbox_half_x": 0.2, "bbox_half_y": 0.35, "bbox_half_z": 0.2},
        ]))
        assert with_bar.ok

    def test_fireplace_requires_wall(self):
        engine = get_support_rule_engine()
        # Free-standing fireplace in the room centre (room is 10×12)
        center = engine.check_scene(_scene([
            {"asset_id": "f", "asset_name": "Stone Fireplace", "tx": 0, "ty": 1.0,
             "tz": 0, "bbox_half_x": 0.9, "bbox_half_y": 1.0, "bbox_half_z": 0.35},
        ]))
        assert not center.ok
        on_wall = engine.check_scene(_scene([
            {"asset_id": "f", "asset_name": "Stone Fireplace", "tx": 0, "ty": 1.0,
             "tz": -5.65, "bbox_half_x": 0.9, "bbox_half_y": 1.0, "bbox_half_z": 0.35},
        ]))
        assert on_wall.ok

    def test_door_requires_wall_opening(self):
        engine = get_support_rule_engine()
        fake = engine.check_scene(_scene([
            {"asset_id": "d", "asset_name": "Swing Door", "tx": 0, "ty": 1.05,
             "tz": 0, "bbox_half_x": 0.5, "bbox_half_y": 1.05, "bbox_half_z": 0.06},
        ]))
        assert not fake.ok
        real = engine.check_scene(_scene([
            {"asset_id": "d", "asset_name": "Swing Door", "tx": 0, "ty": 1.05,
             "tz": 5.97, "bbox_half_x": 0.5, "bbox_half_y": 1.05, "bbox_half_z": 0.06},
        ]))
        assert real.ok

    def test_lantern_on_table_or_wall(self):
        engine = get_support_rule_engine()
        on_table = engine.check_scene(_scene([
            {"asset_id": "t", "asset_name": "Table", "tx": 0, "ty": 0.375, "tz": 0,
             "bbox_half_x": 1.1, "bbox_half_y": 0.375, "bbox_half_z": 0.65},
            {"asset_id": "l", "asset_name": "Oil Lantern", "tx": 0.6, "ty": 0.90,
             "tz": -0.2, "bbox_half_x": 0.1, "bbox_half_y": 0.15, "bbox_half_z": 0.1},
        ]))
        assert on_table.ok
        floating = engine.check_scene(_scene([
            {"asset_id": "l", "asset_name": "Oil Lantern", "tx": 0, "ty": 1.5,
             "tz": 0, "bbox_half_x": 0.1, "bbox_half_y": 0.15, "bbox_half_z": 0.1},
        ]))
        assert not floating.ok

    def test_canonical_scene_passes(self, western_room_scene):
        result = get_support_rule_engine().check_scene(western_room_scene)
        assert result.ok, [v.detail for v in result.violations]

    def test_never_raises(self):
        result = get_support_rule_engine().check_scene(None)
        assert result.checked == 0
