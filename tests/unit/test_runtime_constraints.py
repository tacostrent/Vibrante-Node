"""
Unit tests for src.runtime.runtime_constraints.

Covers:
  • built-in policies active on fresh instance
  • validate_operation passes clean ops
  • protected_path policy blocks writes to /stage and /out
  • forbidden_op policy
  • forbidden_node_type policy (create_node + build_node_chain)
  • max_ops applies to validate_transaction
  • permission policy with callable check
  • add_policy / remove_policy (builtin blocks removal)
  • validate_transaction aggregates per-op violations
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.runtime_constraints import (
    RuntimeConstraints,
    get_runtime_constraints,
    reset_runtime_constraints_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_runtime_constraints_for_tests()
    yield
    reset_runtime_constraints_for_tests()


# ---------------------------------------------------------------------------
# Built-in policies
# ---------------------------------------------------------------------------

def test_fresh_instance_has_builtin_policies():
    r = get_runtime_constraints()
    policies = r.list_policies()
    ids = {p["id"] for p in policies}
    assert "_builtin_protect_stage" in ids
    assert "_builtin_protect_out" in ids
    assert "_builtin_max_ops" in ids


# ---------------------------------------------------------------------------
# validate_operation — clean ops pass
# ---------------------------------------------------------------------------

def test_clean_create_op_passes():
    r = get_runtime_constraints()
    result = r.validate_operation({"op": "create_node", "parent": "/obj", "type": "geo"})
    assert result["valid"] is True
    assert result["violations"] == []


def test_clean_set_parms_passes():
    r = get_runtime_constraints()
    result = r.validate_operation({"op": "set_parms", "node": "/obj/geo1", "parms": {"tx": 1.0}})
    assert result["valid"] is True


# ---------------------------------------------------------------------------
# Protected path — /stage
# ---------------------------------------------------------------------------

def test_create_inside_stage_is_blocked():
    r = get_runtime_constraints()
    result = r.validate_operation({"op": "create_node", "parent": "/stage", "type": "geo"})
    assert result["valid"] is False
    assert any("_builtin_protect_stage" == v["policy_id"] for v in result["violations"])


def test_create_inside_stage_subpath_is_blocked():
    r = get_runtime_constraints()
    result = r.validate_operation({"op": "create_node", "parent": "/stage/look", "type": "geo"})
    assert result["valid"] is False


def test_set_parms_on_stage_node_is_blocked():
    r = get_runtime_constraints()
    result = r.validate_operation({"op": "set_parms", "node": "/stage/light1", "parms": {}})
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# Protected path — /out
# ---------------------------------------------------------------------------

def test_delete_inside_out_is_blocked():
    r = get_runtime_constraints()
    result = r.validate_operation({"op": "delete_node", "path": "/out/karma1"})
    assert result["valid"] is False
    assert any("_builtin_protect_out" == v["policy_id"] for v in result["violations"])


def test_create_in_safe_path_is_ok():
    r = get_runtime_constraints()
    result = r.validate_operation({"op": "create_node", "parent": "/obj", "type": "geo"})
    assert result["valid"] is True


# ---------------------------------------------------------------------------
# forbidden_op policy
# ---------------------------------------------------------------------------

def test_forbidden_op_blocks_delete():
    r = get_runtime_constraints()
    r.add_policy("forbidden_op", "no_delete", {"op": "delete_node", "message": "no deletes allowed"})
    result = r.validate_operation({"op": "delete_node", "path": "/obj/old"})
    assert result["valid"] is False
    assert any("no_delete" == v["policy_id"] for v in result["violations"])


def test_non_forbidden_op_passes():
    r = get_runtime_constraints()
    r.add_policy("forbidden_op", "no_delete", {"op": "delete_node"})
    result = r.validate_operation({"op": "create_node", "parent": "/obj", "type": "geo"})
    assert result["valid"] is True


# ---------------------------------------------------------------------------
# forbidden_node_type policy
# ---------------------------------------------------------------------------

def test_forbidden_node_type_blocks_create():
    r = get_runtime_constraints()
    r.add_policy("forbidden_node_type", "no_python", {"node_type": "python"})
    result = r.validate_operation({"op": "create_node", "parent": "/obj/geo1", "type": "python"})
    assert result["valid"] is False


def test_forbidden_node_type_case_insensitive():
    r = get_runtime_constraints()
    r.add_policy("forbidden_node_type", "no_python", {"node_type": "python"})
    result = r.validate_operation({"op": "create_node", "parent": "/obj", "type": "PYTHON"})
    assert result["valid"] is False


def test_forbidden_node_type_in_build_chain():
    r = get_runtime_constraints()
    r.add_policy("forbidden_node_type", "no_python", {"node_type": "python"})
    result = r.validate_operation({
        "op": "build_node_chain",
        "spec": {
            "nodes": [{"id": "n1", "parent": "/obj", "type": "python", "name": "bad"}],
            "connections": [],
        }
    })
    assert result["valid"] is False


def test_allowed_node_type_passes():
    r = get_runtime_constraints()
    r.add_policy("forbidden_node_type", "no_python", {"node_type": "python"})
    result = r.validate_operation({"op": "create_node", "parent": "/obj", "type": "geo"})
    assert result["valid"] is True


# ---------------------------------------------------------------------------
# max_ops
# ---------------------------------------------------------------------------

def test_max_ops_builtin_blocks_over_100():
    r = get_runtime_constraints()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo"}] * 101
    result = r.validate_transaction(ops)
    assert result["valid"] is False
    assert any("_builtin_max_ops" == v["policy_id"] for v in result["violations"])


def test_max_ops_exactly_at_limit_passes():
    r = get_runtime_constraints()
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo"}] * 100
    result = r.validate_transaction(ops)
    # No max_ops violation (exactly at limit)
    max_violations = [v for v in result["violations"] if v["policy_id"] == "_builtin_max_ops"]
    assert max_violations == []


def test_custom_max_ops_policy():
    r = get_runtime_constraints()
    r.add_policy("max_ops", "small_cap", {"limit": 3})
    ops = [{"op": "create_node", "parent": "/obj", "type": "geo"}] * 4
    result = r.validate_transaction(ops)
    assert result["valid"] is False
    assert any("small_cap" == v["policy_id"] for v in result["violations"])


# ---------------------------------------------------------------------------
# permission policy
# ---------------------------------------------------------------------------

def test_permission_policy_callable():
    r = get_runtime_constraints()
    r.add_policy("permission", "no_geo_nodes", {
        "check": lambda op: str(op.get("type", "")) != "geo",
        "message": "geo nodes not permitted",
    })
    result = r.validate_operation({"op": "create_node", "parent": "/obj", "type": "geo"})
    assert result["valid"] is False
    assert any("no_geo_nodes" == v["policy_id"] for v in result["violations"])


def test_permission_policy_raising_check_captured():
    r = get_runtime_constraints()
    def bad_check(op):
        raise RuntimeError("oops")
    r.add_policy("permission", "explode", {"check": bad_check})
    result = r.validate_operation({"op": "create_node", "parent": "/obj", "type": "geo"})
    assert result["valid"] is False
    assert any("oops" in v["message"] for v in result["violations"])


# ---------------------------------------------------------------------------
# add_policy / remove_policy
# ---------------------------------------------------------------------------

def test_add_and_remove_custom_policy():
    r = get_runtime_constraints()
    r.add_policy("forbidden_op", "my_rule", {"op": "cook_node"})
    assert r.get_policy("my_rule") is not None
    removed = r.remove_policy("my_rule")
    assert removed is True
    assert r.get_policy("my_rule") is None


def test_remove_builtin_returns_false():
    r = get_runtime_constraints()
    assert r.remove_policy("_builtin_protect_stage") is False


def test_remove_unknown_returns_false():
    r = get_runtime_constraints()
    assert r.remove_policy("does_not_exist") is False


def test_add_policy_invalid_type_raises():
    r = get_runtime_constraints()
    with pytest.raises(ValueError, match="Unknown policy type"):
        r.add_policy("bad_type", "x", {})


def test_add_policy_builtin_prefix_raises():
    r = get_runtime_constraints()
    with pytest.raises(ValueError, match="reserved"):
        r.add_policy("forbidden_op", "_builtin_foo", {"op": "cook_node"})


# ---------------------------------------------------------------------------
# validate_transaction
# ---------------------------------------------------------------------------

def test_validate_transaction_clean_ops():
    r = get_runtime_constraints()
    ops = [
        {"op": "create_node", "parent": "/obj", "type": "geo"},
        {"op": "set_parms", "node": "/obj/geo1", "parms": {"tx": 1.0}},
    ]
    result = r.validate_transaction(ops)
    assert result["valid"] is True
    assert result["op_count"] == 2


def test_validate_transaction_captures_op_index():
    r = get_runtime_constraints()
    ops = [
        {"op": "create_node", "parent": "/obj", "type": "geo"},
        {"op": "create_node", "parent": "/stage", "type": "geo"},  # index 1 — violates stage
    ]
    result = r.validate_transaction(ops)
    assert result["valid"] is False
    stage_violation = next(v for v in result["violations"] if v["policy_id"] == "_builtin_protect_stage")
    assert stage_violation["op_index"] == 1


def test_validate_transaction_non_list_invalid():
    r = get_runtime_constraints()
    result = r.validate_transaction("not a list")
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_runtime_constraints()
    b = get_runtime_constraints()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_runtime_constraints()
    reset_runtime_constraints_for_tests()
    b = get_runtime_constraints()
    assert a is not b


def test_reset_restores_builtins():
    r = get_runtime_constraints()
    r.add_policy("forbidden_op", "tmp_rule", {"op": "cook_node"})
    reset_runtime_constraints_for_tests()
    r2 = get_runtime_constraints()
    assert r2.get_policy("tmp_rule") is None
    assert r2.get_policy("_builtin_protect_stage") is not None
