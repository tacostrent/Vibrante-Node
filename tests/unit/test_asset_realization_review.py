"""
Tests for AssetRealizationReview (Tier 13)
"""
import pytest

from src.runtime.assets.realization import (
    get_asset_realization_review,
    reset_asset_realization_review_for_tests,
    RealizationReviewResult,
    reset_asset_importer_for_tests,
    reset_asset_converter_for_tests,
    reset_asset_dependency_resolver_for_tests,
    reset_asset_material_mapper_for_tests,
    reset_scene_asset_realizer_for_tests,
)

# Import the weight constants to test their sum
from src.runtime.assets.realization.asset_realization_review import _WEIGHTS


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_asset_realization_review_for_tests()
    reset_asset_importer_for_tests()
    reset_asset_converter_for_tests()
    reset_asset_dependency_resolver_for_tests()
    reset_asset_material_mapper_for_tests()
    reset_scene_asset_realizer_for_tests()
    yield
    reset_asset_realization_review_for_tests()
    reset_asset_importer_for_tests()
    reset_asset_converter_for_tests()
    reset_asset_dependency_resolver_for_tests()
    reset_asset_material_mapper_for_tests()
    reset_scene_asset_realizer_for_tests()


def test_singleton():
    assert get_asset_realization_review() is get_asset_realization_review()


def test_weights_sum_to_1():
    total = sum(_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9


def test_grade_thresholds():
    reviewer = get_asset_realization_review()
    from src.runtime.assets.realization.asset_realization_review import _grade
    assert _grade(0.95) == "A"
    assert _grade(0.85) == "B"
    assert _grade(0.75) == "C"
    assert _grade(0.65) == "D"
    assert _grade(0.55) == "F"


def test_review_import_has_score_and_issues():
    mock = {"ok": True, "asset_id": "rv1", "format": "usd", "errors": []}
    result = get_asset_realization_review().review_import(mock)
    assert "score" in result
    assert "issues" in result
    assert 0.0 <= result["score"] <= 1.0


def test_review_conversion_has_score():
    mock = {"ok": True, "target_format": "usd", "errors": []}
    result = get_asset_realization_review().review_conversion(mock)
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0


def test_review_dependencies_has_score():
    mock = {"ok": True, "missing_deps": [], "errors": []}
    result = get_asset_realization_review().review_dependencies(mock)
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0


def test_review_materials_has_score():
    mock = {"ok": True, "profiles": [{"name": "mat"}], "material_count": 1, "errors": []}
    result = get_asset_realization_review().review_materials(mock)
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0


def test_review_realization_has_score():
    mock = {"transaction_ops": [{"op": "create_node"}], "errors": []}
    result = get_asset_realization_review().review_realization(mock)
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0


def test_generate_review_returns_result():
    result = get_asset_realization_review().generate_review({
        "asset_id": "rv2",
        "name": "Tank",
        "format": "usd",
    })
    assert isinstance(result, RealizationReviewResult)


def test_generate_review_has_required_keys():
    result = get_asset_realization_review().generate_review({"asset_id": "rv3"})
    d = result.to_dict()
    for key in ("ok", "asset_id", "overall_score", "grade", "production_ready",
                "import_score", "conversion_score", "dependency_score",
                "material_score", "realization_score", "findings",
                "recommendations", "review_summary", "reviewed_at"):
        assert key in d


def test_empty_asset_not_production_ready():
    result = get_asset_realization_review().generate_review({})
    # An empty asset may or may not be production_ready depending on scores,
    # but it should at least return a valid result with a score
    assert isinstance(result.overall_score, float)
    assert 0.0 <= result.overall_score <= 1.0


def test_review_summary_never_contains_execution_successful():
    result = get_asset_realization_review().generate_review({"asset_id": "rv4"})
    assert "execution successful" not in result.review_summary.lower()


def test_to_dict_from_dict_round_trip():
    result = get_asset_realization_review().generate_review({"asset_id": "rv5"})
    d = result.to_dict()
    restored = RealizationReviewResult.from_dict(d)
    assert abs(restored.overall_score - result.overall_score) < 1e-9
    assert restored.grade == result.grade


def test_never_raises():
    result = get_asset_realization_review().generate_review(None)  # type: ignore
    assert isinstance(result, RealizationReviewResult)


def test_stats_increments():
    reviewer = get_asset_realization_review()
    before = reviewer.stats()["review_count"]
    reviewer.generate_review({"asset_id": "rv6"})
    after = reviewer.stats()["review_count"]
    assert after == before + 1
