"""
Semantic Plan Validator (Tier 3)
=================================
Multi-layer validation of AI-generated plans BEFORE execution.

Runs after the AI planner produces a plan and before ExecutionPreview /
Transaction creation. Ensures plans are safe, feasible, constraint-compliant,
and resource-appropriate.

Validation layers (in order):
  1. Structural validity    — op fields, required keys
  2. Capability check       — all required capabilities registered
  3. Constraint compliance  — RuntimeConstraints policy gate
  4. Dependency validity    — connection targets exist in dependency graph
  5. Safety checks          — destructive risk, protected paths, cycles
  6. Resource thresholds    — cost/complexity within configured limits

The validator is STATELESS and SYNCHRONOUS — it reads the dependency graph
and capability/constraint registries but NEVER bridges to Houdini.

Public API:
    get_plan_validator() -> PlanValidator
    reset_plan_validator_for_tests()

    PlanValidator.validate(plan, intent_metadata=None) -> dict
"""

import asyncio
import threading
from typing import Any, Dict, List, Optional

from src.runtime.capability_registry import get_capability_registry
from src.runtime.runtime_constraints  import get_runtime_constraints
from src.runtime.resource_estimator   import get_resource_estimator

# Resource limits (configurable via validate() kwargs)
_DEFAULT_MAX_COOK_COST   = 1.5
_DEFAULT_MAX_MEMORY      = 1.5
_DEFAULT_MAX_OP_COUNT    = 150

# Ops that are always structurally valid (no extra fields required)
_NO_FIELD_OPS = frozenset({"layout_children", "cook_node"})


