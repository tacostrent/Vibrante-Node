"""
Resource Estimator (Tier 2.75)
================================
Heuristic-only pre-execution cost estimation for operation batches.

No profiling, no bridge calls, no LLMs. All estimates are based on op
type and node type patterns baked into this module. The goal is "good
enough for a user to decide whether to proceed" not "accurate simulation".

Cost categories:
    memory_impact  — relative memory pressure (0.0 = negligible, 1.0 = high)
    cook_cost      — relative compute cost (0.0 = visual-only, 1.0 = expensive)
    risk_level     — "low" | "medium" | "high" (mirrors validation engine)

Public API:
    get_resource_estimator() -> ResourceEstimator   (singleton)
    reset_resource_estimator_for_tests()

    ResourceEstimator.estimate_operation(op) -> dict
    ResourceEstimator.estimate_transaction(ops) -> dict
    ResourceEstimator.estimate_graph_complexity(n_nodes, n_connections) -> str
"""

import threading
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Heuristic tables
# ---------------------------------------------------------------------------

# Per-op-type base cost weights (memory_impact, cook_cost)
_OP_BASE: Dict[str, tuple] = {
    "create_node":        (0.05, 0.0),
    "set_parms":          (0.0,  0.1),
    "connect_nodes":      (0.0,  0.05),
    "delete_node":        (0.0,  0.0),
    "set_display_flag":   (0.0,  0.0),
    "set_render_flag":    (0.0,  0.0),
    "set_keyframe":       (0.0,  0.05),
    "cook_node":          (0.1,  0.4),
    "layout_children":    (0.0,  0.0),
    "build_node_chain":   (0.1,  0.1),
}

# Node-type patterns that bump memory/cook estimates when seen in an op
_HIGH_MEMORY_TYPES = frozenset({
    "pyro", "smoke", "fluid", "vellum", "cloth", "grain", "flip",
    "volume", "vdb", "heightfield", "crowds",
})
_HIGH_COOK_TYPES = frozenset({
    "pyro", "smoke", "fluid", "vellum", "cloth", "grain", "flip",
    "solver", "dopnet", "rendernode", "karma", "mantra", "ifd",
    "arnold", "redshift_rop", "usdrender_rop",
})
_MEDIUM_MEMORY_TYPES = frozenset({
    "remesh", "boolean", "polyreduce", "tetrahedral", "wire",
    "sphere", "box", "torus", "grid", "tube",
})
_MEDIUM_COOK_TYPES = frozenset({
    "attribwrangle", "vopsop", "wrangle", "python",
    "null", "merge", "switch", "foreach_begin",
})

# Risk thresholds (mirrors validation_engine risk scoring logic)
_HIGH_RISK  = 10.0
_MEDIUM_RISK = 1.0

# Per-op risk weights (same as validation_engine._RISK_WEIGHTS for consistency)
_RISK_WEIGHTS: Dict[str, float] = {
    "create_node":        0.0,
    "set_display_flag":   0.0,
    "set_render_flag":    0.0,
    "set_keyframe":       1.0,
    "layout_children":    0.0,
    "set_parms":          1.0,
    "connect_nodes":      1.0,
    "cook_node":          1.0,
    "build_node_chain":   2.0,
    "delete_node":       10.0,
}


def _node_type_bump(op: Dict[str, Any]) -> tuple:
    """Return (memory_bump, cook_bump) based on node_type patterns in the op."""
    node_type = ""
    if op.get("op") == "create_node":
        node_type = str(op.get("type", "")).lower()
    elif op.get("op") == "build_node_chain":
        spec = op.get("spec", {})
        types = [n.get("type", "") for n in spec.get("nodes", [])]
        node_type = " ".join(str(t).lower() for t in types)

    mem = 0.0
    cook = 0.0
    for t in _HIGH_MEMORY_TYPES:
        if t in node_type:
            mem = max(mem, 0.8)
    for t in _HIGH_COOK_TYPES:
        if t in node_type:
            cook = max(cook, 0.8)
    if mem == 0.0:
        for t in _MEDIUM_MEMORY_TYPES:
            if t in node_type:
                mem = max(mem, 0.3)
    if cook == 0.0:
        for t in _MEDIUM_COOK_TYPES:
            if t in node_type:
                cook = max(cook, 0.3)
    return (mem, cook)


