"""
tests/unit/test_mcp_session.py
================================
Unit tests for src.runtime.mcp_session.
"""

import time

import pytest

from src.runtime.mcp_session import (
    MCPSession,
    SessionManager,
    SESSION_EVENT_TYPES,
    get_session_manager,
    reset_sessions_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_sessions_for_tests()
    yield
    reset_sessions_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_object():
    m1 = get_session_manager()
    m2 = get_session_manager()
    assert m1 is m2


def test_reset_creates_fresh_instance():
    m1 = get_session_manager()
    reset_sessions_for_tests()
    m2 = get_session_manager()
    assert m1 is not m2


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------

def test_create_session_returns_uuid_string():
    mgr = get_session_manager()
    sid = mgr.create_session()
    assert isinstance(sid, str)
    assert len(sid) == 36   # uuid4 canonical form


def test_create_session_with_client_id():
    mgr = get_session_manager()
    sid = mgr.create_session("claude-desktop")
    session = mgr.get_session(sid)
    assert session["client_id"] == "claude-desktop"


def test_create_session_auto_client_id():
    mgr = get_session_manager()
    sid = mgr.create_session()
    session = mgr.get_session(sid)
    assert session["client_id"].startswith("client-")


def test_create_two_sessions_distinct_ids():
    mgr = get_session_manager()
    s1  = mgr.create_session()
    s2  = mgr.create_session()
    assert s1 != s2


# ---------------------------------------------------------------------------
# get_session
# ---------------------------------------------------------------------------

def test_get_session_returns_dict():
    mgr = get_session_manager()
    sid = mgr.create_session()
    s   = mgr.get_session(sid)
    assert isinstance(s, dict)


def test_get_session_keys():
    mgr = get_session_manager()
    sid = mgr.create_session()
    s   = mgr.get_session(sid)
    required = {
        "session_id", "client_id", "created_at", "last_activity",
        "closed", "active_goals", "pending_approval_ids",
        "has_current_plan", "event_count",
    }
    assert required <= set(s.keys())


def test_get_nonexistent_session_returns_none():
    mgr = get_session_manager()
    assert mgr.get_session("00000000-0000-0000-0000-000000000000") is None


def test_get_session_not_closed_by_default():
    mgr = get_session_manager()
    sid = mgr.create_session()
    s   = mgr.get_session(sid)
    assert s["closed"] is False


# ---------------------------------------------------------------------------
# close_session
# ---------------------------------------------------------------------------

def test_close_session_marks_closed():
    mgr = get_session_manager()
    sid = mgr.create_session()
    assert mgr.close_session(sid) is True
    s   = mgr.get_session(sid)
    assert s["closed"] is True


def test_close_nonexistent_returns_false():
    mgr = get_session_manager()
    assert mgr.close_session("00000000-0000-0000-0000-000000000000") is False


# ---------------------------------------------------------------------------
# update_session
# ---------------------------------------------------------------------------

def test_update_session_active_goals():
    mgr = get_session_manager()
    sid = mgr.create_session()
    assert mgr.update_session(sid, active_goals=["build_pyro"]) is True
    s   = mgr.get_session(sid)
    assert s["active_goals"] == ["build_pyro"]


def test_update_session_current_plan():
    mgr = get_session_manager()
    sid = mgr.create_session()
    mgr.update_session(sid, current_plan={"intent": "pyro"})
    s   = mgr.get_session(sid)
    assert s["has_current_plan"] is True


def test_update_nonexistent_returns_false():
    mgr = get_session_manager()
    assert mgr.update_session("bad-id", active_goals=["x"]) is False


def test_update_ignores_non_mutable_fields():
    mgr = get_session_manager()
    sid = mgr.create_session()
    # session_id is not in _MUTABLE_FIELDS — should be silently ignored
    mgr.update_session(sid, session_id="hacked")
    s = mgr.get_session(sid)
    assert s["session_id"] == sid


# ---------------------------------------------------------------------------
# record_session_event / get_session_history
# ---------------------------------------------------------------------------

def test_record_valid_event():
    mgr = get_session_manager()
    sid = mgr.create_session()
    ok  = mgr.record_session_event(sid, "plan_generated", {"intent": "pyro"})
    assert ok is True


def test_record_event_appears_in_history():
    mgr = get_session_manager()
    sid = mgr.create_session()
    mgr.record_session_event(sid, "plan_generated", {"intent": "pyro"})
    history = mgr.get_session_history(sid)
    types = [e["event_type"] for e in history]
    assert "plan_generated" in types
    assert "session_started" in types   # auto-recorded on create


def test_record_invalid_event_type_normalised():
    mgr = get_session_manager()
    sid = mgr.create_session()
    mgr.record_session_event(sid, "definitely_unknown_type", {})
    history = mgr.get_session_history(sid)
    types   = [e["event_type"] for e in history]
    assert "error" in types


def test_record_event_for_nonexistent_session_returns_false():
    mgr = get_session_manager()
    assert mgr.record_session_event("nope", "plan_generated") is False


def test_get_session_history_nonexistent_returns_empty():
    mgr = get_session_manager()
    assert mgr.get_session_history("nope") == []


def test_history_contains_timestamps():
    mgr = get_session_manager()
    sid = mgr.create_session()
    history = mgr.get_session_history(sid)
    for event in history:
        assert "timestamp" in event
        assert isinstance(event["timestamp"], float)


# ---------------------------------------------------------------------------
# list_sessions / active_session_count / stats
# ---------------------------------------------------------------------------

def test_list_sessions_returns_list():
    mgr = get_session_manager()
    assert isinstance(mgr.list_sessions(), list)


def test_list_sessions_contains_created():
    mgr = get_session_manager()
    s1  = mgr.create_session()
    s2  = mgr.create_session()
    ids = [s["session_id"] for s in mgr.list_sessions()]
    assert s1 in ids
    assert s2 in ids


def test_active_session_count():
    mgr = get_session_manager()
    s1  = mgr.create_session()
    s2  = mgr.create_session()
    assert mgr.active_session_count() == 2
    mgr.close_session(s1)
    assert mgr.active_session_count() == 1


def test_stats_keys():
    mgr  = get_session_manager()
    mgr.create_session()
    stat = mgr.stats()
    assert "total_sessions"  in stat
    assert "active_sessions" in stat
    assert "closed_sessions" in stat


def test_stats_counts():
    mgr = get_session_manager()
    s1  = mgr.create_session()
    mgr.create_session()
    mgr.close_session(s1)
    stat = mgr.stats()
    assert stat["total_sessions"]  == 2
    assert stat["active_sessions"] == 1
    assert stat["closed_sessions"] == 1


# ---------------------------------------------------------------------------
# MCPSession.to_dict copies, not references
# ---------------------------------------------------------------------------

def test_to_dict_active_goals_is_copy():
    session = MCPSession("abc", "client")
    session.active_goals = ["goal_a"]
    d = session.to_dict()
    d["active_goals"].append("goal_b")
    assert session.active_goals == ["goal_a"]   # original unchanged


# ---------------------------------------------------------------------------
# EVENT_TYPES constant
# ---------------------------------------------------------------------------

def test_all_known_event_types_are_valid():
    for et in SESSION_EVENT_TYPES:
        assert isinstance(et, str)
        assert len(et) > 0
