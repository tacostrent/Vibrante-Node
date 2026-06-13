"""
Tests for src.runtime.visual_hierarchy_engine
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.visual_hierarchy_engine import (
    VisualHierarchyEngine,
    get_visual_hierarchy_engine,
    reset_visual_hierarchy_engine_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_visual_hierarchy_engine_for_tests()
    yield
    reset_visual_hierarchy_engine_for_tests()


def _zones_full():
    return {
        "hero_area":  ["robot_1"],
        "midground":  ["crate_1", "crate_2"],
        "background": ["wall_1"],
    }


def _zones_hero_only():
    return {"hero_area": ["robot_1"], "midground": [], "background": []}


def _zones_empty():
    return {"hero_area": [], "midground": [], "background": []}


def _lighting_targeting_hero():
    return {"key_strategy": {"target_zone": "hero_area", "intensity": 2.5}}


def _lighting_not_targeting_hero():
    return {"key_strategy": {"target_zone": "midground", "intensity": 2.5}}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_visual_hierarchy_engine()
    b = get_visual_hierarchy_engine()
    assert a is b


def test_reset_creates_new():
    a = get_visual_hierarchy_engine()
    reset_visual_hierarchy_engine_for_tests()
    b = get_visual_hierarchy_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# evaluate_hero_focus
# ---------------------------------------------------------------------------

def test_hero_focus_returns_dict():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus(_zones_empty())
    assert isinstance(result, dict)


def test_hero_focus_has_required_keys():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus(_zones_full())
    for key in ("has_hero", "hero_asset_count", "focus_clarity",
                "lighting_supports_hero", "issues", "strengths"):
        assert key in result, f"Missing key: {key}"


def test_hero_focus_no_hero():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus(_zones_empty())
    assert result["has_hero"] is False
    assert result["hero_asset_count"] == 0
    assert result["focus_clarity"] == pytest.approx(0.0)


def test_hero_focus_one_hero():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus({"hero_area": ["robot"]})
    assert result["has_hero"] is True
    assert result["hero_asset_count"] == 1
    assert result["focus_clarity"] == pytest.approx(1.0)


def test_hero_focus_two_heroes():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus({"hero_area": ["r1", "r2"]})
    assert result["focus_clarity"] == pytest.approx(0.85)


def test_hero_focus_three_heroes():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus({"hero_area": ["r1", "r2", "r3"]})
    assert result["focus_clarity"] == pytest.approx(0.85)


def test_hero_focus_overloaded():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus({"hero_area": ["r1", "r2", "r3", "r4"]})
    assert result["focus_clarity"] == pytest.approx(0.5)


def test_hero_focus_lighting_supports():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus({"hero_area": ["robot"]}, _lighting_targeting_hero())
    assert result["lighting_supports_hero"] is True


def test_hero_focus_lighting_not_targeting():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus({"hero_area": ["robot"]}, _lighting_not_targeting_hero())
    assert result["lighting_supports_hero"] is False


def test_hero_focus_no_lighting():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus({"hero_area": ["robot"]}, None)
    assert result["lighting_supports_hero"] is False


def test_hero_focus_issues_is_list():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus(_zones_empty())
    assert isinstance(result["issues"], list)


def test_hero_focus_strengths_is_list():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus(_zones_full(), _lighting_targeting_hero())
    assert isinstance(result["strengths"], list)


def test_hero_focus_no_hero_adds_issue():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus(_zones_empty())
    assert len(result["issues"]) > 0


def test_hero_focus_hero_lit_adds_strength():
    e = VisualHierarchyEngine()
    result = e.evaluate_hero_focus({"hero_area": ["robot"]}, _lighting_targeting_hero())
    assert len(result["strengths"]) > 0


# ---------------------------------------------------------------------------
# evaluate_depth_readability
# ---------------------------------------------------------------------------

def test_depth_readability_returns_dict():
    e = VisualHierarchyEngine()
    result = e.evaluate_depth_readability(_zones_full())
    assert isinstance(result, dict)


def test_depth_readability_has_required_keys():
    e = VisualHierarchyEngine()
    result = e.evaluate_depth_readability(_zones_full())
    for key in ("depth_score", "depth_layers", "depth_readable",
                "atmosphere_enhances_depth", "issues", "strengths"):
        assert key in result, f"Missing key: {key}"


def test_depth_readability_three_zones_readable():
    e = VisualHierarchyEngine()
    result = e.evaluate_depth_readability(_zones_full())
    assert result["depth_readable"] is True


def test_depth_readability_no_zones():
    e = VisualHierarchyEngine()
    result = e.evaluate_depth_readability(_zones_empty())
    assert result["depth_readable"] is False


def test_depth_readability_depth_layers_list():
    e = VisualHierarchyEngine()
    result = e.evaluate_depth_readability(_zones_full())
    assert isinstance(result["depth_layers"], list)
    assert "hero_area" in result["depth_layers"]


def test_depth_readability_atmosphere_enhances():
    e = VisualHierarchyEngine()
    atm = {"recommended_density": 0.04}
    result = e.evaluate_depth_readability(_zones_full(), atm)
    assert result["atmosphere_enhances_depth"] is True


def test_depth_readability_no_atmosphere():
    e = VisualHierarchyEngine()
    result = e.evaluate_depth_readability(_zones_full(), None)
    assert result["atmosphere_enhances_depth"] is False


def test_depth_readability_zero_density_no_enhance():
    e = VisualHierarchyEngine()
    atm = {"recommended_density": 0.0}
    result = e.evaluate_depth_readability(_zones_full(), atm)
    assert result["atmosphere_enhances_depth"] is False


def test_depth_readability_score_is_float():
    e = VisualHierarchyEngine()
    result = e.evaluate_depth_readability(_zones_full())
    assert isinstance(result["depth_score"], float)


def test_depth_readability_no_midground_adds_issue():
    e = VisualHierarchyEngine()
    zones = {"hero_area": ["r1"], "midground": [], "background": ["w1"]}
    result = e.evaluate_depth_readability(zones)
    assert len(result["issues"]) > 0


# ---------------------------------------------------------------------------
# evaluate_scene_balance
# ---------------------------------------------------------------------------

def test_scene_balance_returns_dict():
    e = VisualHierarchyEngine()
    result = e.evaluate_scene_balance(_zones_full())
    assert isinstance(result, dict)


def test_scene_balance_has_required_keys():
    e = VisualHierarchyEngine()
    result = e.evaluate_scene_balance(_zones_full())
    for key in ("balanced", "balance_score", "zone_weights",
                "heaviest_zone", "lightest_zone", "issues"):
        assert key in result, f"Missing key: {key}"


def test_scene_balance_empty_returns_unbalanced():
    e = VisualHierarchyEngine()
    result = e.evaluate_scene_balance(_zones_empty())
    assert result["balanced"] is False
    assert result["balance_score"] == pytest.approx(0.0)
    assert result["heaviest_zone"] is None
    assert result["lightest_zone"] is None


def test_scene_balance_equal_zones():
    e = VisualHierarchyEngine()
    zones = {"hero_area": ["r1"], "midground": ["c1"], "background": ["w1"]}
    result = e.evaluate_scene_balance(zones)
    assert result["balanced"] is True


def test_scene_balance_overloaded_zone():
    e = VisualHierarchyEngine()
    zones = {"hero_area": ["r1", "r2", "r3", "r4", "r5"], "background": ["w1"]}
    result = e.evaluate_scene_balance(zones)
    assert result["balanced"] is False
    assert result["heaviest_zone"] == "hero_area"


def test_scene_balance_score_range():
    e = VisualHierarchyEngine()
    result = e.evaluate_scene_balance(_zones_full())
    assert 0.0 <= result["balance_score"] <= 1.0


def test_scene_balance_issues_is_list():
    e = VisualHierarchyEngine()
    result = e.evaluate_scene_balance(_zones_full())
    assert isinstance(result["issues"], list)


def test_scene_balance_zone_weights_is_dict():
    e = VisualHierarchyEngine()
    result = e.evaluate_scene_balance(_zones_full())
    assert isinstance(result["zone_weights"], dict)


# ---------------------------------------------------------------------------
# evaluate_light_distribution
# ---------------------------------------------------------------------------

def test_light_distribution_returns_dict():
    e = VisualHierarchyEngine()
    plan = {"key_strategy": {"intensity": 2.5}, "rim_strategy": {"intensity": 1.5}}
    result = e.evaluate_light_distribution(plan)
    assert isinstance(result, dict)


def test_light_distribution_has_required_keys():
    e = VisualHierarchyEngine()
    plan = {"key_strategy": {"intensity": 2.5}}
    result = e.evaluate_light_distribution(plan)
    for key in ("has_key", "has_rim", "has_practicals", "has_volumetric",
                "distribution_score", "issues", "strengths"):
        assert key in result, f"Missing key: {key}"


def test_light_distribution_has_key():
    e = VisualHierarchyEngine()
    plan = {"key_strategy": {"intensity": 2.5}}
    result = e.evaluate_light_distribution(plan)
    assert result["has_key"] is True


def test_light_distribution_no_key():
    e = VisualHierarchyEngine()
    result = e.evaluate_light_distribution({})
    assert result["has_key"] is False


def test_light_distribution_has_rim():
    e = VisualHierarchyEngine()
    plan = {"key_strategy": {"intensity": 2.5}, "rim_strategy": {"intensity": 1.5}}
    result = e.evaluate_light_distribution(plan)
    assert result["has_rim"] is True


def test_light_distribution_no_rim():
    e = VisualHierarchyEngine()
    plan = {"key_strategy": {"intensity": 2.5}}
    result = e.evaluate_light_distribution(plan)
    assert result["has_rim"] is False


def test_light_distribution_has_practicals():
    e = VisualHierarchyEngine()
    plan = {"practical_lighting": {"count": 3}}
    result = e.evaluate_light_distribution(plan)
    assert result["has_practicals"] is True


def test_light_distribution_no_practicals():
    e = VisualHierarchyEngine()
    result = e.evaluate_light_distribution({})
    assert result["has_practicals"] is False


def test_light_distribution_has_volumetric():
    e = VisualHierarchyEngine()
    plan = {"volumetric": {"enabled": True}}
    result = e.evaluate_light_distribution(plan)
    assert result["has_volumetric"] is True


def test_light_distribution_volumetric_disabled():
    e = VisualHierarchyEngine()
    plan = {"volumetric": {"enabled": False}}
    result = e.evaluate_light_distribution(plan)
    assert result["has_volumetric"] is False


def test_light_distribution_score_full():
    e = VisualHierarchyEngine()
    plan = {
        "key_strategy": {"intensity": 2.5},
        "rim_strategy": {"intensity": 1.5},
        "practical_lighting": {"count": 3},
        "volumetric": {"enabled": True},
    }
    result = e.evaluate_light_distribution(plan)
    assert result["distribution_score"] == pytest.approx(1.0)


def test_light_distribution_score_zero():
    e = VisualHierarchyEngine()
    result = e.evaluate_light_distribution({})
    assert result["distribution_score"] == pytest.approx(0.0)


def test_light_distribution_issues_list():
    e = VisualHierarchyEngine()
    result = e.evaluate_light_distribution({})
    assert isinstance(result["issues"], list)
    assert len(result["issues"]) > 0


def test_light_distribution_key_rim_adds_strength():
    e = VisualHierarchyEngine()
    plan = {"key_strategy": {"intensity": 2.5}, "rim_strategy": {"intensity": 1.5}}
    result = e.evaluate_light_distribution(plan)
    assert len(result["strengths"]) > 0


# ---------------------------------------------------------------------------
# generate_hierarchy_review
# ---------------------------------------------------------------------------

def test_hierarchy_review_returns_dict():
    e = VisualHierarchyEngine()
    result = e.generate_hierarchy_review(_zones_full(), _lighting_targeting_hero(), {})
    assert isinstance(result, dict)


def test_hierarchy_review_has_required_keys():
    e = VisualHierarchyEngine()
    result = e.generate_hierarchy_review(_zones_full(), _lighting_targeting_hero(), {})
    for key in ("hero_focus", "depth_readability", "scene_balance", "light_distribution",
                "overall_score", "production_ready", "blocking_issues", "strengths",
                "review_summary", "generated_at"):
        assert key in result, f"Missing key: {key}"


def test_hierarchy_review_overall_score_range():
    e = VisualHierarchyEngine()
    result = e.generate_hierarchy_review(_zones_full(), _lighting_targeting_hero(), {})
    assert 0.0 <= result["overall_score"] <= 1.0


def test_hierarchy_review_production_ready_is_bool():
    e = VisualHierarchyEngine()
    result = e.generate_hierarchy_review(_zones_full(), _lighting_targeting_hero(), {})
    assert isinstance(result["production_ready"], bool)


def test_hierarchy_review_empty_scene_not_ready():
    e = VisualHierarchyEngine()
    result = e.generate_hierarchy_review(_zones_empty(), {}, {})
    assert result["production_ready"] is False


def test_hierarchy_review_blocking_issues_list():
    e = VisualHierarchyEngine()
    result = e.generate_hierarchy_review(_zones_full(), _lighting_targeting_hero(), {})
    assert isinstance(result["blocking_issues"], list)


def test_hierarchy_review_strengths_list():
    e = VisualHierarchyEngine()
    result = e.generate_hierarchy_review(_zones_full(), _lighting_targeting_hero(), {})
    assert isinstance(result["strengths"], list)


def test_hierarchy_review_summary_is_string():
    e = VisualHierarchyEngine()
    result = e.generate_hierarchy_review(_zones_full(), _lighting_targeting_hero(), {})
    assert isinstance(result["review_summary"], str)
    assert len(result["review_summary"]) > 0


def test_hierarchy_review_increments_count():
    e = VisualHierarchyEngine()
    e.generate_hierarchy_review(_zones_full(), {}, {})
    e.generate_hierarchy_review(_zones_full(), {}, {})
    assert e.stats()["review_count"] == 2


def test_hierarchy_review_generated_at_is_float():
    e = VisualHierarchyEngine()
    result = e.generate_hierarchy_review(_zones_full(), {}, {})
    assert isinstance(result["generated_at"], float)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_has_review_count():
    e = VisualHierarchyEngine()
    assert "review_count" in e.stats()


def test_stats_starts_zero():
    e = VisualHierarchyEngine()
    assert e.stats()["review_count"] == 0


def test_stats_increments_on_review():
    e = VisualHierarchyEngine()
    e.generate_hierarchy_review(_zones_full(), {}, {})
    assert e.stats()["review_count"] == 1
