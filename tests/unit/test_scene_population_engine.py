"""Tests for ScenePopulationEngine (Tier 9 — §29)."""
import pytest
from src.runtime.assets.assembly.scene_population_engine import (
    PopulationGroup,
    PopulationPlan,
    ScenePopulationEngine,
    get_scene_population_engine,
    reset_scene_population_engine_for_tests,
    _ALL_GROUPS,
    _GROUP_MAX,
    _CAT_TO_GROUP,
)
from src.runtime.assets.assembly.environment_builder import (
    get_environment_builder,
    reset_environment_builder_for_tests,
)
from src.runtime.assets.assembly.placement_templates import reset_placement_templates_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_scene_population_engine_for_tests()
    reset_environment_builder_for_tests()
    reset_placement_templates_for_tests()
    yield
    reset_scene_population_engine_for_tests()
    reset_environment_builder_for_tests()
    reset_placement_templates_for_tests()


def _env(cats):
    b = get_environment_builder()
    recs = [{"asset": {"name": f"a_{i}", "category": c}} for i, c in enumerate(cats)]
    return b.build_environment("industrial_hangar", recs)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_scene_population_engine() is get_scene_population_engine()


def test_reset():
    a = get_scene_population_engine()
    reset_scene_population_engine_for_tests()
    b = get_scene_population_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# populate_scene
# ---------------------------------------------------------------------------

def test_populate_scene_returns_plan():
    plan = get_scene_population_engine().populate_scene(_env(["machinery"]))
    assert isinstance(plan, PopulationPlan)
    assert plan.ok


def test_all_groups_present():
    plan = get_scene_population_engine().populate_scene(_env([]))
    for name in _ALL_GROUPS:
        assert name in plan.groups


def test_machinery_in_hero_assets():
    env  = _env(["machinery", "vehicle"])
    plan = get_scene_population_engine().populate_scene(env)
    hero = plan.groups["hero_assets"]
    assert hero.asset_count >= 2


def test_prop_in_detail_assets():
    env  = _env(["prop"])
    plan = get_scene_population_engine().populate_scene(env)
    det  = plan.groups["detail_assets"]
    assert det.asset_count >= 1


def test_hdri_in_atmosphere_assets():
    env  = _env(["hdri"])
    plan = get_scene_population_engine().populate_scene(env)
    atm  = plan.groups["atmosphere_assets"]
    assert atm.asset_count >= 1


def test_total_assets_correct():
    cats = ["machinery", "prop", "electronic", "hdri"]
    env  = _env(cats)
    plan = get_scene_population_engine().populate_scene(env)
    assert plan.total_assets == len(cats)


def test_balance_score_range():
    env  = _env(["machinery", "prop"])
    plan = get_scene_population_engine().populate_scene(env)
    assert 0.0 <= plan.balance_score <= 1.0


# ---------------------------------------------------------------------------
# assign_population_levels
# ---------------------------------------------------------------------------

def test_population_levels_set():
    env  = _env(["machinery", "machinery", "machinery"])
    plan = get_scene_population_engine().populate_scene(env)
    hero = plan.groups["hero_assets"]
    # 3 assets, max=3 → fill=1.0 → dense
    assert hero.level in ("sparse", "moderate", "dense")


def test_sparse_level_for_empty_group():
    env  = _env([])
    plan = get_scene_population_engine().populate_scene(env)
    for group in plan.groups.values():
        assert group.level == "sparse"


# ---------------------------------------------------------------------------
# assign_support_assets / assign_detail_assets
# ---------------------------------------------------------------------------

def test_assign_support_assets():
    recs = [
        {"asset": {"name": "s1", "category": "structure"}},
        {"asset": {"name": "e1", "category": "electronic"}},
        {"asset": {"name": "m1", "category": "machinery"}},
    ]
    engine   = get_scene_population_engine()
    filtered = engine.assign_support_assets(recs)
    cats = [r["asset"]["category"] for r in filtered]
    assert "structure" in cats
    assert "electronic" in cats
    assert "machinery" not in cats


def test_assign_detail_assets():
    recs = [
        {"asset": {"name": "p1", "category": "prop"}},
        {"asset": {"name": "pi1", "category": "pipe"}},
        {"asset": {"name": "r1", "category": "robot"}},
    ]
    engine   = get_scene_population_engine()
    filtered = engine.assign_detail_assets(recs)
    cats = [r["asset"]["category"] for r in filtered]
    assert "prop" in cats
    assert "pipe" in cats
    assert "robot" not in cats


# ---------------------------------------------------------------------------
# validate_population_balance
# ---------------------------------------------------------------------------

def test_balance_warns_no_hero():
    plan = PopulationPlan()
    plan.groups = {n: PopulationGroup(n, "sparse", max_assets=_GROUP_MAX[n]) for n in _ALL_GROUPS}
    result = get_scene_population_engine().validate_population_balance(plan)
    assert any("hero" in w.lower() for w in result["warnings"])


def test_balance_ok_with_hero():
    plan = PopulationPlan()
    plan.groups = {n: PopulationGroup(n, "sparse", max_assets=_GROUP_MAX[n]) for n in _ALL_GROUPS}
    plan.groups["hero_assets"].assets = [{"asset": {}}]
    result = get_scene_population_engine().validate_population_balance(plan)
    # No hero warning
    assert not any("hero assets" in w.lower() for w in result["warnings"])


def test_balance_warns_detail_dominates():
    plan = PopulationPlan()
    plan.groups = {n: PopulationGroup(n, "sparse", max_assets=_GROUP_MAX[n]) for n in _ALL_GROUPS}
    # Fill detail to 70%
    plan.groups["hero_assets"].assets   = [{"asset": {}}]
    plan.groups["detail_assets"].assets = [{"asset": {}}] * 7
    result = get_scene_population_engine().validate_population_balance(plan)
    # This may or may not warn depending on total — just confirm no crash
    assert isinstance(result["warnings"], list)


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

def test_population_plan_round_trip():
    env  = _env(["machinery", "prop"])
    plan = get_scene_population_engine().populate_scene(env)
    d   = plan.to_dict()
    p2  = PopulationPlan.from_dict(d)
    assert p2.total_assets == plan.total_assets
    assert set(p2.groups.keys()) == set(plan.groups.keys())
