"""
Asset Catalog Statistics (Tier 12.7)
=======================================
In-memory statistics tracker for semantic catalog operations.
Capped at 2000 operation records.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MAX_RECORDS = 2000


@dataclass
class StatRecord:
    operation:  str = ""
    asset_id:   str = ""
    source:     str = ""
    duration_ms: float = 0.0
    ok:         bool = True
    ts:         float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation":   str(self.operation),
            "asset_id":    str(self.asset_id),
            "source":      str(self.source),
            "duration_ms": float(self.duration_ms),
            "ok":          bool(self.ok),
            "ts":          float(self.ts),
        }


class CatalogStatistics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: List[StatRecord] = []
        self._register_count = 0
        self._query_count = 0
        self._enrich_count = 0
        self._sync_count = 0
        self._error_count = 0

    def record(
        self,
        operation: str,
        asset_id: str = "",
        source: str = "",
        duration_ms: float = 0.0,
        ok: bool = True,
    ) -> None:
        """Append a stat record (capped at _MAX_RECORDS). Never raises."""
        try:
            rec = StatRecord(
                operation=str(operation),
                asset_id=str(asset_id),
                source=str(source),
                duration_ms=float(duration_ms),
                ok=bool(ok),
            )
            with self._lock:
                if len(self._records) >= _MAX_RECORDS:
                    self._records = self._records[-(self._records.__len__() // 2):]
                self._records.append(rec)
                op = str(operation)
                if op == "register":
                    self._register_count += 1
                elif op == "query":
                    self._query_count += 1
                elif op == "enrich":
                    self._enrich_count += 1
                elif op == "sync":
                    self._sync_count += 1
                if not ok:
                    self._error_count += 1
        except Exception:
            pass

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._records)
            errors = sum(1 for r in self._records if not r.ok)
            avg_ms = (
                sum(r.duration_ms for r in self._records) / total
                if total else 0.0
            )
            return {
                "total_records":    total,
                "register_count":   self._register_count,
                "query_count":      self._query_count,
                "enrich_count":     self._enrich_count,
                "sync_count":       self._sync_count,
                "error_count":      self._error_count,
                "avg_duration_ms":  round(avg_ms, 2),
            }

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._records[-n:]]

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._register_count = 0
            self._query_count = 0
            self._enrich_count = 0
            self._sync_count = 0
            self._error_count = 0


_INSTANCE: Optional[CatalogStatistics] = None
_INSTANCE_LOCK = threading.Lock()


def get_catalog_statistics() -> CatalogStatistics:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = CatalogStatistics()
    return _INSTANCE


def reset_catalog_statistics_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
