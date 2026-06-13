"""
Workflow Statistics (Tier 10 — Workflow Packs & Production Blueprints)
======================================================================
Tracks workflow pack usage — executions, successes, failures, scores —
and provides aggregated runtime analytics.

Data is in-memory only (no disk persistence in this implementation).
All counters are thread-safe.

DESIGN RULES:
  1. Append-only — records are never modified.
  2. Thread-safe — all mutations under a single lock.
  3. No bridge calls.  No Houdini imports.
  4. Never raises.

Public API:
    WorkflowStatistics
    get_workflow_statistics()
    reset_workflow_statistics_for_tests()
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class _ExecutionRecord:
    """Internal record of one workflow execution."""
    workflow:   str
    status:     str        # committed | rolled_back | failed | previewed
    score:      float      # 0.0–1.0; 0.0 if no review
    grade:      str        # A/B/C/D/F; "" if no review
    duration:   float      # seconds; 0 if unknown
    dry_run:    bool
    timestamp:  float = field(default_factory=time.time)


class WorkflowStatistics:
    """In-memory workflow execution statistics tracker."""

    _MAX_RECORDS = 2_000

    def __init__(self) -> None:
        self._lock    = threading.Lock()
        self._records: List[_ExecutionRecord] = []
        self._write_count = 0

    # -----------------------------------------------------------------
    def record_execution(
        self,
        workflow:  str,
        status:    str,
        score:     float = 0.0,
        grade:     str   = "",
        duration:  float = 0.0,
        dry_run:   bool  = False,
    ) -> None:
        """Record one workflow execution."""
        rec = _ExecutionRecord(
            workflow  = workflow,
            status    = status,
            score     = max(0.0, min(1.0, score)),
            grade     = grade,
            duration  = duration,
            dry_run   = dry_run,
        )
        with self._lock:
            self._records.append(rec)
            self._write_count += 1
            if len(self._records) > self._MAX_RECORDS * 2:
                self._records = self._records[-self._MAX_RECORDS:]

    def record_success(
        self, workflow: str, score: float = 1.0, grade: str = "A", duration: float = 0.0
    ) -> None:
        """Convenience wrapper for committed executions."""
        self.record_execution(
            workflow=workflow, status="committed",
            score=score, grade=grade, duration=duration,
        )

    def record_failure(
        self, workflow: str, score: float = 0.0, grade: str = "F", duration: float = 0.0
    ) -> None:
        """Convenience wrapper for failed executions."""
        self.record_execution(
            workflow=workflow, status="failed",
            score=score, grade=grade, duration=duration,
        )

    # -----------------------------------------------------------------
    def get_pack_statistics(self, workflow: str) -> Dict[str, Any]:
        """Return statistics for a specific workflow pack."""
        with self._lock:
            recs = [r for r in self._records if r.workflow == workflow and not r.dry_run]

        if not recs:
            return {
                "workflow":    workflow,
                "executions":  0,
                "successes":   0,
                "failures":    0,
                "success_rate": 0.0,
                "average_score": 0.0,
                "average_duration": 0.0,
                "grade_distribution": {},
            }

        successes  = sum(1 for r in recs if r.status == "committed")
        failures   = sum(1 for r in recs if r.status in ("failed", "rolled_back"))
        scores     = [r.score for r in recs]
        durations  = [r.duration for r in recs]
        grades: Dict[str, int] = defaultdict(int)
        for r in recs:
            if r.grade:
                grades[r.grade] += 1

        return {
            "workflow":           workflow,
            "executions":         len(recs),
            "successes":          successes,
            "failures":           failures,
            "success_rate":       successes / len(recs),
            "average_score":      sum(scores) / len(scores) if scores else 0.0,
            "average_duration":   sum(durations) / len(durations) if durations else 0.0,
            "grade_distribution": dict(grades),
        }

    def get_runtime_statistics(self) -> Dict[str, Any]:
        """Return aggregate statistics across all workflow packs."""
        with self._lock:
            all_recs  = [r for r in self._records if not r.dry_run]
            dry_count = sum(1 for r in self._records if r.dry_run)

        if not all_recs:
            return {
                "total_executions":    0,
                "total_previews":      dry_count,
                "success_rate":        0.0,
                "average_score":       0.0,
                "rollback_rate":       0.0,
                "top_workflows":       [],
                "write_count":         self._write_count,
            }

        successes  = sum(1 for r in all_recs if r.status == "committed")
        rollbacks  = sum(1 for r in all_recs if r.status == "rolled_back")
        scores     = [r.score for r in all_recs]

        # Count per workflow
        counts: Dict[str, int] = defaultdict(int)
        for r in all_recs:
            counts[r.workflow] += 1
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:5]

        return {
            "total_executions":    len(all_recs),
            "total_previews":      dry_count,
            "success_rate":        successes / len(all_recs) if all_recs else 0.0,
            "average_score":       sum(scores) / len(scores) if scores else 0.0,
            "rollback_rate":       rollbacks / len(all_recs) if all_recs else 0.0,
            "top_workflows":       [{"workflow": k, "count": v} for k, v in top],
            "write_count":         self._write_count,
        }

    # -----------------------------------------------------------------
    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._write_count = 0

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "record_count":  len(self._records),
                "write_count":   self._write_count,
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[WorkflowStatistics] = None
_lock = threading.Lock()


def get_workflow_statistics() -> WorkflowStatistics:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = WorkflowStatistics()
    return _instance


def reset_workflow_statistics_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
