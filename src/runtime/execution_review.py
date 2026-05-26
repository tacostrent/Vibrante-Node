"""
Self-Review System (Tier 3)
=============================
Post-execution structured review: did execution match intent?

NOT autonomous self-repair. The reviewer reads the execution result and the
original plan and produces a structured assessment that a human (or the next
AI planning cycle) can read and act on.

The reviewer is STATELESS and DETERMINISTIC. It reads scene lineage from
the cache and the execution result dict. No bridge calls, no LLM calls.

Scoring:
  - outcome:      "success" | "partial" | "failure" | "undetermined"
  - match_score:  0.0–1.0  (fraction of planned ops that completed OK)
  - findings:     list[str] of specific observations
  - recommendations: list[str] advisory next steps

Public API:
    get_execution_reviewer() -> ExecutionReviewer
    reset_execution_reviewer_for_tests()

    ExecutionReviewer.review(plan, execution_result) -> dict
"""

import threading
import time
import uuid
from typing import Any, Dict, List, Optional


def _score_from_ops(ops_executed: List[Dict[str, Any]]) -> float:
    """Fraction of executed ops that completed OK."""
    if not ops_executed:
        return 0.0
    ok_count = sum(1 for op in ops_executed if op.get("status") == "ok")
    return ok_count / len(ops_executed)


def _diff_matches_plan(
    plan_ops:   List[Dict[str, Any]],
    graph_diff: Dict[str, Any],
) -> List[str]:
    """Compare planned create_node ops against graph_diff.created.

    Returns list of unmatched expectation strings.
    """
    expected_creates = set()
    for op in plan_ops:
        if op.get("op") == "create_node" and op.get("name"):
            expected_creates.add(op["name"])

    created_paths = {p.rsplit("/", 1)[-1] for p in graph_diff.get("created", [])}
    unmatched = expected_creates - created_paths
    return [f"Planned node '{n}' not found in graph diff." for n in sorted(unmatched)]


def _classify_outcome(
    match_score:  float,
    status:       str,
    unmatched:    List[str],
) -> str:
    if status in ("rolled_back", "failed"):
        return "failure"
    if status == "validated":
        return "undetermined"
    if match_score >= 0.95 and not unmatched:
        return "success"
    if match_score >= 0.5:
        return "partial"
    return "failure"


class ExecutionReviewer:
    """Post-execution review engine. Stateless."""

    def review(
        self,
        plan:             Dict[str, Any],
        execution_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Review an execution result against the original plan.

        Args:
            plan:             Output of AIPlanner.plan() — the original intent + ops.
            execution_result: Output of SemanticExecutor.execute() or hou_mcp_transaction.

        Returns:
            {
                "review_id":          str,
                "intent":             str,
                "outcome":            "success" | "partial" | "failure" | "undetermined",
                "intent_match_score": float,
                "findings":           list[str],
                "recommendations":    list[str],
                "op_stats":           dict,
                "diff_analysis":      dict,
                "timestamp":          float,
            }
        """
        review_id = str(uuid.uuid4())
        ts        = time.time()
        findings: List[str] = []
        recommendations: List[str] = []

        intent      = plan.get("intent") or execution_result.get("intent") or "?"
        plan_ops    = plan.get("operations", [])
        ops_executed = execution_result.get("operations_executed", [])
        graph_diff  = execution_result.get("graph_diff", {})
        status      = execution_result.get("status", "unknown")
        errors      = execution_result.get("errors", [])
        warnings    = execution_result.get("warnings", [])

        # Compute match score.
        # If operations_executed is absent (e.g. older callers or semantic-
        # executor path that doesn't surface per-op records) but the transaction
        # committed, treat every op as successful — committed == all ops ok.
        if ops_executed:
            match_score = _score_from_ops(ops_executed)
        elif status == "committed":
            match_score = 1.0
        else:
            match_score = 0.0

        # Planned vs executed op count delta
        planned_count  = len(plan_ops)
        executed_count = len(ops_executed)

        op_stats = {
            "planned":  planned_count,
            "executed": executed_count,
            "ok":       sum(1 for op in ops_executed if op.get("status") == "ok"),
            "failed":   sum(1 for op in ops_executed if op.get("status") == "failed"),
        }

        if planned_count != executed_count and executed_count > 0:
            findings.append(
                f"Planned {planned_count} op(s), executed {executed_count}. "
                "Execution may have been interrupted."
            )

        # Check graph diff against plan
        unmatched = _diff_matches_plan(plan_ops, graph_diff)
        for msg in unmatched:
            findings.append(msg)

        diff_analysis = {
            "created_count":  len(graph_diff.get("created", [])),
            "modified_count": len(graph_diff.get("modified", [])),
            "deleted_count":  len(graph_diff.get("deleted", [])),
            "unmatched_nodes": unmatched,
        }

        # Error-based findings
        for err in errors:
            findings.append(f"Execution error: {err}")

        for warn in warnings:
            findings.append(f"Warning during execution: {warn}")

        # Status-based findings
        if status == "rolled_back":
            findings.append("Transaction was rolled back — all changes reverted.")
            recommendations.append("Review the error and fix the failing operation before retrying.")

        elif status == "committed":
            if not unmatched:
                findings.append("All planned nodes are present in the scene diff.")
            if op_stats["failed"] == 0:
                findings.append("All operations completed without errors.")

        elif status == "validated":
            findings.append("This was a dry run — no actual changes were made.")

        # Recommendations
        if unmatched:
            recommendations.append("Verify the missing node(s) in Houdini directly.")
        if match_score < 0.5 and status not in ("rolled_back",):
            recommendations.append(
                "Low match score — consider re-running the plan after reviewing the errors."
            )
        if plan.get("requires_approval") and status == "committed":
            recommendations.append(
                "This plan required approval. Ensure the approval was legitimate before referencing its output."
            )

        outcome = _classify_outcome(match_score, status, unmatched)

        return {
            "review_id":          review_id,
            "intent":             intent,
            "outcome":            outcome,
            "intent_match_score": round(match_score, 3),
            "findings":           findings,
            "recommendations":    recommendations,
            "op_stats":           op_stats,
            "diff_analysis":      diff_analysis,
            "timestamp":          ts,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_REVIEWER: Optional[ExecutionReviewer] = None
_LOCK = threading.Lock()


def get_execution_reviewer() -> ExecutionReviewer:
    global _REVIEWER
    with _LOCK:
        if _REVIEWER is None:
            _REVIEWER = ExecutionReviewer()
        return _REVIEWER


def reset_execution_reviewer_for_tests() -> None:
    global _REVIEWER
    with _LOCK:
        _REVIEWER = None
