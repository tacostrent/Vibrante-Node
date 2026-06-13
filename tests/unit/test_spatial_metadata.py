"""Tests for SpatialMetadata (Tier 9.4)."""

import pytest
from src.runtime.assets.assembly.spatial_metadata import (
    SpatialMetadata, PLACEMENT_TYPES, UNIT_SYSTEMS, _UNIT_TO_METERS,
)


class TestSpatialMetadataDefaults:
    def test_default_fields(self):
        m = SpatialMetadata()
        assert m.asset_id == ""
        assert m.bbox_x == 1.0
        assert m.bbox_y == 1.0
        assert m.bbox_z == 1.0
        assert m.footprint_area == 1.0
        assert m.placement_radius == 0.5
        assert m.world_scale == 1.0
        assert m.unit_system == "meters"
        assert m.placement_type == "unknown"
        assert m.anchor_capable is False
        assert m.walkable_obstacle is True

    def test_custom_fields(self):
        m = SpatialMetadata(
            asset_id="table_01",
            bbox_x=2.2, bbox_y=0.8, bbox_z=1.3,
            placement_type="table",
            anchor_capable=True,
        )
        assert m.asset_id == "table_01"
        assert m.bbox_x == 2.2
        assert m.bbox_y == 0.8
        assert m.bbox_z == 1.3
        assert m.placement_type == "table"
        assert m.anchor_capable is True


class TestSpatialMetadataSerialization:
    def test_round_trip(self):
        m = SpatialMetadata(
            asset_id="chair_02",
            bbox_x=0.6, bbox_y=1.0, bbox_z=0.6,
            footprint_area=0.36,
            placement_radius=0.3,
            placement_type="chair",
            anchor_capable=False,
            walkable_obstacle=True,
        )
        d = m.to_dict()
        m2 = SpatialMetadata.from_dict(d)
        assert m2.asset_id == m.asset_id
        assert m2.bbox_x == m.bbox_x
        assert m2.placement_type == m.placement_type

    def test_from_dict_defaults(self):
        m = SpatialMetadata.from_dict({})
        assert m.bbox_x == 1.0
        assert m.unit_system == "meters"


class TestSpatialMetadataNormalization:
    def test_meters_to_centimeters(self):
        m = SpatialMetadata(asset_id="a", bbox_x=2.0, bbox_y=1.0, bbox_z=1.5,
                            footprint_area=3.0, placement_radius=1.0,
                            unit_system="meters")
        m_cm = m.normalized_to("centimeters")
        assert m_cm.unit_system == "centimeters"
        assert abs(m_cm.bbox_x - 200.0) < 1e-6

    def test_centimeters_to_meters(self):
        m = SpatialMetadata(asset_id="b", bbox_x=100.0, bbox_y=50.0, bbox_z=60.0,
                            unit_system="centimeters")
        m_m = m.normalized_to("meters")
        assert abs(m_m.bbox_x - 1.0) < 1e-6

    def test_same_unit_no_change(self):
        m = SpatialMetadata(bbox_x=2.0, unit_system="meters")
        m2 = m.normalized_to("meters")
        assert m2.bbox_x == 2.0

    def test_unknown_target_defaults_to_meters(self):
        m = SpatialMetadata(bbox_x=2.0, unit_system="meters")
        m2 = m.normalized_to("parsecs")
        assert m2.unit_system == "meters"

    def test_footprint_recomputed_after_normalization(self):
        m = SpatialMetadata(bbox_x=2.0, bbox_z=1.0, unit_system="meters")
        m_cm = m.normalized_to("centimeters")
        assert abs(m_cm.footprint_area - 200.0 * 100.0) < 1e-4

    def test_placement_radius_recomputed(self):
        m = SpatialMetadata(bbox_x=4.0, bbox_z=2.0, unit_system="meters")
        m_cm = m.normalized_to("centimeters")
        # max(400, 200) / 2 = 200 cm
        assert abs(m_cm.placement_radius - 200.0) < 1e-4

    def test_feet_to_meters(self):
        m = SpatialMetadata(bbox_x=10.0, unit_system="feet")
        m_m = m.normalized_to("meters")
        assert abs(m_m.bbox_x - 3.048) < 1e-6


class TestPlacementTypeConstants:
    def test_known_types_present(self):
        for t in ("table", "chair", "machine", "vehicle", "terrain", "unknown"):
            assert t in PLACEMENT_TYPES

    def test_unit_systems_present(self):
        for u in ("meters", "centimeters", "millimeters", "inches", "feet"):
            assert u in UNIT_SYSTEMS

    def test_unit_to_meters_factors(self):
        assert _UNIT_TO_METERS["meters"] == 1.0
        assert abs(_UNIT_TO_METERS["feet"] - 0.3048) < 1e-10
        assert abs(_UNIT_TO_METERS["inches"] - 0.0254) < 1e-10
