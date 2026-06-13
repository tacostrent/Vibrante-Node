"""Tests for the §54 Relationship Correction Pass (Tier 15.0+)."""

import pytest

from src.runtime.reality.correction_pass_engine import (
    get_reality_correction_pass,
    reset_reality_correction_pass_for_tests,
)
from src.runtime.reality.floating_object_detector import (
    reset_floating_object_detector_for_tests,
)
from src.runtime.reality.functional_zone_builder import (
    reset_functional_zone_builder_for_tests,
)
from src.runtime.reality.correction_applier import (
    get_correction_applier,
    reset_correction_applier_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    for reset in (reset_reality_correction_pass_for_tests,
                  reset_floating_object_detector_for_tests,
                  reset_functional_zone_builder_for_tests,
                  reset_correction_applier_for_tests):
        reset()
    yield
    for reset in (reset_reality_correction_pass_for_tests,
                  reset_floating_object_detector_for_tests,
                  reset_functional_zone_builder_for_tests,
                  reset_correction_applier_for_tests):
        reset()


def _scene(transforms):
    return {"environment": "western_room", "transforms": transforms}


class TestCorrectionPlanning:
    def test_clean_scene_produces_no_ops(self, western_room_scene):
        plan = get_reality_correction_pass().build_correction_plan(western_room_scene)
        assert plan.clean, [o.reason for o in plan.ops]

    def test_floating_prop_gets_drop_fix(self):
        plan = get_reality_correction_pass().build_correction_plan(_scene([
            {"asset_id": "t", "asset_name": "Table", "tx": 0, "ty": 0.375, "tz": 0,
             "bbox_half_x": 1.1, "bbox_half_y": 0.375, "bbox_half_z": 0.65},
            {"asset_id": "b", "asset_name": "Whiskey Bottle", "tx": 0.3, "ty": 2.5,
             "tz": 0.2, "bbox_half_x": 0.05, "bbox_half_y": 0.15, "bbox_half_z": 0.05},
        ]))
        assert plan.floating_fixes == 1
        op = [o for o in plan.ops if o.category == "floating"][0]
        assert op.asset_id == "b"
        assert op.parms["ty"] == pytest.approx(0.90)

    def test_chair_facing_away_gets_rotation_fix(self):
        plan = get_reality_correction_pass().build_correction_plan(_scene([
            {"asset_id": "t", "asset_name": "Table", "tx": 0, "ty": 0.375, "tz": 0,
             "bbox_half_x": 1.1, "bbox_half_y": 0.375, "bbox_half_z": 0.65},
            # Chair south of the table but facing AWAY (ry=0 faces +z, table is at -z)
            {"asset_id": "c", "asset_name": "Wooden Chair", "tx": 0, "ty": 0.45,
             "tz": 1.55, "ry": 0.0,
             "bbox_half_x": 0.25, "bbox_half_y": 0.45, "bbox_half_z": 0.25},
        ]))
        assert plan.facing_fixes == 1
        op = [o for o in plan.ops if o.category == "facing"][0]
        assert op.parms["ry"] == pytest.approx(180.0)

    def test_wall_intersection_gets_push_fix(self):
        plan = get_reality_correction_pass().build_correction_plan(_scene([
            {"asset_id": "c", "asset_name": "Wooden Crate", "tx": 5.2, "ty": 0.4,
             "tz": 0, "bbox_half_x": 0.4, "bbox_half_y": 0.4, "bbox_half_z": 0.4},
        ]))
        assert plan.wall_fixes == 1
        op = [o for o in plan.ops if o.category == "wall_intersection"][0]
        assert op.parms["tx"] == pytest.approx(4.6)   # wall_x - half_x

    def test_deterministic(self, western_room_scene):
        western_room_scene["transforms"][5]["ty"] = 3.0   # float the bottle
        p1 = get_reality_correction_pass().build_correction_plan(western_room_scene).to_dict()
        p2 = get_reality_correction_pass().build_correction_plan(western_room_scene).to_dict()
        assert p1 == p2

    def test_never_raises(self):
        plan = get_reality_correction_pass().build_correction_plan(None)
        assert plan.ops == []


class TestCorrectionApplier:
    def test_build_op_dicts_dry_run(self):
        plan = get_reality_correction_pass().build_correction_plan(_scene([
            {"asset_id": "c", "asset_name": "Wooden Crate", "tx": 5.2, "ty": 0.4,
             "tz": 0, "bbox_half_x": 0.4, "bbox_half_y": 0.4, "bbox_half_z": 0.4},
        ]))
        ops = get_correction_applier().build_op_dicts(
            [o.to_dict() for o in plan.ops],
            {"c": "/obj/env/crate_01"},
        )
        assert len(ops) == 1
        assert ops[0]["type"] == "set_parms"
        assert ops[0]["node_path"] == "/obj/env/crate_01"
        assert "tx" in ops[0]["parms"]

    def test_unmapped_assets_skipped_in_dry_run(self):
        ops = get_correction_applier().build_op_dicts(
            [{"asset_id": "ghost", "parms": {"ty": 1.0}, "reason": "x"}], {})
        assert ops == []
