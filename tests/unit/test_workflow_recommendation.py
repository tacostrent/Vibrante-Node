"""Tests for WorkflowRecommendationEngine (Tier 10 — §30)."""
import pytest
from src.runtime.workflows.workflow_recommendation import (
    WorkflowRecommendation,
    RecommendationResult,
    WorkflowRecommendationEngine,
    get_workflow_recommendation_engine,
    reset_workflow_recommendation_engine_for_tests,
    _INTENT_KEYWORDS,
    _DEFAULT_PACK_NAMES,
)
from src.runtime.workflows.workflow_pack import reset_workflow_pack_for_tests
from src.runtime.workflows.workflow_registry import reset_workflow_registry_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_workflow_recommendation_engine_for_tests()
    reset_workflow_pack_for_tests()
    reset_workflow_registry_for_tests()
    yield
    reset_workflow_recommendation_engine_for_tests()
    reset_workflow_pack_for_tests()
    reset_workflow_registry_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    assert get_workflow_recommendation_engine() is get_workflow_recommendation_engine()


# ---------------------------------------------------------------------------
# match_environment
# ---------------------------------------------------------------------------

def test_match_environment_industrial():
    eng = get_workflow_recommendation_engine()
    assert eng.match_environment("build cinematic industrial hangar scene") == "industrial_hangar"


def test_match_environment_robotics():
    eng = get_workflow_recommendation_engine()
    assert eng.match_environment("robotics laboratory testing") == "robotics_lab"


def test_match_environment_control_room():
    eng = get_workflow_recommendation_engine()
    assert eng.match_environment("command control room hub") == "control_room"


def test_match_environment_sci_fi():
    eng = get_workflow_recommendation_engine()
    assert eng.match_environment("futuristic scifi corridor") == "sci_fi_corridor"


def test_match_environment_abandoned():
    eng = get_workflow_recommendation_engine()
    assert eng.match_environment("abandoned derelict ruined factory") == "abandoned_factory"


def test_match_environment_no_match():
    eng = get_workflow_recommendation_engine()
    assert eng.match_environment("unknown place xyz") is None


# ---------------------------------------------------------------------------
# rank_candidates
# ---------------------------------------------------------------------------

def test_rank_candidates_by_confidence():
    eng = get_workflow_recommendation_engine()
    recs = [
        WorkflowRecommendation("a", 0.50, "default", "", "industrial_hangar"),
        WorkflowRecommendation("b", 0.95, "memory",  "", "industrial_hangar"),
        WorkflowRecommendation("c", 0.80, "pattern", "", "industrial_hangar"),
    ]
    ranked = eng.rank_candidates(recs)
    assert ranked[0].confidence == 0.95
    assert ranked[1].confidence == 0.80
    assert ranked[2].confidence == 0.50


def test_rank_candidates_stable_on_equal():
    eng  = get_workflow_recommendation_engine()
    recs = [
        WorkflowRecommendation("z_pack", 0.50, "default", "", "industrial_hangar"),
        WorkflowRecommendation("a_pack", 0.50, "default", "", "industrial_hangar"),
    ]
    ranked = eng.rank_candidates(recs)
    assert ranked[0].pack_name == "a_pack"


# ---------------------------------------------------------------------------
# recommend_pack
# ---------------------------------------------------------------------------

def test_recommend_pack_industrial():
    result = get_workflow_recommendation_engine().recommend_pack(
        "industrial machinery repair facility"
    )
    assert result.ok is True
    assert result.matched_environment == "industrial_hangar"
    assert result.top_recommendation is not None
    assert result.top_recommendation.pack_name == "industrial_hangar_pack"


def test_recommend_pack_no_match_returns_empty():
    result = get_workflow_recommendation_engine().recommend_pack("completely random xyz 123")
    assert result.ok is True   # ok even without a match (graceful)
    assert result.matched_environment is None
    assert result.top_recommendation is None


def test_recommend_pack_max_results():
    result = get_workflow_recommendation_engine().recommend_pack(
        "industrial hangar", max_results=1
    )
    assert len(result.recommendations) <= 1


def test_recommend_pack_result_structure():
    result = get_workflow_recommendation_engine().recommend_pack("robotics lab robot")
    d      = result.to_dict()
    for key in ("ok", "intent", "recommendations",
                "matched_environment", "source_counts", "top_recommendation"):
        assert key in d


def test_recommend_pack_recommendations_sorted():
    result = get_workflow_recommendation_engine().recommend_pack(
        "industrial hangar factory"
    )
    confidences = [r.confidence for r in result.recommendations]
    assert confidences == sorted(confidences, reverse=True)


# ---------------------------------------------------------------------------
# build_recommendation
# ---------------------------------------------------------------------------

def test_build_recommendation_keys():
    eng  = get_workflow_recommendation_engine()
    rec  = eng.build_recommendation("industrial factory hangar")
    for key in ("recommended_pack", "confidence", "source", "reason",
                "environment", "all_candidates"):
        assert key in rec


def test_build_recommendation_industrial():
    rec = get_workflow_recommendation_engine().build_recommendation(
        "industrial hangar machinery"
    )
    assert rec["recommended_pack"] == "industrial_hangar_pack"
    assert rec["confidence"] >= 0.50


def test_build_recommendation_no_match():
    rec = get_workflow_recommendation_engine().build_recommendation("abc xyz 999")
    assert rec["recommended_pack"] is None
    assert rec["confidence"] == 0.0


# ---------------------------------------------------------------------------
# WorkflowRecommendation model
# ---------------------------------------------------------------------------

def test_workflow_recommendation_to_dict():
    r = WorkflowRecommendation(
        pack_name="test", confidence=0.75, source="default",
        reason="test reason", environment="industrial_hangar",
    )
    d = r.to_dict()
    for key in ("pack_name", "confidence", "source", "reason", "environment"):
        assert key in d


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_increments():
    eng = get_workflow_recommendation_engine()
    eng.recommend_pack("industrial hangar")
    assert eng.stats()["recommendation_count"] >= 1


# ---------------------------------------------------------------------------
# Default pack names cover all envs
# ---------------------------------------------------------------------------

def test_default_pack_names_cover_all_envs():
    from src.runtime.workflows.workflow_pack import VALID_ENVIRONMENT_TYPES
    for env in VALID_ENVIRONMENT_TYPES:
        assert env in _DEFAULT_PACK_NAMES, f"No default pack name for {env}"
