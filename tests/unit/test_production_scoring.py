"""
Tests for src.runtime.production_scoring
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.production_scoring import (
    ProductionScoring,
    get_production_scoring,
    reset_production_scoring_for_tests,
    _SCENE_SCORE_WEIGHTS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_production_scoring_for_tests()
    yield
    reset_production_scoring_for_tests()


def _zones_full():
    return {"hero_area": ["robot"], "midground": ["crate"], "background": ["wall"]}

def _zones_hero_only():
    return {"hero_area": ["robot"], "midground": [], "background": []}

def _zones_empty():
    return {}

def _good_lighting():
    return {
        "key_strategy": {"intensity": 2.5, "target_zone": "hero_area"},
        "rim_strategy": {"intensity": 1.5},
        "balance": {"balanced": True, "balance_score": 0.9, "issues": []},
    }

def _bad_lighting():
    return {
        "key_strategy": {"intensity": 0.0},
        "rim_strategy": {"intensity": 0.0},
        "balance": {"balanced": False, "balance_score": 0.0, "issues": ["rim exceeds key"]},
    }

def _good_camera():
    return {
        "camera_mode": "cinematic_push_in",
        "readability": {"readability_score": 0.8, "readable": True, "issues": []},
        "targets": [{"shot_type": "wide_establishing", "priority": 2},
                    {"shot_type": "hero_focus", "priority": 1}],
    }

def _good_atmosphere():
    return {"recommended_density": 0.04, "depth_atmosphere": {"depth_support": "strong"}}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_production_scoring()
    b = get_production_scoring()
    assert a is b


def test_reset_creates_new():
    a = get_production_scoring()
    reset_production_scoring_for_tests()
    b = get_production_scoring()
    assert a is not b


# ---------------------------------------------------------------------------
# score_readability
# ---------------------------------------------------------------------------

def test_readability_returns_dict():
    s = ProductionScoring()
    result = s.score_readability(_zones_full())
    assert isinstance(result, dict)


def test_readability_has_required_keys():
    s = ProductionScoring()
    result = s.score_readability(_zones_full())
    for key in ("readability_score", "hero_count", "depth_layers",
                "has_midground", "has_background", "issues", "grade"):
        assert key in result, f"Missing key: {key}"


def test_readability_full_zones_high_score():
    s = ProductionScoring()
    result = s.score_readability(_zones_full())
    assert result["readability_score"] >= 0.7


def test_readability_no_hero_penalised():
    s = ProductionScoring()
    result = s.score_readability({"hero_area": [], "midground": ["c"], "background": ["w"]})
    assert result["hero_count"] == 0
    assert result["readability_score"] < 0.7
    assert len(result["issues"]) > 0


def test_readability_one_hero_max_clarity():
    s = ProductionScoring()
    result = s.score_readability({"hero_area": ["r1"]})
    assert result["hero_count"] == 1


def test_readability_four_heroes_diluted():
    s = ProductionScoring()
    result = s.score_readability({"hero_area": ["r1", "r2", "r3", "r4"]})
    assert result["hero_count"] == 4
    assert any("diluted" in i.lower() for i in result["issues"])


def test_readability_empty_zones_zero():
    s = ProductionScoring()
    result = s.score_readability(_zones_empty())
    assert result["readability_score"] == 0.0


def test_readability_depth_layers_list():
    s = ProductionScoring()
    result = s.score_readability(_zones_full())
    assert isinstance(result["depth_layers"], list)
    assert "hero_area" in result["depth_layers"]


def test_readability_score_range():
    s = ProductionScoring()
    for zones in [_zones_full(), _zones_empty(), _zones_hero_only()]:
        r = s.score_readability(zones)
        assert 0.0 <= r["readability_score"] <= 1.0


# ---------------------------------------------------------------------------
# score_composition
# ---------------------------------------------------------------------------

def test_composition_returns_dict():
    s = ProductionScoring()
    result = s.score_composition(_zones_full())
    assert isinstance(result, dict)


def test_composition_has_required_keys():
    s = ProductionScoring()
    result = s.score_composition(_zones_full())
    for key in ("composition_score", "zone_weights", "balance_ratio",
                "heaviest_zone", "issues", "grade"):
        assert key in result


def test_composition_empty_scene():
    s = ProductionScoring()
    result = s.score_composition(_zones_empty())
    assert result["composition_score"] == 0.0
    assert result["heaviest_zone"] is None


def test_composition_equal_zones_balanced():
    s = ProductionScoring()
    result = s.score_composition({"hero_area": ["r"], "midground": ["c"], "background": ["w"]})
    assert result["composition_score"] > 0.5


def test_composition_overloaded_zone_penalised():
    s = ProductionScoring()
    zones = {"hero_area": ["r1", "r2", "r3", "r4", "r5"], "background": ["w"]}
    result = s.score_composition(zones)
    assert result["heaviest_zone"] == "hero_area"
    assert len(result["issues"]) > 0


def test_composition_zone_weights_sum_to_one():
    s = ProductionScoring()
    result = s.score_composition(_zones_full())
    total = sum(result["zone_weights"].values())
    assert total == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# score_lighting
# ---------------------------------------------------------------------------

def test_lighting_returns_dict():
    s = ProductionScoring()
    result = s.score_lighting(_good_lighting())
    assert isinstance(result, dict)


def test_lighting_has_required_keys():
    s = ProductionScoring()
    result = s.score_lighting(_good_lighting())
    for key in ("lighting_score", "has_key", "has_rim", "balanced", "issues", "grade"):
        assert key in result


def test_lighting_good_plan_high_score():
    s = ProductionScoring()
    result = s.score_lighting(_good_lighting())
    assert result["lighting_score"] >= 0.7
    assert result["has_key"] is True
    assert result["has_rim"] is True
    assert result["balanced"] is True


def test_lighting_no_plan_zero():
    s = ProductionScoring()
    result = s.score_lighting(None)
    assert result["lighting_score"] == 0.0
    assert len(result["issues"]) > 0


def test_lighting_bad_plan_low_score():
    s = ProductionScoring()
    result = s.score_lighting(_bad_lighting())
    assert result["lighting_score"] < 0.5
    assert result["has_key"] is False


def test_lighting_score_range():
    s = ProductionScoring()
    for plan in [_good_lighting(), _bad_lighting(), None]:
        r = s.score_lighting(plan)
        assert 0.0 <= r["lighting_score"] <= 1.0


# ---------------------------------------------------------------------------
# score_camera
# ---------------------------------------------------------------------------

def test_camera_returns_dict():
    s = ProductionScoring()
    result = s.score_camera(_good_camera())
    assert isinstance(result, dict)


def test_camera_has_required_keys():
    s = ProductionScoring()
    result = s.score_camera(_good_camera())
    for key in ("camera_score", "readable", "has_establishing", "mode", "issues", "grade"):
        assert key in result


def test_camera_good_plan():
    s = ProductionScoring()
    result = s.score_camera(_good_camera())
    assert result["camera_score"] >= 0.5
    assert result["readable"] is True
    assert result["has_establishing"] is True


def test_camera_no_plan_zero():
    s = ProductionScoring()
    result = s.score_camera(None)
    assert result["camera_score"] == 0.0


def test_camera_no_establishing_penalised():
    s = ProductionScoring()
    plan = {
        "camera_mode": "hero_focus",
        "readability": {"readability_score": 0.8, "readable": True, "issues": []},
        "targets": [{"shot_type": "hero_focus", "priority": 1}],
    }
    result = s.score_camera(plan)
    assert result["has_establishing"] is False
    assert any("establishing" in i.lower() for i in result["issues"])


# ---------------------------------------------------------------------------
# score_atmosphere
# ---------------------------------------------------------------------------

def test_atmosphere_returns_dict():
    s = ProductionScoring()
    result = s.score_atmosphere(_good_atmosphere())
    assert isinstance(result, dict)


def test_atmosphere_has_required_keys():
    s = ProductionScoring()
    result = s.score_atmosphere(_good_atmosphere())
    for key in ("atmosphere_score", "density_ok", "supports_depth", "density", "issues", "grade"):
        assert key in result


def test_atmosphere_good_density():
    s = ProductionScoring()
    result = s.score_atmosphere(_good_atmosphere())
    assert result["density_ok"] is True
    assert result["atmosphere_score"] >= 0.5


def test_atmosphere_no_plan_neutral():
    s = ProductionScoring()
    result = s.score_atmosphere(None)
    assert result["atmosphere_score"] == pytest.approx(0.5)


def test_atmosphere_high_density_penalised():
    s = ProductionScoring()
    result = s.score_atmosphere({"recommended_density": 0.10})
    assert result["density_ok"] is False
    assert result["atmosphere_score"] < 0.9
    assert any("density" in i.lower() or "obscured" in i.lower() for i in result["issues"])


def test_atmosphere_zero_density():
    s = ProductionScoring()
    result = s.score_atmosphere({"recommended_density": 0.0})
    assert result["density"] == 0.0


# ---------------------------------------------------------------------------
# score_scene
# ---------------------------------------------------------------------------

def test_score_scene_returns_dict():
    s = ProductionScoring()
    result = s.score_scene({
        "zones": _zones_full(),
        "lighting_plan": _good_lighting(),
        "camera_plan": _good_camera(),
        "atmosphere_plan": _good_atmosphere(),
    })
    assert isinstance(result, dict)


def test_score_scene_has_required_keys():
    s = ProductionScoring()
    result = s.score_scene({"zones": _zones_full()})
    for key in ("overall", "grade", "readability", "composition", "lighting",
                "camera", "atmosphere", "dimension_scores", "production_ready", "issues"):
        assert key in result, f"Missing key: {key}"


def test_score_scene_weights_sum():
    weights = _SCENE_SCORE_WEIGHTS
    assert sum(weights.values()) == pytest.approx(1.0, abs=0.001)


def test_score_scene_full_scene_high_score():
    s = ProductionScoring()
    result = s.score_scene({
        "zones": _zones_full(),
        "lighting_plan": _good_lighting(),
        "camera_plan": _good_camera(),
        "atmosphere_plan": _good_atmosphere(),
    })
    assert result["overall"] >= 0.5


def test_score_scene_empty_is_low():
    s = ProductionScoring()
    result = s.score_scene({"zones": {}})
    assert result["overall"] < 0.5


def test_score_scene_overall_range():
    s = ProductionScoring()
    for data in [
        {"zones": _zones_full(), "lighting_plan": _good_lighting()},
        {"zones": _zones_empty()},
    ]:
        r = s.score_scene(data)
        assert 0.0 <= r["overall"] <= 1.0


def test_score_scene_grade_f_for_empty():
    s = ProductionScoring()
    result = s.score_scene({"zones": {}})
    assert result["grade"] == "F"


def test_score_scene_increments_eval_count():
    s = ProductionScoring()
    s.score_scene({"zones": _zones_full()})
    s.score_scene({"zones": _zones_full()})
    assert s.stats()["eval_count"] == 2


def test_score_scene_production_ready_false_when_empty():
    s = ProductionScoring()
    result = s.score_scene({"zones": {}})
    assert result["production_ready"] is False


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_has_eval_count():
    s = ProductionScoring()
    assert "eval_count" in s.stats()


def test_stats_starts_zero():
    s = ProductionScoring()
    assert s.stats()["eval_count"] == 0
