"""Tests for CeilingBuilder — §49 Structural Environment Realization."""
import pytest
from src.runtime.environment_realization import (
    get_ceiling_builder, reset_ceiling_builder_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_ceiling_builder_for_tests()
    yield
    reset_ceiling_builder_for_tests()


def test_western_room_beam_ceiling():
    c = get_ceiling_builder().build_ceiling("western_room", 10.0, 12.0, 4.0)
    assert c is not None
    assert c.metadata["ceiling_type"] == "beam_ceiling"


def test_industrial_hangar_ceiling_type():
    c = get_ceiling_builder().build_ceiling("industrial_hangar", 30.0, 40.0, 12.0)
    assert c.metadata["ceiling_type"] == "industrial_ceiling"


def test_castle_hall_vaulted():
    c = get_ceiling_builder().build_ceiling("castle_hall", 20.0, 30.0, 10.0)
    assert c.metadata["ceiling_type"] == "vaulted_ceiling"


def test_sci_fi_corridor_ceiling():
    c = get_ceiling_builder().build_ceiling("sci_fi_corridor", 4.0, 20.0, 3.0)
    assert c.metadata["ceiling_type"] == "sci_fi_ceiling"


def test_outdoor_forest_no_ceiling():
    c = get_ceiling_builder().build_ceiling("forest", 0.0, 0.0, 0.0)
    assert c is None


def test_outdoor_desert_no_ceiling():
    c = get_ceiling_builder().build_ceiling("desert", 0.0, 0.0, 0.0)
    assert c is None


def test_ceiling_position_at_height():
    c = get_ceiling_builder().build_ceiling("office", 10.0, 12.0, 3.0)
    assert c.position[1] == pytest.approx(3.0)


def test_ceiling_face_top():
    c = get_ceiling_builder().build_ceiling("western_room", 10.0, 12.0, 4.0)
    assert c.face == "top"


def test_ceiling_dimensions_match_room():
    c = get_ceiling_builder().build_ceiling("warehouse", 20.0, 30.0, 8.0)
    assert c.dimensions["width"] == pytest.approx(20.0)
    assert c.dimensions["depth"] == pytest.approx(30.0)


def test_is_outdoor_helper():
    assert get_ceiling_builder().is_outdoor("forest") is True
    assert get_ceiling_builder().is_outdoor("western_room") is False


def test_get_ceiling_type():
    assert get_ceiling_builder().get_ceiling_type("western_room") == "beam_ceiling"
    assert get_ceiling_builder().get_ceiling_type("castle_hall") == "vaulted_ceiling"
    assert get_ceiling_builder().get_ceiling_type("sci_fi_corridor") == "sci_fi_ceiling"
