"""Tests for AssetPlacementEngine (Tier 9 — §29)."""
import pytest
from src.runtime.assets.assembly.asset_placement_engine import (
    AssetPlacement,
    PlacementPlan,
    AssetPlacementEngine,
    get_asset_placement_engine,
    reset_asset_placement_engine_for_tests,
    _CATEGORY_SCALES,
    _DEFAULT_SCALE,
)
from src.runtime.assets.assembly.environment_builder import (
    EnvironmentPlan,
    EnvironmentZone,
    get_environment_builder,
    reset_environment_builder_for_tests,
)
from src.runtime.assets.assembly.placement_templates import reset_placement_templates_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_asset_placement_engine_for_tests()
    reset_environment_builder_for_tests()
    reset_placement_templates_for_tests()
    yield
    reset_asset_placement_engine_for_tests()
    reset_environment_builder_for_tests()
    reset_placement_templates_for_tests()


def _populated_env_plan(environment="industrial_hangar", n_hero=2, n_mid=2):
    """Helper: build an env plan with assigned assets."""
    builder = get_environment_builder()
    recs = [{"asset": {"name": f"hero_{i}", "category": "machinery"}} for i in range(n_hero)]
    recs += [{"asset": {"name": f"mid_{i}", "category": "structure"}} for i in range(n_mid)]
    return builder.build_environment(environment, recs)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_asset_placement_engine()
    b = get_asset_placement_engine()
    assert a is b


def test_reset():
    a = get_asset_placement_engine()
    reset_asset_placement_engine_for_tests()
    b = get_asset_placement_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# generate_placement_plan
# ---------------------------------------------------------------------------

def test_placement_plan_ok():
    env_plan = _populated_env_plan()
    engine   = get_asset_placement_engine()
    plan     = engine.generate_placement_plan(env_plan)
    assert plan.ok
    assert isinstance(plan, PlacementPlan)


def test_placement_plan_environment_propagated():
    env_plan = _populated_env_plan("robotics_lab")
    engine   = get_asset_placement_engine()
    plan     = engine.generate_placement_plan(env_plan)
    assert plan.environment == "robotics_lab"


def test_placement_total_placed():
    env_plan = _populated_env_plan(n_hero=2, n_mid=2)
    engine   = get_asset_placement_engine()
    plan     = engine.generate_placement_plan(env_plan)
    assert plan.total_placed >= 2


def test_placement_placements_have_required_fields():
    env_plan = _populated_env_plan()
    engine   = get_asset_placement_engine()
    plan     = engine.generate_placement_plan(env_plan)
    for p in plan.placements:
        assert len(p.position) == 3
        assert len(p.rotation) == 3
        assert len(p.scale) == 3
        assert p.zone_name


def test_placement_deterministic():
    env_plan1 = _populated_env_plan()
    env_plan2 = _populated_env_plan()
    engine    = get_asset_placement_engine()
    plan1 = engine.generate_placement_plan(env_plan1)
    plan2 = engine.generate_placement_plan(env_plan2)
    pos1 = [p.position for p in plan1.placements]
    pos2 = [p.position for p in plan2.placements]
    assert pos1 == pos2


def test_placement_empty_env_plan_ok():
    env_plan = EnvironmentPlan(environment="industrial_hangar")
    zones_raw = get_environment_builder().build_environment_zones("industrial_hangar")
    env_plan.zones = zones_raw
    env_plan.zone_order = list(zones_raw.keys())
    engine = get_asset_placement_engine()
    plan   = engine.generate_placement_plan(env_plan)
    assert plan.ok
    assert plan.total_placed == 0


# ---------------------------------------------------------------------------
# assign_asset_positions
# ---------------------------------------------------------------------------

def test_assign_positions_returns_dict():
    env_plan = _populated_env_plan()
    engine   = get_asset_placement_engine()
    from src.runtime.assets.assembly.placement_templates import get_placement_templates
    tmpl  = get_placement_templates().get_template_or_default(env_plan.environment)
    pos   = engine.assign_asset_positions(env_plan, tmpl)
    assert isinstance(pos, dict)
    for key, coords in pos.items():
        assert len(coords) == 3


