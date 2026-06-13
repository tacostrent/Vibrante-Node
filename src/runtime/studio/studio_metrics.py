"""Studio performance metrics tracker (Tier 11 — §31).

In-memory, thread-safe, append-only metric store.
Metric types: execution_success, execution_failure, review_score, workflow_usage.
No persistence — metrics are accumulated per session.
"""

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

_module_lock = threading.Lock()
_instance: Optional["StudioMetrics"] = None
_MAX_RECORDS = 5000


def get_studio_metrics() -> "StudioMetrics":
    global _instance
    with _module_lock:
        if _instance is None:
            _instance = StudioMetrics()
    return _instance


def reset_studio_metrics_for_tests() -> None:
    global _instance
    with _module_lock:
        _instance = None


class StudioMetrics:
    """Tracks studio-wide performance metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics: List[Dict[str, Any]] = []
        self._write_count = 0

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def record_metric(
        self,
        metric_type: str,
        value: float,
        workflow: str = "",
        environment: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        with self._lock:
            mid = str(uuid.uuid4())
            self._metrics.append({
                "metric_id": mid,
                "metric_type": metric_type,
                "value": float(value),
                "workflow": workflow,
                "environment": environment,
                "metadata": metadata or {},
                "timestamp": time.time(),
            })
            self._write_count += 1
            if len(self._metrics) > _MAX_RECORDS * 2:
                self._metrics = self._metrics[-_MAX_RECORDS:]
            return mid

    # ------------------------------------------------------------------
    # Calculated metrics
    # ------------------------------------------------------------------

    def calculate_success_rate(self, workflow: Optional[str] = None) -> float:
        with self._lock:
            records = [
                m for m in self._metrics
                if m.get("metric_type") in ("execution_success", "execution_failure")
                and (workflow is None or m.get("workflow") == workflow)
            ]
            if not records:
                return 0.0
            successes = sum(1 for r in records if r.get("metric_type") == "execution_success")
            return round(successes / len(records), 3)

    def calculate_quality_average(self, workflow: Optional[str] = None) -> float:
        with self._lock:
            records = [
                m for m in self._metrics
                if m.get("metric_type") == "review_score"
                and (workflow is None or m.get("workflow") == workflow)
            ]
            if not records:
                return 0.0
            return round(sum(r.get("value", 0.0) for r in records) / len(records), 3)

    def calculate_workflow_performance(self, workflow: str) -> Dict[str, Any]:
        with self._lock:
            records = [m for m in self._metrics if m.get("workflow") == workflow]
        if not records:
            return {
                "workflow": workflow, "total": 0,
                "success_rate": 0.0, "avg_score": 0.0,
            }
        successes = sum(1 for r in records if r.get("metric_type") == "execution_success")
        score_recs = [r for r in records if r.get("metric_type") == "review_score"]
        avg_score = (
            sum(r.get("value", 0.0) for r in score_recs) / len(score_recs)
            if score_recs else 0.0
        )
        return {
            "workflow": workflow,
            "total": len(records),
            "successes": successes,
            "success_rate": round(successes / len(records), 3),
            "avg_score": round(avg_score, 3),
        }

    def calculate_review_performance(self) -> Dict[str, Any]:
        with self._lock:
            records = [m for m in self._metrics if m.get("metric_type") == "review_score"]
        if not records:
            return {"total_reviews": 0, "avg_score": 0.0, "passing_rate": 0.0}
        avg = sum(r.get("value", 0.0) for r in records) / len(records)
        passing = sum(1 for r in records if r.get("value", 0.0) >= 0.7)
        return {
            "total_reviews": len(records),
            "avg_score": round(avg, 3),
            "passing_rate": round(passing / len(records), 3),
        }

    def generate_metrics_report(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self._metrics)

        seen_workflows: set = set()
        wf_perfs: List[Dict[str, Any]] = []
        for r in records:
            wf = r.get("workflow", "")
            if wf and wf not in seen_workflows:
                seen_workflows.add(wf)
                wf_perfs.append(self.calculate_workflow_performance(wf))

        return {
            "total_metrics": len(records),
            "overall_success_rate": self.calculate_success_rate(),
            "overall_quality_average": self.calculate_quality_average(),
            "review_performance": self.calculate_review_performance(),
            "workflow_performance": wf_perfs,
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_metrics": len(self._metrics),
                "write_count": self._write_count,
            }
