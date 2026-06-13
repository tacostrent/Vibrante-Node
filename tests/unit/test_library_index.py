"""
Tests for LibraryIndex (Tier 12.5).
In-memory mode only — no VIBRANTE_ASSET_STORAGE set.
"""
import pytest

from src.runtime.assets.acquisition import (
    IndexEntry,
    IndexSearchResult,
    get_library_index,
    reset_library_index_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singleton(monkeypatch):
    monkeypatch.delenv("VIBRANTE_ASSET_STORAGE", raising=False)
    reset_library_index_for_tests()
    yield
    reset_library_index_for_tests()


def test_singleton_identity():
    assert get_library_index() is get_library_index()


def test_add_entry_returns_entry():
    idx = get_library_index()
    entry = idx.add_entry(
        asset_id="fab_001", provider="fab", name="Industrial Tank",
        category="prop", tags=["tank", "industrial"], formats=["fbx"]
    )
    assert isinstance(entry, IndexEntry)
    assert entry.asset_id == "fab_001"
    assert entry.provider == "fab"


def test_search_by_name():
    idx = get_library_index()
    idx.add_entry("a1", "fab", "Industrial Tank", category="prop")
    result = idx.search(query="tank")
    assert result.ok is True
    assert len(result.entries) >= 1
    assert any("tank" in e.name.lower() for e in result.entries)


def test_search_by_category():
    idx = get_library_index()
    idx.add_entry("b1", "fab", "Rock Wall", category="material")
    idx.add_entry("b2", "fab", "Forklift",  category="prop")
    result = idx.search(category="material")
    assert all(e.category == "material" for e in result.entries)


def test_search_by_provider():
    idx = get_library_index()
    idx.add_entry("c1", "fab",        "Asset A", category="prop")
    idx.add_entry("c2", "megascans", "Asset B", category="prop")
    result = idx.search(provider="fab")
    assert all(e.provider == "fab" for e in result.entries)


def test_search_no_match():
    idx = get_library_index()
    idx.add_entry("d1", "fab", "Barrel", category="prop")
    result = idx.search(query="zzz_no_match_xyz")
    assert len(result.entries) == 0
    assert result.total_hits == 0


def test_search_empty_returns_all():
    idx = get_library_index()
    idx.add_entry("e1", "fab", "A")
    idx.add_entry("e2", "fab", "B")
    result = idx.search()
    assert len(result.entries) == 2


def test_get_entry_by_provider_id():
    idx = get_library_index()
    idx.add_entry("f1", "megascans", "Surface", category="material")
    entry = idx.get_entry("megascans", "f1")
    assert entry is not None
    assert entry.name == "Surface"


def test_get_entry_nonexistent():
    assert get_library_index().get_entry("fab", "no_such_id") is None


def test_remove_entry():
    idx = get_library_index()
    idx.add_entry("g1", "fab", "Remove Me")
    assert idx.remove("fab", "g1") is True
    assert idx.get_entry("fab", "g1") is None


def test_remove_nonexistent():
    assert get_library_index().remove("fab", "nonexistent") is False


def test_update_existing_entry():
    idx = get_library_index()
    idx.add_entry("h1", "fab", "Old Name", formats=["fbx"])
    idx.add_entry("h1", "fab", "New Name", formats=["usd"])
    entry = idx.get_entry("fab", "h1")
    assert "usd" in entry.formats
    assert "fbx" in entry.formats  # merged


def test_list_providers():
    idx = get_library_index()
    idx.add_entry("p1", "fab", "A")
    idx.add_entry("p2", "megascans", "B")
    providers = idx.list_providers()
    assert "fab" in providers
    assert "megascans" in providers


def test_list_categories():
    idx = get_library_index()
    idx.add_entry("q1", "fab", "A", category="prop")
    idx.add_entry("q2", "fab", "B", category="material")
    cats = idx.list_categories()
    assert "prop" in cats
    assert "material" in cats


def test_add_from_descriptor():
    idx = get_library_index()
    desc = {"asset_id": "fab_desc01", "provider": "fab", "name": "Barrel",
            "category": "prop", "tags": ["barrel"], "formats": ["fbx"]}
    entry = idx.add_from_descriptor(desc, provenance="fab_local_library")
    assert entry is not None
    assert entry.provider == "fab"


def test_search_result_to_dict():
    result = IndexSearchResult(ok=True, query="test", total_hits=3)
    d = result.to_dict()
    for key in ("ok", "query", "entries", "total_hits", "search_time", "errors"):
        assert key in d


def test_index_entry_to_dict_keys():
    entry = IndexEntry(asset_id="x", provider="fab", name="X", category="prop")
    d = entry.to_dict()
    for key in ("index_id", "asset_id", "provider", "name", "category",
                "tags", "formats", "local_path", "provenance", "indexed_at"):
        assert key in d


def test_entry_from_dict_round_trip():
    entry = IndexEntry(asset_id="rt", provider="megascans", name="Soil",
                       category="material", tags=["soil"], formats=["exr"])
    restored = IndexEntry.from_dict(entry.to_dict())
    assert restored.asset_id == "rt"
    assert restored.name == "Soil"
    assert "soil" in restored.tags


def test_get_statistics_structure():
    idx = get_library_index()
    idx.add_entry("s1", "fab", "A")
    stats = idx.get_statistics()
    assert "total_entries" in stats
    assert "by_provider" in stats
    assert "by_category" in stats
    assert stats["total_entries"] == 1


def test_search_respects_limit():
    idx = get_library_index()
    for i in range(10):
        idx.add_entry(f"lim{i:02d}", "fab", f"Asset {i}")
    result = idx.search(limit=3)
    assert len(result.entries) <= 3
    assert result.total_hits == 10
