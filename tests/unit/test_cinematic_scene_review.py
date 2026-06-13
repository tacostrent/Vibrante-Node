"""
Tests for src.runtime.cinematic_scene_review
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.cinematic_scene_review import (
    CinematicSceneReview,
    get_cinematic_scene_review,
    reset_cinematic_scene_review_for_tests,
    _CINEMATIC_SCORE_WEIGHTS,
    _CINEMATIC_GRADE_THRESHOLDS,
    _CINEMATIC_CRITIQUES,
    _CRITICAL_KEYWORDS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_cinematic_scene_review_for_tests()
    yield
    reset_cinematic_scene_review_for_tests()


def _full_scene_data():
    return {
        "zones": {
            "hero_area":  ["robot_1"],
            "midground":  ["crate_1"],
            "background": ["wall_1"],
        },
        "lighting_plan": {
            "key_strategy":   {"target_zone": "hero_area", "intensity": 2.5},
            "rim_strategy":   {"intensity": 1.5},
            "practical_lighting": {"count": 3},
            "volumetric":     {"enabled": True, "density": 0.05},
            "balance":        {"balance_score": 0.85},
        },
        "camera_plan": {
            "targets": [{"shot_type": "hero_focus", "priority": 1},
                        {"shot_type": "wide_establishing", "priority": 2}],
            "readability": {"readability_score": 0.9},
        },
        "atmosphere_plan": {
            "recommended_density": 0.04,
        },
    }


def _empty_scene_data():
    return {
        "zones": {"hero_area": [], "midground": [], "background": []},
        "lighting_plan": None,
        "camera_plan": None,
        "atmosphere_plan": None,
    }


def _zones_full():
    return {"hero_area": ["robot_1"], "midground": ["crate_1"], "background": ["wall_1"]}


def _zones_empty():
    return {"hero_area": [], "midground": [], "background": []}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_cinematic_scene_review()
    b = get_cinematic_scene_review()
    assert a is b


def test_reset_creates_new():
    a = get_cinematic_scene_review()
    reset_cinematic_scene_review_for_tests()
    b = get_cinematic_scene_review()
    assert a is not b


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_score_weights_sum_to_one():
    total = sum(_CINEMATIC_SCORE_WEIGHTS.values())
    assert total == pytest.approx(1.0)


def test_score_weights_has_all_dimensions():
    for dim in ("storytelling", "depth", "atmosphere", "lighting", "camera"):
        assert dim in _CINEMATIC_SCORE_WEIGHTS


def test_grade_thresholds_have_abcd():
    for grade in ("A", "B", "C", "D"):
        assert grade in _CINEMATIC_GRADE_THRESHOLDS


def test_critiques_are_all_specific():
    generic_phrases = ("execution successful", "completed successfully", "stage completed")
    for key, msg in _CINEMATIC_CRITIQUES.items():
        for phrase in generic_phrases:
            assert phrase.lower() not in msg.lower(), \
                f"Critique '{key}' contains generic phrase '{phrase}'"


def test_critical_keywords_nonempty():
    assert len(_CRITICAL_KEYWORDS) > 0


# ---------------------------------------------------------------------------
# evaluate_cinematic_quality
# ---------------------------------------------------------------------------

def test_cinematic_quality_returns_dict():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_full_scene_data())
    assert isinstance(result, dict)


def test_cinematic_quality_has_required_keys():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_full_scene_data())
    for key in ("overall_score", "grade", "dimensions", "findings",
                "recommendations", "generated_at"):
        assert key in result, f"Missing key: {key}"


def test_cinematic_quality_overall_score_range():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_full_scene_data())
    assert 0.0 <= result["overall_score"] <= 1.0


def test_cinematic_quality_grade_is_letter():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_full_scene_data())
    assert result["grade"] in ("A", "B", "C", "D", "F")


def test_cinematic_quality_dimensions_has_all_keys():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_full_scene_data())
    for dim in ("storytelling", "depth", "atmosphere", "lighting", "camera"):
        assert dim in result["dimensions"], f"Missing dimension: {dim}"


def test_cinematic_quality_dimensions_are_floats():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_full_scene_data())
    for dim, val in result["dimensions"].items():
        assert isinstance(val, float), f"Dimension {dim} is not float"


def test_cinematic_quality_findings_is_list():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_full_scene_data())
    assert isinstance(result["findings"], list)


def test_cinematic_quality_recommendations_is_list():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_full_scene_data())
    assert isinstance(result["recommendations"], list)


def test_cinematic_quality_empty_scene_low_score():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_empty_scene_data())
    assert result["overall_score"] < 0.5


def test_cinematic_quality_empty_scene_adds_no_camera_finding():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_empty_scene_data())
    assert any("camera" in f.lower() or "undefined" in f.lower() for f in result["findings"])


def test_cinematic_quality_no_lighting_adds_finding():
    r = CinematicSceneReview()
    data = _full_scene_data()
    data["lighting_plan"] = None
    result = r.evaluate_cinematic_quality(data)
    assert any("light" in f.lower() or "illumination" in f.lower()
               for f in result["findings"])


def test_cinematic_quality_no_camera_score_zero():
    r = CinematicSceneReview()
    data = _full_scene_data()
    data["camera_plan"] = None
    result = r.evaluate_cinematic_quality(data)
    assert result["dimensions"]["camera"] == pytest.approx(0.0)


def test_cinematic_quality_lighting_balance_score_used():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_full_scene_data())
    # balance_score = 0.85 in _full_scene_data
    assert result["dimensions"]["lighting"] == pytest.approx(0.85)


def test_cinematic_quality_camera_readability_score_used():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_full_scene_data())
    # readability_score = 0.9 in _full_scene_data
    assert result["dimensions"]["camera"] == pytest.approx(0.9)


def test_cinematic_quality_grade_f_for_empty():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_empty_scene_data())
    assert result["grade"] == "F"


def test_cinematic_quality_generated_at_is_float():
    r = CinematicSceneReview()
    result = r.evaluate_cinematic_quality(_full_scene_data())
    assert isinstance(result["generated_at"], float)


# ---------------------------------------------------------------------------
# evaluate_visual_storytelling
# ---------------------------------------------------------------------------

def test_storytelling_returns_dict():
    r = CinematicSceneReview()
    result = r.evaluate_visual_storytelling(_zones_full())
    assert isinstance(result, dict)


def test_storytelling_has_required_keys():
    r = CinematicSceneReview()
    result = r.evaluate_visual_storytelling(_zones_full())
    for key in ("score", "has_hero", "hero_lit", "has_camera", "findings", "strengths"):
        assert key in result, f"Missing key: {key}"


def test_storytelling_no_hero_zero_score():
    r = CinematicSceneReview()
    result = r.evaluate_visual_storytelling(_zones_empty())
    assert result["has_hero"] is False
    assert result["score"] < 0.4


def test_storytelling_hero_present_adds_score():
    r = CinematicSceneReview()
    result = r.evaluate_visual_storytelling(_zones_full())
    assert result["has_hero"] is True
    assert result["score"] >= 0.4


def test_storytelling_hero_lit_when_key_targets_hero():
    r = CinematicSceneReview()
    lighting = {"key_strategy": {"target_zone": "hero_area", "intensity": 2.5}}
    result = r.evaluate_visual_storytelling(_zones_full(), lighting)
    assert result["hero_lit"] is True


def test_storytelling_hero_not_lit_when_key_misses():
    r = CinematicSceneReview()
    lighting = {"key_strategy": {"target_zone": "midground", "intensity": 2.5}}
    result = r.evaluate_visual_storytelling(_zones_full(), lighting)
    assert result["hero_lit"] is False


def test_storytelling_camera_present():
    r = CinematicSceneReview()
    camera = {"targets": [{"shot_type": "hero_focus", "priority": 1}]}
    result = r.evaluate_visual_storytelling(_zones_full(), None, camera)
    assert result["has_camera"] is True


def test_storytelling_no_camera():
    r = CinematicSceneReview()
    result = r.evaluate_visual_storytelling(_zones_full(), None, None)
    assert result["has_camera"] is False


def test_storytelling_hero_focus_shot_adds_score():
    r = CinematicSceneReview()
    lighting = {"key_strategy": {"target_zone": "hero_area", "intensity": 2.5}}
    camera = {"targets": [{"shot_type": "hero_focus", "priority": 1},
                          {"shot_type": "wide_establishing", "priority": 2}]}
    result = r.evaluate_visual_storytelling(_zones_full(), lighting, camera)
    assert result["score"] >= 1.0


def test_storytelling_score_capped_at_1():
    r = CinematicSceneReview()
    lighting = {"key_strategy": {"target_zone": "hero_area", "intensity": 2.5}}
    camera = {"targets": [{"shot_type": "hero_focus", "priority": 1}]}
    result = r.evaluate_visual_storytelling(_zones_full(), lighting, camera)
    assert result["score"] <= 1.0


def test_storytelling_no_hero_adds_finding():
    r = CinematicSceneReview()
    result = r.evaluate_visual_storytelling(_zones_empty())
    assert len(result["findings"]) > 0
    assert any("focal" in f.lower() or "hero" in f.lower() for f in result["findings"])


# ---------------------------------------------------------------------------
# evaluate_depth_readability
# ---------------------------------------------------------------------------

def test_depth_readability_returns_dict():
    r = CinematicSceneReview()
    result = r.evaluate_depth_readability(_zones_full())
    assert isinstance(result, dict)


def test_depth_readability_has_required_keys():
    r = CinematicSceneReview()
    result = r.evaluate_depth_readability(_zones_full())
    for key in ("score", "zone_count", "has_atmosphere", "findings", "strengths"):
        assert key in result, f"Missing key: {key}"


def test_depth_readability_three_zones_count():
    r = CinematicSceneReview()
    result = r.evaluate_depth_readability(_zones_full())
    assert result["zone_count"] == 3


def test_depth_readability_no_zones_count():
    r = CinematicSceneReview()
    result = r.evaluate_depth_readability(_zones_empty())
    assert result["zone_count"] == 0


def test_depth_readability_atmosphere_enhances():
    r = CinematicSceneReview()
    atm = {"recommended_density": 0.04}
    result = r.evaluate_depth_readability(_zones_full(), atm)
    assert result["has_atmosphere"] is True


def test_depth_readability_no_atmosphere():
    r = CinematicSceneReview()
    result = r.evaluate_depth_readability(_zones_full(), None)
    assert result["has_atmosphere"] is False


def test_depth_readability_score_increases_with_zones():
    r = CinematicSceneReview()
    one_zone = r.evaluate_depth_readability({"hero_area": ["r1"]})
    three_zones = r.evaluate_depth_readability(_zones_full())
    assert three_zones["score"] >= one_zone["score"]


def test_depth_readability_fog_too_dense_adds_finding():
    r = CinematicSceneReview()
    atm = {"recommended_density": 0.09}
    result = r.evaluate_depth_readability(_zones_full(), atm)
    assert any("dense" in f.lower() or "obscured" in f.lower() for f in result["findings"])


def test_depth_readability_correct_density_adds_strength():
    r = CinematicSceneReview()
    atm = {"recommended_density": 0.04}
    result = r.evaluate_depth_readability(_zones_full(), atm)
    assert len(result["strengths"]) > 0


def test_depth_readability_three_zones_adds_strength():
    r = CinematicSceneReview()
    atm = {"recommended_density": 0.04}
    result = r.evaluate_depth_readability(_zones_full(), atm)
    assert any("depth" in s.lower() or "separation" in s.lower() for s in result["strengths"])


# ---------------------------------------------------------------------------
# evaluate_atmosphere_balance
# ---------------------------------------------------------------------------

def test_atmosphere_balance_returns_dict():
    r = CinematicSceneReview()
    result = r.evaluate_atmosphere_balance({"recommended_density": 0.04}, None)
    assert isinstance(result, dict)


def test_atmosphere_balance_has_required_keys():
    r = CinematicSceneReview()
    result = r.evaluate_atmosphere_balance(None, None)
    for key in ("score", "atmosphere_present", "lighting_volumetric",
                "density_appropriate", "findings", "strengths"):
        assert key in result, f"Missing key: {key}"


def test_atmosphere_balance_none_plan_neutral_score():
    r = CinematicSceneReview()
    result = r.evaluate_atmosphere_balance(None, None)
    assert result["score"] == pytest.approx(0.5)


def test_atmosphere_balance_present_adds_score():
    r = CinematicSceneReview()
    atm = {"recommended_density": 0.04}
    result = r.evaluate_atmosphere_balance(atm, None)
    assert result["atmosphere_present"] is True
    assert result["score"] >= 0.6


def test_atmosphere_balance_volumetric_lighting_adds_score():
    r = CinematicSceneReview()
    atm = {"recommended_density": 0.04}
    lighting = {"volumetric": {"enabled": True}}
    result = r.evaluate_atmosphere_balance(atm, lighting)
    assert result["lighting_volumetric"] is True
    assert result["score"] >= 0.8


def test_atmosphere_balance_too_dense_reduces_score():
    r = CinematicSceneReview()
    atm = {"recommended_density": 0.09}
    result = r.evaluate_atmosphere_balance(atm, None)
    assert result["density_appropriate"] is False
    assert len(result["findings"]) > 0


def test_atmosphere_balance_appropriate_density():
    r = CinematicSceneReview()
    atm = {"recommended_density": 0.04}
    result = r.evaluate_atmosphere_balance(atm, None)
    assert result["density_appropriate"] is True


def test_atmosphere_balance_score_range():
    r = CinematicSceneReview()
    atm = {"recommended_density": 0.09}
    result = r.evaluate_atmosphere_balance(atm, None)
    assert 0.0 <= result["score"] <= 1.0


# ---------------------------------------------------------------------------
# generate_cinematic_review
# ---------------------------------------------------------------------------

def test_cinematic_review_returns_dict():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_full_scene_data())
    assert isinstance(result, dict)


def test_cinematic_review_has_required_keys():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_full_scene_data())
    for key in ("production_ready", "overall_score", "grade", "cinematic_quality",
                "storytelling", "depth", "atmosphere", "findings", "strengths",
                "recommendations", "review_summary", "generated_at"):
        assert key in result, f"Missing key: {key}"


def test_cinematic_review_production_ready_is_bool():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_full_scene_data())
    assert isinstance(result["production_ready"], bool)


def test_cinematic_review_empty_scene_not_ready():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_empty_scene_data())
    assert result["production_ready"] is False


def test_cinematic_review_summary_never_generic():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_full_scene_data())
    summary = result["review_summary"].lower()
    for generic in ("execution successful", "completed successfully", "stage completed"):
        assert generic not in summary


def test_cinematic_review_summary_is_specific():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_full_scene_data())
    summary = result["review_summary"]
    # Must contain actual cinematic terms
    cinematic_terms = ("cinematic", "hero", "depth", "lighting", "atmosphere",
                       "readability", "separation", "threshold", "viable")
    assert any(term in summary.lower() for term in cinematic_terms)


def test_cinematic_review_increments_review_count():
    r = CinematicSceneReview()
    r.generate_cinematic_review(_full_scene_data())
    r.generate_cinematic_review(_empty_scene_data())
    assert r.stats()["review_count"] == 2


def test_cinematic_review_findings_deduplicated():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_empty_scene_data())
    # No duplicate strings
    assert len(result["findings"]) == len(set(result["findings"]))


def test_cinematic_review_grade_f_for_empty_scene():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_empty_scene_data())
    assert result["grade"] == "F"


def test_cinematic_review_score_range():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_full_scene_data())
    assert 0.0 <= result["overall_score"] <= 1.0


def test_cinematic_review_production_ready_requires_score_threshold():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_empty_scene_data())
    # Empty scene has critical findings → not production_ready regardless of score
    if result["production_ready"]:
        assert result["overall_score"] >= 0.7


def test_cinematic_review_critical_findings_block_ready():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_empty_scene_data())
    critical = [f for f in result["findings"]
                if any(kw in f.lower() for kw in _CRITICAL_KEYWORDS)]
    if len(critical) > 0:
        assert result["production_ready"] is False


def test_cinematic_review_generated_at_is_float():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_full_scene_data())
    assert isinstance(result["generated_at"], float)


def test_cinematic_review_sub_dicts_have_score():
    r = CinematicSceneReview()
    result = r.generate_cinematic_review(_full_scene_data())
    for sub in ("storytelling", "depth", "atmosphere"):
        assert "score" in result[sub], f"Sub-review '{sub}' missing score"


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_has_review_count():
    r = CinematicSceneReview()
    assert "review_count" in r.stats()


def test_stats_starts_zero():
    r = CinematicSceneReview()
    assert r.stats()["review_count"] == 0


def test_stats_increments_on_review():
    r = CinematicSceneReview()
    r.generate_cinematic_review(_full_scene_data())
    assert r.stats()["review_count"] == 1


def test_stats_does_not_increment_on_evaluate_quality():
    r = CinematicSceneReview()
    r.evaluate_cinematic_quality(_full_scene_data())
    # Only generate_cinematic_review increments the counter
    assert r.stats()["review_count"] == 0
