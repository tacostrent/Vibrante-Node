"""
Planning Memory (Tier 3)
========================
Structured in-memory + optional JSONL-backed storage for AI planning events.

NOT a chat log. Stores structured runtime metadata only:
  - parsed_intent   — output of intent_parser
  - plan_generated  — output of ai_planner
  - plan_validated  — output of plan_validator
  - plan_approved   — approval pipeline decision
  - plan_rejected   — rejection with reason
  - execution_result — outcome from semantic_execution
  - review_result   — output of execution_review

This enables:
  - planning analytics ("how often does pyro intent succeed?")
  - replayability ("replay this plan_id")
  - explainability ("why was this approved?")
  - debugging ("what happened before this failure?")

Public API:
    get_planning_memory() -> PlanningMemory
    reset_planning_memory_for_tests()

    PlanningMemory.record(event_type, data) -> str  # returns event_id
    PlanningMemory.get_event(event_id) -> dict | None
    PlanningMemory.query(event_type=None, intent=None, limit=50) -> list[dict]
    PlanningMemory.stats() -> dict
    PlanningMemory.clear()
"""

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

# Valid event types
PLANNING_EVENT_TYPES = frozenset({
    "intent_parsed",
    "plan_generated",
    "plan_validated",
    "plan_approved",
    "plan_rejected",
    "plan_deferred",
    "execution_result",
    "review_result",
})

_DEFAULT_MAX_RECORDS = 500
_DEFAULT_PATH_ENV    = "VIBRANTE_PLANNING_MEMORY_PATH"


class PlanningMemory:
    """Structured planning event store.

    Args:
        path:        Path to JSONL file for persistence, or None for in-memory only.
        max_records: Cap on in-memory records (oldest pruned first).
    """

    def __init__(
        self,
        path:        Optional[str] = None,
        max_records: int = _DEFAULT_MAX_RECORDS,
    ):
        self._path        = path
        self._max_records = max_records
        self._memory:     List[Dict[str, Any]] = []
        self._lock        = threading.Lock()
        self._write_count = 0
        self._loaded      = False

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record(self, event_type: str, data: Dict[str, Any]) -> str:
        """Synchronously record a planning event.

        Args:
            event_type: One of PLANNING_EVENT_TYPES.
            data:       Arbitrary dict of planning metadata.

        Returns:
            event_id (uuid4 string)
        """
        if event_type not in PLANNING_EVENT_TYPES:
            raise ValueError(f"Unknown planning event type: {event_type!r}")

        event = dict(data)
        if "event_id" not in event:
            event["event_id"] = str(uuid.uuid4())
        event["event_type"] = event_type
        if "timestamp" not in event:
            event["timestamp"] = time.time()

        event_id = event["event_id"]

        with self._lock:
            self._memory.append(event)
            # Prune if over cap
            if len(self._memory) > self._max_records * 2:
                self._memory = self._memory[-self._max_records:]
            self._write_count += 1

        # Disk write (non-blocking, best-effort)
        if self._path:
            try:
                self._append_to_disk(event)
            except Exception:
                pass

        return event_id

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Return a single event by id, or None."""
        with self._lock:
            for e in reversed(self._memory):
                if e.get("event_id") == event_id:
                    return dict(e)
        return None

    def query(
        self,
        event_type: Optional[str] = None,
        intent:     Optional[str] = None,
        limit:      int           = 50,
    ) -> List[Dict[str, Any]]:
        """Return events matching filters, newest first.

        Args:
            event_type: Filter by event type (or None for all).
            intent:     Filter by intent string in data (or None for all).
            limit:      Max records returned.
        """
        with self._lock:
            events = list(reversed(self._memory))

        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]
        if intent:
            events = [
                e for e in events
                if e.get("intent") == intent
                or e.get("data", {}).get("intent") == intent
            ]

        return [dict(e) for e in events[:limit]]

    def get_recent_plans(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent plan_generated events."""
        return self.query(event_type="plan_generated", limit=limit)

    def get_execution_results(self, intent: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Return execution_result events, optionally filtered by intent."""
        return self.query(event_type="execution_result", intent=intent, limit=limit)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._memory)
            by_type: Dict[str, int] = {}
            for e in self._memory:
                t = e.get("event_type", "unknown")
                by_type[t] = by_type.get(t, 0) + 1
            return {
                "total_events":  total,
                "write_count":   self._write_count,
                "by_type":       by_type,
                "path":          self._path,
                "max_records":   self._max_records,
            }

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all in-memory events. Does not touch disk."""
        with self._lock:
            self._memory.clear()

    # ------------------------------------------------------------------
    # Internal disk helpers
    # ------------------------------------------------------------------

    def _append_to_disk(self, event: Dict[str, Any]) -> None:
        line = json.dumps(event, default=str) + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)

    def _load_from_disk(self) -> None:
        if not self._path or not os.path.exists(self._path):
            return
        records: List[Dict[str, Any]] = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except (json.JSONDecodeError, ValueError):
                        pass
        except OSError:
            pass
        with self._lock:
            self._memory = records[-self._max_records:]
            self._loaded = True


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_MEMORY: Optional[PlanningMemory] = None
_LOCK = threading.Lock()


def get_planning_memory() -> PlanningMemory:
    global _MEMORY
    with _LOCK:
        if _MEMORY is None:
            path = os.environ.get(_DEFAULT_PATH_ENV)
            _MEMORY = PlanningMemory(path=path or None)
        return _MEMORY


def reset_planning_memory_for_tests() -> None:
    global _MEMORY
    with _LOCK:
        _MEMORY = None
