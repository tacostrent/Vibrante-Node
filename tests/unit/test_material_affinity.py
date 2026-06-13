"""Tests for MaterialAffinity — §45 Semantic Asset Suitability Ranking."""

import pytest
from src.runtime.assets.suitability.material_affinity import (
    get_material_affinity,
    reset_material_affinity_for_tests,
)

WOODEN_ASSET = {
    "name": "Wooden Barrel",
    "tags": ["wood", "wooden"],
    "material_tags": ["wood", "iron"],
}

CHROME_ASSET = {
    "name": "Chrome Robot Part",
    "tags": ["chrome", "plastic", "electronic"],
    "material_tags": ["chrome", "carbon fiber"],
}

STEEL_ASSET = {
    "name": "Steel Machine",
    "tags": ["steel", "iron", "metal"],
    "material_tags": ["steel", "metal"],
}


@pytest.fixture(autouse=True)
def reset():
    reset_material_affinity_for_tests()
    yield
    reset_material_affinity_for_tests()


class TestWesternRoom:
    def test_wood_scores_high_for_western(self):
        ma = get_material_affinity()
        assert ma.score(WOODEN_ASSET, "western_room") >= 0.60

    def test_chrome_penalised_for_western(self):
        ma = get_material_affinity()
        score = ma.score(CHROME_ASSET, "western_room")
        assert score < 0.50

    def test_wood_beats_chrome_for_western(self):
        ma = get_material_affinity()
        assert ma.score(WOODEN_ASSET, "western_room") > ma.score(CHROME_ASSET, "western_room")


class TestIndustrialHangar:
    def test_steel_scores_high_for_industrial(self):
        ma = get_material_affinity()
        assert ma.score(STEEL_ASSET, "industrial_hangar") >= 0.60

    def test_chrome_not_rejected_for_industrial(self):
        ma = get_material_affinity()
        s = ma.score(CHROME_ASSET, "industrial_hangar")
        assert 0.0 <= s <= 1.0


class TestRoboticsLab:
    def test_chrome_scores_high_for_robotics(self):
        ma = get_material_affinity()
        assert ma.score(CHROME_ASSET, "robotics_lab") >= 0.60

    def test_wood_penalised_for_robotics(self):
        ma = get_material_affinity()
        score = ma.score(WOODEN_ASSET, "robotics_lab")
        assert score < 0.50


class TestNeutral:
    def test_empty_asset_returns_0_5(self):
        ma = get_material_affinity()
        assert ma.score({}, "western_room") == 0.5


class TestAccessors:
    def test_get_preferred_materials_nonempty(self):
        ma = get_material_affinity()
        assert len(ma.get_preferred_materials("western_room")) > 0

    def test_get_rejected_materials_nonempty(self):
        ma = get_material_affinity()
        assert len(ma.get_rejected_materials("western_room")) > 0


class TestAllEnvironmentsNoRaise:
    def test_all_safe(self):
        ma = get_material_affinity()
        for env in (
            "western_room", "industrial_hangar", "medical_lab",
            "sci_fi_corridor", "forest", "dungeon"
        ):
            s = ma.score(WOODEN_ASSET, env)
            assert 0.0 <= s <= 1.0
