"""Tests for AnchorAssetEngine (Tier 9.5)."""

import pytest
from src.runtime.assets.assembly.anchor_asset_engine import (
    AnchorAsset,
    AnchorPlan,
    AnchorAssetEngine,
    SEMANTIC_RELATIONSHIPS,
    get_anchor_asset_engine,
    reset_anchor_asset_engine_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_anchor_asset_engine_for_tests()
    yield
    reset_anchor_asset_engine_for_tests()


class TestSingleton:
    def test_singleton_returns_same_instance(self):
        a = get_anchor_asset_engine()
        b = get_anchor_asset_engine()
        assert a is b

    def test_reset_creates_fresh_instance(self):
        a = get_anchor_asset_engine()
        reset_anchor_asset_engine_for_tests()
        b = get_anchor_asset_engine()
        assert a is not b


class TestGetAnchorPlan:
    def test_returns_anchor_plan(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("industrial_hangar")
        assert isinstance(plan, AnchorPlan)

    def test_anchor_plan_has_correct_environment(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("western_room")
        assert plan.environment_name == "western_room"

    def test_anchor_plan_has_anchors(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("industrial_hangar")
        assert len(plan.anchors) > 0

    def test_primary_anchor_is_set(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("industrial_hangar")
        assert plan.primary_anchor is not None
        assert plan.primary_anchor.is_primary is True

    def test_western_room_primary_anchor_is_table(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("western_room")
        assert plan.primary_anchor is not None
        assert plan.primary_anchor.asset_type == "table"

    def test_castle_hall_primary_anchor_is_throne(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("castle_hall")
        assert plan.primary_anchor is not None
        assert plan.primary_anchor.asset_type == "throne"

    def test_industrial_hangar_primary_anchor_is_machine(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("industrial_hangar")
        assert plan.primary_anchor is not None
        assert plan.primary_anchor.asset_type == "main_machine"

    def test_anchors_have_zones(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("robotics_lab")
        for anchor in plan.anchors:
            assert anchor.zone != "", f"Anchor {anchor.asset_type} has no zone"

    def test_anchors_have_position_hints(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("control_room")
        for anchor in plan.anchors:
            assert anchor.position_hint != ""

    def test_primary_anchor_has_supports_types(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("western_room")
        # table supports chairs, cups, bottles, lanterns
        assert len(plan.primary_anchor.supports_types) > 0
        assert "chair" in plan.primary_anchor.supports_types

    def test_unknown_env_returns_fallback_plan(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("nonexistent_env_xyz")
        assert isinstance(plan, AnchorPlan)
        assert len(plan.anchors) > 0
        assert plan.primary_anchor is not None

    def test_all_environments_have_plans(self):
        from src.runtime.assets.assembly.architectural_templates import SUPPORTED_ENVIRONMENTS
        engine = get_anchor_asset_engine()
        for env in SUPPORTED_ENVIRONMENTS:
            plan = engine.get_anchor_plan(env)
            assert len(plan.anchors) > 0, f"{env} has no anchors"

    def test_no_errors_for_known_environments(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("library")
        assert plan.errors == []


class TestSemanticRelationships:
    def test_chair_belongs_near_table(self):
        engine = get_anchor_asset_engine()
        rel = engine.get_semantic_relationship("chair")
        assert "table" in rel["belongs_near"]

    def test_cup_belongs_on_table(self):
        engine = get_anchor_asset_engine()
        rel = engine.get_semantic_relationship("cup")
        assert "table" in rel["belongs_on"]

    def test_bucket_belongs_near_wall(self):
        engine = get_anchor_asset_engine()
        rel = engine.get_semantic_relationship("bucket")
        assert "wall" in rel["belongs_near"]

    def test_lantern_belongs_on_wall(self):
        engine = get_anchor_asset_engine()
        rel = engine.get_semantic_relationship("lantern")
        assert "wall" in rel["belongs_on"]

    def test_unknown_type_returns_defaults(self):
        engine = get_anchor_asset_engine()
        rel = engine.get_semantic_relationship("imaginary_prop_xyz")
        assert "belongs_near" in rel
        assert "belongs_on" in rel
        assert rel["min_dist"] >= 0.0
        assert rel["max_dist"] >= 0.0

    def test_semantic_relationships_dict_non_empty(self):
        assert len(SEMANTIC_RELATIONSHIPS) > 0


class TestGetChildrenForAnchor:
    def test_table_children_include_chair(self):
        engine = get_anchor_asset_engine()
        children = engine.get_children_for_anchor("western_room", "table")
        assert "chair" in children

    def test_unknown_anchor_returns_empty(self):
        engine = get_anchor_asset_engine()
        children = engine.get_children_for_anchor("western_room", "nonexistent_anchor")
        assert children == []


class TestAnchorPlanSerialization:
    def test_to_dict_roundtrip(self):
        engine = get_anchor_asset_engine()
        plan = engine.get_anchor_plan("castle_hall")
        d = plan.to_dict()
        restored = AnchorPlan.from_dict(d)
        assert restored.environment_name == "castle_hall"
        assert len(restored.anchors) == len(plan.anchors)
        assert restored.primary_anchor is not None
        assert restored.primary_anchor.asset_type == plan.primary_anchor.asset_type
