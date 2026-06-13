"""Tests for src/runtime/assets/acquisition_online/megascans_download.py"""
import os
import pytest
from src.runtime.assets.acquisition_online import (
    get_megascans_auth,
    get_megascans_downloader,
    get_asset_provenance_tracker,
    reset_megascans_auth_for_tests,
    reset_megascans_downloader_for_tests,
    reset_asset_provenance_tracker_for_tests,
    reset_download_serializer_for_tests,
    reset_asset_cache_manager_for_tests,
    DownloadResult,
)


class _MockAuthTransport:
    def get_user_info(self, token):
        return {"user_id": "u1", "username": "test"}


class _MockDownloadTransport:
    def __init__(self, ok=True, bytes_written=1024):
        self.ok           = ok
        self.bytes_written = bytes_written
        self.calls        = []

    def resolve_url(self, asset_id, token, quality):
        return f"https://mock.api/assets/{asset_id}/download.zip"

    def download(self, url, token, dest_path):
        self.calls.append(dest_path)
        if self.ok:
            with open(dest_path, "wb") as f:
                f.write(b"x" * self.bytes_written)
            return {"ok": True, "bytes": self.bytes_written, "error": ""}
        return {"ok": False, "bytes": 0, "error": "mock error"}


@pytest.fixture(autouse=True)
def reset_all(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBRANTE_MEGASCANS_TOKEN", "tok")
    monkeypatch.setenv("VIBRANTE_ASSET_CACHE", str(tmp_path))
    reset_download_serializer_for_tests()
    reset_asset_cache_manager_for_tests()
    reset_asset_provenance_tracker_for_tests()
    reset_megascans_auth_for_tests()
    reset_megascans_downloader_for_tests()
    auth = get_megascans_auth()
    auth._transport = _MockAuthTransport()
    yield
    reset_megascans_downloader_for_tests()
    reset_megascans_auth_for_tests()
    reset_asset_provenance_tracker_for_tests()
    reset_asset_cache_manager_for_tests()
    reset_download_serializer_for_tests()
    monkeypatch.delenv("VIBRANTE_MEGASCANS_TOKEN", raising=False)
    monkeypatch.delenv("VIBRANTE_ASSET_CACHE", raising=False)


def test_singleton():
    a = get_megascans_downloader()
    b = get_megascans_downloader()
    assert a is b


def test_download_success(tmp_path):
    dl = get_megascans_downloader()
    transport = _MockDownloadTransport(ok=True, bytes_written=512)
    dl._transport = transport
    result = dl.download_asset("asset1", str(tmp_path))
    assert result.ok is True
    assert result.bytes_downloaded == 512
    assert os.path.isfile(result.local_path)


def test_download_no_token(monkeypatch):
    monkeypatch.delenv("VIBRANTE_MEGASCANS_TOKEN", raising=False)
    reset_megascans_auth_for_tests()
    reset_megascans_downloader_for_tests()
    dl = get_megascans_downloader()
    result = dl.download_asset("asset2", "/tmp/dest")
    assert result.ok is False
    assert "token" in result.error.lower() or result.source == "offline"


def test_download_failure(tmp_path):
    dl = get_megascans_downloader()
    transport = _MockDownloadTransport(ok=False)
    dl._transport = transport
    result = dl.download_asset("asset3", str(tmp_path))
    assert result.ok is False
    assert result.error != ""


def test_download_checksum_mismatch(tmp_path):
    dl = get_megascans_downloader()
    transport = _MockDownloadTransport(ok=True, bytes_written=100)
    dl._transport = transport
    result = dl.download_asset("asset4", str(tmp_path), expected_checksum="wronghash")
    assert result.ok is False
    assert "checksum" in result.error.lower()


def test_download_missing_asset_id(tmp_path):
    dl = get_megascans_downloader()
    result = dl.download_asset("", str(tmp_path))
    assert result.ok is False


def test_verify_download_file_exists(tmp_path):
    f = tmp_path / "check.zip"
    f.write_bytes(b"data")
    dl = get_megascans_downloader()
    result = dl.verify_download(str(f))
    assert result["verified"] is True


def test_verify_download_file_missing():
    dl = get_megascans_downloader()
    result = dl.verify_download("/nonexistent/file.zip")
    assert result["verified"] is False
    assert result["reason"] == "file_missing"


def test_register_download(tmp_path):
    f = tmp_path / "asset5.zip"
    f.write_bytes(b"content")
    dl = get_megascans_downloader()
    result = dl.register_download("asset5", str(f), provider="megascans")
    assert result["registered"] is True
    prov = get_asset_provenance_tracker().lookup("asset5", "megascans")
    assert prov is not None


def test_download_result_to_dict():
    r = DownloadResult(ok=True, asset_id="x", bytes_downloaded=999, checksum="c1")
    d = r.to_dict()
    assert d["ok"] is True
    assert d["bytes_downloaded"] == 999


def test_download_result_from_dict():
    d = {"ok": False, "asset_id": "y", "error": "timeout", "attempts": 3}
    r = DownloadResult.from_dict(d)
    assert r.ok is False
    assert r.attempts == 3


def test_statistics():
    dl = get_megascans_downloader()
    stats = dl.get_statistics()
    assert "download_count" in stats
