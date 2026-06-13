"""Tests for src/runtime/assets/acquisition_online/download_queue.py"""
import pytest
from src.runtime.assets.acquisition_online import (
    get_download_queue,
    reset_download_queue_for_tests,
    reset_download_serializer_for_tests,
    DownloadTask,
)


@pytest.fixture(autouse=True)
def reset_all(monkeypatch):
    monkeypatch.delenv("VIBRANTE_ASSET_CACHE", raising=False)
    reset_download_serializer_for_tests()
    reset_download_queue_for_tests()
    yield
    reset_download_queue_for_tests()
    reset_download_serializer_for_tests()


def test_singleton():
    a = get_download_queue()
    b = get_download_queue()
    assert a is b


def test_enqueue_basic():
    q = get_download_queue()
    task = q.enqueue("asset1", provider="megascans", quality="medium")
    assert task.asset_id == "asset1"
    assert task.provider == "megascans"
    assert task.status == "pending"
    assert task.task_id.startswith("dl_")


def test_enqueue_dedup():
    q = get_download_queue()
    t1 = q.enqueue("asset1", provider="megascans")
    t2 = q.enqueue("asset1", provider="megascans")  # same asset, should dedup
    assert t1.task_id == t2.task_id


def test_enqueue_no_asset_id():
    q = get_download_queue()
    task = q.enqueue("")
    assert task.status == "failed"


def test_dequeue_returns_highest_priority():
    q = get_download_queue()
    q.enqueue("low_priority",  provider="megascans", priority=1)
    q.enqueue("high_priority", provider="megascans", priority=9)
    task = q.dequeue()
    assert task is not None
    assert task.asset_id == "high_priority"
    assert task.status == "in_progress"


def test_dequeue_empty_queue():
    q = get_download_queue()
    assert q.dequeue() is None


def test_complete_task():
    q = get_download_queue()
    task = q.enqueue("asset2", provider="fab")
    q.dequeue()  # marks in_progress
    ok = q.complete(task.task_id)
    assert ok is True
    updated = q.get_status(task.task_id)
    assert updated.status == "completed"


def test_fail_task():
    q = get_download_queue()
    task = q.enqueue("asset3", provider="megascans")
    q.dequeue()
    ok = q.fail(task.task_id, error="network error")
    assert ok is True
    updated = q.get_status(task.task_id)
    assert updated.status == "failed"
    assert updated.error == "network error"


def test_cancel_pending():
    q = get_download_queue()
    task = q.enqueue("asset4", provider="megascans")
    ok = q.cancel(task.task_id)
    assert ok is True
    updated = q.get_status(task.task_id)
    assert updated.status == "cancelled"


def test_retry_failed():
    q = get_download_queue()
    task = q.enqueue("asset5", provider="megascans")
    q.dequeue()
    q.fail(task.task_id, error="timeout")
    ok = q.retry(task.task_id)
    assert ok is True
    updated = q.get_status(task.task_id)
    assert updated.status == "pending"
    assert updated.retry_count == 1


def test_get_pending():
    q = get_download_queue()
    q.enqueue("a1", priority=5)
    q.enqueue("a2", priority=8)
    pending = q.get_pending()
    assert len(pending) == 2
    assert pending[0].asset_id == "a2"  # highest priority first


def test_clear_completed():
    q = get_download_queue()
    t1 = q.enqueue("c1", provider="megascans")
    t2 = q.enqueue("c2", provider="megascans")
    q.dequeue()
    q.complete(t1.task_id)
    n = q.clear_completed()
    assert n >= 1


def test_get_statistics():
    q = get_download_queue()
    q.enqueue("s1")
    q.enqueue("s2")
    stats = q.get_statistics()
    assert stats["total"] == 2
    assert stats["by_status"]["pending"] == 2


def test_download_task_roundtrip():
    task = DownloadTask(asset_id="t1", provider="fab", quality="high", priority=7)
    d = task.to_dict()
    restored = DownloadTask.from_dict(d)
    assert restored.asset_id == "t1"
    assert restored.priority == 7
    assert restored.quality == "high"
