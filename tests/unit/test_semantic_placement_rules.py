"""Tests for SemanticPlacementRules (Tier 9.4)."""

import pytest
from src.runtime.assets.assembly.semantic_placement_rules import (
    get_semantic_placement_rules,
    reset_semantic_placement_rules_for_tests,
    _BUILTIN_RULES,
)


@pytest.fixture(autouse=True)
def reset():
    reset_semantic_placement_rules_for_tests()
    yield
    reset_semantic_placement_rules_for_tests()


class TestGetRule:
    def test_known_type_table(self):
        rule = get_semantic_placement_rules().get_rule("table")
        assert rule.placement_type == "table"
        assert rule.is_anchor is True

    def test_known_type_chair(self):
        rule = get_semantic_placement_rules().get_rule("chair")
        assert rule.placement_type == "chair"
        assert rule.is_anchor is False
        assert rule.preferred_anchor == "table"

    def test_unknown_type_falls_back(self):
        rule = get_semantic_placement_rules().get_rule("sofa")
        assert rule.placement_type == "unknown"

    def test_machine_is_anchor(self):
        rule = get_semantic_placement_rules().get_rule("machine")
        assert rule.is_anchor is True
        assert "pipe" in rule.supports

    def test_vehicle_has_clearance_radius(self):
        rule = get_semantic_placement_rules().get_rule("vehicle")
        assert rule.clearance_radius >= 2.0


class TestAnchorRelationship:
    def test_table_supports_chair(self):
        spr = get_semantic_placement_rules()
        assert spr.is_valid_anchor_relationship("table", "chair") is True

    def test_table_supports_lantern(self):
        assert get_semantic_placement_rules().is_valid_anchor_relationship("table", "lantern") is True

    def test_table_does_not_support_machine(self):
        assert get_semantic_placement_rules().is_valid_anchor_relationship("table", "machine") is False

    def test_non_anchor_type(self):
        assert get_semantic_placement_rules().is_valid_anchor_relationship("chair", "bucket") is False

    def test_machine_supports_pipe(self):
        assert get_semantic_placement_rules().is_valid_anchor_relationship("machine", "pipe") is True

    def test_terrain_supports_vehicle(self):
        assert get_semantic_placement_rules().is_valid_anchor_relationship("terrain", "vehicle") is True


class TestZoneCompatibility:
    def test_table_preferred_in_hero_zone(self):
        result = get_semantic_placement_rules().check_zone_compatibility("table", "hero_zone")
        assert result["compatible"] is True
        assert result["preferred"] is True

    def test_bucket_preferred_in_service_area(self):
        result = get_semantic_placement_rules().check_zone_compatibility("bucket", "service_area")
        assert result["preferred"] is True

    def test_bucket_not_preferred_in_hero_zone(self):
        result = get_semantic_placement_rules().check_zone_compatibility("bucket", "hero_zone")
        assert result["preferred"] is False
        assert result["compatible"] is True  # still compatible, just not preferred

    def test_vehicle_preferred_in_hero_zone(self):
        result = get_semantic_placement_rules().check_zone_compatibility("vehicle", "hero_zone")
        assert result["preferred"] is True

    def test_unknown_type_compatible_everywhere(self):
        result = get_semantic_placement_rules().check_zone_compatibility("unknown", "midground")
        assert result["compatible"] is True


class TestEvaluateSemanticCompliance:
    def test_empty_placements(self):
        result = get_semantic_placement_rules().evaluate_semantic_compliance([])
        assert result["score"] == 1.0
        assert result["total"] == 0

    def test_all_preferred_perfect_score(self):
        placements = [
            {"asset_id": "table_01", "zone_name": "hero_zone",    "placement_type": "table"},
            {"asset_id": "chair_01", "zone_name": "hero_zone",    "placement_type": "chair"},
            {"asset_id": "vehicle",  "zone_name": "hero_zone",    "placement_type": "vehicle"},
        ]
        result = get_semantic_placement_rules().evaluate_semantic_compliance(placements)
        assert result["score"] == 1.0

    def test_bucket_in_hero_zone_violation(self):
        placements = [
            {"asset_id": "bucket_01", "zone_name": "hero_zone", "placement_type": "bucket"},
        ]
        result = get_semantic_placement_rules().evaluate_semantic_compliance(placements)
        assert result["score"] < 1.0
        assert len(result["violations"]) > 0

    def test_mixed_compliance(self):
        placements = [
            {"asset_id": "table",   "zone_name": "hero_zone",    "placement_type": "table"},   # preferred
            {"asset_id": "bucket",  "zone_name": "hero_zone",    "placement_type": "bucket"},  # not preferred
        ]
        result = get_semantic_placement_rules().evaluate_semantic_compliance(placements)
        assert 0.0 < result["score"] < 1.0

    def test_score_deterministic(self):
        placements = [
            {"asset_id": "a", "zone_name": "hero_zone", "placement_type": "table"},
            {"asset_id": "b", "zone_name": "background", "placement_type": "terrain"},
        ]
        r1 = get_semantic_placement_rules().evaluate_semantic_compliance(placements)
        r2 = get_semantic_placement_rules().evaluate_semantic_compliance(placements)
        assert r1["score"] == r2["score"]
