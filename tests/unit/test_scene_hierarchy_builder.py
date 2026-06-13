"""
Tests for src.runtime.scene_hierarchy_builder
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.scene_hierarchy_builder import (
    SceneHierarchyBuilder,
    get_scene_hierarchy_builder,
    reset_scene_hierarchy_builder_for_tests,
    _CANONICAL_ROOTS,
    _ZONE_PARENTS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_scene_hierarchy_builder_for_tests()
    yield
    reset_scene_hierarchy_builder_for_tests()


def _base_layout(zones=None, theme="industrial_hangar"):
    zones = zones or {
        "hero_area":  [{"name": "mech", "category": "robot"}],
        "midground":  [{"name": "crate", "category": "container"}],
        "background": [{"name": "wall", "category": "structure"}],
    }
    return {"scene_theme": theme, "zones": zones}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_scene_hierarchy_builder()
    b = get_scene_hierarchy_builder()
    assert a is b


def test_reset_creates_new():
    a = get_scene_hierarchy_builder()
    reset_scene_hierarchy_builder_for_tests()
    b = get_scene_hierarchy_builder()
    assert a is not b


# ---------------------------------------------------------------------------
# build_hierarchy
# ---------------------------------------------------------------------------

def test_build_hierarchy_has_required_keys():
    b = SceneHierarchyBuilder()
    h = b.build_hierarchy(_base_layout())
    required = {"roots", "zone_map", "asset_assignments", "network_ops", "scene_theme"}
    assert required <= set(h.keys())


def test_build_hierarchy_roots_count():
    b = SceneHierarchyBuilder()
    h = b.build_hierarchy(_base_layout())
    assert len(h["roots"]) == len(_CANONICAL_ROOTS)


def test_build_hierarchy_zone_map():
    b = SceneHierarchyBuilder()
    h = b.build_hierarchy(_base_layout())
    zm = h["zone_map"]
    assert "hero_area" in zm
    assert zm["hero_area"] == "/obj/hero_assets"


def test_build_hierarchy_midground_maps_to_background():
    b = SceneHierarchyBuilder()
    h = b.build_hierarchy(_base_layout())
    assert h["zone_map"]["midground"] == "/obj/background"


def test_build_hierarchy_asset_assignments():
    b = SceneHierarchyBuilder()
    h = b.build_hierarchy(_base_layout())
    aa = h["asset_assignments"]
    assert "mech" in aa
    assert aa["mech"] == "/obj/hero_assets"
    assert aa["wall"] == "/obj/background"


def test_build_hierarchy_scene_theme_preserved():
    b = SceneHierarchyBuilder()
    h = b.build_hierarchy(_base_layout(theme="robotics_lab"))
    assert h["scene_theme"] == "robotics_lab"


def test_build_hierarchy_increments_count():
    b = SceneHierarchyBuilder()
    b.build_hierarchy(_base_layout())
    b.build_hierarchy(_base_layout())
    assert b.stats()["build_count"] == 2


def test_build_hierarchy_empty_zones():
    b = SceneHierarchyBuilder()
    h = b.build_hierarchy({"scene_theme": "test", "zones": {}})
    assert h["zone_map"] == {}
    assert h["asset_assignments"] == {}


# ---------------------------------------------------------------------------
# generate_network_structure
# ---------------------------------------------------------------------------

def test_network_structure_returns_list():
    b = SceneHierarchyBuilder()
    ops = b.generate_network_structure("industrial_hangar")
    assert isinstance(ops, list)


def test_network_structure_all_create_node():
    b = SceneHierarchyBuilder()
    ops = b.generate_network_structure("industrial_hangar")
    for op in ops:
        assert op["op"] == "create_node"


def test_network_structure_count_matches_roots():
    b = SceneHierarchyBuilder()
    ops = b.generate_network_structure("industrial_hangar")
    assert len(ops) == len(_CANONICAL_ROOTS)


def test_network_structure_parent_is_obj():
    b = SceneHierarchyBuilder()
    ops = b.generate_network_structure("industrial_hangar")
    for op in ops:
        assert op["parent"] == "/obj"


def test_network_structure_has_name():
    b = SceneHierarchyBuilder()
    ops = b.generate_network_structure("industrial_hangar")
    for op in ops:
        assert op.get("name"), f"Op missing name: {op}"


# ---------------------------------------------------------------------------
# assign_assets_to_zones
# ---------------------------------------------------------------------------

def _staging_plan(orders):
    queue = [{"asset_name": n, "order": o} for n, o in orders.items()]
    return {"import_queue": queue}


def test_assign_assets_returns_dict():
    b = SceneHierarchyBuilder()
    zones = {"hero_area": [{"name": "mech", "category": "robot"}]}
    result = b.assign_assets_to_zones(zones, _staging_plan({"mech": 1}))
    assert isinstance(result, dict)


def test_assign_assets_hero_parent():
    b = SceneHierarchyBuilder()
    zones = {"hero_area": [{"name": "mech", "category": "robot"}]}
    result = b.assign_assets_to_zones(zones, _staging_plan({"mech": 1}))
    assert result["mech"]["parent_path"] == "/obj/hero_assets"
    assert result["mech"]["zone"] == "hero_area"


def test_assign_assets_background_parent():
    b = SceneHierarchyBuilder()
    zones = {"background": [{"name": "wall", "category": "structure"}]}
    result = b.assign_assets_to_zones(zones, _staging_plan({"wall": 1}))
    assert result["wall"]["parent_path"] == "/obj/background"


def test_assign_assets_order_from_staging():
    b = SceneHierarchyBuilder()
    zones = {"hero_area": [{"name": "mech", "category": "robot"}]}
    result = b.assign_assets_to_zones(zones, _staging_plan({"mech": 5}))
    assert result["mech"]["order"] == 5


def test_assign_assets_missing_order_defaults():
    b = SceneHierarchyBuilder()
    zones = {"hero_area": [{"name": "mech", "category": "robot"}]}
    result = b.assign_assets_to_zones(zones, {"import_queue": []})
    assert result["mech"]["order"] == 999


# ---------------------------------------------------------------------------
# validate_hierarchy_integrity
# ---------------------------------------------------------------------------

def _valid_hierarchy():
    b = SceneHierarchyBuilder()
    return b.build_hierarchy(_base_layout())


def test_validate_valid_hierarchy():
    b = SceneHierarchyBuilder()
    h = _valid_hierarchy()
    result = b.validate_hierarchy_integrity(h)
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_missing_keys():
    b = SceneHierarchyBuilder()
    result = b.validate_hierarchy_integrity({})
    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validate_empty_roots_error():
    b = SceneHierarchyBuilder()
    h = _valid_hierarchy()
    h["roots"] = []
    result = b.validate_hierarchy_integrity(h)
    assert result["valid"] is False


def test_validate_invalid_asset_path():
    b = SceneHierarchyBuilder()
    h = _valid_hierarchy()
    h["asset_assignments"]["bad_asset"] = "not/a/valid/path"
    result = b.validate_hierarchy_integrity(h)
    assert result["valid"] is False
    assert any("bad_asset" in e for e in result["errors"])


def test_validate_bad_network_op():
    b = SceneHierarchyBuilder()
    h = _valid_hierarchy()
    h["network_ops"].append({"op": "delete_node", "path": "/obj/something"})
    result = b.validate_hierarchy_integrity(h)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# get_zone_parent
# ---------------------------------------------------------------------------

def test_get_zone_parent_hero():
    b = SceneHierarchyBuilder()
    assert b.get_zone_parent("hero_area") == "/obj/hero_assets"


def test_get_zone_parent_background():
    b = SceneHierarchyBuilder()
    assert b.get_zone_parent("background") == "/obj/background"


def test_get_zone_parent_unknown_fallback():
    b = SceneHierarchyBuilder()
    assert b.get_zone_parent("weird_zone") == "/obj/background"


# ---------------------------------------------------------------------------
# build_hierarchy — extended
# ---------------------------------------------------------------------------

def test_build_hierarchy_network_ops_all_create_node():
    b = SceneHierarchyBuilder()
    h = b.build_hierarchy(_base_layout())
    for op in h["network_ops"]:
        assert op["op"] == "create_node"


def test_build_hierarchy_network_ops_count():
    b = SceneHierarchyBuilder()
    h = b.build_hierarchy(_base_layout())
    assert len(h["network_ops"]) == len(_CANONICAL_ROOTS)


def test_build_hierarchy_ceiling_goes_to_environment():
    b = SceneHierarchyBuilder()
    layout = _base_layout(zones={"ceiling": [{"name": "roof", "category": "ceiling"}]})
    h = b.build_hierarchy(layout)
    assert h["zone_map"].get("ceiling") == "/obj/environment"


def test_build_hierarchy_unknown_zone_fallback():
    b = SceneHierarchyBuilder()
    layout = _base_layout(zones={"weird_zone": [{"name": "thing", "category": "misc"}]})
    h = b.build_hierarchy(layout)
    assert h["zone_map"].get("weird_zone") == "/obj/background"


def test_build_hierarchy_asset_assignments_background():
    b = SceneHierarchyBuilder()
    h = b.build_hierarchy(_base_layout())
    assert h["asset_assignments"]["wall"] == "/obj/background"


def test_build_hierarchy_crate_midground_maps_to_background():
    b = SceneHierarchyBuilder()
    h = b.build_hierarchy(_base_layout())
    assert h["asset_assignments"]["crate"] == "/obj/background"


# ---------------------------------------------------------------------------
# generate_network_structure — extended
# ---------------------------------------------------------------------------

def test_network_structure_contains_hero_assets():
    b = SceneHierarchyBuilder()
    ops = b.generate_network_structure("test")
    names = [op["name"] for op in ops]
    assert "hero_assets" in names


def test_network_structure_contains_lighting():
    b = SceneHierarchyBuilder()
    ops = b.generate_network_structure("test")
    names = [op["name"] for op in ops]
    assert "lighting" in names


def test_network_structure_theme_doesnt_change_output():
    b = SceneHierarchyBuilder()
    ops_a = b.generate_network_structure("industrial_hangar")
    ops_b = b.generate_network_structure("sci_fi_corridor")
    assert [o["name"] for o in ops_a] == [o["name"] for o in ops_b]


# ---------------------------------------------------------------------------
# get_zone_parent — extended
# ---------------------------------------------------------------------------

def test_get_zone_parent_midground():
    b = SceneHierarchyBuilder()
    assert b.get_zone_parent("midground") == "/obj/background"


def test_get_zone_parent_ceiling():
    b = SceneHierarchyBuilder()
    assert b.get_zone_parent("ceiling") == "/obj/environment"


def test_get_zone_parent_floor():
    b = SceneHierarchyBuilder()
    assert b.get_zone_parent("floor") == "/obj/environment"


def test_get_zone_parent_walls():
    b = SceneHierarchyBuilder()
    assert b.get_zone_parent("walls") == "/obj/environment"


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    b = SceneHierarchyBuilder()
    s = b.stats()
    assert "build_count" in s


def test_stats_starts_zero():
    b = SceneHierarchyBuilder()
    assert b.stats()["build_count"] == 0
