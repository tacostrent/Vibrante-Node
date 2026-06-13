"""
Retrieval Statistics (Tier 12.8)
===================================
In-memory retrieval usage tracker. Capped at 2000 records.
"""
from __future__ import annotations

import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


@dataclass
class RetrievalRecord:
    query:       str = ""
    environment: str = ""
    role:        str = ""
    top_asset:   str = ""
    score:       float = 0.0
    result_count: int = 0
    duration_ms: float = 0.0
    ok:          bool = True
    ts:          float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query":        str(self.query),
            "environment":  str(self.environment),
            "role":         str(self.role),
            "top_asset":    str(self.top_asset),
            "score":        float(self.score),
            "result_count": int(self.result_count),
            "duration_ms":  float(self.duration_ms),
            "ok":           bool(self.ok),
            "ts":           float(self.ts),
        }


class RetrievalStatistics:
    def __init__(self) -> None:
        self._lock    = threading.Lock()
        self._records: List[RetrievalRecord] = []
        self._total_queries   = 0
        self._total_score     = 0.0
        self._env_counter:   Counter = Counter()
        self._role_counter:  Counter = Counter()
        self._asset_counter: Counter = Counter()

    def record(
        self,
        query: str = "",
        environment: str = "",
        role: str = "",
        top_asset: str = "",
        score: float = 0.0,
        result_count: int = 0,
        duration_ms: float = 0.0,
        ok: bool = True,
    ) -> None:
        """Append a retrieval record. Never raises."""
        try:
            rec = RetrievalRecord(
                query=str(query)[:200],
                environment=str(environment),
                role=str(role),
                top_asset=str(top_asset),
                score=float(score),
                result_count=int(result_count),
                duration_ms=float(duration_ms),
                ok=bool(ok),
            )
            with self._lock:
                if len(self._records) >= _MAX_RECORDS:
                    self._records = self._records[-(self._records.__len__() // 2):]
                self._records.append(rec)
                self._total_queries  += 1
                self._total_score    += float(score)
                if environment:
                    self._env_counter[environment]   += 1
                if role:
                    self._role_counter[role]          += 1
                if top_asset:
                    self._asset_counter[top_asset]    += 1
        except Exception:
            pass

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            avg_score = self._total_score / max(self._total_queries, 1)
            return {
                "total_queries":    self._total_queries,
                "avg_score":        round(avg_score, 4),
                "top_environments": self._env_counter.most_common(5),
                "top_roles":        self._role_counter.most_common(5),
                "top_assets":       self._asset_counter.most_common(5),
                "record_count":     len(self._records),
            }

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._records[-n:]]

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._total_queries  = 0
            self._total_score    = 0.0
            self._env_counter    = Counter()
            self._role_counter   = Counter()
            self._asset_counter  = Counter()


_INSTANCE: Optional[RetrievalStatistics] = None
_INSTANCE_LOCK = threading.Lock()


def get_retrieval_statistics() -> RetrievalStatistics:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = RetrievalStatistics()
    return _INSTANCE


def reset_retrieval_statistics_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
