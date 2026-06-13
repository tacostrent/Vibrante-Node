"""
Tests for AssetInstancer (Tier 13)
"""
import pytest
import uuid

from src.runtime.assets.realization import (
    get_asset_instancer,
    reset_asset_instancer_for_tests,
    AssetInstance,
    InstancePlan,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_asset_instancer_for_tests()
    yield
    reset_asset_instancer_for_tests()


def test_singleton():
    assert get_asset_instancer() is get_asset_instancer()


def test_create_instance_returns_asset_instance():
    inst = get_asset_instancer().create_instance({"asset_id": "i1", "name": "Tank"})
    assert isinstance(inst, AssetInstance)
    assert inst.asset_id == "i1"


def test_create_instance_has_uuid_instance_id():
    inst = get_asset_instancer().create_instance({"asset_id": "i2"})
    # instance_id should be a non-empty string
    assert isinstance(inst.instance_id, str)
    assert len(inst.instance_id) > 0


def test_create_instance_default_transform_zeros():
    inst = get_asset_instancer().create_instance({"asset_id": "i3"})
    assert abs(inst.transform.get("tx", 0.0)) < 1e-6
    assert abs(inst.transform.get("ty", 0.0)) < 1e-6
    assert abs(inst.transform.get("tz", 0.0)) < 1e-6
    # Scale should default to 1.0
    assert abs(inst.transform.get("sx", 1.0) - 1.0) < 1e-6


def test_create_instances_with_3_transforms():
    transforms = [
        {"tx": 0.0, "ty": 0.0, "tz": 0.0},
        {"tx": 5.0, "ty": 0.0, "tz": 0.0},
        {"tx": 10.0, "ty": 0.0, "tz": 0.0},
    ]
    plan = get_asset_instancer().create_instances({"asset_id": "i4"}, transforms)
    assert isinstance(plan, InstancePlan)
    assert plan.instance_count == 3
    assert len(plan.instances) == 3


def test_build_instance_metadata_returns_dict():
    meta = get_asset_instancer().build_instance_metadata({
        "category": "vehicle",
        "style": "sci_fi",
    })
    assert isinstance(meta, dict)
    assert "category" in meta
    assert meta["category"] == "vehicle"


def test_validate_instance_valid():
    inst = get_asset_instancer().create_instance({"asset_id": "i5", "name": "Robot"})
    validation = get_asset_instancer().validate_instance(inst)
    assert "valid" in validation
    assert validation["valid"] is True


def test_asset_instance_to_dict_from_dict():
    inst = get_asset_instancer().create_instance(
        {"asset_id": "i6", "name": "Box"},
        transform={"tx": 1.0, "ty": 2.0, "tz": 3.0},
    )
    d = inst.to_dict()
    restored = AssetInstance.from_dict(d)
    assert restored.asset_id == inst.asset_id
    assert abs(restored.transform["tx"] - 1.0) < 1e-6


def test_created_at_is_float():
    inst = get_asset_instancer().create_instance({"asset_id": "i7"})
    assert isinstance(inst.created_at, float)
    assert inst.created_at > 0


def test_never_raises():
    inst = get_asset_instancer().create_instance(None)  # type: ignore
    assert isinstance(inst, AssetInstance)
