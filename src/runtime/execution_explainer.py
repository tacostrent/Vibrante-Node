"""
Execution Explanation Layer (Tier 3)
======================================
Generate human-readable explanations for AI-generated plans, validation
results, constraints, and execution outcomes.

This module is purely TEMPLATE-BASED — no LLM calls, no bridge calls.
Its output is deterministic given the same inputs.

Critical for: inspectability, operator trust, audit trails, debugging.

Public API:
    get_execution_explainer() -> ExecutionExplainer
    reset_execution_explainer_for_tests()

    ExecutionExplainer.explain_plan(plan) -> dict
    ExecutionExplainer.explain_validation(validation_result) -> dict
    ExecutionExplainer.explain_approval(approval_state) -> dict
    ExecutionExplainer.explain_execution(execution_result) -> dict
    ExecutionExplainer.explain_review(review_result) -> dict
"""

import threading
from typing import Any, Dict, List, Optional


def _op_to_human(op: Dict[str, Any]) -> str:
    """Convert a single op dict to a one-line human description."""
    op_type = op.get("op", "?")

    if op_type == "create_node":
        return (
            f"Create '{op.get('type', '?')}' node"
            + (f" named '{op.get('name')}'" if op.get("name") else "")
            + f" inside '{op.get('parent', '?')}'"
        )
    if op_type == "set_parms":
        parms = op.get("parms", {})
        keys  = ", ".join(list(parms.keys())[:3])
        tail  = "…" if len(parms) > 3 else ""
        return f"Set parameter(s) [{keys}{tail}] on '{op.get('node', '?')}'"

    if op_type == "connect_nodes":
        return (
            f"Connect '{op.get('from_node', '?')}' → '{op.get('to_node', '?')}'"
            + f" (out={op.get('out', 0)}, in={op.get('in', op.get('input_idx', 0))})"
        )
    if op_type == "delete_node":
        return f"⚠ Delete node '{op.get('path', '?')}'"

    if op_type == "cook_node":
        return f"Cook node '{op.get('path', '?')}'"

    if op_type == "set_display_flag":
        state = "on" if op.get("on", True) else "off"
        return f"Set display flag {state} on '{op.get('path', '?')}'"

    if op_type == "set_render_flag":
        state = "on" if op.get("on", True) else "off"
        return f"Set render flag {state} on '{op.get('path', '?')}'"

    if op_type == "layout_children":
        return f"Auto-layout children of '{op.get('path', '?')}'"

    if op_type == "build_node_chain":
        spec = op.get("spec", {})
        node_count = len(spec.get("nodes", []))
        conn_count = len(spec.get("connections", []))
        return f"Build node chain: {node_count} node(s), {conn_count} connection(s)"

    return f"Execute op '{op_type}'"


def _risk_label(risk_level: str) -> str:
    return {
        "low":    "Low — minor impact, no special precautions needed.",
        "medium": "Medium — moderate impact; review operations before executing.",
        "high":   "High — significant impact; approval recommended.",
    }.get(risk_level, f"Unknown ({risk_level})")


