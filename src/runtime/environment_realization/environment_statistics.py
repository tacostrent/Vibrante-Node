"""
environment_statistics.py — §49 Structural Environment Realization
===================================================================
Rolling in-memory statistics for environment realization runs.
Capped at 2000 records.

Public API:
    EnvRealizationRecord
    EnvRealizationStatistics
    get_env_realization_statistics()
    reset_env_realization_statistics_for_tests()
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


@dataclass
class EnvRealizationRecord:
    environment:      str
    wall_count:       int
    floor_count:      int
    ceiling_count:    int
    door_count:       int
    beam_count:       int
    overall_score:    float
    grade:            str
    production_ready: bool
    realized_at:      float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":      self.environment,
            "wall_count":       self.wall_count,
            "floor_count":      self.floor_count,
            "ceiling_count":    self.ceiling_count,
            "door_count":       self.door_count,
            "beam_count":       self.beam_count,
            "overall_score":    round(self.overall_score, 4),
            "grade":            self.grade,
            "production_ready": self.production_ready,
            "realized_at":      self.realized_at,
        }


class EnvRealizationStatistics:
    """Rolling statistics for environment realization runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: List[EnvRealizationRecord] = []

    def record(
        self,
        environment: str,
        wall_count: int,
        floor_count: int,
        ceiling_count: int,
        door_count: int,
        beam_count: int,
        overall_score: float,
        grade: str,
        production_ready: bool,
    ) -> None:
        with self._lock:
            self._records.append(EnvRealizationRecord(
                environment=environment,
                wall_count=wall_count,
                floor_count=floor_count,
                ceiling_count=ceiling_count,
                door_count=door_count,
                beam_count=beam_count,
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

    def recent(self, n: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._records[-n:]]

    def summary(self) -> Dict[str, Any]:
        return {
            "total":                 self.total(),
            "production_ready_rate": round(self.production_ready_rate(), 4),
            "average_score":         round(self.average_score(), 4),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[EnvRealizationStatistics] = None
_lock = threading.Lock()


def get_env_realization_statistics() -> EnvRealizationStatistics:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = EnvRealizationStatistics()
    return _instance


def reset_env_realization_statistics_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
