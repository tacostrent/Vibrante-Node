"""Tests for §46 SurfacePlacementEngine."""

import pytest
from src.runtime.layout import (
    SurfacePlacement,
    SurfacePlacementResult,
    get_surface_placement_engine,
    reset_surface_placement_engine_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_surface_placement_engine_for_tests()
    yield
    reset_surface_placement_engine_for_tests()


def _table(asset_id="table_01"):
    return {"asset_id": asset_id, "name": "Wooden Table", "placement_type": "table"}


def _bottle(asset_id="bottle_01"):
    return {"asset_id": asset_id, "name": "Whiskey Bottle", "placement_type": "bottle"}


def _cup(asset_id="cup_01"):
    return {"asset_id": asset_id, "name": "Tin Cup", "placement_type": "cup"}


# ---------------------------------------------------------------------------
# Basic placement
# ---------------------------------------------------------------------------

def test_bottle_placed_above_table_surface():
    eng = get_surface_placement_engine()
    result = eng.place_on_surface(_table(), [_bottle()])
    assert result.ok
    assert len(result.placements) == 1
    sp = result.placements[0]
    assert sp.surface_height == pytest.approx(0.75, abs=0.01)
    # Y = host_y (0) + surface_height
    assert sp.position[1] == pytest.approx(0.75, abs=0.01)


def test_multiple_items_spread_across_surface():
    eng = get_surface_placement_engine()
    children = [_bottle(f"b{i}") for i in range(3)]
    result = eng.place_on_surface(_table(), children)
    assert len(result.placements) == 3
    xs = [p.position[0] for p in result.placements]
    # All X positions should be distinct
    assert len(set(round(x, 3) for x in xs)) == 3


def test_overflow_items_rejected_not_placed():
    eng = get_surface_placement_engine()
    children = [_bottle(f"b{i}") for i in range(20)]
    result = eng.place_on_surface(_table(), children)
    # Max items for table is 6
    assert len(result.placements) <= 6
    assert len(result.rejected) >= 14


def test_bar_counter_higher_surface():
    eng = get_surface_placement_engine()
    bar = {"asset_id": "bar_01", "name": "Bar Counter", "placement_type": "bar_counter"}
    result = eng.place_on_surface(bar, [_bottle()])
    assert result.surface_height == pytest.approx(1.05, abs=0.01)
    assert result.placements[0].position[1] == pytest.approx(1.05, abs=0.01)


def test_host_position_applied():
    eng = get_surface_placement_engine()
    host_pos = [3.0, 0.0, 2.0]
    result = eng.place_on_surface(_table(), [_bottle()], host_pos)
    p = result.placements[0]
    # Y should be host_y + surface_height
    assert p.position[1] == pytest.approx(host_pos[1] + 0.75, abs=0.01)
    # Z should match host Z
    assert p.position[2] == pytest.approx(host_pos[2], abs=0.01)


def test_empty_children_returns_empty_placements():
    eng = get_surface_placement_engine()
    result = eng.place_on_surface(_table(), [])
    assert result.ok
    assert len(result.placements) == 0


def test_surface_type_field():
    eng = get_surface_placement_engine()
    result = eng.place_on_surface(_table(), [_bottle()])
    assert "table" in result.surface_type


def test_get_surface_height():
    eng = get_surface_placement_engine()
    assert eng.get_surface_height("table") == pytest.approx(0.75)
    assert eng.get_surface_height("shelf") == pytest.approx(1.40)
    assert eng.get_surface_height("workbench") == pytest.approx(0.90)


def test_to_dict_from_dict_roundtrip():
    eng = get_surface_placement_engine()
    result = eng.place_on_surface(_table(), [_bottle()])
    sp = result.placements[0]
    d = sp.to_dict()
    sp2 = SurfacePlacement.from_dict(d)
    assert sp2.child_asset_id == sp.child_asset_id
    assert sp2.surface_height == pytest.approx(sp.surface_height)
