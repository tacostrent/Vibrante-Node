"""Tests for EnvironmentRealizationEngine — §49 Structural Environment Realization."""
import pytest
from src.runtime.environment_realization import (
    get_environment_realization_engine, reset_environment_realization_engine_for_tests,
    get_structural_builder, reset_structural_builder_for_tests,
    get_room_shell_builder, reset_room_shell_builder_for_tests,
    reset_floor_builder_for_tests, reset_ceiling_builder_for_tests,
    reset_wall_builder_for_tests, reset_opening_builder_for_tests,
    reset_beam_builder_for_tests, reset_architectural_constraint_solver_for_tests,
    reset_env_realization_review_for_tests, reset_env_realization_statistics_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    for fn in [
        reset_environment_realization_engine_for_tests,
        reset_structural_builder_for_tests, reset_room_shell_builder_for_tests,
        reset_floor_builder_for_tests, reset_ceiling_builder_for_tests,
        reset_wall_builder_for_tests, reset_opening_builder_for_tests,
        reset_beam_builder_for_tests, reset_architectural_constraint_solver_for_tests,
        reset_env_realization_review_for_tests, reset_env_realization_statistics_for_tests,
    ]:
        fn()
    yield
    for fn in [
        reset_environment_realization_engine_for_tests,
        reset_structural_builder_for_tests, reset_room_shell_builder_for_tests,
        reset_floor_builder_for_tests, reset_ceiling_builder_for_tests,
        reset_wall_builder_for_tests, reset_opening_builder_for_tests,
        reset_beam_builder_for_tests, reset_architectural_constraint_solver_for_tests,
        reset_env_realization_review_for_tests, reset_env_realization_statistics_for_tests,
    ]:
        fn()


def test_western_room_production_ready():
    plan = get_environment_realization_engine().realize("western_room")
    assert plan.ok
    assert plan.production_ready, (
        f"western_room not production_ready: walls={plan.wall_count} "
        f"floor={plan.floor_count} ceiling={plan.ceiling_count}"
    )


def test_western_room_all_structural():
    plan = get_environment_realization_engine().realize("western_room")
    assert plan.floor_count == 1
    assert plan.wall_count == 4
    assert plan.ceiling_count == 1
    assert plan.door_count >= 1
    assert plan.window_count >= 2
    assert plan.beam_count == 4


def test_industrial_hangar_production_ready():
    plan = get_environment_realization_engine().realize("industrial_hangar")
    assert plan.production_ready


def test_castle_hall_production_ready():
    plan = get_environment_realization_engine().realize("castle_hall")
    assert plan.production_ready


def test_sci_fi_corridor_production_ready():
    plan = get_environment_realization_engine().realize("sci_fi_corridor")
    assert plan.production_ready


def test_forest_outdoor_production_ready():
    plan = get_environment_realization_engine().realize("forest")
    assert plan.production_ready


def test_zones_populated():
    plan = get_environment_realization_engine().realize("western_room")
    assert plan.zone_count == 6


def test_transaction_ops_have_correct_format():
    plan = get_environment_realization_engine().realize("western_room")
    assert len(plan.transaction_ops) > 0
    valid_ops = {"create_node", "set_parms", "set_display_flag", "layout_children"}
    for op in plan.transaction_ops:
        assert "op" in op, f"Op missing 'op' key: {op}"
        assert op["op"] in valid_ops, f"Unknown op type: {op['op']}"
    # All set_parms ops must carry tx/ty/tz
    parm_ops = [op for op in plan.transaction_ops if op["op"] == "set_parms"]
    assert len(parm_ops) > 0
    for op in parm_ops:
        assert "parms" in op
        for key in ("tx", "ty", "tz"):
            assert key in op["parms"], f"Missing parm {key!r} in {op}"


def test_room_closed_western_room():
    plan = get_environment_realization_engine().realize("western_room")
    assert plan.room_closed


def test_override_dims():
    plan = get_environment_realization_engine().realize("western_room", (15.0, 5.0, 20.0))
    assert plan.room_shell.width == pytest.approx(15.0)


def test_deterministic():
    p1 = get_environment_realization_engine().realize("western_room")
    p2 = get_environment_realization_engine().realize("western_room")
    assert p1.wall_count == p2.wall_count
    assert p1.beam_count == p2.beam_count
    assert p1.production_ready == p2.production_ready
