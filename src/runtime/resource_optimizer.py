"""
Resource Optimizer
==================
Advisory-only optimizer for worker allocation, execution scheduling,
transaction sizing, and resource balancing.

All recommendations are:
  • advisory — NEVER auto-executes, NEVER changes worker state directly
  • inspectable — every recommendation includes a reason
  • deterministic — identical inputs produce identical recommendations

This module NEVER:
  • calls the bridge or houdini_runtime
  • acquires or releases workers
  • submits transactions
  • modifies execution plans

Public API:
    get_resource_optimizer() -> ResourceOptimizer   (singleton)
    reset_resource_optimizer_for_tests()             (test isolation only)

    optimizer.recommend_worker_allocation(operations, workers) -> dict
    optimizer.recommend_transaction_sizing(operations) -> dict
    optimizer.recommend_scheduling_order(pending_items) -> dict
    optimizer.recommend_load_balancing(workers) -> dict
    optimizer.stats() -> dict
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

_MAX_OPS_PER_TRANSACTION = 15
_IDEAL_WORKER_LOAD       = 0.7   # target utilisation ratio
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


class ResourceOptimizer:
    """Advisory resource utilisation optimizer."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._call_count = 0

    # ------------------------------------------------------------------
    # Worker allocation
    # ------------------------------------------------------------------

    def recommend_worker_allocation(
        self,
        operations: List[Dict[str, Any]],
        workers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Recommend which worker(s) should handle a batch of operations.

        Returns:
            {
                "recommended_worker": str | None,
                "load_after":         float,    # projected load ratio
                "alternatives":       [str, ...],
                "reasoning":          [str, ...],
                "should_split":       bool,
            }
        """
        with self._lock:
            self._call_count += 1

        reasoning: List[str] = []

        # Filter idle workers
        idle = [w for w in workers
                if isinstance(w, dict) and w.get("status") in ("idle", "busy")
                and w.get("current_load", 0) < (w.get("max_load", 1) or 1)]

        if not idle:
            return {
                "recommended_worker": None,
                "load_after": 1.0,
                "alternatives": [],
                "reasoning": ["No workers with available capacity."],
                "should_split": False,
            }

        # Sort by ascending load ratio
        def load_ratio(w):
            ml = w.get("max_load", 1) or 1
            return w.get("current_load", 0) / ml

        idle.sort(key=load_ratio)
        best = idle[0]
        alternatives = [w["id"] for w in idle[1:3]]

        # Project load after this job
        ml = best.get("max_load", 1) or 1
        current = best.get("current_load", 0)
        new_load = (current + 1) / ml
        reasoning.append(f"Worker '{best['id']}' has lowest load ratio ({load_ratio(best):.2f}).")

        # Check if splitting is beneficial
        should_split = len(operations) > _MAX_OPS_PER_TRANSACTION
        if should_split:
            reasoning.append(
                f"Batch has {len(operations)} ops > {_MAX_OPS_PER_TRANSACTION} — "
                "consider splitting for lower per-transaction rollback cost."
            )

        if new_load > _IDEAL_WORKER_LOAD:
            reasoning.append(
                f"Projected load {new_load:.2f} exceeds ideal {_IDEAL_WORKER_LOAD} — "
                "consider registering additional workers."
            )

        return {
            "recommended_worker": best["id"],
            "load_after":         round(new_load, 3),
            "alternatives":       alternatives,
            "reasoning":          reasoning,
            "should_split":       should_split,
        }

    # ------------------------------------------------------------------
    # Transaction sizing
    # ------------------------------------------------------------------

    def recommend_transaction_sizing(
        self, operations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Recommend how to size transactions for a batch of operations.

        Returns:
            {
                "recommended_size": int,
                "split_points":     [int, ...],   # op indices where to split
                "group_count":      int,
                "reasoning":        [str, ...],
            }
        """
        with self._lock:
            self._call_count += 1

        if not operations:
            return {"recommended_size": 0, "split_points": [], "group_count": 0, "reasoning": []}

        reasoning: List[str] = []
        split_points: List[int] = []
        current_risk = 0
        current_count = 0
        size_limit = _MAX_OPS_PER_TRANSACTION

        for i, op in enumerate(operations):
            op_type = op.get("op", "") if isinstance(op, dict) else ""
            risk = _OP_RISK_WEIGHTS.get(op_type, 0)
            current_risk += risk
            current_count += 1

            # Split if: risk threshold hit, size limit hit, or high-risk op
            if (current_risk >= 10 or current_count >= size_limit or
                    (op_type == "delete_node" and current_count > 1)):
                if i < len(operations) - 1:
                    split_points.append(i + 1)
                    current_risk = 0
                    current_count = 0
                    reason = (
                        f"Split at op[{i+1}]: risk={current_risk}, count={current_count}"
                    )
                    if op_type == "delete_node":
                        reason = f"Split at op[{i+1}]: isolating delete_node for safe rollback."
                    reasoning.append(reason)

        group_count = len(split_points) + 1
        recommended_size = max(1, len(operations) // group_count)

        if not split_points:
            reasoning.append("Operations fit in a single transaction.")

        return {
            "recommended_size": recommended_size,
            "split_points":     split_points,
            "group_count":      group_count,
            "reasoning":        reasoning,
        }

    # ------------------------------------------------------------------
    # Scheduling order
    # ------------------------------------------------------------------

    def recommend_scheduling_order(
        self, pending_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Recommend the order in which pending items should be scheduled.

        Each item: {"id", "priority"? (0–100), "risk_level"?, "op_count"?, "timestamp"?}

        Returns:
            {
                "ordered_ids": [str, ...],
                "reasoning":   [str, ...],
            }
        """
        with self._lock:
            self._call_count += 1

        if not pending_items:
            return {"ordered_ids": [], "reasoning": []}

        def sort_key(item):
            priority  = -(item.get("priority") or 50)
            risk_ord  = {"low": 0, "medium": 1, "high": 2}.get(item.get("risk_level", "low"), 0)
            op_count  = item.get("op_count", 0)
            timestamp = item.get("timestamp", 0)
            return (priority, risk_ord, op_count, timestamp)

        ordered = sorted(pending_items, key=sort_key)
        reasoning = [
            "Order: highest priority → lowest risk → smallest job → oldest submission.",
            f"{len(pending_items)} item(s) scheduled.",
        ]
        return {
            "ordered_ids": [item["id"] for item in ordered],
            "reasoning":   reasoning,
        }

    # ------------------------------------------------------------------
    # Load balancing
    # ------------------------------------------------------------------

    def recommend_load_balancing(
        self, workers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Recommend load balancing actions for a worker pool.

        Returns:
            {
                "actions":      [{"action", "worker_id", "reason"}, ...],
                "pool_health":  "healthy" | "unbalanced" | "overloaded",
                "reasoning":    [str, ...],
            }
        """
        with self._lock:
            self._call_count += 1

        if not workers:
            return {"actions": [], "pool_health": "healthy", "reasoning": ["No workers in pool."]}

        actions: List[Dict[str, Any]] = []
        reasoning: List[str] = []

        ratios = []
        for w in workers:
            if not isinstance(w, dict):
                continue
            ml = w.get("max_load", 1) or 1
            ratio = w.get("current_load", 0) / ml
            ratios.append((w.get("id", ""), ratio, w.get("status", "idle")))

        if not ratios:
            return {"actions": [], "pool_health": "healthy", "reasoning": ["No valid workers."]}

        avg_ratio = sum(r for _, r, _ in ratios) / len(ratios)
        max_ratio = max(r for _, r, _ in ratios)
        min_ratio = min(r for _, r, _ in ratios)

        pool_health: str
        if max_ratio >= 1.0:
            pool_health = "overloaded"
            reasoning.append(f"At least one worker at full capacity (max_ratio={max_ratio:.2f}).")
        elif max_ratio - min_ratio > 0.4:
            pool_health = "unbalanced"
            reasoning.append(f"Load imbalance detected (spread={max_ratio - min_ratio:.2f}).")
        else:
            pool_health = "healthy"
            reasoning.append(f"Pool is balanced (avg_ratio={avg_ratio:.2f}).")

        # Suggest actions
        for wid, ratio, status in ratios:
            if ratio >= 1.0:
                actions.append({
                    "action":    "scale_up",
                    "worker_id": wid,
                    "reason":    f"Worker '{wid}' is at full load ({ratio:.2f}) — add more capacity.",
                })
            elif status == "offline":
                actions.append({
                    "action":    "revive_or_remove",
                    "worker_id": wid,
                    "reason":    f"Worker '{wid}' is offline — revive via heartbeat or remove.",
                })
            elif ratio > _IDEAL_WORKER_LOAD and avg_ratio < 0.5:
                actions.append({
                    "action":    "rebalance",
                    "worker_id": wid,
                    "reason":    (
                        f"Worker '{wid}' load ({ratio:.2f}) above ideal "
                        f"while pool average is low ({avg_ratio:.2f})."
                    ),
                })

        return {
            "actions":     actions,
            "pool_health": pool_health,
            "reasoning":   reasoning,
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"call_count": self._call_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[ResourceOptimizer] = None
_INSTANCE_LOCK = threading.Lock()


def get_resource_optimizer() -> ResourceOptimizer:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = ResourceOptimizer()
        return _INSTANCE


def reset_resource_optimizer_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
