"""Tests for ArchitecturalPlanBuilder (Tier 10.5)."""

import pytest
from src.runtime.architectural_features import (
    ArchitecturalPlan,
    ArchitecturalPlanBuilder,
    get_architectural_plan_builder,
    reset_architectural_plan_builder_for_tests,
    WALL_THICKNESS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_architectural_plan_builder_for_tests()
    yield
    reset_architectural_plan_builder_for_tests()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _western_shell():
    """Minimal shell dict for a western_room (10m × 4m × 12m)."""
    return {
        "environment":    "western_room",
        "ceiling_height": 4.0,
        "room_width":     10.0,
        "room_length":    12.0,
        "is_outdoor":     False,
        "ceiling_type":   "beam_ceiling",
        "anchors": [
            {
                "anchor_id":    "door_anchor_0",
                "anchor_type":  "door_anchor",
                "wall_face":    "south",
                "tx": 0.0, "ty": 1.8, "tz": 6.0,
                "door_width":   0.9, "door_height": 2.1,
            },
            {
                "anchor_id":    "window_anchor_0",
                "anchor_type":  "window_anchor",
                "wall_face":    "east",
                "tx": 5.0, "ty": 2.2, "tz": 0.0,
                "window_width": 1.0, "window_height": 1.2,
            },
            {
                "anchor_id":    "window_anchor_1",
                "anchor_type":  "window_anchor",
                "wall_face":    "west",
                "tx": -5.0, "ty": 2.2, "tz": 0.0,
                "window_width": 1.0, "window_height": 1.2,
            },
            {
                "anchor_id":            "beam_anchor_0",
                "anchor_type":          "beam_anchor",
                "tx": -2.5, "ty": 3.9, "tz": 0.0,
                "beam_span":            12.0,
            },
            {
                "anchor_id":            "beam_anchor_1",
                "anchor_type":          "beam_anchor",
                "tx":  2.5, "ty": 3.9, "tz": 0.0,
                "beam_span":            12.0,
            },
            {
                "anchor_id":            "fireplace_anchor_0",
                "anchor_type":          "fireplace_anchor",
                "wall_face":            "north",
                "tx": 0.0, "ty": 0.0, "tz": -5.7,
                "fireplace_width":      1.2,
                "fireplace_height":     1.5,
            },
        ],
    }


def _outdoor_shell():
    return {
        "environment": "forest",
        "is_outdoor":  True,
        "anchors":     [],
    }


# ── Singleton ──────────────────────────────────────────────────────────────────

class TestSingleton:
    def test_same_instance(self):
        a = get_architectural_plan_builder()
        b = get_architectural_plan_builder()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = get_architectural_plan_builder()
        reset_architectural_plan_builder_for_tests()
        b = get_architectural_plan_builder()
        assert a is not b


# ── Outdoor environment ────────────────────────────────────────────────────────

class TestOutdoorPlan:
    def test_outdoor_plan_has_no_features(self):
        plan = get_architectural_plan_builder().build(_outdoor_shell())
        assert plan.is_outdoor is True
        assert plan.total_features == 0

    def test_outdoor_plan_ok(self):
        plan = get_architectural_plan_builder().build(_outdoor_shell())
        assert plan.ok is True


# ── Door openings ──────────────────────────────────────────────────────────────

class TestDoorOpenings:
    def test_one_door_opening_for_one_anchor(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        assert len(plan.door_openings) == 1

    def test_door_opening_has_correct_wall_face(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        door = plan.door_openings[0]
        assert door.wall_face == "south"

    def test_door_opening_width_from_anchor(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        door = plan.door_openings[0]
        assert door.width == pytest.approx(0.9, abs=1e-3)

    def test_door_opening_height_from_anchor(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        door = plan.door_openings[0]
        assert door.height == pytest.approx(2.1, abs=1e-3)

    def test_door_opening_depth_exceeds_wall_thickness(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        door = plan.door_openings[0]
        assert door.depth > WALL_THICKNESS

    def test_door_cy_at_half_height(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        door = plan.door_openings[0]
        assert door.cy == pytest.approx(2.1 / 2.0, abs=1e-3)

    def test_door_houdini_node_name(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        door = plan.door_openings[0]
        assert door.houdini_node_name == "sh_door_opening_0"

    def test_door_anchor_id_preserved(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        assert plan.door_openings[0].anchor_id == "door_anchor_0"


# ── Window openings ────────────────────────────────────────────────────────────

class TestWindowOpenings:
    def test_two_window_openings_for_two_anchors(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        assert len(plan.window_openings) == 2

    def test_window_faces_match_anchors(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        faces = {o.wall_face for o in plan.window_openings}
        assert "east" in faces
        assert "west" in faces

    def test_window_houdini_node_names(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        names = [o.houdini_node_name for o in plan.window_openings]
        assert "sh_window_opening_0" in names
        assert "sh_window_opening_1" in names

    def test_window_depth_exceeds_wall_thickness(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        for win in plan.window_openings:
            assert win.depth > WALL_THICKNESS


# ── Fireplace ─────────────────────────────────────────────────────────────────

class TestFireplacePlacement:
    def test_one_fireplace_for_one_anchor(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        assert len(plan.fireplace_placements) == 1

    def test_fireplace_on_north_wall(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        fp = plan.fireplace_placements[0]
        assert fp.wall_face == "north"

    def test_fireplace_forward_axis_faces_interior(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        fp = plan.fireplace_placements[0]
        assert fp.forward_axis == [0.0, 0.0, 1.0]

    def test_fireplace_center_offset_near_zero(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        fp = plan.fireplace_placements[0]
        assert fp.center_offset == pytest.approx(0.0, abs=1e-3)

    def test_fireplace_houdini_node_name(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        assert plan.fireplace_placements[0].houdini_node_name == "sh_fireplace_0"


# ── Beam placements ────────────────────────────────────────────────────────────

class TestBeamPlacements:
    def test_two_beams_for_two_anchors(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        assert len(plan.beam_placements) == 2

    def test_beam_long_axis_z(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        for b in plan.beam_placements:
            assert b.long_axis == "z"

    def test_beam_length_equals_room_depth(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        for b in plan.beam_placements:
            assert b.length == pytest.approx(12.0, abs=1e-3)

    def test_beam_is_below_ceiling(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        for b in plan.beam_placements:
            assert b.is_below_ceiling is True

    def test_beam_does_not_intersect_walls(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        for b in plan.beam_placements:
            assert b.intersects_wall is False

    def test_beam_gap_to_ceiling_small(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        for b in plan.beam_placements:
            assert b.gap_to_ceiling <= 0.10

    def test_beam_houdini_node_names(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        names = [b.houdini_node_name for b in plan.beam_placements]
        assert "sh_beam_0" in names
        assert "sh_beam_1" in names

    def test_beam_dims_from_beam_ceiling_type(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        for b in plan.beam_placements:
            assert b.width == pytest.approx(0.20, abs=1e-3)
            assert b.height == pytest.approx(0.30, abs=1e-3)


# ── Wall shelves ───────────────────────────────────────────────────────────────

class TestWallShelves:
    def test_western_room_gets_two_shelves(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        assert len(plan.shelf_placements) == 2

    def test_library_gets_six_shelves(self):
        shell = _western_shell()
        shell["environment"] = "library"
        plan = get_architectural_plan_builder().build(shell)
        assert len(plan.shelf_placements) == 6

    def test_no_shelves_for_unknown_environment(self):
        shell = _western_shell()
        shell["environment"] = "dungeon"
        shell["anchors"] = []
        plan = get_architectural_plan_builder().build(shell)
        assert len(plan.shelf_placements) == 0

    def test_shelves_not_floating(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        for s in plan.shelf_placements:
            assert s.is_floating is False

    def test_shelves_above_floor(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        for s in plan.shelf_placements:
            assert s.ty > 0.0

    def test_shelf_houdini_node_names(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        for i, s in enumerate(plan.shelf_placements):
            assert s.houdini_node_name == f"sh_shelf_{i}"


# ── Room geometry extraction ───────────────────────────────────────────────────

class TestRoomGeometry:
    def test_room_dims_from_shell(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        assert plan.room_width  == pytest.approx(10.0, abs=1e-3)
        assert plan.room_length == pytest.approx(12.0, abs=1e-3)
        assert plan.room_height == pytest.approx(4.0,  abs=1e-3)

    def test_defaults_when_no_dims(self):
        plan = get_architectural_plan_builder().build({})
        assert plan.room_width  > 0.0
        assert plan.room_length > 0.0
        assert plan.room_height > 0.0

    def test_environment_name_preserved(self):
        plan = get_architectural_plan_builder().build(_western_shell())
        assert plan.environment == "western_room"


# ── Determinism ────────────────────────────────────────────────────────────────

class TestDeterminism:
    def test_same_shell_same_plan(self):
        builder = get_architectural_plan_builder()
        shell = _western_shell()
        p1 = builder.build(shell)
        p2 = builder.build(shell)
        assert len(p1.door_openings)        == len(p2.door_openings)
        assert len(p1.window_openings)      == len(p2.window_openings)
        assert len(p1.beam_placements)      == len(p2.beam_placements)
        assert len(p1.fireplace_placements) == len(p2.fireplace_placements)
        assert p1.door_openings[0].cx       == pytest.approx(p2.door_openings[0].cx)


# ── Never raises ──────────────────────────────────────────────────────────────

class TestNeverRaises:
    def test_none_input(self):
        plan = get_architectural_plan_builder().build(None)
        assert isinstance(plan, ArchitecturalPlan)

    def test_empty_dict(self):
        plan = get_architectural_plan_builder().build({})
        assert isinstance(plan, ArchitecturalPlan)

    def test_garbage_input(self):
        plan = get_architectural_plan_builder().build("not_a_dict")
        assert isinstance(plan, ArchitecturalPlan)
