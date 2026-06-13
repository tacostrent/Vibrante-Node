"""Tests for EnvRealizationReview — §49 Structural Environment Realization."""
import pytest
from src.runtime.environment_realization import (
    get_env_realization_review, reset_env_realization_review_for_tests,
    get_environment_realization_engine, reset_environment_realization_engine_for_tests,
    reset_structural_builder_for_tests, reset_room_shell_builder_for_tests,
    reset_floor_builder_for_tests, reset_ceiling_builder_for_tests,
    reset_wall_builder_for_tests, reset_opening_builder_for_tests,
    reset_beam_builder_for_tests, reset_architectural_constraint_solver_for_tests,
    reset_env_realization_statistics_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    for fn in [
        reset_env_realization_review_for_tests,
        reset_environment_realization_engine_for_tests,
        reset_structural_builder_for_tests, reset_room_shell_builder_for_tests,
        reset_floor_builder_for_tests, reset_ceiling_builder_for_tests,
        reset_wall_builder_for_tests, reset_opening_builder_for_tests,
        reset_beam_builder_for_tests, reset_architectural_constraint_solver_for_tests,
        reset_env_realization_statistics_for_tests,
    ]:
        fn()
    yield
    reset_env_realization_review_for_tests()
    reset_environment_realization_engine_for_tests()


def _good_plan():
    plan = get_environment_realization_engine().realize("western_room")
    return plan.to_dict()


def test_western_room_grade_a_or_b():
    result = get_env_realization_review().review(_good_plan())
    assert result.grade in ("A", "B")


def test_western_room_production_ready():
    result = get_env_realization_review().review(_good_plan())
    assert result.production_ready


def test_no_blocking_for_good_plan():
    result = get_env_realization_review().review(_good_plan())
    assert result.blocking == []


def test_missing_floor_is_blocking():
    plan = _good_plan()
    plan["floor_count"] = 0
    result = get_env_realization_review().review(plan)
    assert "floor missing" in result.blocking
    assert not result.production_ready


def test_missing_wall_is_blocking():
    plan = _good_plan()
    plan["wall_count"] = 2
    result = get_env_realization_review().review(plan)
    assert "wall missing" in result.blocking


def test_missing_door_is_blocking():
    plan = _good_plan()
    plan["door_count"] = 0
    result = get_env_realization_review().review(plan)
    assert "no door" in result.blocking


def test_room_not_closed_is_blocking():
    plan = _good_plan()
    plan["room_closed"] = False
    result = get_env_realization_review().review(plan)
    assert "room not closed" in result.blocking


def test_no_zones_is_blocking():
    plan = _good_plan()
    plan["zone_count"] = 0
    result = get_env_realization_review().review(plan)
    assert "no zones defined" in result.blocking


def test_outdoor_no_wall_blocking():
    plan = get_environment_realization_engine().realize("forest").to_dict()
    result = get_env_realization_review().review(plan)
    wall_blocking = [b for b in result.blocking if "wall" in b]
    assert wall_blocking == []


def test_all_score_dimensions_present():
    result = get_env_realization_review().review(_good_plan())
    d = result.to_dict()
    for key in ("structural_completeness", "architectural_validity", "zone_accuracy",
                "opening_quality", "beam_quality", "room_integrity"):
        assert key in d
        assert isinstance(d[key], float)
