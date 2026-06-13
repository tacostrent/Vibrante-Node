"""
Tests for src.runtime.houdini_asset_realizer
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.houdini_asset_realizer import (
    HoudiniAssetRealizer,
    get_houdini_asset_realizer,
    reset_houdini_asset_realizer_for_tests,
    _SCENE_ROOTS,
    _ZONE_CONTAINERS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_houdini_asset_realizer_for_tests()
    yield
    reset_houdini_asset_realizer_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_houdini_asset_realizer()
    b = get_houdini_asset_realizer()
    assert a is b


def test_reset_creates_new():
    a = get_houdini_asset_realizer()
    reset_houdini_asset_realizer_for_tests()
    b = get_houdini_asset_realizer()
    assert a is not b


# ---------------------------------------------------------------------------
# create_environment_structure
# ---------------------------------------------------------------------------

def test_create_env_structure_returns_list():
    r = HoudiniAssetRealizer()
    ops = r.create_environment_structure("industrial_hangar")
    assert isinstance(ops, list)


def test_create_env_structure_count_matches_roots():
    r = HoudiniAssetRealizer()
    ops = r.create_environment_structure("industrial_hangar")
    assert len(ops) == len(_SCENE_ROOTS)


def test_create_env_structure_all_create_node():
    r = HoudiniAssetRealizer()
    ops = r.create_environment_structure("industrial_hangar")
    for op in ops:
        assert op["op"] == "create_node"


def test_create_env_structure_parent_is_obj():
    r = HoudiniAssetRealizer()
    ops = r.create_environment_structure("industrial_hangar")
    for op in ops:
        assert op["parent"] == "/obj"


def test_create_env_structure_names_from_roots():
    r = HoudiniAssetRealizer()
    ops = r.create_environment_structure("industrial_hangar")
    names = {op["name"] for op in ops}
    expected = {path.split("/")[-1] for path in _SCENE_ROOTS}
    assert names == expected


# ---------------------------------------------------------------------------
# create_asset_container
# ---------------------------------------------------------------------------

def test_create_asset_container_hero():
    r = HoudiniAssetRealizer()
    op = r.create_asset_container("hero_area")
    assert op["op"] == "create_node"
    assert "hero" in op["name"]


def test_create_asset_container_background():
    r = HoudiniAssetRealizer()
    op = r.create_asset_container("background")
    assert op["op"] == "create_node"
    assert "background" in op["name"]


def test_create_asset_container_has_type():
    r = HoudiniAssetRealizer()
    op = r.create_asset_container("midground")
    assert "type" in op


def test_create_asset_container_unknown_zone():
    r = HoudiniAssetRealizer()
    op = r.create_asset_container("custom_zone")
    assert op["op"] == "create_node"


# ---------------------------------------------------------------------------
# apply_semantic_naming
# ---------------------------------------------------------------------------

def test_semantic_naming_robot():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "mech_warrior", "category": "robot"}, "hero_area")
    assert name.startswith("bot_")


def test_semantic_naming_vehicle():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "tank1", "category": "vehicle"}, "hero_area")
    assert name.startswith("veh_")


def test_semantic_naming_structure():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "wall panel", "category": "structure"}, "background")
    assert name.startswith("str_")
    assert " " not in name


def test_semantic_naming_sanitises_spaces():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "my asset", "category": "misc"}, "midground")
    assert " " not in name


def test_semantic_naming_unknown_category():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "thing", "category": "exotic_unknown"}, "midground")
    assert isinstance(name, str)
    assert len(name) > 0


def test_semantic_naming_returns_valid_identifier():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "a-b+c", "category": "container"}, "midground")
    for ch in name:
        assert ch.isalnum() or ch == "_"


# ---------------------------------------------------------------------------
# register_realized_assets
# ---------------------------------------------------------------------------

def test_register_realized_assets_returns_count():
    r = HoudiniAssetRealizer()
    result = r.register_realized_assets([], {"robot1": "/obj/hero_assets/bot_robot1"})
    assert result["asset_count"] == 1


def test_register_realized_assets_stored():
    r = HoudiniAssetRealizer()
    r.register_realized_assets([], {"robot1": "/obj/hero_assets/bot_robot1"})
    assert r.get_realized_path("robot1") == "/obj/hero_assets/bot_robot1"


def test_get_realized_path_unknown_returns_none():
    r = HoudiniAssetRealizer()
    assert r.get_realized_path("nonexistent") is None


# ---------------------------------------------------------------------------
# build_transaction_operations
# ---------------------------------------------------------------------------

def _make_layout_plan(zones=None, scene_theme="industrial_hangar"):
    zones = zones or {"hero_area": [{"name": "mech", "category": "robot"}], "background": []}
    return {"scene_theme": scene_theme, "zones": zones}


def _make_staging_plan(import_queue=None):
    queue = import_queue or [
        {"order": 1, "asset_name": "mech", "asset_category": "robot", "zone": "hero_area",
         "import_priority": 3, "asset_metadata": {}}
    ]
    return {"import_queue": queue}


def test_build_transaction_ops_returns_list():
    r = HoudiniAssetRealizer()
    ops = r.build_transaction_operations(_make_layout_plan(), _make_staging_plan())
    assert isinstance(ops, list)


def test_build_transaction_ops_has_create_node():
    r = HoudiniAssetRealizer()
    ops = r.build_transaction_operations(_make_layout_plan(), _make_staging_plan())
    op_types = [op["op"] for op in ops]
    assert "create_node" in op_types


def test_build_transaction_ops_has_layout_children():
    r = HoudiniAssetRealizer()
    ops = r.build_transaction_operations(_make_layout_plan(), _make_staging_plan())
    op_types = [op["op"] for op in ops]
    assert "layout_children" in op_types


def test_build_transaction_ops_empty_queue():
    r = HoudiniAssetRealizer()
    ops = r.build_transaction_operations(_make_layout_plan(), {"import_queue": []})
    # Still has scene root + layout ops even with no assets
    assert len(ops) > 0


def test_build_transaction_ops_multiple_assets():
    r = HoudiniAssetRealizer()
    layout = _make_layout_plan(zones={
        "hero_area":  [{"name": "mech", "category": "robot"}],
        "background": [{"name": "wall", "category": "structure"}],
    })
    staging = _make_staging_plan([
        {"order": 1, "asset_name": "wall", "asset_category": "structure", "zone": "background",
         "import_priority": 1, "asset_metadata": {}},
        {"order": 2, "asset_name": "mech", "asset_category": "robot", "zone": "hero_area",
         "import_priority": 3, "asset_metadata": {}},
    ])
    ops = r.build_transaction_operations(layout, staging)
    assert len(ops) > 4


# ---------------------------------------------------------------------------
# realize_scene (integration)
# ---------------------------------------------------------------------------

def test_realize_scene_has_required_keys():
    r = HoudiniAssetRealizer()
    result = r.realize_scene(_make_layout_plan(), _make_staging_plan())
    required = {"realization_id", "scene_theme", "operations", "asset_count",
                "zone_map", "path_map", "generated_at"}
    assert required <= set(result.keys())


def test_realize_scene_theme_preserved():
    r = HoudiniAssetRealizer()
    result = r.realize_scene(_make_layout_plan(scene_theme="robotics_lab"), _make_staging_plan())
    assert result["scene_theme"] == "robotics_lab"


def test_realize_scene_increments_count():
    r = HoudiniAssetRealizer()
    r.realize_scene(_make_layout_plan(), _make_staging_plan())
    r.realize_scene(_make_layout_plan(), _make_staging_plan())
    assert r.stats()["realization_count"] == 2


def test_realize_scene_path_map_populated():
    r = HoudiniAssetRealizer()
    result = r.realize_scene(_make_layout_plan(), _make_staging_plan())
    assert "mech" in result["path_map"]


def test_realize_scene_zone_map_populated():
    r = HoudiniAssetRealizer()
    result = r.realize_scene(_make_layout_plan(), _make_staging_plan())
    assert "mech" in result["zone_map"]
    assert result["zone_map"]["mech"] == "hero_area"


# ---------------------------------------------------------------------------
# create_environment_structure — extended
# ---------------------------------------------------------------------------

def test_create_env_structure_all_seven_roots():
    r = HoudiniAssetRealizer()
    ops = r.create_environment_structure("sci_fi_corridor")
    assert len(ops) == 7


def test_create_env_structure_node_type_is_null():
    r = HoudiniAssetRealizer()
    ops = r.create_environment_structure("robotics_lab")
    for op in ops:
        assert op["type"] == "null"


def test_create_env_structure_params_key_present():
    r = HoudiniAssetRealizer()
    ops = r.create_environment_structure("industrial_hangar")
    for op in ops:
        assert "params" in op


def test_create_env_structure_theme_does_not_affect_result():
    r = HoudiniAssetRealizer()
    ops_a = r.create_environment_structure("industrial_hangar")
    ops_b = r.create_environment_structure("robotics_lab")
    assert [o["name"] for o in ops_a] == [o["name"] for o in ops_b]


def test_create_env_structure_contains_hero_assets():
    r = HoudiniAssetRealizer()
    ops = r.create_environment_structure("test")
    names = [op["name"] for op in ops]
    assert "hero_assets" in names


def test_create_env_structure_contains_lighting():
    r = HoudiniAssetRealizer()
    ops = r.create_environment_structure("test")
    names = [op["name"] for op in ops]
    assert "lighting" in names


def test_create_env_structure_contains_camera():
    r = HoudiniAssetRealizer()
    ops = r.create_environment_structure("test")
    names = [op["name"] for op in ops]
    assert "camera" in names


# ---------------------------------------------------------------------------
# create_asset_container — extended
# ---------------------------------------------------------------------------

def test_create_asset_container_midground_maps_to_background():
    r = HoudiniAssetRealizer()
    op = r.create_asset_container("midground")
    # midground → /obj/background container
    assert "midground" in op["name"]


def test_create_asset_container_ceiling_zone():
    r = HoudiniAssetRealizer()
    op = r.create_asset_container("ceiling")
    assert op["op"] == "create_node"
    assert "ceiling" in op["name"]


def test_create_asset_container_floor_zone():
    r = HoudiniAssetRealizer()
    op = r.create_asset_container("floor")
    assert op["op"] == "create_node"
    assert "floor" in op["name"]


def test_create_asset_container_type_is_geo():
    r = HoudiniAssetRealizer()
    op = r.create_asset_container("hero_area")
    assert op["type"] == "geo"


# ---------------------------------------------------------------------------
# apply_semantic_naming — additional categories
# ---------------------------------------------------------------------------

def test_semantic_naming_character():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "soldier", "category": "character"}, "hero_area")
    assert name.startswith("chr_")


def test_semantic_naming_machinery_hero():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "crane", "category": "machinery_hero"}, "hero_area")
    assert name.startswith("mch_")


def test_semantic_naming_hero_prop():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "crate", "category": "hero_prop"}, "hero_area")
    assert name.startswith("prop_")


def test_semantic_naming_creature():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "beast", "category": "creature"}, "hero_area")
    assert name.startswith("crt_")


def test_semantic_naming_vegetation():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "tree", "category": "vegetation"}, "midground")
    assert name.startswith("veg_")


def test_semantic_naming_tech_panel():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "panel_a", "category": "tech_panel"}, "background")
    assert name.startswith("tech_")


def test_semantic_naming_hyphen_sanitised():
    r = HoudiniAssetRealizer()
    name = r.apply_semantic_naming({"name": "a-b-c", "category": "structure"}, "background")
    assert "-" not in name


# ---------------------------------------------------------------------------
# build_transaction_operations — extended
# ---------------------------------------------------------------------------

def test_build_transaction_ops_layout_children_count():
    r = HoudiniAssetRealizer()
    ops = r.build_transaction_operations(_make_layout_plan(), _make_staging_plan())
    layout_ops = [op for op in ops if op["op"] == "layout_children"]
    assert len(layout_ops) == len(_SCENE_ROOTS)


def test_build_transaction_ops_zone_container_created_once():
    r = HoudiniAssetRealizer()
    staging = _make_staging_plan([
        {"order": 1, "asset_name": "wall1", "asset_category": "structure",
         "zone": "background", "import_priority": 1, "asset_metadata": {}},
        {"order": 2, "asset_name": "wall2", "asset_category": "structure",
         "zone": "background", "import_priority": 1, "asset_metadata": {}},
    ])
    ops = r.build_transaction_operations(_make_layout_plan(), staging)
    # "zone_background" container should be created exactly once
    zone_containers = [op for op in ops if op.get("name") == "zone_background"]
    assert len(zone_containers) == 1


def test_build_transaction_ops_transforms_passed_through():
    r = HoudiniAssetRealizer()
    staging = _make_staging_plan([
        {"order": 1, "asset_name": "mech", "asset_category": "robot",
         "zone": "hero_area", "import_priority": 3,
         "asset_metadata": {"tx": 5.0, "ty": 0.0, "tz": -10.0}},
    ])
    ops = r.build_transaction_operations(_make_layout_plan(), staging)
    asset_ops = [op for op in ops if op.get("op") == "create_node"
                 and op.get("name", "").startswith("bot_")]
    assert len(asset_ops) == 1
    assert asset_ops[0]["params"].get("tx") == 5.0


def test_build_transaction_ops_empty_queue_still_has_roots():
    r = HoudiniAssetRealizer()
    ops = r.build_transaction_operations(_make_layout_plan(), {"import_queue": []})
    create_ops = [op for op in ops if op["op"] == "create_node"]
    assert len(create_ops) == len(_SCENE_ROOTS)


# ---------------------------------------------------------------------------
# realize_scene — extended
# ---------------------------------------------------------------------------

def test_realize_scene_realization_id_is_uuid_string():
    import uuid
    r = HoudiniAssetRealizer()
    result = r.realize_scene(_make_layout_plan(), _make_staging_plan())
    rid = result["realization_id"]
    assert isinstance(rid, str)
    uuid.UUID(rid)  # raises if not valid UUID


def test_realize_scene_generated_at_is_float():
    r = HoudiniAssetRealizer()
    result = r.realize_scene(_make_layout_plan(), _make_staging_plan())
    assert isinstance(result["generated_at"], float)
    assert result["generated_at"] > 0


def test_realize_scene_operations_nonempty():
    r = HoudiniAssetRealizer()
    result = r.realize_scene(_make_layout_plan(), _make_staging_plan())
    assert len(result["operations"]) > 0


def test_realize_scene_asset_count():
    r = HoudiniAssetRealizer()
    layout = _make_layout_plan(zones={
        "hero_area":  [{"name": "mech", "category": "robot"},
                       {"name": "tank", "category": "vehicle"}],
        "background": [{"name": "wall", "category": "structure"}],
    })
    result = r.realize_scene(layout, _make_staging_plan())
    assert result["asset_count"] == 3


def test_realize_scene_empty_zones():
    r = HoudiniAssetRealizer()
    layout = {"scene_theme": "test", "zones": {}}
    result = r.realize_scene(layout, {"import_queue": []})
    assert result["zone_map"] == {}
    assert result["path_map"] == {}


def test_realize_scene_path_map_starts_with_obj():
    r = HoudiniAssetRealizer()
    result = r.realize_scene(_make_layout_plan(), _make_staging_plan())
    for path in result["path_map"].values():
        assert path.startswith("/obj/")


# ---------------------------------------------------------------------------
# register_realized_assets — extended
# ---------------------------------------------------------------------------

def test_register_realized_assets_returns_path_map():
    r = HoudiniAssetRealizer()
    result = r.register_realized_assets([], {"a": "/obj/x"})
    assert "path_map" in result
    assert result["path_map"]["a"] == "/obj/x"


def test_register_realized_assets_empty_dict():
    r = HoudiniAssetRealizer()
    result = r.register_realized_assets([], {})
    assert result["asset_count"] == 0


def test_register_realized_assets_accumulates():
    r = HoudiniAssetRealizer()
    r.register_realized_assets([], {"a": "/obj/a"})
    r.register_realized_assets([], {"b": "/obj/b"})
    assert r.stats()["registered_assets"] == 2


def test_realize_scene_updates_registered_assets():
    r = HoudiniAssetRealizer()
    r.realize_scene(_make_layout_plan(), _make_staging_plan())
    assert r.stats()["registered_assets"] >= 1


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    r = HoudiniAssetRealizer()
    s = r.stats()
    assert "realization_count" in s
    assert "registered_assets" in s


def test_stats_starts_at_zero():
    r = HoudiniAssetRealizer()
    assert r.stats()["realization_count"] == 0


def test_stats_registered_assets_starts_zero():
    r = HoudiniAssetRealizer()
    assert r.stats()["registered_assets"] == 0
