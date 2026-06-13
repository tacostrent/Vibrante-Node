"""Tests for KnowledgeRecommendationEngine (Tier 11 — §31)."""
import pytest
from src.runtime.studio.knowledge_recommendation import (
    KnowledgeRecommendationEngine,
    get_knowledge_recommendation_engine,
    reset_knowledge_recommendation_engine_for_tests,
    _DEFAULT_WORKFLOWS,
    _DEFAULT_LIGHTING,
    _DEFAULT_CAMERA,
    _DEFAULT_ATMOSPHERE,
)
from src.runtime.studio.studio_standards import reset_studio_standards_for_tests
from src.runtime.studio.studio_knowledge import reset_studio_knowledge_db_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_knowledge_recommendation_engine_for_tests()
    reset_studio_standards_for_tests()
    reset_studio_knowledge_db_for_tests()
    yield
    reset_knowledge_recommendation_engine_for_tests()
    reset_studio_standards_for_tests()
    reset_studio_knowledge_db_for_tests()


def test_singleton():
    assert get_knowledge_recommendation_engine() is get_knowledge_recommendation_engine()


# ---------------------------------------------------------------------------
# recommend_workflow
# ---------------------------------------------------------------------------

def test_recommend_workflow_default_known_env():
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_workflow("industrial_hangar")
    assert result["recommended_workflow"] == "industrial_hangar_pack"
    assert result["confidence"] >= 0.5


def test_recommend_workflow_unknown_env():
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_workflow("unknown_environment")
    assert result["recommended_workflow"] is None
    assert result["source"] == "default"


def test_recommend_workflow_required_keys():
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_workflow("robotics_lab")
    for key in ("recommended_workflow", "confidence", "source", "reason"):
        assert key in result


def test_recommend_workflow_all_envs():
    engine = KnowledgeRecommendationEngine()
    for env, expected in _DEFAULT_WORKFLOWS.items():
        result = engine.recommend_workflow(env)
        assert result["recommended_workflow"] == expected


# ---------------------------------------------------------------------------
# recommend_lighting
# ---------------------------------------------------------------------------

def test_recommend_lighting_default():
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_lighting("control_room")
    assert result["recommended_lighting"] == "warm_control_room"
    assert result["confidence"] >= 0.5


def test_recommend_lighting_standards_priority():
    from src.runtime.studio.studio_standards import get_studio_standards
    # The studio standards already have the defaults approved → confidence 0.90
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_lighting("industrial_hangar")
    assert result["confidence"] >= 0.9
    assert result["source"] == "studio_standards"


def test_recommend_lighting_required_keys():
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_lighting("robotics_lab")
    for key in ("recommended_lighting", "confidence", "source", "reason"):
        assert key in result


# ---------------------------------------------------------------------------
# recommend_camera
# ---------------------------------------------------------------------------

def test_recommend_camera_default():
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_camera("sci_fi_corridor")
    assert result["recommended_camera"] == "atmospheric_tracking"


def test_recommend_camera_standards_priority():
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_camera("industrial_hangar")
    assert result["confidence"] >= 0.9


# ---------------------------------------------------------------------------
# recommend_atmosphere
# ---------------------------------------------------------------------------

def test_recommend_atmosphere_default():
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_atmosphere("abandoned_factory")
    assert result["recommended_atmosphere"] == "dusty_hangar"


def test_recommend_atmosphere_required_keys():
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_atmosphere("industrial_hangar")
    for key in ("recommended_atmosphere", "confidence", "source", "reason"):
        assert key in result


# ---------------------------------------------------------------------------
# recommend_environment
# ---------------------------------------------------------------------------

def test_recommend_environment_keyword_match():
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_environment("create an industrial hangar scene")
    assert result["recommended_environment"] == "industrial_hangar"
    assert result["confidence"] == 0.85
    assert result["source"] == "keyword_match"


def test_recommend_environment_no_match_fallback():
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_environment("build a completely random thing")
    assert result["recommended_environment"] == "industrial_hangar"
    assert result["source"] == "fallback"
    assert result["confidence"] < 0.5


def test_recommend_environment_robotics_match():
    engine = KnowledgeRecommendationEngine()
    result = engine.recommend_environment("set up a robotics lab environment")
    assert result["recommended_environment"] == "robotics_lab"


# ---------------------------------------------------------------------------
# recommend_production_strategy
# ---------------------------------------------------------------------------

def test_recommend_production_strategy_keys():
    engine = KnowledgeRecommendationEngine()
    strategy = engine.recommend_production_strategy("industrial_hangar")
    for key in ("environment", "workflow", "lighting", "camera", "atmosphere",
                "overall_confidence", "production_ready"):
        assert key in strategy


def test_recommend_production_strategy_confidence_range():
    engine = KnowledgeRecommendationEngine()
    strategy = engine.recommend_production_strategy("robotics_lab")
    assert 0.0 <= strategy["overall_confidence"] <= 1.0


def test_recommend_production_strategy_production_ready():
    engine = KnowledgeRecommendationEngine()
    strategy = engine.recommend_production_strategy("industrial_hangar")
    # Studio standards are already loaded → confidence >= 0.9 → production_ready True
    assert strategy["production_ready"] is True


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------

def test_stats_key():
    engine = KnowledgeRecommendationEngine()
    assert "recommendation_count" in engine.stats()


def test_stats_count_increments():
    engine = KnowledgeRecommendationEngine()
    engine.recommend_workflow("industrial_hangar")
    engine.recommend_lighting("industrial_hangar")
    engine.recommend_camera("industrial_hangar")
    engine.recommend_atmosphere("industrial_hangar")
    engine.recommend_environment("some intent")
    engine.recommend_production_strategy("industrial_hangar")
    # Each sub-call in production_strategy also increments
    assert engine.stats()["recommendation_count"] >= 5
