"""Tests for src/runtime/assets/providers/studio_library_provider.py"""
import json
import os
import pytest

from src.runtime.assets.providers.studio_library_provider import StudioLibraryProvider
from src.runtime.assets.schema import AssetDescriptor


class TestStudioLibraryProviderUnavailable:
    def test_unavailable_without_env_var(self, monkeypatch):
        monkeypatch.delenv("VIBRANTE_STUDIO_LIBRARY_PATH", raising=False)
        p = StudioLibraryProvider()
        assert p.is_available is False

    def test_unavailable_with_nonexistent_path(self):
        p = StudioLibraryProvider(library_path="/nonexistent/studio/path")
        assert p.is_available is False

    def test_search_empty_when_unavailable(self, monkeypatch):
        monkeypatch.delenv("VIBRANTE_STUDIO_LIBRARY_PATH", raising=False)
        p = StudioLibraryProvider()
        result = p.search(category="vehicle")
        assert result.success is True
        assert result.normalized_assets == []

    def test_provider_name(self):
        assert StudioLibraryProvider().provider_name == "studio_library"

    def test_all_categories_supported(self):
        cats = StudioLibraryProvider().supported_categories
        assert "vehicle" in cats
        assert "material" in cats
        assert len(cats) > 10


class TestStudioLibraryProviderWithFiles:
    def test_available_with_valid_path(self, tmp_path):
        p = StudioLibraryProvider(library_path=str(tmp_path))
        assert p.is_available is True

    def test_scan_empty_directory(self, tmp_path):
        p = StudioLibraryProvider(library_path=str(tmp_path))
        assets = p.scan_repository()
        assert assets == []

    def test_scan_category_structure(self, tmp_path):
        # Create category/asset_name/file.fbx structure
        vehicle_dir = tmp_path / "vehicle" / "truck_01"
        vehicle_dir.mkdir(parents=True)
        (vehicle_dir / "truck_01.fbx").write_bytes(b"FBX_DATA")
        p = StudioLibraryProvider(library_path=str(tmp_path))
        assets = p.scan_repository()
        assert len(assets) >= 1
        assert any(a.category == "vehicle" for a in assets)

    def test_scan_multiple_categories(self, tmp_path):
        for cat in ("vehicle", "prop"):
            asset_dir = tmp_path / cat / "test_asset"
            asset_dir.mkdir(parents=True)
            (asset_dir / "test.fbx").write_bytes(b"FBX")
        p = StudioLibraryProvider(library_path=str(tmp_path))
        assets = p.scan_repository()
        cats = {a.category for a in assets}
        assert "vehicle" in cats
        assert "prop" in cats

    def test_reads_studio_manifest(self, tmp_path):
        manifest = {
            "assets": [
                {
                    "name": "Hero Robot",
                    "category": "robot",
                    "relative_path": "robot_hero/robot.fbx",
                    "tags": ["robot", "hero"],
                    "formats": ["fbx"],
                }
            ]
        }
        (tmp_path / "studio_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        p = StudioLibraryProvider(library_path=str(tmp_path))
        assets = p.scan_repository()
        assert len(assets) >= 1
        names = [a.name for a in assets]
        assert "Hero Robot" in names

    def test_normalize_result(self):
        p = StudioLibraryProvider()
        raw = {
            "asset_id": "my_robot",
            "name": "My Robot",
            "category": "robot",
            "formats": ["fbx", "usd"],
            "tags": ["robot", "mech"],
        }
        asset = p.normalize_result(raw)
        assert isinstance(asset, AssetDescriptor)
        assert asset.provider == "studio_library"
        assert asset.asset_id.startswith("stl_")
        assert "robot" in asset.tags

    def test_query_tags(self, tmp_path):
        asset_dir = tmp_path / "prop" / "barrel"
        asset_dir.mkdir(parents=True)
        (asset_dir / "barrel.fbx").write_bytes(b"FBX")
        p = StudioLibraryProvider(library_path=str(tmp_path))
        # Tags from name inference won't be set, but query_tags should still work
        results = p.query_tags(["barrel"])
        assert isinstance(results, list)

    def test_query_categories(self, tmp_path):
        for cat in ("vehicle", "prop", "robot"):
            d = tmp_path / cat / "asset"
            d.mkdir(parents=True)
            (d / "asset.fbx").write_bytes(b"FBX")
        p = StudioLibraryProvider(library_path=str(tmp_path))
        cats = p.query_categories()
        assert isinstance(cats, list)
        assert sorted(cats) == cats  # sorted

    def test_search_returns_assets(self, tmp_path):
        asset_dir = tmp_path / "machinery" / "crane_01"
        asset_dir.mkdir(parents=True)
        (asset_dir / "crane.fbx").write_bytes(b"FBX")
        p = StudioLibraryProvider(library_path=str(tmp_path))
        result = p.search(category="machinery")
        assert result.success is True
