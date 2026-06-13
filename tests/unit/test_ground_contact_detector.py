"""Tests for GroundContactDetector (Tier 9.7)."""
import pytest
from src.runtime.assets.geometry import (
    get_ground_contact_detector,
    reset_ground_contact_detector_for_tests,
    GroundContact,
)


@pytest.fixture(autouse=True)
def reset():
    reset_ground_contact_detector_for_tests()
    yield
    reset_ground_contact_detector_for_tests()


class TestChairAndTable:
    def test_chair_four_legs(self):
        contacts = get_ground_contact_detector().detect(
            {"placement_type": "chair"}, 0.55, 0.90, 0.55
        )
        assert len(contacts) == 1
        c = contacts[0]
        assert c.contact_type == "leg"
        assert c.count == 4
        assert len(c.positions) == 4

    def test_table_four_legs(self):
        contacts = get_ground_contact_detector().detect(
            {"placement_type": "table"}, 1.2, 0.75, 0.8
        )
        assert len(contacts) == 1
        c = contacts[0]
        assert c.contact_type == "leg"
        assert c.count == 4

    def test_desk_four_legs(self):
        contacts = get_ground_contact_detector().detect(
            {"placement_type": "desk"}, 1.4, 0.76, 0.7
        )
        c = contacts[0]
        assert c.contact_type == "leg"
        assert c.count == 4


class TestRingAndPlane:
    def test_bucket_base_ring(self):
        contacts = get_ground_contact_detector().detect(
            {"placement_type": "bucket"}, 0.30, 0.38, 0.30
        )
        c = contacts[0]
        assert c.contact_type == "base_ring"
        assert c.count == 8

    def test_barrel_base_ring(self):
        contacts = get_ground_contact_detector().detect(
            {"placement_type": "barrel"}, 0.55, 0.90, 0.55
        )
        c = contacts[0]
        assert c.contact_type == "base_ring"

    def test_machine_base_plane(self):
        contacts = get_ground_contact_detector().detect(
            {"placement_type": "machine"}, 2.5, 2.0, 2.0
        )
        c = contacts[0]
        assert c.contact_type == "base_plane"
        assert c.count == 1

    def test_crate_base_plane(self):
        contacts = get_ground_contact_detector().detect(
            {"placement_type": "crate"}, 0.8, 0.8, 0.8
        )
        c = contacts[0]
        assert c.contact_type == "base_plane"


class TestVehicle:
    def test_vehicle_wheels(self):
        contacts = get_ground_contact_detector().detect(
            {"placement_type": "vehicle"}, 4.5, 1.8, 2.0
        )
        c = contacts[0]
        assert c.contact_type == "wheel"
        assert c.count == 4


class TestHangingAssets:
    def test_hanging_light_no_contact(self):
        contacts = get_ground_contact_detector().detect(
            {"placement_type": "hanging_light"}, 0.3, 0.5, 0.3
        )
        assert contacts == []

    def test_pendant_light_no_contact(self):
        contacts = get_ground_contact_detector().detect(
            {"placement_type": "pendant_light"}, 0.2, 0.4, 0.2
        )
        assert contacts == []


class TestCategoryFallback:
    def test_furniture_category_four_legs(self):
        contacts = get_ground_contact_detector().detect(
            {"category": "furniture"}, 1.0, 0.9, 0.7
        )
        c = contacts[0]
        assert c.contact_type == "leg"
        assert c.count == 4

    def test_vehicle_category_wheels(self):
        contacts = get_ground_contact_detector().detect(
            {"category": "vehicle"}, 4.5, 1.8, 2.0
        )
        c = contacts[0]
        assert c.contact_type == "wheel"

    def test_structure_category_base_plane(self):
        contacts = get_ground_contact_detector().detect(
            {"category": "structure"}, 5.0, 3.0, 0.3
        )
        c = contacts[0]
        assert c.contact_type == "base_plane"


class TestExplicitContacts:
    def test_explicit_contacts_field_used(self):
        asset = {
            "placement_type": "chair",
            "ground_contacts": [
                {"contact_type": "spike", "count": 3, "positions": [[0, 0, 0.2], [-0.1, 0, -0.1], [0.1, 0, -0.1]], "description": "Tripod"}
            ]
        }
        contacts = get_ground_contact_detector().detect(asset, 0.4, 0.9, 0.4)
        assert len(contacts) == 1
        assert contacts[0].contact_type == "spike"
        assert contacts[0].count == 3


class TestReturnTypes:
    def test_returns_list_of_ground_contact(self):
        contacts = get_ground_contact_detector().detect(
            {"placement_type": "table"}, 1.2, 0.75, 0.8
        )
        assert all(isinstance(c, GroundContact) for c in contacts)

    def test_to_dict_round_trip(self):
        contacts = get_ground_contact_detector().detect(
            {"placement_type": "chair"}, 0.55, 0.90, 0.55
        )
        for c in contacts:
            d = c.to_dict()
            c2 = GroundContact.from_dict(d)
            assert c2.contact_type == c.contact_type
            assert c2.count == c.count

    def test_no_raise_on_none(self):
        contacts = get_ground_contact_detector().detect(None, 1.0, 1.0, 1.0)  # type: ignore
        assert isinstance(contacts, list)
