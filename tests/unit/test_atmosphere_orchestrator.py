"""
Tests for src.runtime.atmosphere_orchestrator
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.atmosphere_orchestrator import (
    AtmosphereOrchestrator,
    get_atmosphere_orchestrator,
    reset_atmosphere_orchestrator_for_tests,
    _ATMOSPHERE_TYPES,
    _DEFAULT_TYPE,
)


@pytest.fixture(autouse=True)
def reset():
    reset_atmosphere_orchestrator_for_tests()
    yield
    reset_atmosphere_orchestrator_for_tests()


def _zone_depths():
    return {"hero_area": 0.0, "midground": -10.0, "background": -30.0}


def _layout_rules(fog_density="medium"):
    return {"fog_density": fog_density}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_atmosphere_orchestrator()
    b = get_atmosphere_orchestrator()
    assert a is b


def test_reset_creates_new():
    a = get_atmosphere_orchestrator()
    reset_atmosphere_orchestrator_for_tests()
    b = get_atmosphere_orchestrator()
    assert a is not b


# ---------------------------------------------------------------------------
# _ATMOSPHERE_TYPES constant
# ---------------------------------------------------------------------------

def test_atmosphere_types_has_required_keys():
    required = {"industrial_fog", "volumetric_scifi", "dusty_hangar",
                "cold_atmosphere", "cinematic_depth_fog"}
    assert required <= set(_ATMOSPHERE_TYPES.keys())


def test_default_type_exists():
    assert _DEFAULT_TYPE in _ATMOSPHERE_TYPES


def test_each_preset_has_density_and_particle():
    for name, preset in _ATMOSPHERE_TYPES.items():
        assert "density" in preset, f"Missing 'density' in preset '{name}'"
        assert "particle" in preset, f"Missing 'particle' in preset '{name}'"


# ---------------------------------------------------------------------------
# generate_fog_layers
# ---------------------------------------------------------------------------

def test_fog_layers_returns_list():
    o = AtmosphereOrchestrator()
    result = o.generate_fog_layers("industrial_fog", 0.04, _zone_depths())
    assert isinstance(result, list)


def test_fog_layers_one_per_zone():
    o = AtmosphereOrchestrator()
    result = o.generate_fog_layers("industrial_fog", 0.04, _zone_depths())
    assert len(result) == 3


def test_fog_layers_parent_is_environment():
    o = AtmosphereOrchestrator()
    result = o.generate_fog_layers("industrial_fog", 0.04, _zone_depths())
    for layer in result:
        assert layer["parent"] == "/obj/environment"


def test_fog_layers_type_is_vdbfrompolygons():
    o = AtmosphereOrchestrator()
    result = o.generate_fog_layers("industrial_fog", 0.04, _zone_depths())
    for layer in result:
        assert layer["type"] == "vdbfrompolygons"


def test_fog_layers_has_zone_key():
    o = AtmosphereOrchestrator()
    result = o.generate_fog_layers("industrial_fog", 0.04, _zone_depths())
    zones_found = {layer["zone"] for layer in result}
    assert "background" in zones_found
    assert "hero_area" in zones_found


def test_fog_layers_background_denser_than_hero():
    o = AtmosphereOrchestrator()
    result = o.generate_fog_layers("industrial_fog", 0.04, _zone_depths())
    bg_layer = next(l for l in result if l["zone"] == "background")
    hero_layer = next(l for l in result if l["zone"] == "hero_area")
    assert bg_layer["density"] > hero_layer["density"]


def test_fog_layers_empty_zone_depths_returns_empty():
    o = AtmosphereOrchestrator()
    result = o.generate_fog_layers("industrial_fog", 0.04, {})
    assert result == []


def test_fog_layers_unknown_type_falls_back():
    o = AtmosphereOrchestrator()
    # Should not raise; falls back to _DEFAULT_TYPE
    result = o.generate_fog_layers("unknown_xyz", 0.04, _zone_depths())
    assert isinstance(result, list)
    assert len(result) == 3


def test_fog_layers_op_is_create_node():
    o = AtmosphereOrchestrator()
    result = o.generate_fog_layers("industrial_fog", 0.04, _zone_depths())
    for layer in result:
        assert layer["op"] == "create_node"


# ---------------------------------------------------------------------------
# generate_depth_atmosphere
# ---------------------------------------------------------------------------

def test_depth_atmosphere_returns_dict():
    o = AtmosphereOrchestrator()
    result = o.generate_depth_atmosphere({}, _layout_rules("medium"))
    assert isinstance(result, dict)


def test_depth_atmosphere_has_required_keys():
    o = AtmosphereOrchestrator()
    result = o.generate_depth_atmosphere({}, _layout_rules("medium"))
    for key in ("atmosphere_type", "recommended_density", "depth_support",
                "zone_coverage", "readability_risk", "notes"):
        assert key in result, f"Missing key: {key}"


def test_depth_atmosphere_fog_density_none():
    o = AtmosphereOrchestrator()
    result = o.generate_depth_atmosphere({}, _layout_rules("none"))
    assert result["recommended_density"] == 0.0


def test_depth_atmosphere_fog_density_light():
    o = AtmosphereOrchestrator()
    result = o.generate_depth_atmosphere({}, _layout_rules("light"))
    assert result["recommended_density"] == pytest.approx(0.02)


def test_depth_atmosphere_fog_density_medium():
    o = AtmosphereOrchestrator()
    result = o.generate_depth_atmosphere({}, _layout_rules("medium"))
    assert result["recommended_density"] == pytest.approx(0.04)


def test_depth_atmosphere_fog_density_heavy():
    o = AtmosphereOrchestrator()
    result = o.generate_depth_atmosphere({}, _layout_rules("heavy"))
    assert result["recommended_density"] == pytest.approx(0.08)


def test_depth_atmosphere_increments_plan_count():
    o = AtmosphereOrchestrator()
    o.generate_depth_atmosphere({}, _layout_rules("medium"))
    o.generate_depth_atmosphere({}, _layout_rules("light"))
    assert o.stats()["plan_count"] == 2


def test_depth_atmosphere_zone_coverage_is_dict():
    o = AtmosphereOrchestrator()
    zones = {"hero_area": [], "background": []}
    result = o.generate_depth_atmosphere(zones, _layout_rules("medium"))
    assert isinstance(result["zone_coverage"], dict)


def test_depth_atmosphere_readability_risk_string():
    o = AtmosphereOrchestrator()
    result = o.generate_depth_atmosphere({}, _layout_rules("heavy"))
    assert isinstance(result["readability_risk"], str)


def test_depth_atmosphere_heavy_is_high_risk():
    o = AtmosphereOrchestrator()
    result = o.generate_depth_atmosphere({}, _layout_rules("heavy"))
    assert result["readability_risk"] == "high"


def test_depth_atmosphere_light_is_low_risk():
    o = AtmosphereOrchestrator()
    result = o.generate_depth_atmosphere({}, _layout_rules("light"))
    assert result["readability_risk"] == "low"


# ---------------------------------------------------------------------------
# generate_volumetric_density
# ---------------------------------------------------------------------------

def test_volumetric_density_has_required_keys():
    o = AtmosphereOrchestrator()
    result = o.generate_volumetric_density("industrial_fog")
    for key in ("enabled", "density", "scatter_multiplier", "absorption",
                "emission", "color", "notes"):
        assert key in result, f"Missing key: {key}"


def test_volumetric_density_no_lighting_scatter_1_0():
    o = AtmosphereOrchestrator()
    result = o.generate_volumetric_density("industrial_fog", lighting_plan=None)
    assert result["scatter_multiplier"] == pytest.approx(1.0)


def test_volumetric_density_vol_enabled_scatter_1_2():
    o = AtmosphereOrchestrator()
    lighting = {"volumetric": {"enabled": True}}
    result = o.generate_volumetric_density("industrial_fog", lighting_plan=lighting)
    assert result["scatter_multiplier"] == pytest.approx(1.2)


def test_volumetric_density_vol_disabled_scatter_0_8():
    o = AtmosphereOrchestrator()
    lighting = {"volumetric": {"enabled": False}}
    result = o.generate_volumetric_density("industrial_fog", lighting_plan=lighting)
    assert result["scatter_multiplier"] == pytest.approx(0.8)


def test_volumetric_density_enabled_is_bool():
    o = AtmosphereOrchestrator()
    result = o.generate_volumetric_density("industrial_fog")
    assert isinstance(result["enabled"], bool)


def test_volumetric_density_color_is_list():
    o = AtmosphereOrchestrator()
    result = o.generate_volumetric_density("industrial_fog")
    assert isinstance(result["color"], list)


def test_volumetric_density_cold_atmosphere_not_enabled():
    o = AtmosphereOrchestrator()
    result = o.generate_volumetric_density("cold_atmosphere")
    assert result["enabled"] is False


def test_volumetric_density_industrial_fog_enabled():
    o = AtmosphereOrchestrator()
    result = o.generate_volumetric_density("industrial_fog")
    assert result["enabled"] is True


# ---------------------------------------------------------------------------
# build_particle_layers
# ---------------------------------------------------------------------------

def test_particle_layers_returns_list():
    o = AtmosphereOrchestrator()
    result = o.build_particle_layers("industrial_hangar", "industrial_fog")
    assert isinstance(result, list)


def test_particle_layers_nonempty_for_dust():
    o = AtmosphereOrchestrator()
    result = o.build_particle_layers("industrial_hangar", "industrial_fog")
    # industrial_fog has particle="dust"
    assert len(result) > 0


def test_particle_layers_empty_for_none():
    o = AtmosphereOrchestrator()
    result = o.build_particle_layers("test", "cinematic_depth_fog")
    # cinematic_depth_fog has particle="none"
    assert result == []


def test_particle_layers_unknown_type_returns_empty():
    o = AtmosphereOrchestrator()
    result = o.build_particle_layers("test", "unknown_xyz")
    assert result == []


def test_particle_layers_op_is_create_node():
    o = AtmosphereOrchestrator()
    result = o.build_particle_layers("industrial_hangar", "industrial_fog")
    if result:
        assert result[0]["op"] == "create_node"


def test_particle_layers_type_is_popnet():
    o = AtmosphereOrchestrator()
    result = o.build_particle_layers("industrial_hangar", "industrial_fog")
    if result:
        assert result[0]["type"] == "popnet"


def test_particle_layers_parent_is_fx():
    o = AtmosphereOrchestrator()
    result = o.build_particle_layers("industrial_hangar", "industrial_fog")
    if result:
        assert result[0]["parent"] == "/obj/fx"


# ---------------------------------------------------------------------------
# evaluate_atmospheric_readability
# ---------------------------------------------------------------------------

def test_evaluate_readability_returns_dict():
    o = AtmosphereOrchestrator()
    plan = o.generate_depth_atmosphere({}, _layout_rules("medium"))
    result = o.evaluate_atmospheric_readability(plan)
    assert isinstance(result, dict)


def test_evaluate_readability_has_required_keys():
    o = AtmosphereOrchestrator()
    plan = o.generate_depth_atmosphere({}, _layout_rules("medium"))
    result = o.evaluate_atmospheric_readability(plan)
    for key in ("readable", "readability_score", "issues", "strengths"):
        assert key in result, f"Missing key: {key}"


def test_evaluate_readability_readable_is_bool():
    o = AtmosphereOrchestrator()
    plan = o.generate_depth_atmosphere({}, _layout_rules("medium"))
    result = o.evaluate_atmospheric_readability(plan)
    assert isinstance(result["readable"], bool)


def test_evaluate_readability_score_is_float():
    o = AtmosphereOrchestrator()
    plan = o.generate_depth_atmosphere({}, _layout_rules("medium"))
    result = o.evaluate_atmospheric_readability(plan)
    assert isinstance(result["readability_score"], (int, float))


def test_evaluate_readability_issues_is_list():
    o = AtmosphereOrchestrator()
    plan = o.generate_depth_atmosphere({}, _layout_rules("medium"))
    result = o.evaluate_atmospheric_readability(plan)
    assert isinstance(result["issues"], list)


def test_evaluate_readability_strengths_is_list():
    o = AtmosphereOrchestrator()
    plan = o.generate_depth_atmosphere({}, _layout_rules("medium"))
    result = o.evaluate_atmospheric_readability(plan)
    assert isinstance(result["strengths"], list)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_has_plan_count():
    o = AtmosphereOrchestrator()
    s = o.stats()
    assert "plan_count" in s


def test_stats_starts_zero():
    o = AtmosphereOrchestrator()
    assert o.stats()["plan_count"] == 0


def test_stats_increments_on_fog_layers():
    o = AtmosphereOrchestrator()
    o.generate_fog_layers("industrial_fog", 0.04, _zone_depths())
    assert o.stats()["plan_count"] >= 1


def test_stats_increments_on_depth_atmosphere():
    o = AtmosphereOrchestrator()
    o.generate_depth_atmosphere({}, _layout_rules())
    o.generate_depth_atmosphere({}, _layout_rules())
    assert o.stats()["plan_count"] == 2


def test_stats_volumetric_density_increments():
    o = AtmosphereOrchestrator()
    o.generate_volumetric_density("industrial_fog")
    assert o.stats()["plan_count"] >= 1
