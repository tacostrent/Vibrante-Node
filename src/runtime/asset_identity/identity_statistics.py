"""
identity_statistics.py — Tier 14.4.5 Asset Identity Audit
==========================================================
In-memory rolling statistics for identity audit runs.
Capped at 2000 records.

Public API:
    IdentityStatRecord
    IdentityStatistics
    get_identity_statistics()
    reset_identity_statistics_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


_CAP = 2000


@dataclass
class IdentityStatRecord:
    """One statistics record per audit run."""
    timestamp:           float = 0.0
    total_assets:        int   = 0
    resolved_assets:     int   = 0
    opaque_assets:       int   = 0
    unclassified_assets: int   = 0
    identity_coverage:   float = 0.0
    production_ready:    bool  = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp":           self.timestamp,
            "total_assets":        self.total_assets,
            "resolved_assets":     self.resolved_assets,
            "opaque_assets":       self.opaque_assets,
            "unclassified_assets": self.unclassified_assets,
            "identity_coverage":   round(self.identity_coverage, 4),
            "production_ready":    self.production_ready,
        }


class IdentityStatistics:
    """Rolling window of identity audit statistics, capped at 2000 records."""

    def __init__(self) -> None:
        self._records: List[IdentityStatRecord] = []
        self._lock = threading.Lock()

    def record(
        self,
        total_assets:        int,
        resolved_assets:     int,
        opaque_assets:       int,
        unclassified_assets: int,
        identity_coverage:   float,
        production_ready:    bool,
    ) -> None:
        rec = IdentityStatRecord(
            timestamp           = time.time(),
            total_assets        = total_assets,
            resolved_assets     = resolved_assets,
            opaque_assets       = opaque_assets,
            unclassified_assets = unclassified_assets,
            identity_coverage   = identity_coverage,
            production_ready    = production_ready,
        )
        with self._lock:
            self._records.append(rec)
            if len(self._records) > _CAP:
                self._records = self._records[-_CAP:]

    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def pass_rate(self) -> float:
        with self._lock:
            if not self._records:
                return 0.0
            return sum(1 for r in self._records if r.production_ready) / len(self._records)

    def average_coverage(self) -> float:
        with self._lock:
            if not self._records:
                return 0.0
            return sum(r.identity_coverage for r in self._records) / len(self._records)

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            n = len(self._records)
            if n == 0:
                return {"total_runs": 0, "pass_rate": 0.0, "average_coverage": 0.0}
            return {
                "total_runs":       n,
                "pass_rate":        round(sum(1 for r in self._records if r.production_ready) / n, 4),
                "average_coverage": round(sum(r.identity_coverage for r in self._records) / n, 4),
                "total_opaque":     sum(r.opaque_assets for r in self._records),
                "total_unclassified": sum(r.unclassified_assets for r in self._records),
            }

    def recent(self, n: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._records[-n:]]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[IdentityStatistics] = None
_lock = threading.Lock()


def get_identity_statistics() -> IdentityStatistics:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = IdentityStatistics()
    return _instance


def reset_identity_statistics_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
