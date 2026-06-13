"""
Tests for ScenePlan schema (Tier 7).

Covers:
 - AssetQuery, CameraTarget, CompositionRule, PlacementHint to_dict/from_dict round-trips
 - SceneZonePlan to_dict/from_dict/to_json/from_json
 - ScenePlan to_dict/from_dict/to_json/from_json
 - PlanningResult to_dict
 - ScenePlan properties (is_valid, zone_types, has_foreground, has_background, total_required_assets)
 - Unique plan_id per instance
"""

import json
import pytest

from src.runtime.planning.schema.scene_plan import (
    SCHEMA_VERSION,
    AssetQuery,
    CameraTarget,
    CompositionRule,
    PlacementHint,
    SceneZonePlan,
    ScenePlan,
    PlanningResult,
)


# ---------------------------------------------------------------------------
# AssetQuery
# ---------------------------------------------------------------------------

class TestAssetQuery:
    def test_defaults(self):
        q = AssetQuery()
        assert q.query_id.startswith("aq_")
        assert q.category == ""
        assert q.quantity == 1
        assert q.priority == "recommended"
        assert q.size_hint == "medium"

    def test_to_dict_keys(self):
        q = AssetQuery(category="building", tags=["sci-fi", "damaged"], zone="midground", quantity=3)
        d = q.to_dict()
        for key in ("query_id", "category", "tags", "zone", "quantity", "priority", "style_hints", "size_hint", "metadata"):
            assert key in d

    def test_round_trip(self):
        q = AssetQuery(category="vehicle", tags=["damaged"], zone="foreground",
                       quantity=2, priority="required", style_hints=["post-apocalyptic"], size_hint="large")
        q2 = AssetQuery.from_dict(q.to_dict())
        assert q2.category == "vehicle"
        assert q2.tags == ["damaged"]
        assert q2.zone == "foreground"
        assert q2.quantity == 2
        assert q2.priority == "required"
        assert q2.style_hints == ["post-apocalyptic"]
        assert q2.size_hint == "large"

    def test_to_json_from_json(self):
        q = AssetQuery(category="debris", tags=["city"], zone="background")
        q2 = AssetQuery.from_json(q.to_json())
        assert q2.category == q.category

    def test_sorted_keys_in_json(self):
        q = AssetQuery(category="structure")
        data = json.loads(q.to_json())
        keys = list(data.keys())
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# CameraTarget
# ---------------------------------------------------------------------------

class TestCameraTarget:
    def test_defaults(self):
        c = CameraTarget()
        assert c.target_id.startswith("ct_")
        assert c.shot_type == "hero"
        assert 0.0 <= c.importance <= 1.0

    def test_round_trip(self):
        c = CameraTarget(name="hero_building", zone="midground",
                         position_hint="left_third", look_at_hint="damaged_section",
                         importance=0.9, shot_type="establishing")
        c2 = CameraTarget.from_dict(c.to_dict())
        assert c2.name == "hero_building"
        assert c2.shot_type == "establishing"
        assert c2.importance == pytest.approx(0.9)

    def test_to_json_from_json(self):
        c = CameraTarget(name="overview", shot_type="aerial")
        c2 = CameraTarget.from_json(c.to_json())
        assert c2.name == c.name


# ---------------------------------------------------------------------------
# CompositionRule
# ---------------------------------------------------------------------------

class TestCompositionRule:
    def test_defaults(self):
        r = CompositionRule()
        assert r.rule_id.startswith("cr_")
        assert r.applies_to == "full_scene"
        assert 0.0 <= r.priority <= 1.0

    def test_round_trip(self):
        r = CompositionRule(rule_type="hero_focal_point", description="hero focus",
                            applies_to="foreground", priority=0.8)
        r2 = CompositionRule.from_dict(r.to_dict())
        assert r2.rule_type == "hero_focal_point"
        assert r2.applies_to == "foreground"
        assert r2.priority == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# PlacementHint
# ---------------------------------------------------------------------------

class TestPlacementHint:
    def test_defaults(self):
        h = PlacementHint()
        assert h.hint_id.startswith("ph_")
        assert h.position == "distributed"
        assert h.spacing == "medium"

    def test_round_trip(self):
        h = PlacementHint(asset_category="vehicle", zone="foreground",
                          position="left", depth_hint="front", spacing="loose")
        h2 = PlacementHint.from_dict(h.to_dict())
        assert h2.asset_category == "vehicle"
        assert h2.depth_hint == "front"


# ---------------------------------------------------------------------------
# SceneZonePlan
# ---------------------------------------------------------------------------

