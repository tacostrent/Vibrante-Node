"""
Predictive Execution
====================
Heuristic-based pre-execution risk prediction. Predicts likely failures,
resource exhaustion, dependency conflicts, scheduler congestion, and high
rollback probability BEFORE any execution begins.

All predictions are:
  • heuristic-based — no opaque ML models
  • explainable — every factor is named and described
  • deterministic — identical input → identical output
  • advisory — predictions never block execution directly

This module NEVER:
  • executes operations or calls the bridge
  • modifies plans
  • interacts with TransactionManager

Output shape (from predict):
  {
    "predicted_risk":    "low" | "medium" | "high",
    "failure_probability": float (0.0–1.0),
    "risk_factors":     [{"factor", "severity", "explanation"}, ...],
    "recommendations":  [str, ...],
    "confidence":       float (0.0–1.0),
  }

Public API:
    get_predictive_engine() -> PredictiveExecution   (singleton)
    reset_predictive_engine_for_tests()               (test isolation only)

    engine.predict(operations, context=None) -> dict
    engine.predict_resource_pressure(operations) -> dict
    engine.predict_dependency_conflicts(operations) -> dict
    engine.predict_scheduler_congestion(queue_depth) -> dict
    engine.stats() -> dict
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Heuristic thresholds
# ---------------------------------------------------------------------------

_LARGE_BATCH         = 20    # ops
_HIGH_DELETE_COUNT   = 5
_HIGH_COOK_COUNT     = 4
_HIGH_RISK_SCORE     = 10
_CONGESTION_DEPTH    = 5     # items in scheduler queue
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


class PredictiveExecution:
    """Heuristic failure prediction engine."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._prediction_count = 0

    # ------------------------------------------------------------------
    # Primary prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        operations: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Predict execution risk for a batch of operations.

        Returns:
            {
                "predicted_risk":      "low" | "medium" | "high",
                "failure_probability": float,
                "risk_factors":        [{"factor", "severity", "explanation"}, ...],
                "recommendations":     [str, ...],
                "confidence":          float,
            }
        """
        with self._lock:
            self._prediction_count += 1

        if not operations:
            return {
                "predicted_risk": "low",
                "failure_probability": 0.0,
                "risk_factors": [],
                "recommendations": ["Add operations to the plan before executing."],
                "confidence": 1.0,
            }

        risk_factors: List[Dict[str, Any]] = []
        recommendations: List[str] = []
        probability_accumulator = 0.0

        context = context or {}

        # --- Factor: large batch ---
        if len(operations) >= _LARGE_BATCH:
            risk_factors.append({
                "factor":      "large_batch",
                "severity":    "medium",
                "explanation": f"{len(operations)} ops in a single transaction increases rollback cost.",
            })
            probability_accumulator += 0.15
            recommendations.append(f"Split the {len(operations)}-op batch into smaller transactions of ≤10 ops.")

        # --- Factor: high delete count ---
        delete_count = sum(1 for op in operations if isinstance(op, dict) and op.get("op") == "delete_node")
        if delete_count >= _HIGH_DELETE_COUNT:
            risk_factors.append({
                "factor":      "high_delete_count",
                "severity":    "high",
                "explanation": f"{delete_count} delete_node ops — deletes are irreversible in Tier 1.",
            })
            probability_accumulator += 0.30
            recommendations.append("Verify all delete targets before execution; deletes cannot be rolled back.")

        # --- Factor: cook before connect ---
        ops_types = [op.get("op", "") if isinstance(op, dict) else "" for op in operations]
        cook_idx   = [i for i, t in enumerate(ops_types) if t == "cook_node"]
        connect_idx = [i for i, t in enumerate(ops_types) if t == "connect_nodes"]
        if cook_idx and connect_idx and min(cook_idx) < max(connect_idx):
            risk_factors.append({
                "factor":      "cook_before_connect",
                "severity":    "medium",
                "explanation": "cook_node appears before some connect_nodes — cooking an incomplete network.",
            })
            probability_accumulator += 0.12
            recommendations.append("Reorder: complete all connect_nodes before any cook_node ops.")

        # --- Factor: unknown op types ---
        unknown_ops = [op.get("op", "?") for op in operations
                       if isinstance(op, dict) and op.get("op") not in _OP_RISK_WEIGHTS]
        if unknown_ops:
            risk_factors.append({
                "factor":      "unknown_op_types",
                "severity":    "high",
                "explanation": f"Unknown op types detected: {list(set(unknown_ops))} — likely to fail validation.",
            })
            probability_accumulator += 0.50

        # --- Factor: risk score ---
        total_risk = sum(_OP_RISK_WEIGHTS.get(op.get("op", ""), 0)
                         for op in operations if isinstance(op, dict))
        if total_risk >= _HIGH_RISK_SCORE:
            risk_factors.append({
                "factor":      "high_risk_score",
                "severity":    "high",
                "explanation": f"Cumulative risk score {total_risk} ≥ {_HIGH_RISK_SCORE} (delete-heavy batch).",
            })
            probability_accumulator += 0.20
            recommendations.append("Enable rollback_on_error and dry_run validation before committing.")

        # --- Factor: dependency conflict hints from context ---
        existing_nodes = set(context.get("existing_node_paths", []))
        for op in operations:
            if not isinstance(op, dict):
                continue
            if op.get("op") == "connect_nodes":
                frm = op.get("from", "")
                to  = op.get("to", "")
                if frm and frm not in existing_nodes and frm not in self._get_created_paths(operations):
                    risk_factors.append({
                        "factor":      "missing_source_node",
                        "severity":    "high",
                        "explanation": f"connect_nodes from='{frm}' — source not in existing or created nodes.",
                    })
                    probability_accumulator += 0.25
                    recommendations.append(f"Ensure '{frm}' is created before connecting.")
                    break  # one instance is enough to flag

        probability = min(1.0, probability_accumulator)
        predicted_risk = "high" if probability >= 0.5 else "medium" if probability >= 0.2 else "low"
        confidence = max(0.5, 1.0 - 0.05 * len(risk_factors))

        return {
            "predicted_risk":      predicted_risk,
            "failure_probability": round(probability, 3),
            "risk_factors":        risk_factors,
            "recommendations":     recommendations,
            "confidence":          round(confidence, 3),
        }

    def _get_created_paths(self, operations: List[Dict]) -> set:
        """Extract path stubs from create_node ops in the batch."""
        paths: set = set()
        for op in operations:
            if isinstance(op, dict) and op.get("op") == "create_node":
                parent = op.get("parent", "")
                name   = op.get("name", "")
                if parent and name:
                    paths.add(f"{parent.rstrip('/')}/{name}")
        return paths

    # ------------------------------------------------------------------
    # Resource pressure prediction
    # ------------------------------------------------------------------

    def predict_resource_pressure(
        self, operations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Estimate resource pressure from operation types.

        Returns:
            {
                "memory_pressure":  "low" | "medium" | "high",
                "cook_pressure":    "low" | "medium" | "high",
                "estimated_cooks":  int,
                "heavy_ops":        [str, ...],
                "notes":            [str, ...],
            }
        """
        cook_count = 0
        chain_count = 0
        heavy_ops: List[str] = []
        notes: List[str] = []

        _heavy_types = {"pyro", "flip", "vellum", "ocean", "crowd", "smoke"}

        for op in operations:
            if not isinstance(op, dict):
                continue
            op_type = op.get("op", "")
            if op_type == "cook_node":
                cook_count += 1
            elif op_type == "build_node_chain":
                chain_count += 1
                # Check for heavy node types inside spec
                spec = op.get("spec", {})
                for node in (spec.get("nodes") or []):
                    if isinstance(node, dict) and node.get("type", "") in _heavy_types:
                        heavy_ops.append(node["type"])
            elif op_type == "create_node":
                ntype = op.get("type", "")
                if ntype in _heavy_types:
                    heavy_ops.append(ntype)

        if cook_count > _HIGH_COOK_COUNT or heavy_ops:
            cook_pressure = "high"
            notes.append(f"{cook_count} cook operations — high session impact expected.")
        elif cook_count > 1:
            cook_pressure = "medium"
        else:
            cook_pressure = "low"

        memory_pressure = "high" if heavy_ops else "medium" if chain_count > 2 else "low"
        if memory_pressure == "high":
            notes.append(f"Heavy node types detected: {list(set(heavy_ops))} — significant memory expected.")

        return {
            "memory_pressure": memory_pressure,
            "cook_pressure":   cook_pressure,
            "estimated_cooks": cook_count,
            "heavy_ops":       list(set(heavy_ops)),
            "notes":           notes,
        }

    # ------------------------------------------------------------------
    # Dependency conflict prediction
    # ------------------------------------------------------------------

    def predict_dependency_conflicts(
        self, operations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Predict dependency ordering conflicts within a batch.

        Returns:
            {
                "conflicts":        [{"type", "op_index", "explanation"}, ...],
                "conflict_count":   int,
                "safe":             bool,
            }
        """
        conflicts: List[Dict[str, Any]] = []
        created: set = set()

        for i, op in enumerate(operations):
            if not isinstance(op, dict):
                continue
            op_type = op.get("op", "")

            if op_type == "create_node":
                parent = op.get("parent", "")
                name   = op.get("name", "")
                if parent and name:
                    created.add(f"{parent.rstrip('/')}/{name}")

            elif op_type in ("set_parms", "set_display_flag", "set_render_flag",
                             "cook_node", "delete_node", "layout_children"):
                target = op.get("node") or op.get("path") or op.get("parent", "")
                if target and "/" in target and target not in created:
                    pass  # assumed pre-existing; no conflict

            elif op_type == "connect_nodes":
                frm = op.get("from", "")
                to  = op.get("to", "")
                if frm and frm not in created:
                    pass  # assumed pre-existing; skip
                if to and to not in created:
                    pass  # assumed pre-existing; skip
                if frm and to and frm == to:
                    conflicts.append({
                        "type":        "self_connection",
                        "op_index":    i,
                        "explanation": f"connect_nodes op[{i}] connects a node to itself: '{frm}'.",
                    })

        return {
            "conflicts":      conflicts,
            "conflict_count": len(conflicts),
            "safe":           len(conflicts) == 0,
        }

    # ------------------------------------------------------------------
    # Scheduler congestion prediction
    # ------------------------------------------------------------------

    def predict_scheduler_congestion(self, queue_depth: int) -> Dict[str, Any]:
        """Predict whether the execution scheduler is congested.

        Returns:
            {
                "congested":   bool,
                "severity":    "none" | "mild" | "severe",
                "explanation": str,
                "recommendation": str,
            }
        """
        if queue_depth >= _CONGESTION_DEPTH * 2:
            return {
                "congested":      True,
                "severity":       "severe",
                "explanation":    f"Queue depth {queue_depth} is severely congested — new requests will wait.",
                "recommendation": "Pause new submissions until the queue drains below {_CONGESTION_DEPTH}.",
            }
        elif queue_depth >= _CONGESTION_DEPTH:
            return {
                "congested":      True,
                "severity":       "mild",
                "explanation":    f"Queue depth {queue_depth} is mildly congested.",
                "recommendation": "Consider batching operations to reduce queue pressure.",
            }
        else:
            return {
                "congested":      False,
                "severity":       "none",
                "explanation":    f"Queue depth {queue_depth} is within normal range.",
                "recommendation": "",
            }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"prediction_count": self._prediction_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[PredictiveExecution] = None
_INSTANCE_LOCK = threading.Lock()


def get_predictive_engine() -> PredictiveExecution:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = PredictiveExecution()
        return _INSTANCE


def reset_predictive_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
