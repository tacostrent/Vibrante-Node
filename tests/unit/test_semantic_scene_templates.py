"""
Tests for src.runtime.semantic_scene_templates
No bridge, no LLM.  Pure unit tests.
"""
import pytest
from src.runtime.semantic_scene_templates import (
    SemanticSceneTemplates,
    get_semantic_scene_templates,
    reset_semantic_scene_templates_for_tests,
    _BUILTIN_TEMPLATES,
    _REQUIRED_FIELDS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_semantic_scene_templates_for_tests()
    yield
    reset_semantic_scene_templates_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_semantic_scene_templates()
    b = get_semantic_scene_templates()
    assert a is b


def test_reset_creates_new():
    a = get_semantic_scene_templates()
    reset_semantic_scene_templates_for_tests()
    b = get_semantic_scene_templates()
    assert a is not b


# ---------------------------------------------------------------------------
# Built-in templates — presence & structure
# ---------------------------------------------------------------------------

def test_all_builtin_templates_present():
    sst = SemanticSceneTemplates()
    listed_ids = {t["id"] for t in sst.list_templates()}
    for tid in _BUILTIN_TEMPLATES:
        assert tid in listed_ids, f"Missing built-in template: {tid}"


def test_each_builtin_has_required_fields():
    sst = SemanticSceneTemplates()
    for tid in _BUILTIN_TEMPLATES:
        tmpl = sst.get_template(tid)
        assert tmpl is not None
        for field in _REQUIRED_FIELDS:
            assert field in tmpl, f"Template '{tid}' missing required field: '{field}'"


def test_builtin_cinematic_industrial_hangar():
    sst = SemanticSceneTemplates()
    t = sst.get_template("cinematic_industrial_hangar")
    assert t["environment"]    == "industrial_hangar"
    assert t["lighting_style"] == "practical_industrial"
    assert any(l["type"] == "volumetric_fog" for l in t["fx_layers"])


def test_builtin_robotics_repair_facility():
    sst = SemanticSceneTemplates()
    t = sst.get_template("robotics_repair_facility")
    assert t["environment"]    == "robotics_lab"
    assert t["lighting_style"] == "clean_white"
    assert any(l["type"] == "holographic_ui" for l in t["fx_layers"])


def test_builtin_atmospheric_scifi_corridor():
    sst = SemanticSceneTemplates()
    t = sst.get_template("atmospheric_scifi_corridor")
    assert t["environment"]    == "sci_fi_corridor"
    assert t["lighting_style"] == "neon_accent"
    assert any(l["type"] == "neon_glow" for l in t["fx_layers"])


def test_builtin_cinematic_control_room():
    sst = SemanticSceneTemplates()
    t = sst.get_template("cinematic_control_room")
    assert t["environment"]    == "cinematic_control_room"
    assert t["lighting_style"] == "dramatic_screen_glow"
    assert any(l["type"] == "screen_glow" for l in t["fx_layers"])


# ---------------------------------------------------------------------------
# get_template
# ---------------------------------------------------------------------------

def test_get_template_unknown_returns_none():
    sst = SemanticSceneTemplates()
    assert sst.get_template("does_not_exist") is None


def test_get_template_returns_copy():
    sst = SemanticSceneTemplates()
    t1 = sst.get_template("cinematic_industrial_hangar")
    t1["lighting_style"] = "mutated"
    t2 = sst.get_template("cinematic_industrial_hangar")
    assert t2["lighting_style"] != "mutated"


# ---------------------------------------------------------------------------
# list_templates
# ---------------------------------------------------------------------------

def test_list_templates_summary_keys():
    sst = SemanticSceneTemplates()
    for summary in sst.list_templates():
        required = {"id", "name", "description", "tags", "environment", "scene_intent"}
        assert required <= set(summary.keys()), f"Missing key in summary for {summary.get('id')}"


def test_list_templates_sorted_by_id():
    sst = SemanticSceneTemplates()
    ids = [t["id"] for t in sst.list_templates()]
    assert ids == sorted(ids)


def test_list_templates_tag_filter():
    sst = SemanticSceneTemplates()
    industrial = sst.list_templates(tag="industrial")
    assert len(industrial) >= 1
    for t in industrial:
        assert "industrial" in t["tags"] or t["id"] == "cinematic_industrial_hangar"


def test_list_templates_tag_no_match():
    sst = SemanticSceneTemplates()
    result = sst.list_templates(tag="nonexistent_tag_xyz")
    assert result == []


# ---------------------------------------------------------------------------
# register_template
# ---------------------------------------------------------------------------

_CUSTOM_TEMPLATE = {
    "scene_intent":               "test_staging",
    "environment":                "robotics_lab",
    "preferred_asset_categories": ["robot", "tools"],
    "lighting_style":             "test_light",
    "fx_layers":                  [{"type": "test_fx", "density": "light", "priority": 1}],
    "camera_logic":               {"primary_shot": "eye_level", "depth_of_field": False},
    "name":                       "Test Template",
    "description":                "A test template.",
    "tags":                       ["test"],
}


def test_register_custom_template():
    sst = SemanticSceneTemplates()
    sst.register_template("custom_test_env", _CUSTOM_TEMPLATE)
    assert sst.get_template("custom_test_env") is not None


def test_register_sets_id_field():
    sst = SemanticSceneTemplates()
    sst.register_template("my_custom", _CUSTOM_TEMPLATE)
    t = sst.get_template("my_custom")
    assert t["id"] == "my_custom"


def test_register_appears_in_list():
    sst = SemanticSceneTemplates()
    sst.register_template("my_custom", _CUSTOM_TEMPLATE)
    ids = [t["id"] for t in sst.list_templates()]
    assert "my_custom" in ids


def test_register_missing_required_field_raises():
    sst = SemanticSceneTemplates()
    incomplete = {k: v for k, v in _CUSTOM_TEMPLATE.items() if k != "lighting_style"}
    with pytest.raises(ValueError, match="lighting_style"):
        sst.register_template("bad_template", incomplete)


def test_register_overwrites_custom():
    sst = SemanticSceneTemplates()
    sst.register_template("overwrite_me", _CUSTOM_TEMPLATE)
    updated = dict(_CUSTOM_TEMPLATE, lighting_style="updated_style")
    sst.register_template("overwrite_me", updated)
    t = sst.get_template("overwrite_me")
    assert t["lighting_style"] == "updated_style"


# ---------------------------------------------------------------------------
# deregister_template
# ---------------------------------------------------------------------------

def test_deregister_custom_template():
    sst = SemanticSceneTemplates()
    sst.register_template("to_remove", _CUSTOM_TEMPLATE)
    removed = sst.deregister_template("to_remove")
    assert removed is True
    assert sst.get_template("to_remove") is None


def test_deregister_returns_false_if_not_found():
    sst = SemanticSceneTemplates()
    assert sst.deregister_template("nonexistent_template") is False


def test_deregister_builtin_raises():
    sst = SemanticSceneTemplates()
    with pytest.raises(ValueError):
        sst.deregister_template("cinematic_industrial_hangar")


def test_deregister_builtin_still_present_after_failed_attempt():
    sst = SemanticSceneTemplates()
    try:
        sst.deregister_template("robotics_repair_facility")
    except ValueError:
        pass
    assert sst.get_template("robotics_repair_facility") is not None


# ---------------------------------------------------------------------------
# apply_template
# ---------------------------------------------------------------------------

def test_apply_template_no_interpolation():
    sst = SemanticSceneTemplates()
    result = sst.apply_template("cinematic_industrial_hangar", {})
    assert result["environment"] == "industrial_hangar"
    assert result["lighting_style"] == "practical_industrial"


def test_apply_template_with_interpolation():
    sst = SemanticSceneTemplates()
    template_with_vars = dict(_CUSTOM_TEMPLATE, lighting_style="style_{custom_var}")
    sst.register_template("interpolation_test", template_with_vars)
    result = sst.apply_template("interpolation_test", {"custom_var": "dynamic"})
    assert result["lighting_style"] == "style_dynamic"


def test_apply_template_missing_variable_raises():
    sst = SemanticSceneTemplates()
    template_with_vars = dict(_CUSTOM_TEMPLATE, lighting_style="style_{missing_var}")
    sst.register_template("missing_var_test", template_with_vars)
    with pytest.raises(ValueError, match="missing_var"):
        sst.apply_template("missing_var_test", {})


def test_apply_template_unknown_id_raises():
    sst = SemanticSceneTemplates()
    with pytest.raises(KeyError):
        sst.apply_template("no_such_template", {})


def test_apply_template_result_has_required_fields():
    sst = SemanticSceneTemplates()
    result = sst.apply_template("atmospheric_scifi_corridor", {})
    for field in _REQUIRED_FIELDS:
        assert field in result


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    sst = SemanticSceneTemplates()
    s = sst.stats()
    assert "total_templates" in s
    assert "builtin_count" in s
    assert "custom_count" in s


def test_stats_builtin_count_matches():
    sst = SemanticSceneTemplates()
    s = sst.stats()
    assert s["builtin_count"] == len(_BUILTIN_TEMPLATES)


def test_stats_custom_count_increases_after_register():
    sst = SemanticSceneTemplates()
    before = sst.stats()["custom_count"]
    sst.register_template("extra_custom", _CUSTOM_TEMPLATE)
    after = sst.stats()["custom_count"]
    assert after == before + 1


def test_stats_custom_count_decreases_after_deregister():
    sst = SemanticSceneTemplates()
    sst.register_template("temp_custom", _CUSTOM_TEMPLATE)
    before = sst.stats()["custom_count"]
    sst.deregister_template("temp_custom")
    after = sst.stats()["custom_count"]
    assert after == before - 1


def test_stats_total_equals_builtin_plus_custom():
    sst = SemanticSceneTemplates()
    s = sst.stats()
    assert s["total_templates"] == s["builtin_count"] + s["custom_count"]
