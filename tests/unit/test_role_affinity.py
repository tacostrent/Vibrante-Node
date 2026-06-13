"""Tests for RoleAffinity — §45 Semantic Asset Suitability Ranking."""

import pytest
from src.runtime.assets.suitability.role_affinity import (
    get_role_affinity,
    reset_role_affinity_for_tests,
)

WOODEN_CHAIR = {
    "name": "Wooden Saloon Chair",
    "type": "chair",
    "placement_type": "chair",
    "tags": ["wooden", "saloon", "chair"],
}

OIL_LANTERN = {
    "name": "Oil Lantern",
    "type": "lantern",
    "placement_type": "lantern",
    "tags": ["oil", "lantern", "wall_lantern"],
}

WANTED_POSTER = {
    "name": "Wanted Poster",
    "type": "poster",
    "placement_type": "poster",
    "tags": ["poster", "paper", "sign"],
}

BOTTLE = {
    "name": "Whiskey Bottle",
    "type": "bottle",
    "placement_type": "bottle",
    "tags": ["bottle", "glass"],
}

SHELF = {
    "name": "Wooden Shelf",
    "type": "shelf",
    "placement_type": "shelf",
    "tags": ["shelf", "wooden"],
}

BEAM = {
    "name": "Wooden Beam",
    "type": "beam",
    "placement_type": "beam",
    "tags": ["beam", "structural", "wood"],
}


@pytest.fixture(autouse=True)
def reset():
    reset_role_affinity_for_tests()
    yield
    reset_role_affinity_for_tests()


class TestExactMatch:
    def test_chair_gets_full_score_for_chair_role(self):
        ra = get_role_affinity()
        assert ra.score(WOODEN_CHAIR, "chair") == 1.0

    def test_lantern_gets_full_score_for_lantern_role(self):
        ra = get_role_affinity()
        assert ra.score(OIL_LANTERN, "lantern") == 1.0

    def test_poster_gets_full_score_for_poster_role(self):
        ra = get_role_affinity()
        assert ra.score(WANTED_POSTER, "poster") == 1.0

    def test_bottle_gets_full_score_for_bottle_role(self):
        ra = get_role_affinity()
        assert ra.score(BOTTLE, "bottle") == 1.0


class TestRejectedTypes:
    def test_bottle_rejected_for_lantern_role(self):
        ra = get_role_affinity()
        score = ra.score(BOTTLE, "lantern")
        assert score < 0.50

    def test_shelf_rejected_for_chair_role(self):
        ra = get_role_affinity()
        score = ra.score(SHELF, "chair")
        assert score < 0.50

    def test_beam_rejected_for_poster_role(self):
        ra = get_role_affinity()
        score = ra.score(BEAM, "poster")
        assert score < 0.50


class TestCorrectOrdering:
    def test_chair_beats_beam_for_chair_role(self):
        ra = get_role_affinity()
        assert ra.score(WOODEN_CHAIR, "chair") > ra.score(BEAM, "chair")

    def test_lantern_beats_bottle_for_lantern_role(self):
        ra = get_role_affinity()
        assert ra.score(OIL_LANTERN, "lantern") > ra.score(BOTTLE, "lantern")

    def test_poster_beats_shelf_for_poster_role(self):
        ra = get_role_affinity()
        assert ra.score(WANTED_POSTER, "poster") > ra.score(SHELF, "poster")


class TestEmptyRole:
    def test_empty_role_returns_neutral(self):
        ra = get_role_affinity()
        assert ra.score(WOODEN_CHAIR, "") == 0.5


class TestAccessors:
    def test_get_exact_returns_list(self):
        ra = get_role_affinity()
        assert "chair" in ra.get_exact("chair")

    def test_known_roles_contains_common_roles(self):
        ra = get_role_affinity()
        roles = ra.known_roles()
        for r in ("chair", "table", "barrel", "lantern", "poster"):
            assert r in roles


class TestAllRolesNoRaise:
    def test_no_exception_on_any_known_role(self):
        ra = get_role_affinity()
        for role in ra.known_roles():
            s = ra.score(WOODEN_CHAIR, role)
            assert 0.0 <= s <= 1.0
