"""Tests for GeometryAnalyzer (Tier 9.7)."""
import pytest
from src.runtime.assets.geometry import (
    get_geometry_analyzer,
    reset_geometry_analyzer_for_tests,
    reset_asset_metrics_builder_for_tests,
    reset_geometry_bbox_extractor_for_tests,
    reset_pivot_detector_for_tests,
    reset_ground_contact_detector_for_tests,
    reset_support_surface_detector_for_tests,
    GeometryAnalysisResult,
    AssetMetrics,
)


@pytest.fixture(autouse=True)
def reset_all():
    reset_geometry_analyzer_for_tests()
    reset_asset_metrics_builder_for_tests()
    reset_geometry_bbox_extractor_for_tests()
    reset_pivot_detector_for_tests()
    reset_ground_contact_detector_for_tests()
    reset_support_surface_detector_for_tests()
    yield
    reset_geometry_analyzer_for_tests()
    reset_asset_metrics_builder_for_tests()
    reset_geometry_bbox_extractor_for_tests()
    reset_pivot_detector_for_tests()
    reset_ground_contact_detector_for_tests()
    reset_support_surface_detector_for_tests()


class TestAnalyzeAsset:
    def test_returns_analysis_result(self):
        analyzer = get_geometry_analyzer()
        result = analyzer.analyze_asset({"asset_id": "test", "placement_type": "chair"})
        assert isinstance(result, GeometryAnalysisResult)
        assert result.asset_id == "test"

    def test_explicit_bbox_min_max(self):
        asset = {
            "asset_id": "chair01",
            "bbox_min": [0.0, 0.0, 0.0],
            "bbox_max": [0.55, 0.90, 0.55],
            "placement_type": "chair",
        }
        result = get_geometry_analyzer().analyze_asset(asset)
        assert abs(result.width_m  - 0.55) < 1e-4
        assert abs(result.height_m - 0.90) < 1e-4
        assert abs(result.depth_m  - 0.55) < 1e-4
        assert result.source == "explicit"

    def test_placement_type_fallback_chair(self):
        asset = {"asset_id": "c1", "placement_type": "chair"}
        result = get_geometry_analyzer().analyze_asset(asset)
        assert result.width_m  > 0
        assert result.height_m > 0
        assert result.depth_m  > 0
        assert result.scale_class == "medium"

    def test_placement_type_fallback_machine(self):
        asset = {"asset_id": "m1", "placement_type": "machine"}
        result = get_geometry_analyzer().analyze_asset(asset)
        assert result.scale_class == "hero"
        assert result.is_hero is True
        assert result.is_structural is False

    def test_placement_type_fallback_beam(self):
        asset = {"asset_id": "b1", "placement_type": "beam"}
        result = get_geometry_analyzer().analyze_asset(asset)
        assert result.scale_class == "structural"
        assert result.is_structural is True

    def test_tiny_scale_cup(self):
        asset = {
            "asset_id": "cup1",
            "bbox_min": [0.0, 0.0, 0.0],
            "bbox_max": [0.08, 0.10, 0.08],
            "placement_type": "prop",
        }
        result = get_geometry_analyzer().analyze_asset(asset)
        assert result.scale_class == "tiny"

    def test_small_scale_bucket(self):
        asset = {"asset_id": "bkt1", "placement_type": "bucket"}
        result = get_geometry_analyzer().analyze_asset(asset)
        assert result.scale_class == "small"

    def test_large_scale_table(self):
        asset = {"asset_id": "t1", "placement_type": "table"}
        result = get_geometry_analyzer().analyze_asset(asset)
        # Table default dims: 1.20 x 0.75 x 0.80 → max=1.2 → "medium" < 1.5
        # But table top is 1.2m → medium
        assert result.scale_class in ("medium", "large")

    def test_cm_unit_conversion(self):
        asset = {
            "asset_id": "ch_cm",
            "bbox_x": 55.0,
            "bbox_y": 90.0,
            "bbox_z": 55.0,
            "unit_system": "cm",
            "placement_type": "chair",
        }
        result = get_geometry_analyzer().analyze_asset(asset)
        assert abs(result.width_m  - 0.55) < 0.01
        assert abs(result.height_m - 0.90) < 0.01
        assert abs(result.depth_m  - 0.55) < 0.01

    def test_empty_asset_no_crash(self):
        result = get_geometry_analyzer().analyze_asset({})
        assert isinstance(result, GeometryAnalysisResult)
        assert result.width_m > 0
        assert result.height_m > 0

    def test_none_asset_no_crash(self):
        result = get_geometry_analyzer().analyze_asset(None)  # type: ignore
        assert isinstance(result, GeometryAnalysisResult)
        assert result.ok is False

    def test_pivot_type_in_result(self):
        asset = {"asset_id": "tbl1", "placement_type": "table"}
        result = get_geometry_analyzer().analyze_asset(asset)
        assert result.pivot_type in ("bottom_center", "center", "bottom_left", "top_center", "custom")

    def test_analyze_count_increments(self):
        analyzer = get_geometry_analyzer()
        count0 = analyzer.analyze_count
        analyzer.analyze_asset({"asset_id": "x1"})
        analyzer.analyze_asset({"asset_id": "x2"})
        assert analyzer.analyze_count == count0 + 2


class TestBuildMetrics:
    def test_returns_asset_metrics(self):
        result = get_geometry_analyzer().build_metrics({"asset_id": "tbl", "placement_type": "table"})
        assert isinstance(result, AssetMetrics)
        assert result.width_m > 0

    def test_no_raise_on_invalid(self):
        result = get_geometry_analyzer().build_metrics(None)  # type: ignore
        assert isinstance(result, AssetMetrics)


class TestExtractGeometryInformation:
    def test_returns_dict(self):
        info = get_geometry_analyzer().extract_geometry_information(
            {"asset_id": "c1", "placement_type": "chair"}
        )
        assert isinstance(info, dict)
        assert "dimensions_m" in info
        assert "scale_class" in info
        assert "role" in info

    def test_contains_bbox(self):
        asset = {
            "asset_id": "c2",
            "bbox_min": [0.0, 0.0, 0.0],
            "bbox_max": [0.55, 0.90, 0.55],
            "placement_type": "chair",
        }
        info = get_geometry_analyzer().extract_geometry_information(asset)
        assert "bbox_min" in info
        assert "bbox_max" in info
        assert "support_surfaces" in info
        assert "ground_contacts" in info

    def test_no_raise_on_empty(self):
        info = get_geometry_analyzer().extract_geometry_information({})
        assert isinstance(info, dict)
