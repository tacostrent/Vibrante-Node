"""
Unit tests for src.runtime.capability_registry.

Covers:
  • built-in capabilities are pre-registered
  • register_capability / deregister_capability
  • query_capabilities with and without type filter
  • supports() lookup
  • get() lookup
  • invalid type raises ValueError
  • stats() shape
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.capability_registry import (
    CapabilityRegistry,
    CAPABILITY_TYPES,
    get_capability_registry,
    reset_capability_registry_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_capability_registry_for_tests()
    yield
    reset_capability_registry_for_tests()


# ---------------------------------------------------------------------------
# Built-ins
# ---------------------------------------------------------------------------

def test_builtin_houdini_ops_registered():
    r = get_capability_registry()
    for op_id in ("create_node", "set_parms", "connect_nodes", "delete_node",
                  "set_display_flag", "set_render_flag", "cook_node",
                  "layout_children", "build_node_chain"):
        assert r.supports(op_id), f"Expected built-in houdini_op '{op_id}'"


def test_builtin_runtime_services_registered():
    r = get_capability_registry()
    for svc in ("transaction_manager", "scene_cache", "dependency_graph",
                "validation_engine", "audit_store", "execution_scheduler",
                "mcp_runtime"):
        assert r.supports(svc), f"Expected built-in runtime_service '{svc}'"


def test_builtin_houdini_dcc_registered():
    assert get_capability_registry().supports("houdini")


def test_builtin_renderers_registered():
    r = get_capability_registry()
    for renderer in ("karma", "mantra", "arnold", "redshift", "vray", "opengl"):
        assert r.supports(renderer), f"Expected built-in renderer '{renderer}'"


# ---------------------------------------------------------------------------
# Register / deregister
# ---------------------------------------------------------------------------

def test_register_new_capability():
    r = get_capability_registry()
    r.register_capability("mcp_server", "my_mcp_server", {"url": "http://localhost"})
    assert r.supports("my_mcp_server")


def test_register_overwrites_existing():
    r = get_capability_registry()
    r.register_capability("renderer", "karma", {"rop_type": "karma_new"})
    cap = r.get("karma")
    assert cap["metadata"]["rop_type"] == "karma_new"


def test_deregister_returns_true_if_found():
    r = get_capability_registry()
    r.register_capability("mcp_server", "tmp_srv", {})
    assert r.deregister_capability("tmp_srv") is True
    assert not r.supports("tmp_srv")


def test_deregister_returns_false_if_not_found():
    assert get_capability_registry().deregister_capability("does_not_exist") is False


def test_register_invalid_type_raises():
    with pytest.raises(ValueError, match="Unknown capability type"):
        get_capability_registry().register_capability("bad_type", "foo", {})


def test_register_empty_id_raises():
    with pytest.raises(ValueError):
        get_capability_registry().register_capability("renderer", "", {})


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def test_query_all_returns_list():
    caps = get_capability_registry().query_capabilities()
    assert isinstance(caps, list)
    assert len(caps) > 0


def test_query_by_type_filters():
    r = get_capability_registry()
    ops = r.query_capabilities(cap_type="houdini_op")
    assert all(c["type"] == "houdini_op" for c in ops)
    assert len(ops) > 0


def test_query_empty_type_returns_empty():
    r = get_capability_registry()
    result = r.query_capabilities(cap_type="mcp_server")
    # No MCP servers registered by default
    assert result == []


def test_query_sorted_by_type_then_id():
    caps = get_capability_registry().query_capabilities()
    pairs = [(c["type"], c["id"]) for c in caps]
    assert pairs == sorted(pairs)


# ---------------------------------------------------------------------------
# supports / get
# ---------------------------------------------------------------------------

def test_supports_known():
    assert get_capability_registry().supports("karma") is True


def test_supports_unknown():
    assert get_capability_registry().supports("nonexistent_xyz") is False


def test_get_returns_dict():
    cap = get_capability_registry().get("karma")
    assert isinstance(cap, dict)
    assert cap["id"] == "karma"
    assert cap["type"] == "renderer"


def test_get_unknown_returns_none():
    assert get_capability_registry().get("nonexistent") is None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    s = get_capability_registry().stats()
    assert "total" in s
    assert "by_type" in s
    assert s["total"] > 0
    assert "houdini_op" in s["by_type"]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_capability_registry()
    b = get_capability_registry()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_capability_registry()
    reset_capability_registry_for_tests()
    b = get_capability_registry()
    assert a is not b


def test_reset_restores_builtins():
    r = get_capability_registry()
    r.deregister_capability("karma")
    reset_capability_registry_for_tests()
    assert get_capability_registry().supports("karma")
