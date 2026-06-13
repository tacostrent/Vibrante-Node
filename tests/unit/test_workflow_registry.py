"""Tests for WorkflowRegistry (Tier 10 — §30)."""
import pytest
from src.runtime.workflows.workflow_registry import (
    WorkflowRegistry,
    get_workflow_registry,
    reset_workflow_registry_for_tests,
)
from src.runtime.workflows.workflow_pack import (
    WorkflowPack,
    get_builtin_packs,
    reset_workflow_pack_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_workflow_registry_for_tests()
    reset_workflow_pack_for_tests()
    yield
    reset_workflow_registry_for_tests()
    reset_workflow_pack_for_tests()


def _custom_pack(name="my_custom_pack") -> WorkflowPack:
    return WorkflowPack(
        name             = name,
        version          = "1.0.0",
        environment_type = "industrial_hangar",
        asset_strategy   = {"hero_categories": ["machinery"]},
        population_strategy = {"hero_max": 3},
        placement_strategy  = {"template": "industrial_hangar"},
        lighting_strategy   = {"style": "cinematic_industrial"},
        camera_strategy     = {"mode": "cinematic_push_in"},
        atmosphere_strategy = {"fog_density": "medium"},
        review_strategy     = {"production_threshold": 0.70},
    )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_workflow_registry() is get_workflow_registry()


# ---------------------------------------------------------------------------
# Built-ins
# ---------------------------------------------------------------------------

def test_builtin_packs_loaded():
    reg   = get_workflow_registry()
    stats = reg.get_statistics()
    assert stats["builtin_pack_count"] == 5


def test_builtin_packs_retrievable():
    reg = get_workflow_registry()
    for name in ("industrial_hangar_pack", "robotics_lab_pack",
                 "control_room_pack", "sci_fi_corridor_pack", "abandoned_factory_pack"):
        assert reg.get_pack(name) is not None


# ---------------------------------------------------------------------------
# register_pack
# ---------------------------------------------------------------------------

def test_register_custom_pack():
    reg  = get_workflow_registry()
    pack = _custom_pack()
    assert reg.register_pack(pack) is True
    assert reg.get_pack("my_custom_pack") is not None


def test_register_invalid_pack_returns_false():
    reg  = get_workflow_registry()
    bad  = WorkflowPack(
        name="", version="", environment_type="",
        asset_strategy={}, population_strategy={}, placement_strategy={},
        lighting_strategy={}, camera_strategy={}, atmosphere_strategy={},
        review_strategy={},
    )
    assert reg.register_pack(bad) is False


def test_register_builtin_name_raises():
    reg  = get_workflow_registry()
    pack = _custom_pack(name="industrial_hangar_pack")
    with pytest.raises(ValueError, match="built-in"):
        reg.register_pack(pack)


# ---------------------------------------------------------------------------
# unregister_pack
# ---------------------------------------------------------------------------

def test_unregister_custom_pack():
    reg  = get_workflow_registry()
    pack = _custom_pack()
    reg.register_pack(pack)
    assert reg.unregister_pack("my_custom_pack") is True
    assert reg.get_pack("my_custom_pack") is None


def test_unregister_missing_returns_false():
    reg = get_workflow_registry()
    assert reg.unregister_pack("does_not_exist") is False


def test_unregister_builtin_raises():
    reg = get_workflow_registry()
    with pytest.raises(ValueError, match="built-in"):
        reg.unregister_pack("industrial_hangar_pack")


# ---------------------------------------------------------------------------
# list_packs
# ---------------------------------------------------------------------------

def test_list_packs_sorted():
    reg   = get_workflow_registry()
    packs = reg.list_packs()
    names = [p.name for p in packs]
    assert names == sorted(names)


def test_list_packs_by_environment():
    reg   = get_workflow_registry()
    packs = reg.list_packs(environment_type="robotics_lab")
    assert all(p.environment_type == "robotics_lab" for p in packs)


def test_list_packs_builtin_only():
    reg   = get_workflow_registry()
    reg.register_pack(_custom_pack())
    packs = reg.list_packs(builtin_only=True)
    assert len(packs) == 5
    assert all(p.name != "my_custom_pack" for p in packs)


def test_list_packs_custom_only():
    reg  = get_workflow_registry()
    reg.register_pack(_custom_pack())
    packs = reg.list_packs(custom_only=True)
    assert len(packs) == 1
    assert packs[0].name == "my_custom_pack"


# ---------------------------------------------------------------------------
# find_packs
# ---------------------------------------------------------------------------

def test_find_packs_by_tag():
    reg   = get_workflow_registry()
    packs = reg.find_packs(tags=["industrial"])
    assert len(packs) >= 1
    assert any(p.name == "industrial_hangar_pack" for p in packs)


def test_find_packs_min_threshold():
    reg   = get_workflow_registry()
    packs = reg.find_packs(min_threshold=0.70)
    for p in packs:
        assert p.review_strategy.get("production_threshold", 0) >= 0.70


# ---------------------------------------------------------------------------
# get_statistics
# ---------------------------------------------------------------------------

def test_statistics_keys():
    stats = get_workflow_registry().get_statistics()
    for key in ("total_packs", "builtin_pack_count", "custom_pack_count",
                "register_count", "query_count"):
        assert key in stats


def test_statistics_custom_count_updates():
    reg = get_workflow_registry()
    reg.register_pack(_custom_pack())
    assert reg.get_statistics()["custom_pack_count"] == 1
