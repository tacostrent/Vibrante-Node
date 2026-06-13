"""Tests for EnvironmentBuilder (Tier 9 — §29)."""
import pytest
from src.runtime.assets.assembly.environment_builder import (
    EnvironmentBuilder,
    EnvironmentPlan,
    EnvironmentZone,
    get_environment_builder,
    reset_environment_builder_for_tests,
    _ENV_ZONE_CATEGORIES,
    _DEFAULT_ENV,
)
from src.runtime.assets.assembly.placement_templates import reset_placement_templates_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_environment_builder_for_tests()
    reset_placement_templates_for_tests()
    yield
    reset_environment_builder_for_tests()
    reset_placement_templates_for_tests()


def _make_recs(n=2, category="machinery"):
    return [{"asset": {"name": f"asset_{i}", "category": category}} for i in range(n)]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_environment_builder()
    b = get_environment_builder()
    assert a is b


def test_reset_returns_new_instance():
    a = get_environment_builder()
    reset_environment_builder_for_tests()
    b = get_environment_builder()
    assert a is not b


# ---------------------------------------------------------------------------
# build_environment
# ---------------------------------------------------------------------------

def test_build_environment_returns_plan():
    b = get_environment_builder()
    plan = b.build_environment("industrial_hangar")
    assert isinstance(plan, EnvironmentPlan)
    assert plan.ok
    assert plan.environment == "industrial_hangar"


def test_build_environment_has_hero_zone():
    b = get_environment_builder()
    plan = b.build_environment("industrial_hangar")
    assert plan.has_hero_zone
    assert "hero_zone" in plan.zones


def test_build_environment_five_envs():
    b = get_environment_builder()
    for env in _ENV_ZONE_CATEGORIES:
        plan = b.build_environment(env)
        assert plan.ok, f"{env} failed: {plan.errors}"
        assert plan.has_hero_zone


def test_build_environment_unknown_falls_back():
    b = get_environment_builder()
    plan = b.build_environment("mystery_place")
    assert plan.ok
    assert any("industrial_hangar" in w for w in plan.warnings)


def test_build_environment_total_capacity_positive():
    b = get_environment_builder()
    plan = b.build_environment("industrial_hangar")
    assert plan.total_capacity > 0


# ---------------------------------------------------------------------------
# Recommendations assignment
# ---------------------------------------------------------------------------

def test_recommendations_assigned():
    b = get_environment_builder()
    recs = _make_recs(2, "machinery")
    plan = b.build_environment("industrial_hangar", recs)
    assert plan.asset_count >= 2


def test_recommendations_overflow_to_background():
    b = get_environment_builder()
    # Flood all zones
    recs = _make_recs(50, "machinery")
    plan = b.build_environment("industrial_hangar", recs)
    # Should not raise; some may warn
    assert plan.ok


# ---------------------------------------------------------------------------
# build_environment_zones
# ---------------------------------------------------------------------------

def test_build_environment_zones_returns_dict():
    b = get_environment_builder()
    zones = b.build_environment_zones("industrial_hangar")
    assert isinstance(zones, dict)
    assert "hero_zone" in zones
    assert "midground" in zones
    assert "background" in zones


def test_zones_have_depths():
    b = get_environment_builder()
    zones = b.build_environment_zones("industrial_hangar")
    hero_depth = zones["hero_zone"].depth
    bg_depth   = zones["background"].depth
    assert hero_depth > bg_depth, "Background should be deeper (more negative) than hero"


# ---------------------------------------------------------------------------
# Zone roles
# ---------------------------------------------------------------------------

def test_hero_zone_role_is_primary():
    b = get_environment_builder()
    plan = b.build_environment("industrial_hangar")
    assert plan.zones["hero_zone"].role == "primary"


def test_midground_role_is_support():
    b = get_environment_builder()
    plan = b.build_environment("industrial_hangar")
    assert plan.zones["midground"].role == "support"


# ---------------------------------------------------------------------------
# validate_environment_structure
# ---------------------------------------------------------------------------

def test_validate_structure_valid():
    b = get_environment_builder()
    plan = b.build_environment("industrial_hangar")
    result = b.validate_environment_structure(plan)
    assert result["valid"]
    assert not result["errors"]


def test_validate_structure_no_hero_zone():
    b = get_environment_builder()
    plan = EnvironmentPlan(environment="test")
    plan.zones = {"midground": EnvironmentZone(zone_name="midground", role="support")}
    result = b.validate_environment_structure(plan)
    assert not result["valid"]
    assert any("hero_zone" in e for e in result["errors"])


def test_validate_structure_no_midground_warning():
    b = get_environment_builder()
    plan = EnvironmentPlan(environment="test")
    plan.zones = {"hero_zone": EnvironmentZone(zone_name="hero_zone", role="primary")}
    result = b.validate_environment_structure(plan)
    assert result["valid"]
    assert any("midground" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# EnvironmentZone dataclass
# ---------------------------------------------------------------------------

def test_environment_zone_round_trip():
    zone = EnvironmentZone(
        zone_name="hero_zone", role="primary", depth=0.0, width=12.0,
        categories=["machinery", "robot"], max_assets=3, facing="camera",
    )
    d = zone.to_dict()
    z2 = EnvironmentZone.from_dict(d)
    assert z2.zone_name == "hero_zone"
    assert z2.categories == ["machinery", "robot"]
    assert z2.max_assets == 3


# ---------------------------------------------------------------------------
# EnvironmentPlan dataclass
# ---------------------------------------------------------------------------

def test_environment_plan_round_trip():
    b = get_environment_builder()
    plan = b.build_environment("robotics_lab")
    d  = plan.to_dict()
    p2 = EnvironmentPlan.from_dict(d)
    assert p2.environment == "robotics_lab"
    assert set(p2.zones.keys()) == set(plan.zones.keys())
    assert p2.ok == plan.ok
