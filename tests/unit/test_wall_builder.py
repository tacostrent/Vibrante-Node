"""Tests for WallBuilder — §49 Structural Environment Realization."""
import pytest
from src.runtime.environment_realization import (
    get_wall_builder, reset_wall_builder_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_wall_builder_for_tests()
    yield
    reset_wall_builder_for_tests()


def test_western_room_four_walls():
    walls = get_wall_builder().build_walls("western_room", 10.0, 4.0, 12.0)
    assert len(walls) == 4
    for face in ("north", "south", "east", "west"):
        assert face in walls


def test_western_room_wall_material_wood():
    walls = get_wall_builder().build_walls("western_room", 10.0, 4.0, 12.0)
    for w in walls.values():
        assert w.material == "wood"


def test_castle_hall_wall_material_stone():
    walls = get_wall_builder().build_walls("castle_hall", 20.0, 10.0, 30.0)
    for w in walls.values():
        assert w.material == "stone"


def test_sci_fi_corridor_wall_material():
    walls = get_wall_builder().build_walls("sci_fi_corridor", 4.0, 3.0, 20.0)
    for w in walls.values():
        assert w.material == "sci_fi_panel"


def test_outdoor_forest_no_walls():
    walls = get_wall_builder().build_walls("forest", 0.0, 0.0, 0.0)
    assert len(walls) == 0


def test_north_wall_position():
    walls = get_wall_builder().build_walls("western_room", 10.0, 4.0, 12.0)
    north = walls["north"]
    assert north.position[2] == pytest.approx(-6.0)   # -depth/2


def test_south_wall_position():
    walls = get_wall_builder().build_walls("western_room", 10.0, 4.0, 12.0)
    south = walls["south"]
    assert south.position[2] == pytest.approx(6.0)    # +depth/2


def test_east_wall_position():
    walls = get_wall_builder().build_walls("western_room", 10.0, 4.0, 12.0)
    east = walls["east"]
    assert east.position[0] == pytest.approx(5.0)    # +width/2


def test_west_wall_position():
    walls = get_wall_builder().build_walls("western_room", 10.0, 4.0, 12.0)
    west = walls["west"]
    assert west.position[0] == pytest.approx(-5.0)   # -width/2


def test_wall_height_matches_room():
    walls = get_wall_builder().build_walls("warehouse", 20.0, 8.0, 30.0)
    for w in walls.values():
        assert w.dimensions["height"] == pytest.approx(8.0)


def test_north_south_wall_width_equals_room_width():
    walls = get_wall_builder().build_walls("western_room", 10.0, 4.0, 12.0)
    assert walls["north"].dimensions["width"] == pytest.approx(10.0)
    assert walls["south"].dimensions["width"] == pytest.approx(10.0)


def test_east_west_wall_width_equals_room_depth():
    walls = get_wall_builder().build_walls("western_room", 10.0, 4.0, 12.0)
    assert walls["east"].dimensions["width"] == pytest.approx(12.0)
    assert walls["west"].dimensions["width"] == pytest.approx(12.0)
