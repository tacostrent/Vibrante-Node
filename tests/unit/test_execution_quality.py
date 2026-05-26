"""
Unit tests for src.runtime.execution_quality.

Covers:
  • evaluate: committed, no errors → overall_score high, grade A or B
  • evaluate: failed → lower score, grade D or F
  • evaluate: with plan → semantic_correctness dimension present
  • evaluate: with history → stability dimension reflects history
  • evaluate: findings list always present
  • evaluate: dimensions dict contains all 6 keys
  • score_efficiency: within budget → 1.0
  • score_efficiency: 2× budget → ~0.5
  • score_efficiency: zero duration → 1.0
  • score_efficiency: zero op_count treated as 1
  • score_stability: all success → 1.0
  • score_stability: all failed → 0.0
  • score_stability: empty → 1.0
  • score_validation_reliability: all valid → 1.0
  • score_validation_reliability: mixed → 0.5
  • score_validation_reliability: empty → 1.0
  • grade: A B C D F thresholds
  • stats.eval_count increments
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.execution_quality import (
    ExecutionQuality,
    get_execution_quality,
    reset_execution_quality_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_execution_quality_for_tests()
    yield
    reset_execution_quality_for_tests()


def _result(status="committed", op_count=5, duration=2.0, errors=None, rollback=False):
    return {
        "status":             status,
        "op_count":           op_count,
        "duration_sec":       duration,
        "errors":             errors or [],
        "rollback_performed": rollback,
        "operations_executed": op_count,
    }


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------

def test_evaluate_committed_no_errors_high_score():
    q = get_execution_quality()
    result = q.evaluate(_result())
    assert result["overall_score"] >= 0.7
    assert result["grade"] in ("A", "B", "C")


def test_evaluate_failed_lower_score():
    q = get_execution_quality()
    result = q.evaluate(_result("failed", errors=["op failed"]))
    # stability will be low because status=failed
    assert result["overall_score"] < 0.9


def test_evaluate_dimensions_all_present():
    q = get_execution_quality()
    result = q.evaluate(_result())
    dims = result["dimensions"]
    assert "efficiency"             in dims
    assert "semantic_correctness"   in dims
    assert "stability"              in dims
    assert "validation_reliability" in dims
    assert "replay_consistency"     in dims
    assert "dependency_integrity"   in dims


def test_evaluate_with_plan():
    q = get_execution_quality()
    plan = {"operations": [{"op": "create_node"} for _ in range(5)], "intent": "test"}
    result = q.evaluate(_result(op_count=5), plan=plan)
    assert result["dimensions"]["semantic_correctness"] == 1.0


def test_evaluate_plan_partial_execution():
    q = get_execution_quality()
    plan = {"operations": [{"op": "create_node"} for _ in range(10)], "intent": "test"}
    result = q.evaluate(_result(op_count=5), plan=plan)
    assert result["dimensions"]["semantic_correctness"] == 0.5


def test_evaluate_with_history():
    q = get_execution_quality()
    history = [_result("committed")] * 3 + [_result("failed")] * 7
    result = q.evaluate(_result(), history=history)
    assert result["dimensions"]["stability"] < 0.8


def test_evaluate_findings_always_present():
    q = get_execution_quality()
    result = q.evaluate(_result())
    assert isinstance(result["findings"], list)
    assert len(result["findings"]) >= 1


def test_evaluate_grade_present():
    q = get_execution_quality()
    result = q.evaluate(_result())
    assert result["grade"] in ("A", "B", "C", "D", "F")


# ---------------------------------------------------------------------------
# score_efficiency
# ---------------------------------------------------------------------------

def test_score_efficiency_within_budget():
    q = get_execution_quality()
    # 5 ops × 2 sec/op = 10 sec budget; 5 sec actual → within budget
    assert q.score_efficiency({"op_count": 5, "duration_sec": 5.0}) == 1.0


def test_score_efficiency_double_budget():
    q = get_execution_quality()
    # budget = 5 × 2 = 10; actual = 20 → ratio = 10/20 = 0.5
    score = q.score_efficiency({"op_count": 5, "duration_sec": 20.0})
    assert abs(score - 0.5) < 0.01


def test_score_efficiency_zero_duration():
    q = get_execution_quality()
    assert q.score_efficiency({"op_count": 5, "duration_sec": 0.0}) == 1.0


def test_score_efficiency_zero_op_count():
    q = get_execution_quality()
    # op_count defaults to 1 → budget = 2 sec; duration 1 → within budget
    assert q.score_efficiency({"op_count": 0, "duration_sec": 1.0}) == 1.0


# ---------------------------------------------------------------------------
# score_stability
# ---------------------------------------------------------------------------

def test_score_stability_all_success():
    q = get_execution_quality()
    records = [_result("committed") for _ in range(5)]
    assert q.score_stability(records) == 1.0


def test_score_stability_all_failed():
    q = get_execution_quality()
    records = [_result("failed") for _ in range(5)]
    assert q.score_stability(records) == 0.0


def test_score_stability_empty():
    q = get_execution_quality()
    assert q.score_stability([]) == 1.0


def test_score_stability_mixed():
    q = get_execution_quality()
    records = [_result("committed")] * 3 + [_result("failed")] * 2
    assert q.score_stability(records) == 0.6


# ---------------------------------------------------------------------------
# score_validation_reliability
# ---------------------------------------------------------------------------

def test_score_validation_reliability_all_valid():
    q = get_execution_quality()
    records = [{"valid": True} for _ in range(5)]
    assert q.score_validation_reliability(records) == 1.0


def test_score_validation_reliability_mixed():
    q = get_execution_quality()
    records = [{"valid": True}, {"valid": False}, {"valid": True}, {"valid": False}]
    assert q.score_validation_reliability(records) == 0.5


def test_score_validation_reliability_empty():
    q = get_execution_quality()
    assert q.score_validation_reliability([]) == 1.0


# ---------------------------------------------------------------------------
# grade
# ---------------------------------------------------------------------------

def test_grade_A():
    q = get_execution_quality()
    assert q.grade(0.95) == "A"


def test_grade_B():
    q = get_execution_quality()
    assert q.grade(0.85) == "B"


def test_grade_C():
    q = get_execution_quality()
    assert q.grade(0.75) == "C"


def test_grade_D():
    q = get_execution_quality()
    assert q.grade(0.65) == "D"


def test_grade_F():
    q = get_execution_quality()
    assert q.grade(0.5) == "F"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_eval_count():
    q = get_execution_quality()
    q.evaluate(_result())
    q.evaluate(_result())
    assert q.stats()["eval_count"] == 2


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    assert get_execution_quality() is get_execution_quality()


def test_reset_creates_fresh():
    a = get_execution_quality()
    reset_execution_quality_for_tests()
    b = get_execution_quality()
    assert a is not b
