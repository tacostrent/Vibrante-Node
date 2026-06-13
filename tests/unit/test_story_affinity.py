"""Tests for StoryAffinity — §45 Semantic Asset Suitability Ranking."""

import pytest
from src.runtime.assets.suitability.story_affinity import (
    get_story_affinity,
    reset_story_affinity_for_tests,
)

WANTED_POSTER = {
    "name": "Wanted Poster",
    "type": "poster",
    "tags": ["wanted", "poster", "paper"],
}

WHISKEY_BOTTLE = {
    "name": "Whiskey Bottle",
    "type": "bottle",
    "tags": ["whiskey", "bottle", "glass"],
}

OIL_LANTERN = {
    "name": "Oil Lantern",
    "type": "lantern",
    "tags": ["oil", "lantern"],
}

SERVER_RACK = {
    "name": "Server Rack",
    "type": "rack",
    "tags": ["server", "rack", "electronic"],
}

ROBOT_ARM = {
    "name": "Robot Arm",
    "type": "machine",
    "tags": ["robot", "arm", "robotic"],
}

TEST_TUBE = {
    "name": "Test Tube",
    "type": "vessel",
    "tags": ["test", "tube", "glass"],
}


@pytest.fixture(autouse=True)
def reset():
    reset_story_affinity_for_tests()
    yield
    reset_story_affinity_for_tests()


class TestWesternStory:
    def test_wanted_poster_scores_high_for_western(self):
        sa = get_story_affinity()
        assert sa.score(WANTED_POSTER, "western_room") >= 0.60

    def test_whiskey_bottle_scores_high_for_western(self):
        sa = get_story_affinity()
        assert sa.score(WHISKEY_BOTTLE, "western_room") >= 0.60

    def test_oil_lantern_scores_high_for_western(self):
        sa = get_story_affinity()
        assert sa.score(OIL_LANTERN, "western_room") >= 0.60

    def test_server_rack_rejected_for_western(self):
        sa = get_story_affinity()
        score = sa.score(SERVER_RACK, "western_room")
        assert score < 0.30

    def test_robot_arm_rejected_for_western(self):
        sa = get_story_affinity()
        score = sa.score(ROBOT_ARM, "western_room")
        assert score < 0.30


class TestRoboticsLabStory:
    def test_robot_arm_scores_high_for_robotics(self):
        sa = get_story_affinity()
        assert sa.score(ROBOT_ARM, "robotics_lab") >= 0.60

    def test_wanted_poster_low_for_robotics(self):
        sa = get_story_affinity()
        score = sa.score(WANTED_POSTER, "robotics_lab")
        assert score < 0.60  # may score neutral, not penalised


class TestResearchLab:
    def test_test_tube_scores_high_for_research_lab(self):
        sa = get_story_affinity()
        assert sa.score(TEST_TUBE, "research_lab") >= 0.60


class TestNarrative:
    def test_story_assets_beats_generic_for_env(self):
        sa = get_story_affinity()
        generic = {"name": "Generic Box", "type": "crate", "tags": ["crate"]}
        s_poster = sa.score(WANTED_POSTER, "western_room")
        s_generic = sa.score(generic, "western_room")
        assert s_poster > s_generic


class TestAccessors:
    def test_get_story_assets_returns_list(self):
        sa = get_story_affinity()
        assets = sa.get_story_assets("western_room")
        assert isinstance(assets, list)
        assert len(assets) > 0
        assert any("lantern" in a for a in assets)

    def test_known_environments_includes_western(self):
        sa = get_story_affinity()
        assert "western_room" in sa.known_environments()


class TestNeutralAndSafety:
    def test_empty_asset_returns_neutral_or_low(self):
        sa = get_story_affinity()
        s = sa.score({}, "western_room")
        assert 0.0 <= s <= 1.0

    def test_unknown_env_safe(self):
        sa = get_story_affinity()
        s = sa.score(WANTED_POSTER, "unknown_env")
        assert 0.0 <= s <= 1.0
