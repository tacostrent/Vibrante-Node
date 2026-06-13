import pytest
from src.runtime.lookdev import (
    AssignmentEntry,
    AssignmentPlan,
    get_material_assignment_engine,
    reset_material_assignment_engine_for_tests,
    reset_material_recommendation_engine_for_tests,
    reset_material_library_for_tests,
    reset_material_knowledge_for_tests,
    reset_lookdev_patterns_for_tests,
    reset_renderer_profiles_for_tests,
)


@pytest.fixture(autouse=True)
def reset_all():
    reset_material_assignment_engine_for_tests()
    reset_material_recommendation_engine_for_tests()
    reset_material_library_for_tests()
    reset_material_knowledge_for_tests()
    reset_lookdev_patterns_for_tests()
    reset_renderer_profiles_for_tests()
    yield
    reset_material_assignment_engine_for_tests()
    reset_material_recommendation_engine_for_tests()
    reset_material_library_for_tests()
    reset_material_knowledge_for_tests()
    reset_lookdev_patterns_for_tests()
    reset_renderer_profiles_for_tests()


def test_singleton_identity():
    assert get_material_assignment_engine() is get_material_assignment_engine()


def test_assign_materials_returns_entry():
    entry = get_material_assignment_engine().assign_materials(
        {"asset_id": "a1", "name": "tank_chassis"}, "usd_preview_surface"
    )
    assert isinstance(entry, AssignmentEntry)
    assert entry.material_name != ""
    assert entry.renderer == "usd_preview_surface"


def test_assign_materials_has_ops():
    entry = get_material_assignment_engine().assign_materials(
        {"asset_id": "a2", "name": "concrete_slab"}, "arnold"
    )
    assert len(entry.assignment_ops) >= 1
    op = entry.assignment_ops[0]
    assert op.get("op") == "assign_material"
    assert op.get("renderer") == "arnold"


def test_generate_assignment_plan_ok():
    engine = get_material_assignment_engine()
    assets = [
        {"asset_id": "x1", "name": "pipe_01"},
        {"asset_id": "x2", "name": "concrete_block"},
    ]
    plan = engine.generate_assignment_plan(assets, "usd_preview_surface")
    assert isinstance(plan, AssignmentPlan)
    assert plan.ok is True
    assert plan.total_assets == 2
    assert plan.total_assigned == 2
    assert len(plan.assignments) == 2


def test_plan_assignments_have_material():
    plan = get_material_assignment_engine().generate_assignment_plan(
        [{"name": "forklift"}, {"name": "wall_panel"}], "karma"
    )
    for entry in plan.assignments:
        assert entry.material_name != ""


def test_assign_environment_materials():
    engine = get_material_assignment_engine()
    assets = [{"asset_id": "e1", "name": "shelf"}, {"asset_id": "e2", "name": "drum"}]
    plan = engine.assign_environment_materials("industrial_hangar", assets, "usd_preview_surface")
    assert isinstance(plan, AssignmentPlan)
    assert plan.ok is True
    assert len(plan.assignments) == 2


def test_validate_assignments_valid_plan():
    plan = get_material_assignment_engine().generate_assignment_plan(
        [{"asset_id": "v1", "name": "tank"}], "arnold"
    )
    validation = get_material_assignment_engine().validate_assignments(plan.to_dict())
    assert validation["ok"] is True
    assert isinstance(validation["errors"], list)


def test_validate_assignments_missing_material():
    result = get_material_assignment_engine().validate_assignments({
        "assignments": [{"asset_id": "x", "renderer": "arnold"}],
        "renderer": "arnold",
    })
    assert result["ok"] is False
    assert any("material_name" in e for e in result["errors"])


def test_entry_to_dict_keys():
    entry = AssignmentEntry(asset_id="a", material_name="glass", renderer="karma")
    d = entry.to_dict()
    for key in ("entry_id", "asset_id", "asset_name", "material_name",
                "material_id", "renderer", "confidence", "assignment_ops"):
        assert key in d


def test_entry_from_dict_round_trip():
    entry = AssignmentEntry(asset_id="rt", material_name="plastic", renderer="usd_preview_surface")
    restored = AssignmentEntry.from_dict(entry.to_dict())
    assert restored.asset_id == "rt"
    assert restored.material_name == "plastic"


def test_plan_to_dict_keys():
    plan = AssignmentPlan(renderer="arnold", total_assets=3, total_assigned=3)
    d = plan.to_dict()
    for key in ("plan_id", "assignments", "total_assets", "total_assigned",
                "renderer", "ok", "errors", "warnings", "created_at"):
        assert key in d


def test_never_raises_none():
    entry = get_material_assignment_engine().assign_materials(None, "usd_preview_surface")  # type: ignore
    assert isinstance(entry, AssignmentEntry)


def test_generate_plan_empty_list():
    plan = get_material_assignment_engine().generate_assignment_plan([], "usd_preview_surface")
    assert isinstance(plan, AssignmentPlan)
    assert plan.total_assets == 0
