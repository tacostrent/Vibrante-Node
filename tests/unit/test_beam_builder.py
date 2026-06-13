"""Tests for BeamBuilder — §49 Structural Environment Realization."""
import pytest
from src.runtime.environment_realization import (
    get_beam_builder, reset_beam_builder_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_beam_builder_for_tests()
    yield
    reset_beam_builder_for_tests()


def test_western_room_wooden_beams():
    beams, cols = get_beam_builder().build_beams("western_room", 10.0, 4.0, 12.0)
    assert len(beams) == 4
    for b in beams:
        assert b.metadata["beam_type"] == "wooden_beam"
        assert b.material == "wood"


def test_industrial_hangar_steel_girders():
    beams, cols = get_beam_builder().build_beams("industrial_hangar", 30.0, 12.0, 40.0)
    assert len(beams) == 8
    assert len(cols) == 6
    for b in beams:
        assert b.material == "industrial_metal"


def test_sci_fi_corridor_panel_ribs():
    beams, cols = get_beam_builder().build_beams("sci_fi_corridor", 4.0, 3.0, 20.0)
    assert len(beams) == 8
    for b in beams:
        assert b.metadata["beam_type"] == "panel_rib"


def test_castle_hall_stone_arches():
    beams, cols = get_beam_builder().build_beams("castle_hall", 20.0, 10.0, 30.0)
    assert len(beams) == 4
    assert len(cols) == 8
    for b in beams:
        assert b.material == "stone"


def test_outdoor_forest_no_beams():
    beams, cols = get_beam_builder().build_beams("forest", 0.0, 0.0, 0.0)
    assert beams == []
    assert cols == []


def test_office_no_beams():
    beams, cols = get_beam_builder().build_beams("office", 10.0, 3.0, 12.0)
    assert beams == []


def test_beams_at_ceiling_level():
    """Beams should be near the ceiling height."""
    beams, _ = get_beam_builder().build_beams("western_room", 10.0, 4.0, 12.0)
    for b in beams:
        assert b.position[1] > 3.0, f"beam below mid-height: {b.position[1]}"


def test_columns_at_room_perimeter():
    """Columns should be near the room edge."""
    _, cols = get_beam_builder().build_beams("industrial_hangar", 30.0, 12.0, 40.0)
    for c in cols:
        assert abs(c.position[0]) > 10.0, f"column not near perimeter: {c.position[0]}"


def test_beam_element_type():
    beams, _ = get_beam_builder().build_beams("western_room", 10.0, 4.0, 12.0)
    for b in beams:
        assert b.element_type == "beam"


def test_column_element_type():
    _, cols = get_beam_builder().build_beams("industrial_hangar", 30.0, 12.0, 40.0)
    for c in cols:
        assert c.element_type == "column"


def test_deterministic():
    b1, c1 = get_beam_builder().build_beams("western_room", 10.0, 4.0, 12.0)
    b2, c2 = get_beam_builder().build_beams("western_room", 10.0, 4.0, 12.0)
    assert [b.to_dict() for b in b1] == [b.to_dict() for b in b2]
