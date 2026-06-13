"""
Lighting Statistics (Tier 15)
===============================
In-memory statistics tracking for lighting operations.
Capped at 2000 records per record type.
Deterministic output (sorted keys), thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


class LightingStatistics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._review_records: List[Dict[str, Any]] = []
        self._pattern_usage: Dict[str, int] = {}
        self._mood_usage: Dict[str, int] = {}
        self._environment_usage: Dict[str, int] = {}
        self._plan_records: List[Dict[str, Any]] = []

    def record_review(self, review_dict: Dict[str, Any]) -> None:
        try:
            review_dict = review_dict if isinstance(review_dict, dict) else {}
            record = {
                "score":           float(review_dict.get("score") or 0.0),
                "grade":           str(review_dict.get("grade", "")),
                "production_ready": bool(review_dict.get("production_ready", False)),
                "mood":            str(review_dict.get("mood", "")),
                "environment":     str(review_dict.get("environment", "")),
                "recorded_at":     time.time(),
            }
            with self._lock:
                if len(self._review_records) >= _MAX_RECORDS:
                    self._review_records = self._review_records[_MAX_RECORDS // 2:]
                self._review_records.append(record)
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

    def record_mood_usage(self, mood: str) -> None:
        try:
            m = str(mood or "").strip()
            if not m:
                return
            with self._lock:
                self._mood_usage[m] = self._mood_usage.get(m, 0) + 1
        except Exception:
            pass

    def record_environment_usage(self, environment: str) -> None:
        try:
            e = str(environment or "").strip()
            if not e:
                return
            with self._lock:
                self._environment_usage[e] = self._environment_usage.get(e, 0) + 1
        except Exception:
            pass

    def record_plan(self, plan_dict: Dict[str, Any]) -> None:
        try:
            plan_dict = plan_dict if isinstance(plan_dict, dict) else {}
            record = {
                "plan_id":     str(plan_dict.get("plan_id", "")),
                "environment": str(plan_dict.get("environment", "")),
                "mood":        str(plan_dict.get("mood", "")),
                "recorded_at": time.time(),
            }
            with self._lock:
                if len(self._plan_records) >= _MAX_RECORDS:
                    self._plan_records = self._plan_records[_MAX_RECORDS // 2:]
                self._plan_records.append(record)
        except Exception:
            pass

    def generate_statistics(self) -> Dict[str, Any]:
        try:
            with self._lock:
                reviews    = list(self._review_records)
                pat_usage  = dict(self._pattern_usage)
                mood_usage = dict(self._mood_usage)
                env_usage  = dict(self._environment_usage)
                plans      = list(self._plan_records)

            top_patterns     = sorted(pat_usage.items(),  key=lambda x: (-x[1], x[0]))[:10]
            top_moods        = sorted(mood_usage.items(), key=lambda x: (-x[1], x[0]))[:8]
            top_environments = sorted(env_usage.items(),  key=lambda x: (-x[1], x[0]))[:8]

            scores = [r.get("score", 0.0) for r in reviews if isinstance(r.get("score"), (int, float))]
            avg_score = round(sum(scores) / len(scores), 3) if scores else 0.0

            return {
                "total_reviews":          len(reviews),
                "total_plans":            len(plans),
                "average_review_score":   avg_score,
                "top_patterns":           [{"pattern_id": p, "count": c} for p, c in top_patterns],
                "top_moods":              [{"mood": m, "count": c} for m, c in top_moods],
                "top_environments":       [{"environment": e, "count": c} for e, c in top_environments],
            }
        except Exception as exc:
            return {
                "total_reviews": 0,
                "total_plans": 0,
                "average_review_score": 0.0,
                "top_patterns": [],
                "top_moods": [],
                "top_environments": [],
                "error": str(exc),
            }


_INSTANCE: Optional[LightingStatistics] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_statistics() -> LightingStatistics:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingStatistics()
    return _INSTANCE


def reset_lighting_statistics_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
