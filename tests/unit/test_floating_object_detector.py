"""Tests for the §54 No Floating Objects Rule (Tier 15.0+)."""

import pytest

from src.runtime.reality.floating_object_detector import (
    get_floating_object_detector,
    reset_floating_object_detector_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_floating_object_detector_for_tests()
    yield
    reset_floating_object_detector_for_tests()


def _scene(transforms):
    return {"environment": "western_room", "transforms": transforms}


class TestFloatingDetection:
    def test_floating_crate_fails_with_relocation(self):
        result = get_floating_object_detector().detect(_scene([
            {"asset_id": "c", "asset_name": "Wooden Crate", "tx": 2.0, "ty": 2.0,
             "tz": 2.0, "bbox_half_x": 0.4, "bbox_half_y": 0.4, "bbox_half_z": 0.4},
        ]))
        assert not result.ok
        v = result.violations[0]
        assert v.asset_id == "c"
        assert v.severity == "BLOCKING"
        # Relocate onto the floor: ty = floor + half_y
        assert v.suggested_ty == pytest.approx(0.4)

    def test_bottle_on_table_passes_raycast(self):
        result = get_floating_object_detector().detect(_scene([
            {"asset_id": "t", "asset_name": "Table", "tx": 0, "ty": 0.375, "tz": 0,
             "bbox_half_x": 1.1, "bbox_half_y": 0.375, "bbox_half_z": 0.65},
            {"asset_id": "b", "asset_name": "Whiskey Bottle", "tx": 0.3, "ty": 0.90,
             "tz": 0.2, "bbox_half_x": 0.05, "bbox_half_y": 0.15, "bbox_half_z": 0.05},
        ]))
        assert result.ok
        assert result.supported == 2

    def test_floating_bottle_relocates_to_table_top(self):
        result = get_floating_object_detector().detect(_scene([
            {"asset_id": "t", "asset_name": "Table", "tx": 0, "ty": 0.375, "tz": 0,
             "bbox_half_x": 1.1, "bbox_half_y": 0.375, "bbox_half_z": 0.65},
            {"asset_id": "b", "asset_name": "Whiskey Bottle", "tx": 0.3, "ty": 2.5,
             "tz": 0.2, "bbox_half_x": 0.05, "bbox_half_y": 0.15, "bbox_half_z": 0.05},
        ]))
        assert not result.ok
        v = result.violations[0]
        # Drop onto the table surface: 0.75 + 0.15
        assert v.suggested_ty == pytest.approx(0.90)
        assert v.support_id == "t"

    def test_wall_mounted_poster_exempt(self):
        result = get_floating_object_detector().detect(_scene([
            {"asset_id": "p", "asset_name": "Wanted Poster", "tx": -4.97, "ty": 1.6,
             "tz": 2.0, "bbox_half_x": 0.02, "bbox_half_y": 0.5, "bbox_half_z": 0.4},
        ]))
        assert result.ok
        assert result.exempt == 1

    def test_structural_beam_exempt(self):
        result = get_floating_object_detector().detect(_scene([
            {"asset_id": "beam", "asset_name": "Wooden Beam", "tx": 0, "ty": 3.8,
             "tz": 0, "bbox_half_x": 5.0, "bbox_half_y": 0.15, "bbox_half_z": 0.15},
        ]))
        assert result.ok
        assert result.exempt == 1

    def test_on_floor_asset_passes(self):
        result = get_floating_object_detector().detect(_scene([
            {"asset_id": "c", "asset_name": "Wooden Chair", "tx": 0, "ty": 0.45,
             "tz": 0, "bbox_half_x": 0.25, "bbox_half_y": 0.45, "bbox_half_z": 0.25},
        ]))
        assert result.ok

    def test_canonical_scene_has_no_floating_objects(self, western_room_scene):
        result = get_floating_object_detector().detect(western_room_scene)
        assert result.ok, [v.detail for v in result.violations]

    def test_deterministic(self, western_room_scene):
        d1 = get_floating_object_detector().detect(western_room_scene).to_dict()
        d2 = get_floating_object_detector().detect(western_room_scene).to_dict()
        assert d1 == d2

    def test_never_raises(self):
        assert get_floating_object_detector().detect(None).checked == 0
