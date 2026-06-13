"""
Tests for DownloadRegistry (Tier 12.5).
Uses in-memory mode (no VIBRANTE_ASSET_STORAGE set) for portability.
"""
import os
import pytest

from src.runtime.assets.acquisition import (
    RegistryEntry,
    get_download_registry,
    reset_download_registry_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singleton(monkeypatch):
    # Ensure no accidental file I/O during tests
    monkeypatch.delenv("VIBRANTE_ASSET_STORAGE", raising=False)
    reset_download_registry_for_tests()
    yield
    reset_download_registry_for_tests()


def test_singleton_identity():
    assert get_download_registry() is get_download_registry()


def test_register_returns_entry():
    reg = get_download_registry()
    entry = reg.register("asset_001", "fab", "/local/path/asset_001.fbx",
                         name="Industrial Tank", category="prop", formats=["fbx"])
    assert isinstance(entry, RegistryEntry)
    assert entry.asset_id == "asset_001"
    assert entry.provider == "fab"
    assert entry.local_path == "/local/path/asset_001.fbx"


def test_find_by_provider_and_id():
    reg = get_download_registry()
    reg.register("ms_rock01", "megascans", "/ms/rock01", name="Rock")
    found = reg.find("megascans", "ms_rock01")
    assert found is not None
    assert found.name == "Rock"


def test_find_nonexistent_returns_none():
    found = get_download_registry().find("fab", "nonexistent_xyz")
    assert found is None


def test_exists_true_and_false():
    reg = get_download_registry()
    reg.register("a1", "fab", "/path/a1.fbx")
    assert reg.exists("fab", "a1") is True
    assert reg.exists("fab", "nonexistent") is False


def test_remove_entry():
    reg = get_download_registry()
    entry = reg.register("rem01", "fab", "/path/rem01.fbx")
    assert reg.remove(entry.entry_id) is True
    assert reg.find("fab", "rem01") is None


def test_remove_nonexistent_returns_false():
    assert get_download_registry().remove("no_such_entry_id") is False


def test_update_existing_entry():
    reg = get_download_registry()
    reg.register("upd01", "fab", "/old/path.fbx", name="Old Name")
    reg.register("upd01", "fab", "/new/path.fbx", name="New Name")
    entry = reg.find("fab", "upd01")
    assert entry is not None
    assert entry.local_path == "/new/path.fbx"
    assert entry.name == "New Name"


def test_list_entries_all():
    reg = get_download_registry()
    reg.register("la1", "fab", "/a1.fbx")
    reg.register("la2", "megascans", "/a2.fbx")
    entries = reg.list_entries()
    assert len(entries) == 2


def test_list_entries_filter_provider():
    reg = get_download_registry()
    reg.register("lp1", "fab", "/p1.fbx")
    reg.register("lp2", "megascans", "/p2.fbx")
    fab_only = reg.list_entries(provider="fab")
    assert all(e.provider == "fab" for e in fab_only)
    assert len(fab_only) == 1


def test_list_entries_filter_category():
    reg = get_download_registry()
    reg.register("lc1", "fab", "/c1.fbx", category="prop")
    reg.register("lc2", "fab", "/c2.fbx", category="material")
    props = reg.list_entries(category="prop")
    assert all(e.category == "prop" for e in props)


def test_mark_missing():
    reg = get_download_registry()
    entry = reg.register("mm1", "fab", "/nonexistent.fbx")
    reg.mark_missing(entry.entry_id)
    found = reg.find("fab", "mm1")
    assert found.status == "missing"


def test_get_statistics_structure():
    reg = get_download_registry()
    reg.register("s1", "fab", "/s1.fbx")
    stats = reg.get_statistics()
    assert "total_entries" in stats
    assert "by_provider" in stats
    assert "by_status" in stats
    assert stats["total_entries"] == 1


def test_entry_to_dict_keys():
    entry = RegistryEntry(asset_id="x", provider="fab", local_path="/x.fbx", formats=["fbx"])
    d = entry.to_dict()
    for key in ("entry_id", "asset_id", "provider", "name", "category", "local_path",
                "formats", "tags", "semantic_tags", "provenance", "status",
                "registered_at", "last_verified"):
        assert key in d


def test_entry_from_dict_round_trip():
    entry = RegistryEntry(asset_id="rt", provider="megascans", local_path="/rt.fbx",
                          tags=["rock"], formats=["fbx", "usd"])
    restored = RegistryEntry.from_dict(entry.to_dict())
    assert restored.asset_id == "rt"
    assert restored.provider == "megascans"
    assert "rock" in restored.tags


def test_register_no_crash_on_empty_fields():
    reg = get_download_registry()
    entry = reg.register("", "fab", "")
    assert isinstance(entry, RegistryEntry)