class ResourceEstimator:
    """Heuristic resource estimator. Thread-safe, stateless."""

    def estimate_operation(self, op: Any) -> Dict[str, Any]:
        """Estimate resource cost for a single operation dict.

        Returns:
            {
                "op":            str,
                "memory_impact": float (0.0–1.0),
                "cook_cost":     float (0.0–1.0),
                "risk_level":    "low" | "medium" | "high",
                "notes":         list[str],
            }
        """
        if not isinstance(op, dict):
            return {
                "op": str(op), "memory_impact": 0.0, "cook_cost": 0.0,
                "risk_level": "low", "notes": ["invalid op shape"],
            }

        op_type = str(op.get("op", ""))
        base_mem, base_cook = _OP_BASE.get(op_type, (0.05, 0.05))
        bump_mem, bump_cook = _node_type_bump(op)
        memory_impact = min(1.0, base_mem + bump_mem)
        cook_cost     = min(1.0, base_cook + bump_cook)

        risk_weight = _RISK_WEIGHTS.get(op_type, 0.0)
        if risk_weight >= _HIGH_RISK:
            risk_level = "high"
        elif risk_weight >= _MEDIUM_RISK:
            risk_level = "medium"
        else:
            risk_level = "low"

        notes: List[str] = []
        if op_type == "delete_node":
            notes.append("deletion is irreversible in Tier 2")
        if memory_impact >= 0.8:
            notes.append("high memory pressure expected (simulation/volume node type)")
        if cook_cost >= 0.8:
            notes.append("expensive cook expected (simulation/render node type)")
        if op_type == "cook_node":
            notes.append("cook_node forces immediate evaluation")

        return {
            "op":            op_type,
            "memory_impact": round(memory_impact, 3),
            "cook_cost":     round(cook_cost, 3),
            "risk_level":    risk_level,
            "notes":         notes,
        }

    def estimate_transaction(self, ops: Any) -> Dict[str, Any]:
        """Aggregate cost estimate for a list of operations.

        Returns:
            {
                "op_count":           int,
                "estimated_memory":   float (0.0–1.0, max across ops),
                "estimated_cook_cost": float (0.0–1.0, max across ops),
                "risk_level":         "low" | "medium" | "high",
                "graph_complexity":   "low" | "medium" | "high",
                "per_op":             list[dict],
            }
        """
        if not isinstance(ops, list):
            return {
                "op_count": 0, "estimated_memory": 0.0, "estimated_cook_cost": 0.0,
                "risk_level": "low", "graph_complexity": "low", "per_op": [],
            }

        per_op = [self.estimate_operation(op) for op in ops]

        max_mem  = max((r["memory_impact"] for r in per_op), default=0.0)
        max_cook = max((r["cook_cost"] for r in per_op), default=0.0)

        # Aggregate risk from raw weights
        total_risk = sum(
            _RISK_WEIGHTS.get(str(op.get("op", "")), 0.0)
            for op in ops if isinstance(op, dict)
        )
        if total_risk >= _HIGH_RISK:
            risk_level = "high"
        elif total_risk >= _MEDIUM_RISK:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Node count heuristic: check create_node + build_node_chain nodes
        n_created = sum(
            1 if str(op.get("op", "")) == "create_node" else
            len(op.get("spec", {}).get("nodes", [])) if str(op.get("op", "")) == "build_node_chain" else 0
            for op in ops if isinstance(op, dict)
        )
        n_connections = sum(
            len(op.get("spec", {}).get("connections", [])) if str(op.get("op", "")) == "build_node_chain" else 0
            for op in ops if isinstance(op, dict)
        )
        graph_complexity = self.estimate_graph_complexity(n_created, n_connections)

        return {
            "op_count":             len(ops),
            "estimated_memory":     round(max_mem, 3),
            "estimated_cook_cost":  round(max_cook, 3),
            "risk_level":           risk_level,
            "graph_complexity":     graph_complexity,
            "per_op":               per_op,
        }

    def estimate_graph_complexity(self, n_nodes: int, n_connections: int) -> str:
        """Heuristic graph complexity label based on node + connection count.

        Returns "low" | "medium" | "high".
        """
        n_nodes = max(0, int(n_nodes))
        n_connections = max(0, int(n_connections))
        score = n_nodes + n_connections * 0.5
        if score >= 20:
            return "high"
        if score >= 5:
            return "medium"
        return "low"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_ESTIMATOR: Optional[ResourceEstimator] = None
_LOCK = threading.Lock()


def get_resource_estimator() -> ResourceEstimator:
    global _ESTIMATOR
    with _LOCK:
        if _ESTIMATOR is None:
            _ESTIMATOR = ResourceEstimator()
        return _ESTIMATOR


def reset_resource_estimator_for_tests() -> None:
    global _ESTIMATOR
    with _LOCK:
        _ESTIMATOR = None
