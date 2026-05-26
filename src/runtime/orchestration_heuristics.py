"""
Orchestration Heuristics
========================
Reusable, inspectable, explainable heuristics for execution ordering, worker
selection, dependency scheduling, transaction grouping, orchestration routing,
and execution batching.

All heuristics are:
  • inspectable  — every rule is a named, documented function
  • explainable  — reasoning is returned alongside the recommendation
  • overridable  — callers can apply any subset or replace them entirely

This module NEVER:
  • executes operations or calls the bridge
  • modifies plans
  • accesses TransactionManager or ExecutionScheduler

Public API:
    get_orchestration_heuristics() -> OrchestrationHeuristics   (singleton)
    reset_orchestration_heuristics_for_tests()                   (test isolation only)

    h.order_operations(operations) -> dict
    h.select_worker(workers, required_capabilities) -> dict
    h.group_for_batching(operations, max_batch_size=10) -> dict
    h.route_operation(op, available_dccs) -> dict
    h.prioritize_queue(items) -> dict
    h.list_heuristics() -> list[dict]
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

# Execution ordering weights — lower = should run first
_ORDER_WEIGHTS: Dict[str, int] = {
    "create_node":      1,
    "build_node_chain": 2,
    "set_parms":        3,
    "connect_nodes":    4,
    "set_display_flag": 5,
    "set_render_flag":  5,
    "layout_children":  6,
    "cook_node":        7,
    "delete_node":      8,   # deletes last — never nuke what you haven't finished building
}

_HOUDINI_OPS = frozenset(_ORDER_WEIGHTS.keys())


class OrchestrationHeuristics:
    """Collection of orchestration heuristics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Heuristic: execution ordering
    # ------------------------------------------------------------------

    def order_operations(
        self, operations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Recommend an execution order for a batch of operations.

        Applies: create-before-modify, connect-before-cook, delete-last.

        Returns:
            {
                "ordered_indices": [int, ...],   # original indices in recommended order
                "changed":         bool,
                "reasoning":       [str, ...],
            }
        """
        if not operations:
            return {"ordered_indices": [], "changed": False, "reasoning": []}

        indexed = list(enumerate(operations))
        original_order = list(range(len(operations)))

        def sort_key(item):
            idx, op = item
            if not isinstance(op, dict):
                return (99, idx)
            return (_ORDER_WEIGHTS.get(op.get("op", ""), 50), idx)

        sorted_items = sorted(indexed, key=sort_key)
        new_order = [i for i, _ in sorted_items]

        changed = new_order != original_order
        reasoning: List[str] = []
        if changed:
            reasoning.append("Reordered: create_node/build_node_chain first, delete_node last.")
            reasoning.append("connect_nodes placed before cook_node to avoid cooking incomplete networks.")

        return {
            "ordered_indices": new_order,
            "changed":         changed,
            "reasoning":       reasoning,
        }

    # ------------------------------------------------------------------
    # Heuristic: worker selection
    # ------------------------------------------------------------------

    def select_worker(
        self,
        workers: List[Dict[str, Any]],
        required_capabilities: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Select the best worker from a list using least-load heuristic.

        Each worker dict: {"id", "capabilities", "current_load", "max_load", "status"}

        Returns:
            {
                "selected_id": str | None,
                "reason":      str,
                "alternatives": [str, ...],   # other viable worker ids
            }
        """
        required = set(required_capabilities or [])
        eligible = [
            w for w in workers
            if isinstance(w, dict)
            and w.get("status") == "idle"
            and required.issubset(set(w.get("capabilities", [])))
        ]

        if not eligible:
            return {
                "selected_id": None,
                "reason":      "No idle workers with required capabilities.",
                "alternatives": [],
            }

        # Least-load ratio: current_load / max_load
        def load_ratio(w):
            ml = w.get("max_load", 1) or 1
            return w.get("current_load", 0) / ml

        eligible.sort(key=load_ratio)
        best = eligible[0]
        alternatives = [w["id"] for w in eligible[1:]]

        return {
            "selected_id":  best["id"],
            "reason":       f"Lowest load ratio ({load_ratio(best):.2f}) among {len(eligible)} eligible workers.",
            "alternatives": alternatives,
        }

    # ------------------------------------------------------------------
    # Heuristic: batching
    # ------------------------------------------------------------------

    def group_for_batching(
        self,
        operations: List[Dict[str, Any]],
        max_batch_size: int = 10,
    ) -> Dict[str, Any]:
        """Group operations into batches for staged execution.

        Groups are separated at natural boundaries:
          - delete_node ops always start a new group (high risk isolation)
          - after max_batch_size is reached

        Returns:
            {
                "batches":       [[op_index, ...], ...],
                "batch_count":   int,
                "reasoning":     [str, ...],
            }
        """
        if not operations:
            return {"batches": [], "batch_count": 0, "reasoning": []}

        batches: List[List[int]] = []
        current: List[int] = []
        reasoning: List[str] = []

        for i, op in enumerate(operations):
            op_type = op.get("op", "") if isinstance(op, dict) else ""

            # Delete ops start a new batch
            if op_type == "delete_node" and current:
                batches.append(current)
                current = []
                reasoning.append(f"Op[{i}] delete_node splits batch — delete isolated for safety.")

            current.append(i)

            # Max batch size reached
            if len(current) >= max_batch_size:
                batches.append(current)
                current = []
                reasoning.append(f"Batch split at {max_batch_size} ops.")

        if current:
            batches.append(current)

        if not reasoning and len(batches) == 1:
            reasoning.append("All operations fit in a single batch.")

        return {
            "batches":     batches,
            "batch_count": len(batches),
            "reasoning":   reasoning,
        }

    # ------------------------------------------------------------------
    # Heuristic: DCC routing
    # ------------------------------------------------------------------

    def route_operation(
        self,
        op: Dict[str, Any],
        available_dccs: List[str],
    ) -> Dict[str, Any]:
        """Recommend the best DCC for a single operation.

        Returns:
            {
                "recommended_dcc": str | None,
                "confidence":      float,
                "reason":          str,
            }
        """
        if not isinstance(op, dict):
            return {"recommended_dcc": None, "confidence": 0.0, "reason": "Invalid op."}

        op_type = op.get("op", "")
        hint    = op.get("hint_dcc", "")

        # Explicit hint wins
        if hint and hint in available_dccs:
            return {
                "recommended_dcc": hint,
                "confidence":      1.0,
                "reason":          f"Explicit hint_dcc='{hint}' present.",
            }

        # Houdini ops
        if op_type in _HOUDINI_OPS and "houdini" in available_dccs:
            return {
                "recommended_dcc": "houdini",
                "confidence":      0.95,
                "reason":          f"'{op_type}' is a standard Houdini operation.",
            }

        # First available DCC as fallback
        if available_dccs:
            return {
                "recommended_dcc": available_dccs[0],
                "confidence":      0.4,
                "reason":          "No explicit routing rule — defaulting to first available DCC.",
            }

        return {"recommended_dcc": None, "confidence": 0.0, "reason": "No available DCCs."}

    # ------------------------------------------------------------------
    # Heuristic: queue prioritization
    # ------------------------------------------------------------------

    def prioritize_queue(
        self, items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Sort a queue of pending execution items by priority.

        Each item dict: {"id", "priority"? (int 0–100), "op_count"?, "timestamp"?, "risk_level"?}

        Higher priority value = run sooner.
        Lower op_count = run sooner (smaller jobs first for fairness).
        Older timestamp = run sooner (FIFO as tiebreaker).

        Returns:
            {
                "ordered_ids": [str, ...],
                "reasoning":   [str, ...],
            }
        """
        if not items:
            return {"ordered_ids": [], "reasoning": []}

        def sort_key(item):
            priority  = -(item.get("priority") or 50)          # higher priority first (negate)
            risk      = {"low": 0, "medium": 1, "high": 2}.get(item.get("risk_level", "low"), 0)
            op_count  = item.get("op_count", 0)                # fewer ops first
            timestamp = item.get("timestamp") or 0             # older first
            return (priority, risk, op_count, timestamp)

        sorted_items = sorted(items, key=sort_key)
        reasoning = [
            "Priority order: explicit priority > risk level > op count > FIFO.",
            f"{len(items)} item(s) prioritized.",
        ]
        return {
            "ordered_ids": [item["id"] for item in sorted_items],
            "reasoning":   reasoning,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_heuristics(self) -> List[Dict[str, Any]]:
        """Return a description of all available heuristics."""
        return [
            {
                "name":        "order_operations",
                "description": "Reorder ops: create first, delete last, cook after connect.",
                "inputs":      ["operations: list[dict]"],
                "outputs":     ["ordered_indices", "changed", "reasoning"],
            },
            {
                "name":        "select_worker",
                "description": "Select least-loaded idle worker with required capabilities.",
                "inputs":      ["workers: list[dict]", "required_capabilities: list[str]"],
                "outputs":     ["selected_id", "reason", "alternatives"],
            },
            {
                "name":        "group_for_batching",
                "description": "Split operations into safe batches at delete boundaries.",
                "inputs":      ["operations: list[dict]", "max_batch_size: int"],
                "outputs":     ["batches", "batch_count", "reasoning"],
            },
            {
                "name":        "route_operation",
                "description": "Recommend best DCC for a single operation.",
                "inputs":      ["op: dict", "available_dccs: list[str]"],
                "outputs":     ["recommended_dcc", "confidence", "reason"],
            },
            {
                "name":        "prioritize_queue",
                "description": "Sort pending queue items by priority, risk, op count, FIFO.",
                "inputs":      ["items: list[dict]"],
                "outputs":     ["ordered_ids", "reasoning"],
            },
        ]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[OrchestrationHeuristics] = None
_INSTANCE_LOCK = threading.Lock()


def get_orchestration_heuristics() -> OrchestrationHeuristics:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = OrchestrationHeuristics()
        return _INSTANCE


def reset_orchestration_heuristics_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
