"""Tests for AssetClusteringEngine (Tier 9 — §29)."""
import pytest
from src.runtime.assets.assembly.asset_clustering_engine import (
    AssetCluster,
    ClusterPlan,
    AssetClusteringEngine,
    get_asset_clustering_engine,
    reset_asset_clustering_engine_for_tests,
    _CLUSTER_AFFINITIES,
    _CLUSTER_MAX,
)
from src.runtime.assets.assembly.environment_builder import (
    get_environment_builder,
    reset_environment_builder_for_tests,
)
from src.runtime.assets.assembly.placement_templates import reset_placement_templates_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_asset_clustering_engine_for_tests()
    reset_environment_builder_for_tests()
    reset_placement_templates_for_tests()
    yield
    reset_asset_clustering_engine_for_tests()
    reset_environment_builder_for_tests()
    reset_placement_templates_for_tests()


def _env_with_assets(cats):
    builder = get_environment_builder()
    recs = [{"asset": {"name": f"a_{i}", "category": c}} for i, c in enumerate(cats)]
    return builder.build_environment("industrial_hangar", recs)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_asset_clustering_engine() is get_asset_clustering_engine()


def test_reset():
    a = get_asset_clustering_engine()
    reset_asset_clustering_engine_for_tests()
    b = get_asset_clustering_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# build_clusters
# ---------------------------------------------------------------------------

def test_build_clusters_returns_plan():
    env_plan = _env_with_assets(["machinery", "robot"])
    plan     = get_asset_clustering_engine().build_clusters(env_plan)
    assert isinstance(plan, ClusterPlan)
    assert plan.ok


def test_build_clusters_empty_plan_ok():
    builder  = get_environment_builder()
    env_plan = builder.build_environment("industrial_hangar")  # no assets
    plan     = get_asset_clustering_engine().build_clusters(env_plan)
    assert plan.ok
    assert plan.total_members == 0


def test_build_clusters_machinery_goes_to_machinery_cluster():
    env_plan = _env_with_assets(["machinery", "machinery"])
    plan     = get_asset_clustering_engine().build_clusters(env_plan)
    mc = [c for c in plan.clusters if c.cluster_type == "machinery_cluster"]
    assert mc, "No machinery_cluster found"
    assert mc[0].member_count >= 1


def test_build_clusters_prop_goes_to_workstation():
    env_plan = _env_with_assets(["prop"])
    plan     = get_asset_clustering_engine().build_clusters(env_plan)
    # prop → workstation_cluster
    wc = [c for c in plan.clusters if c.cluster_type == "workstation_cluster"]
    assert wc


def test_build_clusters_total_members():
    cats     = ["machinery", "machinery", "electronic", "prop"]
    env_plan = _env_with_assets(cats)
    plan     = get_asset_clustering_engine().build_clusters(env_plan)
    assert plan.total_members == len(cats)


# ---------------------------------------------------------------------------
# assign_cluster_roles
# ---------------------------------------------------------------------------

def test_machinery_cluster_role_primary():
    env_plan = _env_with_assets(["machinery"])
    clusters = get_asset_clustering_engine().assign_cluster_roles(
        [{"rec": {}, "asset": {}, "zone_name": "hero_zone", "category": "machinery", "name": "m1"}],
        env_plan,
    )
    mc = [c for c in clusters if c.cluster_type == "machinery_cluster"]
    assert mc
    assert mc[0].role == "primary"


def test_pipe_cluster_role_detail():
    env_plan = _env_with_assets(["pipe"])
    clusters = get_asset_clustering_engine().assign_cluster_roles(
        [{"rec": {}, "asset": {}, "zone_name": "service_area", "category": "pipe", "name": "p1"}],
        env_plan,
    )
    pc = [c for c in clusters if c.cluster_type == "pipe_cluster"]
    assert pc
    assert pc[0].role == "detail"


def test_atmosphere_cluster_role():
    env_plan = _env_with_assets(["hdri"])
    clusters = get_asset_clustering_engine().assign_cluster_roles(
        [{"rec": {}, "asset": {}, "zone_name": "background", "category": "hdri", "name": "h1"}],
        env_plan,
    )
    ac = [c for c in clusters if c.cluster_type == "atmosphere_cluster"]
    assert ac
    assert ac[0].role == "atmosphere"


# ---------------------------------------------------------------------------
# calculate_cluster_density
# ---------------------------------------------------------------------------

def test_density_full():
    engine = get_asset_clustering_engine()
    members = [{}] * 3
    assert engine.calculate_cluster_density(members, 3) == 1.0


def test_density_half():
    engine = get_asset_clustering_engine()
    members = [{}] * 2
    assert abs(engine.calculate_cluster_density(members, 4) - 0.5) < 0.001


def test_density_over_max_clamped():
    engine = get_asset_clustering_engine()
    members = [{}] * 10
    assert engine.calculate_cluster_density(members, 3) == 1.0


def test_density_zero_max():
    engine = get_asset_clustering_engine()
    assert engine.calculate_cluster_density([], 0) == 0.0


# ---------------------------------------------------------------------------
# validate_cluster_balance
# ---------------------------------------------------------------------------

def test_balance_warns_no_primary():
    plan = ClusterPlan()
    plan.clusters = [AssetCluster("c1", "workstation_cluster", "support", "midground", max_members=3)]
    plan.clusters[0].members = [{}]
    result = get_asset_clustering_engine().validate_cluster_balance(plan)
    assert result["warnings"]
    assert any("primary" in w for w in result["warnings"])


def test_balance_ok_with_primary():
    plan = ClusterPlan()
    mc = AssetCluster("c1", "machinery_cluster", "primary", "hero_zone", max_members=3)
    mc.members = [{}, {}]
    plan.clusters = [mc]
    result = get_asset_clustering_engine().validate_cluster_balance(plan)
    assert not result["warnings"]


# ---------------------------------------------------------------------------
# Pipe cluster is linear
# ---------------------------------------------------------------------------

def test_pipe_cluster_is_linear():
    env_plan = _env_with_assets(["pipe", "pipe"])
    plan     = get_asset_clustering_engine().build_clusters(env_plan)
    pc = [c for c in plan.clusters if c.cluster_type == "pipe_cluster"]
    if pc:
        assert pc[0].is_linear


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

def test_cluster_round_trip():
    env_plan = _env_with_assets(["machinery", "electronic"])
    plan     = get_asset_clustering_engine().build_clusters(env_plan)
    d  = plan.to_dict()
    p2 = ClusterPlan.from_dict(d)
    assert p2.total_members == plan.total_members
    assert len(p2.clusters) == len(plan.clusters)
