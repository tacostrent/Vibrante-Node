"""Tests for LayoutRealizationEngine — §47 Layout Realization."""
import pytest
from src.runtime.layout_realization import (
    get_layout_realization_engine,
    reset_layout_realization_engine_for_tests,
    get_cluster_realizer,
    reset_cluster_realizer_for_tests,
    get_surface_realizer,
    reset_surface_realizer_for_tests,
    get_wall_attachment_realizer,
    reset_wall_attachment_realizer_for_tests,
    get_collision_solver,
    reset_collision_solver_for_tests,
    get_scene_constraint_solver,
    reset_scene_constraint_solver_for_tests,
    get_transform_resolver,
    reset_transform_resolver_for_tests,
)


@pytest.fixture(autouse=True)
def reset_all():
    for fn in [
        reset_layout_realization_engine_for_tests,
        reset_cluster_realizer_for_tests,
        reset_surface_realizer_for_tests,
        reset_wall_attachment_realizer_for_tests,
        reset_collision_solver_for_tests,
        reset_scene_constraint_solver_for_tests,
        reset_transform_resolver_for_tests,
    ]:
        fn()
    yield
    for fn in [
        reset_layout_realization_engine_for_tests,
        reset_cluster_realizer_for_tests,
        reset_surface_realizer_for_tests,
        reset_wall_attachment_realizer_for_tests,
        reset_collision_solver_for_tests,
        reset_scene_constraint_solver_for_tests,
        reset_transform_resolver_for_tests,
    ]:
        fn()


def _western_room_plan():
    return {
        "plan_id": "plan_test_001",
        "environment": "western_room",
        "anchor_placements": [
            {"anchor_id": "poker_table", "anchor_name": "Poker Table",
             "anchor_type": "table", "zone": "hero_zone",
             "position": [0.0, 0.0, 0.0], "is_hero": True, "priority": 10},
            {"anchor_id": "bar_counter", "anchor_name": "Bar Counter",
             "anchor_type": "bar_counter", "zone": "support_zone",
             "position": [2.5, 0.0, 0.0], "is_hero": False, "priority": 9},
        ],
        "clusters": [
            {
                "cluster_id": "cluster_0001", "cluster_type": "saloon_table_cluster",
                "anchor_asset_id": "poker_table", "anchor_asset_name": "Poker Table",
                "anchor_asset_type": "table", "anchor_position": [0.0, 0.0, 0.0],
                "members": [
                    {"asset_id": "chair_s", "asset_name": "Chair South", "asset_type": "chair",
                     "relationship": "around", "relative_position": [0.0, 0.0, 0.9], "orientation_deg": 180.0},
                    {"asset_id": "chair_n", "asset_name": "Chair North", "asset_type": "chair",
                     "relationship": "around", "relative_position": [0.0, 0.0, -0.9], "orientation_deg": 0.0},
                    {"asset_id": "whiskey_bottle", "asset_name": "Whiskey Bottle", "asset_type": "bottle",
                     "relationship": "supports", "relative_position": [-0.25, 0.0, 0.15], "orientation_deg": 0.0},
                ],
            },
        ],
        "surface_placements": [
            {"child_asset_id": "whiskey_glass", "child_asset_name": "Whiskey Glass",
             "host_asset_id": "bar_counter", "host_asset_name": "Bar Counter",
             "surface_type": "bar_counter_surface", "surface_height": 1.05,
             "position": [2.5, 1.05, 0.0]},
        ],
        "wall_attachments": [
            {"asset_id": "wanted_poster", "asset_name": "Wanted Poster", "asset_type": "poster",
             "wall_name": "wall_north", "wall_normal": [0.0, 0.0, -1.0],
             "mount_height": 1.6, "position": [0.0, 1.6, -4.0], "ok": True},
            {"asset_id": "wall_lantern", "asset_name": "Lantern", "asset_type": "lantern",
             "wall_name": "wall_east", "wall_normal": [-1.0, 0.0, 0.0],
             "mount_height": 2.4, "position": [4.0, 2.4, 0.0], "ok": True},
        ],
        "decoration_items": [
            {"asset_id": "barrel_01", "asset_name": "Barrel", "asset_type": "barrel",
             "placement_mode": "corner", "placement_target": "corner",
             "position": [-2.5, 0.0, 2.5]},
        ],
        "review": None, "ok": True, "errors": [],
    }


# ---- core realization -------------------------------------------------------

def test_realize_produces_transforms():
    scene = get_layout_realization_engine().realize(_western_room_plan())
    assert scene.ok
    assert scene.asset_count > 0
    assert len(scene.transforms) == scene.asset_count


def test_chairs_not_at_origin():
    scene = get_layout_realization_engine().realize(_western_room_plan())
    chairs = [t for t in scene.transforms if "chair" in t.asset_id]
    assert len(chairs) == 2
    for ch in chairs:
        dist = (ch.tx ** 2 + ch.tz ** 2) ** 0.5
        assert dist > 0.5, f"chair {ch.asset_id} still at/near origin"


def test_whiskey_glass_on_bar_surface():
    scene = get_layout_realization_engine().realize(_western_room_plan())
    glass = next((t for t in scene.transforms if "glass" in t.asset_id), None)
    assert glass is not None
    assert glass.ty > 0.5, f"glass should be on bar surface, ty={glass.ty}"


def test_poster_on_wall():
    scene = get_layout_realization_engine().realize(_western_room_plan())
    poster = next((t for t in scene.transforms if "poster" in t.asset_id), None)
    assert poster is not None
    assert poster.ty == pytest.approx(1.6)
    assert abs(poster.tz) > 3.0, "poster should be near north wall"


def test_no_unresolved_collisions_western_room():
    scene = get_layout_realization_engine().realize(_western_room_plan())
    assert scene.collision_count == 0, (
        f"{scene.collision_count} unresolved collision(s) in realized scene"
    )


def test_production_ready_western_room():
    scene = get_layout_realization_engine().realize(_western_room_plan())
    assert scene.production_ready, (
        f"western_room not production ready: collisions={scene.collision_count} "
        f"constraints={scene.constraint_violations}"
    )


def test_empty_plan_no_crash():
    scene = get_layout_realization_engine().realize({})
    assert scene.ok or not scene.ok  # either is fine; just must not raise


def test_deterministic():
    plan = _western_room_plan()
    s1 = get_layout_realization_engine().realize(plan)
    s2 = get_layout_realization_engine().realize(plan)
    ids1 = sorted(t.asset_id for t in s1.transforms)
    ids2 = sorted(t.asset_id for t in s2.transforms)
    assert ids1 == ids2


def test_cluster_count_set():
    scene = get_layout_realization_engine().realize(_western_room_plan())
    assert scene.cluster_count == 1


def test_wall_attachment_count_set():
    scene = get_layout_realization_engine().realize(_western_room_plan())
    assert scene.wall_attachment_count == 2
