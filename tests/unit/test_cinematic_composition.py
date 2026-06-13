"""
Tests for src.runtime.cinematic_composition
No bridge, no LLM.  Pure unit tests.
"""
import pytest
from src.runtime.cinematic_composition import (
    CinematicCompositionEngine,
    get_cinematic_composition_engine,
    reset_cinematic_composition_engine_for_tests,
    _MAX_HERO_ASSETS,
    _DEPTH_LAYER_MIN_ASSETS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_cinematic_composition_engine_for_tests()
    yield
    reset_cinematic_composition_engine_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_cinematic_composition_engine()
    b = get_cinematic_composition_engine()
    assert a is b


def test_reset_creates_new():
    a = get_cinematic_composition_engine()
    reset_cinematic_composition_engine_for_tests()
    b = get_cinematic_composition_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# analyze_visual_balance
# ---------------------------------------------------------------------------

def test_balance_empty_zones():
    eng = CinematicCompositionEngine()
    result = eng.analyze_visual_balance({"hero_area": [], "midground": [], "background": []})
    assert result["balanced"] is True
    assert result["balance_score"] == 1.0
    assert result["heaviest_zone"] is None
    assert result["lightest_zone"] is None
    assert len(result["recommendations"]) > 0


def test_balance_single_populated_zone():
    eng = CinematicCompositionEngine()
    zones = {"hero_area": [{"name": "a"}], "midground": [], "background": []}
    result = eng.analyze_visual_balance(zones)
    assert result["heaviest_zone"] == "hero_area"
    assert "midground" in " ".join(result["recommendations"]).lower() or \
           "background" in " ".join(result["recommendations"]).lower()


def test_balance_too_many_heroes():
    eng = CinematicCompositionEngine()
    hero_assets = [{"name": f"hero_{i}"} for i in range(_MAX_HERO_ASSETS + 1)]
    zones = {"hero_area": hero_assets, "midground": [{"name": "m1"}], "background": [{"name": "b1"}]}
    result = eng.analyze_visual_balance(zones)
    recs = " ".join(result["recommendations"])
    assert str(_MAX_HERO_ASSETS) in recs or "focal point" in recs.lower()


def test_balance_missing_midground():
    eng = CinematicCompositionEngine()
    zones = {"hero_area": [{"name": "h1"}], "midground": [], "background": [{"name": "b1"}]}
    result = eng.analyze_visual_balance(zones)
    recs = " ".join(result["recommendations"])
    assert "midground" in recs.lower()


def test_balance_missing_background():
    eng = CinematicCompositionEngine()
    zones = {"hero_area": [{"name": "h1"}], "midground": [{"name": "m1"}], "background": []}
    result = eng.analyze_visual_balance(zones)
    recs = " ".join(result["recommendations"])
    assert "background" in recs.lower()


def test_balance_score_range():
    eng = CinematicCompositionEngine()
    zones = {
        "hero_area":  [{"name": "h1"}, {"name": "h2"}],
        "midground":  [{"name": "m1"}],
        "background": [{"name": "b1"}],
    }
    result = eng.analyze_visual_balance(zones)
    assert 0.0 <= result["balance_score"] <= 1.0


def test_balance_result_keys():
    eng = CinematicCompositionEngine()
    result = eng.analyze_visual_balance({})
    required = {"balanced", "balance_score", "zone_weights", "heaviest_zone", "lightest_zone", "recommendations"}
    assert required <= set(result.keys())


# ---------------------------------------------------------------------------
# calculate_focus_distribution
# ---------------------------------------------------------------------------

def test_focus_empty_zones():
    eng = CinematicCompositionEngine()
    result = eng.calculate_focus_distribution({})
    assert result["primary_focus"] is None
    assert result["secondary_focus"] is None
    assert result["focus_clarity"] == 0.0
    assert result["distribution"] == {}


def test_focus_single_zone():
    eng = CinematicCompositionEngine()
    zones = {"hero_area": [{"name": "a"}, {"name": "b"}]}
    result = eng.calculate_focus_distribution(zones)
    assert result["primary_focus"] == "hero_area"
    assert result["focus_clarity"] == 1.0
    assert result["secondary_focus"] is None


def test_focus_two_zones():
    eng = CinematicCompositionEngine()
    zones = {
        "hero_area": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
        "midground": [{"name": "m1"}],
    }
    result = eng.calculate_focus_distribution(zones)
    assert result["primary_focus"] == "hero_area"
    assert result["secondary_focus"] == "midground"


def test_focus_distribution_sums_to_one():
    eng = CinematicCompositionEngine()
    zones = {
        "hero_area":  [{"name": f"h{i}"} for i in range(2)],
        "midground":  [{"name": f"m{i}"} for i in range(3)],
        "background": [{"name": f"b{i}"} for i in range(5)],
    }
    result = eng.calculate_focus_distribution(zones)
    total = sum(result["distribution"].values())
    assert abs(total - 1.0) < 0.001


def test_focus_clarity_in_range():
    eng = CinematicCompositionEngine()
    zones = {"hero_area": [{"name": "h1"}], "background": [{"name": "b1"}]}
    result = eng.calculate_focus_distribution(zones)
    assert 0.0 <= result["focus_clarity"] <= 1.0


# ---------------------------------------------------------------------------
# suggest_camera_targets
# ---------------------------------------------------------------------------

def _make_plan(hero=None, midground=None, background=None, camera_hints=None, scene_theme="test"):
    zones = {
        "hero_area":  hero      if hero      is not None else [],
        "midground":  midground if midground is not None else [],
        "background": background if background is not None else [],
    }
    return {
        "zones":        zones,
        "scene_theme":  scene_theme,
        "layout_rules": {"hero_focus": "center"},
        "camera_hints": camera_hints or [],
    }


def test_camera_targets_always_has_establishing():
    eng = CinematicCompositionEngine()
    targets = eng.suggest_camera_targets(_make_plan())
    shot_types = [t["shot_type"] for t in targets]
    assert "wide_establishing" in shot_types


def test_camera_targets_hero_focus_when_populated():
    eng = CinematicCompositionEngine()
    plan = _make_plan(hero=[{"name": "h1"}])
    targets = eng.suggest_camera_targets(plan)
    zones = [t["zone"] for t in targets]
    assert "hero_area" in zones


def test_camera_targets_no_hero_focus_when_empty():
    eng = CinematicCompositionEngine()
    plan = _make_plan(hero=[])
    targets = eng.suggest_camera_targets(plan)
    zones = [t["zone"] for t in targets]
    assert "hero_area" not in zones


def test_camera_targets_depth_reveal_when_populated():
    eng = CinematicCompositionEngine()
    plan = _make_plan(midground=[{"name": "m1"}], background=[{"name": "b1"}])
    targets = eng.suggest_camera_targets(plan)
    shot_types = [t["shot_type"] for t in targets]
    assert "depth_of_field" in shot_types


def test_camera_targets_hint_slots_capped_at_two():
    eng = CinematicCompositionEngine()
    hints = ["low_angle", "dutch_tilt", "overhead_shot", "tracking_shot"]
    plan = _make_plan(camera_hints=hints)
    targets = eng.suggest_camera_targets(plan)
    hint_shots = [t for t in targets if t["shot_type"] in hints]
    assert len(hint_shots) <= 2


def test_camera_targets_priorities_ordered():
    eng = CinematicCompositionEngine()
    plan = _make_plan(hero=[{"name": "h1"}])
    targets = eng.suggest_camera_targets(plan)
    priorities = [t["priority"] for t in targets]
    assert priorities == sorted(priorities)


def test_camera_targets_have_required_keys():
    eng = CinematicCompositionEngine()
    plan = _make_plan(hero=[{"name": "h1"}])
    for target in eng.suggest_camera_targets(plan):
        assert {"name", "zone", "priority", "shot_type", "description"} <= set(target.keys())


# ---------------------------------------------------------------------------
# evaluate_scene_readability
# ---------------------------------------------------------------------------

def test_readability_empty_scene():
    eng = CinematicCompositionEngine()
    result = eng.evaluate_scene_readability(_make_plan())
    assert result["readable"] is False
    assert result["readability_score"] == 0.0
    issues_text = " ".join(result["issues"])
    assert "empty" in issues_text.lower()


def test_readability_no_hero():
    eng = CinematicCompositionEngine()
    plan = _make_plan(midground=[{"name": "m1"}], background=[{"name": "b1"}])
    result = eng.evaluate_scene_readability(plan)
    issues_text = " ".join(result["issues"])
    assert "hero" in issues_text.lower() or "narrative" in issues_text.lower()
    assert result["readability_score"] < 1.0


def test_readability_overloaded_hero():
    eng = CinematicCompositionEngine()
    hero_assets = [{"name": f"h{i}"} for i in range(_MAX_HERO_ASSETS + 2)]
    plan = _make_plan(hero=hero_assets, midground=[{"name": "m1"}], background=[{"name": "b1"}])
    result = eng.evaluate_scene_readability(plan)
    issues_text = " ".join(result["issues"])
    assert "overload" in issues_text.lower() or "focal" in issues_text.lower()
    assert result["readability_score"] < 1.0


def test_readability_flat_scene():
    eng = CinematicCompositionEngine()
    plan = _make_plan(hero=[{"name": "h1"}])
    result = eng.evaluate_scene_readability(plan)
    issues_text = " ".join(result["issues"])
    assert "flat" in issues_text.lower() or "depth" in issues_text.lower()


def test_readability_three_layer_strengths():
    eng = CinematicCompositionEngine()
    plan = _make_plan(
        hero=[{"name": "h1"}],
        midground=[{"name": "m1"}],
        background=[{"name": "b1"}],
    )
    result = eng.evaluate_scene_readability(plan)
    strengths_text = " ".join(result["strengths"])
    assert "depth" in strengths_text.lower() or "three" in strengths_text.lower()
    assert result["readability_score"] >= 0.5


def test_readability_score_in_range():
    eng = CinematicCompositionEngine()
    plan = _make_plan(hero=[{"name": "h1"}], midground=[{"name": "m1"}], background=[{"name": "b1"}])
    result = eng.evaluate_scene_readability(plan)
    assert 0.0 <= result["readability_score"] <= 1.0


def test_readability_result_keys():
    eng = CinematicCompositionEngine()
    result = eng.evaluate_scene_readability(_make_plan())
    required = {"readable", "readability_score", "issues", "strengths"}
    assert required <= set(result.keys())


def test_readability_increments_eval_count():
    eng = CinematicCompositionEngine()
    eng.evaluate_scene_readability(_make_plan())
    eng.evaluate_scene_readability(_make_plan())
    assert eng.stats()["eval_count"] == 2


# ---------------------------------------------------------------------------
# suggest_depth_layers
# ---------------------------------------------------------------------------

def test_depth_layers_always_has_three_core():
    eng = CinematicCompositionEngine()
    layers = eng.suggest_depth_layers("industrial_hangar", 5)
    names = [l["layer_name"] for l in layers]
    assert "hero_area" in names
    assert "midground" in names
    assert "background" in names


def test_depth_layers_no_foreground_for_small_scenes():
    eng = CinematicCompositionEngine()
    layers = eng.suggest_depth_layers("test", _DEPTH_LAYER_MIN_ASSETS - 1)
    names = [l["layer_name"] for l in layers]
    assert "foreground_frame" not in names


def test_depth_layers_has_foreground_for_large_scenes():
    eng = CinematicCompositionEngine()
    layers = eng.suggest_depth_layers("test", _DEPTH_LAYER_MIN_ASSETS)
    names = [l["layer_name"] for l in layers]
    assert "foreground_frame" in names


def test_depth_layers_required_fields():
    eng = CinematicCompositionEngine()
    for layer in eng.suggest_depth_layers("test", 8):
        assert {"layer_name", "purpose", "suggested_asset_count", "depth_priority"} <= set(layer.keys())


def test_depth_layers_depth_priority_ordering():
    eng = CinematicCompositionEngine()
    layers = eng.suggest_depth_layers("test", 8)
    priorities = [l["depth_priority"] for l in layers]
    assert sorted(priorities) == priorities


def test_depth_layers_allocations_positive():
    eng = CinematicCompositionEngine()
    for layer in eng.suggest_depth_layers("test", 20):
        assert layer["suggested_asset_count"] >= 0


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    eng = CinematicCompositionEngine()
    s = eng.stats()
    assert "eval_count" in s


def test_stats_starts_at_zero():
    eng = CinematicCompositionEngine()
    assert eng.stats()["eval_count"] == 0
