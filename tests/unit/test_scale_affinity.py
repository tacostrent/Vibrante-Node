"""Tests for ScaleAffinity — §45 Semantic Asset Suitability Ranking."""

import pytest
from src.runtime.assets.suitability.scale_affinity import (
    get_scale_affinity,
    reset_scale_affinity_for_tests,
)

MEDIUM_CHAIR = {"name": "Chair", "scale_class": "medium"}
TINY_CUP = {"name": "Cup", "scale_class": "tiny"}
STRUCTURAL_BEAM = {"name": "Beam", "scale_class": "structural"}
HERO_MACHINE = {"name": "Machine", "scale_class": "hero"}
SMALL_LANTERN = {"name": "Lantern", "scale_class": "small"}
NO_SCALE_ASSET = {"name": "Unknown Asset"}


@pytest.fixture(autouse=True)
def reset():
    reset_scale_affinity_for_tests()
    yield
    reset_scale_affinity_for_tests()


class TestExactScaleMatch:
    def test_medium_chair_perfect_for_chair_role(self):
        sa = get_scale_affinity()
        assert sa.score(MEDIUM_CHAIR, "chair") == 1.0

    def test_small_lantern_perfect_for_lantern_role(self):
        sa = get_scale_affinity()
        assert sa.score(SMALL_LANTERN, "lantern") == 1.0

    def test_tiny_cup_perfect_for_cup_role(self):
        sa = get_scale_affinity()
        assert sa.score(TINY_CUP, "cup") == 1.0


class TestMismatchedScale:
    def test_structural_beam_bad_for_chair(self):
        sa = get_scale_affinity()
        score = sa.score(STRUCTURAL_BEAM, "chair")
        assert score < 0.10

    def test_tiny_cup_bad_for_machine_role(self):
        sa = get_scale_affinity()
        score = sa.score(TINY_CUP, "machine")
        assert score < 0.30

    def test_hero_machine_perfect_for_machine_role(self):
        sa = get_scale_affinity()
        assert sa.score(HERO_MACHINE, "machine") == 1.0


class TestOrdering:
    def test_medium_chair_beats_structural_for_chair(self):
        sa = get_scale_affinity()
        assert sa.score(MEDIUM_CHAIR, "chair") > sa.score(STRUCTURAL_BEAM, "chair")


class TestNoScaleInfo:
    def test_no_scale_returns_neutral(self):
        sa = get_scale_affinity()
        assert sa.score(NO_SCALE_ASSET, "chair") == 0.5

    def test_no_role_returns_neutral(self):
        sa = get_scale_affinity()
        assert sa.score(MEDIUM_CHAIR, "") == 0.5


class TestExpectedScaleHelper:
    def test_chair_expected_medium(self):
        sa = get_scale_affinity()
        assert sa.expected_scale_for_role("chair") == "medium"

    def test_lantern_expected_small(self):
        sa = get_scale_affinity()
        assert sa.expected_scale_for_role("lantern") == "small"

    def test_machine_expected_hero(self):
        sa = get_scale_affinity()
        assert sa.expected_scale_for_role("machine") == "hero"

    def test_unknown_role_empty_string(self):
        sa = get_scale_affinity()
        assert sa.expected_scale_for_role("nonexistent") == ""


class TestExplicitExpectedScale:
    def test_explicit_medium_overrides_role(self):
        sa = get_scale_affinity()
        score = sa.score(MEDIUM_CHAIR, role="", expected_scale="medium")
        assert score == 1.0

    def test_explicit_structural_rejects_medium(self):
        sa = get_scale_affinity()
        score = sa.score(MEDIUM_CHAIR, role="", expected_scale="structural")
        assert score < 0.10
