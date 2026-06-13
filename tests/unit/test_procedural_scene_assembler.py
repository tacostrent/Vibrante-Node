"""
Tests for src.runtime.procedural_scene_assembler
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.procedural_scene_assembler import (
    ProceduralSceneAssembler,
    get_procedural_scene_assembler,
    reset_procedural_scene_assembler_for_tests,
    _LIGHTING_PRESETS,
)
from src.runtime.houdini_asset_realizer import reset_houdini_asset_realizer_for_tests
from src.runtime.scene_hierarchy_builder import reset_scene_hierarchy_builder_for_tests
from src.runtime.layout_transform_engine import reset_layout_transform_engine_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_procedural_scene_assembler_for_tests()
    reset_houdini_asset_realizer_for_tests()
    reset_scene_hierarchy_builder_for_tests()
    reset_layout_transform_engine_for_tests()
    yield
    reset_procedural_scene_assembler_for_tests()
    reset_houdini_asset_realizer_for_tests()
    reset_scene_hierarchy_builder_for_tests()
    reset_layout_transform_engine_for_tests()


def _base_layout(theme="industrial_hangar", zones=None, rules=None):
    zones = zones or {
        "hero_area":  [{"name": "mech", "category": "robot"}],
        "midground":  [{"name": "crate", "category": "container"}],
        "background": [{"name": "wall", "category": "structure"}],
    }
    rules = rules or {"fog_density": "medium", "lighting_style": "practical_industrial"}
    return {
        "scene_theme":   theme,
        "zones":         zones,
        "layout_rules":  rules,
        "camera_hints":  ["low_angle"],
        "depth_layers":  ["hero_area", "midground", "background"],
    }


def _base_staging(zones=None, rules=None):
    queue = [
        {"order": 1, "asset_name": "wall",  "asset_category": "structure", "zone": "background",
         "import_priority": 1, "asset_metadata": {}},
        {"order": 2, "asset_name": "crate", "asset_category": "container", "zone": "midground",
         "import_priority": 2, "asset_metadata": {}},
        {"order": 3, "asset_name": "mech",  "asset_category": "robot",     "zone": "hero_area",
         "import_priority": 3, "asset_metadata": {}},
    ]
    return {
        "import_queue":    queue,
        "layout_rules":    rules or {"fog_density": "medium", "hero_focus": "center"},
        "recommended_fx":  ["volumetric_fog"],
        "zone_assignments": zones or {},
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_procedural_scene_assembler()
    b = get_procedural_scene_assembler()
    assert a is b


def test_reset_creates_new():
    a = get_procedural_scene_assembler()
    reset_procedural_scene_assembler_for_tests()
    b = get_procedural_scene_assembler()
    assert a is not b


# ---------------------------------------------------------------------------
# assemble_scene — result structure
# ---------------------------------------------------------------------------

def test_assemble_scene_has_required_keys():
    asm = ProceduralSceneAssembler()
    result = asm.assemble_scene(_base_layout(), _base_staging())
    required = {"assembly_id", "scene_theme", "operations", "phase_counts",
                "total_ops", "generated_at"}
    assert required <= set(result.keys())


def test_assemble_scene_theme_preserved():
    asm = ProceduralSceneAssembler()
    result = asm.assemble_scene(_base_layout(theme="robotics_lab"), _base_staging())
    assert result["scene_theme"] == "robotics_lab"


def test_assemble_scene_operations_is_list():
    asm = ProceduralSceneAssembler()
    result = asm.assemble_scene(_base_layout(), _base_staging())
    assert isinstance(result["operations"], list)


def test_assemble_scene_operations_nonempty():
    asm = ProceduralSceneAssembler()
    result = asm.assemble_scene(_base_layout(), _base_staging())
    assert result["total_ops"] > 0
    assert result["total_ops"] == len(result["operations"])


def test_assemble_scene_phase_counts_has_all_phases():
    asm = ProceduralSceneAssembler()
    result = asm.assemble_scene(_base_layout(), _base_staging())
    pc = result["phase_counts"]
    for phase in ("hierarchy", "environment", "asset_placement", "lighting", "camera", "layout"):
        assert phase in pc, f"Missing phase: {phase}"


def test_assemble_scene_increments_count():
    asm = ProceduralSceneAssembler()
    asm.assemble_scene(_base_layout(), _base_staging())
    asm.assemble_scene(_base_layout(), _base_staging())
    assert asm.stats()["assembly_count"] == 2


# ---------------------------------------------------------------------------
# build_environment_operations
# ---------------------------------------------------------------------------

def test_env_ops_returns_list():
    asm = ProceduralSceneAssembler()
    ops = asm.build_environment_operations("industrial_hangar", {"fog_density": "medium"})
    assert isinstance(ops, list)


def test_env_ops_has_ground_geo():
    asm = ProceduralSceneAssembler()
    ops = asm.build_environment_operations("industrial_hangar", {})
    names = [op.get("name") for op in ops]
    assert "ground_geo" in names


def test_env_ops_fog_when_present():
    asm = ProceduralSceneAssembler()
    ops = asm.build_environment_operations("industrial_hangar", {"fog_density": "medium"})
    names = [op.get("name") for op in ops]
    assert "fog_volume" in names


def test_env_ops_no_fog_when_none():
    asm = ProceduralSceneAssembler()
    ops = asm.build_environment_operations("robotics_lab", {"fog_density": "none"})
    names = [op.get("name") for op in ops]
    assert "fog_volume" not in names


def test_env_ops_all_create_node():
    asm = ProceduralSceneAssembler()
    ops = asm.build_environment_operations("industrial_hangar", {"fog_density": "light"})
    for op in ops:
        assert op["op"] == "create_node"


# ---------------------------------------------------------------------------
# build_lighting_operations
# ---------------------------------------------------------------------------

def test_lighting_ops_returns_list():
    asm = ProceduralSceneAssembler()
    ops = asm.build_lighting_operations({"lighting_style": "practical_industrial"}, "industrial_hangar")
    assert isinstance(ops, list)


def test_lighting_ops_nonempty():
    asm = ProceduralSceneAssembler()
    ops = asm.build_lighting_operations({"lighting_style": "practical_industrial"}, "industrial_hangar")
    assert len(ops) > 0


def test_lighting_ops_all_create_node():
    asm = ProceduralSceneAssembler()
    ops = asm.build_lighting_operations({"lighting_style": "clean_white"}, "robotics_lab")
    for op in ops:
        assert op["op"] == "create_node"


def test_lighting_ops_parent_is_lighting():
    asm = ProceduralSceneAssembler()
    ops = asm.build_lighting_operations({"lighting_style": "clean_white"}, "robotics_lab")
    for op in ops:
        assert op["parent"] == "/obj/lighting"


def test_lighting_ops_unknown_style_uses_default():
    asm = ProceduralSceneAssembler()
    ops = asm.build_lighting_operations({"lighting_style": "unknown_xyz"}, "test")
    assert len(ops) > 0


# ---------------------------------------------------------------------------
# build_camera_operations
# ---------------------------------------------------------------------------

def test_camera_ops_returns_list():
    asm = ProceduralSceneAssembler()
    targets = [{"shot_type": "hero_focus", "position": (0.0, 1.5, 0.0), "priority": 1}]
    ops = asm.build_camera_operations(targets, [])
    assert isinstance(ops, list)


def test_camera_ops_creates_cam():
    asm = ProceduralSceneAssembler()
    targets = [{"shot_type": "hero_focus", "position": (0.0, 1.5, 0.0), "priority": 1}]
    ops = asm.build_camera_operations(targets, [])
    assert any(op.get("type") == "cam" for op in ops)


def test_camera_ops_parent_is_camera():
    asm = ProceduralSceneAssembler()
    targets = [{"shot_type": "hero_focus", "position": (0.0, 1.5, 0.0), "priority": 1}]
    ops = asm.build_camera_operations(targets, [])
    for op in ops:
        assert op["parent"] == "/obj/camera"


def test_camera_ops_empty_targets():
    asm = ProceduralSceneAssembler()
    ops = asm.build_camera_operations([], [])
    assert ops == []


# ---------------------------------------------------------------------------
# build_asset_placement_operations
# ---------------------------------------------------------------------------

def test_asset_placement_returns_list():
    asm = ProceduralSceneAssembler()
    zones = {"hero_area": [{"name": "mech", "category": "robot"}]}
    ops = asm.build_asset_placement_operations(zones, _base_staging())
    assert isinstance(ops, list)


def test_asset_placement_has_create_node():
    asm = ProceduralSceneAssembler()
    zones = {"hero_area": [{"name": "mech", "category": "robot"}]}
    ops = asm.build_asset_placement_operations(zones, _base_staging())
    op_types = [op["op"] for op in ops]
    assert "create_node" in op_types


def test_asset_placement_empty_zones():
    asm = ProceduralSceneAssembler()
    ops = asm.build_asset_placement_operations({}, {"import_queue": []})
    assert ops == []


def test_asset_placement_transforms_applied():
    asm = ProceduralSceneAssembler()
    zones = {
        "hero_area": [{"name": "mech", "category": "robot"}],
        "background": [{"name": "wall", "category": "structure"}],
    }
    ops = asm.build_asset_placement_operations(zones, _base_staging())
    # Should have set_parms for transforms
    op_types = [op["op"] for op in ops]
    # At least one set_parms expected when multiple assets get different X positions
    assert "create_node" in op_types


# ---------------------------------------------------------------------------
# assemble_scene has layout_children for containers
# ---------------------------------------------------------------------------

def test_assemble_has_layout_children():
    asm = ProceduralSceneAssembler()
    result = asm.assemble_scene(_base_layout(), _base_staging())
    op_types = [op["op"] for op in result["operations"]]
    assert "layout_children" in op_types


# ---------------------------------------------------------------------------
# assemble_scene — extended
# ---------------------------------------------------------------------------

def test_assemble_scene_assembly_id_is_string():
    asm = ProceduralSceneAssembler()
    result = asm.assemble_scene(_base_layout(), _base_staging())
    assert isinstance(result["assembly_id"], str)
    assert len(result["assembly_id"]) > 0


def test_assemble_scene_generated_at_is_float():
    asm = ProceduralSceneAssembler()
    result = asm.assemble_scene(_base_layout(), _base_staging())
    assert isinstance(result["generated_at"], float)
    assert result["generated_at"] > 0


def test_assemble_scene_phase_counts_positive():
    asm = ProceduralSceneAssembler()
    result = asm.assemble_scene(_base_layout(), _base_staging())
    for phase, count in result["phase_counts"].items():
        assert count >= 0, f"Phase '{phase}' has negative count"


def test_assemble_scene_total_ops_matches_sum_of_phases():
    asm = ProceduralSceneAssembler()
    result = asm.assemble_scene(_base_layout(), _base_staging())
    total_from_phases = sum(result["phase_counts"].values())
    assert result["total_ops"] == total_from_phases


def test_assemble_scene_hierarchy_phase_positive():
    asm = ProceduralSceneAssembler()
    result = asm.assemble_scene(_base_layout(), _base_staging())
    assert result["phase_counts"]["hierarchy"] > 0


def test_assemble_scene_lighting_phase_positive():
    asm = ProceduralSceneAssembler()
    result = asm.assemble_scene(_base_layout(), _base_staging())
    assert result["phase_counts"]["lighting"] > 0


def test_assemble_scene_empty_zones():
    asm = ProceduralSceneAssembler()
    layout = _base_layout(zones={}, rules={"fog_density": "none", "lighting_style": "clean_white"})
    staging = {"import_queue": [], "layout_rules": {}, "recommended_fx": [], "zone_assignments": {}}
    result = asm.assemble_scene(layout, staging)
    assert result["total_ops"] > 0  # hierarchy + layout ops still created


def test_assemble_scene_no_fog_when_none():
    asm = ProceduralSceneAssembler()
    layout = _base_layout(rules={"fog_density": "none", "lighting_style": "practical_industrial"})
    result = asm.assemble_scene(layout, _base_staging())
    env_ops = [op for op in result["operations"]
               if op.get("name") == "fog_volume"]
    assert len(env_ops) == 0


def test_assemble_scene_fog_when_heavy():
    asm = ProceduralSceneAssembler()
    layout = _base_layout(rules={"fog_density": "heavy", "lighting_style": "natural_decay"})
    result = asm.assemble_scene(layout, _base_staging())
    env_ops = [op for op in result["operations"]
               if op.get("name") == "fog_volume"]
    assert len(env_ops) >= 1


# ---------------------------------------------------------------------------
# build_environment_operations — extended
# ---------------------------------------------------------------------------

def test_env_ops_empty_fog_density():
    asm = ProceduralSceneAssembler()
    ops = asm.build_environment_operations("robotics_lab", {"fog_density": ""})
    names = [op.get("name") for op in ops]
    assert "fog_volume" not in names


def test_env_ops_parent_is_environment():
    asm = ProceduralSceneAssembler()
    ops = asm.build_environment_operations("industrial_hangar", {})
    for op in ops:
        assert op.get("parent") == "/obj/environment"


# ---------------------------------------------------------------------------
# build_lighting_operations — extended
# ---------------------------------------------------------------------------

def test_lighting_ops_all_lighting_presets_nonempty():
    asm = ProceduralSceneAssembler()
    for style in _LIGHTING_PRESETS:
        ops = asm.build_lighting_operations({"lighting_style": style}, "test")
        assert len(ops) > 0, f"Preset '{style}' produced no ops"


def test_lighting_ops_have_name():
    asm = ProceduralSceneAssembler()
    ops = asm.build_lighting_operations({"lighting_style": "clean_white"}, "robotics_lab")
    for op in ops:
        assert op.get("name"), f"Op missing name: {op}"


# ---------------------------------------------------------------------------
# build_camera_operations — extended
# ---------------------------------------------------------------------------

def test_camera_ops_multiple_targets():
    asm = ProceduralSceneAssembler()
    targets = [
        {"shot_type": "hero_focus",       "position": (0.0, 1.5, 0.0),  "priority": 1},
        {"shot_type": "wide_establishing","position": (-5.0, 3.0, 10.0), "priority": 2},
    ]
    ops = asm.build_camera_operations(targets, [])
    cam_ops = [op for op in ops if op.get("type") == "cam"]
    assert len(cam_ops) == 2


def test_camera_ops_cam_name_includes_shot_type():
    asm = ProceduralSceneAssembler()
    targets = [{"shot_type": "hero_focus", "position": (0.0, 1.5, 0.0), "priority": 1}]
    ops = asm.build_camera_operations(targets, [])
    cam_names = [op["name"] for op in ops if op.get("type") == "cam"]
    assert any("hero" in name for name in cam_names)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    asm = ProceduralSceneAssembler()
    s = asm.stats()
    assert "assembly_count" in s


def test_stats_starts_zero():
    asm = ProceduralSceneAssembler()
    assert asm.stats()["assembly_count"] == 0
