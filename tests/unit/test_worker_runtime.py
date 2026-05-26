"""
Unit tests for src.runtime.worker_runtime.

Covers:
  • register_worker returns uuid
  • register_worker empty name raises
  • deregister_worker True / False
  • get_worker / list_workers
  • list_workers status filter
  • update_heartbeat True / False
  • update_heartbeat revives offline worker
  • acquire_worker returns id when available
  • acquire_worker returns None when no matching worker
  • acquire_worker least-loaded selection
  • acquire_worker at max_load returns None
  • release_worker decrements load
  • release_worker below zero clamped to zero
  • find_workers_for capability match
  • find_workers_for status filter
  • check_stale_workers marks offline
  • stats shape
  • singleton / reset
"""

from __future__ import annotations

import time

import pytest

from src.runtime.worker_runtime import (
    WorkerRuntime,
    get_worker_runtime,
    reset_worker_runtime_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_worker_runtime_for_tests()
    yield
    reset_worker_runtime_for_tests()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_worker_returns_uuid():
    wr  = get_worker_runtime()
    wid = wr.register_worker("farm-01", ["houdini", "karma"])
    assert isinstance(wid, str) and len(wid) == 36


def test_register_worker_empty_name_raises():
    wr = get_worker_runtime()
    with pytest.raises(ValueError):
        wr.register_worker("", [])


def test_deregister_worker_true():
    wr  = get_worker_runtime()
    wid = wr.register_worker("farm-01", [])
    assert wr.deregister_worker(wid) is True
    assert wr.get_worker(wid) is None


def test_deregister_worker_unknown_false():
    wr = get_worker_runtime()
    assert wr.deregister_worker("00000000-0000-0000-0000-000000000000") is False


def test_get_worker_returns_dict():
    wr  = get_worker_runtime()
    wid = wr.register_worker("farm-01", ["houdini"], endpoint="remote://host1", max_load=8)
    w   = wr.get_worker(wid)
    assert w is not None
    assert w["name"]     == "farm-01"
    assert "houdini" in w["capabilities"]
    assert w["max_load"] == 8
    assert w["status"]   == "idle"


def test_get_worker_unknown_returns_none():
    wr = get_worker_runtime()
    assert wr.get_worker("missing") is None


def test_list_workers_status_filter():
    wr  = get_worker_runtime()
    w1  = wr.register_worker("idle-worker",  ["a"], max_load=4)
    w2  = wr.register_worker("busy-worker",  ["b"], max_load=1)
    wr.acquire_worker(["b"])   # fills w2 → busy
    idle_workers = wr.list_workers(status="idle")
    assert all(w["status"] == "idle" for w in idle_workers)
    assert any(w["id"] == w1 for w in idle_workers)


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

def test_update_heartbeat_true():
    wr  = get_worker_runtime()
    wid = wr.register_worker("worker-01", [])
    assert wr.update_heartbeat(wid) is True


def test_update_heartbeat_unknown_false():
    wr = get_worker_runtime()
    assert wr.update_heartbeat("missing") is False


def test_update_heartbeat_revives_offline_worker():
    wr  = get_worker_runtime()
    wid = wr.register_worker("old-worker", [])
    # Force offline via check_stale with a very short timeout
    with wr._lock:
        wr._workers[wid]["last_heartbeat"] = time.time() - 200
    stale = wr.check_stale_workers(timeout_sec=10)
    assert wid in stale
    assert wr.get_worker(wid)["status"] == "offline"
    # Revive
    wr.update_heartbeat(wid)
    assert wr.get_worker(wid)["status"] == "idle"


# ---------------------------------------------------------------------------
# Acquire / release
# ---------------------------------------------------------------------------

def test_acquire_worker_returns_id():
    wr  = get_worker_runtime()
    wid = wr.register_worker("farm-01", ["houdini"])
    acquired = wr.acquire_worker(["houdini"])
    assert acquired == wid


def test_acquire_worker_no_match_returns_none():
    wr = get_worker_runtime()
    wr.register_worker("farm-01", ["maya"])
    assert wr.acquire_worker(["houdini"]) is None


def test_acquire_worker_at_max_load_returns_none():
    wr  = get_worker_runtime()
    wid = wr.register_worker("farm-01", ["houdini"], max_load=1)
    wr.acquire_worker(["houdini"])   # fills it
    assert wr.acquire_worker(["houdini"]) is None


def test_acquire_worker_least_loaded():
    wr  = get_worker_runtime()
    w1  = wr.register_worker("w1", ["cap"], max_load=4)
    w2  = wr.register_worker("w2", ["cap"], max_load=4)
    # Pre-fill w1 with 3 tasks directly so w2 is definitely less loaded
    with wr._lock:
        wr._workers[w1]["current_load"] = 3
        wr._workers[w1]["status"] = "busy"
    # Next acquire should prefer w2 (load 0 < w1 load 3)
    acquired = wr.acquire_worker(["cap"])
    assert acquired == w2


def test_release_worker_decrements_load():
    wr  = get_worker_runtime()
    wid = wr.register_worker("w1", ["cap"], max_load=4)
    wr.acquire_worker(["cap"])
    assert wr.get_worker(wid)["current_load"] == 1
    wr.release_worker(wid)
    assert wr.get_worker(wid)["current_load"] == 0
    assert wr.get_worker(wid)["status"] == "idle"


def test_release_worker_unknown_false():
    wr = get_worker_runtime()
    assert wr.release_worker("missing") is False


def test_release_worker_not_below_zero():
    wr  = get_worker_runtime()
    wid = wr.register_worker("w1", [], max_load=4)
    # Release without acquire
    wr.release_worker(wid)
    assert wr.get_worker(wid)["current_load"] == 0


# ---------------------------------------------------------------------------
# find_workers_for
# ---------------------------------------------------------------------------

def test_find_workers_for_capability_match():
    wr = get_worker_runtime()
    w1 = wr.register_worker("h1", ["houdini", "karma"])
    w2 = wr.register_worker("m1", ["maya"])
    found = wr.find_workers_for(["houdini"])
    assert w1 in found
    assert w2 not in found


def test_find_workers_for_all_caps_required():
    wr = get_worker_runtime()
    w1 = wr.register_worker("full", ["houdini", "karma", "redshift"])
    w2 = wr.register_worker("part", ["houdini"])
    found = wr.find_workers_for(["houdini", "karma"])
    assert w1 in found
    assert w2 not in found


def test_find_workers_for_empty_caps_matches_all():
    wr = get_worker_runtime()
    w1 = wr.register_worker("a", ["houdini"])
    w2 = wr.register_worker("b", ["maya"])
    found = wr.find_workers_for([])
    assert w1 in found and w2 in found


# ---------------------------------------------------------------------------
# check_stale_workers
# ---------------------------------------------------------------------------

def test_check_stale_workers_marks_offline():
    wr  = get_worker_runtime()
    wid = wr.register_worker("stale-worker", [])
    with wr._lock:
        wr._workers[wid]["last_heartbeat"] = time.time() - 300
    stale = wr.check_stale_workers(timeout_sec=60)
    assert wid in stale
    assert wr.get_worker(wid)["status"] == "offline"


def test_check_stale_workers_fresh_not_included():
    wr  = get_worker_runtime()
    wid = wr.register_worker("fresh-worker", [])
    stale = wr.check_stale_workers(timeout_sec=60)
    assert wid not in stale


def test_check_stale_workers_already_offline_not_duplicated():
    wr  = get_worker_runtime()
    wid = wr.register_worker("w1", [])
    with wr._lock:
        wr._workers[wid]["last_heartbeat"] = time.time() - 300
        wr._workers[wid]["status"] = "offline"
    # Should not be returned again (already offline)
    stale = wr.check_stale_workers(timeout_sec=60)
    assert wid not in stale


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    wr = get_worker_runtime()
    wr.register_worker("w1", ["houdini"], max_load=4)
    wr.register_worker("w2", ["maya"],    max_load=8)
    s = wr.stats()
    assert "total_workers"  in s
    assert "by_status"      in s
    assert "total_load"     in s
    assert "total_capacity" in s
    assert s["total_workers"]  == 2
    assert s["total_capacity"] == 12


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_worker_runtime()
    b = get_worker_runtime()
    assert a is b


def test_reset_creates_fresh_instance():
    a = get_worker_runtime()
    reset_worker_runtime_for_tests()
    b = get_worker_runtime()
    assert a is not b
