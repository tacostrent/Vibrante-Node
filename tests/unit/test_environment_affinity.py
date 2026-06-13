"""Tests for EnvironmentAffinity — §45 Semantic Asset Suitability Ranking."""

import pytest
from src.runtime.assets.suitability.environment_affinity import (
    get_environment_affinity,
    reset_environment_affinity_for_tests,
)

WESTERN_CHAIR = {
    "asset_id": "wooden_saloon_chair",
    "name": "Wooden Saloon Chair",
    "category": "furniture",
    "type": "chair",
    "placement_type": "chair",
    "tags": ["wooden", "saloon", "weathered", "rustic"],
    "style_tags": ["weathered", "rustic"],
    "material_tags": ["wood"],
    "environment_tags": ["western_room", "saloon"],
}

MODERN_CHAIR = {
    "asset_id": "modern_plastic_chair",
    "name": "Modern Plastic Chair",
    "category": "furniture",
    "type": "chair",
    "placement_type": "chair",
    "tags": ["modern", "plastic", "office"],
    "style_tags": ["clean", "modern"],
    "material_tags": ["plastic", "chrome"],
    "environment_tags": ["office"],
}

ROBOT_ARM = {
    "asset_id": "robot_arm_001",
    "name": "Industrial Robot Arm",
    "category": "machinery",
    "type": "machine",
    "tags": ["robotic", "industrial", "electronic", "metal"],
    "environment_tags": ["robotics_lab"],
}


@pytest.fixture(autouse=True)
def reset():
    reset_environment_affinity_for_tests()
    yield
    reset_environment_affinity_for_tests()


class TestExplicitEnvironmentTag:
    def test_exact_env_tag_returns_1(self):
        ea = get_environment_affinity()
        assert ea.score(WESTERN_CHAIR, "western_room") == 1.0

    def test_wrong_env_tag_not_full_score(self):
        ea = get_environment_affinity()
        score = ea.score(MODERN_CHAIR, "western_room")
        assert score < 0.9


class TestPreferredKeywords:
    def test_preferred_keywords_raise_score(self):
        ea = get_environment_affinity()
        base = ea.score({}, "western_room")   # neutral asset
        scored = ea.score(WESTERN_CHAIR, "western_room")
        assert scored >= base

    def test_western_chair_scores_high_for_western(self):
        ea = get_environment_affinity()
        assert ea.score(WESTERN_CHAIR, "western_room") >= 0.80

    def test_robot_arm_scores_high_for_robotics_lab(self):
        ea = get_environment_affinity()
        score = ea.score(ROBOT_ARM, "robotics_lab")
        assert score >= 0.60


class TestRejectedKeywords:
    def test_modern_chair_penalised_for_western(self):
        ea = get_environment_affinity()
        s_western = ea.score(WESTERN_CHAIR, "western_room")
        s_modern = ea.score(MODERN_CHAIR, "western_room")
        assert s_western > s_modern

    def test_robot_arm_penalised_for_western(self):
        ea = get_environment_affinity()
        score = ea.score(ROBOT_ARM, "western_room")
        assert score < 0.50

    def test_western_chair_penalised_for_robotics_lab(self):
        ea = get_environment_affinity()
        score = ea.score(WESTERN_CHAIR, "robotics_lab")
        assert score < 0.50


class TestNeutralAsset:
    def test_empty_asset_returns_0_5(self):
        ea = get_environment_affinity()
        assert ea.score({}, "western_room") == 0.5

    def test_unknown_environment_uses_neutral(self):
        ea = get_environment_affinity()
        score = ea.score(WESTERN_CHAIR, "nonexistent_env")
        assert 0.0 <= score <= 1.0


class TestAccessors:
    def test_get_preferred_returns_list(self):
        ea = get_environment_affinity()
        kws = ea.get_preferred("western_room")
        assert isinstance(kws, list)
        assert "western" in kws

    def test_get_rejected_returns_list(self):
        ea = get_environment_affinity()
        kws = ea.get_rejected("western_room")
        assert isinstance(kws, list)
        assert len(kws) > 0

    def test_known_environments_includes_standard(self):
        ea = get_environment_affinity()
        envs = ea.known_environments()
        for env in ("western_room", "industrial_hangar", "sci_fi_corridor", "forest"):
            assert env in envs


class TestAllEnvironmentsNoRaise:
    def test_score_on_all_known_environments(self):
        ea = get_environment_affinity()
        for env in ea.known_environments():
            s = ea.score(WESTERN_CHAIR, env)
            assert 0.0 <= s <= 1.0
