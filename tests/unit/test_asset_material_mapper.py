"""
Tests for AssetMaterialMapper (Tier 13)
"""
import pytest

from src.runtime.assets.realization import (
    get_asset_material_mapper,
    reset_asset_material_mapper_for_tests,
    MaterialProfile,
    MaterialMappingResult,
    SUPPORTED_RENDERERS,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_asset_material_mapper_for_tests()
    yield
    reset_asset_material_mapper_for_tests()


def test_singleton():
    assert get_asset_material_mapper() is get_asset_material_mapper()


def test_supported_renderers_contains_expected():
    assert "arnold" in SUPPORTED_RENDERERS
    assert "usd_preview_surface" in SUPPORTED_RENDERERS
    assert "generic_pbr" in SUPPORTED_RENDERERS
    assert "karma" in SUPPORTED_RENDERERS


def test_map_materials_arnold():
    result = get_asset_material_mapper().map_materials(
        {"asset_id": "m1", "name": "Tank"}, "arnold"
    )
    assert isinstance(result, MaterialMappingResult)
    assert result.ok is True
    assert result.renderer == "arnold"
    assert result.material_count >= 1


def test_map_materials_usd_preview_surface():
    result = get_asset_material_mapper().map_materials(
        {"asset_id": "m2"}, "usd_preview_surface"
    )
    assert result.ok is True
    assert result.renderer == "usd_preview_surface"


def test_build_material_profile_has_required_fields():
    profile = get_asset_material_mapper().build_material_profile(
        {"name": "metal"}, "arnold"
    )
    assert isinstance(profile, MaterialProfile)
    assert profile.renderer == "arnold"
    assert isinstance(profile.base_color, list)
    assert isinstance(profile.roughness, float)
    assert isinstance(profile.metallic, float)
    assert isinstance(profile.opacity, float)


def test_validate_materials_valid():
    result = get_asset_material_mapper().map_materials({"asset_id": "m3"}, "karma")
    validation = get_asset_material_mapper().validate_materials(result)
    assert "valid" in validation
    assert "errors" in validation
    assert "warnings" in validation
    assert validation["valid"] is True


def test_extract_material_metadata_returns_dict():
    meta = get_asset_material_mapper().extract_material_metadata({
        "category": "vehicle",
        "style": "sci_fi",
        "has_pbr": True,
    })
    assert isinstance(meta, dict)
    assert "category" in meta
    assert meta["category"] == "vehicle"


def test_material_profile_to_dict_from_dict():
    profile = get_asset_material_mapper().build_material_profile(
        {"name": "glass"}, "usd_preview_surface"
    )
    d = profile.to_dict()
    restored = MaterialProfile.from_dict(d)
    assert restored.name == profile.name
    assert restored.renderer == profile.renderer


def test_unknown_renderer_ok_with_warning():
    result = get_asset_material_mapper().map_materials(
        {"asset_id": "m4"}, "unknown_renderer"
    )
    assert result.ok is True
    assert len(result.warnings) > 0
    # Falls back to generic_pbr
    assert result.renderer == "generic_pbr"


def test_never_raises():
    result = get_asset_material_mapper().map_materials(None, "arnold")  # type: ignore
    assert isinstance(result, MaterialMappingResult)
