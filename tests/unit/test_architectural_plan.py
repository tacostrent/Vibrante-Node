"""Tests for ArchitecturalPlan data models (Tier 10.5)."""

import pytest
from src.runtime.architectural_features.architectural_plan import (
    ArchitecturalOpening,
    FireplacePlacement,
    BeamPlacement,
    WallShelfPlacement,
    ArchitecturalPlan,
    WALL_THICKNESS,
    _WALL_NORMALS,
    _INTERIOR_VECTORS,
)


# ---------------------------------------------------------------------------
# WALL_THICKNESS constant
# ---------------------------------------------------------------------------

class TestConstants:
    def test_wall_thickness_is_positive(self):
        assert WALL_THICKNESS > 0.0

    def test_wall_normals_cover_all_faces(self):
        for face in ("north", "south", "east", "west"):
            assert face in _WALL_NORMALS

    def test_interior_vectors_cover_all_faces(self):
        for face in ("north", "south", "east", "west"):
            assert face in _INTERIOR_VECTORS

    def test_normal_and_interior_are_opposite(self):
        for face in ("north", "south", "east", "west"):
            n = _WALL_NORMALS[face]
            i = _INTERIOR_VECTORS[face]
            for a, b in zip(n, i):
                assert abs(a + b) < 0.001


# ---------------------------------------------------------------------------
# ArchitecturalOpening
# ---------------------------------------------------------------------------

class TestArchitecturalOpening:
    def _make(self, **kwargs):
        defaults = dict(
            opening_id="door_opening_0",
            opening_type="door",
            anchor_id="door_anchor_0",
            wall_face="south",
            wall_normal=[0.0, 0.0, 1.0],
            cx=0.0, cy=1.05, cz=6.0,
            width=0.9, height=2.1,
            depth=WALL_THICKNESS + 0.2,
            houdini_node_name="sh_door_opening_0",
        )
        defaults.update(kwargs)
        return ArchitecturalOpening(**defaults)

    def test_basic_fields(self):
        o = self._make()
        assert o.opening_type == "door"
        assert o.wall_face == "south"
        assert o.depth >= WALL_THICKNESS

    def test_to_dict_round_trip(self):
        o = self._make()
        d = o.to_dict()
        o2 = ArchitecturalOpening.from_dict(d)
        assert o2.opening_id == o.opening_id
        assert o2.opening_type == o.opening_type
        assert o2.width == pytest.approx(o.width, abs=1e-3)
        assert o2.depth == pytest.approx(o.depth, abs=1e-3)

    def test_window_type(self):
        o = self._make(opening_type="window", opening_id="window_opening_0",
                       wall_face="east", wall_normal=[1.0, 0.0, 0.0],
                       cy=2.2)
        assert o.opening_type == "window"
        assert o.wall_face == "east"

    def test_depth_greater_than_wall_thickness(self):
        o = self._make()
        assert o.depth >= WALL_THICKNESS

    def test_houdini_node_name_format(self):
        o = self._make(houdini_node_name="sh_door_opening_0")
        assert o.houdini_node_name.startswith("sh_")

    def test_from_dict_defaults_on_missing_keys(self):
        o = ArchitecturalOpening.from_dict({})
        assert o.opening_type == ""
        assert o.width > 0.0
        assert o.height > 0.0
        assert o.depth >= WALL_THICKNESS


# ---------------------------------------------------------------------------
# FireplacePlacement
# ---------------------------------------------------------------------------

class TestFireplacePlacement:
    def _make(self, **kwargs):
        defaults = dict(
            feature_id="fireplace_0",
            anchor_id="fireplace_anchor_0",
            wall_face="north",
            wall_normal=[0.0, 0.0, -1.0],
            forward_axis=[0.0, 0.0, 1.0],
            tx=0.0, ty=0.0, tz=-5.7,
            width=1.2, height=1.5, depth=0.6,
            wall_coord=-6.0,
            back_face_coord=-5.7,
            back_face_distance=0.3,
            center_offset=0.0,
            houdini_node_name="sh_fireplace_0",
        )
        defaults.update(kwargs)
        return FireplacePlacement(**defaults)

    def test_basic_fields(self):
        fp = self._make()
        assert fp.wall_face == "north"
        assert fp.forward_axis == [0.0, 0.0, 1.0]

    def test_to_dict_round_trip(self):
        fp = self._make()
        d = fp.to_dict()
        fp2 = FireplacePlacement.from_dict(d)
        assert fp2.feature_id == fp.feature_id
        assert fp2.wall_face == fp.wall_face
        assert fp2.back_face_distance == pytest.approx(fp.back_face_distance, abs=1e-4)
        assert fp2.center_offset == pytest.approx(fp.center_offset, abs=1e-4)

    def test_forward_axis_points_to_interior_for_north_wall(self):
        fp = self._make(wall_face="north",
                        wall_normal=[0.0, 0.0, -1.0],
                        forward_axis=[0.0, 0.0, 1.0])
        expected = _INTERIOR_VECTORS["north"]
        assert fp.forward_axis == expected

    def test_from_dict_defaults(self):
        fp = FireplacePlacement.from_dict({})
        assert fp.wall_face == "north"
        assert fp.width > 0.0
        assert fp.depth > 0.0


