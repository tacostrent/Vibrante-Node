"""
Tests for src.runtime.scene_layout_planner
No bridge, no LLM.  Pure unit tests.
"""
import pytest
from src.runtime.scene_layout_planner import (
    SceneLayoutPlanner,
    get_scene_layout_planner,
    reset_scene_layout_planner_for_tests,
    _HERO_CATEGORIES,
    _BACKGROUND_CATEGORIES,
    _CANONICAL_ZONES,
)
from src.runtime.environment_rules import reset_environment_rules_for_tests
from src.runtime.cinematic_composition import reset_cinematic_composition_engine_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_scene_layout_planner_for_tests()
    reset_environment_rules_for_tests()
    reset_cinematic_composition_engine_for_tests()
    yield
    reset_scene_layout_planner_for_tests()
    reset_environment_rules_for_tests()
    reset_cinematic_composition_engine_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_scene_layout_planner()
    b = get_scene_layout_planner()
    assert a is b


def test_reset_creates_new():
    a = get_scene_layout_planner()
    reset_scene_layout_planner_for_tests()
    b = get_scene_layout_planner()
    assert a is not b


# ---------------------------------------------------------------------------
# create_zones
# ---------------------------------------------------------------------------

def test_create_zones_always_has_canonical_zones():
    planner = SceneLayoutPlanner()
    zones = planner.create_zones("industrial_hangar")
    for zone in _CANONICAL_ZONES:
        assert zone in zones, f"Missing canonical zone: {zone}"


def test_create_zones_values_are_lists():
    planner = SceneLayoutPlanner()
    zones = planner.create_zones("robotics_lab")
    for name, assets in zones.items():
        assert isinstance(assets, list), f"Zone '{name}' is not a list"


def test_create_zones_unknown_theme_still_has_canonical():
    planner = SceneLayoutPlanner()
    zones = planner.create_zones("nonexistent_theme_xyz")
    for zone in _CANONICAL_ZONES:
        assert zone in zones


def test_create_zones_industrial_has_ceiling_layer():
    planner = SceneLayoutPlanner()
    zones = planner.create_zones("industrial_hangar")
    # industrial_hangar depth_layers includes "ceiling"
    assert "ceiling" in zones


# ---------------------------------------------------------------------------
# assign_hero_assets
# ---------------------------------------------------------------------------

def _base_zones():
    return {"hero_area": [], "midground": [], "background": []}


def test_assign_hero_by_category():
    planner = SceneLayoutPlanner()
    assets = [{"name": "big_mech", "category": "vehicle"}]
    zones = planner.assign_hero_assets(assets, _base_zones())
    assert any(a["name"] == "big_mech" for a in zones["hero_area"])


def test_assign_hero_by_is_hero_flag():
    planner = SceneLayoutPlanner()
    assets = [{"name": "special_asset", "category": "container", "is_hero": True}]
    zones = planner.assign_hero_assets(assets, _base_zones())
    assert any(a["name"] == "special_asset" for a in zones["hero_area"])


def test_assign_hero_by_priority():
    planner = SceneLayoutPlanner()
    assets = [{"name": "priority_asset", "category": "misc", "priority": 9}]
    zones = planner.assign_hero_assets(assets, _base_zones())
    assert any(a["name"] == "priority_asset" for a in zones["hero_area"])


def test_assign_hero_skips_low_priority():
    planner = SceneLayoutPlanner()
    assets = [{"name": "ordinary_prop", "category": "container", "priority": 3}]
    zones = planner.assign_hero_assets(assets, _base_zones())
    assert not any(a["name"] == "ordinary_prop" for a in zones["hero_area"])


def test_assign_hero_does_not_mutate_input_zones():
    planner = SceneLayoutPlanner()
    original = {"hero_area": [], "midground": [], "background": []}
    assets = [{"name": "robot1", "category": "robot"}]
    planner.assign_hero_assets(assets, original)
    assert original["hero_area"] == []