class ExecutionExplainer:
    """Template-based human-readable explanation generator. Stateless."""

    def explain_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a human-readable explanation of an AI plan.

        Returns:
            {
                "summary":          str,
                "intent_line":      str,
                "strategy_line":    str,
                "operations_text":  list[str],
                "warnings_text":    list[str],
                "errors_text":      list[str],
                "risk_summary":     str,
                "approval_text":    str | None,
                "reasoning_text":   list[str],
                "full_text":        str,
            }
        """
        intent   = plan.get("intent") or "unknown"
        ok       = plan.get("ok", False)
        ops      = plan.get("operations", [])
        warnings = plan.get("warnings", [])
        errors   = plan.get("errors", [])
        strategy = plan.get("execution_strategy", {})
        resource = plan.get("resource_estimate", {})
        reasoning = plan.get("reasoning", [])

        intent_line = (
            f"Intent: '{intent}' (confidence={plan.get('confidence', 0):.0%})"
        )
        strategy_line = (
            f"Strategy: {strategy.get('strategy', 'create_new')} — {strategy.get('rationale', '')}"
        )

        ops_text = [f"  {i+1}. {_op_to_human(op)}" for i, op in enumerate(ops)]
        warn_text = [f"  ⚠ {w}" for w in warnings]
        err_text  = [f"  ✗ {e}" for e in errors]

        risk_summary = _risk_label(resource.get("risk_level", "low"))

        approval_text = None
        if plan.get("requires_approval"):
            reasons = plan.get("approval_reasons", [])
            approval_text = "Human approval required:\n" + "\n".join(f"  • {r}" for r in reasons)

        status_word = "Ready to execute" if ok else "Cannot execute"
        summary = (
            f"{status_word}: '{intent}' → {len(ops)} operation(s). "
            f"Template: {plan.get('selected_template') or 'semantic registry'}."
        )

        sections: List[str] = [
            f"=== AI Plan Explanation ===",
            intent_line,
            strategy_line,
            "",
            f"Operations ({len(ops)}):",
        ] + ops_text

        if warnings:
            sections += ["", "Warnings:"] + warn_text
        if errors:
            sections += ["", "Errors:"] + err_text
        if approval_text:
            sections += ["", approval_text]
        sections += [
            "",
            f"Risk: {risk_summary}",
            f"Cook cost estimate: {resource.get('estimated_cook_cost', 0.0):.2f}",
        ]
        if reasoning:
            sections += ["", "Planner reasoning:"] + [f"  • {r}" for r in reasoning]

        return {
            "summary":         summary,
            "intent_line":     intent_line,
            "strategy_line":   strategy_line,
            "operations_text": ops_text,
            "warnings_text":   warn_text,
            "errors_text":     err_text,
            "risk_summary":    risk_summary,
            "approval_text":   approval_text,
            "reasoning_text":  [f"• {r}" for r in reasoning],
            "full_text":       "\n".join(sections),
        }

    def explain_validation(self, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a human-readable explanation of a validation result.

        Returns:
            {
                "summary":    str,
                "errors_text": list[str],
                "warnings_text": list[str],
                "capability_text": list[str],
                "full_text":  str,
            }
        """
        valid    = validation_result.get("valid", False)
        errors   = validation_result.get("errors", [])
        warnings = validation_result.get("warnings", [])
        cap_gaps = validation_result.get("capability_gaps", [])

        def _fmt_issue(item: Any) -> str:
            if isinstance(item, dict):
                return f"Op[{item.get('index', '?')}] {item.get('op', '?')}: {item.get('message', '')}"
            return str(item)

        err_text  = [f"  ✗ {_fmt_issue(e)}" for e in errors]
        warn_text = [f"  ⚠ {_fmt_issue(w)}" for w in warnings]
        cap_text  = [f"  ? Missing capability: {c.get('capability', '?')} — {c.get('message', '')}"
                     for c in cap_gaps]

        summary = (
            f"Plan validation {'PASSED' if valid else 'FAILED'}. "
            f"{len(errors)} error(s), {len(warnings)} warning(s), {len(cap_gaps)} missing capability/ies."
        )
        risk = validation_result.get("risk_level", "low")
        summary += f" Risk: {risk}."

        sections: List[str] = ["=== Validation Report ===", summary]
        if err_text:
            sections += ["", "Errors (block execution):"] + err_text
        if warn_text:
            sections += ["", "Warnings (advisory):"] + warn_text
        if cap_text:
            sections += ["", "Missing Capabilities:"] + cap_text

        return {
            "summary":          summary,
            "errors_text":      err_text,
            "warnings_text":    warn_text,
            "capability_text":  cap_text,
            "full_text":        "\n".join(sections),
        }

    def explain_approval(self, approval_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a human-readable explanation of an approval state.

        Returns:
            {
                "summary":    str,
                "status_line": str,
                "reasons_text": list[str],
                "full_text":  str,
            }
        """
        status  = approval_state.get("status", "unknown")
        reasons = approval_state.get("approval_reasons", [])
        notes   = approval_state.get("notes", "")

        status_labels = {
            "pending":  "Pending — awaiting human review",
            "approved": "Approved — execution authorized",
            "rejected": "Rejected — execution blocked",
            "deferred": "Deferred — postponed for later review",
            "auto":     "Auto-approved — risk is below approval threshold",
        }
        status_line = status_labels.get(status, f"Status: {status}")

        reasons_text = [f"  • {r}" for r in reasons]
        sections: List[str] = ["=== Approval Status ===", status_line]
        if reasons:
            sections += ["", "Approval triggers:"] + reasons_text
        if notes:
            sections += ["", f"Notes: {notes}"]

        summary = f"Approval: {status_line}."
        if reasons:
            summary += f" Triggered by: {reasons[0]}"

        return {
            "summary":      summary,
            "status_line":  status_line,
            "reasons_text": reasons_text,
            "full_text":    "\n".join(sections),
        }

    def explain_execution(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a human-readable explanation of an execution result.

        Returns:
            {
                "summary":    str,
                "status_line": str,
                "ops_text":   list[str],
                "diff_text":  list[str],
                "full_text":  str,
            }
        """
        status  = execution_result.get("status", "unknown")
        intent  = execution_result.get("intent", "?")
        txn_id  = execution_result.get("transaction_id") or ""
        ops     = execution_result.get("operations_executed", [])
        diff    = execution_result.get("graph_diff", {})
        errors  = execution_result.get("errors", [])

        status_labels = {
            "committed":   "✓ Committed successfully",
            "rolled_back": "↺ Rolled back (error during execution)",
            "failed":      "✗ Failed",
            "validated":   "✓ Validated (dry run — no changes made)",
        }
        status_line = status_labels.get(status, f"Status: {status}")

        ops_text: List[str] = []
        for i, op in enumerate(ops):
            op_status = op.get("status", "?")
            marker    = "✓" if op_status == "ok" else "✗"
            ops_text.append(f"  {marker} {i+1}. {_op_to_human(op.get('params', op))}")

        diff_text: List[str] = []
        if diff.get("created"):
            diff_text.append(f"  Created: {', '.join(diff['created'][:5])}")
        if diff.get("modified"):
            diff_text.append(f"  Modified: {', '.join(diff['modified'][:5])}")
        if diff.get("deleted"):
            diff_text.append(f"  Deleted: {', '.join(diff['deleted'][:5])}")

        summary = (
            f"Execution of '{intent}': {status_line}. "
            f"{len(ops)} op(s) run."
        )
        if errors:
            summary += f" Error: {errors[0]}"

        sections: List[str] = [
            "=== Execution Report ===",
            f"Intent: {intent}",
            status_line,
        ]
        if txn_id:
            sections.append(f"Transaction: {txn_id[:8]}…")
        if ops_text:
            sections += ["", f"Operations ({len(ops)}):"] + ops_text
        if diff_text:
            sections += ["", "Scene changes:"] + diff_text
        if errors:
            sections += ["", "Errors:"] + [f"  ✗ {e}" for e in errors]

        return {
            "summary":    summary,
            "status_line": status_line,
            "ops_text":   ops_text,
            "diff_text":  diff_text,
            "full_text":  "\n".join(sections),
        }

    def explain_review(self, review_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a human-readable explanation of a post-execution review.

        Returns:
            {
                "summary":        str,
                "outcome_line":   str,
                "findings_text":  list[str],
                "full_text":      str,
            }
        """
        outcome   = review_result.get("outcome", "unknown")
        findings  = review_result.get("findings", [])
        intent    = review_result.get("intent", "?")
        match_score = review_result.get("intent_match_score", None)

        outcome_labels = {
            "success":        "✓ Execution matched intent",
            "partial":        "~ Partial success — some goals not met",
            "failure":        "✗ Execution did not match intent",
            "undetermined":   "? Could not determine outcome",
        }
        outcome_line = outcome_labels.get(outcome, f"Outcome: {outcome}")

        findings_text = [f"  • {f}" for f in findings]

        summary = f"Review of '{intent}': {outcome_line}."
        if match_score is not None:
            summary += f" Match score: {match_score:.0%}."

        sections: List[str] = [
            "=== Execution Review ===",
            f"Intent: {intent}",
            outcome_line,
        ]
        if match_score is not None:
            sections.append(f"Intent match score: {match_score:.0%}")
        if findings_text:
            sections += ["", "Findings:"] + findings_text

        return {
            "summary":       summary,
            "outcome_line":  outcome_line,
            "findings_text": findings_text,
            "full_text":     "\n".join(sections),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_EXPLAINER: Optional[ExecutionExplainer] = None
_LOCK = threading.Lock()


def get_execution_explainer() -> ExecutionExplainer:
    global _EXPLAINER
    with _LOCK:
        if _EXPLAINER is None:
            _EXPLAINER = ExecutionExplainer()
        return _EXPLAINER


def reset_execution_explainer_for_tests() -> None:
    global _EXPLAINER
    with _LOCK:
        _EXPLAINER = None
