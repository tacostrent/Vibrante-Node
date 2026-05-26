"""
Unit tests for src.runtime.execution_explainer.

Covers:
  • explain_plan returns required keys + non-empty full_text
  • explain_plan surfaces warnings/errors/approval text
  • explain_plan hides approval_text when not required
  • explain_validation returns required keys
  • explain_validation labels valid/invalid
  • explain_approval returns status_line matching status
  • explain_execution returns required keys
  • explain_execution labels committed/rolled_back/validated
  • explain_review returns required keys
  • explain_review outcome labels
  • _op_to_human coverage for all supported op types
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.execution_explainer import (
    ExecutionExplainer,
    get_execution_explainer,
    reset_execution_explainer_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_execution_explainer_for_tests()
    yield
    reset_execution_explainer_for_tests()


def _make_plan(intent="build_pyro_source", ops=None, ok=True,
               warnings=None, errors=None, requires_approval=False,
               approval_reasons=None, reasoning=None):
    return {
        "intent":             intent,
        "ok":                 ok,
        "operations":         ops or [{"op": "create_node", "parent": "/obj", "type": "pyro", "name": "fire"}],
        "op_count":           len(ops or [1]),
        "parameters":         {"name": "fire"},
        "warnings":           warnings or [],
        "errors":             errors or [],
        "requires_approval":  requires_approval,
        "approval_reasons":   approval_reasons or [],
        "resource_estimate":  {"risk_level": "low", "estimated_cook_cost": 0.3},
        "reasoning":          reasoning or ["test reasoning"],
        "confidence":         0.9,
        "execution_strategy": {"strategy": "create_new", "rationale": "no existing"},
        "selected_template":  "pyro_source",
    }


# ---------------------------------------------------------------------------
# explain_plan
# ---------------------------------------------------------------------------

def test_explain_plan_required_keys():
    expl = get_execution_explainer()
    result = expl.explain_plan(_make_plan())
    for key in ("summary", "intent_line", "strategy_line", "operations_text",
                "warnings_text", "errors_text", "risk_summary",
                "approval_text", "reasoning_text", "full_text"):
        assert key in result, f"Missing key: {key}"


def test_explain_plan_full_text_non_empty():
    expl = get_execution_explainer()
    result = expl.explain_plan(_make_plan())
    assert len(result["full_text"]) > 50


def test_explain_plan_includes_warnings():
    expl = get_execution_explainer()
    plan = _make_plan(warnings=["something risky here"])
    result = expl.explain_plan(plan)
    assert any("risky" in t for t in result["warnings_text"])


def test_explain_plan_includes_errors():
    expl = get_execution_explainer()
    plan = _make_plan(errors=["constraint violated"])
    result = expl.explain_plan(plan)
    assert any("constraint" in t for t in result["errors_text"])


def test_explain_plan_approval_text_when_required():
    expl = get_execution_explainer()
    plan = _make_plan(requires_approval=True, approval_reasons=["High risk detected."])
    result = expl.explain_plan(plan)
    assert result["approval_text"] is not None
    assert "approval" in result["approval_text"].lower()


def test_explain_plan_no_approval_text_when_not_required():
    expl = get_execution_explainer()
    plan = _make_plan(requires_approval=False)
    result = expl.explain_plan(plan)
    assert result["approval_text"] is None


# ---------------------------------------------------------------------------
# explain_validation
# ---------------------------------------------------------------------------

def test_explain_validation_required_keys():
    expl = get_execution_explainer()
    result = expl.explain_validation({"valid": True, "errors": [], "warnings": [],
                                      "capability_gaps": [], "risk_level": "low"})
    for key in ("summary", "errors_text", "warnings_text", "capability_text", "full_text"):
        assert key in result, f"Missing key: {key}"


def test_explain_validation_passed_label():
    expl = get_execution_explainer()
    result = expl.explain_validation({"valid": True, "errors": [], "warnings": [],
                                      "capability_gaps": [], "risk_level": "low"})
    assert "PASSED" in result["summary"]


def test_explain_validation_failed_label():
    expl = get_execution_explainer()
    err = {"index": 0, "op": "create_node", "message": "missing parent"}
    result = expl.explain_validation({"valid": False, "errors": [err], "warnings": [],
                                      "capability_gaps": [], "risk_level": "medium"})
    assert "FAILED" in result["summary"]
    assert len(result["errors_text"]) == 1


# ---------------------------------------------------------------------------
# explain_approval
# ---------------------------------------------------------------------------

def test_explain_approval_required_keys():
    expl = get_execution_explainer()
    result = expl.explain_approval({"status": "pending", "approval_reasons": []})
    for key in ("summary", "status_line", "reasons_text", "full_text"):
        assert key in result, f"Missing key: {key}"


def test_explain_approval_approved_label():
    expl = get_execution_explainer()
    result = expl.explain_approval({"status": "approved", "approval_reasons": []})
    assert "approved" in result["status_line"].lower()


def test_explain_approval_rejected_label():
    expl = get_execution_explainer()
    result = expl.explain_approval({"status": "rejected", "approval_reasons": ["too risky"]})
    assert "rejected" in result["status_line"].lower()
    assert len(result["reasons_text"]) == 1


# ---------------------------------------------------------------------------
# explain_execution
# ---------------------------------------------------------------------------

def test_explain_execution_required_keys():
    expl = get_execution_explainer()
    result = expl.explain_execution({
        "status": "committed", "intent": "build_pyro_source",
        "operations_executed": [], "graph_diff": {}, "errors": [],
        "transaction_id": "abc-123",
    })
    for key in ("summary", "status_line", "ops_text", "diff_text", "full_text"):
        assert key in result, f"Missing key: {key}"


def test_explain_execution_committed_label():
    expl = get_execution_explainer()
    result = expl.explain_execution({"status": "committed", "intent": "x",
                                     "operations_executed": [], "graph_diff": {}, "errors": []})
    assert "committed" in result["status_line"].lower() or "✓" in result["status_line"]


def test_explain_execution_rolled_back_label():
    expl = get_execution_explainer()
    result = expl.explain_execution({"status": "rolled_back", "intent": "x",
                                     "operations_executed": [], "graph_diff": {}, "errors": []})
    assert "rolled" in result["status_line"].lower() or "↺" in result["status_line"]


def test_explain_execution_dry_run_label():
    expl = get_execution_explainer()
    result = expl.explain_execution({"status": "validated", "intent": "x",
                                     "operations_executed": [], "graph_diff": {}, "errors": []})
    assert "dry run" in result["status_line"].lower() or "validated" in result["status_line"].lower()


def test_explain_execution_diff_in_full_text():
    expl = get_execution_explainer()
    result = expl.explain_execution({
        "status": "committed", "intent": "x",
        "operations_executed": [],
        "graph_diff": {"created": ["/obj/new_node"], "modified": [], "deleted": []},
        "errors": [],
    })
    assert "/obj/new_node" in result["full_text"]


# ---------------------------------------------------------------------------
# explain_review
# ---------------------------------------------------------------------------

def test_explain_review_required_keys():
    expl = get_execution_explainer()
    result = expl.explain_review({"outcome": "success", "intent": "x",
                                  "findings": [], "intent_match_score": 1.0})
    for key in ("summary", "outcome_line", "findings_text", "full_text"):
        assert key in result, f"Missing key: {key}"


def test_explain_review_success_label():
    expl = get_execution_explainer()
    result = expl.explain_review({"outcome": "success", "intent": "x",
                                  "findings": [], "intent_match_score": 1.0})
    assert "✓" in result["outcome_line"] or "success" in result["outcome_line"].lower()


def test_explain_review_failure_label():
    expl = get_execution_explainer()
    result = expl.explain_review({"outcome": "failure", "intent": "x",
                                  "findings": ["Something went wrong."], "intent_match_score": 0.2})
    assert "✗" in result["outcome_line"] or "failure" in result["outcome_line"].lower()
    assert len(result["findings_text"]) == 1


# ---------------------------------------------------------------------------
# _op_to_human coverage
# ---------------------------------------------------------------------------

def test_op_to_human_all_types():
    from src.runtime.execution_explainer import _op_to_human
    ops = [
        {"op": "create_node", "parent": "/obj", "type": "geo", "name": "g1"},
        {"op": "set_parms", "node": "/obj/g1", "parms": {"tx": 1.0}},
        {"op": "connect_nodes", "from_node": "/obj/a", "to_node": "/obj/b", "out": 0, "in": 0},
        {"op": "delete_node", "path": "/obj/old"},
        {"op": "cook_node", "path": "/obj/geo1"},
        {"op": "set_display_flag", "path": "/obj/n", "on": True},
        {"op": "set_render_flag", "path": "/obj/n", "on": False},
        {"op": "layout_children", "path": "/obj"},
        {"op": "build_node_chain", "spec": {"nodes": [{"id": "n1"}], "connections": []}},
        {"op": "unknown_type"},
    ]
    for op in ops:
        desc = _op_to_human(op)
        assert isinstance(desc, str) and len(desc) > 0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_execution_explainer()
    b = get_execution_explainer()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_execution_explainer()
    reset_execution_explainer_for_tests()
    b = get_execution_explainer()
    assert a is not b
