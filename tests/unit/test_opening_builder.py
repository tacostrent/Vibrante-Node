"""Tests for OpeningBuilder — §49 Structural Environment Realization."""
import pytest
from src.runtime.environment_realization import (
    get_opening_builder, reset_opening_builder_for_tests,
    get_wall_builder, reset_wall_builder_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_opening_builder_for_tests()
    reset_wall_builder_for_tests()
    yield
    reset_opening_builder_for_tests()
    reset_wall_builder_for_tests()


def _walls(env="western_room", w=10.0, h=4.0, d=12.0):
    return get_wall_builder().build_walls(env, w, h, d)


def test_western_room_has_door():
    walls = _walls()
    openings = get_opening_builder().build_openings("western_room", walls)
    doors = [o for o in openings if "door" in o.element_type]
    assert len(doors) >= 1


def test_western_room_has_windows():
    walls = _walls()
    openings = get_opening_builder().build_openings("western_room", walls)
    windows = [o for o in openings if o.element_type == "window"]
    assert len(windows) == 2


def test_openings_reference_parent_wall():
    walls = _walls()
    openings = get_opening_builder().build_openings("western_room", walls)
    for o in openings:
        assert o.wall_id != "", f"{o.element_id} has no wall_id"


def test_door_height_positive():
    walls = _walls()
    openings = get_opening_builder().build_openings("western_room", walls)
    for o in openings:
        assert o.dimensions["height"] > 0
        assert o.dimensions["width"] > 0


def test_industrial_hangar_has_hangar_opening():
    walls = _walls("industrial_hangar", 30.0, 12.0, 40.0)
    openings = get_opening_builder().build_openings("industrial_hangar", walls)
    large = [o for o in openings if o.element_type == "hangar_opening"]
    assert len(large) >= 1


def test_industrial_hangar_has_skylights():
    walls = _walls("industrial_hangar", 30.0, 12.0, 40.0)
    openings = get_opening_builder().build_openings("industrial_hangar", walls)
    skylights = [o for o in openings if o.element_type == "skylight"]
    assert len(skylights) >= 2


def test_sci_fi_corridor_sliding_doors():
    walls = _walls("sci_fi_corridor", 4.0, 3.0, 20.0)
    openings = get_opening_builder().build_openings("sci_fi_corridor", walls)
    sliding = [o for o in openings if o.element_type == "sliding_door"]
    assert len(sliding) == 2


def test_castle_hall_has_archway():
    walls = _walls("castle_hall", 20.0, 10.0, 30.0)
    openings = get_opening_builder().build_openings("castle_hall", walls)
    arches = [o for o in openings if o.element_type == "archway"]
    assert len(arches) >= 1


def test_dungeon_has_arrow_slits():
    walls = _walls("dungeon", 8.0, 3.0, 10.0)
    openings = get_opening_builder().build_openings("dungeon", walls)
    slits = [o for o in openings if o.element_type == "arrow_slit"]
    assert len(slits) >= 2


def test_is_opening_flag():
    walls = _walls()
    openings = get_opening_builder().build_openings("western_room", walls)
    for o in openings:
        assert o.is_opening is True
