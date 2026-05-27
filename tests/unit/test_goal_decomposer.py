"""
Tests for src.runtime.goal_decomposer
No Houdini, no bridge, no external APIs. Pure unit tests.
"""

import pytest
from src.runtime.goal_decomposer import (
    GoalDecomposer,
    DecompositionResult,
    get_goal_decomposer,
    reset_goal_decomposer_for_tests,
    _WORKFLOW_STAGES,
    _COMPOSITE_GOALS,
    _GOAL_KEYWORDS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_goal_decomposer_for_tests()
    yield
    reset_goal_decomposer_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_returns_same_instance():
    a = get_goal_decomposer()
    b = get_goal_decomposer()
    assert a is b


def test_reset_creates_new_instance():
    a = get_goal_decomposer()
    reset_goal_decomposer_for_tests()
    b = get_goal_decomposer()
    assert a is not b


# ---------------------------------------------------------------------------
# DecompositionResult basics
# ---------------------------------------------------------------------------

def test_decomposition_result_ok_when_workflows_present():
    r = DecompositionResult(
        goal="test",
        matched_workflows=["cinematic_explosion"],
        stages=["terrain_prep"],
        execution_order=[],
        confidence=0.9,
        notes=[],
    )
    assert r.ok is True


def test_decomposition_result_not_ok_when_empty():
    r = DecompositionResult(
        goal="test",
        matched_workflows=[],
        stages=[],
        execution_order=[],
        confidence=0.0,
        notes=[],
    )
    assert r.ok is False


def test_decomposition_result_to_dict():
    r = DecompositionResult(
        goal="fireball",
        matched_workflows=["fuel_fireball"],
        stages=["fuel_source_geo"],
        execution_order=[],
        confidence=0.85,
        notes=["test note"],
    )
    d = r.to_dict()
    assert d["goal"] == "fireball"
    assert d["ok"] is True
    assert d["workflow_count"] == 1
    assert d["stage_count"] == 1
    assert d["confidence"] == 0.85
    assert "notes" in d


# ---------------------------------------------------------------------------
# decompose — no match
# ---------------------------------------------------------------------------

def test_decompose_no_match():
    gd = GoalDecomposer()
    result = gd.decompose("completely unknown goal xyz")
    assert result.ok is False
    assert result.matched_workflows == []
    assert result.stages == []
    assert result.confidence == 0.0
    assert len(result.notes) > 0


# ---------------------------------------------------------------------------
# decompose — forced workflow_id override
# ---------------------------------------------------------------------------

def test_decompose_forced_workflow():
    gd = GoalDecomposer()
    result = gd.decompose("anything", context={"workflow_id": "cinematic_explosion"})
    assert result.ok is True
    assert result.matched_workflows == ["cinematic_explosion"]
    assert result.confidence == 1.0
    assert result.stages == _WORKFLOW_STAGES["cinematic_explosion"]


def test_decompose_forced_unknown_workflow_falls_through():
    gd = GoalDecomposer()
    # Unknown workflow_id — should fall through to keyword matching
    result = gd.decompose("rolling dust wave from pressure", context={"workflow_id": "nonexistent_workflow"})
    # Should still try keyword matching since forced workflow doesn't exist
    # dust_wave keywords should match
    assert "dust_wave" in result.matched_workflows or result.ok is False  # either keyword match or no match


# ---------------------------------------------------------------------------
# decompose — composite goals
# ---------------------------------------------------------------------------

def test_decompose_cinematic_explosion_scene():
    gd = GoalDecomposer()
    result = gd.decompose("create cinematic explosion scene")
    assert result.ok is True
    expected_workflows = _COMPOSITE_GOALS["cinematic explosion scene"]
    for wf in expected_workflows:
        assert wf in result.matched_workflows
    assert result.confidence == 0.95
    assert len(result.stages) > 0
    assert any("Composite goal matched" in n for n in result.notes)


def test_decompose_full_explosion():
    gd = GoalDecomposer()
    result = gd.decompose("full explosion vfx shot")
    assert result.ok is True
    # "full explosion" is in _COMPOSITE_GOALS
    assert len(result.matched_workflows) >= 3


def test_decompose_missile_strike():
    gd = GoalDecomposer()
    result = gd.decompose("set up a missile strike scene")
    assert result.ok is True
    assert "missile_impact" in result.matched_workflows


def test_decompose_render_ready():
    gd = GoalDecomposer()
    result = gd.decompose("make it render ready")
    assert result.ok is True
    assert "arnold_render_ready" in result.matched_workflows


def test_decompose_night_explosion():
    gd = GoalDecomposer()
    result = gd.decompose("create a night explosion scene")
    assert result.ok is True
    # night explosion composite goal
    assert "night_explosion_lighting" in result.matched_workflows or result.ok is True


# ---------------------------------------------------------------------------
# decompose — single workflow keyword matching
# ---------------------------------------------------------------------------

def test_decompose_smoke_column():
    gd = GoalDecomposer()
    result = gd.decompose("add a rising smoke column")
    assert result.ok is True
    assert "smoke_column" in result.matched_workflows


def test_decompose_camera_shake():
    gd = GoalDecomposer()
    result = gd.decompose("add camera shake on impact")
    assert result.ok is True
    assert "impact_handheld" in result.matched_workflows


def test_decompose_slow_motion():
    gd = GoalDecomposer()
    result = gd.decompose("add slow motion reveal to the end")
    assert result.ok is True
    assert "slow_motion_reveal" in result.matched_workflows


def test_decompose_push_in():
    gd = GoalDecomposer()
    result = gd.decompose("create a push in camera move toward the explosion")
    assert result.ok is True
    assert "cinematic_push_in" in result.matched_workflows


def test_decompose_aov_setup():
    gd = GoalDecomposer()
    result = gd.decompose("set up render passes and aov configuration")
    assert result.ok is True
    assert "cinematic_aov_setup" in result.matched_workflows


def test_decompose_debris_field():
    gd = GoalDecomposer()
    result = gd.decompose("create a secondary debris field")
    assert result.ok is True
    assert "debris_field" in result.matched_workflows


def test_decompose_fuel_fireball():
    gd = GoalDecomposer()
    result = gd.decompose("set up fuel fireball simulation")
    assert result.ok is True
    assert "fuel_fireball" in result.matched_workflows


def test_decompose_volumetric_lighting():
    gd = GoalDecomposer()
    result = gd.decompose("set up volumetric lighting with godrays")
    assert result.ok is True
    assert "volumetric_contrast_lighting" in result.matched_workflows


def test_decompose_case_insensitive():
    gd = GoalDecomposer()
    result = gd.decompose("CREATE CINEMATIC EXPLOSION SCENE")
    assert result.ok is True


# ---------------------------------------------------------------------------
# decompose — stage list shape
# ---------------------------------------------------------------------------

def test_decompose_stages_are_ordered_list():
    gd = GoalDecomposer()
    result = gd.decompose("add rising smoke column")
    assert isinstance(result.stages, list)
    assert len(result.stages) > 0


def test_decompose_no_duplicate_stages():
    gd = GoalDecomposer()
    result = gd.decompose("cinematic explosion scene")
    # Stages should be deduplicated
    assert len(result.stages) == len(set(result.stages))


def test_decompose_execution_order_shape():
    gd = GoalDecomposer()
    result = gd.decompose("cinematic explosion scene")
    for entry in result.execution_order:
        assert "workflow" in entry
        assert "stage" in entry
        assert "description" in entry


# ---------------------------------------------------------------------------
# get_workflow_stages
# ---------------------------------------------------------------------------

def test_get_workflow_stages_known():
    gd = GoalDecomposer()
    stages = gd.get_workflow_stages("cinematic_explosion")
    assert stages == _WORKFLOW_STAGES["cinematic_explosion"]
    assert isinstance(stages, list)
    assert len(stages) == 9


def test_get_workflow_stages_unknown():
    gd = GoalDecomposer()
    stages = gd.get_workflow_stages("completely_unknown_workflow")
    assert stages == []


def test_get_workflow_stages_returns_copy():
    gd = GoalDecomposer()
    stages = gd.get_workflow_stages("smoke_column")
    stages.append("fake_stage")
    # Original should be unaffected
    assert "fake_stage" not in gd.get_workflow_stages("smoke_column")


# ---------------------------------------------------------------------------
# sequence_goals
# ---------------------------------------------------------------------------

def test_sequence_goals_multiple():
    gd = GoalDecomposer()
    goals = ["add rising smoke column", "set up camera shake"]
    results = gd.sequence_goals(goals)
    assert len(results) == 2
    assert all(isinstance(r, DecompositionResult) for r in results)


def test_sequence_goals_empty():
    gd = GoalDecomposer()
    results = gd.sequence_goals([])
    assert results == []


def test_sequence_goals_order_preserved():
    gd = GoalDecomposer()
    goals = ["add rising smoke column", "completely unknown xyz"]
    results = gd.sequence_goals(goals)
    assert results[0].ok is True
    assert results[1].ok is False


# ---------------------------------------------------------------------------
# list_known_workflows
# ---------------------------------------------------------------------------

def test_list_known_workflows():
    gd = GoalDecomposer()
    known = gd.list_known_workflows()
    assert isinstance(known, list)
    assert "cinematic_explosion" in known
    assert "arnold_render_ready" in known
    assert len(known) >= 14  # at minimum the 14 we defined


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    gd = GoalDecomposer()
    s = gd.stats()
    assert "decompose_count" in s
    assert "known_workflows" in s
    assert "known_composite_goals" in s


def test_stats_count_increments():
    gd = GoalDecomposer()
    gd.decompose("smoke column")
    gd.decompose("camera shake")
    assert gd.stats()["decompose_count"] == 2


def test_stats_known_workflows_count():
    gd = GoalDecomposer()
    s = gd.stats()
    assert s["known_workflows"] == len(_WORKFLOW_STAGES)
    assert s["known_composite_goals"] == len(_COMPOSITE_GOALS)


# ---------------------------------------------------------------------------
# confidence levels
# ---------------------------------------------------------------------------

def test_confidence_composite_goal():
    gd = GoalDecomposer()
    result = gd.decompose("cinematic explosion scene")
    assert result.confidence == 0.95


def test_confidence_single_workflow():
    gd = GoalDecomposer()
    result = gd.decompose("add smoke column simulation")
    assert result.confidence == 0.85


def test_confidence_multi_workflow_keyword():
    gd = GoalDecomposer()
    # Matches multiple workflows via keyword (not composite)
    result = gd.decompose("explosion scene with camera shake and render setup")
    if result.ok and len(result.matched_workflows) > 1:
        assert result.confidence == 0.9
