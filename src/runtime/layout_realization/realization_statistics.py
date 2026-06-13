"""
realization_statistics.py — §47 Layout Realization & Scene Constraint Solver
=============================================================================
In-memory statistics for layout realization runs. Capped at 2000 records.

Public API:
    RealizationRecord
    RealizationStatistics
    get_realization_statistics()
    reset_realization_statistics_for_tests()
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


@dataclass
class RealizationRecord:
    environment:          str
    asset_count:          int
    collision_count:      int
    constraint_violations: int
    overall_score:        float
    grade:                str
    production_ready:     bool
    realized_at:          float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":           self.environment,
            "asset_count":           self.asset_count,
            "collision_count":       self.collision_count,
            "constraint_violations": self.constraint_violations,
            "overall_score":         round(self.overall_score, 4),
            "grade":                 self.grade,
            "production_ready":      self.production_ready,
            "realized_at":           self.realized_at,
        }


class RealizationStatistics:
    """Rolling statistics for layout realization runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: List[RealizationRecord] = []

    def record(
        self,
        environment: str,
        asset_count: int,
        collision_count: int,
        constraint_violations: int,
        overall_score: float,
        grade: str,
        production_ready: bool,
    ) -> None:
        with self._lock:
            self._records.append(RealizationRecord(
                environment=environment,
                asset_count=asset_count,
                collision_count=collision_count,
                constraint_violations=constraint_violations,
                overall_score=overall_score,
                grade=grade,
                production_ready=production_ready,
            ))
            if len(self._records) > _MAX_RECORDS:
                self._records = self._records[-_MAX_RECORDS:]

    def total(self) -> int:
        with self._lock:
            return len(self._records)

    def production_ready_rate(self) -> float:
        with self._lock:
            if not self._records:
                return 0.0
            return sum(1 for r in self._records if r.production_ready) / len(self._records)

    def average_score(self) -> float:
        with self._lock:
            if not self._records:
                return 0.0
            return sum(r.overall_score for r in self._records) / len(self._records)

    def average_collisions(self) -> float:
        with self._lock:
            if not self._records:
                return 0.0
            return sum(r.collision_count for r in self._records) / len(self._records)

    def recent(self, n: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._records[-n:]]

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            n = len(self._records)
            return {
                "total":                 n,
                "production_ready_rate": round(self.production_ready_rate(), 4),
                "average_score":         round(self.average_score(), 4),
                "average_collisions":    round(self.average_collisions(), 4),
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RealizationStatistics] = None
_lock = threading.Lock()


def get_realization_statistics() -> RealizationStatistics:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RealizationStatistics()
    return _instance


def reset_realization_statistics_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
