"""Tests for LayoutApplicationEngine (dry-run / op-dict mode) — §47."""
import pytest
from src.runtime.layout_realization import (
    get_layout_application_engine,
    reset_layout_application_engine_for_tests,
    ResolvedTransform,
)


@pytest.fixture(autouse=True)
def reset():
    reset_layout_application_engine_for_tests()
    yield
    reset_layout_application_engine_for_tests()


def _xf(asset_id, tx=0.0, ty=0.0, tz=0.0, ry=0.0):
    return ResolvedTransform(asset_id=asset_id, asset_name=asset_id,
                             tx=tx, ty=ty, tz=tz, ry=ry)


# ---- build_transform_op_dicts (no bridge needed) ---------------------------

def test_op_dicts_produced_for_mapped_assets():
    transforms = [_xf("table_01", tx=1.0, ty=0.0, tz=-2.0, ry=45.0)]
    node_path_map = {"table_01": "/obj/geo1/null_table"}
    ops = get_layout_application_engine().build_transform_op_dicts(transforms, node_path_map)
    assert len(ops) == 1
    op = ops[0]
    assert op["type"] == "set_parms"
    assert op["node_path"] == "/obj/geo1/null_table"
    assert op["parms"]["tx"] == pytest.approx(1.0)
    assert op["parms"]["ry"] == pytest.approx(45.0)


def test_unmapped_assets_skipped_in_op_dicts():
    transforms = [_xf("mapped"), _xf("unmapped")]
    node_path_map = {"mapped": "/obj/geo1/null_mapped"}
    ops = get_layout_application_engine().build_transform_op_dicts(transforms, node_path_map)
    assert len(ops) == 1
    assert ops[0]["node_path"] == "/obj/geo1/null_mapped"


def test_all_six_dof_in_op_dict():
    xf = ResolvedTransform(
        asset_id="a", asset_name="a",
        tx=1.0, ty=0.75, tz=-2.0,
        rx=0.0, ry=90.0, rz=0.0,
    )
    ops = get_layout_application_engine().build_transform_op_dicts(
        [xf], {"a": "/obj/null"}
    )
    parms = ops[0]["parms"]
    assert set(parms.keys()) >= {"tx", "ty", "tz", "rx", "ry", "rz"}


def test_empty_transforms_returns_empty_ops():
    ops = get_layout_application_engine().build_transform_op_dicts([], {})
    assert ops == []


def test_multiple_assets_multiple_ops():
    transforms = [_xf(f"a{i}", tx=float(i)) for i in range(5)]
    path_map   = {f"a{i}": f"/obj/null_{i}" for i in range(5)}
    ops = get_layout_application_engine().build_transform_op_dicts(transforms, path_map)
    assert len(ops) == 5


def test_ty_preserved_in_op():
    xf = _xf("bottle", tx=0.3, ty=0.9, tz=0.0)   # bottle on bar counter
    ops = get_layout_application_engine().build_transform_op_dicts(
        [xf], {"bottle": "/obj/bottle"}
    )
    assert ops[0]["parms"]["ty"] == pytest.approx(0.9)


def test_no_bridge_called_in_op_dict_mode():
    """build_transform_op_dicts must never call the bridge."""
    xf = _xf("a", tx=1.0)
    ops = get_layout_application_engine().build_transform_op_dicts([xf], {"a": "/obj/null"})
    assert len(ops) == 1  # if bridge was called we'd get an error in test env
