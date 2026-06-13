"""
asset_suitability_statistics.py — §45 Semantic Asset Suitability Ranking
=========================================================================
In-memory statistics for suitability ranking operations. Capped at 2000 records.

Public API:
    get_asset_suitability_statistics() -> AssetSuitabilityStatistics
    reset_asset_suitability_statistics_for_tests()
"""

import threading
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SuitabilityStatRecord:
    environment: str
    role: str
    best_score: float
    mean_score: float
    candidate_count: int
    rejected_count: int
    production_ready: bool

    def to_dict(self) -> dict:
        return {
            "environment": self.environment,
            "role": self.role,
            "best_score": round(self.best_score, 4),
            "mean_score": round(self.mean_score, 4),
            "candidate_count": self.candidate_count,
            "rejected_count": self.rejected_count,
            "production_ready": self.production_ready,
        }


class AssetSuitabilityStatistics:
    _MAX = 2000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: List[SuitabilityStatRecord] = []

    def record(
        self,
        environment: str,
        role: str,
        best_score: float,
        mean_score: float,
        candidate_count: int,
        rejected_count: int,
        production_ready: bool,
    ) -> None:
        try:
            rec = SuitabilityStatRecord(
                environment=environment,
                role=role,
                best_score=best_score,
                mean_score=mean_score,
                candidate_count=candidate_count,
                rejected_count=rejected_count,
                production_ready=production_ready,
            )
            with self._lock:
                self._records.append(rec)
                if len(self._records) > self._MAX:
                    self._records = self._records[-self._MAX:]
        except Exception:
            pass

    def record_count(self) -> int:
        with self._lock:
            return len(self._records)

    def mean_best_score(self, environment: str = "") -> float:
        with self._lock:
            subset = [
                r for r in self._records
                if not environment or r.environment == environment
            ]
        if not subset:
            return 0.0
        return sum(r.best_score for r in subset) / len(subset)

    def top_environments(self, n: int = 5) -> List[Dict]:
        with self._lock:
            env_scores: Dict[str, List[float]] = {}
            for r in self._records:
                env_scores.setdefault(r.environment, []).append(r.best_score)
        result = [
            {"environment": env, "mean_best_score": sum(scores) / len(scores)}
            for env, scores in env_scores.items()
        ]
        result.sort(key=lambda x: x["mean_best_score"], reverse=True)
        return result[:n]

    def summary(self) -> dict:
        with self._lock:
            records = list(self._records)
        if not records:
            return {
                "total_rankings": 0,
                "mean_best_score": 0.0,
                "production_ready_rate": 0.0,
                "mean_rejection_rate": 0.0,
            }
        ready = sum(1 for r in records if r.production_ready)
        total_candidates = sum(r.candidate_count for r in records)
        total_rejected = sum(r.rejected_count for r in records)
        return {
            "total_rankings": len(records),
            "mean_best_score": round(sum(r.best_score for r in records) / len(records), 4),
            "production_ready_rate": round(ready / len(records), 4),
            "mean_rejection_rate": round(
                total_rejected / max(1, total_candidates), 4
            ),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: AssetSuitabilityStatistics | None = None
_instance_lock = threading.Lock()


def get_asset_suitability_statistics() -> AssetSuitabilityStatistics:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = AssetSuitabilityStatistics()
    return _instance


def reset_asset_suitability_statistics_for_tests() -> None:
    global _instance
    with _instance_lock:
        _instance = None