def test_assign_hero_no_duplicate_placement():
    planner = SceneLayoutPlanner()
    # asset already in hero_area — should not be added again
    zones = {
        "hero_area": [{"name": "already_here", "category": "robot"}],
        "midground": [],
        "background": [],
    }
    assets = [{"name": "already_here", "category": "robot"}]
    result = planner.assign_hero_assets(assets, zones)
    hero_names = [a["name"] for a in result["hero_area"]]
    assert hero_names.count("already_here") == 1


# ---------------------------------------------------------------------------
# assign_background_assets
# ---------------------------------------------------------------------------

def test_assign_background_category_goes_to_background():
    planner = SceneLayoutPlanner()
    assets = [{"name": "sky_dome", "category": "sky"}]
    zones = planner.assign_background_assets(assets, _base_zones())
    assert any(a["name"] == "sky_dome" for a in zones["background"])


def test_assign_non_bg_goes_to_midground_or_background():
    planner = SceneLayoutPlanner()
    assets = [
        {"name": "crate1",    "category": "container"},
        {"name": "crate2",    "category": "container"},
        {"name": "crate3",    "category": "container"},
        {"name": "crate4",    "category": "container"},
    ]
    zones = planner.assign_background_assets(assets, _base_zones())
    placed = len(zones["midground"]) + len(zones["background"])
    assert placed == 4


def test_assign_background_balances_mid_and_bg():
    planner = SceneLayoutPlanner()
    assets = [{"name": f"crate{i}", "category": "container"} for i in range(6)]
    zones = planner.assign_background_assets(assets, _base_zones())
    diff = abs(len(zones["midground"]) - len(zones["background"]))
    assert diff <= 1


def test_assign_background_does_not_mutate_input():
    planner = SceneLayoutPlanner()
    original = {"hero_area": [], "midground": [], "background": []}
    assets = [{"name": "terrain1", "category": "terrain"}]
    planner.assign_background_assets(assets, original)
    assert original["background"] == []


def test_assign_background_skips_already_assigned():
    planner = SceneLayoutPlanner()
    zones = {
        "hero_area": [{"name": "already_placed", "category": "vehicle"}],
        "midground": [],
        "background": [],
    }
    assets = [{"name": "already_placed", "category": "vehicle"},
              {"name": "new_asset", "category": "container"}]
    result = planner.assign_background_assets(assets, zones)
    all_placed = (
        [a["name"] for a in result["hero_area"]] +
        [a["name"] for a in result["midground"]] +
        [a["name"] for a in result["background"]]
    )
    assert all_placed.count("already_placed") == 1


# ---------------------------------------------------------------------------
# generate_layout_hierarchy
# ---------------------------------------------------------------------------

def _simple_plan():
    # depth_layers lists zones hero-first (as environment_rules does);
    # generate_layout_hierarchy reverses this to get back-to-front render order.
    return {
        "zones": {
            "hero_area":  [{"name": "h1"}],
            "midground":  [{"name": "m1"}],
            "background": [{"name": "b1"}],
        },
        "depth_layers": ["hero_area", "midground", "background"],
    }


def test_hierarchy_has_required_keys():
    planner = SceneLayoutPlanner()
    h = planner.generate_layout_hierarchy(_simple_plan())
    assert {"render_order", "zone_priorities", "focus_path"} <= set(h.keys())


def test_hierarchy_render_order_is_back_to_front():
    planner = SceneLayoutPlanner()
    h = planner.generate_layout_hierarchy(_simple_plan())
    ro = h["render_order"]
    # background should appear before hero_area (painter's algorithm)
    assert ro.index("background") < ro.index("hero_area")


def test_hierarchy_zone_priorities_hero_first():
    planner = SceneLayoutPlanner()
    h = planner.generate_layout_hierarchy(_simple_plan())
    prios = h["zone_priorities"]
    assert prios["hero_area"] < prios["midground"]
    assert prios["midground"] < prios["background"]


