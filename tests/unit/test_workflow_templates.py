"""
Unit tests for src.runtime.workflow_templates.

Covers:
  • built-in templates are registered
  • list_templates returns all / filtered by tag
  • get_template returns deep copy
  • apply_template with full context
  • variable interpolation in nested dicts/lists
  • missing variable raises KeyError
  • register_template / deregister_template
  • invalid template shape raises ValueError
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.workflow_templates import (
    WorkflowTemplates,
    get_workflow_templates,
    reset_workflow_templates_for_tests,
    _interpolate,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_workflow_templates_for_tests()
    yield
    reset_workflow_templates_for_tests()


# ---------------------------------------------------------------------------
# Built-ins
# ---------------------------------------------------------------------------

def test_builtin_templates_registered():
    wt = get_workflow_templates()
    ids = {t["template_id"] for t in wt.list_templates()}
    for expected in ("pyro_source", "usd_export", "karma_render",
                     "geometry_cache", "asset_publish", "vfx_container",
                     "solaris_lighting_setup"):
        assert expected in ids, f"Expected built-in template '{expected}'"


def test_builtin_templates_have_required_keys():
    wt = get_workflow_templates()
    for t in wt.list_templates():
        assert "template_id" in t
        assert "description" in t
        assert "operations" in t
        assert isinstance(t["operations"], list)


# ---------------------------------------------------------------------------
# list_templates
# ---------------------------------------------------------------------------

def test_list_templates_sorted():
    wt = get_workflow_templates()
    ids = [t["template_id"] for t in wt.list_templates()]
    assert ids == sorted(ids)


def test_list_templates_tag_filter():
    wt = get_workflow_templates()
    vfx = wt.list_templates(tag="vfx")
    assert len(vfx) > 0
    assert all("vfx" in t.get("tags", []) for t in vfx)


def test_list_templates_tag_no_match():
    wt = get_workflow_templates()
    result = wt.list_templates(tag="nonexistent_tag_xyz")
    assert result == []


# ---------------------------------------------------------------------------
# get_template
# ---------------------------------------------------------------------------

def test_get_template_returns_copy():
    wt = get_workflow_templates()
    t = wt.get_template("usd_export")
    assert t is not None
    assert t["template_id"] == "usd_export"
    # Modify copy — original must be unaffected
    t["template_id"] = "mutated"
    assert wt.get_template("usd_export")["template_id"] == "usd_export"


def test_get_template_unknown_returns_none():
    assert get_workflow_templates().get_template("does_not_exist") is None


# ---------------------------------------------------------------------------
# apply_template
# ---------------------------------------------------------------------------

def test_apply_usd_export_template():
    wt = get_workflow_templates()
    ops = wt.apply_template("usd_export", {
        "name": "my_export", "output_path": "$HIP/out.usd",
        "frame_start": "1", "frame_end": "100",
    })
    assert isinstance(ops, list)
    assert len(ops) >= 1
    # The first op should be a create_node for /out
    create_op = ops[0]
    assert create_op["op"] == "create_node"
    assert create_op["name"] == "my_export_usd_out"


def test_apply_karma_render_template():
    wt = get_workflow_templates()
    ops = wt.apply_template("karma_render", {
        "name": "karma1", "stage_path": "/stage",
        "output_path": "$HIP/render.exr", "res_x": "1920", "res_y": "1080",
    })
    assert any(op["op"] == "create_node" and "karma" in op.get("type", "") for op in ops)


def test_apply_asset_publish_template():
    wt = get_workflow_templates()
    ops = wt.apply_template("asset_publish", {"parent": "/obj", "asset_name": "hero_asset"})
    assert len(ops) == 1
    assert ops[0]["op"] == "build_node_chain"
    spec = ops[0]["spec"]
    names = [n["name"] for n in spec["nodes"]]
    assert "hero_asset" in names
    assert "INPUT" in names
    assert "OUTPUT" in names


def test_apply_template_unknown_raises_key_error():
    wt = get_workflow_templates()
    with pytest.raises(KeyError):
        wt.apply_template("nonexistent_template_xyz", {})


def test_apply_template_missing_var_raises_key_error():
    wt = get_workflow_templates()
    with pytest.raises(KeyError):
        # usd_export requires "name", "output_path", etc.
        wt.apply_template("usd_export", {})  # no context vars


# ---------------------------------------------------------------------------
# Variable interpolation
# ---------------------------------------------------------------------------

def test_interpolate_string():
    assert _interpolate("{name}_geo", {"name": "hero"}) == "hero_geo"


def test_interpolate_nested_dict():
    obj = {"params": {"tx": "{x}", "ty": "{y}"}}
    result = _interpolate(obj, {"x": "1.0", "y": "2.0"})
    assert result == {"params": {"tx": "1.0", "ty": "2.0"}}


def test_interpolate_list():
    obj = ["{a}", "{b}"]
    result = _interpolate(obj, {"a": "foo", "b": "bar"})
    assert result == ["foo", "bar"]


def test_interpolate_non_string_values_passthrough():
    obj = {"count": 42, "flag": True}
    result = _interpolate(obj, {})
    assert result == obj


def test_interpolate_missing_key_raises():
    with pytest.raises(KeyError):
        _interpolate("{missing_var}", {})


# ---------------------------------------------------------------------------
# register_template / deregister_template
# ---------------------------------------------------------------------------

def test_register_custom_template():
    wt = get_workflow_templates()
    wt.register_template({
        "template_id": "my_custom",
        "description": "A custom template",
        "operations": [{"op": "create_node", "parent": "/obj", "type": "geo", "name": "{name}"}],
        "required_capabilities": [],
        "tags": ["custom"],
    })
    assert wt.get_template("my_custom") is not None
    ops = wt.apply_template("my_custom", {"name": "test_geo"})
    assert ops[0]["name"] == "test_geo"


def test_register_overwrites_existing():
    wt = get_workflow_templates()
    wt.register_template({
        "template_id": "usd_export",
        "description": "overwritten",
        "operations": [],
    })
    t = wt.get_template("usd_export")
    assert t["description"] == "overwritten"


def test_deregister_template():
    wt = get_workflow_templates()
    wt.register_template({
        "template_id": "temp_tpl",
        "description": "temp",
        "operations": [],
    })
    assert wt.deregister_template("temp_tpl") is True
    assert wt.get_template("temp_tpl") is None


def test_deregister_unknown_returns_false():
    assert get_workflow_templates().deregister_template("nonexistent") is False


def test_register_template_missing_operations_raises():
    wt = get_workflow_templates()
    with pytest.raises(ValueError, match="operations"):
        wt.register_template({"template_id": "bad_tpl"})


def test_register_template_missing_id_raises():
    wt = get_workflow_templates()
    with pytest.raises(ValueError, match="template_id"):
        wt.register_template({"operations": []})


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_workflow_templates()
    b = get_workflow_templates()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_workflow_templates()
    reset_workflow_templates_for_tests()
    b = get_workflow_templates()
    assert a is not b
