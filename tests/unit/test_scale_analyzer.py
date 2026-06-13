"""Tests for AssetScaleAnalyzer (Tier 9.6)."""

import pytest
from src.runtime.assets.assembly.asset_scale_analyzer import (
    SCALE_CLASSES,
    STRUCTURAL_PLACEMENT_TYPES,
    STRUCTURAL_CATEGORIES,
    AssetScaleProfile,
    AssetScaleAnalyzer,
    get_asset_scale_analyzer,
    reset_asset_scale_analyzer_for_tests,
)
from src.runtime.assets.assembly.unit_normalizer import reset_unit_normalizer_for_tests
from src.runtime.assets.assembly.bounding_box_extractor import reset_bbox_extractor_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_asset_scale_analyzer_for_tests()
    reset_unit_normalizer_for_tests()
    reset_bbox_extractor_for_tests()
    yield
    reset_asset_scale_analyzer_for_tests()
    reset_unit_normalizer_for_tests()
    reset_bbox_extractor_for_tests()


class TestSingleton:
    def test_singleton_same_instance(self):
        assert get_asset_scale_analyzer() is get_asset_scale_analyzer()

    def test_reset_new_instance(self):
        a = get_asset_scale_analyzer()
        reset_asset_scale_analyzer_for_tests()
        assert a is not get_asset_scale_analyzer()


class TestClassifyScale:
    def test_cup_is_tiny(self):
        a = get_asset_scale_analyzer()
        # Cup: ~8cm diameter — max_dim ~0.08 m
        cls, is_struct = a.classify_scale(0.08, 0.0064, "", "prop")
        assert cls == "tiny"
        assert is_struct is False

    def test_bucket_is_small(self):
        a = get_asset_scale_analyzer()
        # Bucket: ~0.40 m
        cls, is_struct = a.classify_scale(0.40, 0.16, "bucket", "prop")
        assert cls == "small"

    def test_chair_is_medium(self):
        a = get_asset_scale_analyzer()
        # Chair: 0.489 × 0.838 × 0.433 m → max_dim = 0.838
        cls, is_struct = a.classify_scale(0.838, 0.212, "chair", "furniture")
        assert cls == "medium"

    def test_table_is_medium(self):
        a = get_asset_scale_analyzer()
        # Small table: 0.697 × 0.499 × 0.698 m → max_dim = 0.698
        cls, is_struct = a.classify_scale(0.698, 0.487, "table", "furniture")
        assert cls == "medium"

    def test_beam_is_structural_by_size(self):
        a = get_asset_scale_analyzer()
        # Beam: 3.777 m max dim → >= 4.0 threshold... wait, 3.777 < 4.0
        # Actually 3.777 < 4.0 so it's "large" by size alone
        # But placement_type "beam" → structural override
        cls, is_struct = a.classify_scale(3.777, 1.367, "beam", "structure")
        assert cls == "structural"
        assert is_struct is True

    def test_structural_by_placement_type(self):
        a = get_asset_scale_analyzer()
        for pt in ["wall", "column", "platform", "crane", "terrain"]:
            cls, is_struct = a.classify_scale(1.0, 0.5, pt, "prop")
            assert cls == "structural", f"{pt} should be structural"
            assert is_struct is True

    def test_structural_by_category(self):
        a = get_asset_scale_analyzer()
        for cat in ["structure", "architectural", "terrain"]:
            cls, is_struct = a.classify_scale(1.0, 0.5, "", cat)
            assert cls == "structural", f"category '{cat}' should be structural"

    def test_very_large_asset_is_structural(self):
        a = get_asset_scale_analyzer()
        cls, is_struct = a.classify_scale(5.0, 25.0, "", "prop")
        assert cls == "structural"

    def test_large_machine_is_large(self):
        a = get_asset_scale_analyzer()
        # 3.5 m machine — under 4.0 threshold, not structural type
        cls, is_struct = a.classify_scale(3.5, 9.0, "machine", "machinery")
        assert cls == "large"
        assert is_struct is False


