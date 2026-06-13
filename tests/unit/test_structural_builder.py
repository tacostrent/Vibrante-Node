"""Tests for StructuralBuilder — §49 Structural Environment Realization."""
import pytest
from src.runtime.environment_realization import (
    get_structural_builder, reset_structural_builder_for_tests,
    reset_room_shell_builder_for_tests, reset_floor_builder_for_tests,
    reset_ceiling_builder_for_tests, reset_wall_builder_for_tests,
    reset_opening_builder_for_tests, reset_beam_builder_for_tests,
    reset_architectural_constraint_solver_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    for fn in [
        reset_structural_builder_for_tests,
        reset_room_shell_builder_for_tests, reset_floor_builder_for_tests,
        reset_ceiling_builder_for_tests, reset_wall_builder_for_tests,
        reset_opening_builder_for_tests, reset_beam_builder_for_tests,
        reset_architectural_constraint_solver_for_tests,
    ]:
        fn()
    yield
    for fn in [
        reset_structural_builder_for_tests,
        reset_room_shell_builder_for_tests, reset_floor_builder_for_tests,
        reset_ceiling_builder_for_tests, reset_wall_builder_for_tests,
        reset_opening_builder_for_tests, reset_beam_builder_for_tests,
        reset_architectural_constraint_solver_for_tests,
    ]:
        fn()


def test_western_room_plan_complete():
    plan = get_structural_builder().build("western_room")
    assert plan.ok
    assert plan.room_closed
    assert plan.wall_count == 4
    assert plan.floor_count == 1
    assert plan.ceiling_count == 1
    assert plan.door_count >= 1


def test_western_room_production_ready():
    plan = get_structural_builder().build("western_room")
    assert plan.production_ready


def test_transaction_ops_generated():
    plan = get_structural_builder().build("western_room")
    assert len(plan.transaction_ops) > 0
    valid_ops = {"create_node", "set_parms", "set_display_flag", "layout_children"}
    for op in plan.transaction_ops:
        assert "op" in op, f"Op missing 'op' key: {op}"
        assert op["op"] in valid_ops, f"Unknown op type: {op['op']}"
    # create_node ops must have parent and type
    create_ops = [op for op in plan.transaction_ops if op["op"] == "create_node"]
    assert len(create_ops) > 0
    for op in create_ops:
        assert "parent" in op
        assert "type" in op
    # set_parms ops: geo-node transform ops must carry tx/ty/tz;
    # box-SOP size ops carry sizex/sizey/sizez instead — both are valid.
    parm_ops = [op for op in plan.transaction_ops if op["op"] == "set_parms"]
    assert len(parm_ops) > 0
    for op in parm_ops:
        assert "node" in op
        assert "parms" in op
    transform_ops = [op for op in parm_ops if "tx" in op["parms"]]
    size_ops      = [op for op in parm_ops if "sizex" in op["parms"]]
    assert len(transform_ops) > 0, "Expected at least one set_parms with tx/ty/tz"
    assert len(size_ops) > 0,      "Expected at least one set_parms with sizex/sizey/sizez (box SOP)"
    for op in transform_ops:
        for key in ("tx", "ty", "tz"):
            assert key in op["parms"], f"Missing parm {key!r}"
    for op in size_ops:
        for key in ("sizex", "sizey", "sizez"):
            assert key in op["parms"], f"Missing box parm {key!r}"


def test_structural_elements_flat():
    plan = get_structural_builder().build("western_room")
    assert len(plan.structural_elements) >= 8  # floor + 4 walls + ceiling + openings


def test_zone_regions_present():
    plan = get_structural_builder().build("western_room")
    assert plan.zone_count == 6
    zone_names = {z["zone"] for z in plan.zone_regions}
    assert "hero_zone" in zone_names
    assert "entrance_zone" in zone_names


def test_industrial_hangar_plan():
    plan = get_structural_builder().build("industrial_hangar")
    assert plan.room_closed
    assert plan.beam_count == 8
    assert plan.column_count == 6
    assert plan.door_count >= 1


def test_outdoor_forest_plan():
    plan = get_structural_builder().build("forest")
    assert plan.floor_count == 1
    assert plan.wall_count == 0
    assert plan.production_ready  # outdoor plans are production-ready


def test_castle_hall_plan():
    plan = get_structural_builder().build("castle_hall")
    assert plan.room_closed
    assert plan.door_count >= 1


def test_override_dimensions():
    plan = get_structural_builder().build("western_room", (20.0, 6.0, 25.0))
    shell = plan.room_shell
    assert shell.width == pytest.approx(20.0)


def test_deterministic():
    p1 = get_structural_builder().build("western_room")
    p2 = get_structural_builder().build("western_room")
    assert p1.wall_count == p2.wall_count
    assert p1.beam_count == p2.beam_count
    assert len(p1.transaction_ops) == len(p2.transaction_ops)
