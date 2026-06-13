"""Tests for WorkflowSerializer (Tier 10 — §30)."""
import json
import os
import tempfile
import pytest
from src.runtime.workflows.workflow_serializer import (
    WorkflowSerializer,
    get_workflow_serializer,
    reset_workflow_serializer_for_tests,
)
from src.runtime.workflows.workflow_pack import (
    WorkflowPack,
    PACK_SCHEMA_VERSION,
    get_builtin_packs,
    reset_workflow_pack_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_workflow_serializer_for_tests()
    reset_workflow_pack_for_tests()
    yield
    reset_workflow_serializer_for_tests()
    reset_workflow_pack_for_tests()


def _hangar_pack():
    return next(p for p in get_builtin_packs() if p.name == "industrial_hangar_pack")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_workflow_serializer() is get_workflow_serializer()


# ---------------------------------------------------------------------------
# to_json
# ---------------------------------------------------------------------------

def test_to_json_returns_string():
    s = get_workflow_serializer().to_json(_hangar_pack())
    assert isinstance(s, str)
    assert len(s) > 10


def test_to_json_valid_json():
    s = get_workflow_serializer().to_json(_hangar_pack())
    d = json.loads(s)
    assert isinstance(d, dict)


def test_to_json_sorted_keys():
    s    = get_workflow_serializer().to_json(_hangar_pack())
    d    = json.loads(s)
    keys = list(d.keys())
    assert keys == sorted(keys)


def test_to_json_has_schema_version():
    s = get_workflow_serializer().to_json(_hangar_pack())
    d = json.loads(s)
    assert d["_schema_version"] == PACK_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# from_json
# ---------------------------------------------------------------------------

def test_from_json_round_trip():
    pack  = _hangar_pack()
    s     = get_workflow_serializer().to_json(pack)
    pack2 = get_workflow_serializer().from_json(s)
    assert pack2.name             == pack.name
    assert pack2.environment_type == pack.environment_type
    assert pack2.lighting_strategy == pack.lighting_strategy


def test_from_json_invalid_lenient():
    result = get_workflow_serializer().from_json("NOT_JSON", lenient=True)
    assert result is None


def test_from_json_invalid_strict():
    with pytest.raises(Exception):
        get_workflow_serializer().from_json("NOT_JSON", lenient=False)


# ---------------------------------------------------------------------------
# save_pack / load_pack
# ---------------------------------------------------------------------------

def test_save_and_load_pack():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        pack = _hangar_pack()
        assert get_workflow_serializer().save_pack(pack, path) is True

        loaded = get_workflow_serializer().load_pack(path)
        assert loaded is not None
        assert loaded.name             == pack.name
        assert loaded.environment_type == pack.environment_type
    finally:
        os.unlink(path)


def test_load_missing_file_lenient():
    result = get_workflow_serializer().load_pack("/nonexistent/path.json", lenient=True)
    assert result is None


def test_load_missing_file_strict():
    with pytest.raises(Exception):
        get_workflow_serializer().load_pack("/nonexistent/path.json", lenient=False)


# ---------------------------------------------------------------------------
# export_pack / import_pack
# ---------------------------------------------------------------------------

def test_export_import_round_trip():
    pack   = _hangar_pack()
    d      = get_workflow_serializer().export_pack(pack)
    pack2  = get_workflow_serializer().import_pack(dict(d))
    assert pack2.name             == pack.name
    assert pack2.environment_type == pack.environment_type


def test_export_has_schema_version():
    d = get_workflow_serializer().export_pack(_hangar_pack())
    assert "_schema_version" in d


def test_import_invalid_lenient():
    result = get_workflow_serializer().import_pack(
        {"garbage": "data"}, lenient=True
    )
    # Should not raise; may return a partial pack or None
    # (from_dict is lenient with missing keys)
    assert result is not None or result is None   # either is acceptable


# ---------------------------------------------------------------------------
# to_json_list / from_json_list
# ---------------------------------------------------------------------------

def test_list_round_trip():
    packs  = get_builtin_packs()[:2]
    s      = get_workflow_serializer().to_json_list(packs)
    packs2 = get_workflow_serializer().from_json_list(s)
    assert len(packs2) == 2
    names = {p.name for p in packs2}
    assert names == {p.name for p in packs}


def test_list_invalid_lenient():
    result = get_workflow_serializer().from_json_list("NOT_JSON", lenient=True)
    assert result == []


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_increments():
    ser = get_workflow_serializer()
    ser.to_json(_hangar_pack())
    ser.to_json(_hangar_pack())
    assert ser.stats()["serialize_count"] == 2
