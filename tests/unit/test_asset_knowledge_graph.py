"""
Tests for src.runtime.asset_knowledge_graph
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.asset_knowledge_graph import (
    AssetKnowledgeGraph,
    get_asset_knowledge_graph,
    reset_asset_knowledge_graph_for_tests,
    _VALID_REL_TYPES,
    _SEED_SCENE_ASSETS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_asset_knowledge_graph_for_tests()
    yield
    reset_asset_knowledge_graph_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_asset_knowledge_graph()
    b = get_asset_knowledge_graph()
    assert a is b


def test_reset_creates_new():
    a = get_asset_knowledge_graph()
    reset_asset_knowledge_graph_for_tests()
    b = get_asset_knowledge_graph()
    assert a is not b


# ---------------------------------------------------------------------------
# Built-in seed data
# ---------------------------------------------------------------------------

def test_seed_assets_populated():
    g = AssetKnowledgeGraph()
    stats = g.graph_statistics()
    assert stats["node_count"] > 0
    assert stats["edge_count"] > 0


def test_seed_industrial_hangar_assets():
    g = AssetKnowledgeGraph()
    assets = g.find_scene_assets("industrial_hangar")
    assert "industrial_pipe" in assets or "maintenance_robot" in assets


def test_seed_same_environment_relationships():
    g = AssetKnowledgeGraph()
    related = g.find_related_assets("industrial_pipe", rel_type="same_environment")
    related_ids = [r["asset_id"] for r in related]
    # industrial_pipe should be related to other industrial_hangar assets
    assert len(related_ids) > 0


def test_valid_rel_types():
    expected = {"commonly_used_with", "same_environment", "same_style",
                "same_template", "successful_pairing"}
    assert expected <= _VALID_REL_TYPES


# ---------------------------------------------------------------------------
# add_asset
# ---------------------------------------------------------------------------

def test_add_asset_new():
    g = AssetKnowledgeGraph()
    before = g.graph_statistics()["node_count"]
    g.add_asset("new_robot", "character", {"style": "industrial"})
    assert g.graph_statistics()["node_count"] == before + 1


def test_add_asset_updates_existing():
    g = AssetKnowledgeGraph()
    g.add_asset("update_test", "prop", {"color": "red"})
    g.add_asset("update_test", "character", {"color": "blue"})
    usage = g.get_asset_usage("update_test")
    assert usage["asset_type"] == "character"


def test_add_asset_no_metadata():
    g = AssetKnowledgeGraph()
    g.add_asset("bare_asset", "prop")
    usage = g.get_asset_usage("bare_asset")
    assert usage["found"] is True


# ---------------------------------------------------------------------------
# add_relationship
# ---------------------------------------------------------------------------

def test_add_relationship_bidirectional():
    g = AssetKnowledgeGraph()
    g.add_asset("a1", "prop")
    g.add_asset("a2", "prop")
    g.add_relationship("a1", "a2", "commonly_used_with", weight=2.0)
    # Both directions should be findable
    related_from_a1 = [r["asset_id"] for r in g.find_related_assets("a1")]
    related_from_a2 = [r["asset_id"] for r in g.find_related_assets("a2")]
    assert "a2" in related_from_a1
    assert "a1" in related_from_a2


def test_add_relationship_auto_creates_stubs():
    g = AssetKnowledgeGraph()
    g.add_relationship("new_a", "new_b", "same_style")
    assert g.get_asset_usage("new_a")["found"] is True
    assert g.get_asset_usage("new_b")["found"] is True


def test_add_relationship_self_raises():
    g = AssetKnowledgeGraph()
    with pytest.raises(ValueError):
        g.add_relationship("a", "a", "same_environment")


def test_add_relationship_invalid_type_raises():
    g = AssetKnowledgeGraph()
    with pytest.raises(ValueError):
        g.add_relationship("a", "b", "invalid_type_xyz")


def test_add_relationship_weight_stored():
    g = AssetKnowledgeGraph()
    g.add_relationship("x", "y", "successful_pairing", weight=3.5)
    related = g.find_related_assets("x")
    match = [r for r in related if r["asset_id"] == "y"]
    assert match[0]["weight"] == pytest.approx(3.5)


def test_add_all_valid_rel_types():
    g = AssetKnowledgeGraph()
    for rt in _VALID_REL_TYPES:
        g.add_relationship(f"src_{rt}", f"dst_{rt}", rt)


# ---------------------------------------------------------------------------
# remove_asset
# ---------------------------------------------------------------------------

def test_remove_asset():
    g = AssetKnowledgeGraph()
    g.add_asset("remove_me", "prop")
    g.remove_asset("remove_me")
    assert g.get_asset_usage("remove_me")["found"] is False


def test_remove_asset_cascades_edges():
    g = AssetKnowledgeGraph()
    g.add_asset("src_asset", "prop")
    g.add_asset("dst_asset", "prop")
    g.add_relationship("src_asset", "dst_asset", "commonly_used_with")
    g.remove_asset("src_asset")
    # dst_asset should have no relation to src_asset anymore
    related = [r["asset_id"] for r in g.find_related_assets("dst_asset")]
    assert "src_asset" not in related


def test_remove_nonexistent_asset_no_error():
    g = AssetKnowledgeGraph()
    g.remove_asset("does_not_exist")  # should not raise


# ---------------------------------------------------------------------------
# find_related_assets
# ---------------------------------------------------------------------------

def test_find_related_assets_returns_list():
    g = AssetKnowledgeGraph()
    result = g.find_related_assets("industrial_pipe")
    assert isinstance(result, list)


def test_find_related_assets_filter_by_rel_type():
    g = AssetKnowledgeGraph()
    g.add_asset("p1", "prop")
    g.add_asset("p2", "prop")
    g.add_asset("p3", "prop")
    g.add_relationship("p1", "p2", "commonly_used_with")
    g.add_relationship("p1", "p3", "same_style")
    commonly = g.find_related_assets("p1", rel_type="commonly_used_with")
    assert all(r["rel_type"] == "commonly_used_with" for r in commonly)


def test_find_related_assets_sorted_by_weight():
    g = AssetKnowledgeGraph()
    g.add_asset("s", "prop")
    g.add_asset("hi", "prop")
    g.add_asset("lo", "prop")
    g.add_relationship("s", "hi", "commonly_used_with", weight=5.0)
    g.add_relationship("s", "lo", "commonly_used_with", weight=1.0)
    related = g.find_related_assets("s")
    weights = [r["weight"] for r in related]
    assert weights == sorted(weights, reverse=True)


def test_find_related_assets_limit():
    g = AssetKnowledgeGraph()
    g.add_asset("hub", "prop")
    for i in range(20):
        g.add_asset(f"spoke_{i}", "prop")
        g.add_relationship("hub", f"spoke_{i}", "commonly_used_with")
    result = g.find_related_assets("hub", limit=5)
    assert len(result) == 5


def test_find_related_assets_unknown_id_returns_empty():
    g = AssetKnowledgeGraph()
    assert g.find_related_assets("nonexistent_xyz") == []


# ---------------------------------------------------------------------------
# find_scene_assets
# ---------------------------------------------------------------------------

def test_find_scene_assets_known_environment():
    g = AssetKnowledgeGraph()
    assets = g.find_scene_assets("robotics_lab")
    assert len(assets) > 0


def test_find_scene_assets_unknown_returns_empty():
    g = AssetKnowledgeGraph()
    assets = g.find_scene_assets("does_not_exist_env")
    assert assets == []


def test_find_scene_assets_returns_list():
    g = AssetKnowledgeGraph()
    assert isinstance(g.find_scene_assets("sci_fi_corridor"), list)


# ---------------------------------------------------------------------------
# get_asset_usage
# ---------------------------------------------------------------------------

def test_get_asset_usage_found():
    g = AssetKnowledgeGraph()
    usage = g.get_asset_usage("industrial_pipe")
    assert usage["found"] is True
    assert "asset_id" in usage
    assert "usage_count" in usage
    assert "relationship_count" in usage
    assert "rel_types" in usage
    assert "scene_types" in usage


def test_get_asset_usage_not_found():
    g = AssetKnowledgeGraph()
    usage = g.get_asset_usage("does_not_exist")
    assert usage["found"] is False


def test_record_asset_usage_increments():
    g = AssetKnowledgeGraph()
    g.add_asset("used_asset", "prop")
    g.record_asset_usage("used_asset")
    g.record_asset_usage("used_asset")
    usage = g.get_asset_usage("used_asset")
    assert usage["usage_count"] == 2


# ---------------------------------------------------------------------------
# graph_statistics
# ---------------------------------------------------------------------------

def test_graph_statistics_has_required_keys():
    g = AssetKnowledgeGraph()
    stats = g.graph_statistics()
    for key in ("node_count", "edge_count", "assets_by_type",
                "edges_by_rel_type", "scene_types_indexed"):
        assert key in stats, f"Missing key: {key}"


def test_graph_statistics_edge_count_positive():
    g = AssetKnowledgeGraph()
    assert g.graph_statistics()["edge_count"] > 0


def test_graph_statistics_scene_types_all_seeded():
    g = AssetKnowledgeGraph()
    stats = g.graph_statistics()
    assert stats["scene_types_indexed"] >= 5
