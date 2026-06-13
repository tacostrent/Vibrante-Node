"""
Tests for src.runtime.environment_rules
No bridge, no LLM.  Pure unit tests.
"""
import pytest
from src.runtime.environment_rules import (
    EnvironmentRules,
    get_environment_rules,
    reset_environment_rules_for_tests,
    _ENVIRONMENT_RULES,
    _DEFAULT_RULES,
)


@pytest.fixture(autouse=True)
def reset():
    reset_environment_rules_for_tests()
    yield
    reset_environment_rules_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_environment_rules()
    b = get_environment_rules()
    assert a is b


def test_reset_creates_new():
    a = get_environment_rules()
    reset_environment_rules_for_tests()
    b = get_environment_rules()
    assert a is not b


# ---------------------------------------------------------------------------
# Built-in environments — presence & structure
# ---------------------------------------------------------------------------

def test_all_builtin_environments_present():
    er = EnvironmentRules()
    supported = er.get_supported_environments()
    for env_id in _ENVIRONMENT_RULES:
        assert env_id in supported, f"Missing environment: {env_id}"


def test_supported_environments_is_sorted():
    er = EnvironmentRules()
    supported = er.get_supported_environments()
    assert supported == sorted(supported)


def test_each_builtin_has_required_keys():
    required = {
        "hero_zone", "lighting_style", "fog_density",
        "camera_hints", "fx_recommendations", "depth_layers",
        "scale", "atmosphere",
    }
    er = EnvironmentRules()
    for env_id in _ENVIRONMENT_RULES:
        rules = er.get_rules(env_id)
        for key in required:
            assert key in rules, f"'{env_id}' missing key: '{key}'"


def test_industrial_hangar_rules():
    er = EnvironmentRules()
    r  = er.get_rules("industrial_hangar")
    assert r["hero_zone"]   == "center"
    assert r["fog_density"] == "medium"
    assert "volumetric_fog" in r["fx_recommendations"]
    assert r["scale"] == "large"


def test_sci_fi_corridor_rules():
    er = EnvironmentRules()
    r  = er.get_rules("sci_fi_corridor")
    assert r["lighting_style"] == "neon_accent"
    assert "neon_glow" in r["fx_recommendations"]
    assert r["fog_density"] == "light"


def test_abandoned_factory_rules():
    er = EnvironmentRules()
    r  = er.get_rules("abandoned_factory")
    assert r["fog_density"] == "heavy"
    assert r["atmosphere"]  == "post_apocalyptic"


def test_robotics_lab_rules():
    er = EnvironmentRules()
    r  = er.get_rules("robotics_lab")
    assert r["fog_density"]    == "none"
    assert r["lighting_style"] == "clean_white"
    assert "holographic_ui" in r["fx_recommendations"]


def test_cinematic_control_room_rules():
    er = EnvironmentRules()
    r  = er.get_rules("cinematic_control_room")
    assert r["lighting_style"] == "dramatic_screen_glow"
    assert r["fog_density"]    == "none"
    assert "screen_glow" in r["fx_recommendations"]


# ---------------------------------------------------------------------------
# get_rules fallback & copy safety
# ---------------------------------------------------------------------------

def test_get_rules_unknown_returns_defaults():
    er = EnvironmentRules()
    r  = er.get_rules("completely_unknown_environment")
    assert r["hero_zone"]   == _DEFAULT_RULES["hero_zone"]
    assert r["fog_density"] == _DEFAULT_RULES["fog_density"]


def test_get_rules_returns_copy():
    er = EnvironmentRules()
    r1 = er.get_rules("industrial_hangar")
    r1["hero_zone"] = "mutated"
    r2 = er.get_rules("industrial_hangar")
    assert r2["hero_zone"] != "mutated"


# ---------------------------------------------------------------------------
# apply_rules
# ---------------------------------------------------------------------------

def test_apply_rules_populates_layout_rules():
    er   = EnvironmentRules()
    plan = {"zones": {}, "layout_rules": {}}
    out  = er.apply_rules("industrial_hangar", plan)
    assert out["layout_rules"]["hero_focus"]     == "center"
    assert out["layout_rules"]["fog_density"]    == "medium"
    assert out["layout_rules"]["lighting_style"] == "practical_industrial"
    assert out["layout_rules"]["scale"]          == "large"


