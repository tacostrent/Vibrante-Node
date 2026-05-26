"""
MCP Session Runtime
===================
Manages connected LLM session lifecycle for the Vibrante Runtime MCP server.

Each session tracks:
  - runtime context established at connection time
  - orchestration state (pending approvals, active goals)
  - execution history (structured events — never raw prompts or user text)
  - current workflow context

Sessions are:
  - inspectable  (full state readable via get_session / list_sessions)
  - replayable   (event log is append-only within the session lifetime)
  - runtime-supervised (sessions carry NO execution authority)

Public API:
    get_session_manager() -> SessionManager      (singleton)
    reset_sessions_for_tests()

    SessionManager.create_session(client_id) -> str
    SessionManager.get_session(session_id) -> dict | None
    SessionManager.update_session(session_id, **kwargs) -> bool
    SessionManager.close_session(session_id) -> bool
    SessionManager.record_session_event(session_id, event_type, data) -> bool
    SessionManager.get_session_history(session_id) -> list[dict]
    SessionManager.list_sessions() -> list[dict]
    SessionManager.stats() -> dict
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Session event types
# ---------------------------------------------------------------------------

SESSION_EVENT_TYPES: frozenset[str] = frozenset({
    "session_started",
    "runtime_context_initialized",
    "plan_generated",
    "execution_started",
    "execution_completed",
    "review_completed",
    "approval_requested",
    "approval_granted",
    "approval_rejected",
    "tool_called",
    "error",
    "session_closed",
})

# Fields that may be updated via SessionManager.update_session()
_MUTABLE_FIELDS: frozenset[str] = frozenset({
    "active_goals",
    "pending_approvals",
    "current_plan",
})


# ---------------------------------------------------------------------------
# MCPSession
# ---------------------------------------------------------------------------

class MCPSession:
    """One connected LLM session — owns its state and event log."""

    __slots__ = (
        "session_id", "client_id", "created_at", "last_activity", "closed",
        "active_goals", "pending_approvals", "current_plan",
        "_history", "_lock",
    )

    def __init__(self, session_id: str, client_id: str) -> None:
        self.session_id     = session_id
        self.client_id      = client_id
        self.created_at     = time.time()
        self.last_activity  = time.time()
        self.closed         = False

        self.active_goals:     List[str]          = []
        self.pending_approvals: Dict[str, Any]    = {}
        self.current_plan:     Optional[Dict[str, Any]] = None

        self._history: List[Dict[str, Any]] = []
        self._lock    = threading.Lock()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "session_id":          self.session_id,
                "client_id":           self.client_id,
                "created_at":          self.created_at,
                "last_activity":       self.last_activity,
                "closed":              self.closed,
                "active_goals":        list(self.active_goals),
                "pending_approval_ids": list(self.pending_approvals.keys()),
                "has_current_plan":    self.current_plan is not None,
                "event_count":         len(self._history),
            }

    def record_event(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Unknown event types are normalised to "error" to avoid silent drops
        if event_type not in SESSION_EVENT_TYPES:
            event_type = "error"
        with self._lock:
            self._history.append({
                "event_type": event_type,
                "timestamp":  time.time(),
                "data":       data or {},
            })
            self.last_activity = time.time()

    def get_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history)

    def update(self, **kwargs: Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if key in _MUTABLE_FIELDS:
                    setattr(self, key, value)
            self.last_activity = time.time()


# ---------------------------------------------------------------------------
# SessionManager (singleton)
# ---------------------------------------------------------------------------

class SessionManager:
    """Registry of all active MCP sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, MCPSession] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def create_session(self, client_id: str = "") -> str:
        """Create a new session and return its session_id."""
        session_id = str(uuid.uuid4())
        session    = MCPSession(
            session_id,
            client_id or f"client-{session_id[:8]}",
        )
        session.record_event("session_started", {"client_id": session.client_id})
        with self._lock:
            self._sessions[session_id] = session
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return a snapshot dict for the session, or None if not found."""
        with self._lock:
            session = self._sessions.get(session_id)
        return session.to_dict() if session is not None else None

    def _get_obj(self, session_id: str) -> Optional[MCPSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def update_session(self, sid: str, **kwargs: Any) -> bool:
        """Update mutable session fields. Returns False if session not found."""
        session = self._get_obj(sid)
        if session is None:
            return False
        session.update(**kwargs)
        return True

    def close_session(self, session_id: str) -> bool:
        """Mark the session as closed. Returns False if not found."""
        session = self._get_obj(session_id)
        if session is None:
            return False
        session.record_event("session_closed")
        with self._lock:
            session.closed = True
            session.last_activity = time.time()
        return True

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def record_session_event(
        self,
        session_id: str,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Append a structured event to the session log. Returns False if not found."""
        session = self._get_obj(session_id)
        if session is None:
            return False
        session.record_event(event_type, data)
        return True

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Return the full event log for a session."""
        session = self._get_obj(session_id)
        if session is None:
            return []
        return session.get_history()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self._lock:
            sessions = list(self._sessions.values())
        return [s.to_dict() for s in sessions]

    def active_session_count(self) -> int:
        with self._lock:
            return sum(1 for s in self._sessions.values() if not s.closed)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total  = len(self._sessions)
            active = sum(1 for s in self._sessions.values() if not s.closed)
        return {
            "total_sessions":  total,
            "active_sessions": active,
            "closed_sessions": total - active,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[SessionManager] = None
_LOCK = threading.Lock()


def get_session_manager() -> SessionManager:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = SessionManager()
        return _INSTANCE


def reset_sessions_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
