"""Tests for src/runtime/assets/acquisition_online/megascans_search.py"""
import pytest
from src.runtime.assets.acquisition_online import (
    get_megascans_auth,
    get_megascans_search,
    reset_megascans_auth_for_tests,
    reset_megascans_search_for_tests,
    MegascansSearchRecord,
)


class _MockTransport:
    def __init__(self, assets=None):
        self.calls = []
        self._assets = assets or [
            {"id": "a001", "name": "Rusted Metal", "type": "surface",
             "tags": "rust,metal,aged", "isFree": True},
            {"id": "a002", "name": "Oil Tank", "type": "3d",
             "tags": ["industrial", "tank"], "isFree": False},
        ]

    def get(self, url, token, params):
        self.calls.append({"url": url, "params": params})
        return {"assets": self._assets}


class _MockAuthTransport:
    def get_user_info(self, token):
        return {"user_id": "u1", "username": "tester"}


@pytest.fixture(autouse=True)
def reset_all(monkeypatch):
    monkeypatch.setenv("VIBRANTE_MEGASCANS_TOKEN", "test_token")
    reset_megascans_auth_for_tests()
    reset_megascans_search_for_tests()
    # Inject auth transport so token is seen as valid
    auth = get_megascans_auth()
    auth._transport = _MockAuthTransport()
    yield
    reset_megascans_search_for_tests()
    reset_megascans_auth_for_tests()
    monkeypatch.delenv("VIBRANTE_MEGASCANS_TOKEN", raising=False)


def test_singleton():
    a = get_megascans_search()
    b = get_megascans_search()
    assert a is b


def test_search_assets_with_results():
    search = get_megascans_search()
    transport = _MockTransport()
    search._transport = transport
    results = search.search_assets("metal")
    assert len(results) == 2
    assert results[0].asset_id == "a001"
    assert results[0].name == "Rusted Metal"
    assert len(transport.calls) == 1


def test_search_assets_normalizes_category():
    search = get_megascans_search()
    transport = _MockTransport()
    search._transport = transport
    results = search.search_assets("test")
    # "surface" → "material", "3d" → "prop"
    categories = {r.category for r in results}
    assert "material" in categories
    assert "prop" in categories


def test_search_by_tags():
    search = get_megascans_search()
    transport = _MockTransport()
    search._transport = transport
    results = search.search_by_tags(["rust", "metal"])
    assert len(results) >= 1


def test_search_by_category():
    search = get_megascans_search()
    transport = _MockTransport()
    search._transport = transport
    results = search.search_by_category("3d")
    assert len(results) >= 1


def test_search_returns_empty_when_no_token(monkeypatch):
    monkeypatch.delenv("VIBRANTE_MEGASCANS_TOKEN", raising=False)
    reset_megascans_auth_for_tests()
    reset_megascans_search_for_tests()
    search = get_megascans_search()
    transport = _MockTransport()
    search._transport = transport
    results = search.search_assets("anything")
    assert results == []


def test_search_returns_empty_on_api_failure():
    search = get_megascans_search()
    class _FailTransport:
        def get(self, url, token, params):
            return None
    search._transport = _FailTransport()
    results = search.search_assets("test")
    assert results == []


def test_lookup_asset():
    search = get_megascans_search()
    transport = _MockTransport(assets=[{"id": "x1", "name": "Rock", "type": "3d"}])
    class _LookupTransport:
        def get(self, url, token, params):
            return {"id": "x1", "name": "Rock", "type": "3d"}
    search._transport = _LookupTransport()
    rec = search.lookup_asset("x1")
    assert rec is not None
    assert rec.asset_id == "x1"


def test_search_record_to_dict():
    rec = MegascansSearchRecord(
        asset_id="r1", name="TestAsset", provider="megascans",
        category="prop", tags=["tag1"], is_free=True,
    )
    d = rec.to_dict()
    assert d["asset_id"] == "r1"
    assert d["is_free"] is True
    assert d["tags"] == ["tag1"]


def test_search_record_from_dict():
    d = {"asset_id": "r2", "name": "Other", "provider": "megascans",
         "category": "material", "ms_type": "surface", "tags": [],
         "is_free": False, "environments": ["industrial_hangar"]}
    rec = MegascansSearchRecord.from_dict(d)
    assert rec.category == "material"
    assert rec.environments == ["industrial_hangar"]


def test_tags_normalized_from_string():
    search = get_megascans_search()
    transport = _MockTransport(assets=[{"id": "t1", "name": "X", "type": "surface",
                                         "tags": "TAG1, TAG2, tag3"}])
    search._transport = transport
    results = search.search_assets("test")
    assert "tag1" in results[0].tags
    assert "tag2" in results[0].tags


def test_statistics():
    search = get_megascans_search()
    transport = _MockTransport()
    search._transport = transport
    search.search_assets("metal")
    stats = search.get_statistics()
    assert stats["search_count"] == 1
