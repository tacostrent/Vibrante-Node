"""
Human Approval Pipeline (Tier 3)
===================================
Approval gate between AI planning and execution. Ensures high-risk,
destructive, or large plans receive explicit human authorization before
running.

State machine per approval request:
    pending → approved → (caller executes)
    pending → rejected → (caller aborts)
    pending → deferred → (caller skips until re-submitted)

Auto-approval: if risk_level != "high" and no destructive ops and no
approval_reasons in the plan → auto-approved immediately.

The pipeline is SYNCHRONOUS (planning decisions should not block on async).
Approvals are stored in an in-memory registry with an optional expiry.

Public API:
    get_approval_pipeline() -> ApprovalPipeline
    reset_approval_pipeline_for_tests()

    ApprovalPipeline.requires_approval(plan) -> bool
    ApprovalPipeline.submit_for_approval(plan, submitter=None) -> str   # → request_id
    ApprovalPipeline.approve(request_id, approver=None, notes="") -> bool
    ApprovalPipeline.reject(request_id, approver=None, reason="") -> bool
    ApprovalPipeline.defer(request_id, approver=None, notes="") -> bool
    ApprovalPipeline.get_status(request_id) -> dict | None
    ApprovalPipeline.auto_approve(plan) -> dict       # skip pipeline if safe
    ApprovalPipeline.list_pending() -> list[dict]
    ApprovalPipeline.clear()
"""

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

_VALID_STATUSES = frozenset({"pending", "approved", "rejected", "deferred", "auto"})
_DESTRUCTIVE_OPS = frozenset({"delete_node"})

# After this many seconds a pending request auto-expires (0 = never)
_DEFAULT_EXPIRY_SEC = 0


def _has_destructive_ops(ops: List[Dict[str, Any]]) -> bool:
    return any(op.get("op") in _DESTRUCTIVE_OPS for op in ops)


class ApprovalPipeline:
    """Synchronous approval state machine.

    Args:
        expiry_sec: Seconds before a pending request expires (0 = never).
    """

    def __init__(self, expiry_sec: int = _DEFAULT_EXPIRY_SEC):
        self._expiry_sec = expiry_sec
        self._store:  Dict[str, Dict[str, Any]] = {}
        self._lock    = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def requires_approval(self, plan: Dict[str, Any]) -> bool:
        """Return True if the plan must go through the human approval gate."""
        if plan.get("requires_approval"):
            return True
        resource = plan.get("resource_estimate", {})
        if resource.get("risk_level") == "high":
            return True
        ops = plan.get("operations", [])
        if _has_destructive_ops(ops):
            return True
        return False

    def submit_for_approval(
        self,
        plan:      Dict[str, Any],
        submitter: Optional[str] = None,
    ) -> str:
        """Create a pending approval request for the plan.

        Returns the request_id (uuid4 string).
        """
        request_id = str(uuid.uuid4())
        now = time.time()
        record = {
            "request_id":       request_id,
            "status":           "pending",
            "plan_id":          plan.get("plan_id", ""),
            "intent":           plan.get("intent", ""),
            "op_count":         plan.get("op_count", len(plan.get("operations", []))),
            "risk_level":       plan.get("resource_estimate", {}).get("risk_level", "low"),
            "approval_reasons": list(plan.get("approval_reasons", [])),
            "submitter":        submitter or "system",
            "approver":         None,
            "notes":            "",
            "submitted_at":     now,
            "decided_at":       None,
            "expires_at":       now + self._expiry_sec if self._expiry_sec > 0 else None,
        }
        with self._lock:
            self._store[request_id] = record
        return request_id

    def auto_approve(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Return an auto-approved decision dict for safe plans (bypass gate).

        The caller is responsible for checking requires_approval() first.
        Only call this if requires_approval() returns False.
        """
        return {
            "request_id": str(uuid.uuid4()),
            "status":     "auto",
            "plan_id":    plan.get("plan_id", ""),
            "intent":     plan.get("intent", ""),
            "notes":      "Auto-approved: risk is below approval threshold.",
            "decided_at": time.time(),
        }

    def approve(
        self,
        request_id: str,
        approver:   Optional[str] = None,
        notes:      str = "",
    ) -> bool:
        """Approve a pending request. Returns True if state changed."""
        return self._transition(request_id, "approved", approver, notes)

    def reject(
        self,
        request_id: str,
        approver:   Optional[str] = None,
        reason:     str = "",
    ) -> bool:
        """Reject a pending request. Returns True if state changed."""
        return self._transition(request_id, "rejected", approver, reason)

    def defer(
        self,
        request_id: str,
        approver:   Optional[str] = None,
        notes:      str = "",
    ) -> bool:
        """Defer a pending request. Returns True if state changed."""
        return self._transition(request_id, "deferred", approver, notes)

    def get_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Return the approval record, or None if not found / expired."""
        with self._lock:
            record = self._store.get(request_id)
            if record is None:
                return None
            if self._is_expired(record):
                record = dict(record)
                record["status"] = "expired"
                return record
            return dict(record)

    def list_pending(self) -> List[Dict[str, Any]]:
        """Return all non-expired pending requests, oldest first."""
        now = time.time()
        with self._lock:
            result = [
                dict(r) for r in self._store.values()
                if r["status"] == "pending"
                and (r.get("expires_at") is None or r["expires_at"] > now)
            ]
        result.sort(key=lambda r: r["submitted_at"])
        return result

    def clear(self) -> None:
        """Remove all records (test helper)."""
        with self._lock:
            self._store.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            counts: Dict[str, int] = {}
            for r in self._store.values():
                s = r["status"]
                counts[s] = counts.get(s, 0) + 1
            return {"total": len(self._store), "by_status": counts}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(
        self,
        request_id: str,
        new_status:  str,
        approver:    Optional[str],
        notes:       str,
    ) -> bool:
        with self._lock:
            record = self._store.get(request_id)
            if record is None:
                return False
            if record["status"] != "pending":
                return False
            if self._is_expired(record):
                return False
            record["status"]     = new_status
            record["approver"]   = approver or "system"
            record["notes"]      = notes
            record["decided_at"] = time.time()
        return True

    @staticmethod
    def _is_expired(record: Dict[str, Any]) -> bool:
        exp = record.get("expires_at")
        return exp is not None and time.time() > exp


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_PIPELINE: Optional[ApprovalPipeline] = None
_LOCK = threading.Lock()


def get_approval_pipeline() -> ApprovalPipeline:
    global _PIPELINE
    with _LOCK:
        if _PIPELINE is None:
            _PIPELINE = ApprovalPipeline()
        return _PIPELINE


def reset_approval_pipeline_for_tests() -> None:
    global _PIPELINE
    with _LOCK:
        _PIPELINE = None
