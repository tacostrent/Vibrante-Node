"""Tests for RelationshipRealizer — §47 Layout Realization."""
import pytest
from src.runtime.layout_realization import (
    get_relationship_realizer,
    reset_relationship_realizer_for_tests,
    ResolvedTransform,
)


@pytest.fixture(autouse=True)
def reset():
    reset_relationship_realizer_for_tests()
    yield
    reset_relationship_realizer_for_tests()


def _table_xf(tx=0.0, ty=0.0, tz=0.0):
    return ResolvedTransform(asset_id="table_01", asset_name="Poker Table",
                             tx=tx, ty=ty, tz=tz)


# ---- around ----------------------------------------------------------------

def test_chair_around_table_offset():
    relationships = [{"from_asset_id": "chair_01", "to_asset_id": "table_01",
                      "relationship_type": "around"}]
    anchor_xfs = {"table_01": _table_xf()}
    result = get_relationship_realizer().realize_relationships(
        relationships, anchor_xfs, {"table_01": "table"}
    )
    r = result.realizations[0]
    assert r.relationship_type == "around"
    # Should be ~0.9m from table origin on X or Z axis
    pos = r.world_position
    dist = (pos[0] ** 2 + pos[2] ** 2) ** 0.5
    assert dist == pytest.approx(0.9, abs=0.05)


def test_multiple_chairs_different_slots():
    relationships = [
        {"from_asset_id": f"chair_{i}", "to_asset_id": "table_01", "relationship_type": "around"}
        for i in range(4)
    ]
    anchor_xfs = {"table_01": _table_xf()}
    result = get_relationship_realizer().realize_relationships(
        relationships, anchor_xfs, {}
    )
    positions = set(tuple(round(v, 3) for v in r.world_position) for r in result.realizations)
    assert len(positions) == 4, "Four chairs should land at four distinct positions"


# ---- supports (surface) ----------------------------------------------------

def test_bottle_supports_table_ty():
    relationships = [{"from_asset_id": "bottle_01", "to_asset_id": "table_01",
                      "relationship_type": "supports"}]
    anchor_xfs = {"table_01": _table_xf()}
    result = get_relationship_realizer().realize_relationships(
        relationships, anchor_xfs, {"table_01": "table"}
    )
    r = result.realizations[0]
    assert r.world_position[1] == pytest.approx(0.75)  # table surface height


def test_bar_counter_surface_height():
    relationships = [{"from_asset_id": "glass_01", "to_asset_id": "bar_01",
                      "relationship_type": "supports"}]
    bar_xf = ResolvedTransform(asset_id="bar_01", asset_name="Bar", tx=0.0, ty=0.0, tz=0.0)
    result = get_relationship_realizer().realize_relationships(
        relationships, {"bar_01": bar_xf}, {"bar_01": "bar_counter"}
    )
    assert result.realizations[0].world_position[1] == pytest.approx(1.05)


# ---- attached_to (wall) ----------------------------------------------------

def test_poster_attached_to_wall():
    relationships = [{"from_asset_id": "poster_01", "to_asset_id": "wall",
                      "relationship_type": "attached_to"}]
    result = get_relationship_realizer().realize_relationships(relationships, {}, {})
    r = result.realizations[0]
    assert r.relationship_type == "attached_to"


# ---- hanging_from ----------------------------------------------------------

def test_lantern_hanging_from_ceiling():
    relationships = [{"from_asset_id": "lantern_01", "to_asset_id": "ceiling",
                      "relationship_type": "hanging_from"}]
    ceil_xf = ResolvedTransform(asset_id="ceiling", asset_name="ceiling", tx=0.0, ty=3.0, tz=0.0)
    result = get_relationship_realizer().realize_relationships(
        relationships, {"ceiling": ceil_xf}, {}
    )
    r = result.realizations[0]
    assert r.world_position[1] < 3.0  # hanging below ceiling


# ---- never raises ----------------------------------------------------------

def test_empty_relationships_ok():
    result = get_relationship_realizer().realize_relationships([], {}, {})
    assert result.ok
    assert result.realizations == []


def test_missing_anchor_no_crash():
    relationships = [{"from_asset_id": "x", "to_asset_id": "nonexistent", "relationship_type": "around"}]
    result = get_relationship_realizer().realize_relationships(relationships, {}, {})
    assert result.ok  # falls back to origin
