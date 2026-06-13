"""Tests for the §54 Architectural Integrity Rule (Tier 15.0+)."""

import pytest

from src.runtime.reality.architectural_integrity_validator import (
    get_architectural_integrity_validator,
    reset_architectural_integrity_validator_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_architectural_integrity_validator_for_tests()
    yield
    reset_architectural_integrity_validator_for_tests()


def _scene(transforms, **extra):
    d = {"environment": "western_room", "transforms": transforms}
    d.update(extra)
    return d


class TestArchitecturalIntegrity:
    def test_fake_door_mid_room_rejected(self):
        result = get_architectural_integrity_validator().validate(_scene([
            {"asset_id": "d", "asset_name": "Swing Door", "tx": 0, "ty": 1.05,
             "tz": 0, "bbox_half_x": 0.5, "bbox_half_y": 1.05, "bbox_half_z": 0.06},
        ]))
        assert not result.architecturally_valid
        v = result.violations[0]
        assert v.violation_code == "FAKE_DOOR"
        assert "decorative fake" in v.detail

    def test_door_in_wall_plane_valid(self):
        result = get_architectural_integrity_validator().validate(_scene([
            {"asset_id": "d", "asset_name": "Swing Door", "tx": 0, "ty": 1.05,
             "tz": 5.97, "bbox_half_x": 0.5, "bbox_half_y": 1.05, "bbox_half_z": 0.06},
        ]))
        assert result.architecturally_valid

    def test_window_must_match_declared_opening(self):
        # Openings declared but none near the window → MISSING_WINDOW_OPENING
        result = get_architectural_integrity_validator().validate(_scene(
            [{"asset_id": "w", "asset_name": "Window", "tx": 4.98, "ty": 1.5,
              "tz": -2.0, "bbox_half_x": 0.05, "bbox_half_y": 0.6, "bbox_half_z": 0.5}],
            openings=[{"kind": "window", "tx": 0.0, "tz": 5.97}],
        ))
        assert not result.architecturally_valid
        assert result.violations[0].violation_code == "MISSING_WINDOW_OPENING"

    def test_window_matching_opening_valid(self):
        result = get_architectural_integrity_validator().validate(_scene(
            [{"asset_id": "w", "asset_name": "Window", "tx": 4.98, "ty": 1.5,
              "tz": -2.0, "bbox_half_x": 0.05, "bbox_half_y": 0.6, "bbox_half_z": 0.5}],
            openings=[{"kind": "window", "tx": 4.98, "tz": -2.0}],
        ))
        assert result.architecturally_valid

    def test_fireplace_off_wall_rejected(self):
        result = get_architectural_integrity_validator().validate(_scene([
            {"asset_id": "f", "asset_name": "Stone Fireplace", "tx": 0, "ty": 1.0,
             "tz": 0, "bbox_half_x": 0.9, "bbox_half_y": 1.0, "bbox_half_z": 0.35},
        ]))
        assert not result.architecturally_valid
        assert result.violations[0].violation_code == "FIREPLACE_OFF_WALL"

    def test_asset_through_perimeter_rejected(self):
        result = get_architectural_integrity_validator().validate(_scene([
            {"asset_id": "c", "asset_name": "Wooden Crate", "tx": 5.2, "ty": 0.4,
             "tz": 0, "bbox_half_x": 0.4, "bbox_half_y": 0.4, "bbox_half_z": 0.4},
        ]))
        assert not result.architecturally_valid
        assert result.violations[0].violation_code == "WALL_INTERSECTION"

    def test_canonical_scene_valid(self, western_room_scene):
        result = get_architectural_integrity_validator().validate(western_room_scene)
        assert result.architecturally_valid, [v.detail for v in result.violations]
        assert result.door_count == 1
        assert result.window_count == 1

    def test_never_raises(self):
        result = get_architectural_integrity_validator().validate(None)
        assert result.door_count == 0
