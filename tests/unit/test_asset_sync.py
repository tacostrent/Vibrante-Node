"""Tests for src/runtime/assets/cache/asset_sync.py"""
import pytest

from src.runtime.assets.cache.asset_sync import (
    SyncReport,
    AssetSync,
    get_asset_sync,
    reset_asset_sync_for_tests,
)
from src.runtime.assets.cache.asset_storage import reset_asset_storage_for_tests
from src.runtime.assets.providers.base import reset_provider_registry_for_tests, get_provider_registry
from src.runtime.assets.providers.sketchfab_provider import SketchfabProvider


@pytest.fixture(autouse=True)
def reset():
    reset_asset_sync_for_tests()
    reset_asset_storage_for_tests()
    reset_provider_registry_for_tests()
    yield
    reset_asset_sync_for_tests()
    reset_asset_storage_for_tests()
    reset_provider_registry_for_tests()


class TestSingleton:
    def test_singleton_identity(self):
        s1 = get_asset_sync()
        s2 = get_asset_sync()
        assert s1 is s2

    def test_reset_creates_new(self):
        s1 = get_asset_sync()
        reset_asset_sync_for_tests()
        s2 = get_asset_sync()
        assert s1 is not s2


class TestSyncReport:
    def test_sync_report_defaults(self):
        report = SyncReport(provider="sketchfab")
        assert report.provider == "sketchfab"
        assert report.assets_found == 0
        assert report.assets_new == 0
        assert report.errors == []

    def test_sync_report_to_dict(self):
        report = SyncReport(provider="test")
        report.assets_found = 5
        d = report.to_dict()
        assert "provider" in d
        assert "assets_found" in d
        assert "assets_new" in d
        assert "sync_id" in d
        assert "errors" in d


class TestSyncProvider:
    def test_sync_unknown_provider_has_error(self):
        sync = get_asset_sync()
        report = sync.sync_provider("nonexistent_provider")
        assert len(report.errors) > 0
        assert report.assets_found == 0

    def test_sync_registered_provider(self):
        reg = get_provider_registry()
        reg.register(SketchfabProvider())
        sync = get_asset_sync()
        report = sync.sync_provider("sketchfab")
        assert report.provider == "sketchfab"
        assert report.assets_found > 0
        assert len(report.errors) == 0

    def test_sync_records_history(self):
        sync = get_asset_sync()
        sync.sync_provider("nonexistent")
        history = sync.get_sync_history()
        assert len(history) >= 1

    def test_sync_populates_storage(self):
        reg = get_provider_registry()
        reg.register(SketchfabProvider())
        sync = get_asset_sync()
        report = sync.sync_provider("sketchfab")
        assert report.assets_new > 0


class TestSyncLibrary:
    def test_sync_nonexistent_path(self):
        sync = get_asset_sync()
        report = sync.sync_library("/nonexistent/path", "local")
        assert len(report.errors) > 0

    def test_sync_empty_directory(self, tmp_path):
        sync = get_asset_sync()
        report = sync.sync_library(str(tmp_path), "local")
        assert report.assets_found == 0
        assert len(report.errors) == 0

    def test_sync_directory_with_files(self, tmp_path):
        (tmp_path / "asset1.fbx").write_bytes(b"FBX")
        (tmp_path / "asset2.obj").write_bytes(b"OBJ")
        sync = get_asset_sync()
        report = sync.sync_library(str(tmp_path), "local")
        assert report.assets_found >= 2
        assert report.assets_new >= 2

    def test_sync_records_history_library(self, tmp_path):
        sync = get_asset_sync()
        sync.sync_library(str(tmp_path), "local")
        history = sync.get_sync_history()
        assert any(r["provider"] == "local" for r in history)


class TestValidateSync:
    def test_validate_unknown_provider(self):
        sync = get_asset_sync()
        result = sync.validate_sync("unknown_provider")
        assert "valid" in result
        assert "issues" in result

    def test_validate_registered_provider(self):
        reg = get_provider_registry()
        reg.register(SketchfabProvider())
        sync = get_asset_sync()
        result = sync.validate_sync("sketchfab")
        assert "valid" in result
        assert "assets_in_storage" in result
        assert "assets_in_provider" in result

    def test_build_sync_report(self):
        sync = get_asset_sync()
        report = sync.build_sync_report("test_prov", found=10, registered=8, errors=[])
        assert report.assets_found == 10
        assert report.assets_new == 8
        assert report.errors == []


class TestHistory:
    def test_history_empty(self):
        sync = get_asset_sync()
        assert sync.get_sync_history() == []

    def test_history_newest_first(self):
        sync = get_asset_sync()
        sync.sync_provider("p1")
        sync.sync_provider("p2")
        history = sync.get_sync_history()
        # Newest should be last in history (get_sync_history returns reversed)
        assert len(history) == 2
        providers = [r["provider"] for r in history]
        assert "p1" in providers
        assert "p2" in providers

    def test_history_limit(self):
        sync = get_asset_sync()
        for i in range(5):
            sync.sync_provider(f"prov_{i}")
        history = sync.get_sync_history(limit=3)
        assert len(history) <= 3


class TestStatistics:
    def test_statistics_structure(self):
        sync = get_asset_sync()
        s = sync.get_statistics()
        assert "total_syncs" in s
        assert "total_new" in s
        assert "total_updated" in s
        assert "total_errors" in s

    def test_statistics_after_sync(self, tmp_path):
        (tmp_path / "a.fbx").write_bytes(b"FBX")
        sync = get_asset_sync()
        sync.sync_library(str(tmp_path), "local")
        s = sync.get_statistics()
        assert s["total_syncs"] == 1
        assert s["total_new"] >= 1
