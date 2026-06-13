"""Tests for RoomShellBuilder — §49 Structural Environment Realization."""
import pytest
from src.runtime.environment_realization import (
    get_room_shell_builder, reset_room_shell_builder_for_tests,
    reset_floor_builder_for_tests, reset_ceiling_builder_for_tests,
    reset_wall_builder_for_tests, reset_opening_builder_for_tests,
    reset_beam_builder_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    for fn in [
        reset_room_shell_builder_for_tests,
        reset_floor_builder_for_tests, reset_ceiling_builder_for_tests,
        reset_wall_builder_for_tests, reset_opening_builder_for_tests,
        reset_beam_builder_for_tests,
    ]:
        fn()
    yield
    for fn in [
        reset_room_shell_builder_for_tests,
        reset_floor_builder_for_tests, reset_ceiling_builder_for_tests,
        reset_wall_builder_for_tests, reset_opening_builder_for_tests,
        reset_beam_builder_for_tests,
    ]:
        fn()


def test_western_room_shell_complete():
    shell = get_room_shell_builder().build("western_room")
    assert shell.ok
    assert shell.floor is not None
    assert shell.ceiling is not None
    assert len(shell.walls) == 4
    assert len(shell.openings) >= 1
    assert shell.room_closed


def test_western_room_dimensions():
    shell = get_room_shell_builder().build("western_room")
    assert shell.width == pytest.approx(10.0)
    assert shell.height == pytest.approx(4.0)
    assert shell.depth == pytest.approx(12.0)


def test_western_room_has_beams():
    shell = get_room_shell_builder().build("western_room")
    assert len(shell.beams) == 4


def test_castle_hall_vaulted_ceiling():
    shell = get_room_shell_builder().build("castle_hall")
    assert shell.ceiling.metadata["ceiling_type"] == "vaulted_ceiling"


def test_industrial_hangar_columns():
    shell = get_room_shell_builder().build("industrial_hangar")
    assert len(shell.columns) >= 4


def test_outdoor_forest_no_walls():
    shell = get_room_shell_builder().build("forest")
    assert shell.is_outdoor
    assert len(shell.walls) == 0
    assert shell.floor is not None


def test_outdoor_room_closed_is_true():
    """Outdoor environments are considered 'closed' (no indoor requirement)."""
    shell = get_room_shell_builder().build("forest")
    assert shell.room_closed  # outdoor = no walls required


def test_override_dimensions():
    shell = get_room_shell_builder().build("western_room", override_dims=(20.0, 6.0, 25.0))
    assert shell.width == pytest.approx(20.0)
    assert shell.height == pytest.approx(6.0)
    assert shell.depth == pytest.approx(25.0)


def test_get_dimensions_helper():
    w, h, d = get_room_shell_builder().get_dimensions("western_room")
    assert w == pytest.approx(10.0)
    assert h == pytest.approx(4.0)
    assert d == pytest.approx(12.0)


def test_all_elements_flat_list():
    shell = get_room_shell_builder().build("western_room")
    elements = shell.all_elements()
    assert len(elements) >= 7  # floor + 4 walls + ceiling + openings


def test_deterministic():
    """Room shells are structurally identical (shell_id differs as it's a UUID)."""
    s1 = get_room_shell_builder().build("saloon")
    s2 = get_room_shell_builder().build("saloon")
    # Compare structural content, excluding UUID-based IDs
    assert s1.width == s2.width
    assert s1.height == s2.height
    assert s1.depth == s2.depth
    assert s1.primary_material == s2.primary_material
    assert len(s1.walls) == len(s2.walls)
    assert len(s1.openings) == len(s2.openings)
    assert len(s1.beams) == len(s2.beams)
    assert s1.room_closed == s2.room_closed
