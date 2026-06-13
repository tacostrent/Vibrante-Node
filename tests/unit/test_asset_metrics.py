"""Tests for AssetMetrics data model (Tier 9.7)."""
import pytest
from src.runtime.assets.geometry import (
    AssetMetrics,
    SupportSurface,
    GroundContact,
    GEOMETRY_SCALE_CLASSES,
    PIVOT_TYPES,
    GEOMETRY_ROLES,
    HERO_PLACEMENT_TYPES,
    STRUCTURAL_PLACEMENT_TYPES,
    classify_geometry_scale,
    infer_role,
    get_asset_metrics_builder,
    reset_asset_metrics_builder_for_tests,
    reset_geometry_bbox_extractor_for_tests,
    reset_pivot_detector_for_tests,
    reset_ground_contact_detector_for_tests,
    reset_support_surface_detector_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_asset_metrics_builder_for_tests()
    reset_geometry_bbox_extractor_for_tests()
    reset_pivot_detector_for_tests()
    reset_ground_contact_detector_for_tests()
    reset_support_surface_detector_for_tests()
    yield
    reset_asset_metrics_builder_for_tests()
    reset_geometry_bbox_extractor_for_tests()
    reset_pivot_detector_for_tests()
    reset_ground_contact_detector_for_tests()
    reset_support_surface_detector_for_tests()


class TestConstants:
    def test_scale_classes_complete(self):
        assert "tiny"       in GEOMETRY_SCALE_CLASSES
        assert "small"      in GEOMETRY_SCALE_CLASSES
        assert "medium"     in GEOMETRY_SCALE_CLASSES
        assert "large"      in GEOMETRY_SCALE_CLASSES
        assert "structural" in GEOMETRY_SCALE_CLASSES
        assert "hero"       in GEOMETRY_SCALE_CLASSES

    def test_pivot_types_complete(self):
        assert "bottom_center" in PIVOT_TYPES
        assert "center"        in PIVOT_TYPES
        assert "bottom_left"   in PIVOT_TYPES
        assert "top_center"    in PIVOT_TYPES
        assert "custom"        in PIVOT_TYPES

    def test_hero_placement_types(self):
        assert "machine" in HERO_PLACEMENT_TYPES
        assert "vehicle" in HERO_PLACEMENT_TYPES
        assert "crane"   in HERO_PLACEMENT_TYPES

    def test_structural_placement_types(self):
        assert "wall"   in STRUCTURAL_PLACEMENT_TYPES
        assert "column" in STRUCTURAL_PLACEMENT_TYPES
        assert "beam"   in STRUCTURAL_PLACEMENT_TYPES


class TestClassifyGeometryScale:
    def test_tiny_cup(self):
        cls, is_s, is_h = classify_geometry_scale(0.08, "prop", "")
        assert cls == "tiny"
        assert not is_s and not is_h

    def test_small_bucket(self):
        cls, is_s, is_h = classify_geometry_scale(0.38, "bucket", "")
        assert cls == "small"

    def test_medium_chair(self):
        cls, is_s, is_h = classify_geometry_scale(0.9, "chair", "")
        assert cls == "medium"

    def test_large_table(self):
        # Conference table 2.4 m wide → max_dim=2.4 → large (>= 1.5 m, < 4.0 m)
        cls, is_s, is_h = classify_geometry_scale(2.4, "table", "")
        assert cls == "large"

    def test_structural_by_type(self):
        cls, is_s, is_h = classify_geometry_scale(1.5, "wall", "")
        assert cls == "structural"
        assert is_s is True

    def test_structural_by_category(self):
        cls, is_s, is_h = classify_geometry_scale(1.5, "", "structure")
        assert cls == "structural"
        assert is_s is True

    def test_structural_by_size(self):
        cls, is_s, is_h = classify_geometry_scale(5.0, "", "")
        assert cls == "structural"
        assert is_s is True

    def test_hero_machine(self):
        cls, is_s, is_h = classify_geometry_scale(2.5, "machine", "")
        assert cls == "hero"
        assert is_h is True
        assert is_s is False

    def test_hero_vehicle(self):
        cls, is_s, is_h = classify_geometry_scale(4.5, "vehicle", "")
        assert cls == "hero"
        assert is_h is True


class TestInferRole:
    def test_furniture_from_placement_type(self):
        assert infer_role("chair",   "", "medium") == "furniture"
        assert infer_role("table",   "", "large")  == "furniture"
        assert infer_role("cabinet", "", "large")  == "furniture"

    def test_structure_from_placement_type(self):
        assert infer_role("wall",   "", "structural") == "structure"
        assert infer_role("beam",   "", "structural") == "structure"
        assert infer_role("column", "", "structural") == "structure"

    def test_hero_asset_from_placement_type(self):
        assert infer_role("machine", "", "hero") == "hero_asset"
        assert infer_role("crane",   "", "hero") == "hero_asset"

    def test_vehicle_from_placement_type(self):
        assert infer_role("vehicle", "", "hero") == "vehicle"

    def test_prop_fallback(self):
        assert infer_role("unknown_thing", "", "medium") == "prop"

    def test_structure_from_scale_class(self):
        assert infer_role("", "", "structural") == "structure"


class TestAssetMetricsDataclass:
    def test_default_values(self):
        m = AssetMetrics()
        assert m.width_m  == 1.0
        assert m.height_m == 1.0
        assert m.depth_m  == 1.0
        assert m.pivot_type == "bottom_center"
        assert m.scale_class == "medium"
        assert m.role == "prop"
        assert m.source == "estimated"
        assert m.errors == []
        assert m.warnings == []

    def test_to_dict_contains_all_fields(self):
        m = AssetMetrics(asset_id="test", width_m=1.2, height_m=0.75)
        d = m.to_dict()
        assert d["asset_id"]   == "test"
        assert d["width_m"]    == 1.2
        assert d["height_m"]   == 0.75
        assert "bbox_min"      in d
        assert "support_surfaces" in d
        assert "ground_contacts"  in d

    def test_from_dict_round_trip(self):
        m = AssetMetrics(
            asset_id    = "r1",
            asset_name  = "Red Chair",
            width_m     = 0.55,
            height_m    = 0.90,
            depth_m     = 0.55,
            volume_m3   = 0.55 * 0.90 * 0.55,
            footprint_m2 = 0.55 * 0.55,
            placement_radius = 0.275,
            bbox_min    = [0.0, 0.0, 0.0],
            bbox_max    = [0.55, 0.90, 0.55],
            pivot_type  = "bottom_center",
            scale_class = "medium",
            role        = "furniture",
            is_structural = False,
            is_hero     = False,
            source      = "explicit",
        )
        d  = m.to_dict()
        m2 = AssetMetrics.from_dict(d)
        assert m2.asset_id    == m.asset_id
        assert m2.width_m     == m.width_m
        assert m2.height_m    == m.height_m
        assert m2.pivot_type  == m.pivot_type
        assert m2.scale_class == m.scale_class
        assert m2.source      == m.source

    def test_support_surfaces_round_trip(self):
        s = SupportSurface(surface_type="tabletop", height_m=0.75, area_m2=0.96)
        m = AssetMetrics(support_surfaces=[s])
        d  = m.to_dict()
        m2 = AssetMetrics.from_dict(d)
        assert len(m2.support_surfaces) == 1
        assert m2.support_surfaces[0].surface_type == "tabletop"

    def test_ground_contacts_round_trip(self):
        c = GroundContact(contact_type="leg", count=4, positions=[[0,0,0],[1,0,0]])
        m = AssetMetrics(ground_contacts=[c])
        d  = m.to_dict()
        m2 = AssetMetrics.from_dict(d)
        assert len(m2.ground_contacts) == 1
        assert m2.ground_contacts[0].contact_type == "leg"


class TestAssetMetricsBuilder:
    def test_build_chair(self):
        asset = {
            "asset_id": "chair1",
            "placement_type": "chair",
            "bbox_min": [0.0, 0.0, 0.0],
            "bbox_max": [0.55, 0.90, 0.55],
        }
        m = get_asset_metrics_builder().build(asset)
        assert isinstance(m, AssetMetrics)
        assert m.scale_class  == "medium"
        assert m.role         == "furniture"
        assert m.pivot_type   == "bottom_center"
        assert len(m.ground_contacts) >= 1
        assert m.ground_contacts[0].contact_type == "leg"

    def test_build_table_has_surface(self):
        asset = {
            "asset_id": "tbl1",
            "placement_type": "table",
            "bbox_min": [0.0, 0.0, 0.0],
            "bbox_max": [1.2, 0.75, 0.8],
        }
        m = get_asset_metrics_builder().build(asset)
        assert len(m.support_surfaces) >= 1
        assert m.support_surfaces[0].surface_type == "tabletop"

    def test_build_no_raise_on_bad_input(self):
        m = get_asset_metrics_builder().build(None)  # type: ignore
        assert isinstance(m, AssetMetrics)
        assert len(m.errors) > 0
