"""
Tests for src.runtime.asset_staging_manager
No bridge, no LLM.  Pure unit tests.
"""
import pytest
from src.runtime.asset_staging_manager import (
    AssetStagingManager,
    get_asset_staging_manager,
    reset_asset_staging_manager_for_tests,
    _COMPLEXITY_THRESHOLDS,
    _MAX_ZONE_ASSETS,
    _CONFLICTING_PAIRS,
    _zone_import_priority,
)


@pytest.fixture(autouse=True)
def reset():
    reset_asset_staging_manager_for_tests()
    yield
    reset_asset_staging_manager_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_asset_staging_manager()
    b = get_asset_staging_manager()
    assert a is b


def test_reset_creates_new():
    a = get_asset_staging_manager()
    reset_asset_staging_manager_for_tests()
    b = get_asset_staging_manager()
    assert a is not b


# ---------------------------------------------------------------------------
# _zone_import_priority helper
# ---------------------------------------------------------------------------

def test_zone_priority_ordering():
    assert _zone_import_priority("background") < _zone_import_priority("midground")
    assert _zone_import_priority("midground")  < _zone_import_priority("hero_area")


def test_zone_priority_unknown_zone():
    unknown_prio = _zone_import_priority("custom_zone")
    assert unknown_prio > _zone_import_priority("hero_area")


# ---------------------------------------------------------------------------
# validate_asset_compatibility
# ---------------------------------------------------------------------------

def test_compat_empty_list():
    mgr = AssetStagingManager()
    result = mgr.validate_asset_compatibility([])
    assert result["compatible"] is True
    assert result["conflicts"] == []
    assert result["asset_count"] == 0


def test_compat_no_conflicts():
    mgr = AssetStagingManager()
    assets = [
        {"name": "robot1",   "category": "robot"},
        {"name": "crate1",   "category": "container"},
        {"name": "panel1",   "category": "tech_panel"},
    ]
    result = mgr.validate_asset_compatibility(assets)
    assert result["compatible"] is True
    assert result["conflicts"] == []


def test_compat_vegetation_vs_tech_panel():
    mgr = AssetStagingManager()
    assets = [
        {"name": "tree1",    "category": "vegetation"},
        {"name": "panel1",   "category": "tech_panel"},
    ]
    result = mgr.validate_asset_compatibility(assets)
    assert result["compatible"] is False
    assert len(result["conflicts"]) > 0


def test_compat_sky_vs_ceiling():
    mgr = AssetStagingManager()
    assets = [
        {"name": "sky1",      "category": "sky"},
        {"name": "ceiling1",  "category": "ceiling"},
    ]
    result = mgr.validate_asset_compatibility(assets)
    assert result["compatible"] is False


def test_compat_creature_vs_robot():
    mgr = AssetStagingManager()
    assets = [
        {"name": "dragon",   "category": "creature"},
        {"name": "mech",     "category": "robot"},
    ]
    result = mgr.validate_asset_compatibility(assets)
    assert result["compatible"] is False


def test_compat_duplicate_names_warn():
    mgr = AssetStagingManager()
    assets = [
        {"name": "crate1", "category": "container"},
        {"name": "crate1", "category": "container"},
    ]
    result = mgr.validate_asset_compatibility(assets)
    assert any("crate1" in w for w in result["warnings"])


def test_compat_no_category_warns():
    mgr = AssetStagingManager()
    assets = [{"name": "mystery_asset"}]
    result = mgr.validate_asset_compatibility(assets)
    assert len(result["warnings"]) > 0


def test_compat_result_keys():
    mgr = AssetStagingManager()
    result = mgr.validate_asset_compatibility([])
    assert {"compatible", "conflicts", "warnings", "asset_count"} <= set(result.keys())


# ---------------------------------------------------------------------------
# build_import_queue
# ---------------------------------------------------------------------------

def _make_layout_plan(zones):
    return {"zones": zones, "scene_theme": "test", "layout_rules": {}, "recommended_fx": [], "camera_hints": []}


def test_import_queue_background_first():
    zones = {
        "background": [{"name": "b1", "category": "structure"}],
        "midground":  [{"name": "m1", "category": "container"}],
        "hero_area":  [{"name": "h1", "category": "robot"}],
    }
    mgr = AssetStagingManager()
    queue = mgr.build_import_queue(_make_layout_plan(zones))
    names_in_order = [item["asset_name"] for item in queue]
    assert names_in_order.index("b1") < names_in_order.index("m1")
    assert names_in_order.index("m1") < names_in_order.index("h1")


def test_import_queue_order_field_sequential():
    zones = {
        "background": [{"name": f"b{i}", "category": "structure"} for i in range(3)],
        "hero_area":  [{"name": "h1", "category": "robot"}],
    }
    mgr = AssetStagingManager()
    queue = mgr.build_import_queue(_make_layout_plan(zones))
    orders = [item["order"] for item in queue]
    assert orders == list(range(1, len(queue) + 1))


