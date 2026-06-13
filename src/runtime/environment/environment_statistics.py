"""
Environment Statistics (§44 — Structural Environment Assembly)
=============================================================
In-memory statistics tracking for environment construction operations.
Capped at 2000 records. Thread-safe.

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Never raises.
  3. Singleton pattern.
  4. Thread-safe.

Public API:
    EnvironmentStatRecord
    EnvironmentStatistics
    get_environment_statistics()
    reset_environment_statistics_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EnvironmentStatRecord:
    """A single environment pipeline operation record."""

    environment_name: str = ""
    operation: str = ""        # build_structure / build_zones / build_anchors / review
    success: bool = False
    score: float = 0.0
    grade: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_name": self.environment_name,
            "operation":        self.operation,
            "success":          self.success,
            "score":            self.score,
            "grade":            self.grade,
            "timestamp":        self.timestamp,
        }


class EnvironmentStatistics:
    """Track environment construction statistics."""

    MAX_RECORDS = 2000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: List[EnvironmentStatRecord] = []

    def record(
        self,
        environment_name: str,
        operation: str,
        success: bool,
        score: float = 0.0,
        grade: str = "",
    ) -> None:
        """Record a pipeline operation."""
        with self._lock:
            rec = EnvironmentStatRecord(
                environment_name = environment_name,
                operation        = operation,
                success          = success,
                score            = score,
                grade            = grade,
            )
            self._records.append(rec)
            if len(self._records) > self.MAX_RECORDS:
                self._records = self._records[-self.MAX_RECORDS:]

    def usage_count(self, environment_name: str) -> int:
        """Return total operation count for the environment."""
        with self._lock:
            return sum(1 for r in self._records if r.environment_name == environment_name)

    def success_rate(self, environment_name: str) -> float:
        """Return success rate (0.0–1.0) for the environment."""
        with self._lock:
            recs = [r for r in self._records if r.environment_name == environment_name]
            if not recs:
                return 0.0
            return sum(1 for r in recs if r.success) / len(recs)

    def average_score(self, environment_name: str) -> float:
        """Return average review score for the environment."""
        with self._lock:
            recs = [r for r in self._records
                    if r.environment_name == environment_name and r.score > 0.0]
            if not recs:
                return 0.0
            return sum(r.score for r in recs) / len(recs)

    def top_environments(self, n: int = 5) -> List[str]:
        """Return the top-n environments by usage count."""
        with self._lock:
            counts: Dict[str, int] = {}
            for r in self._records:
                counts[r.environment_name] = counts.get(r.environment_name, 0) + 1
            return sorted(counts, key=lambda k: counts[k], reverse=True)[:n]

    def summary(self) -> Dict[str, Any]:
        """Return overall statistics summary."""
        with self._lock:
            total = len(self._records)
            success_total = sum(1 for r in self._records if r.success)
            scored = [r.score for r in self._records if r.score > 0.0]
            return {
                "total_records":  total,
                "success_count":  success_total,
                "success_rate":   round(success_total / total, 4) if total else 0.0,
                "average_score":  round(sum(scored) / len(scored), 4) if scored else 0.0,
                "unique_environments": len({r.environment_name for r in self._records}),
            }

    def reset(self) -> None:
        """Clear all records."""
        with self._lock:
            self._records.clear()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentStatistics] = None
_LOCK = threading.Lock()


def get_environment_statistics() -> EnvironmentStatistics:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = EnvironmentStatistics()
        return _INSTANCE


def reset_environment_statistics_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
