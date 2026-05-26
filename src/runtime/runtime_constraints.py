"""
Runtime Constraints (Tier 2.75)
================================
Protected paths, forbidden ops, permission gates, and locked assets.
Validates operation lists BEFORE the transaction system attempts execution
so constraint violations are surfaced with clear error messages.

This is a rule engine, not a permission system. All policies are in-memory,
user-configurable at runtime, and do not persist across sessions. They are
checked synchronously (no bridge calls, no async I/O).

Policy types (string constants):
    "protected_path"     — a specific Houdini path that must not be modified/deleted
    "forbidden_op"       — an op type that is never allowed (e.g. "delete_node" globally)
    "forbidden_node_type"— a Houdini node type that must not be created (e.g. "python")
    "max_ops"            — cap on the number of operations in a single transaction
    "permission"         — custom rule: lambda(op) -> bool evaluated against each op

Built-in policies (always active, cannot be removed):
    - protect /stage     — never mutate the USD stage root directly
    - protect /out/karma / /out/mantra / /out — protect render output nodes
    - max_ops: 100       — safety cap on transaction size

Public API:
    get_runtime_constraints() -> RuntimeConstraints   (singleton)
    reset_runtime_constraints_for_tests()

    RuntimeConstraints.add_policy(type, id, config) -> None
    RuntimeConstraints.remove_policy(id) -> bool
    RuntimeConstraints.get_policy(id) -> dict | None
    RuntimeConstraints.list_policies() -> list[dict]
    RuntimeConstraints.validate_operation(op) -> dict
    RuntimeConstraints.validate_transaction(ops) -> dict
"""

import threading
from typing import Any, Callable, Dict, List, Optional

POLICY_TYPES = frozenset({
    "protected_path",
    "forbidden_op",
    "forbidden_node_type",
    "max_ops",
    "permission",
})

# ---------------------------------------------------------------------------
# Built-in / default policies
# ---------------------------------------------------------------------------

_BUILTIN_POLICIES: List[Dict[str, Any]] = [
    {
        "id": "_builtin_protect_stage",
        "type": "protected_path",
        "config": {
            "path": "/stage",
            "message": "The /stage network (USD stage root) is protected. "
                       "Use dedicated USD/Solaris nodes to mutate it.",
        },
        "_builtin": True,
    },
    {
        "id": "_builtin_protect_out",
        "type": "protected_path",
        "config": {
            "path": "/out",
            "message": "The /out render network is protected. "
                       "Add render nodes via hou_mcp_build_node_chain with explicit /out parent.",
        },
        "_builtin": True,
    },
    {
        "id": "_builtin_max_ops",
        "type": "max_ops",
        "config": {
            "limit": 100,
            "message": "Transaction exceeds maximum of 100 operations. "
                       "Break large plans into smaller transactions.",
        },
        "_builtin": True,
    },
]


def _is_path_protected(op: Dict[str, Any], protected: str) -> bool:
    """Return True if any path in the op starts with the protected prefix."""
    op_type = str(op.get("op", ""))
    candidates: List[str] = []

    if op_type == "create_node":
        candidates.append(str(op.get("parent", "")))
    elif op_type in ("delete_node", "cook_node", "set_display_flag",
                     "set_render_flag", "layout_children"):
        candidates.append(str(op.get("path", "")))
    elif op_type in ("set_parms", "set_keyframe"):
        candidates.append(str(op.get("node", "")))
    elif op_type == "connect_nodes":
        candidates.append(str(op.get("from_node", "")))
        candidates.append(str(op.get("to_node", "")))
    elif op_type == "build_node_chain":
        spec = op.get("spec", {})
        for node in spec.get("nodes", []):
            candidates.append(str(node.get("parent", "")))

    for path in candidates:
        if path and (path == protected or path.startswith(protected + "/")):
            return True
    return False


