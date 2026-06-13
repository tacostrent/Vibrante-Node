"""Tests for WorkflowPack (Tier 10 — §30)."""
import json
import pytest
from src.runtime.workflows.workflow_pack import (
    WorkflowPack,
    PACK_SCHEMA_VERSION,
    VALID_ENVIRONMENT_TYPES,
    get_builtin_packs,
    reset_workflow_pack_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_workflow_pack_for_tests()
    yield
    reset_workflow_pack_for_tests()


def _minimal_pack(env="industrial_hangar") -> WorkflowPack:
    return WorkflowPack(
        name             = "test_pack",
        version          = "1.0.0",
        environment_type = env,
        asset_strategy   = {"hero_categories": ["machinery"]},
        population_strategy = {"hero_max": 3},
        placement_strategy  = {"template": env},
        lighting_strategy   = {"style": "cinematic_industrial"},
        camera_strategy     = {"mode": "cinematic_push_in"},
        atmosphere_strategy = {"fog_density": "medium"},
        review_strategy     = {"production_threshold": 0.70},
    )


# ---------------------------------------------------------------------------
# Built-in packs
# ---------------------------------------------------------------------------

def test_builtin_packs_count():
    packs = get_builtin_packs()
    assert len(packs) == 5


def test_builtin_packs_names():
    names = {p.name for p in get_builtin_packs()}
    assert "industrial_hangar_pack" in names
    assert "robotics_lab_pack"      in names
    assert "control_room_pack"      in names
    assert "sci_fi_corridor_pack"   in names
    assert "abandoned_factory_pack" in names


def test_builtin_packs_environments():
    envs = {p.environment_type for p in get_builtin_packs()}
    assert envs == VALID_ENVIRONMENT_TYPES


def test_builtin_packs_are_valid():
    for pack in get_builtin_packs():
        errors = pack.validate()
        assert errors == [], f"{pack.name}: {errors}"


def test_builtin_pack_has_builtin_metadata():
    for pack in get_builtin_packs():
        assert pack.metadata.get("builtin") is True


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip
# ---------------------------------------------------------------------------

def test_to_dict_keys():
    pack = _minimal_pack()
    d    = pack.to_dict()
    for key in ("pack_id", "name", "version", "environment_type",
                "asset_strategy", "lighting_strategy", "camera_strategy",
                "atmosphere_strategy", "review_strategy"):
        assert key in d


def test_round_trip():
    pack  = _minimal_pack()
    d     = pack.to_dict()
    pack2 = WorkflowPack.from_dict(d)
    assert pack2.name             == pack.name
    assert pack2.environment_type == pack.environment_type
    assert pack2.lighting_strategy == pack.lighting_strategy


def test_to_json_sorted_keys():
    pack = _minimal_pack()
    s    = pack.to_json()
    keys = list(json.loads(s).keys())
    assert keys == sorted(keys)


def test_from_json_round_trip():
    pack  = _minimal_pack()
    pack2 = WorkflowPack.from_json(pack.to_json())
    assert pack2.name             == pack.name
    assert pack2.environment_type == pack.environment_type


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------

def test_validate_valid():
    assert _minimal_pack().validate() == []


def test_validate_empty_name():
    pack = _minimal_pack()
    pack.name = ""
    assert any("name" in e for e in pack.validate())


def test_validate_unknown_environment():
    pack = _minimal_pack(env="unknown_place")
    errs = pack.validate()
    assert any("unknown_place" in e for e in errs)


def test_validate_empty_asset_strategy():
    pack = _minimal_pack()
    pack.asset_strategy = {}
    assert any("asset_strategy" in e for e in pack.validate())


def test_validate_empty_lighting_strategy():
    pack = _minimal_pack()
    pack.lighting_strategy = {}
    assert any("lighting_strategy" in e for e in pack.validate())


def test_validate_threshold_out_of_range():
    pack = _minimal_pack()
    pack.review_strategy = {"production_threshold": 1.5}
    assert any("threshold" in e for e in pack.validate())


# ---------------------------------------------------------------------------
# clone()
# ---------------------------------------------------------------------------

def test_clone_new_identity():
    pack  = _minimal_pack()
    clone = pack.clone(name="clone_pack")
    assert clone.name    == "clone_pack"
    assert clone.pack_id != pack.pack_id


def test_clone_preserves_strategy():
    pack  = _minimal_pack()
    clone = pack.clone()
    assert clone.lighting_strategy == pack.lighting_strategy
    assert clone.environment_type  == pack.environment_type


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

def test_schema_version_present():
    pack = _minimal_pack()
    assert pack.schema_version == PACK_SCHEMA_VERSION
