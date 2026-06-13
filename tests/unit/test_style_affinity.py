"""Tests for StyleAffinity — §45 Semantic Asset Suitability Ranking."""

import pytest
from src.runtime.assets.suitability.style_affinity import (
    get_style_affinity,
    reset_style_affinity_for_tests,
)

RUSTIC_CHAIR = {
    "name": "Weathered Rustic Chair",
    "tags": ["weathered", "rustic", "aged", "distressed"],
    "style_tags": ["weathered", "rustic", "antique"],
}

POLISHED_CHAIR = {
    "name": "Polished Modern Chair",
    "tags": ["polished", "modern", "sleek", "pristine"],
    "style_tags": ["modern", "polished", "minimal"],
}

STERILE_EQUIPMENT = {
    "name": "Sterile Lab Equipment",
    "tags": ["sterile", "clinical", "pristine", "clean"],
    "style_tags": ["sterile", "clinical"],
}


@pytest.fixture(autouse=True)
def reset():
    reset_style_affinity_for_tests()
    yield
    reset_style_affinity_for_tests()


class TestWesternRoom:
    def test_rustic_chair_scores_high_for_western(self):
        sa = get_style_affinity()
        assert sa.score(RUSTIC_CHAIR, "western_room") >= 0.70

    def test_polished_chair_scores_lower_for_western(self):
        sa = get_style_affinity()
        s_rustic = sa.score(RUSTIC_CHAIR, "western_room")
        s_polished = sa.score(POLISHED_CHAIR, "western_room")
        assert s_rustic > s_polished

    def test_polished_chair_penalised_for_western(self):
        sa = get_style_affinity()
        assert sa.score(POLISHED_CHAIR, "western_room") < 0.50


class TestMedicalLab:
    def test_sterile_equipment_scores_high_for_medical(self):
        sa = get_style_affinity()
        assert sa.score(STERILE_EQUIPMENT, "medical_lab") >= 0.70

    def test_rustic_chair_penalised_for_medical(self):
        sa = get_style_affinity()
        score = sa.score(RUSTIC_CHAIR, "medical_lab")
        assert score < 0.50


class TestNeutral:
    def test_empty_asset_returns_0_5(self):
        sa = get_style_affinity()
        assert sa.score({}, "western_room") == 0.5

    def test_unknown_environment_safe(self):
        sa = get_style_affinity()
        s = sa.score(RUSTIC_CHAIR, "unknown_env")
        assert 0.0 <= s <= 1.0


class TestAccessors:
    def test_get_preferred_styles_returns_list(self):
        sa = get_style_affinity()
        prefs = sa.get_preferred_styles("western_room")
        assert "weathered" in prefs

    def test_get_rejected_styles_returns_list(self):
        sa = get_style_affinity()
        rejs = sa.get_rejected_styles("western_room")
        assert "futuristic" in rejs


class TestAllEnvironmentsNoRaise:
    def test_all_environments_safe(self):
        sa = get_style_affinity()
        for env in (
            "western_room", "industrial_hangar", "medical_lab",
            "sci_fi_corridor", "forest", "castle_hall"
        ):
            s = sa.score(RUSTIC_CHAIR, env)
            assert 0.0 <= s <= 1.0
