"""
layout_statistics.py — §46 Semantic Furniture Layout Engine
===========================================================
In-memory statistics for layout operations (capped at 2000 records).

Public API:
    LayoutStatRecord
    LayoutStatistics
    get_layout_statistics()
    reset_layout_statistics_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


@dataclass
class LayoutStatRecord:
    environment:              str
    cluster_count:            int
    relationship_count:       int
    surface_placement_count:  int
    wall_attachment_count:    int
    overall_score:            float
    grade:                    str
    production_ready:         bool
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "environment":             self.environment,
            "cluster_count":           self.cluster_count,
            "relationship_count":      self.relationship_count,
            "surface_placement_count": self.surface_placement_count,
            "wall_attachment_count":   self.wall_attachment_count,
            "overall_score":           round(self.overall_score, 4),
            "grade":                   self.grade,
            "production_ready":        self.production_ready,
            "timestamp":               self.timestamp,
        }


class LayoutStatistics:
    """In-memory stats for layout operations (latest _MAX_RECORDS retained)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: List[LayoutStatRecord] = []

    def record(
        self,
        environment: str,
        cluster_count: int = 0,
        relationship_count: int = 0,
        surface_placement_count: int = 0,
        wall_attachment_count: int = 0,
        overall_score: float = 0.0,
        grade: str = "F",
        production_ready: bool = False,
    ) -> None:
        with self._lock:
            self._records.append(LayoutStatRecord(
                environment=environment,
                cluster_count=cluster_count,
                relationship_count=relationship_count,
                surface_placement_count=surface_placement_count,
                wall_attachment_count=wall_attachment_count,
                overall_score=overall_score,
                grade=grade,
                production_ready=production_ready,
            ))
            if len(self._records) > _MAX_RECORDS:
                self._records = self._records[-_MAX_RECORDS:]

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            if not self._records:
                return {"total": 0, "production_ready_rate": 0.0, "mean_score": 0.0}
            total = len(self._records)
            ready = sum(1 for r in self._records if r.production_ready)
            mean  = sum(r.overall_score for r in self._records) / total
            return {
                "total":                 total,
                "production_ready_rate": round(ready / total, 4),
                "mean_score":            round(mean, 4),
            }

    def all_records(self) -> List[LayoutStatRecord]:
        with self._lock:
            return list(self._records)

    def total(self) -> int:
        with self._lock:
            return len(self._records)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[LayoutStatistics] = None
_lock = threading.Lock()


def get_layout_statistics() -> LayoutStatistics:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = LayoutStatistics()
    return _instance


def reset_layout_statistics_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
