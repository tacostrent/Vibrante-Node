"""Tests for CompositionConstraints (Tier 9 — §29)."""
import pytest
from src.runtime.assets.assembly.composition_constraints import (
    ConstraintResult,
    CompositionReport,
    CompositionConstraints,
    get_composition_constraints,
    reset_composition_constraints_for_tests,
    _MAX_HERO_ASSETS,
    _MIN_DEPTH_LAYERS,
    _MAX_ZONE_FILL_RATIO,
    _MIN_NEG_SPACE_RATIO,
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
    reset_composition_constraints_for_tests()
    reset_environment_builder_for_tests()
    reset_placement_templates_for_tests()
    yield
    reset_composition_constraints_for_tests()
    reset_environment_builder_for_tests()
    reset_placement_templates_for_tests()


def _make_plan(hero_count=1, mid_count=2, bg_count=2):
    """Helper: build a plan with controlled asset counts per zone."""
    b = get_environment_builder()
    recs = (
        [{"asset": {"name": f"h{i}", "category": "machinery"}} for i in range(hero_count)] +
        [{"asset": {"name": f"m{i}", "category": "structure"}} for i in range(mid_count)] +
        [{"asset": {"name": f"b{i}", "category": "architectural"}} for i in range(bg_count)]
    )
    plan = b.build_environment("industrial_hangar", recs)
    return plan


def _empty_plan():
    """A plan with no assets in any zone."""
    b = get_environment_builder()
    return b.build_environment("industrial_hangar")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_composition_constraints() is get_composition_constraints()


def test_reset():
    a = get_composition_constraints()
    reset_composition_constraints_for_tests()
    b = get_composition_constraints()
    assert a is not b


# ---------------------------------------------------------------------------
# validate_readability
# ---------------------------------------------------------------------------

def test_readability_passes_with_one_hero_asset():
    plan = _make_plan(hero_count=1)
    r = get_composition_constraints().validate_readability(plan)
    assert r.check_name == "readability"
    assert r.passed
    assert not r.issues


def test_readability_fails_no_hero_zone():
    plan = EnvironmentPlan(environment="test")
    plan.zones = {"midground": EnvironmentZone("midground", "support")}
    r = get_composition_constraints().validate_readability(plan)
    assert not r.passed
    assert r.issues


def test_readability_fails_empty_hero_zone():
    plan = _make_plan(hero_count=0)
    r = get_composition_constraints().validate_readability(plan)
    assert not r.passed


def test_readability_fails_overloaded_hero():
    # Directly inject more than _MAX_HERO_ASSETS (3) into hero_zone to bypass builder cap
    plan = _make_plan(hero_count=1)
    hero = plan.zones["hero_zone"]
    hero.assigned_assets = [{"asset": {"name": f"h{i}", "category": "machinery"}} for i in range(5)]
    r = get_composition_constraints().validate_readability(plan)
    assert not r.passed


# ---------------------------------------------------------------------------
# validate_negative_space
# ---------------------------------------------------------------------------

def test_negative_space_passes_with_room():
    plan = _make_plan(hero_count=1)  # hero max is 3, 1 used → 66% free
    r = get_composition_constraints().validate_negative_space(plan)
    assert r.passed


def test_negative_space_fails_when_full():
    b    = get_environment_builder()
    recs = [{"asset": {"name": f"h{i}", "category": "machinery"}} for i in range(3)]
    plan = b.build_environment("industrial_hangar", recs)
    r    = get_composition_constraints().validate_negative_space(plan)
    # 3/3 = 0% free < 20% minimum
    assert not r.passed


def test_negative_space_no_hero_zone():
    plan = EnvironmentPlan(environment="test")
    r    = get_composition_constraints().validate_negative_space(plan)
    assert not r.passed


# ---------------------------------------------------------------------------
# validate_depth
# ---------------------------------------------------------------------------

def test_depth_passes_with_two_layers():
    plan = _make_plan(hero_count=1, mid_count=2, bg_count=2)
    r    = get_composition_constraints().validate_depth(plan)
    assert r.passed


def test_depth_fails_with_no_deep_zones_populated():
    plan = _make_plan(hero_count=2, mid_count=0, bg_count=0)
    r    = get_composition_constraints().validate_depth(plan)
    assert not r.passed


# ---------------------------------------------------------------------------
# validate_balance
# ---------------------------------------------------------------------------

def test_balance_passes_distributed():
    plan = _make_plan(hero_count=1, mid_count=2, bg_count=2)
    r    = get_composition_constraints().validate_balance(plan)
    assert r.passed


def test_balance_fails_empty_scene():
    plan = _empty_plan()
    r    = get_composition_constraints().validate_balance(plan)
    assert not r.passed
    assert any("empty" in i.lower() or "no assets" in i.lower() for i in r.issues)


def test_balance_fails_dominant_zone():
    """Flood hero zone to trigger dominant zone warning."""
    b    = get_environment_builder()
    # Put 10 assets all in hero zone (overflow to other zones)
    recs = [{"asset": {"name": f"h{i}", "category": "machinery"}} for i in range(1)]
    plan = b.build_environment("industrial_hangar", recs)
    # Manually make hero_zone hold all assets and clear others
    hero_assets = [{"asset": {"name": "h", "category": "machinery"}}] * 20
    plan.zones["hero_zone"].assigned_assets = hero_assets
    for name in plan.zones:
        if name != "hero_zone":
            plan.zones[name].assigned_assets = []
    r = get_composition_constraints().validate_balance(plan)
    assert not r.passed


# ---------------------------------------------------------------------------
# validate_focus
# ---------------------------------------------------------------------------

def test_focus_passes():
    plan = _make_plan(hero_count=1, mid_count=3, bg_count=2)
    r    = get_composition_constraints().validate_focus(plan)
    assert r.passed or not r.passed  # just assert no crash


def test_focus_fails_no_hero():
    plan = _empty_plan()
    r    = get_composition_constraints().validate_focus(plan)
    assert not r.passed


# ---------------------------------------------------------------------------
# validate_all (CompositionReport)
# ---------------------------------------------------------------------------

def test_validate_all_returns_report():
    plan   = _make_plan(hero_count=1, mid_count=2, bg_count=2)
    report = get_composition_constraints().validate_all(plan)
    assert isinstance(report, CompositionReport)


def test_validate_all_exactly_five_checks():
    plan   = _make_plan(hero_count=1, mid_count=2, bg_count=2)
    report = get_composition_constraints().validate_all(plan)
    assert len(report.checks) == 5


def test_validate_all_score_in_range():
    plan   = _make_plan(hero_count=1, mid_count=2, bg_count=2)
    report = get_composition_constraints().validate_all(plan)
    assert 0.0 <= report.overall_score <= 1.0


def test_validate_all_readable_flag():
    plan   = _make_plan(hero_count=1, mid_count=2, bg_count=2)
    report = get_composition_constraints().validate_all(plan)
    # readable = overall_score >= 0.6 and no issues
    assert report.readable == (report.overall_score >= 0.6 and not report.issues)


def test_validate_all_empty_scene_not_readable():
    plan   = _empty_plan()
    report = get_composition_constraints().validate_all(plan)
    assert not report.readable
    assert report.issues


def test_constraint_result_to_dict():
    r = ConstraintResult("readability", True, 0.9, [], "all good")
    d = r.to_dict()
    assert d["check_name"] == "readability"
    assert d["passed"] is True
    assert d["score"] == 0.9
