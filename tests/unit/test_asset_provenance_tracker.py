"""Tests for src/runtime/assets/acquisition_online/asset_provenance_tracker.py"""
import os
import pytest
from src.runtime.assets.acquisition_online import (
    get_asset_provenance_tracker,
    reset_asset_provenance_tracker_for_tests,
    reset_download_serializer_for_tests,
    ProvenanceRecord,
    compute_file_checksum,
)


@pytest.fixture(autouse=True)
def reset_all(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBRANTE_ASSET_CACHE", str(tmp_path))
    reset_download_serializer_for_tests()
    reset_asset_provenance_tracker_for_tests()
    yield
    reset_asset_provenance_tracker_for_tests()
    reset_download_serializer_for_tests()
    monkeypatch.delenv("VIBRANTE_ASSET_CACHE", raising=False)


def test_singleton():
    a = get_asset_provenance_tracker()
    b = get_asset_provenance_tracker()
    assert a is b


def test_register_and_lookup():
    tracker = get_asset_provenance_tracker()
    tracker.register("asset1", "megascans", "/tmp/asset1.zip", checksum="abc", source="download")
    rec = tracker.lookup("asset1", "megascans")
    assert rec is not None
    assert rec.asset_id == "asset1"
    assert rec.checksum == "abc"
    assert rec.source == "download"


def test_lookup_any_provider():
    tracker = get_asset_provenance_tracker()
    tracker.register("asset2", "fab", "/tmp/a2.zip")
    rec = tracker.lookup("asset2")
    assert rec is not None
    assert rec.provider == "fab"


def test_lookup_missing():
    tracker = get_asset_provenance_tracker()
    assert tracker.lookup("ghost_asset") is None


def test_get_history():
    tracker = get_asset_provenance_tracker()
    tracker.register("asset3", "megascans", "/tmp/v1.zip", version="1.0")
    tracker.register("asset3", "megascans", "/tmp/v2.zip", version="2.0")
    history = tracker.get_history("asset3", "megascans")
    assert len(history) == 2
    assert history[0].version == "1.0"
    assert history[1].version == "2.0"


def test_verify_no_record():
    tracker = get_asset_provenance_tracker()
    result = tracker.verify("nonexistent")
    assert result["verified"] is False
    assert result["reason"] == "no_provenance_record"


def test_verify_file_missing():
    tracker = get_asset_provenance_tracker()
    tracker.register("asset4", "megascans", "/nonexistent/path.zip")
    result = tracker.verify("asset4", "megascans")
    assert result["verified"] is False
    assert result["reason"] == "file_missing"


def test_verify_file_exists_no_checksum(tmp_path):
    tracker = get_asset_provenance_tracker()
    f = tmp_path / "asset5.zip"
    f.write_bytes(b"real data")
    tracker.register("asset5", "megascans", str(f), checksum="")
    result = tracker.verify("asset5", "megascans")
    assert result["verified"] is True


def test_verify_checksum_ok(tmp_path):
    tracker = get_asset_provenance_tracker()
    f = tmp_path / "asset6.zip"
    f.write_bytes(b"content")
    checksum = compute_file_checksum(str(f))
    tracker.register("asset6", "megascans", str(f), checksum=checksum)
    result = tracker.verify("asset6", "megascans")
    assert result["verified"] is True


def test_verify_checksum_mismatch(tmp_path):
    tracker = get_asset_provenance_tracker()
    f = tmp_path / "asset7.zip"
    f.write_bytes(b"content")
    tracker.register("asset7", "megascans", str(f), checksum="wronghash")
    result = tracker.verify("asset7", "megascans")
    assert result["verified"] is False
    assert result["reason"] == "checksum_mismatch"


def test_provenance_record_to_dict():
    rec = ProvenanceRecord(asset_id="r1", provider="fab", local_path="/p/r1.zip",
                           version="3.0", checksum="hash1", source="download")
    d = rec.to_dict()
    assert d["asset_id"] == "r1"
    assert d["provider"] == "fab"
    assert d["source"] == "download"


def test_provenance_record_from_dict():
    d = {"asset_id": "r2", "provider": "megascans", "local_path": "/p", "version": "1",
         "checksum": "h", "source": "local", "metadata": {}}
    rec = ProvenanceRecord.from_dict(d)
    assert rec.asset_id == "r2"
    assert rec.source == "local"


def test_statistics():
    tracker = get_asset_provenance_tracker()
    tracker.register("s1", "megascans", "/p1")
    tracker.register("s2", "megascans", "/p2")
    stats = tracker.get_statistics()
    assert stats["unique_assets"] == 2
    assert stats["register_count"] == 2
