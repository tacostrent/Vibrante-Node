"""Tests for FootprintCalculator (Tier 9.6)."""

import pytest
from src.runtime.assets.assembly.footprint_calculator import (
    FootprintResult,
    FootprintCalculator,
    get_footprint_calculator,
    reset_footprint_calculator_for_tests,
)
from src.runtime.assets.assembly.unit_normalizer import reset_unit_normalizer_for_tests
from src.runtime.assets.assembly.bounding_box_extractor import reset_bbox_extractor_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_footprint_calculator_for_tests()
    reset_unit_normalizer_for_tests()
    reset_bbox_extractor_for_tests()
    yield
    reset_footprint_calculator_for_tests()
    reset_unit_normalizer_for_tests()
    reset_bbox_extractor_for_tests()


class TestSingleton:
    def test_singleton_same_instance(self):
        assert get_footprint_calculator() is get_footprint_calculator()

    def test_reset_new_instance(self):
        a = get_footprint_calculator()
        reset_footprint_calculator_for_tests()
        assert a is not get_footprint_calculator()


class TestCalculate:
    def test_chair_footprint(self):
        calc = get_footprint_calculator()
        # Chair: 48.9 x 43.3 cm → 0.489 x 0.433 m → footprint ≈ 0.212 m²
        asset = {"name": "Wooden Chair", "bbox_x": 48.9, "bbox_y": 83.8, "bbox_z": 43.3}
        result = calc.calculate(asset)
        assert abs(result.footprint_area - 0.489 * 0.433) < 1e-4
        assert result.width_m > 0
        assert result.height_m > 0
        assert result.depth_m > 0

    def test_table_footprint(self):
        calc = get_footprint_calculator()
        asset = {"name": "Wooden Table", "bbox_x": 69.7, "bbox_y": 49.9, "bbox_z": 69.8}
        result = calc.calculate(asset)
        assert abs(result.footprint_area - 0.697 * 0.698) < 1e-3

    def test_clearance_radius(self):
        calc = get_footprint_calculator()
        asset = {"name": "Chair", "bbox_x": 48.9, "bbox_y": 83.8, "bbox_z": 43.3}
        result = calc.calculate(asset)
        expected_radius = max(0.489, 0.433) / 2.0
        assert abs(result.clearance_radius - expected_radius) < 1e-4

    def test_zone_radius_larger_than_clearance(self):
        calc = get_footprint_calculator()
        asset = {"name": "Chair", "bbox_x": 48.9, "bbox_y": 83.8, "bbox_z": 43.3}
        result = calc.calculate(asset)
        assert result.zone_radius > result.clearance_radius

    def test_no_bbox_uses_category_defaults(self):
        calc = get_footprint_calculator()
        asset = {"category": "furniture"}
        result = calc.calculate(asset)
        assert isinstance(result, FootprintResult)
        assert result.footprint_area >= 0.0

    def test_never_raises(self):
        calc = get_footprint_calculator()
        result = calc.calculate(None)  # type: ignore
        assert isinstance(result, FootprintResult)


class TestCalculateFromMeters:
    def test_explicit_meters(self):
        calc = get_footprint_calculator()
        result = calc.calculate_from_meters("test_asset", 1.0, 0.8, 0.8)
        assert abs(result.footprint_area - 0.8) < 1e-6
        assert abs(result.clearance_radius - 0.5) < 1e-6

    def test_footprint_is_width_times_depth(self):
        calc = get_footprint_calculator()
        result = calc.calculate_from_meters("asset", 2.0, 1.0, 3.0)
        assert abs(result.footprint_area - 6.0) < 1e-6


class TestTotalFootprint:
    def test_sum_of_footprints(self):
        calc = get_footprint_calculator()
        r1 = calc.calculate_from_meters("a", 1.0, 1.0, 1.0)
        r2 = calc.calculate_from_meters("b", 2.0, 1.0, 2.0)
        total = calc.total_footprint([r1, r2])
        assert abs(total - (1.0 + 4.0)) < 1e-6


class TestFootprintResultSerialization:
    def test_to_dict_roundtrip(self):
        calc = get_footprint_calculator()
        result = calc.calculate({"name": "Chair", "bbox_x": 48.9, "bbox_y": 83.8, "bbox_z": 43.3})
        d = result.to_dict()
        restored = FootprintResult.from_dict(d)
        assert abs(restored.footprint_area - result.footprint_area) < 1e-6
        assert abs(restored.zone_radius - result.zone_radius) < 1e-6