class TestAnalyzeAsset:
    def test_chair_cm_metadata(self):
        a = get_asset_scale_analyzer()
        asset = {
            "name": "Wooden Chair",
            "bbox_x": 48.9, "bbox_y": 83.8, "bbox_z": 43.3,
            "category": "furniture",
        }
        profile = a.analyze_asset(asset)
        assert profile.asset_scale_class == "medium"
        assert profile.is_structural is False
        assert abs(profile.bbox_meters[0] - 0.489) < 1e-4
        assert abs(profile.bbox_meters[1] - 0.838) < 1e-4

    def test_beam_cm_metadata_is_structural(self):
        a = get_asset_scale_analyzer()
        asset = {
            "name": "Old Wooden Beam",
            "bbox_x": 377.7, "bbox_y": 36.6, "bbox_z": 36.2,
            "category": "structure",
        }
        profile = a.analyze_asset(asset)
        assert profile.asset_scale_class == "structural"
        assert profile.is_structural is True
        assert abs(profile.bbox_meters[0] - 3.777) < 1e-4

    def test_no_bbox_uses_category_defaults(self):
        a = get_asset_scale_analyzer()
        asset = {"name": "Unknown Prop", "category": "prop"}
        profile = a.analyze_asset(asset)
        assert isinstance(profile, AssetScaleProfile)
        assert profile.asset_scale_class in SCALE_CLASSES

    def test_explicit_meters_not_converted(self):
        a = get_asset_scale_analyzer()
        asset = {
            "name": "Precise Asset",
            "bbox_x": 1.5, "bbox_y": 0.9, "bbox_z": 0.8,
            "unit_system": "meters",
            "category": "furniture",
        }
        profile = a.analyze_asset(asset)
        assert abs(profile.bbox_meters[0] - 1.5) < 1e-6

    def test_footprint_area_computed_correctly(self):
        a = get_asset_scale_analyzer()
        # Chair: 0.489 x 0.433 m → footprint ≈ 0.212 m²
        asset = {"name": "Chair", "bbox_x": 48.9, "bbox_y": 83.8, "bbox_z": 43.3}
        profile = a.analyze_asset(asset)
        expected_footprint = profile.bbox_meters[0] * profile.bbox_meters[2]
        assert abs(profile.footprint_area - expected_footprint) < 1e-6

    def test_placement_radius_computed_correctly(self):
        a = get_asset_scale_analyzer()
        asset = {"name": "Table", "bbox_x": 69.7, "bbox_y": 49.9, "bbox_z": 69.8}
        profile = a.analyze_asset(asset)
        expected_radius = max(profile.bbox_meters[0], profile.bbox_meters[2]) / 2.0
        assert abs(profile.placement_radius - expected_radius) < 1e-6

    def test_never_raises(self):
        a = get_asset_scale_analyzer()
        profile = a.analyze_asset(None)  # type: ignore
        assert isinstance(profile, AssetScaleProfile)


class TestSpacingFromProfiles:
    def test_spacing_formula(self):
        a = get_asset_scale_analyzer()
        # radius_a=0.30, margin=0.20, radius_b=0.35 → spacing=0.85
        from src.runtime.assets.assembly.asset_scale_analyzer import AssetScaleProfile
        pa = AssetScaleProfile(placement_radius=0.30, asset_scale_class="medium")
        pb = AssetScaleProfile(placement_radius=0.35, asset_scale_class="medium")
        spacing = a.spacing_from_profiles(pa, pb, clearance_margin=0.20)
        assert abs(spacing - 0.85) < 1e-6

    def test_spacing_always_positive(self):
        a = get_asset_scale_analyzer()
        pa = AssetScaleProfile(placement_radius=0.0, asset_scale_class="tiny")
        pb = AssetScaleProfile(placement_radius=0.0, asset_scale_class="tiny")
        assert a.spacing_from_profiles(pa, pb) >= 0.0


class TestScaleProfileSerialization:
    def test_to_dict_roundtrip(self):
        a = get_asset_scale_analyzer()
        asset = {"name": "Chair", "bbox_x": 48.9, "bbox_y": 83.8, "bbox_z": 43.3}
        profile = a.analyze_asset(asset)
        d = profile.to_dict()
        restored = AssetScaleProfile.from_dict(d)
        assert restored.asset_scale_class == profile.asset_scale_class
        assert restored.is_structural == profile.is_structural
        assert abs(restored.placement_radius - profile.placement_radius) < 1e-6
