"""Tests for src.runtime.environment.environment_zone_builder"""
import pytest
from src.runtime.environment.environment_zone_builder import (
    get_environment_zone_builder,
    reset_environment_zone_builder_for_tests,
    ZonePlan,
    EnvironmentZone,
)
from src.runtime.environment.environment_template_library import (
    reset_environment_template_library_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_environment_zone_builder_for_tests()
    reset_environment_template_library_for_tests()
    yield
    reset_environment_zone_builder_for_tests()
    reset_environment_template_library_for_tests()


class TestBuildZones:
    def test_western_room_has_at_least_4_zones(self):
        builder = get_environment_zone_builder()
        plan = builder.build_zones("western_room")
        assert plan.zone_count >= 4

    def test_industrial_hangar_has_hero_zone(self):
        builder = get_environment_zone_builder()
        plan = builder.build_zones("industrial_hangar")
        zone_types = {z.zone_type for z in plan.zones}
        assert "hero_zone" in zone_types

    def test_all_20_environments_have_hero_zone(self):
        from src.runtime.environment.environment_template_library import get_environment_template_library
        builder = get_environment_zone_builder()
        lib = get_environment_template_library()
        for name in lib.list_templates():
            plan = builder.build_zones(name)
            zone_types = {z.zone_type for z in plan.zones}
            assert "hero_zone" in zone_types, f"{name} missing hero_zone"

    def test_all_20_environments_have_entrance_zone(self):
        from src.runtime.environment.environment_template_library import get_environment_template_library
        builder = get_environment_zone_builder()
        lib = get_environment_template_library()
        for name in lib.list_templates():
            plan = builder.build_zones(name)
            zone_types = {z.zone_type for z in plan.zones}
            assert "entrance_zone" in zone_types, f"{name} missing entrance_zone"

    def test_minimum_zones_present(self):
        builder = get_environment_zone_builder()
        plan = builder.build_zones("castle_hall")
        zone_types = {z.zone_type for z in plan.zones}
        assert "decoration_zone" in zone_types
        assert "atmosphere_zone" in zone_types

    def test_no_duplicate_zone_types(self):
        builder = get_environment_zone_builder()
        plan = builder.build_zones("office")
        zone_types = [z.zone_type for z in plan.zones]
        assert len(zone_types) == len(set(zone_types))

    def test_unknown_environment_gets_minimum_zones(self):
        builder = get_environment_zone_builder()
        plan = builder.build_zones("nonexistent_xyz")
        assert plan.zone_count >= 4

    def test_blueprint_supplement_adds_zones(self):
        from src.runtime.environment.environment_blueprint import EnvironmentBlueprint
        bp = EnvironmentBlueprint(
            environment_name="test",
            required_structure=["floor"],
            required_zones=["hero_zone", "entrance_zone", "seating_zone", "service_zone", "wall_zone"],
            required_anchors=["main_prop"],
            atmosphere_profile="warm_interior",
        )
        builder = get_environment_zone_builder()
        plan = builder.build_zones("western_room", blueprint=bp)
        zone_types = {z.zone_type for z in plan.zones}
        assert "seating_zone" in zone_types
        assert "service_zone" in zone_types


class TestValidateZones:
    def test_validate_returns_empty_for_valid_plan(self):
        builder = get_environment_zone_builder()
        plan = builder.build_zones("western_room")
        errors = builder.validate_zones(plan)
        assert errors == []

    def test_validate_detects_empty_zones(self):
        plan = ZonePlan(environment_name="test", zones=[], zone_count=0)
        builder = get_environment_zone_builder()
        errors = builder.validate_zones(plan)
        assert len(errors) > 0
        assert any("no zones" in e for e in errors)

    def test_validate_detects_missing_hero_zone(self):
        zone = EnvironmentZone(zone_id="z1", zone_type="entrance_zone", display_name="Entrance",
                               description="", max_assets=4, required=True, position_hint="foreground")
        plan = ZonePlan(environment_name="test", zones=[zone, zone], zone_count=1)
        builder = get_environment_zone_builder()
        errors = builder.validate_zones(plan)
        assert any("hero_zone" in e for e in errors)


class TestGetZone:
    def test_get_zone_finds_by_type(self):
        builder = get_environment_zone_builder()
        plan = builder.build_zones("office")
        hero = builder.get_zone(plan, "hero_zone")
        assert hero is not None
        assert hero.zone_type == "hero_zone"

    def test_get_zone_returns_none_for_missing(self):
        builder = get_environment_zone_builder()
        plan = builder.build_zones("desert")
        result = builder.get_zone(plan, "nonexistent_zone_type")
        assert result is None


class TestSerialization:
    def test_zone_plan_roundtrip(self):
        builder = get_environment_zone_builder()
        plan = builder.build_zones("library")
        d = plan.to_dict()
        plan2 = ZonePlan.from_dict(d)
        assert plan2.environment_name == plan.environment_name
        assert plan2.zone_count == plan.zone_count
