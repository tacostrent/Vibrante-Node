"""Tests for src.runtime.environment.environment_blueprint"""
import pytest
from src.runtime.environment.environment_blueprint import EnvironmentBlueprint


@pytest.fixture(autouse=True)
def reset_singletons():
    yield


class TestEnvironmentBlueprintSerialization:
    def test_to_dict_roundtrip(self):
        bp = EnvironmentBlueprint(
            environment_name="test_env",
            environment_category="industrial",
            required_structure=["floor", "wall"],
            optional_structure=["ceiling"],
            required_zones=["hero_zone", "entrance_zone"],
            required_anchors=["main_prop"],
            recommended_assets=["barrel", "crate"],
            atmosphere_profile="industrial_haze",
            construction_order=["structure", "zones", "anchors"],
            description="Test environment.",
        )
        d = bp.to_dict()
        bp2 = EnvironmentBlueprint.from_dict(d)
        assert bp2.environment_name == "test_env"
        assert bp2.environment_category == "industrial"
        assert bp2.required_structure == ["floor", "wall"]
        assert bp2.optional_structure == ["ceiling"]
        assert bp2.required_zones == ["hero_zone", "entrance_zone"]
        assert bp2.required_anchors == ["main_prop"]
        assert bp2.recommended_assets == ["barrel", "crate"]
        assert bp2.atmosphere_profile == "industrial_haze"
        assert bp2.description == "Test environment."

    def test_from_dict_defaults(self):
        bp = EnvironmentBlueprint.from_dict({})
        assert bp.environment_name == ""
        assert bp.environment_category == "interior"
        assert bp.atmosphere_profile == "warm_interior"
        assert isinstance(bp.construction_order, list)
        assert len(bp.construction_order) > 0

    def test_from_dict_construction_order_default(self):
        bp = EnvironmentBlueprint.from_dict({"environment_name": "x"})
        assert "structure" in bp.construction_order
        assert "zones" in bp.construction_order
        assert "anchors" in bp.construction_order


class TestEnvironmentBlueprintValidation:
    def test_validate_returns_empty_for_valid(self):
        bp = EnvironmentBlueprint(
            environment_name="good_env",
            required_structure=["floor", "wall"],
            required_zones=["hero_zone"],
            required_anchors=["main_prop"],
            atmosphere_profile="warm_interior",
        )
        errors = bp.validate()
        assert errors == []

    def test_validate_empty_environment_name(self):
        bp = EnvironmentBlueprint(
            environment_name="",
            required_structure=["floor"],
            required_zones=["hero_zone"],
            required_anchors=["main_prop"],
            atmosphere_profile="warm_interior",
        )
        errors = bp.validate()
        assert any("environment_name" in e for e in errors)

    def test_validate_empty_required_structure(self):
        bp = EnvironmentBlueprint(
            environment_name="test",
            required_structure=[],
            required_zones=["hero_zone"],
            required_anchors=["main_prop"],
            atmosphere_profile="warm_interior",
        )
        errors = bp.validate()
        assert any("required_structure" in e for e in errors)

    def test_validate_empty_required_zones(self):
        bp = EnvironmentBlueprint(
            environment_name="test",
            required_structure=["floor"],
            required_zones=[],
            required_anchors=["main_prop"],
            atmosphere_profile="warm_interior",
        )
        errors = bp.validate()
        assert any("required_zones" in e for e in errors)

    def test_validate_empty_required_anchors(self):
        bp = EnvironmentBlueprint(
            environment_name="test",
            required_structure=["floor"],
            required_zones=["hero_zone"],
            required_anchors=[],
            atmosphere_profile="warm_interior",
        )
        errors = bp.validate()
        assert any("required_anchors" in e for e in errors)

    def test_validate_multiple_errors(self):
        bp = EnvironmentBlueprint(
            environment_name="",
            required_structure=[],
            required_zones=[],
            required_anchors=[],
            atmosphere_profile="",
        )
        errors = bp.validate()
        assert len(errors) >= 4
