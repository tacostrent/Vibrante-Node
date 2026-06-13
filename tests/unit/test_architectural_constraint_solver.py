"""Tests for ArchitecturalConstraintSolver — §49 Structural Environment Realization."""
import pytest
from src.runtime.environment_realization import (
    get_architectural_constraint_solver, reset_architectural_constraint_solver_for_tests,
    get_room_shell_builder, reset_room_shell_builder_for_tests,
    reset_floor_builder_for_tests, reset_ceiling_builder_for_tests,
    reset_wall_builder_for_tests, reset_opening_builder_for_tests,
    reset_beam_builder_for_tests,
    RoomShell,
)


@pytest.fixture(autouse=True)
def reset():
    for fn in [
        reset_architectural_constraint_solver_for_tests,
        reset_room_shell_builder_for_tests, reset_floor_builder_for_tests,
        reset_ceiling_builder_for_tests, reset_wall_builder_for_tests,
        reset_opening_builder_for_tests, reset_beam_builder_for_tests,
    ]:
        fn()
    yield
    for fn in [
        reset_architectural_constraint_solver_for_tests,
        reset_room_shell_builder_for_tests, reset_floor_builder_for_tests,
        reset_ceiling_builder_for_tests, reset_wall_builder_for_tests,
        reset_opening_builder_for_tests, reset_beam_builder_for_tests,
    ]:
        fn()


def test_valid_western_room_no_violations():
    shell = get_room_shell_builder().build("western_room")
    result = get_architectural_constraint_solver().solve(shell)
    assert result.violations_remaining == 0


def test_missing_wall_detected():
    shell = get_room_shell_builder().build("western_room")
    del shell.walls["north"]  # remove one wall
    result = get_architectural_constraint_solver().solve(shell)
    wall_violations = [v for v in result.violations if v.constraint_type == "room_closure" and "north" in v.description]
    assert len(wall_violations) >= 1


def test_missing_floor_detected():
    shell = get_room_shell_builder().build("western_room")
    shell.floor = None
    result = get_architectural_constraint_solver().solve(shell)
    floor_violations = [v for v in result.violations if "floor" in v.description]
    assert len(floor_violations) >= 1


def test_ceiling_dimension_mismatch_corrected():
    shell = get_room_shell_builder().build("western_room")
    shell.ceiling.dimensions["width"] = 5.0  # wrong width
    result = get_architectural_constraint_solver().solve(shell)
    ceiling_violations = [v for v in result.violations if v.constraint_type == "no_disconnected_ceiling"]
    assert any(v.corrected for v in ceiling_violations)
    # Ceiling should now match room width
    assert shell.ceiling.dimensions["width"] == pytest.approx(10.0)


def test_outdoor_no_violations():
    shell = get_room_shell_builder().build("forest")
    result = get_architectural_constraint_solver().solve(shell)
    assert result.violations_found == 0


def test_opening_with_invalid_wall_id_detected():
    shell = get_room_shell_builder().build("western_room")
    # Corrupt opening wall_id
    if shell.openings:
        shell.openings[0].wall_id = "nonexistent_wall_123"
    result = get_architectural_constraint_solver().solve(shell)
    invalid = [v for v in result.violations if "wall_id" in v.description or "not exist" in v.description]
    assert len(invalid) >= 1


def test_violations_found_ge_remaining():
    shell = get_room_shell_builder().build("western_room")
    shell.floor = None
    result = get_architectural_constraint_solver().solve(shell)
    assert result.violations_found >= result.violations_remaining


def test_never_raises_on_empty_shell():
    shell = RoomShell(environment="western_room", is_outdoor=False)
    result = get_architectural_constraint_solver().solve(shell)
    assert result.violations_found > 0  # floor + walls + ceiling missing


def test_valid_industrial_hangar_no_structural_violations():
    shell = get_room_shell_builder().build("industrial_hangar")
    result = get_architectural_constraint_solver().solve(shell)
    structural_violations = [v for v in result.violations if v.constraint_type == "room_closure"]
    assert len(structural_violations) == 0
