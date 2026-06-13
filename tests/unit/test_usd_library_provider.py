"""Tests for src/runtime/assets/providers/usd_library_provider.py"""
import os
import pytest

from src.runtime.assets.providers.usd_library_provider import UsdLibraryProvider
from src.runtime.assets.schema import AssetDescriptor, AssetMetadata


class TestUsdLibraryProviderUnavailable:
    def test_unavailable_without_env_var(self, monkeypatch):
        monkeypatch.delenv("VIBRANTE_USD_LIBRARY_PATH", raising=False)
        p = UsdLibraryProvider()
        assert p.is_available is False

    def test_unavailable_with_nonexistent_path(self):
        p = UsdLibraryProvider(library_path="/nonexistent/usd/path")
        assert p.is_available is False

    def test_search_empty_when_unavailable(self, monkeypatch):
        monkeypatch.delenv("VIBRANTE_USD_LIBRARY_PATH", raising=False)
        p = UsdLibraryProvider()
        result = p.search(category="prop")
        assert result.success is True
        assert result.normalized_assets == []

    def test_provider_name(self):
        assert UsdLibraryProvider().provider_name == "usd_library"

    def test_supported_categories(self):
        cats = UsdLibraryProvider().supported_categories
        assert "prop" in cats
        assert "structure" in cats


class TestUsdLibraryProviderWithFiles:
    def test_available_with_valid_path(self, tmp_path):
        p = UsdLibraryProvider(library_path=str(tmp_path))
        assert p.is_available is True

    def test_scan_empty_directory(self, tmp_path):
        p = UsdLibraryProvider(library_path=str(tmp_path))
        assets = p.scan_directory(str(tmp_path))
        assert assets == []

    def test_scan_finds_usd_files(self, tmp_path):
        (tmp_path / "robot.usd").write_text("#usda 1.0\ndef Xform \"robot\" {}", encoding="utf-8")
        (tmp_path / "table.usdc").write_bytes(b"PXR-USDCfake")
        p = UsdLibraryProvider(library_path=str(tmp_path))
        assets = p.scan_directory(str(tmp_path))
        assert len(assets) >= 2
        names = [a.name for a in assets]
        assert "robot" in names
        assert "table" in names

    def test_scan_finds_usdz(self, tmp_path):
        (tmp_path / "scene.usdz").write_bytes(b"PK\x03\x04")  # Fake zip
        p = UsdLibraryProvider(library_path=str(tmp_path))
        assets = p.scan_directory(str(tmp_path))
        assert any(a.name == "scene" for a in assets)

    def test_scan_ignores_non_usd(self, tmp_path):
        (tmp_path / "texture.png").write_bytes(b"\x89PNG")
        (tmp_path / "readme.txt").write_text("test", encoding="utf-8")
        p = UsdLibraryProvider(library_path=str(tmp_path))
        assets = p.scan_directory(str(tmp_path))
        assert assets == []

    def test_normalize_result(self):
        p = UsdLibraryProvider()
        raw = {
            "asset_id": "my_asset",
            "name": "My Asset",
            "category": "prop",
            "formats": ["usd"],
            "local_path": "/path/to/my_asset.usd",
        }
        asset = p.normalize_result(raw)
        assert isinstance(asset, AssetDescriptor)
        assert asset.provider == "usd_library"
        assert asset.asset_id.startswith("usdlib_")

    def test_extract_metadata_nonexistent(self):
        p = UsdLibraryProvider()
        meta = p.extract_metadata("/nonexistent.usd")
        assert isinstance(meta, AssetMetadata)
        assert meta.file_size_mb == 0.0

    def test_validate_usd_nonexistent(self):
        p = UsdLibraryProvider()
        result = p.validate_usd("/nonexistent.usd")
        assert result["valid"] is False
        assert result["size_bytes"] == 0

    def test_validate_usd_real_file(self, tmp_path):
        usd_file = tmp_path / "test.usda"
        usd_file.write_text("#usda 1.0\ndef Xform \"root\" {}", encoding="utf-8")
        p = UsdLibraryProvider()
        result = p.validate_usd(str(usd_file))
        assert result["valid"] is True
        assert result["format"] == "text"
        assert result["size_bytes"] > 0

    def test_collect_dependencies_empty(self, tmp_path):
        usd_file = tmp_path / "simple.usda"
        usd_file.write_text("#usda 1.0\ndef Xform \"root\" {}", encoding="utf-8")
        p = UsdLibraryProvider()
        deps = p.collect_dependencies(str(usd_file))
        assert isinstance(deps, list)

    def test_collect_dependencies_finds_refs(self, tmp_path):
        usd_file = tmp_path / "ref.usda"
        usd_file.write_text(
            '#usda 1.0\nref = @./other.usd@\nreferences = [@./geo.usd@]',
            encoding="utf-8",
        )
        p = UsdLibraryProvider()
        deps = p.collect_dependencies(str(usd_file))
        assert len(deps) >= 1

    def test_search_with_valid_path(self, tmp_path):
        (tmp_path / "sphere.usd").write_text("#usda 1.0", encoding="utf-8")
        p = UsdLibraryProvider(library_path=str(tmp_path))
        result = p.search(category="")
        assert result.success is True
        assert len(result.normalized_assets) >= 1
