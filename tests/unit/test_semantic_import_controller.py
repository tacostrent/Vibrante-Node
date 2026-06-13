"""
Tests for src.runtime.semantic_import_controller
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.semantic_import_controller import (
    SemanticImportController,
    get_semantic_import_controller,
    reset_semantic_import_controller_for_tests,
    _STYLE_CONFLICTS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_semantic_import_controller_for_tests()
    yield
    reset_semantic_import_controller_for_tests()


def _asset(name="robot1", category="robot", **kwargs):
    a = {"name": name, "category": category}
    a.update(kwargs)
    return a


def _scene(theme="industrial_hangar", renderer="arnold", existing=None):
    return {
        "scene_theme":          theme,
        "renderer":             renderer,
        "existing_categories":  existing or [],
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_semantic_import_controller()
    b = get_semantic_import_controller()
    assert a is b


def test_reset_creates_new():
    a = get_semantic_import_controller()
    reset_semantic_import_controller_for_tests()
    b = get_semantic_import_controller()
    assert a is not b


# ---------------------------------------------------------------------------
# validate_asset_for_scene — result keys
# ---------------------------------------------------------------------------

def test_validate_result_keys():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(_asset(), _scene())
    required = {"valid", "errors", "warnings", "asset_name", "checks_passed", "checks_failed"}
    assert required <= set(result.keys())


def test_validate_valid_asset():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(_asset(), _scene())
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_no_name_fails():
    c = SemanticImportController()
    result = c.validate_asset_for_scene({"category": "robot"}, _scene())
    assert result["valid"] is False
    assert any("name" in e.lower() for e in result["errors"])


def test_validate_unknown_category_warns():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(_asset(category="exotic_xyz"), _scene())
    assert any("exotic_xyz" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# validate_asset_for_scene — renderer compatibility
# ---------------------------------------------------------------------------

def test_validate_bgeo_incompatible_with_arnold():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(format="bgeo"),
        _scene(renderer="arnold"),
    )
    assert result["valid"] is False
    assert "renderer_compatibility" in result["checks_failed"]


def test_validate_abc_compatible_with_arnold():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(format="abc"),
        _scene(renderer="arnold"),
    )
    assert "renderer_compatibility" in result["checks_passed"]


def test_validate_no_format_passes_renderer():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(_asset(), _scene())
    # No format → renderer check passes with a warning
    assert "renderer_compatibility" in result["checks_passed"]


# ---------------------------------------------------------------------------
# validate_asset_for_scene — style conflicts
# ---------------------------------------------------------------------------

def test_validate_vegetation_vs_tech_panel():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(category="vegetation"),
        _scene(existing=["tech_panel"]),
    )
    assert result["valid"] is False
    assert "style_consistency" in result["checks_failed"]


def test_validate_sky_vs_ceiling():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(category="sky"),
        _scene(existing=["ceiling"]),
    )
    assert result["valid"] is False


def test_validate_creature_vs_robot():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(category="creature"),
        _scene(existing=["robot"]),
    )
    assert result["valid"] is False


def test_validate_no_existing_categories_passes():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(_asset(category="vegetation"), _scene())
    assert result["valid"] is True


# ---------------------------------------------------------------------------
# validate_asset_for_scene — scene relevance warning
# ---------------------------------------------------------------------------

def test_validate_irrelevant_category_warns():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(category="vegetation"),
        _scene(theme="industrial_hangar"),
    )
    # vegetation is not preferred in industrial_hangar → warning, not error
    assert any("preferred" in w.lower() or "not preferred" in w.lower() for w in result["warnings"])


def test_validate_preferred_category_no_warning():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(category="vehicle"),
        _scene(theme="industrial_hangar"),
    )
    # vehicle IS preferred in industrial_hangar
    assert result["valid"] is True


# ---------------------------------------------------------------------------
# validate_asset_for_scene — scale check
# ---------------------------------------------------------------------------

def test_validate_scale_too_large_warns():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(category="tech_panel", scale_metres=50.0),
        _scene(),
    )
    assert any("scale" in w.lower() for w in result["warnings"])


def test_validate_scale_in_range_no_warning():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(category="robot", scale_metres=2.0),
        _scene(),
    )
    scale_warnings = [w for w in result["warnings"] if "scale" in w.lower()]
    assert scale_warnings == []


# ---------------------------------------------------------------------------
# validate_renderer_compatibility
# ---------------------------------------------------------------------------

def test_renderer_compat_abc_karma():
    c = SemanticImportController()
    r = c.validate_renderer_compatibility({"format": "abc"}, "karma")
    assert r["compatible"] is True


def test_renderer_compat_vdb_generic():
    c = SemanticImportController()
    r = c.validate_renderer_compatibility({"format": "vdb"}, "generic")
    assert r["compatible"] is False


def test_renderer_compat_unknown_format():
    c = SemanticImportController()
    r = c.validate_renderer_compatibility({"format": "xyz_unknown"}, "arnold")
    assert r["compatible"] is True


def test_renderer_compat_no_format():
    c = SemanticImportController()
    r = c.validate_renderer_compatibility({}, "arnold")
    assert r["compatible"] is True


# ---------------------------------------------------------------------------
# validate_style_consistency
# ---------------------------------------------------------------------------

def test_style_consistent():
    c = SemanticImportController()
    r = c.validate_style_consistency({"category": "robot"}, ["container", "tech_panel"])
    assert r["consistent"] is True


def test_style_inconsistent_vegetation_tech():
    c = SemanticImportController()
    r = c.validate_style_consistency({"category": "vegetation"}, ["tech_panel"])
    assert r["consistent"] is False
    assert len(r["conflicts"]) > 0


def test_style_inconsistent_creature_robot():
    c = SemanticImportController()
    r = c.validate_style_consistency({"category": "creature"}, ["robot"])
    assert r["consistent"] is False


def test_style_empty_existing():
    c = SemanticImportController()
    r = c.validate_style_consistency({"category": "vegetation"}, [])
    assert r["consistent"] is True


# ---------------------------------------------------------------------------
# build_import_operations
# ---------------------------------------------------------------------------

def test_build_import_ops_creates_node():
    c = SemanticImportController()
    ops = c.build_import_operations(
        {"name": "robot1", "category": "robot"},
        "/obj/hero_assets/bot_robot1",
        {},
    )
    assert any(op["op"] == "create_node" for op in ops)


def test_build_import_ops_correct_parent():
    c = SemanticImportController()
    ops = c.build_import_operations(
        {"name": "robot1", "category": "robot"},
        "/obj/hero_assets/bot_robot1",
        {},
    )
    create_ops = [op for op in ops if op["op"] == "create_node"]
    assert create_ops[0]["parent"] == "/obj/hero_assets"
    assert create_ops[0]["name"] == "bot_robot1"


def test_build_import_ops_with_transforms():
    c = SemanticImportController()
    ops = c.build_import_operations(
        {"name": "robot1", "category": "robot"},
        "/obj/hero_assets/bot_robot1",
        {"tx": 5.0, "ty": 0.0, "tz": -10.0},
    )
    parm_ops = [op for op in ops if op["op"] == "set_parms"]
    assert len(parm_ops) == 1
    assert parm_ops[0]["parms"]["tx"] == 5.0


def test_build_import_ops_no_transforms_no_set_parms():
    c = SemanticImportController()
    ops = c.build_import_operations(
        {"name": "robot1", "category": "robot"},
        "/obj/hero_assets/bot_robot1",
        {},
    )
    parm_ops = [op for op in ops if op["op"] == "set_parms"]
    assert len(parm_ops) == 0


# ---------------------------------------------------------------------------
# estimate_import_cost
# ---------------------------------------------------------------------------

def test_estimate_cost_low_poly():
    c = SemanticImportController()
    r = c.estimate_import_cost({"category": "container", "poly_count": 500})
    assert r["cost_level"] == "low"


def test_estimate_cost_high_poly():
    c = SemanticImportController()
    r = c.estimate_import_cost({"category": "robot", "poly_count": 2_000_000})
    assert r["cost_level"] in ("medium", "high")


def test_estimate_cost_vdb_expensive():
    c = SemanticImportController()
    r = c.estimate_import_cost({"category": "misc", "format": "vdb"})
    assert r["cost_score"] > 1.0


def test_estimate_cost_terrain_expensive():
    c = SemanticImportController()
    r = c.estimate_import_cost({"category": "terrain"})
    assert r["cost_score"] >= 2.0


def test_estimate_cost_result_keys():
    c = SemanticImportController()
    r = c.estimate_import_cost({"category": "robot"})
    assert {"cost_level", "cost_score", "notes"} <= set(r.keys())


# ---------------------------------------------------------------------------
# validate_asset_for_scene — extended edge cases
# ---------------------------------------------------------------------------

def test_validate_asset_name_in_result():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(_asset(name="tank_alpha"), _scene())
    assert result["asset_name"] == "tank_alpha"


def test_validate_checks_passed_not_empty():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(_asset(), _scene())
    assert len(result["checks_passed"]) > 0


def test_validate_bgeo_mantra_compatible():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(format="bgeo"),
        _scene(renderer="mantra"),
    )
    assert "renderer_compatibility" in result["checks_passed"]


def test_validate_vdb_karma_compatible():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(format="vdb"),
        _scene(renderer="karma"),
    )
    assert "renderer_compatibility" in result["checks_passed"]


def test_validate_usd_arnold_compatible():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(format="usd"),
        _scene(renderer="arnold"),
    )
    assert "renderer_compatibility" in result["checks_passed"]


def test_validate_organic_vs_industrial():
    c = SemanticImportController()
    result = c.validate_asset_for_scene(
        _asset(category="organic"),
        _scene(existing=["industrial"]),
    )
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# validate_renderer_compatibility — extended
# ---------------------------------------------------------------------------

def test_renderer_compat_bgeo_arnold_fails():
    c = SemanticImportController()
    r = c.validate_renderer_compatibility({"format": "bgeo"}, "arnold")
    assert r["compatible"] is False


def test_renderer_compat_hda_all_renderers():
    c = SemanticImportController()
    for renderer in ("arnold", "karma", "mantra", "generic"):
        r = c.validate_renderer_compatibility({"format": "hda"}, renderer)
        assert r["compatible"] is True, f"hda should be compatible with {renderer}"


def test_renderer_compat_result_has_errors_key():
    c = SemanticImportController()
    r = c.validate_renderer_compatibility({"format": "bgeo"}, "arnold")
    assert "errors" in r
    assert len(r["errors"]) > 0


# ---------------------------------------------------------------------------
# validate_style_consistency — extended
# ---------------------------------------------------------------------------

def test_style_sky_ceiling_blocked():
    c = SemanticImportController()
    r = c.validate_style_consistency({"category": "sky"}, ["ceiling"])
    assert r["consistent"] is False


def test_style_robot_tech_panel_ok():
    c = SemanticImportController()
    r = c.validate_style_consistency({"category": "robot"}, ["tech_panel"])
    assert r["consistent"] is True


def test_style_result_has_conflicts_list():
    c = SemanticImportController()
    r = c.validate_style_consistency({"category": "vegetation"}, ["tech_panel"])
    assert "conflicts" in r
    assert isinstance(r["conflicts"], list)


# ---------------------------------------------------------------------------
# estimate_import_cost — extended
# ---------------------------------------------------------------------------

def test_estimate_cost_high_lod_adds_cost():
    c = SemanticImportController()
    r_lod = c.estimate_import_cost({"category": "robot", "poly_count": 500_000, "lod": 3})
    r_no_lod = c.estimate_import_cost({"category": "robot", "poly_count": 500_000})
    assert r_lod["cost_score"] >= r_no_lod["cost_score"]


def test_estimate_cost_notes_is_list():
    c = SemanticImportController()
    r = c.estimate_import_cost({"category": "robot"})
    assert isinstance(r["notes"], list)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    c = SemanticImportController()
    s = c.stats()
    assert "validation_count" in s
    assert "rejected_count" in s


def test_stats_validation_increments():
    c = SemanticImportController()
    c.validate_asset_for_scene(_asset(), _scene())
    c.validate_asset_for_scene(_asset(), _scene())
    assert c.stats()["validation_count"] == 2


def test_stats_rejection_counts_errors():
    c = SemanticImportController()
    c.validate_asset_for_scene({"category": "robot"}, _scene())  # no name → error
    assert c.stats()["rejected_count"] == 1


def test_stats_rejected_count_starts_zero():
    c = SemanticImportController()
    assert c.stats()["rejected_count"] == 0
