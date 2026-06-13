"""Tests for src/runtime/assets/acquisition_online/asset_fetcher.py"""
import os
import pytest
from src.runtime.assets.acquisition_online import (
    get_asset_fetcher,
    get_asset_cache_manager,
    get_asset_provenance_tracker,
    get_megascans_auth,
    get_megascans_downloader,
    reset_asset_fetcher_for_tests,
    reset_asset_cache_manager_for_tests,
    reset_asset_provenance_tracker_for_tests,
    reset_megascans_auth_for_tests,
    reset_megascans_downloader_for_tests,
    reset_download_statistics_for_tests,
    reset_download_serializer_for_tests,
    FetchResult,
)


class _MockAuthTransport:
    def get_user_info(self, token):
        return {"user_id": "u1", "username": "test"}


class _MockDownloadTransport:
    def __init__(self, ok=True, bytes_written=512):
        self.ok = ok
        self.bytes_written = bytes_written

    def resolve_url(self, asset_id, token, quality):
        return f"https://mock/{asset_id}.zip"

    def download(self, url, token, dest_path):
        if self.ok:
            with open(dest_path, "wb") as f:
                f.write(b"x" * self.bytes_written)
            return {"ok": True, "bytes": self.bytes_written, "error": ""}
        return {"ok": False, "bytes": 0, "error": "mock error"}


@pytest.fixture(autouse=True)
def reset_all(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBRANTE_ASSET_CACHE", str(tmp_path))
    monkeypatch.setenv("VIBRANTE_MEGASCANS_TOKEN", "tok")
    reset_download_serializer_for_tests()
    reset_download_statistics_for_tests()
    reset_asset_cache_manager_for_tests()
    reset_asset_provenance_tracker_for_tests()
    reset_megascans_auth_for_tests()
    reset_megascans_downloader_for_tests()
    reset_asset_fetcher_for_tests()
    auth = get_megascans_auth()
    auth._transport = _MockAuthTransport()
    yield
    reset_asset_fetcher_for_tests()
    reset_megascans_downloader_for_tests()
    reset_megascans_auth_for_tests()
    reset_asset_provenance_tracker_for_tests()
    reset_asset_cache_manager_for_tests()
    reset_download_statistics_for_tests()
    reset_download_serializer_for_tests()
    monkeypatch.delenv("VIBRANTE_ASSET_CACHE", raising=False)
    monkeypatch.delenv("VIBRANTE_MEGASCANS_TOKEN", raising=False)


def test_singleton():
    a = get_asset_fetcher()
    b = get_asset_fetcher()
    assert a is b


def test_fetch_returns_cache_when_available(tmp_path):
    cache = get_asset_cache_manager()
    f = tmp_path / "cached.zip"
    f.write_bytes(b"cached")
    cache.cache_asset("cached_id", "megascans", str(f))

    fetcher = get_asset_fetcher()
    result = fetcher.ensure_asset_available("cached_id", provider="megascans")
    assert result.ok is True
    assert result.source == "cache"
    assert result.local_path == str(f)


def test_fetch_downloads_when_not_cached(tmp_path):
    dl = get_megascans_downloader()
    dl._transport = _MockDownloadTransport(ok=True)

    fetcher = get_asset_fetcher()
    result = fetcher.fetch_asset("new_asset", provider="megascans",
                                  dest_dir=str(tmp_path), quality="medium")
    assert result.ok is True
    assert result.bytes_fetched > 0
    assert os.path.isfile(result.local_path)


def test_fetch_records_to_cache(tmp_path):
    dl = get_megascans_downloader()
    dl._transport = _MockDownloadTransport(ok=True)

    fetcher = get_asset_fetcher()
    fetcher.fetch_asset("new_asset2", provider="megascans", dest_dir=str(tmp_path))
    entry = get_asset_cache_manager().get_cache_entry("new_asset2", "megascans")
    assert entry is not None


def test_fetch_records_provenance(tmp_path):
    dl = get_megascans_downloader()
    dl._transport = _MockDownloadTransport(ok=True)

    fetcher = get_asset_fetcher()
    fetcher.fetch_asset("prov_asset", provider="megascans", dest_dir=str(tmp_path))
    rec = get_asset_provenance_tracker().lookup("prov_asset", "megascans")
    assert rec is not None
    assert rec.source == "download"


def test_fetch_no_asset_id():
    fetcher = get_asset_fetcher()
    result = fetcher.fetch_asset("")
    assert result.ok is False
    assert result.error != ""


def test_fetch_download_fails(tmp_path):
    dl = get_megascans_downloader()
    dl._transport = _MockDownloadTransport(ok=False)

    fetcher = get_asset_fetcher()
    result = fetcher.fetch_asset("fail_asset", provider="megascans", dest_dir=str(tmp_path))
    assert result.ok is False


def test_fetch_assets_list(tmp_path):
    dl = get_megascans_downloader()
    dl._transport = _MockDownloadTransport(ok=True)

    fetcher = get_asset_fetcher()
    asset_list = [
        {"asset_id": "bulk1", "provider": "megascans"},
        {"asset_id": "bulk2", "provider": "megascans"},
    ]
    results = fetcher.fetch_assets(asset_list, dest_dir=str(tmp_path))
    assert len(results) == 2
    assert all(r.ok for r in results)


def test_fetch_result_to_dict():
    r = FetchResult(ok=True, asset_id="x", provider="megascans", local_path="/p",
                    source="cache", bytes_fetched=100)
    d = r.to_dict()
    assert d["ok"] is True
    assert d["source"] == "cache"


def test_fetch_result_from_dict():
    d = {"ok": False, "asset_id": "y", "error": "net", "source": "offline"}
    r = FetchResult.from_dict(d)
    assert r.ok is False
    assert r.source == "offline"
