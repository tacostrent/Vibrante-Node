"""
Workflow Optimizer
==================
Advisory-only analysis of historical workflow executions to recommend more
efficient execution paths, lower-risk operation variants, and better template
selection.

This module NEVER:
  • modifies execution plans directly
  • calls the bridge / houdini_runtime
  • interacts with TransactionManager or ExecutionScheduler
  • makes autonomous decisions

It ONLY produces structured recommendations that a human or the planning
pipeline can inspect, accept, or discard.

Public API:
    get_workflow_optimizer() -> WorkflowOptimizer   (singleton)
    reset_workflow_optimizer_for_tests()             (test isolation only)

    optimizer.analyze_plan(operations, context=None) -> dict
    optimizer.recommend_alternatives(intent, operations, context=None) -> dict
    optimizer.score_template(template_id, context=None) -> dict
    optimizer.get_optimization_history(limit=20) -> list[dict]
    optimizer.record_outcome(plan_id, outcome, metadata=None) -> str
    optimizer.stats() -> dict
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Risk thresholds (mirrors validation_engine weights)
# ---------------------------------------------------------------------------

_OP_RISK_WEIGHTS: Dict[str, int] = {
    "create_node":      0,
    "set_parms":        1,
    "connect_nodes":    1,
    "delete_node":      10,
    "set_display_flag": 0,
    "set_render_flag":  0,
    "cook_node":        1,
    "layout_children":  0,
    "build_node_chain": 2,
}

_HIGH_RISK = 10
_MEDIUM_RISK = 3

# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------


class WorkflowOptimizer:
    """Advisory workflow execution optimizer."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: List[Dict[str, Any]] = []   # recorded outcomes
        self._template_scores: Dict[str, List[float]] = defaultdict(list)
        self._intent_success: Dict[str, List[bool]] = defaultdict(list)
        self._max_history = 500

    # ------------------------------------------------------------------
    # Plan analysis
    # ------------------------------------------------------------------

    def analyze_plan(
        self,
        operations: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze an operation list and return optimisation recommendations.

        Returns:
            {
                "risk_score":        int,
                "risk_level":        "low" | "medium" | "high",
                "op_count":          int,
                "delete_count":      int,
                "optimization_tips": [str, ...],
                "reorder_suggested": bool,
                "batch_suggested":   bool,
                "summary":           str,
            }
        """
        if not operations:
            return self._empty_analysis()

        tips: List[str] = []
        risk_score = 0
        delete_count = 0
        cook_count = 0
        create_count = 0
        connect_count = 0

        for op in operations:
            if not isinstance(op, dict):
                continue
            op_type = op.get("op", "")
            risk_score += _OP_RISK_WEIGHTS.get(op_type, 0)
            if op_type == "delete_node":
                delete_count += 1
            elif op_type == "cook_node":
                cook_count += 1
            elif op_type == "create_node":
                create_count += 1
            elif op_type == "connect_nodes":
                connect_count += 1

        # Reorder suggestion: deletes before cooks avoids cooking doomed nodes
        ops_by_type = [op.get("op", "") for op in operations if isinstance(op, dict)]
        last_delete = max((i for i, t in enumerate(ops_by_type) if t == "delete_node"), default=-1)
        first_cook = min((i for i, t in enumerate(ops_by_type) if t == "cook_node"), default=len(ops_by_type))
        reorder_suggested = last_delete > first_cook and delete_count > 0 and cook_count > 0

        if reorder_suggested:
            tips.append("Move delete_node ops before cook_node ops to avoid cooking nodes that will be removed.")

        # Batch suggestion: many set_parms on same node
        node_parm_counts: Dict[str, int] = defaultdict(int)
        for op in operations:
            if isinstance(op, dict) and op.get("op") == "set_parms":
                node_parm_counts[op.get("node", "")] += 1
        if any(v > 3 for v in node_parm_counts.values()):
            tips.append("Multiple set_parms calls on the same node — consolidate into a single call.")
            batch_suggested = True
        else:
            batch_suggested = False

        if delete_count > 5:
            tips.append(f"{delete_count} delete_node ops detected — consider using build_node_chain to reconstruct instead.")

        if cook_count > 3:
            tips.append(f"{cook_count} cook_node ops — cook only the final output node where possible.")

        # Risk level
        if risk_score >= _HIGH_RISK:
            risk_level = "high"
        elif risk_score >= _MEDIUM_RISK:
            risk_level = "medium"
        else:
            risk_level = "low"

        if risk_level == "high":
            tips.append("High-risk batch detected — consider splitting into smaller transactions with approval gates.")

        summary = (
            f"{len(operations)} ops, risk={risk_level}"
            + (f", {len(tips)} tip(s)" if tips else "")
        )

        return {
            "risk_score":        risk_score,
            "risk_level":        risk_level,
            "op_count":          len(operations),
            "delete_count":      delete_count,
            "optimization_tips": tips,
            "reorder_suggested": reorder_suggested,
            "batch_suggested":   batch_suggested,
            "summary":           summary,
        }

    def _empty_analysis(self) -> Dict[str, Any]:
        return {
            "risk_score": 0, "risk_level": "low", "op_count": 0,
            "delete_count": 0, "optimization_tips": [], "reorder_suggested": False,
            "batch_suggested": False, "summary": "empty operation list",
        }

    # ------------------------------------------------------------------
    # Alternative recommendations
    # ------------------------------------------------------------------

    def recommend_alternatives(
        self,
        intent: str,
        operations: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Suggest alternative execution strategies for a given intent.

        Returns:
            {
                "intent":        str,
                "alternatives":  [{"strategy", "description", "risk_reduction", "notes"}, ...],
                "preferred":     str | None,   # strategy id of top recommendation
                "reasoning":     [str, ...],
            }
        """
        alternatives = []
        reasoning = []

        analysis = self.analyze_plan(operations, context)
        risk_level = analysis["risk_level"]

        # Strategy: dry_run first
        alternatives.append({
            "strategy": "dry_run_first",
            "description": "Execute with dry_run=True to validate before committing.",
            "risk_reduction": "high",
            "notes": "Zero side-effects; reveals validation errors before any mutation.",
        })
        reasoning.append("dry_run_first is always safe to recommend for initial verification.")

        # Strategy: split batch
        if len(operations) > 10:
            alternatives.append({
                "strategy": "split_batch",
                "description": f"Split {len(operations)} ops into smaller batches of ≤10 per transaction.",
                "risk_reduction": "medium",
                "notes": "Smaller transactions reduce rollback cost and aid debugging.",
            })
            reasoning.append("Large op batches increase rollback cost when a single op fails.")

        # Strategy: use template
        with self._lock:
            template_history = dict(self._template_scores)

        best_template: Optional[str] = None
        best_score = 0.0
        for tid, scores in template_history.items():
            if scores:
                avg = sum(scores) / len(scores)
                if avg > best_score and intent in tid:
                    best_score = avg
                    best_template = tid

        if best_template:
            alternatives.append({
                "strategy": "use_template",
                "description": f"Use workflow template '{best_template}' (avg score {best_score:.2f}).",
                "risk_reduction": "medium",
                "notes": "Templates encode known-good operation sequences.",
            })
            reasoning.append(f"Template '{best_template}' has a positive historical score for this intent.")

        # Strategy: transaction wrapping
        if risk_level == "high":
            alternatives.append({
                "strategy": "wrap_transaction",
                "description": "Wrap all ops in a hou_mcp_transaction with rollback_on_error=True.",
                "risk_reduction": "high",
                "notes": "Ensures partial mutations are undone on failure.",
            })
            reasoning.append("High-risk ops require transaction boundaries for safe rollback.")

        preferred = "dry_run_first" if risk_level in ("medium", "high") else None

        return {
            "intent":       intent,
            "alternatives": alternatives,
            "preferred":    preferred,
            "reasoning":    reasoning,
        }

    # ------------------------------------------------------------------
    # Template scoring
    # ------------------------------------------------------------------

    def score_template(
        self,
        template_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return historical performance data for a workflow template.

        Returns:
            {
                "template_id":  str,
                "uses":         int,
                "avg_score":    float,
                "min_score":    float,
                "max_score":    float,
                "recommendation": "preferred" | "acceptable" | "avoid" | "unknown",
            }
        """
        with self._lock:
            scores = list(self._template_scores.get(template_id, []))

        if not scores:
            return {
                "template_id": template_id, "uses": 0,
                "avg_score": 0.0, "min_score": 0.0, "max_score": 0.0,
                "recommendation": "unknown",
            }

        avg = sum(scores) / len(scores)
        rec = "preferred" if avg >= 0.8 else "acceptable" if avg >= 0.5 else "avoid"
        return {
            "template_id":    template_id,
            "uses":           len(scores),
            "avg_score":      round(avg, 3),
            "min_score":      round(min(scores), 3),
            "max_score":      round(max(scores), 3),
            "recommendation": rec,
        }

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        plan_id: str,
        outcome: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record the result of a plan execution for future optimisation.

        outcome: "success" | "partial" | "failure" | "rolled_back"
        Returns the record id.
        """
        if outcome not in ("success", "partial", "failure", "rolled_back"):
            raise ValueError(f"Invalid outcome: '{outcome}'")

        record_id = str(uuid.uuid4())
        score = {"success": 1.0, "partial": 0.5, "failure": 0.0, "rolled_back": 0.1}[outcome]

        md = metadata or {}
        record = {
            "id":        record_id,
            "plan_id":   plan_id,
            "outcome":   outcome,
            "score":     score,
            "intent":    md.get("intent", ""),
            "template":  md.get("template_id", ""),
            "op_count":  md.get("op_count", 0),
            "timestamp": time.time(),
        }

        with self._lock:
            self._history.append(record)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

            # Update template scores
            if record["template"]:
                self._template_scores[record["template"]].append(score)

            # Update intent success
            if record["intent"]:
                self._intent_success[record["intent"]].append(outcome == "success")

        return record_id

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_optimization_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent outcome records, newest first."""
        with self._lock:
            records = list(self._history)
        records.sort(key=lambda r: r["timestamp"], reverse=True)
        return records[:limit]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._history)
            outcomes: Dict[str, int] = defaultdict(int)
            for r in self._history:
                outcomes[r["outcome"]] += 1
            template_count = len(self._template_scores)
            intent_count = len(self._intent_success)

        return {
            "total_records":  total,
            "by_outcome":     dict(outcomes),
            "template_count": template_count,
            "intent_count":   intent_count,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[WorkflowOptimizer] = None
_INSTANCE_LOCK = threading.Lock()


def get_workflow_optimizer() -> WorkflowOptimizer:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = WorkflowOptimizer()
        return _INSTANCE


def reset_workflow_optimizer_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
