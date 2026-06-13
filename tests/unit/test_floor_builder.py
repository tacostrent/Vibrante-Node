"""Tests for FloorBuilder — §49 Structural Environment Realization."""
import pytest
from src.runtime.environment_realization import (
    get_floor_builder, reset_floor_builder_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_floor_builder_for_tests()
    yield
    reset_floor_builder_for_tests()


def test_western_room_floor_material():
    f = get_floor_builder().build_floor("western_room", 10.0, 12.0)
    assert f.element_type == "floor"
    assert f.material == "wood"


def test_castle_hall_floor_stone():
    f = get_floor_builder().build_floor("castle_hall", 20.0, 30.0)
    assert f.material == "stone"


def test_robotics_lab_floor_concrete():
    f = get_floor_builder().build_floor("robotics_lab", 15.0, 20.0)
    assert f.material == "concrete"


def test_medical_lab_floor_tile():
    f = get_floor_builder().build_floor("medical_lab", 10.0, 12.0)
    assert f.material == "tile"


def test_hotel_lobby_floor_marble():
    f = get_floor_builder().build_floor("hotel_lobby", 20.0, 25.0)
    assert f.material == "marble"


def test_outdoor_forest_floor_dirt():
    f = get_floor_builder().build_floor("forest", 0.0, 0.0)
    assert f.material == "dirt"
    assert f.dimensions["width"] == pytest.approx(50.0)


def test_desert_floor_sand():
    f = get_floor_builder().build_floor("desert", 0.0, 0.0)
    assert f.material == "sand"


def test_floor_position_at_origin():
    f = get_floor_builder().build_floor("office", 10.0, 12.0)
    assert f.position == [0.0, 0.0, 0.0]


def test_floor_has_correct_dimensions():
    f = get_floor_builder().build_floor("warehouse", 20.0, 30.0)
    assert f.dimensions["width"] == pytest.approx(20.0)
    assert f.dimensions["depth"] == pytest.approx(30.0)


def test_floor_face_bottom():
    f = get_floor_builder().build_floor("western_room", 10.0, 12.0)
    assert f.face == "bottom"


def test_get_floor_material_helper():
    assert get_floor_builder().get_floor_material("western_room") == "wood"
    assert get_floor_builder().get_floor_material("castle_hall") == "stone"


def test_deterministic():
    f1 = get_floor_builder().build_floor("saloon", 14.0, 18.0)
    f2 = get_floor_builder().build_floor("saloon", 14.0, 18.0)
    assert f1.to_dict() == f2.to_dict()
