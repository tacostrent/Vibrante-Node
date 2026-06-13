"""Tests for src/runtime/assets/acquisition_online/download_statistics.py"""
import pytest
from src.runtime.assets.acquisition_online import (
    get_download_statistics,
    reset_download_statistics_for_tests,
    DownloadRecord,
)


@pytest.fixture(autouse=True)
def reset_all():
    reset_download_statistics_for_tests()
    yield
    reset_download_statistics_for_tests()


def test_singleton_returned():
    a = get_download_statistics()
    b = get_download_statistics()
    assert a is b


def test_record_basic():
    stats = get_download_statistics()
    stats.record(asset_id="abc", provider="megascans", source="cache", bytes_downloaded=1024, ok=True)
    summary = stats.get_summary()
    assert summary["total_downloads"] == 1
    assert summary["cache_hits"] == 1
    assert summary["cache_misses"] == 0


def test_record_download():
    stats = get_download_statistics()
    stats.record(asset_id="xyz", provider="megascans", source="megascans_api", bytes_downloaded=2048, ok=True)
    summary = stats.get_summary()
    assert summary["cache_hits"] == 0
    assert summary["cache_misses"] == 1
    assert summary["total_bytes"] == 2048


def test_cache_hit_rate():
    stats = get_download_statistics()
    stats.record(source="cache", ok=True)
    stats.record(source="megascans_api", ok=True)
    summary = stats.get_summary()
    assert summary["cache_hit_rate"] == 0.5


def test_get_recent():
    stats = get_download_statistics()
    for i in range(5):
        stats.record(asset_id=f"a{i}", ok=True)
    recent = stats.get_recent(3)
    assert len(recent) == 3
    assert recent[-1]["asset_id"] == "a4"


def test_record_never_raises():
    stats = get_download_statistics()
    stats.record(bytes_downloaded=None, duration_ms=None)  # Should not raise


def test_download_record_to_dict():
    rec = DownloadRecord(asset_id="id1", provider="megascans", source="cache", bytes_downloaded=512, ok=True)
    d = rec.to_dict()
    assert d["asset_id"] == "id1"
    assert d["provider"] == "megascans"
    assert d["source"] == "cache"
    assert d["bytes_downloaded"] == 512
    assert d["ok"] is True


def test_reset_clears_data():
    stats = get_download_statistics()
    stats.record(asset_id="x", ok=True)
    stats.reset()
    summary = stats.get_summary()
    assert summary["total_downloads"] == 0
    assert summary["record_count"] == 0


def test_top_providers():
    stats = get_download_statistics()
    for _ in range(3):
        stats.record(provider="megascans")
    stats.record(provider="fab")
    summary = stats.get_summary()
    providers = [p[0] for p in summary["top_providers"]]
    assert "megascans" in providers


def test_record_count():
    stats = get_download_statistics()
    for i in range(10):
        stats.record(asset_id=str(i))
    assert stats.get_summary()["record_count"] == 10
