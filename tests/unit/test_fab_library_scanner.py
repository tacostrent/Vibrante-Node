"""
Tests for FabLibraryScanner (Tier 12.5).
All tests use tmp_path — no network, no authentication.
"""
import json
import os
import pytest

from src.runtime.assets.acquisition import (
    FabAssetRecord,
    FabScanResult,
    get_fab_library_scanner,
    reset_fab_library_scanner_for_tests,
    ENV_FAB_LIBRARY,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_fab_library_scanner_for_tests()
    yield
    reset_fab_library_scanner_for_tests()


def _write_manifest(directory: str, data: dict) -> str:
    path = os.path.join(directory, "manifest.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def _make_fab_asset(tmp_path, name="Rock_Formation", asset_id="fab_abc123", category="prop"):
    asset_dir = tmp_path / asset_id
    asset_dir.mkdir()
    manifest_data = {"id": asset_id, "name": name, "category": category, "tags": ["rock", "stone"]}
    _write_manifest(str(asset_dir), manifest_data)
    # Add an FBX file
    (asset_dir / f"{name}.fbx").write_bytes(b"")
    return str(asset_dir)


def test_singleton_identity():
    assert get_fab_library_scanner() is get_fab_library_scanner()


def test_scan_empty_path_returns_warning():
    result = get_fab_library_scanner().scan_library("")
    assert result.ok is True
    assert len(result.warnings) > 0
    assert len(result.assets_found) == 0


def test_scan_nonexistent_path_returns_error():
    result = get_fab_library_scanner().scan_library("/no/such/path/xyz")
    assert result.ok is False
    assert len(result.errors) > 0


def test_scan_finds_manifest_asset(tmp_path):
    _make_fab_asset(tmp_path, "Tank_01", "fab_tank01")
    result = get_fab_library_scanner().scan_library(str(tmp_path))
    assert result.ok is True
    assert len(result.assets_found) >= 1
    names = [a.name for a in result.assets_found]
    assert "Tank_01" in names


def test_scan_detects_fbx_format(tmp_path):
    _make_fab_asset(tmp_path, "Crate", "fab_crate01")
    result = get_fab_library_scanner().scan_library(str(tmp_path))
    assert any("fbx" in a.formats for a in result.assets_found)


def test_scan_maps_category(tmp_path):
    _make_fab_asset(tmp_path, "Truck", "fab_truck01", category="vehicles")
    result = get_fab_library_scanner().scan_library(str(tmp_path))
    truck = next((a for a in result.assets_found if a.name == "Truck"), None)
    assert truck is not None
    assert truck.category == "vehicle"


def test_scan_extracts_tags(tmp_path):
    _make_fab_asset(tmp_path, "Rock", "fab_rock01")
    result = get_fab_library_scanner().scan_library(str(tmp_path))
    rock = next((a for a in result.assets_found if a.name == "Rock"), None)
    assert rock is not None
    assert "rock" in rock.tags


def test_scan_skips_no_name_json(tmp_path):
    bad_dir = tmp_path / "bad_asset"
    bad_dir.mkdir()
    (bad_dir / "manifest.json").write_text(json.dumps({"id": "x123"}))
    result = get_fab_library_scanner().scan_library(str(tmp_path))
    assert all(a.asset_id != "x123" for a in result.assets_found)


def test_scan_multiple_assets(tmp_path):
    for i in range(3):
        _make_fab_asset(tmp_path, f"Asset_{i}", f"fab_asset{i:03d}")
    result = get_fab_library_scanner().scan_library(str(tmp_path))
    assert len(result.assets_found) == 3


def test_index_assets_returns_dict(tmp_path):
    _make_fab_asset(tmp_path, "Barrel", "fab_barrel01")
    index = get_fab_library_scanner().index_assets(str(tmp_path))
    assert isinstance(index, dict)
    assert "fab_barrel01" in index


def test_extract_metadata_single_file(tmp_path):
    _make_fab_asset(tmp_path, "Drum", "fab_drum01")
    manifest = str(tmp_path / "fab_drum01" / "manifest.json")
    record = get_fab_library_scanner().extract_metadata(manifest)
    assert record is not None
    assert record.name == "Drum"


def test_build_asset_descriptor(tmp_path):
    _make_fab_asset(tmp_path, "Chair", "fab_chair01")
    result = get_fab_library_scanner().scan_library(str(tmp_path))
    assert len(result.assets_found) >= 1
    desc = get_fab_library_scanner().build_asset_descriptor(result.assets_found[0])
    assert isinstance(desc, dict)
    assert desc["provider"] == "fab"
    assert desc["asset_id"] != ""


def test_fab_asset_record_to_dict():
    rec = FabAssetRecord(name="Test", category="prop", tags=["a"], formats=["fbx"])
    d = rec.to_dict()
    for key in ("record_id", "asset_id", "name", "category", "tags", "formats",
                "local_path", "manifest_path", "provider", "license", "discovered_at"):
        assert key in d


def test_fab_asset_record_from_dict_round_trip():
    rec = FabAssetRecord(name="Pipe", category="prop", formats=["usd"], tags=["pipe"])
    restored = FabAssetRecord.from_dict(rec.to_dict())
    assert restored.name == "Pipe"
    assert restored.formats == ["usd"]
    assert restored.tags == ["pipe"]


def test_scan_result_to_dict():
    result = FabScanResult(ok=True, library_path="/lib", total_scanned=5)
    d = result.to_dict()
    for key in ("ok", "library_path", "assets_found", "total_scanned", "errors", "warnings", "scanned_at"):
        assert key in d


def test_never_raises_none_scan():
    result = get_fab_library_scanner().scan_library(None)  # type: ignore
    assert isinstance(result, FabScanResult)


def test_statistics_structure():
    stats = get_fab_library_scanner().get_statistics()
    assert "scan_count" in stats
    assert "last_scan_ok" in stats
    assert "assets_in_last_scan" in stats