# ---------------------------------------------------------------------------
# BeamPlacement
# ---------------------------------------------------------------------------

class TestBeamPlacement:
    def _make(self, **kwargs):
        defaults = dict(
            feature_id="beam_0",
            anchor_id="beam_anchor_0",
            tx=0.0, ty=3.675, tz=0.0,
            long_axis="z",
            length=12.0, width=0.20, height=0.30,
            ceiling_height=4.0,
            beam_top_y=3.825,
            gap_to_ceiling=0.175,
            intersects_wall=False,
            is_below_ceiling=True,
            houdini_node_name="sh_beam_0",
        )
        defaults.update(kwargs)
        return BeamPlacement(**defaults)

    def test_basic_fields(self):
        b = self._make()
        assert b.long_axis == "z"
        assert b.is_below_ceiling is True
        assert b.intersects_wall is False

    def test_to_dict_round_trip(self):
        b = self._make()
        d = b.to_dict()
        b2 = BeamPlacement.from_dict(d)
        assert b2.feature_id == b.feature_id
        assert b2.long_axis == b.long_axis
        assert b2.length == pytest.approx(b.length, abs=1e-4)
        assert b2.gap_to_ceiling == pytest.approx(b.gap_to_ceiling, abs=1e-4)

    def test_beam_top_y_below_ceiling(self):
        b = self._make()
        assert b.beam_top_y <= b.ceiling_height

    def test_from_dict_defaults(self):
        b = BeamPlacement.from_dict({})
        assert b.long_axis == "z"
        assert b.length > 0.0
        assert b.is_below_ceiling is True


# ---------------------------------------------------------------------------
# WallShelfPlacement
# ---------------------------------------------------------------------------

class TestWallShelfPlacement:
    def _make(self, **kwargs):
        defaults = dict(
            feature_id="shelf_0",
            anchor_id="wall_shelf_anchor_0_library",
            wall_face="west",
            tx=-4.87, ty=1.20, tz=0.0,
            width=1.0, depth=0.30, thickness=0.05,
            wall_coord=-5.0,
            is_floating=False,
            houdini_node_name="sh_shelf_0",
        )
        defaults.update(kwargs)
        return WallShelfPlacement(**defaults)

    def test_basic_fields(self):
        s = self._make()
        assert s.wall_face == "west"
        assert s.is_floating is False
        assert s.ty > 0

    def test_to_dict_round_trip(self):
        s = self._make()
        d = s.to_dict()
        s2 = WallShelfPlacement.from_dict(d)
        assert s2.feature_id == s.feature_id
        assert s2.wall_face == s.wall_face
        assert s2.ty == pytest.approx(s.ty, abs=1e-4)

    def test_from_dict_defaults(self):
        s = WallShelfPlacement.from_dict({})
        assert s.ty > 0.0
        assert s.width > 0.0


# ---------------------------------------------------------------------------
# ArchitecturalPlan
# ---------------------------------------------------------------------------

class TestArchitecturalPlan:
    def _make_plan(self):
        opening = ArchitecturalOpening(
            opening_id="door_opening_0", opening_type="door",
            anchor_id="door_anchor_0", wall_face="south",
            wall_normal=[0.0, 0.0, 1.0],
            cx=0.0, cy=1.05, cz=6.0,
            width=0.9, height=2.1,
            depth=WALL_THICKNESS + 0.2,
            houdini_node_name="sh_door_opening_0",
        )
        return ArchitecturalPlan(
            environment="western_room",
            door_openings=[opening],
            room_width=10.0, room_length=12.0, room_height=4.0,
        )

    def test_total_features_counts_all(self):
        plan = self._make_plan()
        assert plan.total_features == 1

    def test_to_dict_round_trip(self):
        plan = self._make_plan()
        d = plan.to_dict()
        plan2 = ArchitecturalPlan.from_dict(d)
        assert plan2.environment == plan.environment
        assert len(plan2.door_openings) == 1
        assert plan2.room_width == plan.room_width

    def test_empty_plan_total_features_zero(self):
        plan = ArchitecturalPlan(environment="forest")
        assert plan.total_features == 0

    def test_ok_defaults_true(self):
        plan = ArchitecturalPlan(environment="western_room")
        assert plan.ok is True

    def test_from_dict_with_all_feature_types(self):
        d = {
            "environment": "library",
            "door_openings": [{"opening_id": "d0", "opening_type": "door",
                                "anchor_id": "a0", "wall_face": "south",
                                "wall_normal": [0, 0, 1], "cx": 0, "cy": 1,
                                "cz": 6, "width": 0.9, "height": 2.1,
                                "depth": 0.6}],
            "window_openings": [],
            "fireplace_placements": [],
            "beam_placements": [],
            "shelf_placements": [{"feature_id": "s0", "anchor_id": "wa0",
                                   "wall_face": "west", "tx": -4.87,
                                   "ty": 1.2, "tz": 0.0, "width": 1.0,
                                   "depth": 0.3, "thickness": 0.05,
                                   "wall_coord": -5.0, "is_floating": False}],
            "room_width": 8.0, "room_length": 15.0, "room_height": 5.0,
        }
        plan = ArchitecturalPlan.from_dict(d)
        assert plan.environment == "library"
        assert len(plan.door_openings) == 1
        assert len(plan.shelf_placements) == 1
        assert plan.total_features == 2
