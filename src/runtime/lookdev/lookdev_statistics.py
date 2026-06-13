"""
Lookdev Statistics (Tier 14)
=============================
In-memory statistics tracking for lookdev operations.
Capped at 2000 records per record type to prevent unbounded growth.
Deterministic output (sorted keys), thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


class LookdevStatistics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._assignment_records: List[Dict[str, Any]] = []
        self._review_records: List[Dict[str, Any]] = []
        self._material_usage: Dict[str, int] = {}
        self._pattern_usage: Dict[str, int] = {}

    def record_assignment(self, assignment_dict: Dict[str, Any]) -> None:
        try:
            assignment_dict = assignment_dict if isinstance(assignment_dict, dict) else {}
            record = {
                "asset_id":      str(assignment_dict.get("asset_id", "")),
                "material_name": str(assignment_dict.get("material_name", "")),
                "renderer":      str(assignment_dict.get("renderer", "")),
                "confidence":    float(assignment_dict.get("confidence") or 0.0),
                "recorded_at":   time.time(),
            }
            with self._lock:
                if len(self._assignment_records) >= _MAX_RECORDS:
                    self._assignment_records = self._assignment_records[_MAX_RECORDS // 2:]
                self._assignment_records.append(record)
        except Exception:
            pass

    def record_material_usage(self, material_name: str, renderer: str = "") -> None:
        try:
            name = str(material_name or "").strip()
            if not name:
                return
            with self._lock:
                self._material_usage[name] = self._material_usage.get(name, 0) + 1
        except Exception:
            pass

    def record_pattern_usage(self, pattern_id: str) -> None:
        try:
            pid = str(pattern_id or "").strip()
            if not pid:
                return
            with self._lock:
                self._pattern_usage[pid] = self._pattern_usage.get(pid, 0) + 1
        except Exception:
            pass

    def record_review(self, review_dict: Dict[str, Any]) -> None:
        try:
            review_dict = review_dict if isinstance(review_dict, dict) else {}
            record = {
                "score":           float(review_dict.get("score") or 0.0),
                "grade":           str(review_dict.get("grade", "")),
                "production_ready": bool(review_dict.get("production_ready", False)),
                "renderer":        str(review_dict.get("renderer", "")),
                "recorded_at":     time.time(),
            }
            with self._lock:
                if len(self._review_records) >= _MAX_RECORDS:
                    self._review_records = self._review_records[_MAX_RECORDS // 2:]
                self._review_records.append(record)
        except Exception:
            pass

    def generate_statistics(self) -> Dict[str, Any]:
        try:
            with self._lock:
                assignments = list(self._assignment_records)
                reviews = list(self._review_records)
                mat_usage = dict(self._material_usage)
                pat_usage = dict(self._pattern_usage)

            total_material_usages = sum(mat_usage.values())
            top_materials = sorted(mat_usage.items(), key=lambda x: (-x[1], x[0]))[:10]
            top_patterns  = sorted(pat_usage.items(), key=lambda x: (-x[1], x[0]))[:5]

            scores = [r.get("score", 0.0) for r in reviews if isinstance(r.get("score"), (int, float))]
            avg_score = round(sum(scores) / len(scores), 3) if scores else 0.0

            return {
                "total_assignments":    len(assignments),
                "total_reviews":        len(reviews),
                "total_material_usages": total_material_usages,
                "top_materials":        [{"name": n, "count": c} for n, c in top_materials],
                "top_patterns":         [{"pattern_id": p, "count": c} for p, c in top_patterns],
                "average_review_score": avg_score,
            }
        except Exception as exc:
            return {
                "total_assignments": 0,
                "total_reviews": 0,
                "total_material_usages": 0,
                "top_materials": [],
                "top_patterns": [],
                "average_review_score": 0.0,
                "error": str(exc),
            }


_INSTANCE: Optional[LookdevStatistics] = None
_INSTANCE_LOCK = threading.Lock()


def get_lookdev_statistics() -> LookdevStatistics:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LookdevStatistics()
    return _INSTANCE


def reset_lookdev_statistics_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
