import pytest
from src.runtime.lookdev import (
    MaterialRecommendation,
    MaterialRecommendationResult,
    get_material_recommendation_engine,
    reset_material_recommendation_engine_for_tests,
    reset_material_library_for_tests,
    reset_material_knowledge_for_tests,
    reset_lookdev_patterns_for_tests,
    reset_renderer_profiles_for_tests,
)


@pytest.fixture(autouse=True)
def reset_all():
    reset_material_recommendation_engine_for_tests()
    reset_material_library_for_tests()
    reset_material_knowledge_for_tests()
    reset_lookdev_patterns_for_tests()
    reset_renderer_profiles_for_tests()
    yield
    reset_material_recommendation_engine_for_tests()
    reset_material_library_for_tests()
    reset_material_knowledge_for_tests()
    reset_lookdev_patterns_for_tests()
    reset_renderer_profiles_for_tests()


def test_singleton_identity():
    assert get_material_recommendation_engine() is get_material_recommendation_engine()


def test_recommend_material_returns_result():
    engine = get_material_recommendation_engine()
    result = engine.recommend_material({"asset_id": "a1", "name": "forklift"}, "usd_preview_surface")
    assert isinstance(result, MaterialRecommendationResult)
    assert result.ok is True
    assert len(result.recommendations) >= 1


def test_recommend_material_has_material_name():
    result = get_material_recommendation_engine().recommend_material(
        {"name": "pipe_assembly", "tags": ["pipe"]}, "arnold"
    )
    assert result.recommendations[0].material_name != ""


def test_recommend_material_renderer_preserved():
    result = get_material_recommendation_engine().recommend_material(
        {"name": "robot_arm"}, "karma"
    )
    assert result.renderer == "karma"


def test_lookdev_pattern_source_for_hangar_asset():
    result = get_material_recommendation_engine().recommend_material(
        {"name": "hangar_crate", "tags": ["hangar", "industrial"]}, "usd_preview_surface"
    )
    assert result.strategy_used in ("lookdev_pattern", "material_knowledge", "renderer_default")


def test_recommend_material_set_returns_multiple():
    result = get_material_recommendation_engine().recommend_material_set(
        {"name": "factory_floor", "tags": ["industrial", "hangar"]}, "usd_preview_surface"
    )
    assert isinstance(result, MaterialRecommendationResult)
    assert len(result.recommendations) >= 1


def test_recommend_environment_materials_hangar():
    result = get_material_recommendation_engine().recommend_environment_materials(
        "industrial_hangar", "usd_preview_surface"
    )
    assert result.ok is True
    assert len(result.recommendations) >= 1
    mat_names = [r.material_name for r in result.recommendations]
    assert any(m in ("industrial_metal", "weathered_concrete", "oxidized_pipe") for m in mat_names)


def test_recommend_environment_materials_unknown():
    result = get_material_recommendation_engine().recommend_environment_materials(
        "unknown_environment_xyz", "usd_preview_surface"
    )
    assert isinstance(result, MaterialRecommendationResult)
    assert len(result.recommendations) >= 1


def test_recommend_renderer_materials_arnold():
    result = get_material_recommendation_engine().recommend_renderer_materials("arnold")
    assert result.ok is True
    assert result.renderer == "arnold"
    assert len(result.recommendations) >= 1


def test_confidence_range():
    result = get_material_recommendation_engine().recommend_material({}, "usd_preview_surface")
    for rec in result.recommendations:
        assert 0.0 <= rec.confidence <= 1.0


def test_recommendation_to_dict_keys():
    rec = MaterialRecommendation(material_name="concrete", renderer="karma", confidence=0.75)
    d = rec.to_dict()
    for key in ("recommendation_id", "asset_id", "material_name", "renderer",
                "confidence", "source", "reasoning", "created_at"):
        assert key in d


def test_recommendation_from_dict_round_trip():
    rec = MaterialRecommendation(material_name="glass", renderer="arnold", source="lookdev_pattern")
    restored = MaterialRecommendation.from_dict(rec.to_dict())
    assert restored.material_name == "glass"
    assert restored.source == "lookdev_pattern"


def test_result_from_dict_round_trip():
    result = get_material_recommendation_engine().recommend_material({"name": "test"}, "karma")
    restored = MaterialRecommendationResult.from_dict(result.to_dict())
    assert restored.renderer == "karma"
    assert len(restored.recommendations) == len(result.recommendations)


def test_never_raises_none():
    result = get_material_recommendation_engine().recommend_material(None, "arnold")  # type: ignore
    assert isinstance(result, MaterialRecommendationResult)
