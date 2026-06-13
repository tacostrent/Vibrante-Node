"""Tests for src/runtime/assets/cache/asset_storage.py"""
import os
import pytest

from src.runtime.assets.cache.asset_storage import (
    AssetStorage,
    StorageRecord,
    get_asset_storage,
    reset_asset_storage_for_tests,
)
from src.runtime.assets.schema import AssetDescriptor


def _make_asset(provider="sketchfab", asset_id="test_001", name="Test Asset", category="prop") -> AssetDescriptor:
    return AssetDescriptor(
        asset_id=asset_id,
        provider=provider,
        name=name,
        category=category,
        formats=["fbx"],
    )


@pytest.fixture(autouse=True)
def reset():
    reset_asset_storage_for_tests()
    yield
    reset_asset_storage_for_tests()


class TestSingleton:
    def test_singleton_identity(self):
        s1 = get_asset_storage()
        s2 = get_asset_storage()
        assert s1 is s2

    def test_reset_creates_new(self):
        s1 = get_asset_storage()
        reset_asset_storage_for_tests()
        s2 = get_asset_storage()
        assert s1 is not s2


class TestRegisterAndFind:
    def test_register_returns_storage_id(self):
        storage = get_asset_storage()
        sid = storage.register_asset(_make_asset(), "/path/to/asset.fbx")
        assert isinstance(sid, str)
        assert sid.startswith("stor_")

    def test_find_after_register(self):
        storage = get_asset_storage()
        asset = _make_asset()
        storage.register_asset(asset, "/path/to/asset.fbx")
        record = storage.find_asset(asset.provider, asset.asset_id)
        assert record is not None
        assert record.asset_id == asset.asset_id

    def test_asset_exists(self):
        storage = get_asset_storage()
        asset = _make_asset()
        storage.register_asset(asset, "/path/to/asset.fbx")
        assert storage.asset_exists(asset.provider, asset.asset_id) is True

    def test_asset_not_exists(self):
        storage = get_asset_storage()
        assert storage.asset_exists("sketchfab", "nonexistent") is False

    def test_register_overwrites_same_key(self):
        storage = get_asset_storage()
        asset = _make_asset()
        sid1 = storage.register_asset(asset, "/path1.fbx")
        sid2 = storage.register_asset(asset, "/path2.fbx")
        # Second registration creates new record with new storage_id
        record = storage.find_asset(asset.provider, asset.asset_id)
        assert record is not None


class TestRemove:
    def test_remove_by_storage_id(self):
        storage = get_asset_storage()
        asset = _make_asset()
        sid = storage.register_asset(asset, "/path.fbx")
        result = storage.remove_asset(sid)
        assert result is True
        assert storage.asset_exists(asset.provider, asset.asset_id) is False

    def test_remove_nonexistent(self):
        storage = get_asset_storage()
        assert storage.remove_asset("nonexistent_sid") is False


class TestGetAsset:
    def test_get_by_storage_id(self):
        storage = get_asset_storage()
        asset = _make_asset()
        sid = storage.register_asset(asset, "/path.fbx")
        record = storage.get_asset(sid)
        assert record is not None
        assert record.storage_id == sid

    def test_get_nonexistent(self):
        storage = get_asset_storage()
        assert storage.get_asset("nonexistent_sid") is None


class TestListAssets:
    def test_list_all(self):
        storage = get_asset_storage()
        storage.register_asset(_make_asset(provider="sf", asset_id="a1"), "")
        storage.register_asset(_make_asset(provider="ph", asset_id="a2", category="material"), "")
        records = storage.list_assets()
        assert len(records) >= 2

    def test_list_filtered_by_provider(self):
        storage = get_asset_storage()
        storage.register_asset(_make_asset(provider="sketchfab", asset_id="a1"), "")
        storage.register_asset(_make_asset(provider="polyhaven", asset_id="a2"), "")
        records = storage.list_assets(provider="sketchfab")
        assert all(r.provider == "sketchfab" for r in records)

    def test_list_filtered_by_category(self):
        storage = get_asset_storage()
        storage.register_asset(_make_asset(asset_id="a1", category="prop"), "")
        storage.register_asset(_make_asset(asset_id="a2", category="material"), "")
        records = storage.list_assets(category="prop")
        assert all(r.category == "prop" for r in records)

    def test_list_sorted(self):
        storage = get_asset_storage()
        storage.register_asset(_make_asset(provider="z_provider", asset_id="z"), "")
        storage.register_asset(_make_asset(provider="a_provider", asset_id="a"), "")
        records = storage.list_assets()
        keys = [(r.provider, r.asset_id) for r in records]
        assert keys == sorted(keys)


class TestStorageRoot:
    def test_default_root(self):
        storage = AssetStorage()
        root = storage.get_storage_root()
        assert isinstance(root, str)
        assert len(root) > 0

    def test_custom_root(self, tmp_path):
        storage = AssetStorage(root=str(tmp_path))
        assert storage.get_storage_root() == str(tmp_path)

    def test_env_var_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VIBRANTE_ASSET_STORAGE", str(tmp_path))
        storage = AssetStorage()
        assert storage.get_storage_root() == str(tmp_path)


class TestStatistics:
    def test_statistics_structure(self):
        storage = get_asset_storage()
        s = storage.get_storage_statistics()
        assert "total_assets" in s
        assert "total_size_bytes" in s
        assert "assets_by_provider" in s
        assert "storage_root" in s

    def test_statistics_count(self):
        storage = get_asset_storage()
        storage.register_asset(_make_asset(provider="sf", asset_id="a1"), "")
        storage.register_asset(_make_asset(provider="sf", asset_id="a2"), "")
        s = storage.get_storage_statistics()
        assert s["total_assets"] == 2
        assert s["assets_by_provider"].get("sf", 0) == 2

    def test_storage_record_to_dict(self):
        storage = get_asset_storage()
        asset = _make_asset()
        sid = storage.register_asset(asset, "/path.fbx")
        record = storage.get_asset(sid)
        d = record.to_dict()
        assert "storage_id" in d
        assert "asset_id" in d
        assert "provider" in d
        assert "local_path" in d