class TestSceneZonePlan:
    def test_defaults(self):
        z = SceneZonePlan()
        assert z.zone_id.startswith("z_")
        assert z.population == "moderate"
        assert z.priority == 5

    def test_round_trip(self):
        h = PlacementHint(asset_category="building", zone="midground")
        z = SceneZonePlan(zone_type="midground", description="buildings", priority=7,
                          asset_categories=["building", "structure"],
                          population="dense", placement_hints=[h])
        z2 = SceneZonePlan.from_dict(z.to_dict())
        assert z2.zone_type == "midground"
        assert len(z2.placement_hints) == 1
        assert z2.placement_hints[0].asset_category == "building"

    def test_to_json_from_json(self):
        z = SceneZonePlan(zone_type="foreground", asset_categories=["debris"])
        z2 = SceneZonePlan.from_json(z.to_json())
        assert z2.zone_type == z.zone_type
        assert z2.asset_categories == ["debris"]


# ---------------------------------------------------------------------------
# ScenePlan
# ---------------------------------------------------------------------------

class TestScenePlan:
    def _make_plan(self):
        fg = SceneZonePlan(zone_type="foreground", asset_categories=["debris", "vehicle"], priority=10)
        mg = SceneZonePlan(zone_type="midground",  asset_categories=["building"],           priority=7)
        bg = SceneZonePlan(zone_type="background", asset_categories=["skyline"],             priority=4)
        q1 = AssetQuery(category="vehicle", zone="foreground", quantity=2, priority="required")
        q2 = AssetQuery(category="building", zone="midground", quantity=4, priority="recommended")
        cam = CameraTarget(name="overview", shot_type="establishing")
        rule = CompositionRule(rule_type="layered_depth", priority=0.9)
        plan = ScenePlan(
            environment="urban",
            style="cinematic",
            mood="dramatic",
            zones=[fg, mg, bg],
            asset_queries=[q1, q2],
            camera_targets=[cam],
            composition_rules=[rule],
            estimated_complexity="complex",
            estimated_asset_count=6,
        )
        return plan

    def test_schema_version(self):
        plan = ScenePlan()
        assert plan.schema_version == SCHEMA_VERSION

    def test_unique_plan_ids(self):
        ids = {ScenePlan().plan_id for _ in range(10)}
        assert len(ids) == 10

    def test_zone_types_property(self):
        plan = self._make_plan()
        assert set(plan.zone_types) == {"foreground", "midground", "background"}

    def test_has_foreground_background(self):
        plan = self._make_plan()
        assert plan.has_foreground is True
        assert plan.has_background is True

    def test_has_foreground_false_when_absent(self):
        plan = ScenePlan(zones=[SceneZonePlan(zone_type="background")])
        assert plan.has_foreground is False

    def test_total_required_assets(self):
        plan = self._make_plan()
        assert plan.total_required_assets == 2  # only q1 is required

    def test_is_valid_false_before_validation(self):
        plan = ScenePlan()
        assert plan.is_valid is False

    def test_is_valid_true_after_validation(self):
        plan = ScenePlan()
        plan.validated = True
        plan.validation_errors = []
        assert plan.is_valid is True

    def test_is_valid_false_with_errors(self):
        plan = ScenePlan()
        plan.validated = True
        plan.validation_errors = ["missing zones"]
        assert plan.is_valid is False

    def test_round_trip(self):
        plan = self._make_plan()
        plan2 = ScenePlan.from_dict(plan.to_dict())
        assert plan2.environment == "urban"
        assert plan2.style == "cinematic"
        assert len(plan2.zones) == 3
        assert len(plan2.asset_queries) == 2
        assert len(plan2.camera_targets) == 1
        assert len(plan2.composition_rules) == 1

    def test_to_json_from_json(self):
        plan = self._make_plan()
        plan2 = ScenePlan.from_json(plan.to_json())
        assert plan2.environment == plan.environment
        assert plan2.estimated_complexity == plan.estimated_complexity

    def test_json_is_sorted(self):
        plan = ScenePlan(environment="industrial")
        data = json.loads(plan.to_json())
        keys = list(data.keys())
        assert keys == sorted(keys)

    def test_repr(self):
        plan = self._make_plan()
        r = repr(plan)
        assert "urban" in r
        assert "zones=3" in r


# ---------------------------------------------------------------------------
# PlanningResult
# ---------------------------------------------------------------------------

class TestPlanningResult:
    def test_defaults(self):
        r = PlanningResult()
        assert r.ok is False
        assert r.plan is None
        assert r.errors == []
        assert r.planning_time == pytest.approx(0.0)
        assert r.pipeline_stages == []

    def test_to_dict_with_plan(self):
        plan = ScenePlan(environment="industrial")
        r = PlanningResult(ok=True, plan=plan, planning_time=0.12, pipeline_stages=["zones"])
        d = r.to_dict()
        assert d["ok"] is True
        assert d["plan"] is not None
        assert d["planning_time"] == pytest.approx(0.12)
        assert "zones" in d["pipeline_stages"]

    def test_to_dict_without_plan(self):
        r = PlanningResult(ok=False, errors=["no zones"])
        d = r.to_dict()
        assert d["plan"] is None
        assert "no zones" in d["errors"]
