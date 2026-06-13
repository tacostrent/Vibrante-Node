"""Tests for BBoxExtractor (Tier 9.4)."""

import pytest
from src.runtime.assets.assembly.bounding_box_extractor import (
    get_bbox_extractor,
    reset_bbox_extractor_for_tests,
    _PLACEMENT_TYPE_DIMS,
    _CATEGORY_DIMS,
    _DEFAULT_DIMS,
)
from src.runtime.assets.assembly.spatial_metadata import SpatialMetadata


@pytest.fixture(autouse=True)
def reset():
    reset_bbox_extractor_for_tests()
    yield
    reset_bbox_extractor_for_tests()


class TestExtractBbox:
    def test_explicit_bbox_fields(self):
        asset = {"bbox_x": 3.0, "bbox_y": 1.5, "bbox_z": 2.0}
        bx, by, bz = get_bbox_extractor().extract_bbox(asset)
        assert (bx, by, bz) == (3.0, 1.5, 2.0)

    def test_explicit_bbox_with_centimeter_unit(self):
        asset = {"bbox_x": 220.0, "bbox_y": 80.0, "bbox_z": 130.0,
                 "unit_system": "centimeters"}
        bx, by, bz = get_bbox_extractor().extract_bbox(asset)
        assert abs(bx - 2.2) < 1e-6
        assert abs(by - 0.8) < 1e-6
        assert abs(bz - 1.3) < 1e-6

    def test_placement_type_table(self):
        asset = {"placement_type": "table"}
        bx, by, bz = get_bbox_extractor().extract_bbox(asset)
        assert (bx, by, bz) == _PLACEMENT_TYPE_DIMS["table"]

    def test_placement_type_chair(self):
        asset = {"placement_type": "chair"}
        bx, by, bz = get_bbox_extractor().extract_bbox(asset)
        assert (bx, by, bz) == _PLACEMENT_TYPE_DIMS["chair"]

    def test_placement_type_machine(self):
        bx, by, bz = get_bbox_extractor().extract_bbox({"placement_type": "machine"})
        assert (bx, by, bz) == _PLACEMENT_TYPE_DIMS["machine"]

    def test_category_vehicle(self):
        asset = {"category": "vehicle"}
        bx, by, bz = get_bbox_extractor().extract_bbox(asset)
        assert (bx, by, bz) == _CATEGORY_DIMS["vehicle"]

    def test_category_furniture(self):
        bx, by, bz = get_bbox_extractor().extract_bbox({"category": "furniture"})
        assert (bx, by, bz) == _CATEGORY_DIMS["furniture"]

    def test_fallback_default(self):
        bx, by, bz = get_bbox_extractor().extract_bbox({})
        assert (bx, by, bz) == _DEFAULT_DIMS

    def test_placement_type_takes_priority_over_category(self):
        asset = {"placement_type": "barrel", "category": "vehicle"}
        bx, by, bz = get_bbox_extractor().extract_bbox(asset)
        assert (bx, by, bz) == _PLACEMENT_TYPE_DIMS["barrel"]

    def test_explicit_bbox_takes_priority_over_placement_type(self):
        asset = {"bbox_x": 9.0, "bbox_y": 9.0, "bbox_z": 9.0,
                 "placement_type": "chair"}
        bx, by, bz = get_bbox_extractor().extract_bbox(asset)
        assert (bx, by, bz) == (9.0, 9.0, 9.0)


class TestExtractDimensions:
    def test_dimensions_dict(self):
        asset = {"bbox_x": 2.0, "bbox_y": 1.0, "bbox_z": 1.5}
        dims = get_bbox_extractor().extract_dimensions(asset)
        assert dims["bbox_x"] == 2.0
        assert abs(dims["footprint_area"] - 3.0) < 1e-9
        assert abs(dims["placement_radius"] - 1.0) < 1e-9  # max(2,1.5)/2

    def test_footprint(self):
        fp = get_bbox_extractor().extract_footprint({"bbox_x": 4.0, "bbox_y": 2.0, "bbox_z": 3.0})
        assert abs(fp - 12.0) < 1e-9


class TestBuildSpatialMetadata:
    def test_table_asset(self):
        asset = {"name": "oak_table", "placement_type": "table"}
        meta = get_bbox_extractor().build_spatial_metadata(asset)
        assert isinstance(meta, SpatialMetadata)
        assert abs(meta.bbox_x - 2.2) < 1e-9
        assert meta.placement_type == "table"
        assert meta.anchor_capable is True
        assert meta.walkable_obstacle is True

    def test_chair_asset(self):
        asset = {"name": "wooden_chair", "placement_type": "chair"}
        meta = get_bbox_extractor().build_spatial_metadata(asset)
        assert meta.placement_type == "chair"
        assert meta.anchor_capable is False

    def test_world_scale_applied(self):
        asset = {"placement_type": "machine"}
        meta = get_bbox_extractor().build_spatial_metadata(asset, world_scale=2.0)
        expected_bx = _PLACEMENT_TYPE_DIMS["machine"][0] * 2.0
        assert abs(meta.bbox_x - expected_bx) < 1e-9

    def test_invalid_asset_returns_default(self):
        meta = get_bbox_extractor().build_spatial_metadata(None)
        assert meta.bbox_x == 1.0

    def test_asset_id_from_name(self):
        asset = {"name": "barrel_01", "placement_type": "barrel"}
        meta = get_bbox_extractor().build_spatial_metadata(asset)
        assert meta.asset_id == "barrel_01"

    def test_vehicle_is_walkable_obstacle(self):
        meta = get_bbox_extractor().build_spatial_metadata({"category": "vehicle"})
        assert meta.walkable_obstacle is True

    def test_hdri_has_zero_dims(self):
        bx, by, bz = get_bbox_extractor().extract_bbox({"category": "hdri"})
        assert bx == 0.0 and by == 0.0 and bz == 0.0


class TestSingleton:
    def test_singleton_returns_same_instance(self):
        a = get_bbox_extractor()
        b = get_bbox_extractor()
        assert a is b

    def test_reset_clears_singleton(self):
        a = get_bbox_extractor()
        reset_bbox_extractor_for_tests()
        b = get_bbox_extractor()
        assert a is not b
