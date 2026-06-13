"""Tests for §46 FurnitureClusterBuilder."""

import pytest
from src.runtime.layout import (
    ClusterMember,
    FurnitureCluster,
    ClusterBuildResult,
    get_furniture_cluster_builder,
    reset_furniture_cluster_builder_for_tests,
    reset_affordance_engine_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_furniture_cluster_builder_for_tests()
    reset_affordance_engine_for_tests()
    yield
    reset_furniture_cluster_builder_for_tests()
    reset_affordance_engine_for_tests()


def _asset(name, a_type):
    return {"asset_id": name, "name": name, "placement_type": a_type}


# ---------------------------------------------------------------------------
# Basic clustering
# ---------------------------------------------------------------------------

def test_table_becomes_cluster_root():
    assets = [
        _asset("hero_table", "table"),
        _asset("chair_01", "chair"),
        _asset("chair_02", "chair"),
    ]
    result = get_furniture_cluster_builder().build_clusters(assets, "western_room")
    assert result.ok
    assert len(result.clusters) == 1
    assert result.clusters[0].anchor_asset_type == "table"


def test_chairs_assigned_around_table():
    assets = [
        _asset("table_01", "table"),
        _asset("chair_01", "chair"),
        _asset("chair_02", "chair"),
        _asset("chair_03", "chair"),
        _asset("chair_04", "chair"),
    ]
    result = get_furniture_cluster_builder().build_clusters(assets, "western_room")
    cluster = result.clusters[0]
    around = [m for m in cluster.members if m.relationship == "around"]
    assert len(around) == 4


def test_bottle_placed_on_table_surface():
    assets = [
        _asset("table_01", "table"),
        _asset("bottle_01", "bottle"),
    ]
    result = get_furniture_cluster_builder().build_clusters(assets)
    cluster = result.clusters[0]
    surf = [m for m in cluster.members if m.relationship == "supports"]
    assert len(surf) == 1
    assert "bottle" in surf[0].asset_type


def test_saloon_cluster_type():
    assets = [_asset("t", "table")]
    result = get_furniture_cluster_builder().build_clusters(assets, "western_room")
    assert "saloon" in result.clusters[0].cluster_type


def test_bar_cluster_type():
    assets = [_asset("bar", "bar_counter")]
    result = get_furniture_cluster_builder().build_clusters(assets, "saloon")
    assert "bar" in result.clusters[0].cluster_type


def test_workbench_cluster_type():
    assets = [_asset("wb", "workbench")]
    result = get_furniture_cluster_builder().build_clusters(assets, "industrial_hangar")
    assert "workbench" in result.clusters[0].cluster_type


def test_unassigned_assets_returned():
    assets = [
        _asset("table_01", "table"),
        _asset("machine_01", "machine"),  # machine is an anchor, separate cluster
        _asset("rock_01", "rock"),        # unknown type, not an anchor
    ]
    result = get_furniture_cluster_builder().build_clusters(assets)
    # rock is not anchor and doesn't fit any cluster
    assert any(a.get("asset_id") == "rock_01" for a in result.unassigned)


def test_no_assets_returns_empty():
    result = get_furniture_cluster_builder().build_clusters([])
    assert result.ok
    assert len(result.clusters) == 0


def test_multiple_anchors_form_separate_clusters():
    assets = [
        _asset("table_01", "table"),
        _asset("workbench_01", "workbench"),
        _asset("chair_01", "chair"),
    ]
    result = get_furniture_cluster_builder().build_clusters(assets)
    assert len(result.clusters) == 2


# ---------------------------------------------------------------------------
# Chair orbit positions
# ---------------------------------------------------------------------------

def test_chairs_at_distinct_positions():
    assets = [
        _asset("table_01", "table"),
        _asset("c1", "chair"),
        _asset("c2", "chair"),
        _asset("c3", "chair"),
        _asset("c4", "chair"),
    ]
    result = get_furniture_cluster_builder().build_clusters(assets)
    cluster = result.clusters[0]
    positions = [tuple(m.relative_position) for m in cluster.members if m.relationship == "around"]
    assert len(set(positions)) == 4  # all distinct


def test_chairs_face_table():
    assets = [
        _asset("table_01", "table"),
        _asset("c1", "chair"),
    ]
    result = get_furniture_cluster_builder().build_clusters(assets)
    cluster = result.clusters[0]
    chairs = [m for m in cluster.members if m.relationship == "around"]
    assert chairs[0].orientation_deg in (0.0, 90.0, 180.0, 270.0)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_cluster_to_dict_from_dict_roundtrip():
    assets = [
        _asset("table_01", "table"),
        _asset("chair_01", "chair"),
        _asset("bottle_01", "bottle"),
    ]
    result = get_furniture_cluster_builder().build_clusters(assets, "western_room")
    cluster = result.clusters[0]
    d = cluster.to_dict()
    c2 = FurnitureCluster.from_dict(d)
    assert c2.anchor_asset_type == "table"
    assert len(c2.members) == len(cluster.members)


def test_cluster_build_result_to_dict():
    result = get_furniture_cluster_builder().build_clusters(
        [_asset("table_01", "table"), _asset("c", "chair")], "western_room"
    )
    d = result.to_dict()
    assert "clusters" in d
    assert "unassigned" in d
    assert d["ok"] is True
