"""Tests for src.runtime.environment.environment_completeness"""
import pytest
from src.runtime.environment.environment_completeness import (
    get_environment_completeness,
    reset_environment_completeness_for_tests,
    CompletenessResult,
)
from src.runtime.environment.environment_structure_builder import (
    get_environment_structure_builder,
    reset_environment_structure_builder_for_tests,
)
from src.runtime.environment.environment_zone_builder import (
    get_environment_zone_builder,
    reset_environment_zone_builder_for_tests,
)
from src.runtime.environment.anchor_asset_builder import (
    get_anchor_asset_builder,
    reset_anchor_asset_builder_for_tests,
)
from src.runtime.environment.support_asset_builder import (
    get_support_asset_builder,
    reset_support_asset_builder_for_tests,
)
from src.runtime.environment.decorative_population import (
    get_decorative_population,
    reset_decorative_population_for_tests,
)
from src.runtime.environment.atmosphere_builder import (
    get_atmosphere_builder,
    reset_atmosphere_builder_for_tests,
)
from src.runtime.environment.environment_template_library import (
    reset_environment_template_library_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_environment_completeness_for_tests()
    reset_environment_structure_builder_for_tests()
    reset_environment_zone_builder_for_tests()
    reset_anchor_asset_builder_for_tests()
    reset_support_asset_builder_for_tests()
    reset_decorative_population_for_tests()
    reset_atmosphere_builder_for_tests()
    reset_environment_template_library_for_tests()
    yield
    reset_environment_completeness_for_tests()
    reset_environment_structure_builder_for_tests()
    reset_environment_zone_builder_for_tests()
    reset_anchor_asset_builder_for_tests()
    reset_support_asset_builder_for_tests()
    reset_decorative_population_for_tests()
    reset_atmosphere_builder_for_tests()
    reset_environment_template_library_for_tests()


def _build_full_plans(env_name):
    struct = get_environment_structure_builder().build_environment(env_name)
    zones  = get_environment_zone_builder().build_zones(env_name)
    anchors = get_anchor_asset_builder().build_anchors(env_name)
    support = get_support_asset_builder().build_support_assets(env_name, anchors)
    deco    = get_decorative_population().populate(env_name, anchors)
    atm     = get_atmosphere_builder().build_atmosphere(env_name)
    return struct, zones, anchors, support, deco, atm


class TestCheckFull:
    def test_full_plans_all_required_met(self):
        struct, zones, anchors, support, deco, atm = _build_full_plans("western_room")
        checker = get_environment_completeness()
        result = checker.check(
            "western_room",
            structure_plan=struct,
            zone_plan=zones,
            anchor_plan=anchors,
            support_plan=support,
            decoration_plan=deco,
            atmosphere_plan=atm,
        )
        assert result.floor_exists is True
        assert result.walls_exist is True
        assert result.zones_exist is True
        assert result.anchors_exist is True
        assert result.all_required_met is True

    def test_full_plans_high_completeness_score(self):
        struct, zones, anchors, support, deco, atm = _build_full_plans("industrial_hangar")
        checker = get_environment_completeness()
        result = checker.check(
            "industrial_hangar",
            structure_plan=struct,
            zone_plan=zones,
            anchor_plan=anchors,
            support_plan=support,
            decoration_plan=deco,
            atmosphere_plan=atm,
        )
        assert result.completeness_score >= 0.7


class TestCheckNoneStructure:
    def test_none_structure_floor_exists_false(self):
        checker = get_environment_completeness()
        result = checker.check("test_env", structure_plan=None)
        assert result.floor_exists is False
        assert result.walls_exist is False
        assert "floor" in result.missing_required or "walls" in result.missing_required

    def test_none_structure_reduces_score(self):
        _, zones, anchors, support, deco, atm = _build_full_plans("office")
        checker = get_environment_completeness()

        # With structure
        struct = get_environment_structure_builder().build_environment("office")
        result_with = checker.check("office", structure_plan=struct, zone_plan=zones)

        # Without structure
        result_without = checker.check("office", structure_plan=None, zone_plan=zones)

        assert result_with.completeness_score > result_without.completeness_score


class TestScoreIncreases:
    def test_completeness_score_increases_with_more_components(self):
        checker = get_environment_completeness()

        # No components
        r0 = checker.check("castle_hall")
        assert r0.completeness_score < 0.5

        # Add structure
        struct = get_environment_structure_builder().build_environment("castle_hall")
        r1 = checker.check("castle_hall", structure_plan=struct)
        assert r1.completeness_score > r0.completeness_score

        # Add zones
        zones = get_environment_zone_builder().build_zones("castle_hall")
        r2 = checker.check("castle_hall", structure_plan=struct, zone_plan=zones)
        assert r2.completeness_score >= r1.completeness_score


class TestSerialization:
    def test_result_roundtrip(self):
        struct, zones, anchors, support, deco, atm = _build_full_plans("library")
        checker = get_environment_completeness()
        result = checker.check("library", structure_plan=struct, zone_plan=zones,
                               anchor_plan=anchors, support_plan=support,
                               decoration_plan=deco, atmosphere_plan=atm)
        d = result.to_dict()
        result2 = CompletenessResult.from_dict(d)
        assert result2.environment_name == result.environment_name
        assert result2.all_required_met == result.all_required_met
        assert abs(result2.completeness_score - result.completeness_score) < 0.001