def test_assign_positions_background_deeper_than_hero():
    env_plan = _populated_env_plan(n_hero=1, n_mid=1)
    # Manually add a background asset
    bg_zone = env_plan.zones.get("background")
    if bg_zone:
        bg_zone.assigned_assets = [{"asset": {"name": "bg_asset", "category": "structure"}}]
    engine = get_asset_placement_engine()
    from src.runtime.assets.assembly.placement_templates import get_placement_templates
    tmpl = get_placement_templates().get_template_or_default(env_plan.environment)
    pos  = engine.assign_asset_positions(env_plan, tmpl)
    bg_keys  = [k for k in pos if k.startswith("background/")]
    hero_keys = [k for k in pos if k.startswith("hero_zone/")]
    if bg_keys and hero_keys:
        # Background Z should be more negative than hero Z
        bg_z   = pos[bg_keys[0]][2]
        hero_z = pos[hero_keys[0]][2]
        assert bg_z <= hero_z


# ---------------------------------------------------------------------------
# assign_asset_rotations
# ---------------------------------------------------------------------------

def test_assign_rotations_returns_dict():
    env_plan = _populated_env_plan()
    engine   = get_asset_placement_engine()
    from src.runtime.assets.assembly.placement_templates import get_placement_templates
    tmpl = get_placement_templates().get_template_or_default(env_plan.environment)
    rots = engine.assign_asset_rotations(env_plan, tmpl)
    assert isinstance(rots, dict)
    for key, rot in rots.items():
        assert len(rot) == 3
        rx, ry, rz = rot
        assert rx == 0.0
        assert rz == 0.0


# ---------------------------------------------------------------------------
# assign_asset_scales
# ---------------------------------------------------------------------------

def test_assign_scales_contains_all_categories():
    env_plan = _populated_env_plan()
    engine   = get_asset_placement_engine()
    scales   = engine.assign_asset_scales(env_plan)
    assert "machinery" in scales
    assert "structure" in scales


def test_category_scales_vehicle():
    assert _CATEGORY_SCALES["vehicle"] == 1.0


def test_default_scale_for_unknown_category():
    env_plan = EnvironmentPlan(environment="industrial_hangar")
    env_plan.zones = {"hero_zone": EnvironmentZone(
        zone_name="hero_zone", role="primary", categories=["unknown_cat"],
    )}
    engine = get_asset_placement_engine()
    scales = engine.assign_asset_scales(env_plan)
    assert scales.get("unknown_cat") == _DEFAULT_SCALE


# ---------------------------------------------------------------------------
# validate_spacing
# ---------------------------------------------------------------------------

def test_validate_spacing_no_duplicates():
    plan = PlacementPlan()
    plan.placements = [
        AssetPlacement("a1", "hero_zone", 0, (0.0, 0.0, 0.0), (0,0,0), (1,1,1)),
        AssetPlacement("a2", "hero_zone", 1, (4.0, 0.0, 0.0), (0,0,0), (1,1,1)),
    ]
    engine = get_asset_placement_engine()
    result = engine.validate_spacing(plan)
    assert not result["warnings"]


def test_validate_spacing_detects_duplicate():
    plan = PlacementPlan()
    plan.placements = [
        AssetPlacement("a1", "hero_zone", 0, (0.0, 0.0, 0.0), (0,0,0), (1,1,1)),
        AssetPlacement("a2", "hero_zone", 1, (0.0, 0.0, 0.0), (0,0,0), (1,1,1)),  # same pos
    ]
    engine = get_asset_placement_engine()
    result = engine.validate_spacing(plan)
    assert result["warnings"]


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

def test_placement_round_trip():
    env_plan = _populated_env_plan()
    engine   = get_asset_placement_engine()
    plan     = engine.generate_placement_plan(env_plan)
    d  = plan.to_dict()
    p2 = PlacementPlan.from_dict(d)
    assert p2.total_placed == plan.total_placed
    assert len(p2.placements) == len(plan.placements)
