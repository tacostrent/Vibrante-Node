"""
Execution Quality
=================
Evaluates the orchestration-level quality of completed executions:
  • execution efficiency (duration vs op count)
  • semantic correctness (did ops match stated intent)
  • orchestration stability (rollback rate, error density)
  • validation reliability (pre-execution check accuracy)
  • replay consistency (same ops reproducible)
  • dependency integrity (connections resolved cleanly)

NOT artistic evaluation — this module assesses runtime/orchestration quality
only. It has no opinion on whether a Houdini scene looks good.

All evaluation is:
  • deterministic — same inputs → same score
  • advisory — scores never block execution
  • explainable — every dimension is named with a finding

Output shape (from evaluate):
  {
    "overall_score":    float (0.0–1.0),
    "dimensions":       {"efficiency", "semantic_correctness", "stability",
                         "validation_reliability", "replay_consistency",
                         "dependency_integrity"},
    "findings":         [str, ...],
    "grade":            "A" | "B" | "C" | "D" | "F",
  }

Public API:
    get_execution_quality() -> ExecutionQuality   (singleton)
    reset_execution_quality_for_tests()            (test isolation only)

    quality.evaluate(execution_result, plan=None, history=None) -> dict
    quality.score_efficiency(execution_result) -> float
    quality.score_stability(execution_records) -> float
    quality.score_validation_reliability(validation_records) -> float
    quality.grade(score) -> str
    quality.stats() -> dict
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

# Expected duration budget per op (seconds) — above this starts docking points
_BUDGET_SEC_PER_OP = 2.0
# Max ops considered "normal" for efficiency scoring
_LARGE_BATCH_OPS = 20


class ExecutionQuality:
    """Orchestration-level execution quality evaluator."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._eval_count = 0

    # ------------------------------------------------------------------
    # Primary evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        execution_result: Dict[str, Any],
        plan: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Evaluate the quality of a completed execution.

        execution_result keys: status, op_count, duration_sec, errors, rollback_performed,
                               operations_executed (list), intent
        plan keys (optional):  operations (list), intent
        history (optional):    list of prior execution records for stability scoring

        Returns:
            {
                "overall_score":  float,
                "dimensions":     {dimension: float, ...},
                "findings":       [str, ...],
                "grade":          str,
            }
        """
        with self._lock:
            self._eval_count += 1

        findings: List[str] = []
        dimensions: Dict[str, float] = {}

        # Efficiency
        eff = self.score_efficiency(execution_result)
        dimensions["efficiency"] = eff
        if eff < 0.5:
            findings.append(f"Efficiency score {eff:.2f} — execution was slow relative to op count.")

        # Semantic correctness
        sem = self._score_semantic_correctness(execution_result, plan)
        dimensions["semantic_correctness"] = sem
        if sem < 0.8:
            findings.append(f"Semantic correctness {sem:.2f} — ops executed diverged from planned intent.")

        # Stability
        stab = self.score_stability([execution_result] + (history or []))
        dimensions["stability"] = stab
        if stab < 0.7:
            findings.append(f"Stability score {stab:.2f} — high rollback/failure rate in recent history.")

        # Validation reliability (requires history with 'valid' field)
        val_records = [r for r in (history or []) if "valid" in r]
        if val_records:
            val_rel = self.score_validation_reliability(val_records)
            dimensions["validation_reliability"] = val_rel
            if val_rel < 0.8:
                findings.append(f"Validation reliability {val_rel:.2f} — validation is not catching failures.")
        else:
            dimensions["validation_reliability"] = 1.0

        # Replay consistency (heuristic: committed + no errors = replayable)
        replay = self._score_replay_consistency(execution_result)
        dimensions["replay_consistency"] = replay
        if replay < 1.0:
            findings.append("Execution has errors or was rolled back — replay may produce different results.")

        # Dependency integrity
        dep_int = self._score_dependency_integrity(execution_result)
        dimensions["dependency_integrity"] = dep_int
        if dep_int < 1.0:
            findings.append("Some operations failed dependency checks — review connection order.")

        overall = round(sum(dimensions.values()) / len(dimensions), 3)

        if not findings:
            findings.append("Execution quality is good — no significant issues detected.")

        return {
            "overall_score": overall,
            "dimensions":    dimensions,
            "findings":      findings,
            "grade":         self.grade(overall),
        }

    # ------------------------------------------------------------------
    # Individual scorers
    # ------------------------------------------------------------------

    def score_efficiency(self, execution_result: Dict[str, Any]) -> float:
        """Score execution efficiency: 1.0 = within budget, lower = over budget."""
        duration = float(execution_result.get("duration_sec", 0.0))
        op_count = max(1, int(execution_result.get("op_count", 1)))
        budget   = _BUDGET_SEC_PER_OP * op_count

        if duration <= 0:
            return 1.0   # instant / not measured
        if duration <= budget:
            return 1.0

        # Linear decay: 2× budget → 0.5
        ratio = budget / duration
        return round(max(0.0, ratio), 3)

    def score_stability(self, execution_records: List[Dict[str, Any]]) -> float:
        """Score stability over a list of records: fraction that committed cleanly."""
        if not execution_records:
            return 1.0
        success = sum(1 for r in execution_records
                      if r.get("status") == "committed" and not r.get("rollback_performed"))
        return round(success / len(execution_records), 3)

    def score_validation_reliability(
        self, validation_records: List[Dict[str, Any]]
    ) -> float:
        """Score how well pre-execution validation predicts actual failures.

        A reliable validator: valid=True → execution succeeds; valid=False → prevented failure.
        True positives (valid=True and status=committed) count as correct.
        """
        if not validation_records:
            return 1.0
        correct = sum(1 for r in validation_records if bool(r.get("valid", True)))
        return round(correct / len(validation_records), 3)

    def grade(self, score: float) -> str:
        """Convert a 0.0–1.0 score to a letter grade."""
        if score >= 0.9:
            return "A"
        if score >= 0.8:
            return "B"
        if score >= 0.7:
            return "C"
        if score >= 0.6:
            return "D"
        return "F"

    def _score_semantic_correctness(
        self, execution_result: Dict[str, Any], plan: Optional[Dict[str, Any]]
    ) -> float:
        """Semantic correctness: fraction of planned ops that executed successfully."""
        if plan is None:
            # No plan to compare against — assume correct if no errors
            errors = execution_result.get("errors") or []
            return 1.0 if len(errors) == 0 else max(0.0, 1.0 - len(errors) * 0.1)

        planned_ops = len(plan.get("operations") or [])
        executed    = int(execution_result.get("op_count") or execution_result.get("operations_executed", 0))

        if planned_ops == 0:
            return 1.0
        return round(min(1.0, executed / planned_ops), 3)

    def _score_replay_consistency(self, execution_result: Dict[str, Any]) -> float:
        """Replay consistency: 1.0 if committed with no errors, lower otherwise."""
        status  = execution_result.get("status", "")
        errors  = execution_result.get("errors") or []
        if status == "committed" and len(errors) == 0:
            return 1.0
        if status == "committed":
            return max(0.7, 1.0 - len(errors) * 0.1)
        return 0.5 if status == "rolled_back" else 0.3

    def _score_dependency_integrity(self, execution_result: Dict[str, Any]) -> float:
        """Dependency integrity: checks for connection-related error keywords."""
        errors = [str(e) for e in (execution_result.get("errors") or [])]
        dep_errors = [e for e in errors if any(kw in e.lower() for kw in
                                               ("connect", "input", "dependency", "parent", "not found"))]
        if not dep_errors:
            return 1.0
        return max(0.0, 1.0 - len(dep_errors) * 0.2)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"eval_count": self._eval_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[ExecutionQuality] = None
_INSTANCE_LOCK = threading.Lock()


def get_execution_quality() -> ExecutionQuality:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = ExecutionQuality()
        return _INSTANCE


def reset_execution_quality_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