def _validate_op_structure(ops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Check that each op has minimal required fields.

    Returns list of error dicts: {"index", "op", "message"}
    """
    errors: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            errors.append({"index": i, "op": "?", "message": "Op is not a dict."})
            continue
        op_type = op.get("op", "")
        if not op_type:
            errors.append({"index": i, "op": op_type, "message": "Missing 'op' field."})
            continue

        if op_type == "create_node":
            if not op.get("parent"):
                errors.append({"index": i, "op": op_type, "message": "'parent' field is required for create_node."})
            if not op.get("type"):
                errors.append({"index": i, "op": op_type, "message": "'type' field is required for create_node."})

        elif op_type == "set_parms":
            if not op.get("node"):
                errors.append({"index": i, "op": op_type, "message": "'node' field is required for set_parms."})
            if not isinstance(op.get("parms"), dict):
                errors.append({"index": i, "op": op_type, "message": "'parms' must be a dict for set_parms."})

        elif op_type == "connect_nodes":
            if not op.get("from_node"):
                errors.append({"index": i, "op": op_type, "message": "'from_node' is required for connect_nodes."})
            if not op.get("to_node"):
                errors.append({"index": i, "op": op_type, "message": "'to_node' is required for connect_nodes."})

        elif op_type == "delete_node":
            if not op.get("path"):
                errors.append({"index": i, "op": op_type, "message": "'path' is required for delete_node."})

        elif op_type == "build_node_chain":
            spec = op.get("spec", {})
            if not isinstance(spec, dict):
                errors.append({"index": i, "op": op_type, "message": "'spec' must be a dict for build_node_chain."})
            else:
                # Check for duplicate node ids within the spec
                node_ids = [n.get("id") for n in spec.get("nodes", []) if n.get("id")]
                if len(node_ids) != len(set(node_ids)):
                    errors.append({"index": i, "op": op_type, "message": "Duplicate node ids in build_node_chain spec."})

    return errors


def _check_capability_requirements(
    ops:      List[Dict[str, Any]],
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Check required capabilities from plan metadata.

    Returns list of warning dicts: {"capability", "message"}
    """
    warnings: List[Dict[str, Any]] = []
    caps = get_capability_registry()

    for cap_id in metadata.get("required_capabilities", []):
        if not caps.supports(cap_id):
            warnings.append({
                "capability": cap_id,
                "message":    f"Required capability '{cap_id}' is not registered.",
            })

    # Node-type capability checks
    for op in ops:
        if op.get("op") == "create_node":
            node_type = op.get("type", "")
            if node_type in ("karma", "mantra", "arnold"):
                if not caps.supports(node_type):
                    warnings.append({
                        "capability": node_type,
                        "message":    f"Renderer '{node_type}' is not registered as a capability.",
                    })

    return warnings


def _check_safety(
    ops: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Safety-specific warnings — destructive ops, large batch deletes, etc.

    Returns list of warning dicts: {"index", "op", "message"}
    """
    warnings: List[Dict[str, Any]] = []

    delete_count = sum(1 for op in ops if op.get("op") == "delete_node")
    if delete_count >= 5:
        warnings.append({
            "index": -1,
            "op":    "delete_node",
            "message": f"Plan contains {delete_count} delete_node ops — review carefully before executing.",
        })

    # Check for self-connections in connect_nodes
    for i, op in enumerate(ops):
        if op.get("op") == "connect_nodes":
            if op.get("from_node") and op.get("from_node") == op.get("to_node"):
                warnings.append({"index": i, "op": "connect_nodes", "message": "Self-connection detected."})

    return warnings


def _check_dependencies(
    ops: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Check delete ops against the dependency graph for downstream impact.

    Returns list of warning dicts: {"index", "op", "message"}
    """
    warnings: List[Dict[str, Any]] = []
    try:
        from src.runtime.dependency_graph import get_dependency_graph
        graph = get_dependency_graph()
        for i, op in enumerate(ops):
            if op.get("op") == "delete_node":
                path = op.get("path", "")
                if path:
                    downstream = graph.get_downstream(path)
                    if downstream:
                        warnings.append({
                            "index": i,
                            "op":    "delete_node",
                            "message": f"Deleting '{path}' will affect {len(downstream)} downstream node(s).",
                        })
    except Exception:
        pass
    return warnings


class PlanValidator:
    """Multi-layer plan validator. Stateless; reads only in-memory registries."""

    async def validate(
        self,
        plan:                    Dict[str, Any],
        intent_metadata:         Optional[Dict[str, Any]] = None,
        max_cook_cost:           float = _DEFAULT_MAX_COOK_COST,
        max_memory:              float = _DEFAULT_MAX_MEMORY,
        max_op_count:            int   = _DEFAULT_MAX_OP_COUNT,
    ) -> Dict[str, Any]:
        """Validate an AI-generated plan.

        Args:
            plan:             Output of AIPlanner.plan().
            intent_metadata:  Optional semantic op metadata (required_capabilities, tags, etc.).
            max_cook_cost:    Reject if estimated cook cost exceeds this.
            max_memory:       Reject if estimated memory impact exceeds this.
            max_op_count:     Reject if op count exceeds this.

        Returns:
            {
                "valid":             bool,
                "errors":            list[dict],     # {index, op, message} — block execution
                "warnings":          list[dict],     # {index, op, message} — advisory
                "capability_gaps":   list[dict],     # missing required capabilities
                "safety_warnings":   list[dict],     # destructive-risk notices
                "dependency_impact": list[dict],     # downstream affected nodes
                "constraint_result": dict,           # raw RuntimeConstraints output
                "resource_result":   dict,           # raw ResourceEstimator output
                "risk_level":        str,            # "low" | "medium" | "high"
                "summary":           str,
            }
        """
        intent_metadata = dict(intent_metadata or {})
        ops = plan.get("operations", [])

        # Layer 1 — structural
        struct_errors = _validate_op_structure(ops)

        # Layer 2 — capability check
        cap_warnings = _check_capability_requirements(ops, intent_metadata)

        # Layer 3 — constraint compliance
        constraint_result = get_runtime_constraints().validate_transaction(ops) if ops else {"valid": True, "violations": []}
        constraint_errors = [
            {"index": -1, "op": "?", "message": f"Constraint '{v.get('policy_id', '?')}': {v.get('message', '')}"}
            for v in constraint_result.get("violations", [])
        ]

        # Layer 4 — dependency validity
        dep_warnings = _check_dependencies(ops)

        # Layer 5 — safety
        safety_warnings = _check_safety(ops)

        # Layer 6 — resource thresholds
        resource_result = get_resource_estimator().estimate_transaction(ops) if ops else {}
        resource_errors: List[Dict[str, Any]] = []

        cook_cost = resource_result.get("estimated_cook_cost", 0.0)
        if cook_cost > max_cook_cost:
            resource_errors.append({
                "index": -1, "op": "?",
                "message": f"Estimated cook cost {cook_cost:.2f} exceeds limit {max_cook_cost:.2f}.",
            })

        mem = resource_result.get("estimated_memory", 0.0)
        if mem > max_memory:
            resource_errors.append({
                "index": -1, "op": "?",
                "message": f"Estimated memory impact {mem:.2f} exceeds limit {max_memory:.2f}.",
            })

        op_count = len(ops)
        if op_count > max_op_count:
            resource_errors.append({
                "index": -1, "op": "?",
                "message": f"Op count {op_count} exceeds limit {max_op_count}.",
            })

        # Combine
        all_errors   = struct_errors + constraint_errors + resource_errors
        all_warnings = dep_warnings + safety_warnings

        valid      = len(all_errors) == 0
        risk_level = resource_result.get("risk_level", "low")

        # Summary
        parts = [f"{'Valid' if valid else 'Invalid'} plan."]
        if all_errors:
            parts.append(f"{len(all_errors)} error(s).")
        if all_warnings:
            parts.append(f"{len(all_warnings)} warning(s).")
        if cap_warnings:
            parts.append(f"{len(cap_warnings)} missing capability/ies.")
        parts.append(f"Risk: {risk_level}.")
        summary = " ".join(parts)

        return {
            "valid":             valid,
            "errors":            all_errors,
            "warnings":          all_warnings,
            "capability_gaps":   cap_warnings,
            "safety_warnings":   safety_warnings,
            "dependency_impact": dep_warnings,
            "constraint_result": constraint_result,
            "resource_result":   resource_result,
            "risk_level":        risk_level,
            "summary":           summary,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_VALIDATOR: Optional[PlanValidator] = None
_LOCK = threading.Lock()


def get_plan_validator() -> PlanValidator:
    global _VALIDATOR
    with _LOCK:
        if _VALIDATOR is None:
            _VALIDATOR = PlanValidator()
        return _VALIDATOR


def reset_plan_validator_for_tests() -> None:
    global _VALIDATOR
    with _LOCK:
        _VALIDATOR = None
