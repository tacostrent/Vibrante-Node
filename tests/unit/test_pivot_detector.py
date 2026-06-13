"""Tests for PivotDetector (Tier 9.7)."""
import pytest
from src.runtime.assets.geometry import (
    get_pivot_detector,
    reset_pivot_detector_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_pivot_detector_for_tests()
    yield
    reset_pivot_detector_for_tests()


class TestFloorPlacedTypes:
    def test_chair_bottom_center(self):
        r = get_pivot_detector().detect({"placement_type": "chair"}, height_m=0.9)
        assert r["pivot_type"] == "bottom_center"
        assert r["confidence"] >= 0.9

    def test_table_bottom_center(self):
        r = get_pivot_detector().detect({"placement_type": "table"}, height_m=0.75)
        assert r["pivot_type"] == "bottom_center"

    def test_machine_bottom_center(self):
        r = get_pivot_detector().detect({"placement_type": "machine"}, height_m=2.0)
        assert r["pivot_type"] == "bottom_center"

    def test_vehicle_bottom_center(self):
        r = get_pivot_detector().detect({"placement_type": "vehicle"}, height_m=1.8)
        assert r["pivot_type"] == "bottom_center"


class TestCeilingMountedTypes:
    def test_hanging_light_top_center(self):
        r = get_pivot_detector().detect({"placement_type": "hanging_light"}, height_m=0.5)
        assert r["pivot_type"] == "top_center"
        assert r["confidence"] >= 0.9

    def test_pendant_light_top_center(self):
        r = get_pivot_detector().detect({"placement_type": "pendant_light"}, height_m=0.4)
        assert r["pivot_type"] == "top_center"


class TestModularTypes:
    def test_floor_panel_bottom_left(self):
        r = get_pivot_detector().detect({"placement_type": "floor_panel"}, height_m=0.1)
        assert r["pivot_type"] == "bottom_left"

    def test_wall_tile_bottom_left(self):
        r = get_pivot_detector().detect({"placement_type": "wall_tile"}, height_m=0.5)
        assert r["pivot_type"] == "bottom_left"


class TestExplicitPivot:
    def test_explicit_string_pivot(self):
        r = get_pivot_detector().detect({"pivot": "center"}, height_m=1.0)
        assert r["pivot_type"] == "center"
        assert r["confidence"] == 1.0

    def test_explicit_top_center_string(self):
        r = get_pivot_detector().detect({"pivot_type": "top_center"}, height_m=0.5)
        assert r["pivot_type"] == "top_center"
        assert r["confidence"] == 1.0

    def test_explicit_position_vector(self):
        r = get_pivot_detector().detect({"pivot": [0.0, 0.5, 0.0]}, height_m=1.0)
        assert r["pivot_type"] == "center"
        assert r["confidence"] == 1.0

    def test_explicit_bottom_position(self):
        r = get_pivot_detector().detect({"pivot_position": [0.0, 0.0, 0.0]}, height_m=1.0)
        assert r["pivot_type"] == "bottom_center"


class TestCategoryFallback:
    def test_furniture_category_bottom_center(self):
        r = get_pivot_detector().detect({"category": "furniture"}, height_m=0.9)
        assert r["pivot_type"] == "bottom_center"
        assert r["confidence"] >= 0.7

    def test_structural_category_bottom_left(self):
        r = get_pivot_detector().detect({"category": "structure"}, height_m=3.0)
        assert r["pivot_type"] == "bottom_left"

    def test_vehicle_category_bottom_center(self):
        r = get_pivot_detector().detect({"category": "vehicle"}, height_m=1.8)
        assert r["pivot_type"] == "bottom_center"


class TestGenericFallback:
    def test_empty_asset_bottom_center(self):
        r = get_pivot_detector().detect({}, height_m=1.0)
        assert r["pivot_type"] == "bottom_center"
        assert r["confidence"] == 0.5

    def test_no_raise_on_none(self):
        r = get_pivot_detector().detect(None, height_m=1.0)  # type: ignore
        assert r["pivot_type"] in ("bottom_center", "center", "bottom_left", "top_center", "custom")


class TestPositionValues:
    def test_bottom_center_at_origin(self):
        r = get_pivot_detector().detect({"placement_type": "table"}, height_m=0.75)
        assert r["pivot_position"] == [0.0, 0.0, 0.0]

    def test_top_center_at_height(self):
        r = get_pivot_detector().detect({"placement_type": "hanging_light"}, height_m=0.4)
        assert abs(r["pivot_position"][1] - 0.4) < 1e-6

    def test_center_at_half_height(self):
        r = get_pivot_detector().detect({"pivot": "center"}, height_m=2.0)
        assert abs(r["pivot_position"][1] - 1.0) < 1e-6
