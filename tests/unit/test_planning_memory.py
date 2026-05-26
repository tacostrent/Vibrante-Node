"""
Unit tests for src.runtime.planning_memory.

Covers:
  • record returns a uuid event_id
  • unknown event_type raises ValueError
  • query by event_type
  • query by intent field
  • query limit respected
  • get_event by id
  • get_event unknown id returns None
  • stats output shape
  • clear resets memory
  • get_recent_plans convenience method
  • get_execution_results convenience method
  • max_records cap prunes oldest
  • disk write (temp file path)
  • singleton / reset
"""

from __future__ import annotations

import os
import tempfile
import pytest

from src.runtime.planning_memory import (
    PlanningMemory,
    get_planning_memory,
    reset_planning_memory_for_tests,
    PLANNING_EVENT_TYPES,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_planning_memory_for_tests()
    yield
    reset_planning_memory_for_tests()


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

def test_record_returns_uuid_string():
    mem = PlanningMemory()
    eid = mem.record("intent_parsed", {"intent": "build_pyro_source"})
    assert isinstance(eid, str) and len(eid) == 36


def test_record_unknown_event_type_raises():
    mem = PlanningMemory()
    with pytest.raises(ValueError, match="Unknown planning event type"):
        mem.record("not_a_real_type", {})


def test_record_all_valid_event_types():
    mem = PlanningMemory()
    for et in PLANNING_EVENT_TYPES:
        eid = mem.record(et, {"test": True})
        assert eid


def test_record_adds_timestamp():
    mem = PlanningMemory()
    eid = mem.record("plan_generated", {})
    event = mem.get_event(eid)
    assert "timestamp" in event
    assert isinstance(event["timestamp"], float)


def test_record_adds_event_type():
    mem = PlanningMemory()
    eid = mem.record("plan_approved", {"note": "ok"})
    event = mem.get_event(eid)
    assert event["event_type"] == "plan_approved"


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------

def test_query_by_event_type():
    mem = PlanningMemory()
    mem.record("intent_parsed",   {"intent": "pyro"})
    mem.record("plan_generated",  {"intent": "pyro"})
    mem.record("intent_parsed",   {"intent": "geo"})
    results = mem.query(event_type="intent_parsed")
    assert len(results) == 2
    assert all(r["event_type"] == "intent_parsed" for r in results)


def test_query_by_intent():
    mem = PlanningMemory()
    mem.record("intent_parsed",  {"intent": "build_pyro_source"})
    mem.record("intent_parsed",  {"intent": "create_geo_container"})
    mem.record("plan_generated", {"intent": "build_pyro_source"})
    results = mem.query(intent="build_pyro_source")
    assert len(results) == 2


def test_query_limit():
    mem = PlanningMemory()
    for i in range(20):
        mem.record("intent_parsed", {"intent": f"op_{i}"})
    results = mem.query(limit=5)
    assert len(results) == 5


def test_query_newest_first():
    mem = PlanningMemory()
    mem.record("intent_parsed", {"intent": "first"})
    mem.record("intent_parsed", {"intent": "second"})
    results = mem.query(event_type="intent_parsed", limit=2)
    # newest = second recorded = index 0 (reversed list)
    assert results[0]["intent"] == "second"


# ---------------------------------------------------------------------------
# get_event
# ---------------------------------------------------------------------------

def test_get_event_returns_copy():
    mem = PlanningMemory()
    eid = mem.record("plan_rejected", {"reason": "too risky"})
    event = mem.get_event(eid)
    assert event["reason"] == "too risky"
    event["reason"] = "mutated"
    # original must be unchanged
    event2 = mem.get_event(eid)
    assert event2["reason"] == "too risky"


def test_get_event_unknown_returns_none():
    mem = PlanningMemory()
    assert mem.get_event("00000000-0000-0000-0000-000000000000") is None


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    mem = PlanningMemory()
    mem.record("intent_parsed",  {})
    mem.record("plan_generated", {})
    mem.record("plan_approved",  {})
    stats = mem.stats()
    assert stats["total_events"] == 3
    assert stats["by_type"]["intent_parsed"] == 1
    assert stats["by_type"]["plan_generated"] == 1
    assert "write_count" in stats


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

def test_clear_removes_all():
    mem = PlanningMemory()
    mem.record("intent_parsed", {})
    mem.clear()
    assert mem.query() == []
    assert mem.stats()["total_events"] == 0


# ---------------------------------------------------------------------------
# convenience methods
# ---------------------------------------------------------------------------

def test_get_recent_plans():
    mem = PlanningMemory()
    mem.record("intent_parsed",  {"intent": "x"})
    mem.record("plan_generated", {"intent": "x"})
    mem.record("plan_generated", {"intent": "y"})
    plans = mem.get_recent_plans(limit=10)
    assert len(plans) == 2
    assert all(p["event_type"] == "plan_generated" for p in plans)


def test_get_execution_results_filtered():
    mem = PlanningMemory()
    mem.record("execution_result", {"intent": "a", "ok": True})
    mem.record("execution_result", {"intent": "b", "ok": False})
    results = mem.get_execution_results(intent="a")
    assert len(results) == 1
    assert results[0]["intent"] == "a"


# ---------------------------------------------------------------------------
# max_records cap
# ---------------------------------------------------------------------------

def test_max_records_prunes_oldest():
    mem = PlanningMemory(max_records=10)
    for i in range(30):
        mem.record("intent_parsed", {"seq": i})
    # Lazy pruning triggers at 2× cap, dropping to max_records.
    # After 30 inserts: pruning fires once (at record 21) leaving 10, then
    # records 22-30 add 9 more, giving at most 2*max_records-1 entries.
    assert len(mem.query(limit=1000)) <= 20


# ---------------------------------------------------------------------------
# disk persistence
# ---------------------------------------------------------------------------

def test_disk_write_creates_jsonl(tmp_path):
    path = str(tmp_path / "planning.jsonl")
    mem  = PlanningMemory(path=path)
    mem.record("intent_parsed", {"intent": "disk_test"})
    assert os.path.exists(path)
    with open(path) as f:
        lines = [l for l in f if l.strip()]
    assert len(lines) == 1


def test_disk_load_restores_records(tmp_path):
    path = str(tmp_path / "planning.jsonl")
    mem1 = PlanningMemory(path=path)
    mem1.record("plan_approved", {"intent": "pyro"})

    mem2 = PlanningMemory(path=path)
    mem2._load_from_disk()
    assert mem2.stats()["total_events"] >= 1


# ---------------------------------------------------------------------------
# singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_planning_memory()
    b = get_planning_memory()
    assert a is b


def test_reset_fresh_singleton():
    a = get_planning_memory()
    reset_planning_memory_for_tests()
    b = get_planning_memory()
    assert a is not b
