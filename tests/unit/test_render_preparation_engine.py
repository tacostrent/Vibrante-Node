"""
Tests for src.runtime.render_preparation_engine
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.render_preparation_engine import (
    RenderPreparationEngine,
    get_render_preparation_engine,
    reset_render_preparation_engine_for_tests,
    _SUPPORTED_RENDERERS,
    _DEFAULT_RENDERER,
    _ARNOLD_BASE_AOVS,
    _ARNOLD_FX_AOVS,
    _KARMA_BASE_AOVS,
    _KARMA_FX_AOVS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_render_preparation_engine_for_tests()
    yield
    reset_render_preparation_engine_for_tests()


def _scene_context_with_geo():
    return {"networks": {"obj": [{"path": "/obj/geo1", "type": "geo"}]}}


def _layout_plan_with_fx():
    return {
        "zones": {"hero_area": ["r1"], "midground": ["c1"], "background": ["w1"]},
        "total_assets": 3,
        "fx_layers": ["pyro_source"],
    }


def _layout_plan_no_fx():
    return {
        "zones": {"hero_area": ["r1"], "midground": ["c1"]},
        "total_assets": 2,
        "fx_layers": [],
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_render_preparation_engine()
    b = get_render_preparation_engine()
    assert a is b


def test_reset_creates_new():
    a = get_render_preparation_engine()
    reset_render_preparation_engine_for_tests()
    b = get_render_preparation_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_supported_renderers_contains_arnold_karma():
    assert "arnold" in _SUPPORTED_RENDERERS
    assert "karma" in _SUPPORTED_RENDERERS


def test_default_renderer_is_arnold():
    assert _DEFAULT_RENDERER == "arnold"


def test_arnold_base_aovs_has_beauty():
    assert "beauty" in _ARNOLD_BASE_AOVS


def test_karma_base_aovs_has_beauty():
    assert "beauty" in _KARMA_BASE_AOVS


def test_arnold_fx_aovs_has_volume():
    assert "volume" in _ARNOLD_FX_AOVS


def test_karma_fx_aovs_has_volume():
    assert "volume" in _KARMA_FX_AOVS


# ---------------------------------------------------------------------------
# generate_render_plan
# ---------------------------------------------------------------------------

def test_render_plan_returns_dict():
    e = RenderPreparationEngine()
    result = e.generate_render_plan({}, "arnold")
    assert isinstance(result, dict)


def test_render_plan_has_required_keys():
    e = RenderPreparationEngine()
    result = e.generate_render_plan({}, "arnold")
    for key in ("plan_id", "renderer", "quality_preset", "renderer_settings",
                "aov_strategy", "complexity", "readiness", "operations", "generated_at"):
        assert key in result, f"Missing key: {key}"


def test_render_plan_unknown_renderer_falls_back():
    e = RenderPreparationEngine()
    result = e.generate_render_plan({}, "unknown_xyz")
    assert result["renderer"] == _DEFAULT_RENDERER


def test_render_plan_karma_renderer():
    e = RenderPreparationEngine()
    result = e.generate_render_plan({}, "karma")
    assert result["renderer"] == "karma"


def test_render_plan_plan_id_is_string():
    e = RenderPreparationEngine()
    result = e.generate_render_plan({}, "arnold")
    assert isinstance(result["plan_id"], str)
    assert len(result["plan_id"]) > 0


def test_render_plan_operations_is_list():
    e = RenderPreparationEngine()
    result = e.generate_render_plan({}, "arnold")
    assert isinstance(result["operations"], list)
    assert len(result["operations"]) > 0


def test_render_plan_operations_contains_create_node():
    e = RenderPreparationEngine()
    result = e.generate_render_plan({}, "arnold")
    ops = result["operations"]
    create_ops = [o for o in ops if o.get("op") == "create_node"]
    assert len(create_ops) >= 1


def test_render_plan_operations_parent_is_out():
    e = RenderPreparationEngine()
    result = e.generate_render_plan({}, "arnold")
    ops = result["operations"]
    create_ops = [o for o in ops if o.get("op") == "create_node"]
    for op in create_ops:
        assert op.get("parent") == "/out"


def test_render_plan_increments_plan_count():
    e = RenderPreparationEngine()
    e.generate_render_plan({}, "arnold")
    e.generate_render_plan({}, "karma")
    assert e.stats()["plan_count"] == 2


def test_render_plan_with_fx_layout_has_fx_aovs():
    e = RenderPreparationEngine()
    result = e.generate_render_plan({}, "arnold", _layout_plan_with_fx())
    aov_names = [a["name"] for a in result["aov_strategy"]]
    for fx_aov in _ARNOLD_FX_AOVS:
        assert fx_aov in aov_names


def test_render_plan_without_fx_no_fx_aovs():
    e = RenderPreparationEngine()
    result = e.generate_render_plan({}, "arnold", _layout_plan_no_fx())
    aov_names = [a["name"] for a in result["aov_strategy"]]
    for fx_aov in _ARNOLD_FX_AOVS:
        assert fx_aov not in aov_names


def test_render_plan_generated_at_is_float():
    e = RenderPreparationEngine()
    result = e.generate_render_plan({}, "arnold")
    assert isinstance(result["generated_at"], float)


# ---------------------------------------------------------------------------
# build_renderer_settings
# ---------------------------------------------------------------------------

def test_renderer_settings_returns_dict():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("arnold", "production")
    assert isinstance(result, dict)


def test_renderer_settings_has_renderer_key():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("arnold", "production")
    assert "renderer" in result
    assert result["renderer"] == "arnold"


def test_renderer_settings_has_quality_preset_key():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("arnold", "production")
    assert "quality_preset" in result
    assert result["quality_preset"] == "production"


def test_renderer_settings_arnold_production_aa_samples():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("arnold", "production")
    assert result["AA_samples"] == 6


def test_renderer_settings_arnold_preview_aa_samples():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("arnold", "preview")
    assert result["AA_samples"] == 3


def test_renderer_settings_arnold_final_aa_samples():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("arnold", "final")
    assert result["AA_samples"] == 10


def test_renderer_settings_karma_production_samples():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("karma", "production")
    assert result["path_trace_samples"] == 256


def test_renderer_settings_karma_final_samples():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("karma", "final")
    assert result["path_trace_samples"] == 1024


def test_renderer_settings_karma_final_xpu_false():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("karma", "final")
    assert result["use_xpu"] is False


def test_renderer_settings_unknown_renderer_falls_back():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("unknown_xyz", "production")
    assert result["renderer"] == "arnold"
    assert "AA_samples" in result


def test_renderer_settings_unknown_quality_falls_back():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("arnold", "unknown_quality")
    assert result["quality_preset"] == "production"


def test_renderer_settings_arnold_production_motion_blur():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("arnold", "production")
    assert result["enable_motion_blur"] is True


def test_renderer_settings_arnold_preview_no_motion_blur():
    e = RenderPreparationEngine()
    result = e.build_renderer_settings("arnold", "preview")
    assert result["enable_motion_blur"] is False


# ---------------------------------------------------------------------------
# build_aov_strategy
# ---------------------------------------------------------------------------

def test_aov_strategy_returns_list():
    e = RenderPreparationEngine()
    result = e.build_aov_strategy("arnold")
    assert isinstance(result, list)


def test_aov_strategy_arnold_base_aovs_present():
    e = RenderPreparationEngine()
    result = e.build_aov_strategy("arnold")
    names = [a["name"] for a in result]
    for aov in _ARNOLD_BASE_AOVS:
        assert aov in names


def test_aov_strategy_karma_base_aovs_present():
    e = RenderPreparationEngine()
    result = e.build_aov_strategy("karma")
    names = [a["name"] for a in result]
    for aov in _KARMA_BASE_AOVS:
        assert aov in names


def test_aov_strategy_base_aovs_required():
    e = RenderPreparationEngine()
    result = e.build_aov_strategy("arnold")
    for aov in result:
        if aov["name"] in _ARNOLD_BASE_AOVS:
            assert aov["required"] is True


def test_aov_strategy_fx_aovs_not_required():
    e = RenderPreparationEngine()
    result = e.build_aov_strategy("arnold", scene_has_fx=True)
    for aov in result:
        if aov["name"] in _ARNOLD_FX_AOVS:
            assert aov["required"] is False


def test_aov_strategy_no_fx_excludes_fx_aovs():
    e = RenderPreparationEngine()
    result = e.build_aov_strategy("arnold", scene_has_fx=False)
    names = [a["name"] for a in result]
    for fx_aov in _ARNOLD_FX_AOVS:
        assert fx_aov not in names


def test_aov_strategy_unknown_renderer_falls_back():
    e = RenderPreparationEngine()
    result = e.build_aov_strategy("unknown_xyz")
    # Falls back to Arnold
    names = [a["name"] for a in result]
    assert "beauty" in names


def test_aov_strategy_each_has_type_aov():
    e = RenderPreparationEngine()
    result = e.build_aov_strategy("arnold")
    for aov in result:
        assert aov["type"] == "aov"


def test_aov_strategy_each_has_renderer():
    e = RenderPreparationEngine()
    result = e.build_aov_strategy("arnold")
    for aov in result:
        assert aov["renderer"] == "arnold"


# ---------------------------------------------------------------------------
# estimate_render_complexity
# ---------------------------------------------------------------------------

def test_complexity_returns_dict():
    e = RenderPreparationEngine()
    result = e.estimate_render_complexity()
    assert isinstance(result, dict)


def test_complexity_has_required_keys():
    e = RenderPreparationEngine()
    result = e.estimate_render_complexity()
    for key in ("complexity_level", "complexity_score",
                "estimated_render_time", "notes"):
        assert key in result, f"Missing key: {key}"


def test_complexity_no_params_is_low():
    e = RenderPreparationEngine()
    result = e.estimate_render_complexity()
    assert result["complexity_level"] == "low"


def test_complexity_high_asset_count():
    e = RenderPreparationEngine()
    layout = {"total_assets": 40, "zones": {"a": [], "b": [], "c": []}, "fx_layers": []}
    result = e.estimate_render_complexity(layout_plan=layout)
    assert result["complexity_level"] in ("medium", "high", "extreme")


def test_complexity_with_volumetric_adds_score():
    e = RenderPreparationEngine()
    lighting = {"volumetric": {"enabled": True}}
    result = e.estimate_render_complexity(lighting_plan=lighting)
    assert result["complexity_score"] >= 5.0


def test_complexity_with_atmosphere_adds_score():
    e = RenderPreparationEngine()
    atmosphere = {"recommended_density": 0.04}
    result = e.estimate_render_complexity(atmosphere_plan=atmosphere)
    assert result["complexity_score"] >= 3.0


def test_complexity_score_is_numeric():
    e = RenderPreparationEngine()
    result = e.estimate_render_complexity()
    assert isinstance(result["complexity_score"], (int, float))


def test_complexity_notes_is_list():
    e = RenderPreparationEngine()
    result = e.estimate_render_complexity()
    assert isinstance(result["notes"], list)


def test_complexity_high_density_adds_note():
    e = RenderPreparationEngine()
    atmosphere = {"recommended_density": 0.08}
    result = e.estimate_render_complexity(atmosphere_plan=atmosphere)
    assert len(result["notes"]) > 0


def test_complexity_levels_progression():
    e = RenderPreparationEngine()
    # Very large scene should be extreme
    layout = {"total_assets": 100, "zones": {"a": [], "b": [], "c": [], "d": [], "e": []},
              "fx_layers": ["p1", "p2", "p3", "p4", "p5"]}
    lighting = {"volumetric": {"enabled": True}}
    result = e.estimate_render_complexity(layout_plan=layout, lighting_plan=lighting)
    assert result["complexity_level"] == "extreme"


# ---------------------------------------------------------------------------
# validate_render_readiness
# ---------------------------------------------------------------------------

def test_readiness_returns_dict():
    e = RenderPreparationEngine()
    render_plan = e.generate_render_plan({}, "arnold")
    result = e.validate_render_readiness({}, render_plan)
    assert isinstance(result, dict)


def test_readiness_has_required_keys():
    e = RenderPreparationEngine()
    render_plan = e.generate_render_plan({}, "arnold")
    result = e.validate_render_readiness({}, render_plan)
    for key in ("ready", "checks", "warnings", "blocking_issues"):
        assert key in result, f"Missing key: {key}"


def test_readiness_checks_is_dict():
    e = RenderPreparationEngine()
    render_plan = e.generate_render_plan({}, "arnold")
    result = e.validate_render_readiness({}, render_plan)
    assert isinstance(result["checks"], dict)


def test_readiness_checks_has_expected_keys():
    e = RenderPreparationEngine()
    render_plan = e.generate_render_plan({}, "arnold")
    result = e.validate_render_readiness({}, render_plan)
    for key in ("has_renderer", "has_geometry", "has_camera", "has_aovs", "output_format"):
        assert key in result["checks"], f"Missing check: {key}"


def test_readiness_has_renderer_true_for_arnold():
    e = RenderPreparationEngine()
    render_plan = e.generate_render_plan({}, "arnold")
    result = e.validate_render_readiness({}, render_plan)
    assert result["checks"]["has_renderer"] is True


def test_readiness_has_aovs_true():
    e = RenderPreparationEngine()
    render_plan = e.generate_render_plan({}, "arnold")
    result = e.validate_render_readiness({}, render_plan)
    assert result["checks"]["has_aovs"] is True


def test_readiness_no_scene_context_adds_warning():
    e = RenderPreparationEngine()
    render_plan = e.generate_render_plan({}, "arnold")
    result = e.validate_render_readiness(None, render_plan)
    assert len(result["warnings"]) > 0


def test_readiness_scene_with_geo_has_geometry():
    e = RenderPreparationEngine()
    render_plan = e.generate_render_plan(_scene_context_with_geo(), "arnold")
    result = e.validate_render_readiness(_scene_context_with_geo(), render_plan)
    assert result["checks"]["has_geometry"] is True


def test_readiness_empty_scene_no_geometry():
    e = RenderPreparationEngine()
    render_plan = e.generate_render_plan({}, "arnold")
    result = e.validate_render_readiness({"networks": {"obj": []}}, render_plan)
    assert result["checks"]["has_geometry"] is False


def test_readiness_ready_is_bool():
    e = RenderPreparationEngine()
    render_plan = e.generate_render_plan({}, "arnold")
    result = e.validate_render_readiness({}, render_plan)
    assert isinstance(result["ready"], bool)


def test_readiness_warnings_is_list():
    e = RenderPreparationEngine()
    render_plan = e.generate_render_plan({}, "arnold")
    result = e.validate_render_readiness({}, render_plan)
    assert isinstance(result["warnings"], list)


def test_readiness_blocking_issues_is_list():
    e = RenderPreparationEngine()
    render_plan = e.generate_render_plan({}, "arnold")
    result = e.validate_render_readiness({}, render_plan)
    assert isinstance(result["blocking_issues"], list)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_has_plan_count():
    e = RenderPreparationEngine()
    assert "plan_count" in e.stats()


def test_stats_starts_zero():
    e = RenderPreparationEngine()
    assert e.stats()["plan_count"] == 0


def test_stats_increments_on_render_plan():
    e = RenderPreparationEngine()
    e.generate_render_plan({}, "arnold")
    assert e.stats()["plan_count"] == 1


def test_stats_increments_multiple():
    e = RenderPreparationEngine()
    e.generate_render_plan({}, "arnold")
    e.generate_render_plan({}, "karma")
    e.generate_render_plan({}, "arnold")
    assert e.stats()["plan_count"] == 3
