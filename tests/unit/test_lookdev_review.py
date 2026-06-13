import pytest
from src.runtime.lookdev import (
    LookdevReviewResult,
    get_lookdev_review,
    reset_lookdev_review_for_tests,
    reset_material_library_for_tests,
    reset_renderer_profiles_for_tests,
    reset_lookdev_patterns_for_tests,
)

_GOOD_LOOKDEV = {
    "environment": "industrial_hangar",
    "renderer": "usd_preview_surface",
    "materials": ["industrial_metal", "weathered_concrete", "industrial_rubber"],
    "assignments": [
        {"asset_id": "a1", "material_name": "industrial_metal", "renderer": "usd_preview_surface"},
        {"asset_id": "a2", "material_name": "weathered_concrete", "renderer": "usd_preview_surface"},
    ],
}


@pytest.fixture(autouse=True)
def reset_all():
    reset_lookdev_review_for_tests()
    reset_material_library_for_tests()
    reset_renderer_profiles_for_tests()
    reset_lookdev_patterns_for_tests()
    yield
    reset_lookdev_review_for_tests()
    reset_material_library_for_tests()
    reset_renderer_profiles_for_tests()
    reset_lookdev_patterns_for_tests()


def test_singleton_identity():
    assert get_lookdev_review() is get_lookdev_review()


def test_review_lookdev_returns_result():
    result = get_lookdev_review().review_lookdev(_GOOD_LOOKDEV)
    assert isinstance(result, LookdevReviewResult)


def test_review_score_range():
    result = get_lookdev_review().review_lookdev(_GOOD_LOOKDEV)
    assert 0.0 <= result.score <= 1.0


def test_review_grade_valid():
    result = get_lookdev_review().review_lookdev(_GOOD_LOOKDEV)
    assert result.grade in ("A", "B", "C", "D", "F")


def test_grade_a_for_high_score():
    result = get_lookdev_review().review_lookdev(_GOOD_LOOKDEV)
    if result.score >= 0.85:
        assert result.grade == "A"


def test_grade_f_for_empty():
    result = get_lookdev_review().review_lookdev({})
    assert result.grade in ("F", "D", "C")


def test_production_ready_true_above_threshold():
    result = get_lookdev_review().review_lookdev(_GOOD_LOOKDEV)
    if result.score >= 0.70 and not result.findings:
        assert result.production_ready is True


def test_production_ready_false_empty():
    result = get_lookdev_review().review_lookdev({})
    assert result.production_ready is False


def test_invalid_renderer_blocks_production():
    lookdev = {**_GOOD_LOOKDEV, "renderer": "invalid_renderer"}
    result = get_lookdev_review().review_lookdev(lookdev)
    assert result.production_ready is False
    assert any("invalid" in f.lower() or "renderer" in f.lower() for f in result.findings)


def test_review_material_consistency_empty():
    r = get_lookdev_review().review_material_consistency([])
    assert r["score"] == 0.0
    assert len(r["findings"]) > 0


def test_review_material_consistency_valid():
    r = get_lookdev_review().review_material_consistency([
        {"material_name": "industrial_metal"},
        {"material_name": "concrete"},
    ])
    assert r["score"] > 0.0


def test_review_environment_coherence_no_env():
    r = get_lookdev_review().review_environment_coherence({"materials": ["glass"]})
    assert r["score"] < 1.0


def test_review_renderer_compatibility_valid():
    r = get_lookdev_review().review_renderer_compatibility({}, "arnold")
    assert r["score"] > 0.0
    assert len(r["findings"]) == 0


def test_review_renderer_compatibility_invalid():
    r = get_lookdev_review().review_renderer_compatibility({}, "bad_renderer")
    assert r["score"] == 0.0
    assert len(r["findings"]) > 0


def test_result_to_dict_keys():
    result = LookdevReviewResult(score=0.8, grade="B", production_ready=True)
    d = result.to_dict()
    for key in ("review_id", "score", "grade", "production_ready",
                "material_consistency", "environment_coherence",
                "renderer_compatibility", "visual_quality",
                "findings", "recommendations", "reviewed_at"):
        assert key in d


def test_result_from_dict_round_trip():
    r = LookdevReviewResult(score=0.75, grade="B", production_ready=True, findings=["f1"])
    restored = LookdevReviewResult.from_dict(r.to_dict())
    assert restored.score == 0.75
    assert restored.grade == "B"
    assert restored.findings == ["f1"]


def test_never_raises_none():
    result = get_lookdev_review().review_lookdev(None)  # type: ignore
    assert isinstance(result, LookdevReviewResult)
