"""
Realization Statistics (Tier 13)
===================================
In-memory, thread-safe, append-only execution tracking for the
asset realization pipeline.

DESIGN RULES:
  1. No bridge calls, no file I/O.
  2. Thread-safe via threading.Lock.
  3. Capped at 2000 records (auto-prune at 2x).
  4. Never raises in public methods.
  5. Singleton pattern.

Public API:
    RealizationStatistics
    get_realization_statistics()
    reset_realization_statistics_for_tests()
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RECORDS   = 2000
_PRUNE_AT      = _MAX_RECORDS * 2

_VALID_STATUSES = frozenset({"success", "failed", "partial"})


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RealizationStatistics:
    """
    In-memory statistics tracker for asset realization operations.
    Capped at 2000 records.
    """

    def __init__(self) -> None:
        self._lock        = threading.Lock()
        self._records:     List[Dict[str, Any]] = []
        self._write_count: int = 0

    # ------------------------------------------------------------------
    # Record methods
    # ------------------------------------------------------------------

    def record_realization(
        self,
        asset_id:  str,
        status:    str,
        score:     Optional[float] = None,
        duration:  Optional[float] = None,
    ) -> None:
        """Record a realization event. Never raises."""
        try:
            if status not in _VALID_STATUSES:
                status = "failed"
            self._append({
                "record_type": "realization",
                "asset_id":    asset_id,
                "status":      status,
                "score":       score,
                "duration_sec": duration,
                "timestamp":   time.time(),
            })
        except Exception:
            pass

    def record_import(self, asset_id: str, format_: str, ok: bool) -> None:
        """Record an import event."""
        try:
            self._append({
                "record_type": "import",
                "asset_id":    asset_id,
                "format":      format_,
                "ok":          bool(ok),
                "timestamp":   time.time(),
            })
        except Exception:
            pass

    def record_conversion(
        self,
        asset_id:    str,
        source_fmt:  str,
        target_fmt:  str,
        ok:          bool,
    ) -> None:
        """Record a conversion event."""
        try:
            self._append({
                "record_type": "conversion",
                "asset_id":    asset_id,
                "source_fmt":  source_fmt,
                "target_fmt":  target_fmt,
                "ok":          bool(ok),
                "timestamp":   time.time(),
            })
        except Exception:
            pass

    def record_failure(
        self,
        asset_id:     str,
        failure_type: str,
        error:        str = "",
    ) -> None:
        """Record a failure event."""
        try:
            self._append({
                "record_type":  "failure",
                "asset_id":     asset_id,
                "failure_type": failure_type,
                "error":        error,
                "timestamp":    time.time(),
            })
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Report methods
    # ------------------------------------------------------------------

    def generate_report(self) -> Dict[str, Any]:
        """Generate a statistics report. Never raises."""
        try:
            return self._do_report()
        except Exception as exc:
            return {
                "total_realizations": 0,
                "success_rate":       0.0,
                "avg_score":          0.0,
                "by_format":          {},
                "by_status":          {},
                "top_failures":       [],
                "error":              str(exc),
            }

    def get_asset_statistics(self, asset_id: str) -> Dict[str, Any]:
        """Get statistics for a specific asset. Never raises."""
        try:
            with self._lock:
                records = [r for r in self._records if r.get("asset_id") == asset_id]
            realizations = [r for r in records if r.get("record_type") == "realization"]
            imports      = [r for r in records if r.get("record_type") == "import"]
            conversions  = [r for r in records if r.get("record_type") == "conversion"]
            failures     = [r for r in records if r.get("record_type") == "failure"]

            scores   = [r["score"] for r in realizations if r.get("score") is not None]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            successes = sum(1 for r in realizations if r.get("status") == "success")
            total_r   = len(realizations)
            return {
                "asset_id":       asset_id,
                "total_realizations": total_r,
                "success_rate":   successes / total_r if total_r else 0.0,
                "avg_score":      avg_score,
                "total_imports":  len(imports),
                "total_conversions": len(conversions),
                "total_failures": len(failures),
            }
        except Exception as exc:
            return {"asset_id": asset_id, "error": str(exc)}

    def stats(self) -> Dict[str, Any]:
        """Return lightweight meta-statistics."""
        with self._lock:
            return {
                "write_count":  self._write_count,
                "record_count": len(self._records),
            }

    def clear(self) -> None:
        """Clear all records."""
        with self._lock:
            self._records.clear()
            self._write_count = 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append(self, record: Dict[str, Any]) -> None:
        with self._lock:
            self._records.append(record)
            self._write_count += 1
            if len(self._records) >= _PRUNE_AT:
                self._records = self._records[-_MAX_RECORDS:]

    def _do_report(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self._records)

        realizations = [r for r in records if r.get("record_type") == "realization"]
        imports      = [r for r in records if r.get("record_type") == "import"]
        failures     = [r for r in records if r.get("record_type") == "failure"]

        total = len(realizations)
        successes = sum(1 for r in realizations if r.get("status") == "success")
        success_rate = successes / total if total else 0.0

        scores = [r["score"] for r in realizations if r.get("score") is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # By format (from imports)
        by_format: Dict[str, int] = {}
        for r in imports:
            fmt = r.get("format", "unknown")
            by_format[fmt] = by_format.get(fmt, 0) + 1

        # By status
        by_status: Dict[str, int] = {}
        for r in realizations:
            st = r.get("status", "unknown")
            by_status[st] = by_status.get(st, 0) + 1

        # Top failures
        failure_counts: Dict[str, int] = {}
        for r in failures:
            ft = r.get("failure_type", "unknown")
            failure_counts[ft] = failure_counts.get(ft, 0) + 1
        top_failures = sorted(failure_counts.items(), key=lambda x: -x[1])[:5]

        return {
            "total_realizations": total,
            "success_rate":       success_rate,
            "avg_score":          avg_score,
            "by_format":          by_format,
            "by_status":          by_status,
            "top_failures":       [{"type": t, "count": c} for t, c in top_failures],
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[RealizationStatistics] = None
_INSTANCE_LOCK = threading.Lock()


def get_realization_statistics() -> RealizationStatistics:
    """Return the module-level singleton RealizationStatistics."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = RealizationStatistics()
    return _INSTANCE


def reset_realization_statistics_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
