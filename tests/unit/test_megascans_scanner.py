"""
Tests for MegascansScanner (Tier 12.5).
All tests use tmp_path — no network, no authentication.
"""
import json
import os
import pytest

from src.runtime.assets.acquisition import (
    MegascansAssetRecord,
    MegascansScanResult,
    get_megascans_scanner,
    reset_megascans_scanner_for_tests,
    ENV_MEGASCANS_LIBRARY,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_megascans_scanner_for_tests()
    yield
    reset_megascans_scanner_for_tests()


def _make_ms_asset(tmp_path, ms_type="3d", asset_id="vgekaxbi", name="Rock Formation"):
    type_dir = tmp_path / ms_type
    type_dir.mkdir(exist_ok=True)
    asset_dir = type_dir / asset_id
    asset_dir.mkdir()
    manifest = {
        "id": asset_id,
        "name": name,
        "type": ms_type,
        "tags": ["rock", "stone", "nature"],
        "maps": [
            {"type": "albedo", "format": "jpg"},
            {"type": "roughness", "format": "jpg"},
            {"type": "normal", "format": "jpg"},
        ],
        "geometry": [{"format": "fbx", "lod": 0}, {"format": "usd", "lod": 0}],
    }
    (asset_dir / f"{asset_id}.json").write_text(json.dumps(manifest))
    (asset_dir / f"{asset_id}_4K_Albedo.jpg").write_bytes(b"")
    (asset_dir / f"{asset_id}_4K_Roughness.jpg").write_bytes(b"")
    (asset_dir / f"{asset_id}.fbx").write_bytes(b"")
    return str(asset_dir)


def test_singleton_identity():
    assert get_megascans_scanner() is get_megascans_scanner()


def test_scan_empty_path_returns_warning():
    result = get_megascans_scanner().scan_megascans("")
    assert result.ok is True
    assert len(result.warnings) > 0


def test_scan_nonexistent_path_returns_error():
    result = get_megascans_scanner().scan_megascans("/no/such/ms/path/xyz")
    assert result.ok is False
    assert len(result.errors) > 0


def test_scan_finds_3d_asset(tmp_path):
    _make_ms_asset(tmp_path, ms_type="3d", asset_id="rock01", name="Rocky Boulder")
    result = get_megascans_scanner().scan_megascans(str(tmp_path))
    assert result.ok is True
    assert len(result.assets_found) >= 1
    assert any(a.name == "Rocky Boulder" for a in result.assets_found)


def test_scan_maps_3d_to_prop_category(tmp_path):
    _make_ms_asset(tmp_path, ms_type="3d", asset_id="prop01")
    result = get_megascans_scanner().scan_megascans(str(tmp_path))
    asset = next(a for a in result.assets_found if a.ms_type == "3d")
    assert asset.category == "prop"


def test_scan_maps_surface_to_material(tmp_path):
    _make_ms_asset(tmp_path, ms_type="surface", asset_id="surf01", name="Concrete Worn")
    result = get_megascans_scanner().scan_megascans(str(tmp_path))
    asset = next((a for a in result.assets_found if a.ms_type == "surface"), None)
    assert asset is not None
    assert asset.category == "material"


def test_scan_maps_3dplant_to_vegetation(tmp_path):
    _make_ms_asset(tmp_path, ms_type="3dplant", asset_id="plant01", name="Oak Tree")
    result = get_megascans_scanner().scan_megascans(str(tmp_path))
    asset = next((a for a in result.assets_found if a.ms_type == "3dplant"), None)
    assert asset is not None
    assert asset.category == "vegetation"


def test_scan_detects_albedo_map(tmp_path):
    _make_ms_asset(tmp_path, ms_type="surface", asset_id="surf02")
    result = get_megascans_scanner().scan_megascans(str(tmp_path))
    asset = next((a for a in result.assets_found), None)
    assert asset is not None
    assert "albedo" in asset.map_types


def test_scan_detects_fbx_format(tmp_path):
    _make_ms_asset(tmp_path, ms_type="3d", asset_id="mesh01")
    result = get_megascans_scanner().scan_megascans(str(tmp_path))
    asset = next((a for a in result.assets_found), None)
    assert asset is not None
    assert "fbx" in asset.formats


def test_scan_by_type_count(tmp_path):
    _make_ms_asset(tmp_path, "3d",      "m1")
    _make_ms_asset(tmp_path, "surface", "m2")
    _make_ms_asset(tmp_path, "decal",   "m3")
    result = get_megascans_scanner().scan_megascans(str(tmp_path))
    assert len(result.assets_found) == 3
    assert "3d" in result.by_type
    assert "surface" in result.by_type


def test_build_metadata(tmp_path):
    _make_ms_asset(tmp_path, "3d", "meta01", "Pillar")
    result = get_megascans_scanner().scan_megascans(str(tmp_path))
    rec = result.assets_found[0]
    meta = get_megascans_scanner().build_metadata(rec)
    assert meta["provider"] == "megascans"
    assert meta["name"] == "Pillar"
    assert "map_types" in meta


def test_infer_semantics(tmp_path):
    _make_ms_asset(tmp_path, "surface", "surf_sem")
    result = get_megascans_scanner().scan_megascans(str(tmp_path))
    rec = result.assets_found[0]
    sem = get_megascans_scanner().infer_semantics(rec)
    assert "environment_suitability" in sem
    assert "style" in sem
    assert "scale" in sem


def test_build_asset_descriptor(tmp_path):
    _make_ms_asset(tmp_path, "3d", "desc01")
    result = get_megascans_scanner().scan_megascans(str(tmp_path))
    rec = result.assets_found[0]
    desc = get_megascans_scanner().build_asset_descriptor(rec)
    assert desc["provider"] == "megascans"
    assert "local_path" in desc["metadata"]["extra"]


def test_record_to_dict_keys():
    rec = MegascansAssetRecord(asset_id="r1", name="Test", ms_type="3d", category="prop")
    d = rec.to_dict()
    for key in ("record_id", "asset_id", "name", "ms_type", "category", "tags",
                "formats", "map_types", "resolution", "local_path", "lod_count"):
        assert key in d


def test_record_from_dict_round_trip():
    rec = MegascansAssetRecord(asset_id="rt", name="Surf", ms_type="surface", category="material",
                               map_types=["albedo", "roughness"])
    restored = MegascansAssetRecord.from_dict(rec.to_dict())
    assert restored.name == "Surf"
    assert restored.ms_type == "surface"
    assert "albedo" in restored.map_types


def test_never_raises_none():
    result = get_megascans_scanner().scan_megascans(None)  # type: ignore
    assert isinstance(result, MegascansScanResult)
