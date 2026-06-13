"""
Geometry Statistics (Tier 9.7 — Geometry Intelligence)
=======================================================
In-memory statistics for geometry analysis operations. Tracks analysis
counts, source distribution, scale class distribution, and quality scores.
Capped at 2000 records to bound memory usage.

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Thread-safe (lock per record append).
  3. Never raises.
  4. Singleton pattern.

Public API:
    GeometryStatRecord
    GeometryStatistics
    get_geometry_statistics()
    reset_geometry_statistics_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


@dataclass
class GeometryStatRecord:
    """One geometry analysis record."""

    asset_id:    str   = ""
    asset_name:  str   = ""
    scale_class: str   = "medium"
    role:        str   = "prop"
    source:      str   = "estimated"
    is_structural: bool = False
    is_hero:     bool  = False
    overall_score: float = 0.0   # from GeometryReviewResult (if reviewed)
    production_ready: bool = False
    surface_count: int = 0
    contact_count: int = 0
    recorded_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":        self.asset_id,
            "asset_name":      self.asset_name,
            "scale_class":     self.scale_class,
            "role":            self.role,
            "source":          self.source,
            "is_structural":   self.is_structural,
            "is_hero":         self.is_hero,
            "overall_score":   self.overall_score,
            "production_ready": self.production_ready,
            "surface_count":   self.surface_count,
            "contact_count":   self.contact_count,
            "recorded_at":     self.recorded_at,
        }


class GeometryStatistics:
    """In-memory geometry analysis statistics. Thread-safe."""

    def __init__(self) -> None:
        self._records: List[GeometryStatRecord] = []
        self._lock = threading.Lock()

    def record_analysis(
        self,
        asset_id:    str,
        asset_name:  str = "",
        scale_class: str = "medium",
        role:        str = "prop",
        source:      str = "estimated",
        is_structural: bool = False,
        is_hero:     bool = False,
        surface_count: int = 0,
        contact_count: int = 0,
    ) -> None:
        """Record a geometry analysis event. Never raises."""
        try:
            rec = GeometryStatRecord(
                asset_id    = asset_id,
                asset_name  = asset_name,
                scale_class = scale_class,
                role        = role,
                source      = source,
                is_structural = is_structural,
                is_hero     = is_hero,
                surface_count = surface_count,
                contact_count = contact_count,
            )
            with self._lock:
                if len(self._records) >= _MAX_RECORDS:
                    self._records.pop(0)
                self._records.append(rec)
        except Exception:
            pass

    def record_review(
        self,
        asset_id: str,
        overall_score: float,
        production_ready: bool,
    ) -> None:
        """Update the most recent record for asset_id with review results. Never raises."""
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

    def source_distribution(self) -> Dict[str, int]:
        """Return count by source type (explicit/format_metadata/estimated)."""
        dist: Dict[str, int] = {}
        with self._lock:
            for rec in self._records:
                dist[rec.source] = dist.get(rec.source, 0) + 1
        return dist

    def scale_class_distribution(self) -> Dict[str, int]:
        """Return count by scale class."""
        dist: Dict[str, int] = {}
        with self._lock:
            for rec in self._records:
                dist[rec.scale_class] = dist.get(rec.scale_class, 0) + 1
        return dist

    def production_ready_rate(self) -> float:
        """Fraction of reviewed assets that are production-ready."""
        with self._lock:
            reviewed = [r for r in self._records if r.overall_score > 0.0]
            if not reviewed:
                return 0.0
            return sum(1 for r in reviewed if r.production_ready) / len(reviewed)

    def average_score(self) -> float:
        with self._lock:
            scored = [r for r in self._records if r.overall_score > 0.0]
            if not scored:
                return 0.0
            return sum(r.overall_score for r in scored) / len(scored)

    def explicit_source_fraction(self) -> float:
        """Fraction of assets with explicit geometry data (not estimated)."""
        with self._lock:
            if not self._records:
                return 0.0
            explicit = sum(
                1 for r in self._records
                if r.source in ("explicit", "format_metadata")
            )
            return explicit / len(self._records)

    def top_scale_classes(self, n: int = 3) -> List[Dict[str, Any]]:
        dist = self.scale_class_distribution()
        top = sorted(dist.items(), key=lambda x: x[1], reverse=True)[:n]
        return [{"scale_class": k, "count": v} for k, v in top]

    def summary(self) -> Dict[str, Any]:
        return {
            "total_records":          self.record_count(),
            "source_distribution":    self.source_distribution(),
            "scale_class_distribution": self.scale_class_distribution(),
            "production_ready_rate":  self.production_ready_rate(),
            "average_score":          self.average_score(),
            "explicit_source_fraction": self.explicit_source_fraction(),
        }

    def all_records(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._records]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[GeometryStatistics] = None
_LOCK = threading.Lock()


def get_geometry_statistics() -> GeometryStatistics:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = GeometryStatistics()
        return _INSTANCE


def reset_geometry_statistics_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
