"""Tests for the §54 Reality Intelligence shared scene model (Tier 15.0+)."""

import pytest

from src.runtime.reality.reality_scene_model import (
    FLOAT_TOLERANCE,
    SceneAsset,
    infer_asset_type,
    parse_scene,
    raycast_down,
    distance_to_nearest_wall,
    is_against_wall,
    is_wall_mounted,
    facing_ry_towards,
)


class TestInferAssetType:
    @pytest.mark.parametrize("name,expected", [
        ("Saloon Table", "table"),
        ("Wooden Chair", "chair"),
        ("Whiskey Bottle", "bottle"),
        ("Tin Cup", "cup"),
        ("Oil Lantern", "lantern"),
        ("Stone Fireplace", "fireplace"),
        ("Old Wooden Beam", "beam"),
        ("Stone Column", "column"),
        ("Swing Door", "door"),
        ("Wanted Poster", "poster"),
        ("Oak Barrel", "barrel"),
        ("Bar Counter", "bar"),
        ("Wall Segment North", "wall"),
    ])
    def test_known_types(self, name, expected):
        assert infer_asset_type(name) == expected

    def test_unknown_returns_empty(self):
        assert infer_asset_type("xgihfgbqx") == ""
        assert infer_asset_type("") == ""


class TestParseScene:
    def test_room_from_environment(self):
        snap = parse_scene({"environment": "western_room", "transforms": []})
        assert snap.room_width == 10.0
        assert snap.room_depth == 12.0
        assert snap.room_area == 120.0

    def test_explicit_room_overrides_environment(self):
        snap = parse_scene({
            "environment": "western_room",
            "room_width": 20.0, "room_depth": 30.0,
            "transforms": [],
        })
        assert snap.room_width == 20.0
        assert snap.room_depth == 30.0

    def test_transforms_normalized(self, western_room_scene):
        snap = parse_scene(western_room_scene)
        assert len(snap.assets) == 19
        table = snap.find("table_01")
        assert table.asset_type == "table"
        assert table.top_y == pytest.approx(0.75)

    def test_default_half_extents_applied(self):
        snap = parse_scene({"transforms": [
            {"asset_id": "c1", "asset_name": "Wooden Chair", "tx": 0, "ty": 0.45, "tz": 0},
        ]})
        chair = snap.assets[0]
        assert chair.half_y > 0.0

    def test_never_raises_on_garbage(self):
        assert parse_scene(None).assets == []
        assert parse_scene({"transforms": "nonsense"}).assets == []


class TestGeometryHelpers:
    def test_raycast_down_finds_table(self):
        snap = parse_scene({"transforms": [
            {"asset_id": "t", "asset_name": "Table", "tx": 0, "ty": 0.375, "tz": 0,
             "bbox_half_x": 1.1, "bbox_half_y": 0.375, "bbox_half_z": 0.65},
            {"asset_id": "b", "asset_name": "Bottle", "tx": 0.3, "ty": 0.90, "tz": 0.2,
             "bbox_half_x": 0.05, "bbox_half_y": 0.15, "bbox_half_z": 0.05},
        ]})
        support = raycast_down(snap, snap.find("b"))
        assert support is not None
        assert support.asset_id == "t"

    def test_raycast_down_no_support(self):
        snap = parse_scene({"transforms": [
            {"asset_id": "b", "asset_name": "Bottle", "tx": 3.0, "ty": 1.5, "tz": 3.0,
             "bbox_half_x": 0.05, "bbox_half_y": 0.15, "bbox_half_z": 0.05},
        ]})
        assert raycast_down(snap, snap.assets[0]) is None

    def test_wall_distance_and_mounting(self):
        snap = parse_scene({"environment": "western_room", "transforms": []})
        assert distance_to_nearest_wall(snap, 0.0, 0.0) == 5.0
        poster = SceneAsset(asset_id="p", asset_name="Poster", asset_type="poster",
                            tx=-4.97, ty=1.6, tz=2.0,
                            half_x=0.02, half_y=0.5, half_z=0.4)
        assert is_wall_mounted(snap, poster)
        assert is_against_wall(snap, poster)

    def test_facing_ry_convention(self):
        # §47.4 convention: forward = (sin ry, 0, cos ry)
        assert facing_ry_towards(0.0, 1.55, 0.0, 0.0) == pytest.approx(180.0)
        assert facing_ry_towards(0.0, -1.55, 0.0, 0.0) == pytest.approx(0.0)
        assert facing_ry_towards(1.85, 0.0, 0.0, 0.0) == pytest.approx(270.0)
        assert facing_ry_towards(-1.85, 0.0, 0.0, 0.0) == pytest.approx(90.0)

    def test_float_tolerance_is_spec_value(self):
        assert FLOAT_TOLERANCE == 0.10
