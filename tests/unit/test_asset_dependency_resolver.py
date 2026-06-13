"""
Tests for AssetDependencyResolver (Tier 13)
"""
import pytest

from src.runtime.assets.realization import (
    get_asset_dependency_resolver,
    reset_asset_dependency_resolver_for_tests,
    DependencyResult,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_asset_dependency_resolver_for_tests()
    yield
    reset_asset_dependency_resolver_for_tests()


def test_singleton():
    assert get_asset_dependency_resolver() is get_asset_dependency_resolver()


def test_collect_dependencies_empty_asset():
    result = get_asset_dependency_resolver().collect_dependencies({})
    assert "textures" in result
    assert "materials" in result
    assert "references" in result
    assert "external_files" in result
    assert isinstance(result["textures"], list)
    assert isinstance(result["materials"], list)
    assert isinstance(result["references"], list)


def test_resolve_materials_returns_list():
    result = get_asset_dependency_resolver().resolve_materials({})
    assert isinstance(result, list)


def test_resolve_materials_from_list():
    result = get_asset_dependency_resolver().resolve_materials({
        "materials": [{"name": "metal_mat", "type": "pbr"}, {"name": "glass_mat"}]
    })
    assert len(result) == 2
    assert result[0]["name"] == "metal_mat"


def test_resolve_textures_returns_list():
    result = get_asset_dependency_resolver().resolve_textures({})
    assert isinstance(result, list)


def test_resolve_references_returns_list():
    result = get_asset_dependency_resolver().resolve_references({})
    assert isinstance(result, list)


def test_resolve_returns_dependency_result():
    result = get_asset_dependency_resolver().resolve({"asset_id": "d1", "name": "Robot"})
    assert isinstance(result, DependencyResult)
    assert result.ok is True
    assert isinstance(result.textures, list)
    assert isinstance(result.materials, list)
    assert isinstance(result.references, list)
    assert isinstance(result.missing_deps, list)


def test_validate_dependencies_valid_result():
    dep = get_asset_dependency_resolver().resolve({"asset_id": "d2"})
    validation = get_asset_dependency_resolver().validate_dependencies(dep)
    assert "valid" in validation
    assert "errors" in validation
    assert "warnings" in validation
    assert validation["valid"] is True


def test_build_dependency_report():
    resolver = get_asset_dependency_resolver()
    r1 = resolver.resolve({"asset_id": "d3"})
    r2 = resolver.resolve({"asset_id": "d4"})
    report = resolver.build_dependency_report([r1, r2])
    assert "total" in report
    assert "successful" in report
    assert "failed" in report
    assert report["total"] == 2


def test_to_dict_from_dict_round_trip():
    result = get_asset_dependency_resolver().resolve({"asset_id": "d5"})
    d = result.to_dict()
    restored = DependencyResult.from_dict(d)
    assert restored.asset_id == result.asset_id
    assert restored.ok == result.ok


def test_never_raises():
    result = get_asset_dependency_resolver().resolve(None)  # type: ignore
    assert isinstance(result, DependencyResult)
