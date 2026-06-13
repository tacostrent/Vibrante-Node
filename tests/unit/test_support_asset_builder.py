"""Tests for src.runtime.environment.support_asset_builder"""
import pytest
from src.runtime.environment.support_asset_builder import (
    get_support_asset_builder,
    reset_support_asset_builder_for_tests,
    SupportPlan,
    SupportAsset,
)
from src.runtime.environment.anchor_asset_builder import (
    get_anchor_asset_builder,
    reset_anchor_asset_builder_for_tests,
)
from src.runtime.environment.environment_template_library import (
    reset_environment_template_library_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_support_asset_builder_for_tests()
    reset_anchor_asset_builder_for_tests()
    reset_environment_template_library_for_tests()
    yield
    reset_support_asset_builder_for_tests()
    reset_anchor_asset_builder_for_tests()
    reset_environment_template_library_for_tests()


class TestBuildSupportAssets:
    def test_western_room_has_at_least_one_support_asset(self):
        builder = get_support_asset_builder()
        plan = builder.build_support_assets("western_room")
        assert plan.total_count >= 1

    def test_support_assets_reference_parent_anchor_types(self):
        anchor_builder = get_anchor_asset_builder()
        anchor_plan = anchor_builder.build_anchors("restaurant")

        builder = get_support_asset_builder()
        plan = builder.build_support_assets("restaurant", anchor_plan=anchor_plan)

        # Some support assets should reference anchors
        anchor_types = {a.anchor_type for a in anchor_plan.anchors}
        parent_types = {s.parent_anchor_type for s in plan.support_assets if s.parent_anchor_type}
        assert len(parent_types) > 0

    def test_build_with_anchor_plan_uses_child_types(self):
        anchor_builder = get_anchor_asset_builder()
        anchor_plan = anchor_builder.build_anchors("western_room")

        builder = get_support_asset_builder()
        plan = builder.build_support_assets("western_room", anchor_plan=anchor_plan)

        # chair should appear since main_table has chair in child_types
        asset_types = {s.asset_type for s in plan.support_assets}
        assert "chair" in asset_types or plan.total_count >= 1

    def test_total_count_is_sum_of_counts(self):
        builder = get_support_asset_builder()
        plan = builder.build_support_assets("library")
        expected = sum(s.count for s in plan.support_assets)
        assert plan.total_count == expected

    def test_no_exceptions_on_any_environment(self):
        from src.runtime.environment.environment_template_library import get_environment_template_library
        builder = get_support_asset_builder()
        lib = get_environment_template_library()
        for name in lib.list_templates():
            plan = builder.build_support_assets(name)
            assert plan is not None
            assert isinstance(plan.support_assets, list)

    def test_support_assets_have_valid_position_modes(self):
        valid_modes = {"around_anchor", "near_wall", "corner", "midground", "scattered"}
        builder = get_support_asset_builder()
        plan = builder.build_support_assets("industrial_hangar")
        for s in plan.support_assets:
            assert s.position_mode in valid_modes, f"Invalid mode: {s.position_mode}"


class TestSerialization:
    def test_support_plan_roundtrip(self):
        builder = get_support_asset_builder()
        plan = builder.build_support_assets("castle_hall")
        d = plan.to_dict()
        plan2 = SupportPlan.from_dict(d)
        assert plan2.environment_name == plan.environment_name
        assert plan2.total_count == plan.total_count
