"""Tests for src.runtime.environment.environment_structure_builder"""
import pytest
from src.runtime.environment.environment_structure_builder import (
    get_environment_structure_builder,
    reset_environment_structure_builder_for_tests,
    EnvironmentStructurePlan,
    BuiltStructuralElement,
)
from src.runtime.environment.environment_template_library import (
    reset_environment_template_library_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_environment_structure_builder_for_tests()
    reset_environment_template_library_for_tests()
    yield
    reset_environment_structure_builder_for_tests()
    reset_environment_template_library_for_tests()


class TestBuildEnvironment:
    def test_western_room_is_complete(self):
        builder = get_environment_structure_builder()
        plan = builder.build_environment("western_room")
        assert plan.structure_complete is True
        assert plan.floor_present is True
        assert plan.walls_present is True
        assert len(plan.elements) >= 2

    def test_industrial_hangar_has_floor_walls_columns(self):
        builder = get_environment_structure_builder()
        plan = builder.build_environment("industrial_hangar")
        assert plan.floor_present is True
        assert plan.walls_present is True
        assert len(plan.elements) >= 3
        elem_types = [e.element_type for e in plan.elements]
        # Should have a column or steel element
        has_structure = any("column" in t or "steel" in t or "roof" in t for t in elem_types)
        assert has_structure

    def test_unknown_environment_returns_generic(self):
        builder = get_environment_structure_builder()
        plan = builder.build_environment("nonexistent_xyz")
        # Generic fallback: floor + wall are always present
        # build_environment always preserves the caller-supplied name
        assert plan.environment_name == "nonexistent_xyz"
        assert plan.floor_present is True
        assert plan.walls_present is True

    def test_all_20_environments_can_be_built(self):
        from src.runtime.environment.environment_template_library import get_environment_template_library
        builder = get_environment_structure_builder()
        lib = get_environment_template_library()
        for name in lib.list_templates():
            plan = builder.build_environment(name)
            assert plan.environment_name == name
            assert isinstance(plan.elements, list)

    def test_no_exceptions_on_build(self):
        builder = get_environment_structure_builder()
        # Should never raise
        plan = builder.build_environment("office")
        assert plan is not None


class TestBuildStructure:
    def test_build_structure_from_blueprint(self):
        from src.runtime.environment.environment_blueprint import EnvironmentBlueprint
        bp = EnvironmentBlueprint(
            environment_name="custom",
            required_structure=["floor", "wall", "ceiling"],
            optional_structure=["window"],
            required_zones=[],
            required_anchors=[],
            atmosphere_profile="warm_interior",
        )
        builder = get_environment_structure_builder()
        plan = builder.build_structure(bp)
        assert plan.floor_present is True
        assert plan.walls_present is True
        assert plan.ceiling_present is True
        assert len(plan.elements) >= 4


class TestSubBuilders:
    def test_build_floor_returns_non_empty(self):
        builder = get_environment_structure_builder()
        floors = builder.build_floor("western_room")
        assert len(floors) >= 1
        assert all(isinstance(e, BuiltStructuralElement) for e in floors)

    def test_build_walls_returns_non_empty(self):
        builder = get_environment_structure_builder()
        walls = builder.build_walls("western_room")
        assert len(walls) >= 1

    def test_build_ceiling_returns_non_empty_for_indoor(self):
        builder = get_environment_structure_builder()
        ceilings = builder.build_ceiling("office")
        assert len(ceilings) >= 1

    def test_build_doors_returns_results(self):
        builder = get_environment_structure_builder()
        doors = builder.build_doors("western_room")
        # western_room requires a door
        assert len(doors) >= 1

    def test_build_windows_returns_results(self):
        builder = get_environment_structure_builder()
        # windows are optional in western_room
        windows = builder.build_windows("western_room")
        # May be 0 or more
        assert isinstance(windows, list)


class TestValidateStructure:
    def test_validate_complete_structure_returns_empty(self):
        builder = get_environment_structure_builder()
        plan = builder.build_environment("western_room")
        errors = builder.validate_structure(plan)
        assert errors == []

    def test_validate_detects_missing_floor(self):
        plan = EnvironmentStructurePlan(
            environment_name="test",
            floor_present=False,
            walls_present=True,
        )
        builder = get_environment_structure_builder()
        errors = builder.validate_structure(plan)
        assert any("floor" in e.lower() for e in errors)

    def test_validate_detects_missing_wall(self):
        plan = EnvironmentStructurePlan(
            environment_name="test",
            floor_present=True,
            walls_present=False,
        )
        builder = get_environment_structure_builder()
        errors = builder.validate_structure(plan)
        assert any("wall" in e.lower() for e in errors)


class TestSerialization:
    def test_plan_roundtrip(self):
        builder = get_environment_structure_builder()
        plan = builder.build_environment("warehouse")
        d = plan.to_dict()
        plan2 = EnvironmentStructurePlan.from_dict(d)
        assert plan2.environment_name == plan.environment_name
        assert plan2.structure_complete == plan.structure_complete
        assert len(plan2.elements) == len(plan.elements)
