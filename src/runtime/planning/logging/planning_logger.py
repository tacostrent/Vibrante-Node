"""
Planning Logger (Tier 7 — Scene Planning Runtime)
==================================================
Lightweight structured log for the scene planning pipeline.

Records planning events as typed log entries. The log is in-memory only;
it can be drained for debugging or ignored in production.

Public API:
    PlanLogEntry
    PlanningLogger
        .log(event_type, message, data=None)
        .get_log() -> List[PlanLogEntry]
        .clear()
        .stats() -> dict
    get_planning_logger() -> PlanningLogger   (singleton)
    reset_planning_logger_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_VALID_EVENT_TYPES = frozenset({
    "planning_started",
    "planning_completed",
    "planning_failed",
    "zone_planned",
    "composition_planned",
    "camera_planned",
    "asset_query_generated",
    "plan_validated",
    "recommendation_applied",
    "serialization",
    "warning",
    "error",
})


@dataclass
class PlanLogEntry:
    event_type: str
    message:    str
    data:       Dict[str, Any]  = field(default_factory=dict)
    timestamp:  float           = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "message":    self.message,
            "data":       dict(self.data),
            "timestamp":  self.timestamp,
        }


class PlanningLogger:
    """In-memory planning event logger."""

    def __init__(self) -> None:
        self._lock:  threading.Lock    = threading.Lock()
        self._log:   List[PlanLogEntry] = []

    def log(
        self,
        event_type: str,
        message:    str,
        data:       Optional[Dict[str, Any]] = None,
    ) -> None:
        et = event_type if event_type in _VALID_EVENT_TYPES else "warning"
        entry = PlanLogEntry(event_type=et, message=message, data=dict(data or {}))
        with self._lock:
            self._log.append(entry)

    def get_log(self) -> List[PlanLogEntry]:
        with self._lock:
            return list(self._log)

    def clear(self) -> None:
        with self._lock:
            self._log.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_type: Dict[str, int] = {}
            for entry in self._log:
                by_type[entry.event_type] = by_type.get(entry.event_type, 0) + 1
            return {"total": len(self._log), "by_type": by_type}


_INSTANCE: Optional[PlanningLogger] = None
_INSTANCE_LOCK = threading.Lock()


def get_planning_logger() -> PlanningLogger:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = PlanningLogger()
    return _INSTANCE


def reset_planning_logger_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
