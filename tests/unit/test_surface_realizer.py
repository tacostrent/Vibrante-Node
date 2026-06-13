"""Tests for SurfaceRealizer — §47 Layout Realization."""
import pytest
from src.runtime.layout_realization import (
    get_surface_realizer,
    reset_surface_realizer_for_tests,
    ResolvedTransform,
)


@pytest.fixture(autouse=True)
def reset():
    reset_surface_realizer_for_tests()
    yield
    reset_surface_realizer_for_tests()


def _anchor_xf(asset_id="table_01", tx=0.0, ty=0.0, tz=0.0):
    return ResolvedTransform(asset_id=asset_id, asset_name=asset_id,
                             tx=tx, ty=ty, tz=tz)


# ---- bottle on table -------------------------------------------------------

def test_bottle_ty_above_floor():
    sp = [{
        "child_asset_id": "bottle_01", "child_asset_name": "Whiskey Bottle",
        "host_asset_id": "table_01", "host_asset_name": "Poker Table",
        "surface_type": "table_surface", "surface_height": 0.75,
        "position": [-0.3, 0.75, 0.0],
    }]
    anchor_xfs = {"table_01": _anchor_xf("table_01")}
    results = get_surface_realizer().realize_surface_placements(sp, anchor_xfs)
    assert len(results) == 1
    assert results[0].ty > 0.5, f"bottle should be above floor, got ty={results[0].ty}"


def test_bottle_not_on_floor():
    """The core fix: bottle must NOT be at ty=0."""
    sp = [{
        "child_asset_id": "b", "child_asset_name": "whiskey bottle",
        "host_asset_id": "table_01", "host_asset_name": "Poker Table",
        "surface_type": "table_surface", "surface_height": 0.75,
        "position": [0.0, 0.75, 0.0],
    }]
    results = get_surface_realizer().realize_surface_placements(
        sp, {"table_01": _anchor_xf("table_01")}
    )
    assert results[0].ty != pytest.approx(0.0)


def test_bar_counter_surface_height():
    sp = [{
        "child_asset_id": "cup_01", "child_asset_name": "Cup",
        "host_asset_id": "bar_01", "host_asset_name": "Bar Counter",
        "surface_type": "bar_counter_surface", "surface_height": 1.05,
        "position": [0.0, 1.05, 0.0],
    }]
    results = get_surface_realizer().realize_surface_placements(
        sp, {"bar_01": _anchor_xf("bar_01")}
    )
    assert results[0].ty >= 1.05


def test_relationship_is_supports():
    sp = [{
        "child_asset_id": "c", "child_asset_name": "Cup",
        "host_asset_id": "t", "host_asset_name": "Table",
        "surface_type": "table_surface", "surface_height": 0.75,
        "position": [0.0, 0.75, 0.0],
    }]
    results = get_surface_realizer().realize_surface_placements(sp, {"t": _anchor_xf("t")})
    assert results[0].relationship == "supports"


def test_parent_id_set_to_host():
    sp = [{
        "child_asset_id": "c", "child_asset_name": "c",
        "host_asset_id": "mytable", "host_asset_name": "My Table",
        "surface_type": "table_surface", "surface_height": 0.75,
        "position": [0.0, 0.75, 0.0],
    }]
    results = get_surface_realizer().realize_surface_placements(
        sp, {"mytable": _anchor_xf("mytable")}
    )
    assert results[0].parent_id == "mytable"


def test_multiple_items_spread_horizontally():
    sp = [
        {"child_asset_id": f"item_{i}", "child_asset_name": f"Item {i}",
         "host_asset_id": "table_01", "host_asset_name": "Table",
         "surface_type": "table_surface", "surface_height": 0.75,
         "position": [0.0, 0.75, 0.0]}
        for i in range(4)
    ]
    results = get_surface_realizer().realize_surface_placements(
        sp, {"table_01": _anchor_xf("table_01")}
    )
    assert len(results) == 4
    tx_values = [r.tx for r in results]
    # At least two different X positions
    assert len(set(round(x, 3) for x in tx_values)) > 1


def test_no_host_transform_no_crash():
    """Missing anchor entry → graceful fallback to origin."""
    sp = [{
        "child_asset_id": "c", "child_asset_name": "c",
        "host_asset_id": "missing_host", "host_asset_name": "Missing",
        "surface_type": "table_surface", "surface_height": 0.75,
        "position": [0.0, 0.75, 0.0],
    }]
    results = get_surface_realizer().realize_surface_placements(sp, {})
    assert len(results) == 1   # still emits a transform


def test_get_surface_height():
    r = get_surface_realizer()
    assert r.get_surface_height("table") == pytest.approx(0.75)
    assert r.get_surface_height("bar_counter") == pytest.approx(1.05)
    assert r.get_surface_height("shelf") == pytest.approx(1.40)
