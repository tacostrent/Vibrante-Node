"""Tests for the §54 Functional Zone System (Tier 15.0+)."""

import pytest

from src.runtime.reality.functional_zone_builder import (
    ZONE_DEFINITIONS,
    get_functional_zone_builder,
    reset_functional_zone_builder_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_functional_zone_builder_for_tests()
    yield
    reset_functional_zone_builder_for_tests()


class TestZoneDefinitions:
    def test_spec_zones_exist(self):
        for zone in ("dining", "fireplace", "storage", "sleeping", "work", "bar"):
            assert zone in ZONE_DEFINITIONS

    def test_dining_zone_members(self):
        members = ZONE_DEFINITIONS["dining"]["members"]
        for m in ("chair", "cup", "bottle", "plate"):
            assert m in members


class TestZoneBuilding:
    def test_canonical_scene_zones(self, western_room_scene):
        plan = get_functional_zone_builder().build_zones(western_room_scene)
        zone_types = {z.zone_type for z in plan.zones}
        assert "dining" in zone_types
        assert "fireplace" in zone_types
        assert "storage" in zone_types
        assert "structure" in zone_types
        assert "wall_decor" in zone_types

    def test_canonical_scene_has_no_orphans(self, western_room_scene):
        plan = get_functional_zone_builder().build_zones(western_room_scene)
        assert plan.no_orphans, plan.orphans
        assert plan.assigned_count == 19

    def test_chairs_assigned_to_nearest_zone(self, western_room_scene):
        plan = get_functional_zone_builder().build_zones(western_room_scene)
        dining = [z for z in plan.zones if z.zone_type == "dining"][0]
        fireplace = [z for z in plan.zones if z.zone_type == "fireplace"][0]
        assert "chair_01" in dining.member_ids
        assert "chair_05" in fireplace.member_ids

    def test_isolated_unknown_asset_is_orphan(self):
        plan = get_functional_zone_builder().build_zones({
            "environment": "western_room",
            "transforms": [
                {"asset_id": "t", "asset_name": "Table", "tx": 0, "ty": 0.375, "tz": 0,
                 "bbox_half_x": 1.1, "bbox_half_y": 0.375, "bbox_half_z": 0.65},
                {"asset_id": "x", "asset_name": "Mystery Prop", "tx": 4.0, "ty": 0.2,
                 "tz": -4.0, "bbox_half_x": 0.2, "bbox_half_y": 0.2, "bbox_half_z": 0.2},
            ],
        })
        assert not plan.no_orphans
        assert plan.orphans[0]["asset_id"] == "x"
        assert "no orphan assets allowed" in plan.orphans[0]["detail"]

    def test_storage_anchors_cluster_into_one_zone(self):
        plan = get_functional_zone_builder().build_zones({
            "environment": "western_room",
            "transforms": [
                {"asset_id": "c1", "asset_name": "Wooden Crate", "tx": 4.3, "ty": 0.4,
                 "tz": 5.3, "bbox_half_x": 0.4, "bbox_half_y": 0.4, "bbox_half_z": 0.4},
                {"asset_id": "b1", "asset_name": "Oak Barrel", "tx": 3.4, "ty": 0.45,
                 "tz": 5.2, "bbox_half_x": 0.3, "bbox_half_y": 0.45, "bbox_half_z": 0.3},
            ],
        })
        storage_zones = [z for z in plan.zones if z.zone_type == "storage"]
        assert len(storage_zones) == 1
        assert "b1" in storage_zones[0].member_ids

    def test_empty_scene_has_no_zones_and_no_orphans(self):
        plan = get_functional_zone_builder().build_zones(
            {"environment": "western_room", "transforms": []})
        assert plan.zones == []
        assert plan.no_orphans

    def test_deterministic(self, western_room_scene):
        p1 = get_functional_zone_builder().build_zones(western_room_scene).to_dict()
        p2 = get_functional_zone_builder().build_zones(western_room_scene).to_dict()
        assert p1 == p2

    def test_never_raises(self):
        plan = get_functional_zone_builder().build_zones(None)
        assert plan.zones == []
