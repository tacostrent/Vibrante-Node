"""Tests for ClusterRealizer — §47 Layout Realization."""
import pytest
from src.runtime.layout_realization import (
    get_cluster_realizer,
    reset_cluster_realizer_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_cluster_realizer_for_tests()
    yield
    reset_cluster_realizer_for_tests()


def _saloon_cluster():
    return {
        "cluster_id":        "cluster_0001",
        "cluster_type":      "saloon_table_cluster",
        "anchor_asset_id":   "poker_table",
        "anchor_asset_name": "Poker Table",
        "anchor_asset_type": "table",
        "anchor_position":   [0.0, 0.0, 0.0],
        "members": [
            {"asset_id": "chair_s", "asset_name": "Chair South", "asset_type": "chair",
             "relationship": "around", "relative_position": [0.0, 0.0, 0.9], "orientation_deg": 180.0},
            {"asset_id": "chair_n", "asset_name": "Chair North", "asset_type": "chair",
             "relationship": "around", "relative_position": [0.0, 0.0, -0.9], "orientation_deg": 0.0},
            {"asset_id": "bottle_01", "asset_name": "Whiskey Bottle", "asset_type": "bottle",
             "relationship": "supports", "relative_position": [-0.25, 0.0, 0.15], "orientation_deg": 0.0},
        ],
    }


def test_anchor_gets_world_position():
    cluster = _saloon_cluster()
    result = get_cluster_realizer().realize_cluster(cluster, anchor_world_pos=[2.0, 0.0, -1.0])
    a = result.anchor_transform
    assert a is not None
    assert a.tx == pytest.approx(2.0)
    assert a.tz == pytest.approx(-1.0)
    assert a.relationship == "anchor"


def test_chairs_orbit_around_table():
    cluster = _saloon_cluster()
    result = get_cluster_realizer().realize_cluster(cluster, anchor_world_pos=[0.0, 0.0, 0.0])
    chairs = [m for m in result.member_transforms if "chair" in m.asset_name.lower()]
    assert len(chairs) == 2
    for ch in chairs:
        # Chair should be 0.9 m from origin on X or Z axis
        dist = (ch.tx ** 2 + ch.tz ** 2) ** 0.5
        assert dist == pytest.approx(0.9, abs=0.05)


def test_chairs_face_table_center():
    cluster = _saloon_cluster()
    result = get_cluster_realizer().realize_cluster(cluster, anchor_world_pos=[0.0, 0.0, 0.0])
    south_chair = next(m for m in result.member_transforms if m.asset_id == "chair_s")
    assert south_chair.ry == pytest.approx(180.0)


def test_bottle_on_tabletop_y():
    """Bottle relative_position y=0 → same level as anchor (height handled by surface realizer)."""
    cluster = _saloon_cluster()
    result = get_cluster_realizer().realize_cluster(cluster, anchor_world_pos=[0.0, 0.0, 0.0])
    bottle = next(m for m in result.member_transforms if "bottle" in m.asset_id)
    # relative y is 0.0 for cluster member (surface height not yet applied here)
    assert bottle.ty == pytest.approx(0.0)
    assert bottle.relationship == "supports"


def test_all_transforms_have_cluster_id():
    cluster = _saloon_cluster()
    result = get_cluster_realizer().realize_cluster(cluster)
    for xf in result.all_transforms():
        assert xf.cluster_id == "cluster_0001"


def test_realize_all_clusters():
    cluster = _saloon_cluster()
    anchor_pos_map = {"poker_table": [1.0, 0.0, 1.0]}
    results = get_cluster_realizer().realize_all_clusters([cluster], anchor_pos_map)
    assert len(results) == 1
    assert results[0].anchor_transform.tx == pytest.approx(1.0)


def test_anchor_fallback_to_cluster_position():
    """No anchor_world_pos supplied → use cluster anchor_position."""
    cluster = _saloon_cluster()
    cluster["anchor_position"] = [5.0, 0.0, 3.0]
    result = get_cluster_realizer().realize_cluster(cluster, anchor_world_pos=None)
    assert result.anchor_transform.tx == pytest.approx(5.0)


def test_empty_cluster_no_crash():
    cluster = {
        "cluster_id": "c", "cluster_type": "t",
        "anchor_asset_id": "a", "anchor_asset_name": "a", "anchor_asset_type": "table",
        "anchor_position": [0.0, 0.0, 0.0], "members": [],
    }
    result = get_cluster_realizer().realize_cluster(cluster)
    assert result.ok
    assert result.member_transforms == []


def test_deterministic():
    cluster = _saloon_cluster()
    r1 = get_cluster_realizer().realize_cluster(cluster, [0.0, 0.0, 0.0])
    r2 = get_cluster_realizer().realize_cluster(cluster, [0.0, 0.0, 0.0])
    for a, b in zip(r1.all_transforms(), r2.all_transforms()):
        assert a.to_dict() == b.to_dict()