def test_hierarchy_focus_path_order():
    planner = SceneLayoutPlanner()
    h = planner.generate_layout_hierarchy(_simple_plan())
    fp = h["focus_path"]
    assert fp[0] == "hero_area"
    assert "midground" in fp
    assert "background" in fp


def test_hierarchy_no_duplicate_render_order():
    planner = SceneLayoutPlanner()
    h = planner.generate_layout_hierarchy(_simple_plan())
    assert len(h["render_order"]) == len(set(h["render_order"]))


# ---------------------------------------------------------------------------
# generate_layout_plan (integration)
# ---------------------------------------------------------------------------

def _mixed_assets():
    return [
        {"name": "main_robot",   "category": "robot"},
        {"name": "support_crate","category": "container"},
        {"name": "far_backdrop", "category": "structure"},
        {"name": "ground_plate", "category": "terrain"},
    ]


def test_generate_plan_has_required_keys():
    planner = SceneLayoutPlanner()
    plan = planner.generate_layout_plan("robotics_lab", _mixed_assets())
    required = {
        "plan_id", "scene_theme", "zones", "layout_rules",
        "asset_placements", "recommended_fx", "camera_hints",
        "depth_layers", "total_assets", "hierarchy",
        "composition_analysis", "generated_at",
    }
    assert required <= set(plan.keys())


def test_generate_plan_scene_theme_preserved():
    planner = SceneLayoutPlanner()
    plan = planner.generate_layout_plan("sci_fi_corridor", _mixed_assets())
    assert plan["scene_theme"] == "sci_fi_corridor"


def test_generate_plan_total_assets_correct():
    planner = SceneLayoutPlanner()
    assets = _mixed_assets()
    plan = planner.generate_layout_plan("industrial_hangar", assets)
    assert plan["total_assets"] == len(assets)


def test_generate_plan_all_assets_placed():
    planner = SceneLayoutPlanner()
    assets = _mixed_assets()
    plan = planner.generate_layout_plan("industrial_hangar", assets)
    placed_names = set()
    for zone_assets in plan["zones"].values():
        for a in zone_assets:
            placed_names.add(a["name"])
    for asset in assets:
        assert asset["name"] in placed_names, f"Asset '{asset['name']}' not placed"


def test_generate_plan_hero_asset_in_hero_zone():
    planner = SceneLayoutPlanner()
    assets = [{"name": "main_robot", "category": "robot"}]
    plan = planner.generate_layout_plan("robotics_lab", assets)
    hero_names = [a["name"] for a in plan["zones"]["hero_area"]]
    assert "main_robot" in hero_names


def test_generate_plan_layout_rules_populated():
    planner = SceneLayoutPlanner()
    plan = planner.generate_layout_plan("industrial_hangar", _mixed_assets())
    lr = plan["layout_rules"]
    assert "fog_density" in lr
    assert "lighting_style" in lr
    assert "hero_focus" in lr


def test_generate_plan_has_composition_analysis():
    planner = SceneLayoutPlanner()
    plan = planner.generate_layout_plan("robotics_lab", _mixed_assets())
    ca = plan["composition_analysis"]
    assert "readable" in ca
    assert "readability_score" in ca


def test_generate_plan_empty_assets():
    planner = SceneLayoutPlanner()
    plan = planner.generate_layout_plan("industrial_hangar", [])
    assert plan["total_assets"] == 0
    for zone_assets in plan["zones"].values():
        assert zone_assets == []


def test_generate_plan_increments_plan_count():
    planner = SceneLayoutPlanner()
    planner.generate_layout_plan("robotics_lab", _mixed_assets())
    planner.generate_layout_plan("robotics_lab", _mixed_assets())
    assert planner.stats()["plan_count"] == 2


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    planner = SceneLayoutPlanner()
    s = planner.stats()
    assert "plan_count" in s


def test_stats_starts_at_zero():
    planner = SceneLayoutPlanner()
    assert planner.stats()["plan_count"] == 0