class RuntimeConstraints:
    def __init__(self):
        self._lock = threading.Lock()
        # id → policy dict
        self._policies: Dict[str, Dict[str, Any]] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        for p in _BUILTIN_POLICIES:
            self._policies[p["id"]] = dict(p)

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def add_policy(self, policy_type: str, policy_id: str, config: Optional[Dict[str, Any]] = None) -> None:
        """Register a constraint policy.

        Args:
            policy_type: One of POLICY_TYPES.
            policy_id:   Unique string id (must not start with '_builtin_').
            config:      Policy configuration dict. Required keys per type:
                         protected_path  → {"path": str, "message"?: str}
                         forbidden_op    → {"op": str, "message"?: str}
                         forbidden_node_type → {"node_type": str, "message"?: str}
                         max_ops         → {"limit": int, "message"?: str}
                         permission      → {"check": Callable[[dict], bool], "message"?: str}
        """
        if policy_type not in POLICY_TYPES:
            raise ValueError(f"Unknown policy type: {policy_type!r}")
        if not policy_id:
            raise ValueError("policy_id must be non-empty")
        if policy_id.startswith("_builtin_"):
            raise ValueError("Policy ids starting with '_builtin_' are reserved")
        with self._lock:
            self._policies[policy_id] = {
                "id":     policy_id,
                "type":   policy_type,
                "config": dict(config or {}),
            }

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy. Returns False for built-in policies or unknown ids."""
        with self._lock:
            p = self._policies.get(policy_id)
            if p is None:
                return False
            if p.get("_builtin"):
                return False
            del self._policies[policy_id]
            return True

    def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            p = self._policies.get(policy_id)
            return dict(p) if p else None

    def list_policies(self) -> List[Dict[str, Any]]:
        with self._lock:
            return sorted(
                [dict(p) for p in self._policies.values()],
                key=lambda p: (p["type"], p["id"]),
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_operation(self, op: Any) -> Dict[str, Any]:
        """Check a single operation against all registered policies.

        Returns:
            {"valid": bool, "violations": [{"policy_id": str, "message": str}]}
        """
        violations: List[Dict[str, str]] = []

        if not isinstance(op, dict):
            return {"valid": False, "violations": [{"policy_id": "_shape", "message": "op must be a dict"}]}

        op_type = str(op.get("op", ""))

        with self._lock:
            policies = list(self._policies.values())

        for p in policies:
            ptype  = p["type"]
            cfg    = p.get("config", {})
            pid    = p["id"]

            if ptype == "protected_path":
                protected = cfg.get("path", "")
                if protected and _is_path_protected(op, protected):
                    msg = cfg.get("message") or f"Operation targets protected path: {protected}"
                    violations.append({"policy_id": pid, "message": msg})

            elif ptype == "forbidden_op":
                forbidden = cfg.get("op", "")
                if forbidden and op_type == forbidden:
                    msg = cfg.get("message") or f"Operation type '{forbidden}' is forbidden"
                    violations.append({"policy_id": pid, "message": msg})

            elif ptype == "forbidden_node_type":
                forbidden_type = str(cfg.get("node_type", "")).lower()
                if forbidden_type:
                    node_type = str(op.get("type", "")).lower()
                    if op_type == "create_node" and node_type == forbidden_type:
                        msg = cfg.get("message") or f"Node type '{forbidden_type}' is forbidden"
                        violations.append({"policy_id": pid, "message": msg})
                    elif op_type == "build_node_chain":
                        spec = op.get("spec", {})
                        for node in spec.get("nodes", []):
                            if str(node.get("type", "")).lower() == forbidden_type:
                                msg = cfg.get("message") or f"Node type '{forbidden_type}' is forbidden"
                                violations.append({"policy_id": pid, "message": msg})
                                break

            elif ptype == "permission":
                check: Optional[Callable] = cfg.get("check")
                if callable(check):
                    try:
                        if not check(op):
                            msg = cfg.get("message") or f"Permission check '{pid}' rejected operation"
                            violations.append({"policy_id": pid, "message": msg})
                    except Exception as exc:
                        violations.append({
                            "policy_id": pid,
                            "message":   f"Permission check '{pid}' raised: {exc}",
                        })

            # max_ops is checked at transaction level, not single-op

        return {"valid": len(violations) == 0, "violations": violations}

    def validate_transaction(self, ops: Any) -> Dict[str, Any]:
        """Check all operations + transaction-level policies.

        Returns:
            {
                "valid": bool,
                "violations": [{"policy_id", "message", "op_index"?}],
                "op_count": int,
            }
        """
        if not isinstance(ops, list):
            return {
                "valid": False,
                "violations": [{"policy_id": "_shape", "message": "ops must be a list"}],
                "op_count": 0,
            }

        violations: List[Dict[str, Any]] = []

        # Transaction-level: max_ops
        with self._lock:
            policies = list(self._policies.values())

        for p in policies:
            if p["type"] == "max_ops":
                limit = int(p.get("config", {}).get("limit", 100))
                if len(ops) > limit:
                    msg = p["config"].get("message") or f"Transaction has {len(ops)} ops (max {limit})"
                    violations.append({"policy_id": p["id"], "message": msg})

        # Per-op checks
        for idx, op in enumerate(ops):
            result = self.validate_operation(op)
            for v in result["violations"]:
                violations.append({
                    "policy_id": v["policy_id"],
                    "message":   v["message"],
                    "op_index":  idx,
                })

        return {
            "valid":      len(violations) == 0,
            "violations": violations,
            "op_count":   len(ops),
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_type: Dict[str, int] = {}
            for p in self._policies.values():
                by_type[p["type"]] = by_type.get(p["type"], 0) + 1
            return {"total_policies": len(self._policies), "by_type": by_type}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_CONSTRAINTS: Optional[RuntimeConstraints] = None
_LOCK = threading.Lock()


def get_runtime_constraints() -> RuntimeConstraints:
    global _CONSTRAINTS
    with _LOCK:
        if _CONSTRAINTS is None:
            _CONSTRAINTS = RuntimeConstraints()
        return _CONSTRAINTS


def reset_runtime_constraints_for_tests() -> None:
    global _CONSTRAINTS
    with _LOCK:
        _CONSTRAINTS = None
