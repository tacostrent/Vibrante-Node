"""Tests for ClearanceValidator (Tier 9.4)."""

import math
import pytest
from src.runtime.assets.assembly.clearance_validator import (
    get_clearance_validator,
    reset_clearance_validator_for_tests,
    _DEFAULT_CLEARANCE,
    _CLEARANCE_RULES,
)
from src.runtime.assets.assembly.spatial_metadata import SpatialMetadata


def _meta(asset_id="x", bx=1.0, by=1.0, bz=1.0, pt="unknown") -> SpatialMetadata:
    return SpatialMetadata(
        asset_id=asset_id,
        bbox_x=bx, bbox_y=by, bbox_z=bz,
        footprint_area=bx * bz,
        placement_radius=max(bx, bz) / 2.0,
        placement_type=pt,
    )


@pytest.fixture(autouse=True)
def reset():
    reset_clearance_validator_for_tests()
    yield
    reset_clearance_validator_for_tests()


class TestGetClearanceRequirement:
    def test_chair_chair(self):
        req = get_clearance_validator().get_clearance_requirement("chair", "chair")
        assert req == 0.4

    def test_machine_machine(self):
        req = get_clearance_validator().get_clearance_requirement("machine", "machine")
        assert req == 2.0

    def test_vehicle_vehicle(self):
        req = get_clearance_validator().get_clearance_requirement("vehicle", "vehicle")
        assert req == 2.5

    def test_machine_wall(self):
        req = get_clearance_validator().get_clearance_requirement("machine", "wall")
        assert req == 1.0

    def test_wall_machine_order_insensitive(self):
        req = get_clearance_validator().get_clearance_requirement("wall", "machine")
        assert req == 1.0

    def test_unknown_pair_default(self):
        req = get_clearance_validator().get_clearance_requirement("lantern", "bucket")
        assert req == _DEFAULT_CLEARANCE


class TestValidateClearance:
    def test_sufficient_clearance(self):
        m_machine = _meta(bx=2.5, bz=2.5, pt="machine")
        m_machine.placement_radius = 1.25
        # Two machines: center distance = 10m, radii sum = 2.5m
        # edge-to-edge = 10 - 2.5 = 7.5m, required = 2.0m → OK
        result = get_clearance_validator().validate_clearance(
            (0.0, 0.0, 0.0), m_machine,
            (10.0, 0.0, 0.0), m_machine,
        )
        assert result["ok"] is True

    def test_insufficient_clearance_machines(self):
        m = _meta(bx=2.5, bz=2.5, pt="machine")
        m.placement_radius = 1.25
        # center distance = 3m, edge-to-edge = 3 - 2.5 = 0.5m, required = 2.0m
        result = get_clearance_validator().validate_clearance(
            (0.0, 0.0, 0.0), m,
            (3.0, 0.0, 0.0), m,
        )
        assert result["ok"] is False
        assert result["shortfall"] > 0.0

    def test_chairs_too_close(self):
        chair = _meta(bx=0.6, bz=0.6, pt="chair")
        # center dist = 0.4m, radii sum = 0.6m, edge-to-edge = -0.2m < 0.4m
        result = get_clearance_validator().validate_clearance(
            (0.0, 0.0, 0.0), chair,
            (0.4, 0.0, 0.0), chair,
        )
        assert result["ok"] is False

    def test_above_required_clearance(self):
        # Two chairs: edge-to-edge = 1.0m > required 0.4m → OK
        chair = _meta(bx=0.6, bz=0.6, pt="chair")
        chair.placement_radius = 0.3
        # dist=2.0, edge-to-edge = 2.0 - 0.3 - 0.3 = 1.4m > 0.4m
        result = get_clearance_validator().validate_clearance(
            (0.0, 0.0, 0.0), chair,
            (2.0, 0.0, 0.0), chair,
        )
        assert result["ok"] is True


class TestValidateSceneClearance:
    def test_empty_scene(self):
        report = get_clearance_validator().validate_scene_clearance([])
        assert report.ok is True
        assert report.violation_count == 0

    def test_single_asset(self):
        report = get_clearance_validator().validate_scene_clearance([
            ("a", (0.0, 0.0, 0.0), _meta())
        ])
        assert report.ok is True

    def test_machines_too_close(self):
        m = _meta(asset_id="m1", bx=2.5, bz=2.5, pt="machine")
        m.placement_radius = 1.25
        m2 = _meta(asset_id="m2", bx=2.5, bz=2.5, pt="machine")
        m2.placement_radius = 1.25
        report = get_clearance_validator().validate_scene_clearance([
            ("machine_01", (0.0, 0.0, 0.0), m),
            ("machine_02", (3.0, 0.0, 0.0), m2),
        ])
        assert report.ok is False
        assert report.violation_count == 1
        v = report.violations[0]
        assert v.type_a == "machine" and v.type_b == "machine"

    def test_well_spaced_machines_ok(self):
        m = _meta(bx=2.5, bz=2.5, pt="machine")
        m.placement_radius = 1.25
        report = get_clearance_validator().validate_scene_clearance([
            ("m1", (0.0, 0.0, 0.0), m),
            ("m2", (8.0, 0.0, 0.0), m),
        ])
        assert report.ok is True

    def test_clearance_report_serializable(self):
        m = _meta(bx=2.5, bz=2.5, pt="machine")
        m.placement_radius = 1.25
        report = get_clearance_validator().validate_scene_clearance([
            ("m1", (0.0, 0.0, 0.0), m),
            ("m2", (2.0, 0.0, 0.0), m),
        ])
        d = report.to_dict()
        assert "violations" in d
        assert isinstance(d["violations"], list)

    def test_vehicle_wall_clearance(self):
        vehicle = _meta(asset_id="truck", bx=4.5, bz=2.2, pt="vehicle")
        vehicle.placement_radius = 2.25
        wall = _meta(asset_id="wall_01", bx=4.0, bz=0.3, pt="wall")
        wall.placement_radius = 2.0
        # distance = 2.0m, edge-to-edge = 2.0 - 2.25 - 2.0 = -2.25m < 1.0m required
        report = get_clearance_validator().validate_scene_clearance([
            ("truck", (0.0, 0.0, 0.0), vehicle),
            ("wall",  (2.0, 0.0, 0.0), wall),
        ])
        assert report.ok is False
