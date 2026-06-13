"""Tests for src/runtime/assets/providers/quixel_provider.py"""
import json
import os
import tempfile

import pytest

from src.runtime.assets.providers.quixel_provider import QuixelProvider
from src.runtime.assets.schema import AssetDescriptor, AssetMetadata


class TestQuixelProviderUnavailable:
    def test_unavailable_without_env_var(self, monkeypatch):
        monkeypatch.delenv("VIBRANTE_MEGASCANS_PATH", raising=False)
        p = QuixelProvider()
        assert p.is_available is False

    def test_unavailable_with_nonexistent_path(self):
        p = QuixelProvider(library_path="/nonexistent/megascans/path")
        assert p.is_available is False

    def test_search_returns_empty_when_unavailable(self, monkeypatch):
        monkeypatch.delenv("VIBRANTE_MEGASCANS_PATH", raising=False)
        p = QuixelProvider()
        result = p.search(category="material")
        assert result.success is True
        assert result.normalized_assets == []

    def test_scan_library_returns_empty_when_unavailable(self, monkeypatch):
        monkeypatch.delenv("VIBRANTE_MEGASCANS_PATH", raising=False)
        p = QuixelProvider()
        assert p.scan_library() == []

    def test_provider_name(self):
        assert QuixelProvider().provider_name == "quixel"

    def test_supported_categories(self):
        cats = QuixelProvider().supported_categories
        assert "material" in cats
        assert "prop" in cats


class TestQuixelProviderWithTempDir:
    def test_available_with_valid_path(self, tmp_path):
        p = QuixelProvider(library_path=str(tmp_path))
        assert p.is_available is True

    def test_scan_empty_directory(self, tmp_path):
        p = QuixelProvider(library_path=str(tmp_path))
        assets = p.scan_library()
        assert assets == []

    def test_scan_finds_metadata_json(self, tmp_path):
        asset_dir = tmp_path / "rock_01"
        asset_dir.mkdir()
        meta = {
            "id": "rock_01",
            "name": "Rock Formation",
            "category": "surfaces",
            "tags": ["rock", "stone", "natural"],
        }
        (asset_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
        p = QuixelProvider(library_path=str(tmp_path))
        assets = p.scan_library()
        assert len(assets) >= 1
        names = [a.name for a in assets]
        assert any("Rock" in n for n in names)

    def test_scan_normalizes_category(self, tmp_path):
        asset_dir = tmp_path / "surface_01"
        asset_dir.mkdir()
        meta = {"id": "surf_01", "name": "Concrete Surface", "category": "surfaces"}
        (asset_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
        p = QuixelProvider(library_path=str(tmp_path))
        assets = p.scan_library()
        for a in assets:
            assert a.category in ("material", "prop", "terrain")  # mapped category

    def test_normalize_result_basic(self):
        p = QuixelProvider()
        raw = {
            "id": "test_01",
            "name": "Test Asset",
            "category": "props",
            "tags": ["test", "prop"],
        }
        asset = p.normalize_result(raw)
        assert isinstance(asset, AssetDescriptor)
        assert asset.provider == "quixel"
        assert asset.asset_id.startswith("qx_")
        assert asset.name == "Test Asset"

    def test_normalize_category_mapping(self):
        p = QuixelProvider()
        raw = {"id": "x", "name": "X", "category": "surfaces"}
        asset = p.normalize(raw)
        assert asset.category == "material"

    def test_build_metadata(self):
        p = QuixelProvider()
        meta = p.build_metadata("/nonexistent", {"author": "Test"})
        assert isinstance(meta, AssetMetadata)
        assert meta.author == "Test"

    def test_search_with_valid_path(self, tmp_path):
        asset_dir = tmp_path / "barrel"
        asset_dir.mkdir()
        meta = {"id": "barrel_01", "name": "Barrel", "category": "props",
                "tags": ["barrel", "industrial"]}
        (asset_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
        p = QuixelProvider(library_path=str(tmp_path))
        result = p.search(category="prop")
        assert result.success is True
        assert len(result.normalized_assets) >= 1

    def test_validate_asset(self, tmp_path):
        p = QuixelProvider(library_path=str(tmp_path))
        raw = {"id": "x", "name": "X", "category": "props", "tags": []}
        asset = p.normalize_result(raw)
        v = p.validate_asset(asset)
        assert "valid" in v
        assert "errors" in v
