"""Tests for TransformResolver — §47 Layout Realization."""
import math
import pytest
from src.runtime.layout_realization import (
    get_transform_resolver,
    reset_transform_resolver_for_tests,
    ResolvedTransform,
)


@pytest.fixture(autouse=True)
def reset():
    reset_transform_resolver_for_tests()
    yield
    reset_transform_resolver_for_tests()


def resolver():
    return get_transform_resolver()


# ---- resolve_anchor --------------------------------------------------------

def test_resolve_anchor_position():
    anchor = {"anchor_id": "table_01", "anchor_name": "Poker Table", "position": [1.5, 0.0, -2.0]}
    xf = resolver().resolve_anchor(anchor)
    assert xf.asset_id == "table_01"
    assert xf.tx == pytest.approx(1.5)
    assert xf.ty == pytest.approx(0.0)
    assert xf.tz == pytest.approx(-2.0)
    assert xf.relationship == "anchor"


def test_resolve_anchor_defaults():
    xf = resolver().resolve_anchor({"anchor_id": "a", "anchor_name": "a"})
    assert xf.tx == 0.0 and xf.ty == 0.0 and xf.tz == 0.0


# ---- resolve_cluster_member ------------------------------------------------

def test_resolve_cluster_member_relative_offset():
    member = {
        "asset_id": "chair_01", "asset_name": "Chair",
        "relative_position": [0.0, 0.0, 0.9],
        "orientation_deg": 180.0,
        "relationship": "around",
        "anchor_asset_id": "table_01",
    }
    anchor_pos = [1.0, 0.0, 2.0]
    xf = resolver().resolve_cluster_member(member, anchor_pos, cluster_id="c001")
    assert xf.tx == pytest.approx(1.0)
    assert xf.tz == pytest.approx(2.9)
    assert xf.ry == pytest.approx(180.0)
    assert xf.cluster_id == "c001"
    assert xf.relationship == "around"
    assert xf.parent_id == "table_01"


def test_resolve_cluster_member_surface():
    member = {
        "asset_id": "bottle_01", "asset_name": "Whiskey Bottle",
        "relative_position": [-0.25, 0.0, 0.15],
        "orientation_deg": 0.0,
        "relationship": "supports",
        "anchor_asset_id": "table_01",
    }
    xf = resolver().resolve_cluster_member(member, [0.0, 0.0, 0.0])
    assert xf.tz == pytest.approx(0.15)
    assert xf.relationship == "supports"


# ---- resolve_surface_placement ---------------------------------------------

def test_resolve_surface_placement_ty():
    sp = {
        "child_asset_id": "cup_01", "child_asset_name": "Cup",
        "host_asset_id": "table_01", "host_asset_name": "Table",
        "surface_type": "table_surface",
        "surface_height": 0.75,
        "position": [-0.3, 0.75, 0.0],
    }
    xf = resolver().resolve_surface_placement(sp)
    assert xf.ty == pytest.approx(0.75)
    assert xf.relationship == "supports"
    assert xf.parent_id == "table_01"


def test_resolve_surface_placement_notes_contain_surface():
    sp = {
        "child_asset_id": "b", "child_asset_name": "b",
        "host_asset_id": "h", "host_asset_name": "h",
        "surface_type": "bar_counter_surface",
        "surface_height": 1.05,
        "position": [0.0, 1.05, 0.0],
    }
    xf = resolver().resolve_surface_placement(sp)
    assert "bar_counter_surface" in xf.notes


# ---- resolve_wall_attachment -----------------------------------------------

def test_resolve_wall_attachment_north_wall_ry():
    att = {
        "asset_id": "poster_01", "asset_name": "Wanted Poster",
        "asset_type": "poster",
        "wall_name": "wall_north",
        "wall_normal": [0.0, 0.0, -1.0],
        "mount_height": 1.6,
        "position": [0.0, 1.6, -4.0],
        "ok": True,
    }
    xf = resolver().resolve_wall_attachment(att)
    assert xf.ty == pytest.approx(1.6)
    # north wall normal=[0,0,-1] → asset faces south (+Z) → ry≈0°
    assert xf.ry == pytest.approx(0.0, abs=5.0)
    assert xf.relationship == "attached_to"


def test_resolve_wall_attachment_east_wall_ry():
    att = {
        "asset_id": "lantern_01", "asset_name": "Lantern",
        "asset_type": "lantern",
        "wall_name": "wall_east",
        "wall_normal": [-1.0, 0.0, 0.0],
        "mount_height": 2.4,
        "position": [4.0, 2.4, 0.0],
        "ok": True,
    }
    xf = resolver().resolve_wall_attachment(att)
    assert abs(xf.ry - 90.0) < 5.0   # east wall → faces west ~90°


# ---- wall_normal_to_ry helper ----------------------------------------------

def test_wall_normal_all_four_walls():
    r = resolver()
    # north wall [0,0,-1] → faces south (+Z) → ry≈0°
    assert r._wall_normal_to_ry([0.0, 0.0, -1.0]) == pytest.approx(0.0, abs=5.0)
    # south wall [0,0,+1] → faces north (-Z) → ry≈180°
    assert r._wall_normal_to_ry([0.0, 0.0,  1.0]) == pytest.approx(180.0, abs=5.0)
    # east wall [-1,0,0] → faces west (-X) → ry≈90°
    assert abs(r._wall_normal_to_ry([-1.0, 0.0, 0.0]) - 90.0) < 5.0
    # west wall [+1,0,0] → faces east (+X) → ry≈270°
    assert abs(r._wall_normal_to_ry([ 1.0, 0.0, 0.0]) - 270.0) < 5.0


# ---- resolve_decoration ----------------------------------------------------

def test_resolve_decoration_floor_level():
    item = {"asset_id": "barrel_01", "asset_name": "Barrel",
            "position": [1.5, 0.0, -1.5], "placement_mode": "corner"}
    xf = resolver().resolve_decoration(item)
    assert xf.ty == pytest.approx(0.0)
    assert xf.tx == pytest.approx(1.5)
    assert xf.relationship == "corner"


# ---- determinism -----------------------------------------------------------

def test_deterministic_output():
    anchor = {"anchor_id": "t", "anchor_name": "t", "position": [3.0, 0.0, 1.0]}
    xf1 = resolver().resolve_anchor(anchor)
    xf2 = resolver().resolve_anchor(anchor)
    assert xf1.to_dict() == xf2.to_dict()
