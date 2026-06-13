"""Tests for src/runtime/assets/acquisition_online/asset_cache_manager.py"""
import os
import pytest
from src.runtime.assets.acquisition_online import (
    get_asset_cache_manager,
    reset_asset_cache_manager_for_tests,
    CacheEntry,
)


@pytest.fixture(autouse=True)
def reset_all(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBRANTE_ASSET_CACHE", str(tmp_path))
    reset_asset_cache_manager_for_tests()
    yield
    reset_asset_cache_manager_for_tests()
    monkeypatch.delenv("VIBRANTE_ASSET_CACHE", raising=False)


def test_singleton():
    a = get_asset_cache_manager()
    b = get_asset_cache_manager()
    assert a is b


def test_cache_asset():
    mgr = get_asset_cache_manager()
    entry = mgr.cache_asset("asset1", "megascans", "/some/path/asset1.zip",
                            version="1.0", checksum="abc123")
    assert entry.asset_id == "asset1"
    assert entry.provider == "megascans"
    assert entry.local_path == "/some/path/asset1.zip"
    assert entry.checksum == "abc123"


def test_asset_exists_no_file():
    mgr = get_asset_cache_manager()
    mgr.cache_asset("asset2", "megascans", "/nonexistent/path.zip")
    assert mgr.asset_exists("asset2", "megascans") is False


def test_asset_exists_with_real_file(tmp_path):
    mgr = get_asset_cache_manager()
    f = tmp_path / "test_asset.zip"
    f.write_bytes(b"fake data")
    mgr.cache_asset("asset3", "megascans", str(f))
    assert mgr.asset_exists("asset3", "megascans") is True


def test_get_asset_path_missing():
    mgr = get_asset_cache_manager()
    assert mgr.get_asset_path("unknown_id") is None


def test_get_asset_path_exists(tmp_path):
    mgr = get_asset_cache_manager()
    f = tmp_path / "myasset.zip"
    f.write_bytes(b"data")
    mgr.cache_asset("myasset", "fab", str(f))
    p = mgr.get_asset_path("myasset", "fab")
    assert p == str(f)


def test_remove_asset():
    mgr = get_asset_cache_manager()
    mgr.cache_asset("todel", "megascans", "/some/path")
    removed = mgr.remove_asset("todel", "megascans")
    assert removed is True
    assert mgr.get_cache_entry("todel", "megascans") is None


def test_remove_nonexistent():
    mgr = get_asset_cache_manager()
    assert mgr.remove_asset("ghost", "megascans") is False


def test_cache_statistics():
    mgr = get_asset_cache_manager()
    mgr.cache_asset("a1", "megascans", "/p1", size_bytes=1000)
    mgr.cache_asset("a2", "megascans", "/p2", size_bytes=2000)
    stats = mgr.cache_statistics()
    assert stats["total_assets"] == 2
    assert stats["total_bytes"] == 3000


def test_list_cached_assets():
    mgr = get_asset_cache_manager()
    mgr.cache_asset("x1", "megascans", "/p1")
    mgr.cache_asset("x2", "fab", "/p2")
    entries = mgr.list_cached_assets()
    assert len(entries) == 2


def test_cache_entry_from_dict():
    d = {"asset_id": "e1", "provider": "fab", "local_path": "/tmp/e1.zip",
         "version": "2.0", "checksum": "def456", "size_bytes": 500}
    entry = CacheEntry.from_dict(d)
    assert entry.asset_id == "e1"
    assert entry.version == "2.0"


def test_get_asset_dir(tmp_path):
    mgr = get_asset_cache_manager()
    d = mgr.get_asset_dir("myasset", "megascans")
    assert d is not None
    assert os.path.isdir(d)


def test_no_cache_root_returns_none(monkeypatch):
    monkeypatch.delenv("VIBRANTE_ASSET_CACHE", raising=False)
    reset_asset_cache_manager_for_tests()
    mgr = get_asset_cache_manager()
    assert mgr.get_asset_dir("x", "y") is None
