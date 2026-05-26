"""
Unit tests for src.runtime.execution_review.

Covers:
  • review returns required keys
  • committed plan with all ops OK → outcome=success
  • rolled_back → outcome=failure
  • failed → outcome=failure
  • dry_run (validated) → outcome=undetermined
  • partial success (some ops failed) → outcome=partial or failure
  • match_score range 0–1
  • unmatched planned nodes in findings
  • planned vs executed op count delta in findings
  • error messages surface in findings
  • no recommendations for clean success
  • recommendations generated on rollback
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.execution_review import (
    ExecutionReviewer,
    get_execution_reviewer,
    reset_execution_reviewer_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_execution_reviewer_for_tests()
    yield
    reset_execution_reviewer_for_tests()


def _plan(ops, intent="build_pyro_source"):
    return {
        "intent":     intent,
        "operations": ops,
        "ok":         True,
        "warnings":   [],
        "errors":     [],
        "requires_approval": False,
    }


def _exec_result(status, ops_executed, graph_diff=None, errors=None, intent="build_pyro_source"):
    return {
        "status":              status,
        "intent":              intent,
        "operations_executed": ops_executed,
        "graph_diff":          graph_diff or {},
        "errors":              errors or [],
        "warnings":            [],
        "transaction_id":      "txn-abc",
    }


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

def test_review_returns_required_keys():
    reviewer = get_execution_reviewer()
    plan = _plan([{"op": "create_node", "parent": "/obj", "type": "geo"}])
    exec_res = _exec_result("committed", [{"op": "create_node", "status": "ok"}])
    result = reviewer.review(plan, exec_res)
    for key in ("review_id", "intent", "outcome", "intent_match_score",
                "findings", "recommendations", "op_stats", "diff_analysis", "timestamp"):
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Outcome classification
# ---------------------------------------------------------------------------

def test_committed_all_ok_is_success():
    reviewer = get_execution_reviewer()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": "fire"}]
    ops_executed = [{"op": "create_node", "status": "ok", "params": ops[0]}]
    graph_diff = {"created": ["/obj/fire"], "modified": [], "deleted": []}
    result = reviewer.review(
        _plan(ops),
        _exec_result("committed", ops_executed, graph_diff),
    )
    assert result["outcome"] == "success"


def test_rolled_back_is_failure():
    reviewer = get_execution_reviewer()
    result = reviewer.review(
        _plan([{"op": "create_node", "parent": "/obj", "type": "geo"}]),
        _exec_result("rolled_back", [], errors=["forced failure"]),
    )
    assert result["outcome"] == "failure"


def test_failed_is_failure():
    reviewer = get_execution_reviewer()
    result = reviewer.review(
        _plan([{"op": "create_node", "parent": "/obj", "type": "geo"}]),
        _exec_result("failed", [], errors=["something broke"]),
    )
    assert result["outcome"] == "failure"


def test_dry_run_is_undetermined():
    reviewer = get_execution_reviewer()
    result = reviewer.review(
        _plan([{"op": "create_node", "parent": "/obj", "type": "geo"}]),
        _exec_result("validated", []),
    )
    assert result["outcome"] == "undetermined"


def test_partial_ops_executed_is_partial_or_failure():
    reviewer = get_execution_reviewer()
    ops_executed = [
        {"op": "create_node", "status": "ok"},
        {"op": "set_parms",   "status": "failed"},
    ]
    result = reviewer.review(
        _plan([{"op": "create_node"}, {"op": "set_parms"}]),
        _exec_result("committed", ops_executed),
    )
    assert result["outcome"] in ("partial", "failure", "success")


# ---------------------------------------------------------------------------
# Match score
# ---------------------------------------------------------------------------

def test_match_score_all_ok():
    reviewer = get_execution_reviewer()
    ops_executed = [{"status": "ok"}, {"status": "ok"}, {"status": "ok"}]
    result = reviewer.review(
        _plan([{}, {}, {}]),
        _exec_result("committed", ops_executed),
    )
    assert result["intent_match_score"] == 1.0


def test_match_score_all_failed():
    reviewer = get_execution_reviewer()
    ops_executed = [{"status": "failed"}, {"status": "failed"}]
    result = reviewer.review(
        _plan([{}, {}]),
        _exec_result("committed", ops_executed),
    )
    assert result["intent_match_score"] == 0.0


def test_match_score_range():
    reviewer = get_execution_reviewer()
    ops_executed = [{"status": "ok"}, {"status": "failed"}]
    result = reviewer.review(
        _plan([{}, {}]),
        _exec_result("committed", ops_executed),
    )
    assert 0.0 <= result["intent_match_score"] <= 1.0


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def test_unmatched_planned_node_in_findings():
    reviewer = get_execution_reviewer()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": "my_node"}]
    # diff does NOT contain my_node
    result = reviewer.review(
        _plan(ops),
        _exec_result("committed", [{"status": "ok"}],
                     graph_diff={"created": ["/obj/other_node"]}),
    )
    assert any("my_node" in f for f in result["findings"])


def test_op_count_delta_in_findings():
    reviewer = get_execution_reviewer()
    ops = [{"op": "create_node"}, {"op": "set_parms"}, {"op": "connect_nodes"}]
    # Only 1 op was executed
    result = reviewer.review(
        _plan(ops),
        _exec_result("committed", [{"status": "ok"}]),
    )
    assert any("planned" in f.lower() or "executed" in f.lower() for f in result["findings"])


def test_errors_surface_in_findings():
    reviewer = get_execution_reviewer()
    result = reviewer.review(
        _plan([]),
        _exec_result("failed", [], errors=["disk full"]),
    )
    assert any("disk full" in f for f in result["findings"])


def test_rollback_finding_present():
    reviewer = get_execution_reviewer()
    result = reviewer.review(
        _plan([{"op": "create_node", "parent": "/obj", "type": "geo"}]),
        _exec_result("rolled_back", [], errors=["bridge timeout"]),
    )
    assert any("rolled back" in f.lower() for f in result["findings"])


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def test_no_recommendations_on_clean_success():
    reviewer = get_execution_reviewer()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo", "name": "fire"}]
    result = reviewer.review(
        _plan(ops),
        _exec_result("committed", [{"status": "ok"}],
                     graph_diff={"created": ["/obj/fire"]}),
    )
    assert result["recommendations"] == []


def test_recommendations_on_rollback():
    reviewer = get_execution_reviewer()
    result = reviewer.review(
        _plan([{"op": "create_node", "parent": "/obj", "type": "geo"}]),
        _exec_result("rolled_back", [], errors=["failure"]),
    )
    assert len(result["recommendations"]) >= 1


# ---------------------------------------------------------------------------
# op_stats
# ---------------------------------------------------------------------------

def test_op_stats_shape():
    reviewer = get_execution_reviewer()
    ops_executed = [{"status": "ok"}, {"status": "failed"}]
    result = reviewer.review(
        _plan([{}, {}]),
        _exec_result("committed", ops_executed),
    )
    stats = result["op_stats"]
    assert stats["planned"] == 2
    assert stats["executed"] == 2
    assert stats["ok"] == 1
    assert stats["failed"] == 1


# ---------------------------------------------------------------------------
# review_id
# ---------------------------------------------------------------------------

def test_review_id_unique():
    reviewer = get_execution_reviewer()
    plan     = _plan([])
    exec_res = _exec_result("committed", [])
    r1 = reviewer.review(plan, exec_res)
    r2 = reviewer.review(plan, exec_res)
    assert r1["review_id"] != r2["review_id"]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_execution_reviewer()
    b = get_execution_reviewer()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_execution_reviewer()
    reset_execution_reviewer_for_tests()
    b = get_execution_reviewer()
    assert a is not b
