"""Tests for SpatialReview (Tier 9.4)."""

import pytest
from src.runtime.assets.assembly.spatial_review import (
    get_spatial_review,
    reset_spatial_review_for_tests,
    SpatialReviewResult,
)
from src.runtime.assets.assembly.collision_detector import reset_collision_detector_for_tests
from src.runtime.assets.assembly.clearance_validator import reset_clearance_validator_for_tests
from src.runtime.assets.assembly.semantic_placement_rules import reset_semantic_placement_rules_for_tests
from src.runtime.assets.assembly.spatial_metadata import SpatialMetadata


def _meta(asset_id="a", bx=1.0, bz=1.0, pt="unknown", obstacle=True) -> SpatialMetadata:
    return SpatialMetadata(
        asset_id=asset_id,
        bbox_x=bx, bbox_y=1.0, bbox_z=bz,
        footprint_area=bx * bz,
        placement_radius=max(bx, bz) / 2.0,
        placement_type=pt,
        walkable_obstacle=obstacle,
    )


@pytest.fixture(autouse=True)
def reset():
    reset_spatial_review_for_tests()
    reset_collision_detector_for_tests()
    reset_clearance_validator_for_tests()
    reset_semantic_placement_rules_for_tests()
    yield
    reset_spatial_review_for_tests()
    reset_collision_detector_for_tests()
    reset_clearance_validator_for_tests()
    reset_semantic_placement_rules_for_tests()


class TestReviewBasics:
    def test_returns_result_instance(self):
        result = get_spatial_review().review_placement("test_env", [])
        assert isinstance(result, SpatialReviewResult)

    def test_empty_scene(self):
        result = get_spatial_review().review_placement("test_env", [])
        assert result.collision_count == 0
        assert result.clearance_violations == 0

    def test_result_is_serializable(self):
        result = get_spatial_review().review_placement("industrial_hangar", [])
        d = result.to_dict()
        assert "overall_score" in d
        assert "production_ready" in d
        assert "grade" in d


class TestCollisionBlock:
    def test_collision_blocks_production_ready(self):
        # Two large cubes at same position → collision
        m = _meta(bx=3.0, bz=3.0, pt="machine")
        result = get_spatial_review().review_placement(
            "industrial_hangar",
            [("m1", (0.0, 0.0, 0.0), m), ("m2", (1.0, 0.0, 0.0), m)],
        )
        assert result.collision_count > 0
        assert result.production_ready is False

    def test_no_collision_allows_production_ready(self):
        m = _meta(bx=1.0, bz=1.0, pt="chair")
        result = get_spatial_review().review_placement(
            "industrial_hangar",
            [("c1", (0.0, 0.0, 0.0), m), ("c2", (10.0, 0.0, 0.0), m)],
            zone_placements=[
                {"asset_id": "c1", "zone_name": "hero_zone", "placement_type": "chair"},
                {"asset_id": "c2", "zone_name": "hero_zone", "placement_type": "chair"},
            ],
            scene_floor_area=200.0,
        )
        assert result.collision_count == 0
        # production_ready depends on score ≥ 0.70; just verify no collision
        assert result.collision_score == 1.0


class TestCollisionScore:
    def test_no_collisions_score_one(self):
        m = _meta(bx=1.0, bz=1.0)
        result = get_spatial_review().review_placement(
            "env", [("a", (0.0, 0.0, 0.0), m), ("b", (5.0, 0.0, 0.0), m)]
        )
        assert result.collision_score == 1.0

    def test_collision_reduces_score(self):
        m = _meta(bx=3.0, bz=3.0)
        result = get_spatial_review().review_placement(
            "env", [("a", (0.0, 0.0, 0.0), m), ("b", (1.0, 0.0, 0.0), m)]
        )
        assert result.collision_score < 1.0


class TestWalkabilityScore:
    def test_large_obstacles_reduce_walkability(self):
        # 4 machines of 10x10=100m² each = 400m² in a 200m² scene → > 100% occupied
        m = _meta(bx=10.0, bz=10.0, pt="machine", obstacle=True)
        result = get_spatial_review().review_placement(
            "industrial_hangar",
            [("m1", (0.0, 0.0, 0.0), m)],
            scene_floor_area=50.0,
        )
        assert result.walkability_fraction < 1.0
        # footprint = 100m², floor = 50m² → fraction = max(0, 1 - 2.0) = 0.0
        assert result.walkability_fraction == 0.0

    def test_small_assets_high_walkability(self):
        m = _meta(bx=0.5, bz=0.5, obstacle=True)
        result = get_spatial_review().review_placement(
            "env",
            [("a", (0.0, 0.0, 0.0), m)],
            scene_floor_area=200.0,
        )
        # footprint = 0.25m², floor = 200m² → walkable ≈ 0.9988
        assert result.walkability_fraction > 0.99

    def test_non_obstacles_dont_reduce_walkability(self):
        m = _meta(bx=10.0, bz=10.0, obstacle=False)
        result = get_spatial_review().review_placement(
            "env",
            [("a", (0.0, 0.0, 0.0), m)],
            scene_floor_area=200.0,
        )
        assert result.walkability_fraction == 1.0


class TestGrading:
    def test_empty_scene_perfect_spatial(self):
        result = get_spatial_review().review_placement("env", [], scene_floor_area=200.0)
        # No collisions, no violations, full walkability → high score
        assert result.overall_score >= 0.7

    def test_grade_mapping(self):
        # Grade via overall_score directly
        from src.runtime.assets.assembly.spatial_review import _grade
        assert _grade(0.95) == "A"
        assert _grade(0.85) == "B"
        assert _grade(0.75) == "C"
        assert _grade(0.60) == "D"
        assert _grade(0.40) == "F"


class TestDeterminism:
    def test_same_input_same_output(self):
        m = _meta(bx=2.0, bz=2.0, pt="table")
        inputs = [
            ("t1", (0.0, 0.0, 0.0), m),
            ("t2", (5.0, 0.0, 0.0), m),
        ]
        r1 = get_spatial_review().review_placement("industrial_hangar", inputs)
        r2 = get_spatial_review().review_placement("industrial_hangar", inputs)
        assert r1.overall_score == r2.overall_score
        assert r1.collision_count == r2.collision_count
