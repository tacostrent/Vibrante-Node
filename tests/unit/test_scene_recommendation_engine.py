"""
Tests for src.runtime.scene_recommendation_engine
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.scene_recommendation_engine import (
    SceneRecommendationEngine,
    get_scene_recommendation_engine,
    reset_scene_recommendation_engine_for_tests,
    _SCENE_DEFAULTS,
    _DEFAULT_FALLBACK,
    _CONFIDENCE_MEMORY,
    _CONFIDENCE_PATTERN,
    _CONFIDENCE_DEFAULT,
)
from src.runtime.production_memory import reset_production_memory_for_tests
from src.runtime.pattern_library import reset_pattern_library_for_tests
from src.runtime.asset_knowledge_graph import reset_asset_knowledge_graph_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_scene_recommendation_engine_for_tests()
    reset_production_memory_for_tests()
    reset_pattern_library_for_tests()
    reset_asset_knowledge_graph_for_tests()
    yield
    reset_scene_recommendation_engine_for_tests()
    reset_production_memory_for_tests()
    reset_pattern_library_for_tests()
    reset_asset_knowledge_graph_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_scene_recommendation_engine()
    b = get_scene_recommendation_engine()
    assert a is b


def test_reset_creates_new():
    a = get_scene_recommendation_engine()
    reset_scene_recommendation_engine_for_tests()
    b = get_scene_recommendation_engine()
    assert a is not b


# ---------------------------------------------------------------------------
# Built-in defaults
# ---------------------------------------------------------------------------

def test_scene_defaults_has_five_environments():
    expected = {"industrial_hangar", "robotics_lab", "sci_fi_corridor",
                "cinematic_control_room", "abandoned_factory"}
    assert expected <= set(_SCENE_DEFAULTS.keys())


def test_default_fallback_has_required_keys():
    for key in ("lighting", "camera", "atmosphere", "template_id"):
        assert key in _DEFAULT_FALLBACK


# ---------------------------------------------------------------------------
# recommend_lighting
# ---------------------------------------------------------------------------

def test_recommend_lighting_returns_dict():
    e = SceneRecommendationEngine()
    result = e.recommend_lighting("industrial_hangar")
    assert isinstance(result, dict)


def test_recommend_lighting_has_required_keys():
    e = SceneRecommendationEngine()
    result = e.recommend_lighting("industrial_hangar")
    for key in ("recommended_style", "confidence", "source", "reasoning"):
        assert key in result, f"Missing key: {key}"


def test_recommend_lighting_known_scene_from_pattern():
    e = SceneRecommendationEngine()
    result = e.recommend_lighting("industrial_hangar")
    # Pattern library is seeded with cinematic_industrial for industrial_hangar
    assert result["recommended_style"] == "cinematic_industrial"


def test_recommend_lighting_unknown_scene_uses_default():
    e = SceneRecommendationEngine()
    result = e.recommend_lighting("unknown_xyz_env")
    assert result["source"] == "builtin_default"
    assert result["confidence"] == _CONFIDENCE_DEFAULT


def test_recommend_lighting_confidence_range():
    e = SceneRecommendationEngine()
    result = e.recommend_lighting("robotics_lab")
    assert 0.0 <= result["confidence"] <= 1.0


def test_recommend_lighting_memory_has_highest_confidence():
    # Seed production memory with successful scenes
    from src.runtime.production_memory import get_production_memory
    mem = get_production_memory()
    mem.record_scene({
        "scene_type": "robotics_lab",
        "lighting_style": "atmospheric_lab",
        "camera_style": "hero_focus",
        "status": "success",
        "score": 0.95,
    })
    e = SceneRecommendationEngine()
    result = e.recommend_lighting("robotics_lab")
    assert result["source"] == "production_memory"
    assert result["confidence"] == _CONFIDENCE_MEMORY
    assert result["recommended_style"] == "atmospheric_lab"


# ---------------------------------------------------------------------------
# recommend_camera
# ---------------------------------------------------------------------------

def test_recommend_camera_returns_dict():
    e = SceneRecommendationEngine()
    result = e.recommend_camera("industrial_hangar")
    assert isinstance(result, dict)


def test_recommend_camera_has_required_keys():
    e = SceneRecommendationEngine()
    result = e.recommend_camera("industrial_hangar")
    for key in ("recommended_mode", "confidence", "source", "reasoning"):
        assert key in result


def test_recommend_camera_known_scene():
    e = SceneRecommendationEngine()
    result = e.recommend_camera("industrial_hangar")
    assert result["recommended_mode"] == "cinematic_push_in"


def test_recommend_camera_control_room():
    e = SceneRecommendationEngine()
    result = e.recommend_camera("cinematic_control_room")
    assert result["recommended_mode"] == "orbital_reveal"


def test_recommend_camera_unknown_falls_back():
    e = SceneRecommendationEngine()
    result = e.recommend_camera("nonexistent_env")
    assert result["source"] == "builtin_default"


# ---------------------------------------------------------------------------
# recommend_atmosphere
# ---------------------------------------------------------------------------

def test_recommend_atmosphere_returns_dict():
    e = SceneRecommendationEngine()
    result = e.recommend_atmosphere("industrial_hangar")
    assert isinstance(result, dict)


def test_recommend_atmosphere_has_required_keys():
    e = SceneRecommendationEngine()
    result = e.recommend_atmosphere("sci_fi_corridor")
    for key in ("recommended_type", "confidence", "source", "reasoning"):
        assert key in result


def test_recommend_atmosphere_industrial_hangar():
    e = SceneRecommendationEngine()
    result = e.recommend_atmosphere("industrial_hangar")
    assert result["recommended_type"] == "industrial_fog"


def test_recommend_atmosphere_scifi_corridor():
    e = SceneRecommendationEngine()
    result = e.recommend_atmosphere("sci_fi_corridor")
    assert result["recommended_type"] == "volumetric_scifi"


# ---------------------------------------------------------------------------
# recommend_patterns
# ---------------------------------------------------------------------------

def test_recommend_patterns_returns_list():
    e = SceneRecommendationEngine()
    result = e.recommend_patterns("industrial_hangar")
    assert isinstance(result, list)


def test_recommend_patterns_nonempty_for_known_scene():
    e = SceneRecommendationEngine()
    result = e.recommend_patterns("industrial_hangar")
    assert len(result) > 0


def test_recommend_patterns_are_dicts():
    e = SceneRecommendationEngine()
    result = e.recommend_patterns("robotics_lab")
    for p in result:
        assert isinstance(p, dict)


def test_recommend_patterns_max_five():
    e = SceneRecommendationEngine()
    result = e.recommend_patterns("industrial_hangar")
    assert len(result) <= 5


# ---------------------------------------------------------------------------
# recommend_assets
# ---------------------------------------------------------------------------

def test_recommend_assets_returns_list():
    e = SceneRecommendationEngine()
    result = e.recommend_assets("industrial_hangar")
    assert isinstance(result, list)


def test_recommend_assets_nonempty_for_known_scene():
    e = SceneRecommendationEngine()
    result = e.recommend_assets("industrial_hangar")
    assert len(result) > 0


def test_recommend_assets_max_ten():
    e = SceneRecommendationEngine()
    result = e.recommend_assets("industrial_hangar")
    assert len(result) <= 10


def test_recommend_assets_unknown_scene_returns_empty():
    e = SceneRecommendationEngine()
    result = e.recommend_assets("nonexistent_xyz")
    assert result == []


# ---------------------------------------------------------------------------
# build_scene_recommendations
# ---------------------------------------------------------------------------

def test_build_scene_recommendations_returns_dict():
    e = SceneRecommendationEngine()
    result = e.build_scene_recommendations("industrial_hangar")
    assert isinstance(result, dict)


def test_build_scene_recommendations_has_required_keys():
    e = SceneRecommendationEngine()
    result = e.build_scene_recommendations("industrial_hangar")
    for key in ("scene_type", "lighting", "camera", "atmosphere", "patterns",
                "assets", "template_id", "overall_confidence", "generated_at"):
        assert key in result, f"Missing key: {key}"


def test_build_scene_recommendations_scene_type_recorded():
    e = SceneRecommendationEngine()
    result = e.build_scene_recommendations("robotics_lab")
    assert result["scene_type"] == "robotics_lab"


def test_build_scene_recommendations_industrial_hangar():
    e = SceneRecommendationEngine()
    result = e.build_scene_recommendations("industrial_hangar")
    assert result["lighting"]["recommended_style"] == "cinematic_industrial"
    assert result["camera"]["recommended_mode"] == "cinematic_push_in"
    assert result["atmosphere"]["recommended_type"] == "industrial_fog"


def test_build_scene_recommendations_control_room():
    e = SceneRecommendationEngine()
    result = e.build_scene_recommendations("cinematic_control_room")
    assert result["camera"]["recommended_mode"] == "orbital_reveal"


def test_build_scene_recommendations_overall_confidence_range():
    e = SceneRecommendationEngine()
    result = e.build_scene_recommendations("industrial_hangar")
    assert 0.0 <= result["overall_confidence"] <= 1.0


def test_build_scene_recommendations_generated_at_is_float():
    e = SceneRecommendationEngine()
    result = e.build_scene_recommendations("robotics_lab")
    assert isinstance(result["generated_at"], float)
    assert result["generated_at"] > 0


def test_build_scene_recommendations_increments_count():
    e = SceneRecommendationEngine()
    e.build_scene_recommendations("industrial_hangar")
    e.build_scene_recommendations("robotics_lab")
    assert e.stats()["recommendation_count"] == 2


def test_build_scene_recommendations_unknown_scene():
    e = SceneRecommendationEngine()
    result = e.build_scene_recommendations("totally_unknown_env")
    # Should return defaults, not raise
    assert result["lighting"]["source"] == "builtin_default"


def test_build_scene_recommendations_template_id_for_known():
    e = SceneRecommendationEngine()
    result = e.build_scene_recommendations("industrial_hangar")
    assert result["template_id"] == "cinematic_industrial_hangar"


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_has_recommendation_count():
    e = SceneRecommendationEngine()
    assert "recommendation_count" in e.stats()


def test_stats_starts_zero():
    e = SceneRecommendationEngine()
    assert e.stats()["recommendation_count"] == 0
