"""
ShellStatistics — Tier 10.4
=============================
In-memory rolling statistics for environment shell construction runs.
Capped at 2000 records. Thread-safe. Never raises.

Public API:
    ShellStatRecord
    ShellStatistics
    get_shell_statistics()
    reset_shell_statistics_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


@dataclass
class ShellStatRecord:
    environment:       str   = ""
    floor_exists:      bool  = False
    wall_count:        int   = 0
    ceiling_exists:    bool  = False
    environment_ready: bool  = False
    overall_score:     float = 0.0
    grade:             str   = "F"
    production_ready:  bool  = False
    timestamp:         float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":       self.environment,
            "floor_exists":      self.floor_exists,
            "wall_count":        self.wall_count,
            "ceiling_exists":    self.ceiling_exists,
            "environment_ready": self.environment_ready,
            "overall_score":     self.overall_score,
            "grade":             self.grade,
            "production_ready":  self.production_ready,
            "timestamp":         self.timestamp,
        }


class ShellStatistics:

    def __init__(self) -> None:
        self._lock    = threading.Lock()
        self._records: List[ShellStatRecord] = []

    def record(
        self,
        environment:       str,
        floor_exists:      bool  = False,
        wall_count:        int   = 0,
        ceiling_exists:    bool  = False,
        environment_ready: bool  = False,
        overall_score:     float = 0.0,
        grade:             str   = "F",
        production_ready:  bool  = False,
    ) -> None:
        """Add a record. Evicts oldest when over cap. Never raises."""
        try:
            rec = ShellStatRecord(
                environment       = environment,
                floor_exists      = floor_exists,
                wall_count        = wall_count,
                ceiling_exists    = ceiling_exists,
                environment_ready = environment_ready,
                overall_score     = overall_score,
                grade             = grade,
                production_ready  = production_ready,
                timestamp         = time.time(),
            )
            with self._lock:
                self._records.append(rec)
                if len(self._records) > _MAX_RECORDS:
                    self._records = self._records[-_MAX_RECORDS:]
        except Exception:
            pass

    def summary(self) -> Dict[str, Any]:
        """Return aggregate statistics. Never raises."""
        try:
            with self._lock:
                recs = list(self._records)
            if not recs:
                return {"total": 0}
            total          = len(recs)
            ready_count    = sum(1 for r in recs if r.environment_ready)
            prod_ready     = sum(1 for r in recs if r.production_ready)
            avg_score      = sum(r.overall_score for r in recs) / total
            grade_counts: Dict[str, int] = {}
            for r in recs:
                grade_counts[r.grade] = grade_counts.get(r.grade, 0) + 1
            return {
                "total":            total,
                "environment_ready_count": ready_count,
                "production_ready_count":  prod_ready,
                "environment_ready_rate":  round(ready_count / total, 3),
                "production_ready_rate":   round(prod_ready / total, 3),
                "avg_overall_score":       round(avg_score, 3),
                "grade_counts":            grade_counts,
            }
        except Exception:
            return {"total": 0}

    def recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return the last n records. Never raises."""
        try:
            with self._lock:
                recs = self._records[-n:]
            return [r.to_dict() for r in reversed(recs)]
        except Exception:
            return []


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[ShellStatistics] = None
_LOCK = threading.Lock()


def get_shell_statistics() -> ShellStatistics:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = ShellStatistics()
    return _INSTANCE


def reset_shell_statistics_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
