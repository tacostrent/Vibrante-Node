"""Tests for SupportSurfaceDetector (Tier 9.7)."""
import pytest
from src.runtime.assets.geometry import (
    get_support_surface_detector,
    reset_support_surface_detector_for_tests,
    SupportSurface,
)


@pytest.fixture(autouse=True)
def reset():
    reset_support_surface_detector_for_tests()
    yield
    reset_support_surface_detector_for_tests()


class TestTableSurfaces:
    def test_table_has_tabletop(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "table"}, 1.2, 0.75, 0.8
        )
        assert len(surfaces) == 1
        s = surfaces[0]
        assert s.surface_type == "tabletop"
        assert abs(s.height_m - 0.75) < 1e-4
        assert s.area_m2 > 0
        assert s.normal == [0.0, 1.0, 0.0]

    def test_table_area_scaled_from_dims(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "table"}, 1.2, 0.75, 0.8
        )
        expected_area = 1.2 * 0.8 * 0.85
        assert abs(surfaces[0].area_m2 - expected_area) < 0.01


class TestWorkbenchSurfaces:
    def test_workbench_has_worktop(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "workbench"}, 1.8, 0.9, 0.75
        )
        worktops = [s for s in surfaces if s.surface_type == "worktop"]
        assert len(worktops) >= 1
        assert abs(worktops[0].height_m - 0.9) < 1e-4

    def test_tall_workbench_has_lower_shelf(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "workbench"}, 1.8, 1.0, 0.75
        )
        types = [s.surface_type for s in surfaces]
        assert "lower_shelf" in types


class TestCounterSurfaces:
    def test_counter_has_countertop(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "counter"}, 2.5, 0.9, 0.7
        )
        tops = [s for s in surfaces if s.surface_type == "countertop"]
        assert len(tops) >= 1

    def test_tall_counter_has_lower_shelf(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "bar_counter"}, 3.0, 1.1, 0.65
        )
        types = [s.surface_type for s in surfaces]
        assert "lower_shelf" in types


class TestCabinetSurfaces:
    def test_cabinet_has_top_and_shelves(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "cabinet"}, 0.9, 1.8, 0.5
        )
        types = [s.surface_type for s in surfaces]
        assert "top_surface" in types
        assert "shelf" in types
        assert len(surfaces) >= 2

    def test_cabinet_shelves_increase_with_height(self):
        surfaces_tall = get_support_surface_detector().detect(
            {"placement_type": "cabinet"}, 0.9, 2.4, 0.5
        )
        surfaces_short = get_support_surface_detector().detect(
            {"placement_type": "cabinet"}, 0.9, 0.9, 0.5
        )
        shelves_tall  = [s for s in surfaces_tall  if s.surface_type == "shelf"]
        shelves_short = [s for s in surfaces_short if s.surface_type == "shelf"]
        assert len(shelves_tall) >= len(shelves_short)


class TestShelfUnit:
    def test_shelf_has_multiple_shelves(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "shelf"}, 0.9, 1.8, 0.35
        )
        assert len(surfaces) >= 2
        for s in surfaces:
            assert s.surface_type == "shelf"

    def test_shelf_heights_increase(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "shelf"}, 0.9, 1.8, 0.35
        )
        heights = [s.height_m for s in surfaces]
        assert heights == sorted(heights)


class TestServerRack:
    def test_rack_has_rack_units(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "server_rack"}, 0.6, 2.0, 1.0
        )
        assert len(surfaces) >= 4
        for s in surfaces:
            assert s.surface_type == "rack_unit"
            assert s.load_capacity == "heavy"


class TestNonSurfaceTypes:
    def test_chair_no_surface(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "chair"}, 0.55, 0.9, 0.55
        )
        assert surfaces == []

    def test_bucket_no_surface(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "bucket"}, 0.3, 0.38, 0.3
        )
        assert surfaces == []

    def test_vehicle_no_surface(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "vehicle"}, 4.5, 1.8, 2.0
        )
        assert surfaces == []

    def test_machine_no_surface(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "machine"}, 2.5, 2.0, 2.0
        )
        assert surfaces == []

    def test_wall_no_surface(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "wall"}, 5.0, 3.0, 0.25
        )
        assert surfaces == []

    def test_beam_no_surface(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "beam"}, 4.0, 0.3, 0.3
        )
        assert surfaces == []


class TestExplicitSurfaces:
    def test_explicit_surfaces_used(self):
        asset = {
            "placement_type": "table",
            "support_surfaces": [
                {"surface_type": "custom_top", "height_m": 0.80, "area_m2": 0.96,
                 "normal": [0, 1, 0], "load_capacity": "heavy", "notes": ""},
            ]
        }
        surfaces = get_support_surface_detector().detect(asset, 1.2, 0.80, 0.8)
        assert surfaces[0].surface_type == "custom_top"
        assert surfaces[0].load_capacity == "heavy"


class TestReturnTypes:
    def test_returns_list_of_support_surface(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "table"}, 1.2, 0.75, 0.8
        )
        assert all(isinstance(s, SupportSurface) for s in surfaces)

    def test_to_dict_round_trip(self):
        surfaces = get_support_surface_detector().detect(
            {"placement_type": "table"}, 1.2, 0.75, 0.8
        )
        for s in surfaces:
            d = s.to_dict()
            s2 = SupportSurface.from_dict(d)
            assert s2.surface_type == s.surface_type
            assert abs(s2.height_m - s.height_m) < 1e-6

    def test_no_raise_on_none(self):
        surfaces = get_support_surface_detector().detect(None, 1.0, 1.0, 1.0)  # type: ignore
        assert isinstance(surfaces, list)
