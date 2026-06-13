"""
Tests for UsdBuilder (Tier 13)
"""
import pytest

from src.runtime.assets.realization import (
    get_usd_builder,
    reset_usd_builder_for_tests,
    UsdAsset,
    UsdBuildResult,
    USD_SCHEMA_VERSION,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_usd_builder_for_tests()
    yield
    reset_usd_builder_for_tests()


def test_singleton():
    assert get_usd_builder() is get_usd_builder()


def test_build_usd_asset_ok():
    result = get_usd_builder().build_usd_asset({"asset_id": "u1", "name": "Tank"})
    assert isinstance(result, UsdBuildResult)
    assert result.ok is True
    assert result.asset is not None


def test_build_usd_metadata_returns_required_keys():
    meta = get_usd_builder().build_usd_metadata({"asset_id": "u2", "name": "Robot"})
    assert "asset_name" in meta
    assert "schema_version" in meta
    assert "usd_type" in meta
    assert meta["schema_version"] == USD_SCHEMA_VERSION


def test_build_usd_hierarchy_has_required_keys():
    hierarchy = get_usd_builder().build_usd_hierarchy({"name": "Tank", "category": "vehicle"})
    assert "root" in hierarchy
    assert "xform" in hierarchy
    assert "mesh" in hierarchy


def test_validate_usd_asset_valid():
    result = get_usd_builder().build_usd_asset({"asset_id": "u3", "name": "Box"})
    validation = get_usd_builder().validate_usd_asset(result.asset)
    assert "valid" in validation
    assert validation["valid"] is True


def test_usd_schema_version_is_string():
    assert isinstance(USD_SCHEMA_VERSION, str)
    assert len(USD_SCHEMA_VERSION) > 0


def test_usd_asset_to_dict_from_dict():
    result = get_usd_builder().build_usd_asset({"asset_id": "u4", "name": "Sphere"})
    d = result.asset.to_dict()
    restored = UsdAsset.from_dict(d)
    assert restored.asset_id == result.asset.asset_id
    assert restored.asset_name == result.asset.asset_name


def test_built_at_is_float():
    result = get_usd_builder().build_usd_asset({"asset_id": "u5"})
    assert isinstance(result.asset.built_at, float)
    assert result.asset.built_at > 0


def test_never_raises():
    result = get_usd_builder().build_usd_asset(None)  # type: ignore
    assert isinstance(result, UsdBuildResult)
