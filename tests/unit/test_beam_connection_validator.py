"""Tests for the §54 Beam Rule (Tier 15.0+)."""

import pytest

from src.runtime.reality.beam_connection_validator import (
    get_beam_connection_validator,
    reset_beam_connection_validator_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_beam_connection_validator_for_tests()
    yield
    reset_beam_connection_validator_for_tests()


def _scene(transforms):
    # western_room: walls at x=±5, z=±6
    return {"environment": "western_room", "transforms": transforms}


class TestBeamConnections:
    def test_wall_to_wall_beam_valid(self):
        result = get_beam_connection_validator().validate(_scene([
            {"asset_id": "beam", "asset_name": "Wooden Beam", "tx": 0, "ty": 3.8,
             "tz": 0, "bbox_half_x": 5.0, "bbox_half_y": 0.15, "bbox_half_z": 0.15},
        ]))
        assert result.ok
        assert result.connections[0].span_kind == "wall-to-wall"

    def test_floating_center_beam_invalid(self):
        result = get_beam_connection_validator().validate(_scene([
            {"asset_id": "beam", "asset_name": "Wooden Beam", "tx": 0, "ty": 3.8,
             "tz": 0, "bbox_half_x": 1.5, "bbox_half_y": 0.15, "bbox_half_z": 0.15},
        ]))
        assert not result.ok
        assert result.violations[0].span_kind == "floating"
        assert "does not connect architecture" in result.violations[0].detail

    def test_wall_to_column_beam_valid(self):
        result = get_beam_connection_validator().validate(_scene([
            {"asset_id": "col", "asset_name": "Stone Column", "tx": 0, "ty": 1.5,
             "tz": 0, "bbox_half_x": 0.25, "bbox_half_y": 1.5, "bbox_half_z": 0.25},
            {"asset_id": "beam", "asset_name": "Wooden Beam", "tx": -2.5, "ty": 3.8,
             "tz": 0, "bbox_half_x": 2.5, "bbox_half_y": 0.15, "bbox_half_z": 0.15},
        ]))
        assert result.ok
        assert result.connections[0].span_kind == "column-to-wall"

    def test_column_to_column_beam_valid(self):
        result = get_beam_connection_validator().validate(_scene([
            {"asset_id": "col_a", "asset_name": "Stone Column", "tx": -2.0, "ty": 1.5,
             "tz": 0, "bbox_half_x": 0.25, "bbox_half_y": 1.5, "bbox_half_z": 0.25},
            {"asset_id": "col_b", "asset_name": "Stone Column", "tx": 2.0, "ty": 1.5,
             "tz": 0, "bbox_half_x": 0.25, "bbox_half_y": 1.5, "bbox_half_z": 0.25},
            {"asset_id": "beam", "asset_name": "Wooden Beam", "tx": 0, "ty": 3.8,
             "tz": 0, "bbox_half_x": 2.0, "bbox_half_y": 0.15, "bbox_half_z": 0.15},
        ]))
        assert result.ok
        assert result.connections[0].span_kind == "column-to-column"

    def test_z_axis_beam_via_rotation(self):
        # Beam major axis along Z (half_z > half_x), spanning z=±6
        result = get_beam_connection_validator().validate(_scene([
            {"asset_id": "beam", "asset_name": "Wooden Beam", "tx": 0, "ty": 3.8,
             "tz": 0, "bbox_half_x": 0.15, "bbox_half_y": 0.15, "bbox_half_z": 6.0},
        ]))
        assert result.ok
        assert result.connections[0].span_kind == "wall-to-wall"

    def test_no_beams_is_ok(self):
        result = get_beam_connection_validator().validate(_scene([]))
        assert result.ok
        assert result.beam_count == 0

    def test_canonical_scene_beams_valid(self, western_room_scene):
        result = get_beam_connection_validator().validate(western_room_scene)
        assert result.ok
        assert result.beam_count == 2

    def test_never_raises(self):
        assert get_beam_connection_validator().validate(None).beam_count == 0