def test_apply_rules_adds_fx_and_camera_hints():
    er  = EnvironmentRules()
    out = er.apply_rules("industrial_hangar", {"zones": {}})
    assert "volumetric_fog" in out["recommended_fx"]
    assert "low_angle_hero" in out["camera_hints"]


def test_apply_rules_preserves_existing_extra_keys():
    er   = EnvironmentRules()
    plan = {"zones": {}, "custom_key": "preserved"}
    out  = er.apply_rules("robotics_lab", plan)
    assert out["custom_key"] == "preserved"


def test_apply_rules_does_not_mutate_input():
    er   = EnvironmentRules()
    plan = {"zones": {}, "layout_rules": {"custom": "value"}}
    er.apply_rules("industrial_hangar", plan)
    assert "hero_focus" not in plan.get("layout_rules", {})


def test_apply_rules_unknown_env_uses_defaults():
    er  = EnvironmentRules()
    out = er.apply_rules("nonexistent_env", {"zones": {}})
    assert out["layout_rules"]["fog_density"] == _DEFAULT_RULES["fog_density"]


# ---------------------------------------------------------------------------
# Lighting & FX recommendation helpers
# ---------------------------------------------------------------------------

def test_get_lighting_recommendation_known():
    er = EnvironmentRules()
    assert er.get_lighting_recommendation("robotics_lab")     == "clean_white"
    assert er.get_lighting_recommendation("sci_fi_corridor")  == "neon_accent"
    assert er.get_lighting_recommendation("abandoned_factory") == "natural_decay"


def test_get_lighting_recommendation_unknown_returns_string():
    er = EnvironmentRules()
    result = er.get_lighting_recommendation("not_an_environment")
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_fx_recommendation_industrial_hangar():
    er = EnvironmentRules()
    fx = er.get_fx_recommendation("industrial_hangar")
    assert isinstance(fx, list)
    assert "volumetric_fog" in fx
    assert "dust_particles" in fx


def test_get_fx_recommendation_returns_copy():
    er  = EnvironmentRules()
    fx1 = er.get_fx_recommendation("industrial_hangar")
    fx1.append("injected_fx")
    fx2 = er.get_fx_recommendation("industrial_hangar")
    assert "injected_fx" not in fx2


def test_get_fx_recommendation_unknown_returns_empty_list():
    er = EnvironmentRules()
    fx = er.get_fx_recommendation("not_real")
    assert fx == []


# ---------------------------------------------------------------------------
# register_environment
# ---------------------------------------------------------------------------

def test_register_custom_environment():
    er = EnvironmentRules()
    er.register_environment("outdoor_plaza", {
        "hero_zone":          "fountain_center",
        "lighting_style":     "natural_daylight",
        "fog_density":        "none",
        "camera_hints":       ["wide_street", "hero_low"],
        "fx_recommendations": ["wind_debris"],
        "depth_layers":       ["hero_area", "midground", "background"],
        "scale":              "large",
        "atmosphere":         "urban_outdoor",
        "asset_placements":   {},
    })
    assert "outdoor_plaza" in er.get_supported_environments()
    assert er.get_rules("outdoor_plaza")["hero_zone"] == "fountain_center"


def test_register_overwrites_existing_custom():
    er = EnvironmentRules()
    er.register_environment("env_x", {"lighting_style": "old", "hero_zone": "a",
                                       "fog_density": "none", "camera_hints": [],
                                       "fx_recommendations": [], "depth_layers": [],
                                       "scale": "small", "atmosphere": "test",
                                       "asset_placements": {}})
    er.register_environment("env_x", {"lighting_style": "new", "hero_zone": "b",
                                       "fog_density": "light", "camera_hints": [],
                                       "fx_recommendations": [], "depth_layers": [],
                                       "scale": "large", "atmosphere": "updated",
                                       "asset_placements": {}})
    assert er.get_rules("env_x")["lighting_style"] == "new"


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    er = EnvironmentRules()
    s  = er.stats()
    assert "environment_count" in s
    assert s["environment_count"] >= len(_ENVIRONMENT_RULES)


def test_stats_increases_after_register():
    er    = EnvironmentRules()
    count = er.stats()["environment_count"]
    er.register_environment("extra_env", {
        "hero_zone": "x", "lighting_style": "x", "fog_density": "x",
        "camera_hints": [], "fx_recommendations": [], "depth_layers": [],
        "scale": "x", "atmosphere": "x", "asset_placements": {},
    })
    assert er.stats()["environment_count"] == count + 1
