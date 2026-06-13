"""
validation_statistics.py — §53 Scene Reality Validation (Tier 14.3)
====================================================================
Rolling in-memory statistics for scene reality validation runs.
Capped at 2000 records.

Public API:
    ValidationRecord
    ValidationStatistics
    get_validation_statistics()
    reset_validation_statistics_for_tests()
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


@dataclass
class ValidationRecord:
    environment:           str
    asset_count:           int
    support_violations:    int
    occupancy_violations:  int
    relationship_failures: int
    orphan_count:          int
    plausibility_score:    float
    semantic_score:        float
    geometry_valid:        bool
    semantic_valid:        bool
    plausibility_valid:    bool
    production_ready:      bool
    validated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":           self.environment,
            "asset_count":           self.asset_count,
            "support_violations":    self.support_violations,
            "occupancy_violations":  self.occupancy_violations,
            "relationship_failures": self.relationship_failures,
            "orphan_count":          self.orphan_count,
            "plausibility_score":    round(self.plausibility_score, 4),
            "semantic_score":        round(self.semantic_score, 4),
            "geometry_valid":        self.geometry_valid,
            "semantic_valid":        self.semantic_valid,
            "plausibility_valid":    self.plausibility_valid,
            "production_ready":      self.production_ready,
            "validated_at":          self.validated_at,
        }


class ValidationStatistics:
    """Rolling statistics for scene reality validation runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: List[ValidationRecord] = []

    def record(
        self,
        environment: str,
        asset_count: int,
        support_violations: int,
        occupancy_violations: int,
        relationship_failures: int,
        orphan_count: int,
        plausibility_score: float,
        semantic_score: float,
        geometry_valid: bool,
        semantic_valid: bool,
        plausibility_valid: bool,
        production_ready: bool,
    ) -> None:
        with self._lock:
            if len(self._records) >= _MAX_RECORDS:
                self._records.pop(0)
            self._records.append(ValidationRecord(
                environment=environment,
                asset_count=asset_count,
                support_violations=support_violations,
                occupancy_violations=occupancy_violations,
                relationship_failures=relationship_failures,
                orphan_count=orphan_count,
                plausibility_score=plausibility_score,
                semantic_score=semantic_score,
                geometry_valid=geometry_valid,
                semantic_valid=semantic_valid,
                plausibility_valid=plausibility_valid,
                production_ready=production_ready,
            ))

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            if not self._records:
                return {"total_runs": 0}
            total  = len(self._records)
            ready  = sum(1 for r in self._records if r.production_ready)
            geo_ok = sum(1 for r in self._records if r.geometry_valid)
            sem_ok = sum(1 for r in self._records if r.semantic_valid)
            pla_ok = sum(1 for r in self._records if r.plausibility_valid)
            avg_p  = sum(r.plausibility_score for r in self._records) / total
            return {
                "total_runs":              total,
                "production_ready_pct":    round(ready  / total * 100, 1),
                "geometry_valid_pct":      round(geo_ok / total * 100, 1),
                "semantic_valid_pct":      round(sem_ok / total * 100, 1),
                "plausibility_valid_pct":  round(pla_ok / total * 100, 1),
                "avg_plausibility_score":  round(avg_p, 4),
            }

    def all_records(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._records]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[ValidationStatistics] = None
_lock = threading.Lock()


def get_validation_statistics() -> ValidationStatistics:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ValidationStatistics()
    return _instance


def reset_validation_statistics_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
