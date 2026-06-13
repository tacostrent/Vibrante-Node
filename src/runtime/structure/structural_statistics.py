"""
Structural Statistics (Tier 10.3 — Structural Asset Classification)
====================================================================
In-memory statistics for structural classification operations.
Capped at 2000 records.

Public API:
    StructuralStatRecord
    StructuralStatistics
    get_structural_statistics()
    reset_structural_statistics_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


@dataclass
class StructuralStatRecord:
    """One classification event record."""

    asset_id:              str   = ""
    asset_name:            str   = ""
    structural_role:       str   = "structural_unknown"
    confidence:            float = 0.0
    classification_source: str   = "none"
    is_structural:         bool  = False
    environment:           str   = ""
    overall_score:         float = 0.0   # from review, if reviewed
    production_ready:      bool  = False
    recorded_at:           float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":              self.asset_id,
            "asset_name":            self.asset_name,
            "structural_role":       self.structural_role,
            "confidence":            self.confidence,
            "classification_source": self.classification_source,
            "is_structural":         self.is_structural,
            "environment":           self.environment,
            "overall_score":         self.overall_score,
            "production_ready":      self.production_ready,
            "recorded_at":           self.recorded_at,
        }


class StructuralStatistics:
    """In-memory classification statistics.  Thread-safe."""

    def __init__(self) -> None:
        self._records: List[StructuralStatRecord] = []
        self._lock = threading.Lock()

    def record_classification(
        self,
        asset_id:              str,
        asset_name:            str   = "",
        structural_role:       str   = "structural_unknown",
        confidence:            float = 0.0,
        classification_source: str   = "none",
        is_structural:         bool  = False,
        environment:           str   = "",
    ) -> None:
        """Record a classification event.  Never raises."""
        try:
            rec = StructuralStatRecord(
                asset_id              = asset_id,
                asset_name            = asset_name,
                structural_role       = structural_role,
                confidence            = confidence,
                classification_source = classification_source,
                is_structural         = is_structural,
                environment           = environment,
            )
            with self._lock:
                if len(self._records) >= _MAX_RECORDS:
                    self._records.pop(0)
                self._records.append(rec)
        except Exception:
            pass

    def record_review(
        self,
        asset_id:        str,
        overall_score:   float,
        production_ready: bool,
    ) -> None:
        """Update the most recent record for asset_id with review results."""
        try:
            with self._lock:
                for rec in reversed(self._records):
                    if rec.asset_id == asset_id:
                        rec.overall_score    = overall_score
                        rec.production_ready = production_ready
                        break
        except Exception:
            pass

    def record_count(self) -> int:
        with self._lock:
            return len(self._records)

    def role_distribution(self) -> Dict[str, int]:
        dist: Dict[str, int] = {}
        with self._lock:
            for rec in self._records:
                dist[rec.structural_role] = dist.get(rec.structural_role, 0) + 1
        return dist

    def source_distribution(self) -> Dict[str, int]:
        dist: Dict[str, int] = {}
        with self._lock:
            for rec in self._records:
                dist[rec.classification_source] = dist.get(rec.classification_source, 0) + 1
        return dist

    def confidence_distribution(self) -> Dict[str, int]:
        """Bucket confidence into 0.0–0.5 / 0.5–0.7 / 0.7–0.85 / 0.85–1.0."""
        buckets = {"low_0_50": 0, "medium_50_70": 0, "good_70_85": 0, "high_85_100": 0}
        with self._lock:
            for rec in self._records:
                c = rec.confidence
                if c < 0.50:
                    buckets["low_0_50"] += 1
                elif c < 0.70:
                    buckets["medium_50_70"] += 1
                elif c < 0.85:
                    buckets["good_70_85"] += 1
                else:
                    buckets["high_85_100"] += 1
        return buckets

    def structural_fraction(self) -> float:
        """Fraction of classified assets that are structural."""
        with self._lock:
            if not self._records:
                return 0.0
            return sum(1 for r in self._records if r.is_structural) / len(self._records)

    def environment_distribution(self) -> Dict[str, int]:
        dist: Dict[str, int] = {}
        with self._lock:
            for rec in self._records:
                if rec.environment:
                    dist[rec.environment] = dist.get(rec.environment, 0) + 1
        return dist

    def average_confidence(self) -> float:
        with self._lock:
            if not self._records:
                return 0.0
            return sum(r.confidence for r in self._records) / len(self._records)

    def misclassification_estimate(self) -> float:
        """Fraction of records with structural_unknown (proxy for misclassification)."""
        with self._lock:
            if not self._records:
                return 0.0
            unknown = sum(1 for r in self._records if r.structural_role == "structural_unknown")
            return unknown / len(self._records)

    def top_roles(self, n: int = 5) -> List[Dict[str, Any]]:
        dist = self.role_distribution()
        top  = sorted(dist.items(), key=lambda x: x[1], reverse=True)[:n]
        return [{"structural_role": k, "count": v} for k, v in top]

    def summary(self) -> Dict[str, Any]:
        return {
            "total_records":           self.record_count(),
            "role_distribution":       self.role_distribution(),
            "source_distribution":     self.source_distribution(),
            "confidence_distribution": self.confidence_distribution(),
            "structural_fraction":     self.structural_fraction(),
            "average_confidence":      self.average_confidence(),
            "misclassification_estimate": self.misclassification_estimate(),
        }

    def all_records(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._records]


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_INSTANCE: Optional[StructuralStatistics] = None
_LOCK = threading.Lock()


def get_structural_statistics() -> StructuralStatistics:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = StructuralStatistics()
        return _INSTANCE


def reset_structural_statistics_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
