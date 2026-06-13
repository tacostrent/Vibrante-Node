"""Tests for src/runtime/assets/download/asset_download_manager.py"""
import pytest

from src.runtime.assets.download.asset_download_manager import (
    AssetDownloadManager,
    DownloadTask,
    STATUS_QUEUED, STATUS_COMPLETED, STATUS_CANCELLED,
    get_asset_download_manager,
    reset_asset_download_manager_for_tests,
)
from src.runtime.assets.schema import AssetDescriptor, AssetMetadata


def _make_asset(name="Test Asset", asset_id="test_asset_001") -> AssetDescriptor:
    return AssetDescriptor(
        asset_id=asset_id,
        provider="sketchfab",
        name=name,
        category="prop",
        formats=["fbx"],
        download_url="https://example.com/test.fbx",
    )


@pytest.fixture(autouse=True)
def reset():
    reset_asset_download_manager_for_tests()
    yield
    reset_asset_download_manager_for_tests()


class TestSingleton:
    def test_singleton_identity(self):
        m1 = get_asset_download_manager()
        m2 = get_asset_download_manager()
        assert m1 is m2

    def test_reset_creates_new(self):
        m1 = get_asset_download_manager()
        reset_asset_download_manager_for_tests()
        m2 = get_asset_download_manager()
        assert m1 is not m2


class TestQueue:
    def test_queue_returns_task_id(self):
        mgr = get_asset_download_manager()
        tid = mgr.queue_download(_make_asset())
        assert isinstance(tid, str)
        assert tid.startswith("dl_")

    def test_queue_unique_ids(self):
        mgr = get_asset_download_manager()
        t1 = mgr.queue_download(_make_asset(asset_id="a1"))
        t2 = mgr.queue_download(_make_asset(asset_id="a2"))
        assert t1 != t2

    def test_queue_with_destination(self, tmp_path):
        mgr = get_asset_download_manager()
        dest = str(tmp_path / "my_asset.fbx")
        tid = mgr.queue_download(_make_asset(), destination=dest)
        status = mgr.get_download_status(tid)
        assert status["destination"] == dest


class TestDownload:
    def test_download_asset_marks_completed(self):
        mgr = get_asset_download_manager()
        tid = mgr.queue_download(_make_asset())
        success = mgr.download_asset(tid)
        assert success is True
        status = mgr.get_download_status(tid)
        assert status["status"] == STATUS_COMPLETED
        assert status["progress"] == 1.0

    def test_download_nonexistent_returns_false(self):
        mgr = get_asset_download_manager()
        assert mgr.download_asset("nonexistent_task") is False

    def test_download_completed_idempotent(self):
        mgr = get_asset_download_manager()
        tid = mgr.queue_download(_make_asset())
        mgr.download_asset(tid)
        # Second call should still return True
        assert mgr.download_asset(tid) is True


class TestCancel:
    def test_cancel_queued(self):
        mgr = get_asset_download_manager()
        tid = mgr.queue_download(_make_asset())
        result = mgr.cancel_download(tid)
        assert result is True
        status = mgr.get_download_status(tid)
        assert status["status"] == STATUS_CANCELLED

    def test_cancel_nonexistent(self):
        mgr = get_asset_download_manager()
        assert mgr.cancel_download("nonexistent") is False

    def test_cancel_completed_returns_false(self):
        mgr = get_asset_download_manager()
        tid = mgr.queue_download(_make_asset())
        mgr.download_asset(tid)
        # Can't cancel a completed task
        assert mgr.cancel_download(tid) is False

    def test_download_cancelled_returns_false(self):
        mgr = get_asset_download_manager()
        tid = mgr.queue_download(_make_asset())
        mgr.cancel_download(tid)
        assert mgr.download_asset(tid) is False


class TestStatus:
    def test_get_status_found(self):
        mgr = get_asset_download_manager()
        tid = mgr.queue_download(_make_asset())
        status = mgr.get_download_status(tid)
        assert status["task_id"] == tid
        assert "status" in status
        assert "progress" in status
        assert "asset_id" in status
        assert "provider" in status

    def test_get_status_not_found(self):
        mgr = get_asset_download_manager()
        status = mgr.get_download_status("nonexistent")
        assert status["status"] == "not_found"

    def test_get_all_downloads(self):
        mgr = get_asset_download_manager()
        mgr.queue_download(_make_asset(asset_id="a1"))
        mgr.queue_download(_make_asset(asset_id="a2"))
        all_dl = mgr.get_all_downloads()
        assert len(all_dl) == 2

    def test_get_all_sorted_by_created_at(self):
        mgr = get_asset_download_manager()
        mgr.queue_download(_make_asset(asset_id="a1"))
        mgr.queue_download(_make_asset(asset_id="a2"))
        all_dl = mgr.get_all_downloads()
        times = [d["created_at"] for d in all_dl]
        assert times == sorted(times)


class TestClearAndStatistics:
    def test_clear_completed(self):
        mgr = get_asset_download_manager()
        t1 = mgr.queue_download(_make_asset(asset_id="a1"))
        t2 = mgr.queue_download(_make_asset(asset_id="a2"))
        mgr.download_asset(t1)
        cleared = mgr.clear_completed()
        assert cleared == 1
        assert len(mgr.get_all_downloads()) == 1

    def test_statistics_structure(self):
        mgr = get_asset_download_manager()
        s = mgr.get_statistics()
        assert "total_tasks" in s
        assert "by_status" in s
        assert "completed" in s
        assert "queued" in s

    def test_statistics_count(self):
        mgr = get_asset_download_manager()
        t1 = mgr.queue_download(_make_asset(asset_id="a1"))
        t2 = mgr.queue_download(_make_asset(asset_id="a2"))
        mgr.download_asset(t1)
        s = mgr.get_statistics()
        assert s["total_tasks"] == 2
        assert s["completed"] == 1
        assert s["queued"] == 1


class TestValidateDownload:
    def test_validate_completed(self):
        mgr = get_asset_download_manager()
        tid = mgr.queue_download(_make_asset())
        mgr.download_asset(tid)
        result = mgr.validate_download(tid)
        assert result["valid"] is True

    def test_validate_not_completed(self):
        mgr = get_asset_download_manager()
        tid = mgr.queue_download(_make_asset())
        result = mgr.validate_download(tid)
        assert result["valid"] is False

    def test_validate_nonexistent(self):
        mgr = get_asset_download_manager()
        result = mgr.validate_download("nonexistent")
        assert result["valid"] is False
