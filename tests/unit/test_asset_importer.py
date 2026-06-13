"""
Tests for AssetImporter (Tier 13)
"""
import pytest
import time

from src.runtime.assets.realization import (
    get_asset_importer,
    reset_asset_importer_for_tests,
    SUPPORTED_FORMATS,
    ImportResult,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_asset_importer_for_tests()
    yield
    reset_asset_importer_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_is_same_instance():
    a = get_asset_importer()
    b = get_asset_importer()
    assert a is b


def test_reset_gives_new_instance():
    a = get_asset_importer()
    reset_asset_importer_for_tests()
    b = get_asset_importer()
    assert a is not b


# ---------------------------------------------------------------------------
# import_asset
# ---------------------------------------------------------------------------

def test_import_asset_minimal_dict():
    result = get_asset_importer().import_asset({"asset_id": "a1", "name": "Box"})
    assert isinstance(result, ImportResult)
    assert result.asset_id == "a1"
    assert result.asset_name == "Box"


def test_import_asset_has_required_keys():
    result = get_asset_importer().import_asset({"asset_id": "a2"})
    d = result.to_dict()
    for key in ("ok", "asset_id", "asset_name", "format", "source_type",
                "file_path", "metadata", "provenance", "errors", "warnings", "imported_at"):
        assert key in d


def test_import_asset_unknown_format_ok_with_warning():
    result = get_asset_importer().import_asset({"asset_id": "a3", "format": "xyz123"})
    assert result.ok is True
    assert len(result.warnings) > 0
    assert result.format == "xyz123"


def test_import_asset_supported_format_preserved():
    result = get_asset_importer().import_asset({"asset_id": "a4", "name": "Robot", "format": "fbx"})
    assert result.ok is True
    assert result.format == "fbx"
    assert "fbx" in SUPPORTED_FORMATS


def test_import_from_storage_returns_import_result():
    result = get_asset_importer().import_from_storage("asset_5", "/path/to/file.usd")
    assert isinstance(result, ImportResult)
    assert result.asset_id == "asset_5"
    assert result.source_type == "storage"


def test_import_from_provider_returns_import_result():
    result = get_asset_importer().import_from_provider("sketchfab", "sf_001")
    assert isinstance(result, ImportResult)
    assert result.asset_id == "sf_001"


def test_validate_import_valid_result():
    result = get_asset_importer().import_asset({"asset_id": "a6", "name": "Chair"})
    validation = get_asset_importer().validate_import(result)
    assert validation["valid"] is True
    assert isinstance(validation["errors"], list)
    assert isinstance(validation["warnings"], list)


def test_build_import_report_has_required_keys():
    importer = get_asset_importer()
    r1 = importer.import_asset({"asset_id": "a7"})
    r2 = importer.import_asset({"asset_id": "a8", "format": "usd"})
    report = importer.build_import_report([r1, r2])
    assert "total" in report
    assert "successful" in report
    assert "failed" in report
    assert report["total"] == 2


def test_import_result_to_dict_from_dict_round_trip():
    original = get_asset_importer().import_asset({"asset_id": "a9", "name": "Sphere", "format": "gltf"})
    d = original.to_dict()
    restored = ImportResult.from_dict(d)
    assert restored.asset_id == original.asset_id
    assert restored.format == original.format
    assert restored.ok == original.ok


def test_import_asset_never_raises():
    # Even with a completely broken dict
    result = get_asset_importer().import_asset(None)  # type: ignore
    assert isinstance(result, ImportResult)


def test_imported_at_is_float():
    result = get_asset_importer().import_asset({"asset_id": "a10"})
    assert isinstance(result.imported_at, float)
    assert result.imported_at > 0


def test_stats_increments():
    importer = get_asset_importer()
    before = importer.stats()["import_count"]
    importer.import_asset({"asset_id": "a11"})
    importer.import_asset({"asset_id": "a12"})
    after = importer.stats()["import_count"]
    assert after == before + 2
