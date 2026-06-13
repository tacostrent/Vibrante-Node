"""
reality_statistics.py — §54 Reality Intelligence (Tier 15.0+)
==============================================================
In-memory statistics for Reality Intelligence evaluations, capped at 2000
records (same convention as every other tier).

Public API:
    RealityStatRecord
    RealityStatistics
    get_reality_statistics()
    reset_reality_statistics_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


@dataclass
class RealityStatRecord:
    environment:      str
    production_ready: bool
    score:            float
    grade:            str
    correction_count: int
    recorded_at:      float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":      self.environment,
            "production_ready": self.production_ready,
            "score":            round(self.score, 4),
            "grade":            self.grade,
            "correction_count": self.correction_count,
            "recorded_at":      self.recorded_at,
        }


class RealityStatistics:
    """Rolling record of §54 evaluations. Thread-safe, never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: List[RealityStatRecord] = []

    def record(self, environment: str = "", production_ready: bool = False,
               score: float = 0.0, grade: str = "F",
               correction_count: int = 0) -> None:
        try:
            with self._lock:
                self._records.append(RealityStatRecord(
                    environment=str(environment or ""),
                    production_ready=bool(production_ready),
                    score=float(score),
                    grade=str(grade or "F"),
                    correction_count=int(correction_count),
                ))
                if len(self._records) > _MAX_RECORDS:
                    self._records = self._records[-_MAX_RECORDS:]
        except Exception:
            pass

    def evaluation_count(self) -> int:
        with self._lock:
            return len(self._records)

    def production_ready_rate(self) -> float:
        with self._lock:
            if not self._records:
                return 0.0
            ready = sum(1 for r in self._records if r.production_ready)
            return ready / len(self._records)

    def average_score(self) -> float:
        with self._lock:
            if not self._records:
                return 0.0
            return sum(r.score for r in self._records) / len(self._records)

    def correction_total(self) -> int:
        with self._lock:
            return sum(r.correction_count for r in self._records)

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self._records)
        if not records:
            return {
                "evaluation_count": 0,
                "production_ready_rate": 0.0,
                "average_score": 0.0,
                "correction_total": 0,
                "by_environment": {},
            }
        by_env: Dict[str, Dict[str, Any]] = {}
        for r in records:
            env = r.environment or "(unknown)"
            bucket = by_env.setdefault(env, {"count": 0, "ready": 0, "score_sum": 0.0})
            bucket["count"] += 1
            bucket["ready"] += 1 if r.production_ready else 0
            bucket["score_sum"] += r.score
        return {
            "evaluation_count": len(records),
            "production_ready_rate": round(
                sum(1 for r in records if r.production_ready) / len(records), 4
            ),
            "average_score": round(sum(r.score for r in records) / len(records), 4),
            "correction_total": sum(r.correction_count for r in records),
            "by_environment": {
                env: {
                    "count": b["count"],
                    "ready": b["ready"],
                    "average_score": round(b["score_sum"] / b["count"], 4),
                }
                for env, b in sorted(by_env.items())
            },
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RealityStatistics] = None
_lock = threading.Lock()


def get_reality_statistics() -> RealityStatistics:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RealityStatistics()
    return _instance


def reset_reality_statistics_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
