"""
Runtime Analytics
=================
Tracks and aggregates execution performance data across the Vibrante-Node
runtime. Records execution durations, transaction success rates, rollback
frequency, worker utilisation, orchestration bottlenecks, and validation
failures.

This module NEVER:
  • executes operations or calls the bridge
  • modifies execution plans
  • interacts with TransactionManager or ExecutionScheduler directly

It ONLY collects metrics and produces structured reports.

Output shape (from get_report):
  {
    "execution_metrics":   {avg_duration_sec, total_executions, success_rate, ...},
    "failure_metrics":     {total_rollbacks, rollback_rate, top_failure_ops, ...},
    "resource_metrics":    {worker_utilization, avg_queue_depth, ...},
    "workflow_statistics": {by_intent, by_template, by_status},
  }

Public API:
    get_runtime_analytics() -> RuntimeAnalytics   (singleton)
    reset_runtime_analytics_for_tests()            (test isolation only)

    analytics.record_execution(data) -> str
    analytics.record_validation(data) -> str
    analytics.record_worker_event(data) -> str
    analytics.get_report() -> dict
    analytics.get_execution_trends(window_sec=300) -> dict
    analytics.stats() -> dict
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional


class RuntimeAnalytics:
    """Execution performance data collector and aggregator."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # Execution records: [{id, intent, status, duration_sec, op_count, timestamp, ...}]
        self._executions: List[Dict[str, Any]] = []

        # Validation records: [{id, intent, valid, error_count, warning_count, timestamp}]
        self._validations: List[Dict[str, Any]] = []

        # Worker events: [{id, event_type, worker_id, timestamp, ...}]
        self._worker_events: List[Dict[str, Any]] = []

        self._max_records = 2000

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_execution(self, data: Dict[str, Any]) -> str:
        """Record a completed transaction execution.

        Expected data keys:
          intent, status ("committed"|"rolled_back"|"failed"), duration_sec,
          op_count, template_id (optional), rollback_performed (bool), errors (list)
        Returns record id.
        """
        record_id = str(uuid.uuid4())
        record = {
            "id":                record_id,
            "intent":            data.get("intent", ""),
            "status":            data.get("status", "unknown"),
            "duration_sec":      float(data.get("duration_sec", 0.0)),
            "op_count":          int(data.get("op_count", 0)),
            "template_id":       data.get("template_id", ""),
            "rollback_performed": bool(data.get("rollback_performed", False)),
            "error_count":       len(data.get("errors", [])),
            "timestamp":         time.time(),
        }
        with self._lock:
            self._executions.append(record)
            self._prune(self._executions)
        return record_id

    def record_validation(self, data: Dict[str, Any]) -> str:
        """Record a pre-execution validation result.

        Expected data keys:
          intent, valid (bool), error_count, warning_count, risk_level
        Returns record id.
        """
        record_id = str(uuid.uuid4())
        record = {
            "id":            record_id,
            "intent":        data.get("intent", ""),
            "valid":         bool(data.get("valid", True)),
            "error_count":   int(data.get("error_count", 0)),
            "warning_count": int(data.get("warning_count", 0)),
            "risk_level":    data.get("risk_level", "low"),
            "timestamp":     time.time(),
        }
        with self._lock:
            self._validations.append(record)
            self._prune(self._validations)
        return record_id

    def record_worker_event(self, data: Dict[str, Any]) -> str:
        """Record a worker pool event.

        Expected data keys:
          event_type ("acquired"|"released"|"stale"|"registered"|"deregistered"),
          worker_id, capabilities (list), current_load, max_load
        Returns record id.
        """
        record_id = str(uuid.uuid4())
        record = {
            "id":           record_id,
            "event_type":   data.get("event_type", "unknown"),
            "worker_id":    data.get("worker_id", ""),
            "current_load": int(data.get("current_load", 0)),
            "max_load":     int(data.get("max_load", 1)),
            "timestamp":    time.time(),
        }
        with self._lock:
            self._worker_events.append(record)
            self._prune(self._worker_events)
        return record_id

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def get_report(self) -> Dict[str, Any]:
        """Return a full analytics report.

        Returns:
            {
                "execution_metrics":   {...},
                "failure_metrics":     {...},
                "resource_metrics":    {...},
                "workflow_statistics": {...},
                "generated_at":        float,
            }
        """
        with self._lock:
            execs = list(self._executions)
            vals  = list(self._validations)
            wevts = list(self._worker_events)

        execution_metrics = self._compute_execution_metrics(execs)
        failure_metrics   = self._compute_failure_metrics(execs)
        resource_metrics  = self._compute_resource_metrics(wevts)
        workflow_stats    = self._compute_workflow_statistics(execs, vals)

        return {
            "execution_metrics":   execution_metrics,
            "failure_metrics":     failure_metrics,
            "resource_metrics":    resource_metrics,
            "workflow_statistics": workflow_stats,
            "generated_at":        time.time(),
        }

    def _compute_execution_metrics(self, execs: List[Dict]) -> Dict[str, Any]:
        if not execs:
            return {
                "total_executions": 0, "success_count": 0, "success_rate": 0.0,
                "avg_duration_sec": 0.0, "max_duration_sec": 0.0, "avg_op_count": 0.0,
            }
        total = len(execs)
        success = sum(1 for e in execs if e["status"] == "committed")
        durations = [e["duration_sec"] for e in execs]
        op_counts = [e["op_count"] for e in execs]
        return {
            "total_executions": total,
            "success_count":    success,
            "success_rate":     round(success / total, 3),
            "avg_duration_sec": round(sum(durations) / total, 3),
            "max_duration_sec": round(max(durations), 3),
            "avg_op_count":     round(sum(op_counts) / total, 2),
        }

    def _compute_failure_metrics(self, execs: List[Dict]) -> Dict[str, Any]:
        if not execs:
            return {
                "total_rollbacks": 0, "rollback_rate": 0.0,
                "total_failures": 0, "failure_rate": 0.0,
                "avg_errors_per_failure": 0.0, "top_failure_intents": [],
            }
        total = len(execs)
        rollbacks = [e for e in execs if e.get("rollback_performed")]
        failures  = [e for e in execs if e["status"] in ("failed", "rolled_back")]
        error_counts = [e["error_count"] for e in failures]

        intent_fails: Dict[str, int] = defaultdict(int)
        for e in failures:
            if e["intent"]:
                intent_fails[e["intent"]] += 1
        top_fails = sorted(intent_fails.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_rollbacks":       len(rollbacks),
            "rollback_rate":         round(len(rollbacks) / total, 3),
            "total_failures":        len(failures),
            "failure_rate":          round(len(failures) / total, 3),
            "avg_errors_per_failure": round(sum(error_counts) / len(error_counts), 2) if error_counts else 0.0,
            "top_failure_intents":   [{"intent": k, "count": v} for k, v in top_fails],
        }

    def _compute_resource_metrics(self, wevts: List[Dict]) -> Dict[str, Any]:
        if not wevts:
            return {
                "total_worker_events": 0, "acquire_count": 0, "release_count": 0,
                "stale_count": 0, "avg_utilization": 0.0,
            }
        acquire = [e for e in wevts if e["event_type"] == "acquired"]
        release = [e for e in wevts if e["event_type"] == "released"]
        stale   = [e for e in wevts if e["event_type"] == "stale"]

        loads = [e["current_load"] / max(e["max_load"], 1) for e in wevts if e["max_load"] > 0]
        avg_util = round(sum(loads) / len(loads), 3) if loads else 0.0

        return {
            "total_worker_events": len(wevts),
            "acquire_count":       len(acquire),
            "release_count":       len(release),
            "stale_count":         len(stale),
            "avg_utilization":     avg_util,
        }

    def _compute_workflow_statistics(
        self, execs: List[Dict], vals: List[Dict]
    ) -> Dict[str, Any]:
        by_intent: Dict[str, int] = defaultdict(int)
        by_template: Dict[str, int] = defaultdict(int)
        by_status: Dict[str, int] = defaultdict(int)

        for e in execs:
            if e["intent"]:
                by_intent[e["intent"]] += 1
            if e["template_id"]:
                by_template[e["template_id"]] += 1
            by_status[e["status"]] += 1

        val_total  = len(vals)
        val_failed = sum(1 for v in vals if not v["valid"])
        val_rate   = round(val_failed / val_total, 3) if val_total else 0.0

        return {
            "by_intent":          dict(by_intent),
            "by_template":        dict(by_template),
            "by_status":          dict(by_status),
            "validation_total":   val_total,
            "validation_failure_rate": val_rate,
        }

    # ------------------------------------------------------------------
    # Trend window
    # ------------------------------------------------------------------

    def get_execution_trends(self, window_sec: float = 300.0) -> Dict[str, Any]:
        """Return metrics for executions within the last `window_sec` seconds."""
        cutoff = time.time() - window_sec
        with self._lock:
            recent = [e for e in self._executions if e["timestamp"] >= cutoff]

        if not recent:
            return {
                "window_sec": window_sec, "count": 0, "success_rate": 0.0,
                "avg_duration_sec": 0.0, "rollback_count": 0,
            }

        success = sum(1 for e in recent if e["status"] == "committed")
        rollbacks = sum(1 for e in recent if e.get("rollback_performed"))
        durations = [e["duration_sec"] for e in recent]

        return {
            "window_sec":      window_sec,
            "count":           len(recent),
            "success_rate":    round(success / len(recent), 3),
            "avg_duration_sec": round(sum(durations) / len(recent), 3),
            "rollback_count":  rollbacks,
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "execution_records":  len(self._executions),
                "validation_records": len(self._validations),
                "worker_events":      len(self._worker_events),
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _prune(self, lst: List) -> None:
        if len(lst) > self._max_records:
            del lst[:len(lst) - self._max_records]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[RuntimeAnalytics] = None
_INSTANCE_LOCK = threading.Lock()


def get_runtime_analytics() -> RuntimeAnalytics:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = RuntimeAnalytics()
        return _INSTANCE


def reset_runtime_analytics_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
