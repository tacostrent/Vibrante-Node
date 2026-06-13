"""Tests for src/runtime/assets/acquisition_online/download_scheduler.py"""
import pytest
from src.runtime.assets.acquisition_online import (
    get_download_scheduler,
    get_download_queue,
    get_asset_cache_manager,
    get_megascans_auth,
    get_megascans_downloader,
    reset_download_scheduler_for_tests,
    reset_download_queue_for_tests,
    reset_asset_cache_manager_for_tests,
    reset_asset_fetcher_for_tests,
    reset_megascans_auth_for_tests,
    reset_megascans_downloader_for_tests,
    reset_download_statistics_for_tests,
    reset_download_serializer_for_tests,
    reset_asset_provenance_tracker_for_tests,
    SchedulerResult,
)


class _MockAuthTransport:
    def get_user_info(self, token):
        return {"user_id": "u1", "username": "t"}


class _MockDownloadTransport:
    def __init__(self, ok=True):
        self.ok = ok

    def resolve_url(self, asset_id, token, quality):
        return f"https://mock/{asset_id}.zip"

    def download(self, url, token, dest_path):
        if self.ok:
            with open(dest_path, "wb") as f:
                f.write(b"data")
            return {"ok": True, "bytes": 4, "error": ""}
        return {"ok": False, "bytes": 0, "error": "fail"}


@pytest.fixture(autouse=True)
def reset_all(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBRANTE_ASSET_CACHE", str(tmp_path))
    monkeypatch.setenv("VIBRANTE_MEGASCANS_TOKEN", "tok")
    reset_download_serializer_for_tests()
    reset_download_statistics_for_tests()
    reset_asset_provenance_tracker_for_tests()
    reset_asset_cache_manager_for_tests()
    reset_megascans_auth_for_tests()
    reset_megascans_downloader_for_tests()
    reset_asset_fetcher_for_tests()
    reset_download_queue_for_tests()
    reset_download_scheduler_for_tests()
    auth = get_megascans_auth()
    auth._transport = _MockAuthTransport()
    yield
    reset_download_scheduler_for_tests()
    reset_download_queue_for_tests()
    reset_asset_fetcher_for_tests()
    reset_megascans_downloader_for_tests()
    reset_megascans_auth_for_tests()
    reset_asset_cache_manager_for_tests()
    reset_asset_provenance_tracker_for_tests()
    reset_download_statistics_for_tests()
    reset_download_serializer_for_tests()
    monkeypatch.delenv("VIBRANTE_ASSET_CACHE", raising=False)
    monkeypatch.delenv("VIBRANTE_MEGASCANS_TOKEN", raising=False)


def test_singleton():
    a = get_download_scheduler()
    b = get_download_scheduler()
    assert a is b


def test_schedule_download():
    scheduler = get_download_scheduler()
    task = scheduler.schedule_download("asset1", provider="megascans", priority=7)
    assert task.asset_id == "asset1"
    assert task.priority == 7


def test_process_queue_success(tmp_path):
    dl = get_megascans_downloader()
    dl._transport = _MockDownloadTransport(ok=True)
    scheduler = get_download_scheduler()
    scheduler.set_rate_limit_delay(0.0)
    scheduler.schedule_download("s1", provider="megascans")
    scheduler.schedule_download("s2", provider="megascans")
    result = scheduler.process_queue(max_tasks=5, dest_dir=str(tmp_path))
    assert isinstance(result, SchedulerResult)
    assert result.succeeded == 2
    assert result.failed == 0
    assert result.ok is True


def test_process_queue_failure(tmp_path):
    dl = get_megascans_downloader()
    dl._transport = _MockDownloadTransport(ok=False)
    scheduler = get_download_scheduler()
    scheduler.set_rate_limit_delay(0.0)
    scheduler.schedule_download("f1", provider="megascans")
    result = scheduler.process_queue(max_tasks=1, dest_dir=str(tmp_path))
    assert result.failed == 1


def test_process_empty_queue():
    scheduler = get_download_scheduler()
    result = scheduler.process_queue(max_tasks=5)
    assert result.total == 0
    assert result.ok is True


def test_pause_resume():
    scheduler = get_download_scheduler()
    scheduler.pause()
    stats = scheduler.get_statistics()
    assert stats["paused"] is True
    scheduler.resume()
    stats = scheduler.get_statistics()
    assert stats["paused"] is False


def test_cancel():
    scheduler = get_download_scheduler()
    scheduler.cancel()


def test_set_rate_limit_delay():
    scheduler = get_download_scheduler()
    scheduler.set_rate_limit_delay(0.5)
    stats = scheduler.get_statistics()
    assert stats["delay_s"] == 0.5


def test_statistics_includes_queue():
    scheduler = get_download_scheduler()
    stats = scheduler.get_statistics()
    assert "queue" in stats
    assert "total_runs" in stats


def test_scheduler_result_to_dict():
    r = SchedulerResult(ok=True, total=3, succeeded=2, failed=1)
    d = r.to_dict()
    assert d["ok"] is True
    assert d["total"] == 3
    assert d["succeeded"] == 2
    assert d["failed"] == 1
