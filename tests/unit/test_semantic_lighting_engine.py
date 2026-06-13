"""
Tests for src.runtime.semantic_lighting_engine
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.semantic_lighting_engine import (
    SemanticLightingEngine,
    get_semantic_lighting_engine,
    reset_semantic_lighting_engine_for_tests,
    _LIGHTING_PRESETS,
    _DEFAULT_STYLE,
)


@pytest.fixture(autouse=True)
def reset():
    reset_semantic_lighting_engine_for_tests()
    yield
    reset_semantic_lighting_engine_for_tests()


def _zones_with_hero():
    return {"hero_area": ["robot_1"], "midground": ["crate_1"], "background": ["wall_1"]}


def _zones_no_hero():
    return {"hero_area": [], "midground": ["crate_1"], "background": ["wall_1"]}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_semantic_lighting_engine()
    b = get_semantic_lighting_engine()
    assert a is b


def test_reset_creates_new():
    a = get_semantic_lighting_engine()
    reset_semantic_lighting_engine_for_tests()
    b = get_semantic_lighting_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# _LIGHTING_PRESETS constant
# ---------------------------------------------------------------------------

def test_lighting_presets_has_required_styles():
    required = {"cinematic_industrial", "bladerunner_noir", "cold_scifi",
                "atmospheric_lab", "warm_control_room"}
    assert required <= set(_LIGHTING_PRESETS.keys())


def test_default_style_exists():
    assert _DEFAULT_STYLE in _LIGHTING_PRESETS


def test_each_preset_has_required_keys():
    required = {"key", "rim", "fill", "practicals", "volumetric", "renderer_hints"}
    for name, preset in _LIGHTING_PRESETS.items():
        assert required <= set(preset.keys()), f"Preset '{name}' missing keys"


def test_each_key_has_intensity():
    for name, preset in _LIGHTING_PRESETS.items():
        assert "intensity" in preset["key"], f"'{name}'.key missing intensity"


def test_volumetric_has_enabled():
    for name, preset in _LIGHTING_PRESETS.items():
        assert "enabled" in preset["volumetric"], f"'{name}'.volumetric missing enabled"


# ---------------------------------------------------------------------------
# generate_lighting_plan
# ---------------------------------------------------------------------------

def test_lighting_plan_returns_dict():
    e = SemanticLightingEngine()
    result = e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial")
    assert isinstance(result, dict)


def test_lighting_plan_has_required_keys():
    e = SemanticLightingEngine()
    result = e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial")
    for key in ("plan_id", "lighting_style", "scene_theme", "key_strategy",
                "rim_strategy", "practical_lighting", "volumetric", "renderer_hints",
                "balance", "operations", "generated_at"):
        assert key in result, f"Missing key: {key}"


def test_lighting_plan_unknown_style_falls_back():
    e = SemanticLightingEngine()
    result = e.generate_lighting_plan(_zones_with_hero(), "unknown_xyz")
    assert result["lighting_style"] == _DEFAULT_STYLE


def test_lighting_plan_none_style_falls_back():
    e = SemanticLightingEngine()
    result = e.generate_lighting_plan(_zones_with_hero(), None)
    assert result["lighting_style"] == _DEFAULT_STYLE


def test_lighting_plan_plan_id_is_string():
    e = SemanticLightingEngine()
    result = e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial")
    assert isinstance(result["plan_id"], str)
    assert len(result["plan_id"]) > 0


def test_lighting_plan_operations_is_list():
    e = SemanticLightingEngine()
    result = e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial")
    assert isinstance(result["operations"], list)


def test_lighting_plan_operations_nonempty():
    e = SemanticLightingEngine()
    result = e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial")
    assert len(result["operations"]) > 0


def test_lighting_plan_increments_plan_count():
    e = SemanticLightingEngine()
    e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial")
    e.generate_lighting_plan(_zones_with_hero(), "bladerunner_noir")
    assert e.stats()["plan_count"] == 2


def test_lighting_plan_has_renderer_hints():
    e = SemanticLightingEngine()
    result = e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial")
    assert "arnold" in result["renderer_hints"] or "karma" in result["renderer_hints"]


def test_lighting_plan_scene_theme_recorded():
    e = SemanticLightingEngine()
    result = e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial",
                                      scene_theme="industrial_hangar")
    assert result["scene_theme"] == "industrial_hangar"


def test_lighting_plan_all_styles():
    e = SemanticLightingEngine()
    for style in _LIGHTING_PRESETS:
        result = e.generate_lighting_plan(_zones_with_hero(), style)
        assert result["lighting_style"] == style


# ---------------------------------------------------------------------------
# build_key_light_strategy
# ---------------------------------------------------------------------------

def test_key_strategy_has_required_keys():
    e = SemanticLightingEngine()
    result = e.build_key_light_strategy("cinematic_industrial", _zones_with_hero())
    for key in ("name", "type", "parent", "target_zone", "intensity"):
        assert key in result, f"Missing key: {key}"


def test_key_strategy_name_is_key_light():
    e = SemanticLightingEngine()
    result = e.build_key_light_strategy("cinematic_industrial", _zones_with_hero())
    assert result["name"] == "key_light"


def test_key_strategy_parent_is_lighting():
    e = SemanticLightingEngine()
    result = e.build_key_light_strategy("cinematic_industrial", _zones_with_hero())
    assert result["parent"] == "/obj/lighting"


def test_key_strategy_targets_hero_when_populated():
    e = SemanticLightingEngine()
    result = e.build_key_light_strategy("cinematic_industrial", _zones_with_hero())
    assert result["target_zone"] == "hero_area"


def test_key_strategy_targets_midground_when_no_hero():
    e = SemanticLightingEngine()
    result = e.build_key_light_strategy("cinematic_industrial", _zones_no_hero())
    assert result["target_zone"] == "midground"


def test_key_strategy_unknown_style_falls_back():
    e = SemanticLightingEngine()
    result = e.build_key_light_strategy("unknown_xyz", _zones_with_hero())
    assert result["target_zone"] in ("hero_area", "midground")


def test_key_strategy_intensity_positive():
    e = SemanticLightingEngine()
    result = e.build_key_light_strategy("cinematic_industrial", _zones_with_hero())
    assert result["intensity"] > 0


# ---------------------------------------------------------------------------
# build_rim_light_strategy
# ---------------------------------------------------------------------------

def test_rim_strategy_has_required_keys():
    e = SemanticLightingEngine()
    result = e.build_rim_light_strategy("cinematic_industrial", _zones_with_hero())
    for key in ("name", "type", "parent", "intensity"):
        assert key in result, f"Missing key: {key}"


def test_rim_strategy_name_is_rim_light():
    e = SemanticLightingEngine()
    result = e.build_rim_light_strategy("cinematic_industrial", _zones_with_hero())
    assert result["name"] == "rim_light"


def test_rim_strategy_parent_is_lighting():
    e = SemanticLightingEngine()
    result = e.build_rim_light_strategy("cinematic_industrial", _zones_with_hero())
    assert result["parent"] == "/obj/lighting"


def test_rim_strategy_intensity_positive():
    e = SemanticLightingEngine()
    result = e.build_rim_light_strategy("cinematic_industrial", _zones_with_hero())
    assert result["intensity"] > 0


# ---------------------------------------------------------------------------
# build_practical_lighting
# ---------------------------------------------------------------------------

def test_practical_lighting_has_required_keys():
    e = SemanticLightingEngine()
    result = e.build_practical_lighting("industrial_hangar", _zones_with_hero())
    for key in ("type", "count", "distribution", "color_temp", "scene_theme", "parent"):
        assert key in result, f"Missing key: {key}"


def test_practical_lighting_parent_is_lighting():
    e = SemanticLightingEngine()
    result = e.build_practical_lighting("industrial_hangar", _zones_with_hero())
    assert result["parent"] == "/obj/lighting"


def test_practical_lighting_records_theme():
    e = SemanticLightingEngine()
    result = e.build_practical_lighting("my_theme", _zones_with_hero())
    assert result["scene_theme"] == "my_theme"


def test_practical_lighting_count_positive():
    e = SemanticLightingEngine()
    result = e.build_practical_lighting("industrial_hangar", _zones_with_hero())
    assert result["count"] > 0


# ---------------------------------------------------------------------------
# build_volumetric_lighting
# ---------------------------------------------------------------------------

def test_volumetric_has_required_keys():
    e = SemanticLightingEngine()
    result = e.build_volumetric_lighting({"enabled": True, "density": 0.05, "color": [1, 1, 1]})
    for key in ("enabled", "density", "color", "type", "parent"):
        assert key in result, f"Missing key: {key}"


def test_volumetric_enabled_type_is_envlight():
    e = SemanticLightingEngine()
    result = e.build_volumetric_lighting({"enabled": True, "density": 0.05, "color": [1, 1, 1]})
    assert result["type"] == "envlight"
    assert result["enabled"] is True


def test_volumetric_disabled_type_is_none():
    e = SemanticLightingEngine()
    result = e.build_volumetric_lighting({"enabled": False, "density": 0.01, "color": [1, 1, 1]})
    assert result["type"] is None
    assert result["enabled"] is False


def test_volumetric_parent_is_lighting():
    e = SemanticLightingEngine()
    result = e.build_volumetric_lighting({"enabled": True, "density": 0.05, "color": [1, 1, 1]})
    assert result["parent"] == "/obj/lighting"


def test_volumetric_color_is_list():
    e = SemanticLightingEngine()
    result = e.build_volumetric_lighting({"enabled": True, "density": 0.05, "color": [0.9, 0.85, 0.8]})
    assert isinstance(result["color"], list)


# ---------------------------------------------------------------------------
# evaluate_light_balance
# ---------------------------------------------------------------------------

def test_light_balance_returns_dict():
    e = SemanticLightingEngine()
    plan = {"key": {"intensity": 2.5}, "rim": {"intensity": 1.5}, "fill": {"intensity": 0.3}}
    result = e.evaluate_light_balance(plan)
    assert isinstance(result, dict)


def test_light_balance_has_required_keys():
    e = SemanticLightingEngine()
    plan = {"key": {"intensity": 2.5}, "rim": {"intensity": 1.5}, "fill": {"intensity": 0.3}}
    result = e.evaluate_light_balance(plan)
    for key in ("balanced", "balance_score", "issues",
                "key_intensity", "rim_intensity", "fill_intensity"):
        assert key in result, f"Missing key: {key}"


def test_light_balance_good_setup():
    e = SemanticLightingEngine()
    plan = {"key": {"intensity": 2.5}, "rim": {"intensity": 1.5}, "fill": {"intensity": 0.3}}
    result = e.evaluate_light_balance(plan)
    assert result["balanced"] is True
    assert len(result["issues"]) == 0


def test_light_balance_rim_exceeds_key():
    e = SemanticLightingEngine()
    plan = {"key": {"intensity": 1.0}, "rim": {"intensity": 2.0}, "fill": {"intensity": 0.1}}
    result = e.evaluate_light_balance(plan)
    assert result["balanced"] is False
    assert len(result["issues"]) > 0


def test_light_balance_fill_too_bright():
    e = SemanticLightingEngine()
    plan = {"key": {"intensity": 2.0}, "rim": {"intensity": 1.0}, "fill": {"intensity": 1.5}}
    result = e.evaluate_light_balance(plan)
    assert result["balanced"] is False


def test_light_balance_zero_total():
    e = SemanticLightingEngine()
    plan = {"key": {"intensity": 0.0}, "rim": {"intensity": 0.0}, "fill": {"intensity": 0.0}}
    result = e.evaluate_light_balance(plan)
    assert result["balance_score"] == pytest.approx(0.0)


def test_light_balance_score_range():
    e = SemanticLightingEngine()
    plan = {"key": {"intensity": 2.5}, "rim": {"intensity": 1.5}, "fill": {"intensity": 0.3}}
    result = e.evaluate_light_balance(plan)
    assert 0.0 <= result["balance_score"] <= 1.0


def test_light_balance_issues_is_list():
    e = SemanticLightingEngine()
    result = e.evaluate_light_balance({})
    assert isinstance(result["issues"], list)


# ---------------------------------------------------------------------------
# Operations structure
# ---------------------------------------------------------------------------

def test_lighting_ops_include_create_node():
    e = SemanticLightingEngine()
    result = e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial")
    ops = result["operations"]
    create_ops = [o for o in ops if o.get("op") == "create_node"]
    assert len(create_ops) >= 2  # at least key + rim lights


def test_lighting_ops_include_layout_children():
    e = SemanticLightingEngine()
    result = e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial")
    ops = result["operations"]
    layout_ops = [o for o in ops if o.get("op") == "layout_children"]
    assert len(layout_ops) >= 1


def test_lighting_ops_key_parent_is_lighting():
    e = SemanticLightingEngine()
    result = e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial")
    ops = result["operations"]
    create_ops = [o for o in ops if o.get("op") == "create_node"]
    for op in create_ops:
        assert op.get("parent") == "/obj/lighting"


def test_lighting_ops_volumetric_enabled_adds_envlight():
    e = SemanticLightingEngine()
    # cinematic_industrial has volumetric enabled
    result = e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial")
    ops = result["operations"]
    create_ops = [o for o in ops if o.get("op") == "create_node"]
    types = [o.get("type") for o in create_ops]
    assert "envlight" in types


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_has_plan_count():
    e = SemanticLightingEngine()
    assert "plan_count" in e.stats()


def test_stats_starts_zero():
    e = SemanticLightingEngine()
    assert e.stats()["plan_count"] == 0


def test_stats_increments():
    e = SemanticLightingEngine()
    e.generate_lighting_plan(_zones_with_hero(), "cinematic_industrial")
    assert e.stats()["plan_count"] == 1
