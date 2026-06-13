"""Tests for the §54 Reality Intelligence orchestrator, visual review,
geometry reconcile (GEOMETRY WINS), statistics and serializer (Tier 15.0+)."""

import pytest

from src.runtime.reality import (
    get_reality_intelligence_engine,
    reset_reality_intelligence_engine_for_tests,
    get_visual_review_engine,
    reset_visual_review_engine_for_tests,
    get_geometry_inspector,
    reset_geometry_inspector_for_tests,
    get_reality_statistics,
    reset_reality_statistics_for_tests,
    get_reality_serializer,
    reset_reality_serializer_for_tests,
    reset_human_reasoning_engine_for_tests,
    reset_functional_zone_builder_for_tests,
    reset_support_rule_engine_for_tests,
    reset_floating_object_detector_for_tests,
    reset_beam_connection_validator_for_tests,
    reset_architectural_integrity_validator_for_tests,
    reset_environment_density_engine_for_tests,
    reset_composition_engine_for_tests,
    reset_reality_correction_pass_for_tests,
)

_ALL_RESETS = (
    reset_reality_intelligence_engine_for_tests,
    reset_visual_review_engine_for_tests,
    reset_geometry_inspector_for_tests,
    reset_reality_statistics_for_tests,
    reset_reality_serializer_for_tests,
    reset_human_reasoning_engine_for_tests,
    reset_functional_zone_builder_for_tests,
    reset_support_rule_engine_for_tests,
    reset_floating_object_detector_for_tests,
    reset_beam_connection_validator_for_tests,
    reset_architectural_integrity_validator_for_tests,
    reset_environment_density_engine_for_tests,
    reset_composition_engine_for_tests,
    reset_reality_correction_pass_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    for r in _ALL_RESETS:
        r()
    yield
    for r in _ALL_RESETS:
        r()


class TestVisualReview:
    def test_canonical_western_room_production_ready(self, western_room_scene):
        review = get_visual_review_engine().review(western_room_scene)
        assert review.production_ready, review.findings
        assert review.grade == "A"
        assert review.criteria_met == review.criteria_total
        assert review.artist_would_approve
        assert review.production_game_quality
        assert review.film_set_quality
        assert review.human_would_use_room

    def test_floating_object_blocks_production(self, western_room_scene):
        western_room_scene["transforms"][5]["ty"] = 3.0   # float the bottle
        western_room_scene["transforms"][5]["tx"] = 3.0   # away from the table
        review = get_visual_review_engine().review(western_room_scene)
        assert not review.production_ready
        assert not review.no_floating_objects
        assert any("NOT_PRODUCTION_READY" in f for f in review.findings)

    def test_empty_room_fails_review(self):
        review = get_visual_review_engine().review(
            {"environment": "western_room", "transforms": []})
        assert not review.production_ready
        assert not review.visually_believable

    def test_findings_are_specific(self, western_room_scene):
        western_room_scene["transforms"].append(
            {"asset_id": "d2", "asset_name": "Swing Door", "tx": 2.0, "ty": 1.05,
             "tz": 0.0, "bbox_half_x": 0.5, "bbox_half_y": 1.05, "bbox_half_z": 0.06})
        review = get_visual_review_engine().review(western_room_scene)
        assert not review.production_ready
        assert any("decorative fake" in f for f in review.findings)


class TestRealityIntelligenceEngine:
    def test_full_pipeline_on_canonical_scene(self, western_room_scene):
        result = get_reality_intelligence_engine().evaluate(western_room_scene)
        assert result.production_ready
        assert result.grade == "A"
        assert result.environment == "western_room"
        assert result.zones["no_orphans"]
        assert result.support["ok"]
        assert result.floating["ok"]
        assert result.beams["ok"]
        assert result.integrity["architecturally_valid"]
        assert result.density["density_ok"]
        assert result.composition["composition_ok"]
        assert result.correction_plan["clean"]

    def test_statistics_recorded(self, western_room_scene):
        get_reality_intelligence_engine().evaluate(western_room_scene)
        stats = get_reality_statistics()
        assert stats.evaluation_count() == 1
        assert stats.production_ready_rate() == 1.0
        assert stats.summary()["by_environment"]["western_room"]["count"] == 1

    def test_geometry_wins_reconcile(self, western_room_scene):
        # Planner says the bottle is on the table; the viewport says it fell
        # to the floor 3 m away. GEOMETRY WINS — the review must fail.
        observed = {
            "assets": [{
                "asset_name": "Whiskey Bottle",
                "tx": 3.0, "ty": 0.15, "tz": 3.0, "ry": 0.0,
                "bbox_half_x": 0.05, "bbox_half_y": 0.15, "bbox_half_z": 0.05,
            }],
        }
        result = get_reality_intelligence_engine().evaluate(
            western_room_scene, observed_scene=observed)
        assert result.viewport_reconciled
        assert not result.production_ready
        assert not result.support["ok"]

    def test_never_raises(self):
        result = get_reality_intelligence_engine().evaluate(None)
        assert not result.production_ready


class TestReconcile:
    def test_observed_transform_overrides_metadata(self):
        merged = get_geometry_inspector().reconcile(
            {"assets": [{"asset_name": "Saloon Table", "tx": 9.0, "ty": 0.5,
                         "tz": 9.0, "ry": 45.0,
                         "bbox_half_x": 1.0, "bbox_half_y": 0.5, "bbox_half_z": 0.6}]},
            {"transforms": [{"asset_id": "t", "asset_name": "Saloon Table",
                             "tx": 0.0, "ty": 0.375, "tz": 0.0}]},
        )
        t = merged["transforms"][0]
        assert t["tx"] == 9.0
        assert t["source"] == "viewport"
        assert merged["viewport_overrides"] == 1

    def test_reconcile_never_raises(self):
        merged = get_geometry_inspector().reconcile(None, None)
        assert isinstance(merged, dict)


class TestSerializer:
    def test_round_trip_with_schema_version(self, western_room_scene):
        result = get_reality_intelligence_engine().evaluate(western_room_scene)
        raw = get_reality_serializer().serialize(result.to_dict())
        assert '"schema_version": "1.0.0"' in raw
        restored = get_reality_serializer().deserialize(raw)
        assert restored["production_ready"] is True

    def test_deserialize_garbage_returns_empty(self):
        assert get_reality_serializer().deserialize("not json") == {}