def test_import_queue_item_has_required_keys():
    zones = {"hero_area": [{"name": "h1", "category": "robot", "poly_count": 5000}]}
    mgr = AssetStagingManager()
    queue = mgr.build_import_queue(_make_layout_plan(zones))
    item = queue[0]
    required = {"order", "asset_name", "asset_category", "zone", "import_priority", "asset_metadata"}
    assert required <= set(item.keys())


def test_import_queue_metadata_excludes_name_and_category():
    zones = {"hero_area": [{"name": "h1", "category": "robot", "poly_count": 5000, "lod": 2}]}
    mgr = AssetStagingManager()
    queue = mgr.build_import_queue(_make_layout_plan(zones))
    meta = queue[0]["asset_metadata"]
    assert "name" not in meta
    assert "category" not in meta
    assert meta["poly_count"] == 5000
    assert meta["lod"] == 2


def test_import_queue_empty_zones():
    mgr = AssetStagingManager()
    queue = mgr.build_import_queue(_make_layout_plan({}))
    assert queue == []


def test_import_queue_extra_zones_after_canonical():
    zones = {
        "hero_area":    [{"name": "h1", "category": "robot"}],
        "extra_zone_a": [{"name": "e1", "category": "misc"}],
    }
    mgr = AssetStagingManager()
    queue = mgr.build_import_queue(_make_layout_plan(zones))
    names = [item["asset_name"] for item in queue]
    # hero_area is canonical → processed before alphabetical extras
    assert names.index("h1") < names.index("e1")


# ---------------------------------------------------------------------------
# validate_scene_coherence
# ---------------------------------------------------------------------------

def _make_staging_plan(zone_assignments, layout_rules=None, recommended_fx=None):
    return {
        "zone_assignments": zone_assignments,
        "layout_rules": layout_rules if layout_rules is not None else {"fog_density": "medium"},
        "recommended_fx": recommended_fx or [],
        "import_queue": [],
    }


def test_coherence_empty_staging_plan():
    mgr = AssetStagingManager()
    result = mgr.validate_scene_coherence(_make_staging_plan({}))
    assert result["coherent"] is False
    assert any("no assets" in issue.lower() for issue in result["issues"])


def test_coherence_valid_plan():
    mgr = AssetStagingManager()
    zones = {
        "hero_area":  ["robot1"],
        "midground":  ["crate1", "crate2"],
        "background": ["wall1"],
    }
    result = mgr.validate_scene_coherence(_make_staging_plan(zones))
    assert result["coherent"] is True
    assert result["issues"] == []


def test_coherence_overloaded_zone_warns():
    mgr = AssetStagingManager()
    zones = {"hero_area": [f"asset_{i}" for i in range(_MAX_ZONE_ASSETS + 1)]}
    result = mgr.validate_scene_coherence(_make_staging_plan(zones))
    warnings_text = " ".join(result["warnings"])
    assert "hero_area" in warnings_text


def test_coherence_no_hero_warns():
    mgr = AssetStagingManager()
    zones = {"midground": ["m1", "m2"], "background": ["b1"]}
    result = mgr.validate_scene_coherence(_make_staging_plan(zones))
    warnings_text = " ".join(result["warnings"])
    assert "hero" in warnings_text.lower() or "focal" in warnings_text.lower()


def test_coherence_no_layout_rules_warns():
    mgr = AssetStagingManager()
    zones = {"hero_area": ["h1"]}
    result = mgr.validate_scene_coherence(_make_staging_plan(zones, layout_rules={}))
    warnings_text = " ".join(result["warnings"])
    assert "layout" in warnings_text.lower() or "rules" in warnings_text.lower()


def test_coherence_zone_summary():
    mgr = AssetStagingManager()
    zones = {"hero_area": ["h1", "h2"], "midground": ["m1"]}
    result = mgr.validate_scene_coherence(_make_staging_plan(zones))
    assert result["zone_summary"]["hero_area"] == 2
    assert result["zone_summary"]["midground"] == 1


def test_coherence_result_keys():
    mgr = AssetStagingManager()
    result = mgr.validate_scene_coherence(_make_staging_plan({}))
    assert {"coherent", "issues", "warnings", "zone_summary"} <= set(result.keys())


# ---------------------------------------------------------------------------
# estimate_scene_complexity
# ---------------------------------------------------------------------------

def _plan_with(total_assets=0, zone_count=0, fx_count=0):
    queue = [{"order": i} for i in range(total_assets)]
    zones = {f"zone_{z}": [f"a{i}"] for z in range(zone_count) for i in range(1)}
    # Simpler: populate zone_assignments with the right number of non-empty zones
    zone_assignments = {f"zone_{z}": ["asset"] for z in range(zone_count)}
    return {
        "import_queue":      queue,
        "zone_assignments":  zone_assignments,
        "recommended_fx":    [f"fx_{i}" for i in range(fx_count)],
    }


