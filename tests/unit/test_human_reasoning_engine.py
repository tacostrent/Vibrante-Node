"""Tests for the §54 Human Reasoning Layer (Tier 15.0+)."""

import pytest

from src.runtime.reality.human_reasoning_engine import (
    get_human_reasoning_engine,
    reset_human_reasoning_engine_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_human_reasoning_engine_for_tests()
    yield
    reset_human_reasoning_engine_for_tests()


class TestJustification:
    def test_known_type_answers_all_six_questions(self):
        j = get_human_reasoning_engine().justify_asset(
            {"asset_id": "t1", "asset_name": "Saloon Table"})
        assert j.justified
        assert j.why_exists
        assert j.who_uses
        assert j.activity
        assert j.supported_by
        assert j.related_to
        assert j.story_value

    def test_unknown_asset_without_metadata_rejected(self):
        j = get_human_reasoning_engine().justify_asset(
            {"asset_id": "x", "asset_name": "xgihfgbqx"})
        assert not j.justified
        assert "Do not place the asset" in j.detail

    def test_unknown_asset_with_metadata_accepted(self):
        j = get_human_reasoning_engine().justify_asset({
            "asset_id": "x", "asset_name": "Strange Relic",
            "why_exists": "quest macguffin on the altar",
            "story_value": "the room exists to guard it",
        })
        assert j.justified

    def test_canonical_scene_fully_justified(self, western_room_scene):
        result = get_human_reasoning_engine().justify_scene(western_room_scene)
        assert result.all_justified, [r.detail for r in result.rejected]
        assert result.justified_count == 19

    def test_scene_with_garbage_asset_flagged(self, western_room_scene):
        western_room_scene["transforms"].append(
            {"asset_id": "x", "asset_name": "qzkvjwpf", "tx": 1, "ty": 0.2, "tz": 1,
             "bbox_half_x": 0.2, "bbox_half_y": 0.2, "bbox_half_z": 0.2})
        result = get_human_reasoning_engine().justify_scene(western_room_scene)
        assert not result.all_justified
        assert result.rejected_count == 1

    def test_never_raises(self):
        result = get_human_reasoning_engine().justify_scene(None)
        assert result.justified_count == 0
