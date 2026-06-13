"""
Environment Statistics (§39 — Environment Expansion Pack)
===========================================================
Tracks usage, success, review averages, asset counts, and
lighting pattern usage per environment.  In-memory, capped at 2000 records.

Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


@dataclass
class EnvironmentStatRecord:
    environment:           str = ""
    event_type:            str = ""   # "usage", "success", "failure", "review", "lighting_pattern"
    score:                 float = 0.0
    lighting_pattern:      str = ""
    asset_count:           int = 0
    metadata:              Dict[str, Any] = field(default_factory=dict)
    recorded_at:           float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":      str(self.environment),
            "event_type":       str(self.event_type),
            "score":            float(self.score),
            "lighting_pattern": str(self.lighting_pattern),
            "asset_count":      int(self.asset_count),
            "metadata":         dict(self.metadata),
            "recorded_at":      float(self.recorded_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentStatRecord":
        d = d if isinstance(d, dict) else {}
        return cls(
            environment=str(d.get("environment", "")),
            event_type=str(d.get("event_type", "")),
            score=float(d.get("score") or 0.0),
            lighting_pattern=str(d.get("lighting_pattern", "")),
            asset_count=int(d.get("asset_count") or 0),
            metadata=dict(d.get("metadata") or {}),
            recorded_at=float(d.get("recorded_at") or time.time()),
        )


class EnvironmentStatistics:
    """In-memory statistics tracker for environment production usage."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: List[EnvironmentStatRecord] = []

    def record_usage(self, environment: str, asset_count: int = 0, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record an environment usage event. Never raises."""
        try:
            self._append(EnvironmentStatRecord(
                environment=str(environment),
                event_type="usage",
                asset_count=int(asset_count),
                metadata=dict(metadata or {}),
            ))
        except Exception:
            pass

    def record_success(self, environment: str, score: float = 1.0, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a successful environment execution. Never raises."""
        try:
            self._append(EnvironmentStatRecord(
                environment=str(environment),
                event_type="success",
                score=float(score),
                metadata=dict(metadata or {}),
            ))
        except Exception:
            pass

    def record_failure(self, environment: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a failed environment execution. Never raises."""
        try:
            self._append(EnvironmentStatRecord(
                environment=str(environment),
                event_type="failure",
                metadata=dict(metadata or {}),
            ))
        except Exception:
            pass

    def record_review(self, environment: str, score: float = 0.0, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a review score for an environment execution. Never raises."""
        try:
            self._append(EnvironmentStatRecord(
                environment=str(environment),
                event_type="review",
                score=float(score),
                metadata=dict(metadata or {}),
            ))
        except Exception:
            pass

    def record_lighting_pattern(self, environment: str, lighting_pattern: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record which lighting pattern was used for an environment. Never raises."""
        try:
            self._append(EnvironmentStatRecord(
                environment=str(environment),
                event_type="lighting_pattern",
                lighting_pattern=str(lighting_pattern),
                metadata=dict(metadata or {}),
            ))
        except Exception:
            pass

    def usage_count(self, environment: str) -> int:
        """Return the number of times an environment was used."""
        env = str(environment)
        with self._lock:
            return sum(1 for r in self._records if r.environment == env and r.event_type == "usage")

    def success_rate(self, environment: str) -> float:
        """Return success rate for an environment as a fraction [0.0, 1.0]."""
        env = str(environment)
        with self._lock:
            successes = sum(1 for r in self._records if r.environment == env and r.event_type == "success")
            failures  = sum(1 for r in self._records if r.environment == env and r.event_type == "failure")
        total = successes + failures
        return round(successes / total, 4) if total > 0 else 0.0

    def review_average(self, environment: str) -> float:
        """Return mean review score for an environment."""
        env = str(environment)
        with self._lock:
            scores = [r.score for r in self._records if r.environment == env and r.event_type == "review"]
        return round(sum(scores) / len(scores), 4) if scores else 0.0

    def asset_count_average(self, environment: str) -> float:
        """Return average asset count seen in usage records for an environment."""
        env = str(environment)
        with self._lock:
            counts = [r.asset_count for r in self._records if r.environment == env and r.event_type == "usage"]
        return round(sum(counts) / len(counts), 2) if counts else 0.0

    def lighting_pattern_usage(self, environment: str) -> Dict[str, int]:
        """Return dict of lighting_pattern → usage_count for the environment."""
        env = str(environment)
        result: Dict[str, int] = {}
        with self._lock:
            for r in self._records:
                if r.environment == env and r.event_type == "lighting_pattern" and r.lighting_pattern:
                    result[r.lighting_pattern] = result.get(r.lighting_pattern, 0) + 1
        return result

    def top_environments(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return the top N environments by usage count."""
        with self._lock:
            counts: Dict[str, int] = {}
            for r in self._records:
                if r.event_type == "usage":
                    counts[r.environment] = counts.get(r.environment, 0) + 1
        ranked = sorted(counts.items(), key=lambda x: -x[1])[:n]
        return [{"environment": e, "usage_count": c} for e, c in ranked]

    def summary(self, environment: str) -> Dict[str, Any]:
        """Return a stats summary dict for the given environment."""
        return {
            "environment":       environment,
            "usage_count":       self.usage_count(environment),
            "success_rate":      self.success_rate(environment),
            "review_average":    self.review_average(environment),
            "asset_count_avg":   self.asset_count_average(environment),
            "lighting_patterns": self.lighting_pattern_usage(environment),
        }

    def get_all_records(self) -> List[EnvironmentStatRecord]:
        with self._lock:
            return list(self._records)

    def record_count(self) -> int:
        with self._lock:
            return len(self._records)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append(self, record: EnvironmentStatRecord) -> None:
        with self._lock:
            if len(self._records) >= _MAX_RECORDS:
                self._records.pop(0)
            self._records.append(record)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentStatistics] = None
_INSTANCE_LOCK = threading.Lock()


def get_environment_statistics() -> EnvironmentStatistics:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = EnvironmentStatistics()
    return _INSTANCE


def reset_environment_statistics_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
