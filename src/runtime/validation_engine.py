"""
Validation Engine
=================
Pre-execution validation of structured Houdini operations. Runs semantic checks
against current runtime state (dependency graph, known op vocabulary) BEFORE
any mutation occurs, complementing the lightweight shape-check in
`houdini_runtime._validate_operation()`.

Validation levels:
  error   — would definitely fail or corrupt the scene; blocks execution
  warning — suspicious or risky; execution allowed but reported to caller

Checks performed:
  • op shape (delegates to houdini_runtime._validate_operation)
  • self-connections (connect_nodes from == to)
  • dangerous deletes (node has downstream dependents in dependency graph)
  • empty operation list
  • build_node_chain sub-spec validity (duplicate ids, self-connections)
  • no-op set_parms (empty parms dict)

Risk scoring (per-op weights summed across the batch):
  low     — total risk < 1  (pure creates, flags, layout)
  medium  — total risk 1–9  (parms, connections, cooks)
  high    — total risk ≥ 10 (any delete, or dependency violation)

Public API:
    get_validation_engine() -> ValidationEngine   (singleton)

    await engine.validate_operations(ops: list[dict]) -> dict
    # Returns: {"valid", "errors", "warnings", "risk_level", "op_count", "summary"}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.runtime.dependency_graph import get_dependency_graph

_RISK_WEIGHTS: Dict[str, int] = {
    "create_node":      0,
    "set_parms":        1,
    "connect_nodes":    1,
    "delete_node":      10,
    "set_display_flag": 0,
    "set_render_flag":  0,
    "set_keyframe":     1,
    "cook_node":        1,
    "layout_children":  0,
    "build_node_chain": 2,
}

_HIGH_RISK_THRESHOLD = 10
_MEDIUM_RISK_THRESHOLD = 1


class ValidationEngine:
    """Stateless pre-execution validator.

    Thread-safe — no mutable instance state. Instantiate once or use the
    module-level `get_validation_engine()` singleton.
    """

    async def validate_operations(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a list of structured operations.

        Returns:
            {
                "valid":      bool,
                "errors":     [{"index": int, "op": str, "message": str}],
                "warnings":   [{"index": int, "op": str, "message": str}],
                "risk_level": "low" | "medium" | "high",
                "op_count":   int,
                "summary":    str,
            }
        """
        if not operations:
            return self._result(
                True, [],
                [{"index": -1, "op": "none", "message": "empty operation list — nothing to execute"}],
                "low", 0,
            )

        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        total_risk = 0

        for i, op in enumerate(operations):
            op_errors, op_warnings, risk = self._validate_one(op, i)
            errors.extend(op_errors)
            warnings.extend(op_warnings)
            total_risk += risk

        if total_risk >= _HIGH_RISK_THRESHOLD:
            risk_level = "high"
        elif total_risk >= _MEDIUM_RISK_THRESHOLD:
            risk_level = "medium"
        else:
            risk_level = "low"

        valid = len(errors) == 0
        return self._result(valid, errors, warnings, risk_level, len(operations))

    def _validate_one(
        self,
        op: Dict[str, Any],
        index: int,
    ) -> Tuple[List[Dict], List[Dict], int]:
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        if not isinstance(op, dict):
            return (
                [self._err(index, "?", f"operation must be a dict, got {type(op).__name__}")],
                [],
                0,
            )

        # Delegate shape check to houdini_runtime (import here to avoid circular)
        from src.runtime.houdini_runtime import _validate_operation  # noqa: PLC0415

        shape_error = _validate_operation(op)
        if shape_error:
            return [self._err(index, op.get("op", "?"), shape_error)], [], 0

        op_type = op.get("op", "")
        risk = _RISK_WEIGHTS.get(op_type, 0)

        # delete_node — warn if node has known downstream dependents
        if op_type == "delete_node":
            path = op.get("path", "")
            graph = get_dependency_graph()
            downstream = graph.get_downstream(path)
            if downstream:
                down_paths = [d["target"] for d in downstream]
                warnings.append(self._warn(
                    index, op_type,
                    f"deleting '{path}' may break {len(down_paths)} downstream "
                    f"dependent(s): {down_paths[:5]}",
                ))

        # connect_nodes — reject self-connections
        if op_type == "connect_nodes":
            if op.get("from") == op.get("to"):
                errors.append(self._err(
                    index, op_type,
                    f"self-connection: 'from' and 'to' are the same node: {op.get('from')}",
                ))

        # build_node_chain — validate sub-spec structure
        if op_type == "build_node_chain":
            spec = op.get("spec") or {}
            nodes = spec.get("nodes") or []
            connections = spec.get("connections") or []
            seen_ids: set = set()
            for j, n in enumerate(nodes):
                if not isinstance(n, dict):
                    errors.append(self._err(index, op_type, f"spec.nodes[{j}] must be a dict"))
                    continue
                nid = n.get("id", "")
                if not nid:
                    errors.append(self._err(index, op_type, f"spec.nodes[{j}] missing 'id'"))
                elif nid in seen_ids:
                    errors.append(self._err(index, op_type, f"duplicate spec node id: '{nid}'"))
                seen_ids.add(nid)
            for j, c in enumerate(connections):
                if not isinstance(c, dict):
                    errors.append(self._err(index, op_type, f"spec.connections[{j}] must be a dict"))
                    continue
                if c.get("from") and c.get("from") == c.get("to"):
                    errors.append(self._err(
                        index, op_type,
                        f"spec.connections[{j}] is a self-connection: '{c.get('from')}'",
                    ))

        # set_parms — warn on empty parms dict (no-op)
        if op_type == "set_parms":
            parms = op.get("parms") or {}
            if isinstance(parms, dict) and len(parms) == 0:
                warnings.append(self._warn(
                    index, op_type, "parms dict is empty — this operation is a no-op"
                ))

        return errors, warnings, risk

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _err(index: int, op: str, message: str) -> Dict[str, Any]:
        return {"index": index, "op": op, "message": message}

    @staticmethod
    def _warn(index: int, op: str, message: str) -> Dict[str, Any]:
        return {"index": index, "op": op, "message": message}

    @staticmethod
    def _result(
        valid: bool,
        errors: List,
        warnings: List,
        risk_level: str,
        op_count: int,
    ) -> Dict[str, Any]:
        if not valid:
            summary = f"{len(errors)} error(s), {len(warnings)} warning(s), risk={risk_level}"
        elif warnings:
            summary = f"valid with {len(warnings)} warning(s), risk={risk_level}"
        else:
            summary = f"valid — {op_count} op(s), risk={risk_level}"
        return {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "risk_level": risk_level,
            "op_count": op_count,
            "summary": summary,
        }


_ENGINE: Optional[ValidationEngine] = None


def get_validation_engine() -> ValidationEngine:
    """Return the process-wide ValidationEngine singleton."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = ValidationEngine()
    return _ENGINE


def reset_validation_engine_for_tests() -> None:
    global _ENGINE
    _ENGINE = None
