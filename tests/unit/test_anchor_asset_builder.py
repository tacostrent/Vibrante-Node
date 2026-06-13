"""Tests for src.runtime.environment.anchor_asset_builder"""
import pytest
from src.runtime.environment.anchor_asset_builder import (
    get_anchor_asset_builder,
    reset_anchor_asset_builder_for_tests,
    AnchorPlan,
    PlacedAnchor,
)
from src.runtime.environment.environment_template_library import (
    reset_environment_template_library_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_anchor_asset_builder_for_tests()
    reset_environment_template_library_for_tests()
    yield
    reset_anchor_asset_builder_for_tests()
    reset_environment_template_library_for_tests()


class TestBuildAnchors:
    def test_western_room_has_main_table_as_primary(self):
        builder = get_anchor_asset_builder()
        plan = builder.build_anchors("western_room")
        assert plan.anchor_count >= 1
        assert plan.primary_anchor == "main_table"

    def test_industrial_hangar_has_hero_machine(self):
        builder = get_anchor_asset_builder()
        plan = builder.build_anchors("industrial_hangar")
        anchor_types = {a.anchor_type for a in plan.anchors}
        assert "hero_machine" in anchor_types

    def test_castle_hall_has_throne(self):
        builder = get_anchor_asset_builder()
        plan = builder.build_anchors("castle_hall")
        anchor_types = {a.anchor_type for a in plan.anchors}
        assert "throne" in anchor_types
        assert plan.primary_anchor == "throne"

    def test_control_room_has_master_console(self):
        builder = get_anchor_asset_builder()
        plan = builder.build_anchors("control_room")
        anchor_types = {a.anchor_type for a in plan.anchors}
        assert "master_console" in anchor_types

    def test_anchors_sorted_by_priority(self):
        builder = get_anchor_asset_builder()
        plan = builder.build_anchors("western_room")
        priorities = [a.priority for a in plan.anchors]
        assert priorities == sorted(priorities)

    def test_primary_anchor_has_priority_1(self):
        builder = get_anchor_asset_builder()
        plan = builder.build_anchors("office")
        primary = builder.get_primary_anchor(plan)
        assert primary is not None
        assert primary.priority == 1

    def test_blueprint_supplement_adds_missing_anchors(self):
        from src.runtime.environment.environment_blueprint import EnvironmentBlueprint
        bp = EnvironmentBlueprint(
            environment_name="test",
            required_structure=["floor"],
            required_zones=["hero_zone"],
            required_anchors=["new_custom_anchor"],
            atmosphere_profile="warm_interior",
        )
        builder = get_anchor_asset_builder()
        plan = builder.build_anchors("western_room", blueprint=bp)
        anchor_types = {a.anchor_type for a in plan.anchors}
        assert "new_custom_anchor" in anchor_types

    def test_unknown_environment_gets_generic_anchor(self):
        builder = get_anchor_asset_builder()
        plan = builder.build_anchors("nonexistent_xyz")
        assert plan.anchor_count >= 1

    def test_all_20_environments_have_at_least_one_anchor(self):
        from src.runtime.environment.environment_template_library import get_environment_template_library
        builder = get_anchor_asset_builder()
        lib = get_environment_template_library()
        for name in lib.list_templates():
            plan = builder.build_anchors(name)
            assert plan.anchor_count >= 1, f"{name} has no anchors"


class TestGetChildrenForAnchor:
    def test_main_table_has_chair_and_cup(self):
        builder = get_anchor_asset_builder()
        children = builder.get_children_for_anchor("main_table")
        assert "chair" in children
        assert "cup" in children

    def test_bar_counter_has_stool_and_bottle(self):
        builder = get_anchor_asset_builder()
        children = builder.get_children_for_anchor("bar_counter")
        assert "stool" in children
        assert "bottle" in children

    def test_camp_fire_has_log_and_lantern(self):
        builder = get_anchor_asset_builder()
        children = builder.get_children_for_anchor("camp_fire")
        assert "log" in children
        assert "lantern" in children

    def test_unknown_anchor_returns_empty_list(self):
        builder = get_anchor_asset_builder()
        children = builder.get_children_for_anchor("nonexistent_anchor_xyz")
        assert children == []


class TestGetPrimaryAnchor:
    def test_get_primary_anchor_returns_priority_1(self):
        builder = get_anchor_asset_builder()
        plan = builder.build_anchors("restaurant")
        primary = builder.get_primary_anchor(plan)
        assert primary is not None
        assert primary.priority == 1

    def test_get_primary_anchor_on_empty_plan(self):
        plan = AnchorPlan(environment_name="test", anchors=[], anchor_count=0)
        builder = get_anchor_asset_builder()
        result = builder.get_primary_anchor(plan)
        assert result is None


class TestSerialization:
    def test_anchor_plan_roundtrip(self):
        builder = get_anchor_asset_builder()
        plan = builder.build_anchors("forest")
        d = plan.to_dict()
        plan2 = AnchorPlan.from_dict(d)
        assert plan2.environment_name == plan.environment_name
        assert plan2.anchor_count == plan.anchor_count
        assert plan2.primary_anchor == plan.primary_anchor
