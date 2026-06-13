"""Tests for src.runtime.environment.decorative_population"""
import pytest
from src.runtime.environment.decorative_population import (
    get_decorative_population,
    reset_decorative_population_for_tests,
    DecorationPlan,
    DecorativeItem,
)
from src.runtime.environment.anchor_asset_builder import (
    reset_anchor_asset_builder_for_tests,
)
from src.runtime.environment.environment_template_library import (
    reset_environment_template_library_for_tests,
)

_VALID_PLACEMENT_TARGETS = {
    "on_table", "near_wall", "corner", "ceiling", "floor",
    "on_shelf", "near_anchor", "scattered", "wall_mounted",
    "ceiling_mounted",
}


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_decorative_population_for_tests()
    reset_anchor_asset_builder_for_tests()
    reset_environment_template_library_for_tests()
    yield
    reset_decorative_population_for_tests()
    reset_anchor_asset_builder_for_tests()
    reset_environment_template_library_for_tests()


class TestPopulate:
    def test_western_room_has_at_least_4_items(self):
        pop = get_decorative_population()
        plan = pop.populate("western_room")
        assert plan.total_count >= 4

    def test_western_room_has_cups_and_bottles(self):
        pop = get_decorative_population()
        plan = pop.populate("western_room")
        item_types = {i.item_type for i in plan.items}
        assert "cup" in item_types or "bottle" in item_types

    def test_industrial_hangar_has_oil_drum_or_toolbox(self):
        pop = get_decorative_population()
        plan = pop.populate("industrial_hangar")
        item_types = {i.item_type for i in plan.items}
        assert "oil_drum" in item_types or "toolbox" in item_types or "safety_sign" in item_types

    def test_office_has_document_stack_or_mug(self):
        pop = get_decorative_population()
        plan = pop.populate("office")
        item_types = {i.item_type for i in plan.items}
        assert "document_stack" in item_types or "coffee_mug" in item_types

    def test_all_items_have_valid_placement_targets(self):
        pop = get_decorative_population()
        plan = pop.populate("castle_hall")
        for item in plan.items:
            assert item.placement_target in _VALID_PLACEMENT_TARGETS, \
                f"Invalid placement target: {item.placement_target!r} for {item.item_type}"

    def test_total_count_is_sum_of_individual_counts(self):
        pop = get_decorative_population()
        plan = pop.populate("library")
        expected = sum(i.count for i in plan.items)
        assert plan.total_count == expected

    def test_no_exceptions_on_any_environment(self):
        from src.runtime.environment.environment_template_library import get_environment_template_library
        pop = get_decorative_population()
        lib = get_environment_template_library()
        for name in lib.list_templates():
            plan = pop.populate(name)
            assert plan is not None

    def test_unknown_environment_returns_empty_plan(self):
        pop = get_decorative_population()
        plan = pop.populate("nonexistent_xyz")
        assert isinstance(plan.items, list)
        assert plan.errors == []


class TestGetItemsForZone:
    def test_filters_by_zone_type(self):
        pop = get_decorative_population()
        plan = pop.populate("western_room")
        hero_items = pop.get_items_for_zone(plan, "hero_zone")
        assert all(i.zone_type == "hero_zone" for i in hero_items)

    def test_wall_zone_items(self):
        pop = get_decorative_population()
        plan = pop.populate("western_room")
        wall_items = pop.get_items_for_zone(plan, "wall_zone")
        assert len(wall_items) >= 1

    def test_returns_empty_for_no_matches(self):
        pop = get_decorative_population()
        plan = pop.populate("western_room")
        result = pop.get_items_for_zone(plan, "nonexistent_zone_type_xyz")
        assert result == []


class TestSerialization:
    def test_decoration_plan_roundtrip(self):
        pop = get_decorative_population()
        plan = pop.populate("survival_camp")
        d = plan.to_dict()
        plan2 = DecorationPlan.from_dict(d)
        assert plan2.environment_name == plan.environment_name
        assert plan2.total_count == plan.total_count
        assert len(plan2.items) == len(plan.items)