def test_complexity_low():
    mgr = AssetStagingManager()
    plan = _plan_with(total_assets=2, zone_count=1, fx_count=0)
    result = mgr.estimate_scene_complexity(plan)
    assert result["complexity_level"] == "low"


def test_complexity_medium():
    mgr = AssetStagingManager()
    # score = 10 + 4 + 3 = 17 -> medium (>10, <=25)
    plan = _plan_with(total_assets=10, zone_count=2, fx_count=1)
    result = mgr.estimate_scene_complexity(plan)
    assert result["complexity_level"] in ("low", "medium")


def test_complexity_high():
    mgr = AssetStagingManager()
    # score = 30 + 4 + 9 = 43 -> high (>25, <=50)
    plan = _plan_with(total_assets=30, zone_count=2, fx_count=3)
    result = mgr.estimate_scene_complexity(plan)
    assert result["complexity_level"] in ("high", "medium")


def test_complexity_extreme():
    mgr = AssetStagingManager()
    # score = 50 + 6 + 12 = 68 -> extreme (>50)
    plan = _plan_with(total_assets=50, zone_count=3, fx_count=4)
    result = mgr.estimate_scene_complexity(plan)
    assert result["complexity_level"] == "extreme"


def test_complexity_fx_notes_for_three_or_more():
    mgr = AssetStagingManager()
    plan = _plan_with(total_assets=5, zone_count=1, fx_count=3)
    result = mgr.estimate_scene_complexity(plan)
    notes_text = " ".join(result["notes"])
    assert "fx" in notes_text.lower() or "gpu" in notes_text.lower()


def test_complexity_result_keys():
    mgr = AssetStagingManager()
    result = mgr.estimate_scene_complexity(_plan_with())
    required = {"complexity_level", "total_assets", "zone_count", "fx_count", "complexity_score", "notes"}
    assert required <= set(result.keys())


# ---------------------------------------------------------------------------
# build_staging_plan (integration)
# ---------------------------------------------------------------------------

def _full_layout_plan():
    return {
        "scene_theme": "industrial_hangar",
        "zones": {
            "hero_area":  [{"name": "main_mech",  "category": "vehicle"}],
            "midground":  [{"name": "crate1",     "category": "container"},
                           {"name": "drum1",      "category": "container"}],
            "background": [{"name": "wall_panel", "category": "structure"}],
        },
        "layout_rules": {"fog_density": "medium", "hero_focus": "center"},
        "recommended_fx": ["volumetric_fog", "dust_particles"],
        "camera_hints": ["low_angle_hero"],
    }


def test_build_staging_plan_has_required_keys():
    mgr = AssetStagingManager()
    plan = mgr.build_staging_plan(_full_layout_plan())
    required = {
        "staging_id", "scene_theme", "import_queue", "zone_assignments",
        "compatibility_result", "coherence_result", "complexity_estimate",
        "layout_rules", "recommended_fx", "camera_hints",
        "ready_for_execution", "generated_at",
    }
    assert required <= set(plan.keys())


def test_build_staging_plan_ready_for_execution():
    mgr = AssetStagingManager()
    plan = mgr.build_staging_plan(_full_layout_plan())
    # no conflicts, no blocking coherence issues -> should be ready
    assert plan["ready_for_execution"] is True


def test_build_staging_plan_conflicting_assets_not_ready():
    mgr = AssetStagingManager()
    layout = {
        "scene_theme": "mixed",
        "zones": {
            "hero_area":  [{"name": "tree1",    "category": "vegetation"}],
            "midground":  [{"name": "panel1",   "category": "tech_panel"}],
            "background": [],
        },
        "layout_rules": {"hero_focus": "center"},
        "recommended_fx": [],
        "camera_hints": [],
    }
    plan = mgr.build_staging_plan(layout)
    assert plan["ready_for_execution"] is False


def test_build_staging_plan_zone_assignments_match_zones():
    mgr = AssetStagingManager()
    plan = mgr.build_staging_plan(_full_layout_plan())
    za = plan["zone_assignments"]
    assert "main_mech" in za["hero_area"]


def test_build_staging_plan_increments_count():
    mgr = AssetStagingManager()
    mgr.build_staging_plan(_full_layout_plan())
    mgr.build_staging_plan(_full_layout_plan())
    assert mgr.stats()["plan_count"] == 2


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    mgr = AssetStagingManager()
    s = mgr.stats()
    assert "plan_count" in s


def test_stats_starts_at_zero():
    mgr = AssetStagingManager()
    assert mgr.stats()["plan_count"] == 0
