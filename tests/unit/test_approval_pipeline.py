"""
Unit tests for src.runtime.approval_pipeline.

Covers:
  • requires_approval: True when plan.requires_approval set
  • requires_approval: True for high risk_level
  • requires_approval: True when delete_node op present
  • requires_approval: False for safe low-risk plan
  • submit_for_approval returns a uuid request_id
  • get_status after submit → status=pending
  • approve transitions pending → approved
  • reject transitions pending → rejected
  • defer transitions pending → deferred
  • cannot approve non-pending (already approved) → returns False
  • cannot approve unknown request_id → returns False
  • auto_approve returns status=auto without storing
  • list_pending returns only pending
  • list_pending sorted oldest first
  • expiry: expired requests show as expired
  • clear removes all records
  • stats shape
  • singleton / reset
"""

from __future__ import annotations

import time
import pytest

from src.runtime.approval_pipeline import (
    ApprovalPipeline,
    get_approval_pipeline,
    reset_approval_pipeline_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_approval_pipeline_for_tests()
    yield
    reset_approval_pipeline_for_tests()


def _low_risk_plan():
    return {
        "requires_approval": False,
        "resource_estimate": {"risk_level": "low", "estimated_cook_cost": 0.1},
        "operations": [{"op": "create_node", "parent": "/obj", "type": "geo"}],
        "plan_id": "plan-001",
        "intent": "create_geo_container",
        "op_count": 1,
        "approval_reasons": [],
    }


def _high_risk_plan():
    return {
        "requires_approval": True,
        "resource_estimate": {"risk_level": "high", "estimated_cook_cost": 1.2},
        "operations": [{"op": "delete_node", "path": "/obj/important"}],
        "plan_id": "plan-002",
        "intent": "cleanup",
        "op_count": 1,
        "approval_reasons": ["High risk detected.", "Destructive op: delete_node."],
    }


# ---------------------------------------------------------------------------
# requires_approval
# ---------------------------------------------------------------------------

def test_requires_approval_when_flag_set():
    pipe = get_approval_pipeline()
    plan = _high_risk_plan()
    assert pipe.requires_approval(plan) is True


def test_requires_approval_for_high_risk_level():
    pipe = get_approval_pipeline()
    plan = {
        "requires_approval": False,
        "resource_estimate": {"risk_level": "high"},
        "operations": [],
        "approval_reasons": [],
    }
    assert pipe.requires_approval(plan) is True


def test_requires_approval_for_delete_node_op():
    pipe = get_approval_pipeline()
    plan = {
        "requires_approval": False,
        "resource_estimate": {"risk_level": "low"},
        "operations": [{"op": "delete_node", "path": "/obj/old"}],
        "approval_reasons": [],
    }
    assert pipe.requires_approval(plan) is True


def test_does_not_require_approval_for_safe_plan():
    pipe = get_approval_pipeline()
    assert pipe.requires_approval(_low_risk_plan()) is False


# ---------------------------------------------------------------------------
# submit + get_status
# ---------------------------------------------------------------------------

def test_submit_returns_uuid():
    pipe = get_approval_pipeline()
    req_id = pipe.submit_for_approval(_low_risk_plan())
    assert isinstance(req_id, str) and len(req_id) == 36


def test_get_status_pending_after_submit():
    pipe = get_approval_pipeline()
    req_id = pipe.submit_for_approval(_low_risk_plan())
    status = pipe.get_status(req_id)
    assert status is not None
    assert status["status"] == "pending"


def test_get_status_unknown_returns_none():
    pipe = get_approval_pipeline()
    assert pipe.get_status("00000000-0000-0000-0000-000000000000") is None


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------

def test_approve_transitions_to_approved():
    pipe = get_approval_pipeline()
    req_id = pipe.submit_for_approval(_high_risk_plan())
    ok = pipe.approve(req_id, approver="td_lead")
    assert ok is True
    status = pipe.get_status(req_id)
    assert status["status"] == "approved"
    assert status["approver"] == "td_lead"


def test_approve_returns_false_for_unknown():
    pipe = get_approval_pipeline()
    assert pipe.approve("no-such-id") is False


def test_approve_returns_false_when_already_approved():
    pipe = get_approval_pipeline()
    req_id = pipe.submit_for_approval(_high_risk_plan())
    pipe.approve(req_id)
    assert pipe.approve(req_id) is False


# ---------------------------------------------------------------------------
# reject
# ---------------------------------------------------------------------------

def test_reject_transitions_to_rejected():
    pipe = get_approval_pipeline()
    req_id = pipe.submit_for_approval(_high_risk_plan())
    ok = pipe.reject(req_id, approver="supervisor", reason="Too many deletions.")
    assert ok is True
    status = pipe.get_status(req_id)
    assert status["status"] == "rejected"
    assert "Too many" in status["notes"]


def test_reject_returns_false_when_already_decided():
    pipe = get_approval_pipeline()
    req_id = pipe.submit_for_approval(_high_risk_plan())
    pipe.reject(req_id)
    assert pipe.reject(req_id) is False


# ---------------------------------------------------------------------------
# defer
# ---------------------------------------------------------------------------

def test_defer_transitions_to_deferred():
    pipe = get_approval_pipeline()
    req_id = pipe.submit_for_approval(_low_risk_plan())
    ok = pipe.defer(req_id, notes="Revisit after lunch.")
    assert ok is True
    assert pipe.get_status(req_id)["status"] == "deferred"


# ---------------------------------------------------------------------------
# auto_approve
# ---------------------------------------------------------------------------

def test_auto_approve_returns_auto_status():
    pipe = get_approval_pipeline()
    result = pipe.auto_approve(_low_risk_plan())
    assert result["status"] == "auto"


def test_auto_approve_does_not_store_in_pipeline():
    pipe = get_approval_pipeline()
    result = pipe.auto_approve(_low_risk_plan())
    # The returned request_id should not be in the store
    req_id = result["request_id"]
    assert pipe.get_status(req_id) is None


# ---------------------------------------------------------------------------
# list_pending
# ---------------------------------------------------------------------------

def test_list_pending_empty_initially():
    pipe = get_approval_pipeline()
    assert pipe.list_pending() == []


def test_list_pending_shows_only_pending():
    pipe = get_approval_pipeline()
    r1 = pipe.submit_for_approval(_low_risk_plan())
    r2 = pipe.submit_for_approval(_high_risk_plan())
    pipe.approve(r1)
    pending = pipe.list_pending()
    assert len(pending) == 1
    assert pending[0]["request_id"] == r2


def test_list_pending_oldest_first():
    pipe = get_approval_pipeline()
    r1 = pipe.submit_for_approval(_low_risk_plan())
    time.sleep(0.01)
    r2 = pipe.submit_for_approval(_low_risk_plan())
    pending = pipe.list_pending()
    assert pending[0]["request_id"] == r1
    assert pending[1]["request_id"] == r2


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------

def test_expired_request_shows_as_expired():
    pipe = ApprovalPipeline(expiry_sec=1)
    req_id = pipe.submit_for_approval(_low_risk_plan())
    # Manually expire by backdating
    with pipe._lock:
        pipe._store[req_id]["expires_at"] = time.time() - 1
    status = pipe.get_status(req_id)
    assert status["status"] == "expired"


def test_approve_expired_returns_false():
    pipe = ApprovalPipeline(expiry_sec=1)
    req_id = pipe.submit_for_approval(_low_risk_plan())
    with pipe._lock:
        pipe._store[req_id]["expires_at"] = time.time() - 1
    assert pipe.approve(req_id) is False


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

def test_clear_removes_all():
    pipe = get_approval_pipeline()
    pipe.submit_for_approval(_low_risk_plan())
    pipe.submit_for_approval(_high_risk_plan())
    pipe.clear()
    assert pipe.list_pending() == []
    assert pipe.stats()["total"] == 0


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    pipe = get_approval_pipeline()
    r1 = pipe.submit_for_approval(_low_risk_plan())
    r2 = pipe.submit_for_approval(_high_risk_plan())
    pipe.approve(r1)
    stats = pipe.stats()
    assert "total" in stats
    assert stats["total"] == 2
    assert stats["by_status"].get("pending", 0) == 1
    assert stats["by_status"].get("approved", 0) == 1


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_approval_pipeline()
    b = get_approval_pipeline()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_approval_pipeline()
    reset_approval_pipeline_for_tests()
    b = get_approval_pipeline()
    assert a is not b
