"""
Unit tests for src.runtime.semantic_registry.

Covers:
  • built-in operations registered
  • register_operation / deregister_operation
  • get_operation returns metadata (no handler)
  • list_operations with and without tag filter
  • resolve_to_execution_plan with known operation
  • resolve with unknown operation returns ok=False
  • handler raising exception returns ok=False
  • handler returning non-list returns ok=False
  • context variables flow into handler output
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.semantic_registry import (
    SemanticRegistry,
    get_semantic_registry,
    reset_semantic_registry_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_semantic_registry_for_tests()
    yield
    reset_semantic_registry_for_tests()


# ---------------------------------------------------------------------------
# Built-ins
# ---------------------------------------------------------------------------

def test_builtin_operations_registered():
    r = get_semantic_registry()
    ids = {op["operation_id"] for op in r.list_operations()}
    for expected in ("create_geo_container", "build_pyro_source", "setup_karma_renderer",
                     "export_to_usd", "cache_geometry", "asset_publish_scaffold",
                     "solaris_lighting_setup"):
        assert expected in ids, f"Expected built-in '{expected}'"


def test_builtin_operations_have_required_keys():
    r = get_semantic_registry()
    for op in r.list_operations():
        assert "operation_id" in op
        assert "description" in op
        assert "handler" not in op, "handler must not appear in metadata output"


# ---------------------------------------------------------------------------
# register_operation / deregister_operation
# ---------------------------------------------------------------------------

def test_register_custom_operation():
    r = get_semantic_registry()
    called = []

    def my_handler(ctx):
        called.append(ctx)
        return [{"op": "create_node", "parent": ctx.get("parent", "/obj"), "type": "geo"}]

    r.register_operation("my_op", {"description": "custom", "tags": ["test"]}, my_handler)
    assert r.get_operation("my_op") is not None
    plan = r.resolve_to_execution_plan("my_op", {"parent": "/obj"})
    assert plan["ok"] is True
    assert len(plan["operations"]) == 1
    assert called[0]["parent"] == "/obj"


def test_register_overwrites_existing():
    r = get_semantic_registry()
    r.register_operation("my_op", {"description": "v1"}, lambda ctx: [])
    r.register_operation("my_op", {"description": "v2"}, lambda ctx: [{"op": "layout_children"}])
    plan = r.resolve_to_execution_plan("my_op", {})
    assert plan["ok"] is True
    assert plan["operations"][0]["op"] == "layout_children"


def test_deregister_operation():
    r = get_semantic_registry()
    r.register_operation("tmp_op", {}, lambda ctx: [])
    assert r.deregister_operation("tmp_op") is True
    assert r.get_operation("tmp_op") is None


def test_deregister_unknown_returns_false():
    assert get_semantic_registry().deregister_operation("nonexistent_op_xyz") is False


def test_register_empty_id_raises():
    with pytest.raises(ValueError, match="operation_id"):
        get_semantic_registry().register_operation("", {}, lambda ctx: [])


def test_register_non_callable_handler_raises():
    with pytest.raises(ValueError, match="callable"):
        get_semantic_registry().register_operation("op", {}, "not a function")


# ---------------------------------------------------------------------------
# get_operation
# ---------------------------------------------------------------------------

def test_get_operation_returns_metadata_no_handler():
    r = get_semantic_registry()
    meta = r.get_operation("create_geo_container")
    assert meta is not None
    assert "handler" not in meta
    assert meta["operation_id"] == "create_geo_container"


def test_get_operation_unknown_returns_none():
    assert get_semantic_registry().get_operation("does_not_exist") is None


# ---------------------------------------------------------------------------
# list_operations
# ---------------------------------------------------------------------------

def test_list_operations_sorted():
    r = get_semantic_registry()
    ops = r.list_operations()
    ids = [op["operation_id"] for op in ops]
    assert ids == sorted(ids)


def test_list_operations_tag_filter():
    r = get_semantic_registry()
    vfx_ops = r.list_operations(tag="vfx")
    assert len(vfx_ops) > 0
    assert all("vfx" in op.get("tags", []) for op in vfx_ops)


def test_list_operations_no_match_tag():
    r = get_semantic_registry()
    result = r.list_operations(tag="nonexistent_tag_xyz")
    assert result == []


# ---------------------------------------------------------------------------
# resolve_to_execution_plan
# ---------------------------------------------------------------------------

def test_resolve_create_geo_container():
    r = get_semantic_registry()
    plan = r.resolve_to_execution_plan("create_geo_container", {"parent": "/obj", "name": "my_geo"})
    assert plan["ok"] is True
    assert plan["operation_id"] == "create_geo_container"
    assert len(plan["operations"]) >= 1
    assert plan["operations"][0]["op"] == "create_node"
    assert plan["operations"][0]["name"] == "my_geo"


def test_resolve_build_pyro_source_returns_build_chain():
    r = get_semantic_registry()
    plan = r.resolve_to_execution_plan("build_pyro_source", {
        "parent": "/obj", "name": "fire", "radius": "2.0"
    })
    assert plan["ok"] is True
    op = plan["operations"][0]
    assert op["op"] == "build_node_chain"
    node_types = [n["type"] for n in op["spec"]["nodes"]]
    assert "pyro_source" in node_types


def test_resolve_unknown_operation_returns_not_ok():
    r = get_semantic_registry()
    plan = r.resolve_to_execution_plan("unknown_operation_xyz", {})
    assert plan["ok"] is False
    assert "unknown_operation_xyz" in plan["error"]


def test_resolve_with_defaults_when_context_empty():
    r = get_semantic_registry()
    plan = r.resolve_to_execution_plan("create_geo_container", {})
    assert plan["ok"] is True
    op = plan["operations"][0]
    # Handler uses defaults: parent=/obj, name=geo1
    assert op["parent"] == "/obj"
    assert op["name"] == "geo1"


def test_resolve_handler_raising_returns_not_ok():
    r = get_semantic_registry()

    def boom(ctx):
        raise RuntimeError("intentional failure")

    r.register_operation("boom_op", {}, boom)
    plan = r.resolve_to_execution_plan("boom_op", {})
    assert plan["ok"] is False
    assert "intentional failure" in plan["error"]


def test_resolve_handler_returning_non_list_returns_not_ok():
    r = get_semantic_registry()
    r.register_operation("bad_return", {}, lambda ctx: "not a list")
    plan = r.resolve_to_execution_plan("bad_return", {})
    assert plan["ok"] is False
    assert "list" in plan["error"]


def test_resolve_op_count_matches():
    r = get_semantic_registry()
    plan = r.resolve_to_execution_plan("setup_karma_renderer", {
        "name": "k1", "output_path": "$HIP/out.exr"
    })
    assert plan["ok"] is True
    assert plan["op_count"] == len(plan["operations"])


# ---------------------------------------------------------------------------
# Context flows into handler output
# ---------------------------------------------------------------------------

def test_context_vars_used_in_create_geo():
    r = get_semantic_registry()
    plan = r.resolve_to_execution_plan("create_geo_container", {
        "parent": "/obj/mycontainer", "name": "custom_geo"
    })
    op = plan["operations"][0]
    assert op["parent"] == "/obj/mycontainer"
    assert op["name"] == "custom_geo"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_semantic_registry()
    b = get_semantic_registry()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_semantic_registry()
    reset_semantic_registry_for_tests()
    b = get_semantic_registry()
    assert a is not b
