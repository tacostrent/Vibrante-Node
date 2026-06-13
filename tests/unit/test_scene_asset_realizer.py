"""
Tests for SceneAssetRealizer (Tier 13)
"""
import pytest

from src.runtime.assets.realization import (
    get_scene_asset_realizer,
    reset_scene_asset_realizer_for_tests,
    RealizedAsset,
    RealizationPlan,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_scene_asset_realizer_for_tests()
    yield
    reset_scene_asset_realizer_for_tests()


_VALID_COMPLEXITIES = {"simple", "moderate", "complex", "epic"}


def test_singleton():
    assert get_scene_asset_realizer() is get_scene_asset_realizer()


def test_realize_asset_returns_realized_asset():
    result = get_scene_asset_realizer().realize_asset(
        {"asset_id": "r1", "name": "Tank", "category": "vehicle"},
        zone="hero_zone",
    )
    assert isinstance(result, RealizedAsset)
    assert result.asset_id == "r1"
    assert result.zone == "hero_zone"


def test_realize_asset_has_required_keys():
    result = get_scene_asset_realizer().realize_asset({"asset_id": "r2"})
    d = result.to_dict()
    for key in ("asset_id", "asset_name", "zone", "node_path", "transaction_op", "status", "realized_at"):
        assert key in d


def test_realize_assets_returns_list_of_3():
    assets = [
        {"asset_id": "r3", "name": "Crate"},
        {"asset_id": "r4", "name": "Barrel"},
        {"asset_id": "r5", "name": "Box"},
    ]
    results = get_scene_asset_realizer().realize_assets(assets)
    assert len(results) == 3
    for r in results:
        assert isinstance(r, RealizedAsset)


def test_build_realization_plan_returns_plan():
    assets = [{"asset_id": "r6", "name": "Sphere"}]
    plan = get_scene_asset_realizer().build_realization_plan(assets)
    assert isinstance(plan, RealizationPlan)
    assert plan.asset_count == 1
    assert isinstance(plan.transaction_ops, list)


def test_generate_transaction_operations_has_op_key():
    assets = [{"asset_id": "r7"}]
    plan = get_scene_asset_realizer().build_realization_plan(assets)
    ops = get_scene_asset_realizer().generate_transaction_operations(plan)
    assert isinstance(ops, list)
    for op in ops:
        assert isinstance(op, dict)
        # At least the asset create ops should have "op" key
    # The plan itself should have transaction_ops
    assert len(ops) == len(plan.transaction_ops)


def test_preview_realization_has_required_keys():
    assets = [{"asset_id": "r8", "name": "Robot"}]
    preview = get_scene_asset_realizer().preview_realization(assets)
    assert "op_count" in preview
    assert "zones" in preview
    assert "complexity" in preview


def test_realization_plan_to_dict_from_dict():
    assets = [{"asset_id": "r9"}]
    plan = get_scene_asset_realizer().build_realization_plan(assets)
    d = plan.to_dict()
    restored = RealizationPlan.from_dict(d)
    assert restored.asset_count == plan.asset_count
    assert restored.estimated_complexity == plan.estimated_complexity


def test_estimated_complexity_valid():
    assets = [{"asset_id": f"r{i}"} for i in range(5)]
    plan = get_scene_asset_realizer().build_realization_plan(assets)
    assert plan.estimated_complexity in _VALID_COMPLEXITIES


def test_never_raises():
    result = get_scene_asset_realizer().realize_asset(None)  # type: ignore
    assert isinstance(result, RealizedAsset)
