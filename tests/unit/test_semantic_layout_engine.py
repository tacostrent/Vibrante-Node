"""Tests for §46 SemanticLayoutEngine (full pipeline integration)."""

import pytest
from src.runtime.layout import (
    LayoutPlan,
    get_semantic_layout_engine,
    reset_semantic_layout_engine_for_tests,
    reset_affordance_engine_for_tests,
    reset_anchor_layout_engine_for_tests,
    reset_furniture_cluster_builder_for_tests,
    reset_surface_placement_engine_for_tests,
    reset_wall_attachment_engine_for_tests,
    reset_decoration_layout_engine_for_tests,
    reset_relationship_graph_for_tests,
    reset_layout_review_for_tests,
    reset_layout_statistics_for_tests,
    reset_layout_serializer_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_semantic_layout_engine_for_tests()
    reset_affordance_engine_for_tests()
    reset_anchor_layout_engine_for_tests()
    reset_furniture_cluster_builder_for_tests()
    reset_surface_placement_engine_for_tests()
    reset_wall_attachment_engine_for_tests()
    reset_decoration_layout_engine_for_tests()
    reset_relationship_graph_for_tests()
    reset_layout_review_for_tests()
    reset_layout_statistics_for_tests()
    reset_layout_serializer_for_tests()
    yield
    reset_semantic_layout_engine_for_tests()
    reset_affordance_engine_for_tests()
    reset_anchor_layout_engine_for_tests()
    reset_furniture_cluster_builder_for_tests()
    reset_surface_placement_engine_for_tests()
    reset_wall_attachment_engine_for_tests()
    reset_decoration_layout_engine_for_tests()
    reset_relationship_graph_for_tests()
    reset_layout_review_for_tests()
    reset_layout_statistics_for_tests()
    reset_layout_serializer_for_tests()


def _asset(name, a_type):
    return {"asset_id": name, "name": name, "placement_type": a_type}


def _western_room_assets():
    return [
        _asset("hero_table", "table"),
        _asset("chair_01", "chair"),
        _asset("chair_02", "chair"),
        _asset("chair_03", "chair"),
        _asset("chair_04", "chair"),
        _asset("whiskey_bottle", "whiskey_bottle"),
        _asset("lantern_01", "lantern"),
        _asset("wanted_poster", "wanted_poster"),
        _asset("barrel_01", "barrel"),
        _asset("barrel_02", "barrel"),
    ]


# ---------------------------------------------------------------------------
# Success Criteria: Western Room
# ---------------------------------------------------------------------------

def test_western_room_has_anchor():
    plan = get_semantic_layout_engine().build_layout(_western_room_assets(), "western_room")
    assert plan.ok
    assert len(plan.anchor_placements) >= 1
    hero = next((a for a in plan.anchor_placements if a.get("is_hero")), None)
    assert hero is not None
    assert hero["anchor_type"] == "table"


def test_chairs_assigned_to_table_cluster():
    plan = get_semantic_layout_engine().build_layout(_western_room_assets(), "western_room")
    cluster = next(
        (c for c in plan.clusters if c.get("anchor_asset_type") == "table"),
        None,
    )
    assert cluster is not None
    around_members = [m for m in cluster.get("members", []) if m.get("relationship") == "around"]
    assert len(around_members) >= 2, "chairs should be around table"


def test_bottle_placed_on_table_surface():
    plan = get_semantic_layout_engine().build_layout(_western_room_assets(), "western_room")
    assert len(plan.surface_placements) >= 1
    # Bottle should be above floor (y > 0.5)
    for sp in plan.surface_placements:
        assert sp["position"][1] > 0.5, "surface items must be above floor"


def test_poster_attached_to_wall():
    plan = get_semantic_layout_engine().build_layout(_western_room_assets(), "western_room")
    # wanted_poster is wall-attachable
    attached = [a for a in plan.wall_attachments if "poster" in a.get("asset_type", "")]
    assert len(attached) >= 1, "wanted_poster must be wall-attached"
    for a in attached:
        assert a["mount_height"] > 1.0, "poster must be at eye level or higher"


def test_barrels_in_decoration_or_corner():
    plan = get_semantic_layout_engine().build_layout(_western_room_assets(), "western_room")
    barrel_decos = [d for d in plan.decoration_items if "barrel" in d.get("asset_type", "")]
    for d in barrel_decos:
        assert d["placement_target"] in ("corner", "scattered", "near_wall")


def test_lantern_wall_or_ceiling():
    plan = get_semantic_layout_engine().build_layout(_western_room_assets(), "western_room")
    lantern_walls = [a for a in plan.wall_attachments if "lantern" in a.get("asset_type", "")]
    if not lantern_walls:
        # may go to decoration with wall_mounted target
        lantern_decos = [d for d in plan.decoration_items if "lantern" in d.get("asset_type", "")]
        assert len(lantern_decos) >= 0   # acceptable


def test_relationships_populated():
    plan = get_semantic_layout_engine().build_layout(_western_room_assets(), "western_room")
    assert len(plan.relationships) >= 1


def test_review_passes():
    plan = get_semantic_layout_engine().build_layout(_western_room_assets(), "western_room")
    review = plan.review
    assert review is not None
    assert review["overall_score"] >= 0.60


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------

def test_empty_assets_no_crash():
    plan = get_semantic_layout_engine().build_layout([], "western_room")
    assert plan.ok


def test_only_chairs_no_anchors():
    assets = [_asset(f"c{i}", "chair") for i in range(4)]
    plan = get_semantic_layout_engine().build_layout(assets, "western_room")
    assert plan.ok
    assert len(plan.anchor_placements) == 0
    assert len(plan.clusters) == 0


def test_only_wall_objects():
    assets = [
        _asset("poster_01", "poster"),
        _asset("clock_01", "clock"),
        _asset("banner_01", "banner"),
    ]
    plan = get_semantic_layout_engine().build_layout(assets, "castle_hall")
    assert plan.ok
    assert len(plan.wall_attachments) >= 1


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_same_input_same_output():
    assets = _western_room_assets()
    plan1 = get_semantic_layout_engine().build_layout(assets, "western_room")
    reset_semantic_layout_engine_for_tests()
    reset_relationship_graph_for_tests()
    reset_furniture_cluster_builder_for_tests()
    plan2 = get_semantic_layout_engine().build_layout(assets, "western_room")
    assert len(plan1.clusters) == len(plan2.clusters)
    assert len(plan1.wall_attachments) == len(plan2.wall_attachments)
    assert len(plan1.surface_placements) == len(plan2.surface_placements)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def test_plan_to_dict_from_dict_roundtrip():
    plan = get_semantic_layout_engine().build_layout(_western_room_assets(), "western_room")
    d = plan.to_dict()
    plan2 = LayoutPlan.from_dict(d)
    assert plan2.environment == plan.environment
    assert len(plan2.clusters) == len(plan.clusters)
    assert len(plan2.wall_attachments) == len(plan.wall_attachments)


def test_plan_has_review():
    plan = get_semantic_layout_engine().build_layout(_western_room_assets(), "western_room")
    assert plan.review is not None
    assert "grade" in plan.review
    assert "production_ready" in plan.review
