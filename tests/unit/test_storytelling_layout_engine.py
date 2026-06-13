"""Tests for StorytellingLayoutEngine (Tier 9 — §29)."""
import pytest
from src.runtime.assets.assembly.storytelling_layout_engine import (
    StoryBeat,
    StoryLayout,
    StorytellingLayoutEngine,
    get_storytelling_layout_engine,
    reset_storytelling_layout_engine_for_tests,
    _ENV_NARRATIVES,
)
from src.runtime.assets.assembly.environment_builder import (
    get_environment_builder,
    reset_environment_builder_for_tests,
)
from src.runtime.assets.assembly.placement_templates import reset_placement_templates_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_storytelling_layout_engine_for_tests()
    reset_environment_builder_for_tests()
    reset_placement_templates_for_tests()
    yield
    reset_storytelling_layout_engine_for_tests()
    reset_environment_builder_for_tests()
    reset_placement_templates_for_tests()


def _env(environment="industrial_hangar", n=2):
    builder = get_environment_builder()
    recs = [{"asset": {"name": f"a_{i}", "category": "machinery"}} for i in range(n)]
    return builder.build_environment(environment, recs)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_storytelling_layout_engine() is get_storytelling_layout_engine()


def test_reset():
    a = get_storytelling_layout_engine()
    reset_storytelling_layout_engine_for_tests()
    b = get_storytelling_layout_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# generate_story_layout
# ---------------------------------------------------------------------------

def test_returns_story_layout():
    layout = get_storytelling_layout_engine().generate_story_layout(_env())
    assert isinstance(layout, StoryLayout)
    assert layout.ok


def test_theme_populated():
    layout = get_storytelling_layout_engine().generate_story_layout(_env())
    assert layout.theme


def test_visual_flow_populated():
    layout = get_storytelling_layout_engine().generate_story_layout(_env())
    assert layout.visual_flow


def test_hero_zone_identified():
    layout = get_storytelling_layout_engine().generate_story_layout(_env())
    assert layout.hero_zone == "hero_zone"


def test_support_zones_not_hero():
    layout = get_storytelling_layout_engine().generate_story_layout(_env())
    assert "hero_zone" not in layout.support_zones


def test_viewer_path_not_empty():
    layout = get_storytelling_layout_engine().generate_story_layout(_env())
    assert layout.viewer_path


def test_viewer_path_zones_exist_in_plan():
    env_plan = _env()
    layout   = get_storytelling_layout_engine().generate_story_layout(env_plan)
    for zone_name in layout.viewer_path:
        assert zone_name in env_plan.zones


def test_beats_not_empty():
    layout = get_storytelling_layout_engine().generate_story_layout(_env())
    assert layout.beats


def test_hero_beat_present():
    layout = get_storytelling_layout_engine().generate_story_layout(_env())
    hero_beats = [b for b in layout.beats if b.beat_type == "hero"]
    assert hero_beats


def test_hero_beat_priority_highest():
    layout = get_storytelling_layout_engine().generate_story_layout(_env())
    # Beats should be sorted priority descending; hero (10) first
    assert layout.beats[0].beat_type == "hero"


# ---------------------------------------------------------------------------
# All 5 environments
# ---------------------------------------------------------------------------

def test_all_environments_produce_layout():
    engine = get_storytelling_layout_engine()
    for env in _ENV_NARRATIVES:
        env_plan = _env(env)
        layout   = engine.generate_story_layout(env_plan)
        assert layout.ok, f"{env}: {layout.errors}"
        assert layout.theme


# ---------------------------------------------------------------------------
# identify_hero_area
# ---------------------------------------------------------------------------

def test_identify_hero_area():
    engine   = get_storytelling_layout_engine()
    env_plan = _env()
    assert engine.identify_hero_area(env_plan) == "hero_zone"


def test_identify_hero_area_no_hero_zone():
    from src.runtime.assets.assembly.environment_builder import EnvironmentPlan, EnvironmentZone
    engine = get_storytelling_layout_engine()
    plan   = EnvironmentPlan(environment="test")
    plan.zones = {"midground": EnvironmentZone("midground", "support")}
    assert engine.identify_hero_area(plan) == ""


# ---------------------------------------------------------------------------
# generate_visual_flow
# ---------------------------------------------------------------------------

def test_generate_visual_flow_returns_string():
    engine   = get_storytelling_layout_engine()
    env_plan = _env()
    flow = engine.generate_visual_flow(env_plan)
    assert isinstance(flow, str)
    assert flow


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

def test_story_layout_round_trip():
    layout = get_storytelling_layout_engine().generate_story_layout(_env())
    d  = layout.to_dict()
    l2 = StoryLayout.from_dict(d)
    assert l2.theme == layout.theme
    assert len(l2.beats) == len(layout.beats)
    assert l2.viewer_path == layout.viewer_path


def test_story_beat_round_trip():
    beat = StoryBeat(
        beat_id="bid", beat_type="hero", zone_name="hero_zone",
        description="central machinery", priority=10,
    )
    d   = beat.to_dict()
    b2  = StoryBeat.from_dict(d)
    assert b2.beat_id == "bid"
    assert b2.beat_type == "hero"
    assert b2.priority == 10
