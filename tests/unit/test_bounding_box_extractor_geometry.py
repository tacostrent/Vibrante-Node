"""Tests for GeometryBBoxExtractor (Tier 9.7)."""
import pytest
from src.runtime.assets.geometry import (
    get_geometry_bbox_extractor,
    reset_geometry_bbox_extractor_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_geometry_bbox_extractor_for_tests()
    yield
    reset_geometry_bbox_extractor_for_tests()


class TestExplicitBboxMinMax:
    def test_explicit_meters(self):
        asset = {
            "bbox_min": [0.0, 0.0, 0.0],
            "bbox_max": [1.2, 0.75, 0.8],
        }
        r = get_geometry_bbox_extractor().extract(asset)
        assert abs(r["width_m"]  - 1.2)  < 1e-6
        assert abs(r["height_m"] - 0.75) < 1e-6
        assert abs(r["depth_m"]  - 0.8)  < 1e-6
        assert r["source"] == "explicit"

    def test_explicit_cm_with_unit_field(self):
        asset = {
            "bbox_min": [0.0, 0.0, 0.0],
            "bbox_max": [120.0, 75.0, 80.0],
            "unit": "cm",
        }
        r = get_geometry_bbox_extractor().extract(asset)
        assert abs(r["width_m"]  - 1.20) < 0.01
        assert abs(r["height_m"] - 0.75) < 0.01
        assert abs(r["depth_m"]  - 0.80) < 0.01

    def test_explicit_cm_heuristic(self):
        """Scalar bbox fields > 10 with no unit field → heuristic detects cm."""
        asset = {
            "bbox_x": 55.0,
            "bbox_y": 90.0,
            "bbox_z": 55.0,
        }
        r = get_geometry_bbox_extractor().extract(asset)
        # Should convert 55 cm → 0.55 m via heuristic
        assert abs(r["width_m"]  - 0.55) < 0.01
        assert abs(r["height_m"] - 0.90) < 0.01


class TestBoundingBoxDict:
    def test_bounding_box_min_max(self):
        asset = {
            "bounding_box": {
                "min": [0.0, 0.0, 0.0],
                "max": [1.0, 0.9, 0.6],
            }
        }
        r = get_geometry_bbox_extractor().extract(asset)
        assert abs(r["width_m"]  - 1.0) < 1e-6
        assert abs(r["height_m"] - 0.9) < 1e-6
        assert abs(r["depth_m"]  - 0.6) < 1e-6

    def test_bounding_box_center_extents(self):
        asset = {
            "bounding_box": {
                "center":  [0.0, 0.45, 0.0],
                "extents": [1.0, 0.9, 0.6],
            }
        }
        r = get_geometry_bbox_extractor().extract(asset)
        assert abs(r["width_m"]  - 1.0) < 0.01
        assert abs(r["height_m"] - 0.9) < 0.01
        assert abs(r["depth_m"]  - 0.6) < 0.01


class TestUsdExtent:
    def test_usd_extent_format(self):
        asset = {
            "extent": [[-0.6, 0.0, -0.4], [0.6, 0.75, 0.4]],
            "unit": "meters",
        }
        r = get_geometry_bbox_extractor().extract(asset)
        assert abs(r["width_m"]  - 1.2)  < 1e-6
        assert abs(r["height_m"] - 0.75) < 1e-6
        assert abs(r["depth_m"]  - 0.8)  < 1e-6
        assert r["source"] == "format_metadata"


class TestScalarBbox:
    def test_bbox_xyz_scalars(self):
        asset = {
            "bbox_x": 0.55,
            "bbox_y": 0.90,
            "bbox_z": 0.55,
        }
        r = get_geometry_bbox_extractor().extract(asset)
        assert abs(r["width_m"]  - 0.55) < 1e-6
        assert abs(r["height_m"] - 0.90) < 1e-6
        assert abs(r["depth_m"]  - 0.55) < 1e-6

    def test_width_height_depth_scalars(self):
        asset = {"width": 1.2, "height": 0.75, "depth": 0.8}
        r = get_geometry_bbox_extractor().extract(asset)
        assert abs(r["width_m"]  - 1.2)  < 1e-6
        assert abs(r["height_m"] - 0.75) < 1e-6


class TestPlacementTypeFallback:
    def test_chair_defaults(self):
        asset = {"placement_type": "chair"}
        r = get_geometry_bbox_extractor().extract(asset)
        assert r["width_m"]  > 0
        assert r["height_m"] > 0
        assert r["source"] == "estimated"
        assert any("placement-type" in w for w in r["warnings"])

    def test_machine_defaults(self):
        asset = {"placement_type": "machine"}
        r = get_geometry_bbox_extractor().extract(asset)
        assert r["width_m"] >= 2.0

    def test_wall_defaults(self):
        asset = {"placement_type": "wall"}
        r = get_geometry_bbox_extractor().extract(asset)
        assert r["width_m"] >= 3.0
        assert r["height_m"] >= 2.5


class TestCategoryFallback:
    def test_furniture_defaults(self):
        asset = {"category": "furniture"}
        r = get_geometry_bbox_extractor().extract(asset)
        assert r["width_m"] > 0
        assert r["source"] == "estimated"

    def test_vehicle_defaults(self):
        asset = {"category": "vehicle"}
        r = get_geometry_bbox_extractor().extract(asset)
        assert r["width_m"] >= 3.0


class TestGenericFallback:
    def test_empty_asset_gets_fallback(self):
        r = get_geometry_bbox_extractor().extract({})
        assert r["width_m"]  == 1.0
        assert r["height_m"] == 1.0
        assert r["depth_m"]  == 1.0
        assert r["source"] == "estimated"
        assert any("fallback" in w for w in r["warnings"])

    def test_no_raise_on_bad_input(self):
        r = get_geometry_bbox_extractor().extract(None)  # type: ignore
        assert r["width_m"] > 0
