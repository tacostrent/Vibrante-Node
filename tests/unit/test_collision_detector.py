"""Tests for CollisionDetector (Tier 9.4)."""

import pytest
from src.runtime.assets.assembly.collision_detector import (
    get_collision_detector,
    reset_collision_detector_for_tests,
    CollisionPair,
    CollisionReport,
)
from src.runtime.assets.assembly.spatial_metadata import SpatialMetadata


def _meta(asset_id="a", bx=1.0, by=1.0, bz=1.0, pt="unknown") -> SpatialMetadata:
    return SpatialMetadata(
        asset_id=asset_id,
        bbox_x=bx, bbox_y=by, bbox_z=bz,
        footprint_area=bx * bz,
        placement_radius=max(bx, bz) / 2.0,
        placement_type=pt,
    )


@pytest.fixture(autouse=True)
def reset():
    reset_collision_detector_for_tests()
    yield
    reset_collision_detector_for_tests()


class TestIntersects:
    def test_overlapping_cubes(self):
        m = _meta(bx=2.0, by=2.0, bz=2.0)
        # Two 2m cubes at distance 1m apart (overlap = 1m)
        assert get_collision_detector().intersects(
            (0.0, 0.0, 0.0), m,
            (1.0, 0.0, 0.0), m
        ) is True

    def test_touching_not_colliding(self):
        m = _meta(bx=2.0, by=2.0, bz=2.0)
        # Exactly touching: distance = sum of half-extents = 2.0 → no overlap
        assert get_collision_detector().intersects(
            (0.0, 0.0, 0.0), m,
            (2.0, 0.0, 0.0), m
        ) is False

    def test_separated_no_collision(self):
        m = _meta(bx=1.0, by=1.0, bz=1.0)
        assert get_collision_detector().intersects(
            (0.0, 0.0, 0.0), m,
            (5.0, 0.0, 0.0), m
        ) is False

    def test_one_inside_other(self):
        big = _meta(bx=4.0, by=4.0, bz=4.0)
        small = _meta(bx=1.0, by=1.0, bz=1.0)
        assert get_collision_detector().intersects(
            (0.0, 0.0, 0.0), big,
            (0.0, 0.0, 0.0), small
        ) is True

    def test_same_position_same_size(self):
        m = _meta(bx=2.0, by=2.0, bz=2.0)
        assert get_collision_detector().intersects(
            (0.0, 0.0, 0.0), m,
            (0.0, 0.0, 0.0), m
        ) is True

    def test_no_overlap_along_z(self):
        m = _meta(bx=1.0, by=1.0, bz=1.0)
        assert get_collision_detector().intersects(
            (0.0, 0.0, 0.0), m,
            (0.0, 0.0, 2.0), m
        ) is False


class TestIntersectsAny:
    def test_no_placed_no_collision(self):
        m = _meta()
        result = get_collision_detector().intersects_any((0.0, 0.0, 0.0), m, [])
        assert result is False

    def test_collision_with_one_placed(self):
        m = _meta(bx=2.0, by=2.0, bz=2.0)
        placed = [((0.0, 0.0, 0.0), m)]
        assert get_collision_detector().intersects_any((1.0, 0.0, 0.0), m, placed) is True

    def test_no_collision_with_placed(self):
        m = _meta()
        placed = [((10.0, 0.0, 0.0), m)]
        assert get_collision_detector().intersects_any((0.0, 0.0, 0.0), m, placed) is False


class TestValidatePosition:
    def test_valid_position(self):
        m = _meta()
        result = get_collision_detector().validate_position(
            (0.0, 0.0, 0.0), m, [((5.0, 0.0, 0.0), m)]
        )
        assert result["valid"] is True
        assert result["collisions"] == []

    def test_invalid_position(self):
        m = _meta(bx=2.0, by=2.0, bz=2.0, asset_id="already_placed")
        result = get_collision_detector().validate_position(
            (0.5, 0.0, 0.0), m, [((0.0, 0.0, 0.0), m)]
        )
        assert result["valid"] is False
        assert "already_placed" in result["collisions"]


class TestValidateScene:
    def test_empty_scene(self):
        report = get_collision_detector().validate_scene([])
        assert report.ok is True
        assert report.collision_count == 0

    def test_single_asset_no_collision(self):
        m = _meta()
        report = get_collision_detector().validate_scene([("a", (0.0, 0.0, 0.0), m)])
        assert report.ok is True

    def test_two_overlapping_assets(self):
        m = _meta(bx=2.0, by=2.0, bz=2.0)
        report = get_collision_detector().validate_scene([
            ("table", (0.0, 0.0, 0.0), m),
            ("chair", (1.0, 0.0, 0.0), m),
        ])
        assert report.ok is False
        assert report.collision_count == 1
        assert report.pairs[0].asset_a == "table"
        assert report.pairs[0].asset_b == "chair"

    def test_three_assets_two_collisions(self):
        m = _meta(bx=3.0, by=3.0, bz=3.0)
        report = get_collision_detector().validate_scene([
            ("a", (0.0, 0.0, 0.0), m),
            ("b", (1.0, 0.0, 0.0), m),
            ("c", (2.0, 0.0, 0.0), m),
        ])
        # a collides with b and c; b collides with c
        assert report.collision_count >= 2

    def test_no_collision_well_spaced(self):
        m = _meta(bx=1.0, by=1.0, bz=1.0)
        report = get_collision_detector().validate_scene([
            ("a", (0.0,  0.0, 0.0), m),
            ("b", (5.0,  0.0, 0.0), m),
            ("c", (10.0, 0.0, 0.0), m),
        ])
        assert report.ok is True
        assert report.collision_count == 0

    def test_affected_asset_ids(self):
        m = _meta(bx=4.0, by=4.0, bz=4.0)
        report = get_collision_detector().validate_scene([
            ("machine_01", (0.0, 0.0, 0.0), m),
            ("barrel_01",  (2.0, 0.0, 0.0), m),
        ])
        assert "machine_01" in report.asset_ids
        assert "barrel_01"  in report.asset_ids

    def test_collision_report_serializable(self):
        m = _meta(bx=2.0, by=2.0, bz=2.0)
        report = get_collision_detector().validate_scene([
            ("a", (0.0, 0.0, 0.0), m),
            ("b", (1.0, 0.0, 0.0), m),
        ])
        d = report.to_dict()
        assert isinstance(d["pairs"], list)
        assert d["collision_count"] == 1
