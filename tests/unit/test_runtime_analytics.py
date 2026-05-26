"""
Unit tests for src.runtime.runtime_analytics.

Covers:
  • record_execution / record_validation / record_worker_event return ids
  • get_report shape (all 4 top-level keys present)
  • execution_metrics: total, success_count, success_rate, avg_duration
  • failure_metrics: total_rollbacks, rollback_rate, top_failure_intents
  • resource_metrics: total_worker_events, acquire/release counts
  • workflow_statistics: by_intent, by_template, by_status, validation_failure_rate
  • get_execution_trends filters by window
  • trends count=0 when no records in window
  • stats shape
  • singleton / reset
"""

from __future__ import annotations

import time

import pytest

from src.runtime.runtime_analytics import (
    RuntimeAnalytics,
    get_runtime_analytics,
    reset_runtime_analytics_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_runtime_analytics_for_tests()
    yield
    reset_runtime_analytics_for_tests()


def _exec(status="committed", intent="build_pyro_source",
          duration=1.0, rollback=False, errors=None, template=""):
    return {
        "intent": intent, "status": status, "duration_sec": duration,
        "op_count": 5, "template_id": template,
        "rollback_performed": rollback, "errors": errors or [],
    }


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def test_record_execution_returns_id():
    a = get_runtime_analytics()
    rid = a.record_execution(_exec())
    assert isinstance(rid, str) and len(rid) == 36


def test_record_validation_returns_id():
    a = get_runtime_analytics()
    rid = a.record_validation({"intent": "build_pyro_source", "valid": True,
                               "error_count": 0, "warning_count": 0, "risk_level": "low"})
    assert isinstance(rid, str) and len(rid) == 36


def test_record_worker_event_returns_id():
    a = get_runtime_analytics()
    rid = a.record_worker_event({"event_type": "acquired", "worker_id": "w1",
                                 "current_load": 1, "max_load": 4})
    assert isinstance(rid, str) and len(rid) == 36


# ---------------------------------------------------------------------------
# get_report
# ---------------------------------------------------------------------------

def test_get_report_empty_returns_all_keys():
    a = get_runtime_analytics()
    r = a.get_report()
    assert "execution_metrics"   in r
    assert "failure_metrics"     in r
    assert "resource_metrics"    in r
    assert "workflow_statistics" in r
    assert "generated_at"        in r


def test_execution_metrics_success_rate():
    a = get_runtime_analytics()
    a.record_execution(_exec("committed"))
    a.record_execution(_exec("committed"))
    a.record_execution(_exec("failed"))
    r = a.get_report()
    m = r["execution_metrics"]
    assert m["total_executions"] == 3
    assert m["success_count"] == 2
    assert abs(m["success_rate"] - 2/3) < 0.01


def test_failure_metrics_rollback_rate():
    a = get_runtime_analytics()
    a.record_execution(_exec("committed"))
    a.record_execution(_exec("rolled_back", rollback=True))
    r = a.get_report()
    fm = r["failure_metrics"]
    assert fm["total_rollbacks"] == 1
    assert abs(fm["rollback_rate"] - 0.5) < 0.01


def test_failure_metrics_top_failure_intents():
    a = get_runtime_analytics()
    for _ in range(3):
        a.record_execution(_exec("failed", intent="bad_intent"))
    r = a.get_report()
    intents = [x["intent"] for x in r["failure_metrics"]["top_failure_intents"]]
    assert "bad_intent" in intents


def test_resource_metrics_acquire_release():
    a = get_runtime_analytics()
    a.record_worker_event({"event_type": "acquired",  "worker_id": "w1", "current_load": 1, "max_load": 4})
    a.record_worker_event({"event_type": "released",  "worker_id": "w1", "current_load": 0, "max_load": 4})
    a.record_worker_event({"event_type": "stale",     "worker_id": "w2", "current_load": 0, "max_load": 4})
    r = a.get_report()
    rm = r["resource_metrics"]
    assert rm["acquire_count"] == 1
    assert rm["release_count"] == 1
    assert rm["stale_count"]   == 1


def test_workflow_statistics_by_intent():
    a = get_runtime_analytics()
    a.record_execution(_exec(intent="build_pyro_source"))
    a.record_execution(_exec(intent="build_pyro_source"))
    a.record_execution(_exec(intent="export_to_usd"))
    r = a.get_report()
    ws = r["workflow_statistics"]
    assert ws["by_intent"]["build_pyro_source"] == 2
    assert ws["by_intent"]["export_to_usd"] == 1


def test_workflow_statistics_by_status():
    a = get_runtime_analytics()
    a.record_execution(_exec("committed"))
    a.record_execution(_exec("failed"))
    r = a.get_report()
    ws = r["workflow_statistics"]
    assert ws["by_status"]["committed"] == 1
    assert ws["by_status"]["failed"] == 1


def test_workflow_statistics_validation_failure_rate():
    a = get_runtime_analytics()
    a.record_validation({"intent": "x", "valid": True,  "error_count": 0, "warning_count": 0, "risk_level": "low"})
    a.record_validation({"intent": "x", "valid": False, "error_count": 1, "warning_count": 0, "risk_level": "high"})
    r = a.get_report()
    ws = r["workflow_statistics"]
    assert ws["validation_total"] == 2
    assert ws["validation_failure_rate"] == 0.5


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

def test_get_execution_trends_within_window():
    a = get_runtime_analytics()
    a.record_execution(_exec("committed"))
    a.record_execution(_exec("failed"))
    trends = a.get_execution_trends(window_sec=300)
    assert trends["count"] == 2
    assert trends["success_rate"] == 0.5


def test_get_execution_trends_empty_window():
    a = get_runtime_analytics()
    trends = a.get_execution_trends(window_sec=300)
    assert trends["count"] == 0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    a = get_runtime_analytics()
    a.record_execution(_exec())
    a.record_validation({"intent": "x", "valid": True, "error_count": 0, "warning_count": 0, "risk_level": "low"})
    s = a.stats()
    assert "execution_records"  in s
    assert "validation_records" in s
    assert "worker_events"      in s
    assert s["execution_records"]  == 1
    assert s["validation_records"] == 1


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    assert get_runtime_analytics() is get_runtime_analytics()


def test_reset_creates_fresh():
    a = get_runtime_analytics()
    reset_runtime_analytics_for_tests()
    b = get_runtime_analytics()
    assert a is not b
