"""Tests for ArchitecturalFeatureRealizer (Tier 10.5).

All tests use build_op_dicts() — the bridge-free dry-run path.
No Houdini connection is required.
"""

import pytest
from src.runtime.architectural_features import (
    ArchitecturalPlan,
    ArchitecturalOpening,
    FireplacePlacement,
    BeamPlacement,
    WallShelfPlacement,
    WALL_THICKNESS,
    RealizationRecord,
    RealizationResult,
    ArchitecturalFeatureRealizer,
    get_architectural_feature_realizer,
    reset_architectural_feature_realizer_for_tests,
    get_architectural_plan_builder,
    reset_architectural_plan_builder_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_architectural_feature_realizer_for_tests()
    reset_architectural_plan_builder_for_tests()
    yield
    reset_architectural_feature_realizer_for_tests()
    reset_architectural_plan_builder_for_tests()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _full_shell():
    return {
        "environment":    "western_room",
        "ceiling_height": 4.0,
        "room_width":     10.0,
        "room_length":    12.0,
        "is_outdoor":     False,
        "ceiling_type":   "beam_ceiling",
        "anchors": [
            {"anchor_id": "door_anchor_0",   "anchor_type": "door_anchor",
             "wall_face": "south", "tx": 0.0, "ty": 1.8, "tz": 6.0,
             "door_width": 0.9, "door_height": 2.1},
            {"anchor_id": "window_anchor_0", "anchor_type": "window_anchor",
             "wall_face": "east", "tx": 5.0, "ty": 2.2, "tz": 0.0,
             "window_width": 1.0, "window_height": 1.2},
            {"anchor_id": "window_anchor_1", "anchor_type": "window_anchor",
             "wall_face": "west", "tx": -5.0, "ty": 2.2, "tz": 0.0,
             "window_width": 1.0, "window_height": 1.2},
            {"anchor_id": "beam_anchor_0",   "anchor_type": "beam_anchor",
             "tx": -2.5, "ty": 3.9, "tz": 0.0, "beam_span": 12.0},
            {"anchor_id": "beam_anchor_1",   "anchor_type": "beam_anchor",
             "tx":  2.5, "ty": 3.9, "tz": 0.0, "beam_span": 12.0},
            {"anchor_id": "fireplace_anchor_0", "anchor_type": "fireplace_anchor",
             "wall_face": "north", "tx": 0.0, "ty": 0.0, "tz": -5.7,
             "fireplace_width": 1.2, "fireplace_height": 1.5},
        ],
    }


def _western_plan() -> ArchitecturalPlan:
    return get_architectural_plan_builder().build(_full_shell())


# ── Singleton ──────────────────────────────────────────────────────────────────

class TestSingleton:
    def test_same_instance(self):
        a = get_architectural_feature_realizer()
        b = get_architectural_feature_realizer()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = get_architectural_feature_realizer()
        reset_architectural_feature_realizer_for_tests()
        b = get_architectural_feature_realizer()
        assert a is not b


# ── build_op_dicts — op structure ─────────────────────────────────────────────

class TestBuildOpDicts:
    def test_returns_list(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        assert isinstance(ops, list)

    def test_non_empty_for_western_room(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        assert len(ops) > 0

    def test_each_op_has_required_keys(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        for op in ops:
            for key in ("feature_id", "feature_type", "houdini_node_name",
                        "tx", "ty", "tz", "sizex", "sizey", "sizez"):
                assert key in op, f"Op {op.get('feature_id')} missing key {key!r}"

    def test_op_houdini_node_names_start_with_sh(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        for op in ops:
            assert op["houdini_node_name"].startswith("sh_"), \
                f"Unexpected node name: {op['houdini_node_name']}"

    def test_door_opening_ops_present(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        door_ops = [o for o in ops if o["feature_type"] == "door_opening"]
        assert len(door_ops) == 1

    def test_window_opening_ops_present(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        win_ops = [o for o in ops if o["feature_type"] == "window_opening"]
        assert len(win_ops) == 2

    def test_beam_ops_present(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        beam_ops = [o for o in ops if o["feature_type"] == "beam"]
        assert len(beam_ops) == 2

    def test_fireplace_ops_present(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        fp_ops = [o for o in ops if o["feature_type"] == "fireplace"]
        assert len(fp_ops) == 1

    def test_shelf_ops_present(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        shelf_ops = [o for o in ops if o["feature_type"] == "shelf"]
        assert len(shelf_ops) == 2    # western_room has 2 shelves


# ── Op sizes — openings ────────────────────────────────────────────────────────

class TestOpeningOpSizes:
    def test_door_opening_sizey_equals_height(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        door_op = next(o for o in ops if o["feature_type"] == "door_opening")
        assert door_op["sizey"] == pytest.approx(2.1, abs=1e-3)

    def test_door_opening_sizez_depth_north_south_wall(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        door_op = next(o for o in ops if o["feature_type"] == "door_opening")
        # south wall → sizex = width (0.9), sizez = depth
        assert door_op["sizex"] == pytest.approx(0.9, abs=1e-3)
        assert door_op["sizez"] > WALL_THICKNESS

    def test_window_opening_east_wall_sizex_is_depth(self):
        plan = _western_plan()
        # Identify the east-wall window from the plan directly
        east_win_in_plan = next(
            o for o in plan.window_openings if o.wall_face == "east"
        )
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        east_win = next(o for o in ops
                        if o["feature_type"] == "window_opening"
                        and o["houdini_node_name"] == east_win_in_plan.houdini_node_name)
        # east wall → sizex = depth (along wall-normal), sizez = width
        assert east_win["sizex"] > WALL_THICKNESS
        assert east_win["sizez"] == pytest.approx(1.0, abs=1e-3)


# ── Op sizes — beams ───────────────────────────────────────────────────────────

class TestBeamOpSizes:
    def test_beam_sizex_is_width_for_z_axis_beam(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        beam_ops = [o for o in ops if o["feature_type"] == "beam"]
        for op in beam_ops:
            assert op["sizex"] == pytest.approx(0.20, abs=1e-3)

    def test_beam_sizez_is_length_for_z_axis_beam(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        beam_ops = [o for o in ops if o["feature_type"] == "beam"]
        for op in beam_ops:
            assert op["sizez"] == pytest.approx(12.0, abs=1e-3)

    def test_x_axis_beam_sizex_is_length(self):
        plan = ArchitecturalPlan(
            environment="western_room",
            beam_placements=[
                BeamPlacement(
                    feature_id="beam_x", anchor_id="ba0",
                    tx=0.0, ty=3.675, tz=0.0,
                    long_axis="x", length=10.0, width=0.20, height=0.30,
                    ceiling_height=4.0, beam_top_y=3.825, gap_to_ceiling=0.02,
                    intersects_wall=False, is_below_ceiling=True,
                    houdini_node_name="sh_beam_x",
                )
            ],
        )
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        beam_op = next(o for o in ops if o["feature_type"] == "beam")
        assert beam_op["sizex"] == pytest.approx(10.0, abs=1e-3)
        assert beam_op["sizez"] == pytest.approx(0.20,  abs=1e-3)


# ── Op sizes — fireplaces ──────────────────────────────────────────────────────

class TestFireplaceOpSizes:
    def test_fireplace_ty_is_half_height(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        fp_op = next(o for o in ops if o["feature_type"] == "fireplace")
        fp = plan.fireplace_placements[0]
        assert fp_op["ty"] == pytest.approx(fp.height / 2.0, abs=1e-3)

    def test_fireplace_sizex_is_width(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        fp_op = next(o for o in ops if o["feature_type"] == "fireplace")
        assert fp_op["sizex"] == pytest.approx(1.2, abs=1e-3)

    def test_fireplace_sizey_is_height(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        fp_op = next(o for o in ops if o["feature_type"] == "fireplace")
        assert fp_op["sizey"] == pytest.approx(1.5, abs=1e-3)


# ── Op sizes — shelves ─────────────────────────────────────────────────────────

class TestShelfOpSizes:
    def test_shelf_sizex_is_width(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        shelf_ops = [o for o in ops if o["feature_type"] == "shelf"]
        for op in shelf_ops:
            assert op["sizex"] == pytest.approx(1.0, abs=1e-3)

    def test_shelf_sizey_is_thickness(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        shelf_ops = [o for o in ops if o["feature_type"] == "shelf"]
        for op in shelf_ops:
            assert op["sizey"] == pytest.approx(0.05, abs=1e-3)

    def test_shelf_sizez_is_depth(self):
        plan = _western_plan()
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        shelf_ops = [o for o in ops if o["feature_type"] == "shelf"]
        for op in shelf_ops:
            assert op["sizez"] == pytest.approx(0.30, abs=1e-3)


# ── Empty and outdoor plans ────────────────────────────────────────────────────

class TestEmptyPlans:
    def test_empty_plan_produces_no_ops(self):
        plan = ArchitecturalPlan(environment="forest", is_outdoor=True)
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        assert ops == []

    def test_plan_with_only_door_produces_one_op(self):
        plan = ArchitecturalPlan(
            environment="western_room",
            door_openings=[
                ArchitecturalOpening(
                    opening_id="d0", opening_type="door",
                    anchor_id="da0", wall_face="south",
                    wall_normal=[0.0, 0.0, 1.0],
                    cx=0.0, cy=1.05, cz=6.0,
                    width=0.9, height=2.1, depth=0.60,
                    houdini_node_name="sh_door_opening_0",
                )
            ],
        )
        ops = get_architectural_feature_realizer().build_op_dicts(plan)
        assert len(ops) == 1
        assert ops[0]["feature_type"] == "door_opening"


# ── Determinism ────────────────────────────────────────────────────────────────

class TestDeterminism:
    def test_same_plan_same_ops(self):
        plan = _western_plan()
        r = get_architectural_feature_realizer()
        ops1 = r.build_op_dicts(plan)
        ops2 = r.build_op_dicts(plan)
        assert len(ops1) == len(ops2)
        for o1, o2 in zip(ops1, ops2):
            assert o1["feature_type"] == o2["feature_type"]
            assert o1["houdini_node_name"] == o2["houdini_node_name"]
            assert o1["sizex"] == pytest.approx(o2["sizex"], abs=1e-6)


# ── RealizationResult / RealizationRecord models ──────────────────────────────

class TestResultModels:
    def test_realization_record_to_dict(self):
        rec = RealizationRecord(
            feature_id="door_opening_0",
            feature_type="door_opening",
            houdini_node_name="sh_door_opening_0",
            houdini_path="/obj/sh_door_opening_0",
            ok=True,
        )
        d = rec.to_dict()
        assert d["feature_id"] == "door_opening_0"
        assert d["ok"] is True

    def test_realization_result_to_dict(self):
        res = RealizationResult(
            realized=3, skipped=0, failed=0, ok=True,
        )
        d = res.to_dict()
        assert d["realized"] == 3
        assert d["ok"] is True
