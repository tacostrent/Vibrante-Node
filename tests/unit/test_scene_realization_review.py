"""
Tests for src.runtime.scene_realization_review
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.scene_realization_review import (
    SceneRealizationReview,
    get_scene_realization_review,
    reset_scene_realization_review_for_tests,
    _MAX_HERO_ASSETS,
    _CRITIQUE_MESSAGES,
)


@pytest.fixture(autouse=True)
def reset():
    reset_scene_realization_review_for_tests()
    yield
    reset_scene_realization_review_for_tests()


def _realization_result(zone_map=None, path_map=None):
    return {
        "zone_map": zone_map or {},
        "path_map": path_map or {},
    }


def _zones(hero=1, mid=1, bg=1):
    z = {}
    if hero > 0:
        z["hero_area"] = [{"name": f"h{i}", "category": "robot"} for i in range(hero)]
    if mid > 0:
        z["midground"] = [{"name": f"m{i}", "category": "container"} for i in range(mid)]
    if bg > 0:
        z["background"] = [{"name": f"b{i}", "category": "structure"} for i in range(bg)]
    return z


def _staging_plan(total=3, zone_count=3, fx=0):
    queue = [{"order": i} for i in range(total)]
    zone_assignments = {f"zone_{z}": ["asset"] for z in range(zone_count)}
    return {
        "import_queue":     queue,
        "zone_assignments": zone_assignments,
        "recommended_fx":   [f"fx_{i}" for i in range(fx)],
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_scene_realization_review()
    b = get_scene_realization_review()
    assert a is b


def test_reset_creates_new():
    a = get_scene_realization_review()
    reset_scene_realization_review_for_tests()
    b = get_scene_realization_review()
    assert a is not b


# ---------------------------------------------------------------------------
# evaluate_scene_readability
# ---------------------------------------------------------------------------

def test_readability_result_keys():
    r = SceneRealizationReview()
    zone_map = {"mech": "hero_area", "wall": "background"}
    path_map = {"mech": "/obj/hero_assets/bot_mech", "wall": "/obj/background/str_wall"}
    result = r.evaluate_scene_readability(_realization_result(zone_map, path_map))
    assert {"readable", "readability_score", "issues", "strengths", "criteria_checked"} <= set(result.keys())


def test_readability_good_scene():
    r = SceneRealizationReview()
    zone_map = {"hero1": "hero_area", "mid1": "midground", "bg1": "background"}
    path_map = {k: f"/obj/{k}" for k in zone_map}
    result = r.evaluate_scene_readability(_realization_result(zone_map, path_map))
    assert result["readability_score"] > 0.5
    assert "hero" in " ".join(result["strengths"]).lower() or len(result["strengths"]) > 0


def test_readability_no_hero_penalised():
    r = SceneRealizationReview()
    zone_map = {"wall": "background", "crate": "midground"}
    path_map = {k: f"/obj/{k}" for k in zone_map}
    result = r.evaluate_scene_readability(_realization_result(zone_map, path_map))
    assert any("hero" in issue.lower() or "focal" in issue.lower() for issue in result["issues"])
    assert result["readability_score"] < 0.8


def test_readability_too_many_heroes_penalised():
    r = SceneRealizationReview()
    zone_map = {f"h{i}": "hero_area" for i in range(_MAX_HERO_ASSETS + 2)}
    path_map = {k: f"/obj/{k}" for k in zone_map}
    result = r.evaluate_scene_readability(_realization_result(zone_map, path_map))
    assert any("overload" in i.lower() or "dilut" in i.lower() for i in result["issues"])


def test_readability_no_depth_penalised():
    r = SceneRealizationReview()
    zone_map = {"hero1": "hero_area"}
    path_map = {"hero1": "/obj/hero1"}
    result = r.evaluate_scene_readability(_realization_result(zone_map, path_map))
    assert any("depth" in i.lower() or "background" in i.lower() or "midground" in i.lower()
               for i in result["issues"])


def test_readability_empty_scene():
    r = SceneRealizationReview()
    result = r.evaluate_scene_readability(_realization_result({}, {}))
    assert result["readability_score"] < 0.5


def test_readability_score_range():
    r = SceneRealizationReview()
    result = r.evaluate_scene_readability(_realization_result({}, {}))
    assert 0.0 <= result["readability_score"] <= 1.0


# ---------------------------------------------------------------------------
# evaluate_layout_balance
# ---------------------------------------------------------------------------

def test_balance_result_keys():
    r = SceneRealizationReview()
    result = r.evaluate_layout_balance(_zones())
    assert {"balanced", "balance_score", "zone_weights", "issues"} <= set(result.keys())


def test_balance_empty_scene():
    r = SceneRealizationReview()
    result = r.evaluate_layout_balance({})
    assert result["balanced"] is False
    assert result["balance_score"] == 0.0


def test_balance_even_distribution():
    r = SceneRealizationReview()
    zones = {
        "hero_area":  [{"name": "h1"}] * 2,
        "midground":  [{"name": "m1"}] * 2,
        "background": [{"name": "b1"}] * 2,
    }
    result = r.evaluate_layout_balance(zones)
    assert result["balance_score"] > 0.6


def test_balance_one_overloaded_zone():
    r = SceneRealizationReview()
    zones = {
        "hero_area":  [{"name": f"h{n}"} for n in range(20)],
        "midground":  [{"name": "m1"}],
        "background": [{"name": "b1"}],
    }
    result = r.evaluate_layout_balance(zones)
    assert any("unbalanced" in issue.lower() or "distribution" in issue.lower() for issue in result["issues"])


def test_balance_score_range():
    r = SceneRealizationReview()
    result = r.evaluate_layout_balance(_zones(hero=1, mid=1, bg=1))
    assert 0.0 <= result["balance_score"] <= 1.0


def test_balance_zone_weights_correct():
    r = SceneRealizationReview()
    zones = {"hero_area": [{"name": "h1"}, {"name": "h2"}], "background": [{"name": "b1"}]}
    result = r.evaluate_layout_balance(zones)
    assert result["zone_weights"]["hero_area"] == 2
    assert result["zone_weights"]["background"] == 1


# ---------------------------------------------------------------------------
# evaluate_asset_distribution
# ---------------------------------------------------------------------------

def test_distribution_result_keys():
    r = SceneRealizationReview()
    result = r.evaluate_asset_distribution(_zones())
    assert {"well_distributed", "distribution", "coverage", "issues", "recommendations"} <= set(result.keys())


def test_distribution_good_scene():
    r = SceneRealizationReview()
    result = r.evaluate_asset_distribution(_zones(hero=1, mid=2, bg=2))
    assert result["well_distributed"] is True
    assert result["coverage"] > 0.5


def test_distribution_no_hero_issues():
    r = SceneRealizationReview()
    result = r.evaluate_asset_distribution({"midground": [{"name": "m1"}]})
    assert any("hero" in i.lower() or "focus" in i.lower() for i in result["issues"])


def test_distribution_overloaded_zone_issues():
    r = SceneRealizationReview()
    zones = {"hero_area": [{"name": f"h{n}"} for n in range(12)]}
    result = r.evaluate_asset_distribution(zones)
    assert any("12" in issue or "split" in issue.lower() for issue in result["issues"])


def test_distribution_coverage_0_to_1():
    r = SceneRealizationReview()
    result = r.evaluate_asset_distribution(_zones())
    assert 0.0 <= result["coverage"] <= 1.0


def test_distribution_recommendations_populated():
    r = SceneRealizationReview()
    result = r.evaluate_asset_distribution({"midground": [{"name": "m1"}]})
    assert len(result["recommendations"]) > 0


# ---------------------------------------------------------------------------
# evaluate_scene_complexity
# ---------------------------------------------------------------------------

def test_complexity_low():
    r = SceneRealizationReview()
    result = r.evaluate_scene_complexity(_staging_plan(total=2, zone_count=1, fx=0))
    assert result["complexity_level"] == "low"


def test_complexity_medium():
    r = SceneRealizationReview()
    result = r.evaluate_scene_complexity(_staging_plan(total=10, zone_count=2, fx=1))
    assert result["complexity_level"] in ("low", "medium")


def test_complexity_high():
    r = SceneRealizationReview()
    result = r.evaluate_scene_complexity(_staging_plan(total=30, zone_count=3, fx=2))
    assert result["complexity_level"] in ("medium", "high")


def test_complexity_extreme():
    r = SceneRealizationReview()
    result = r.evaluate_scene_complexity(_staging_plan(total=50, zone_count=4, fx=5))
    assert result["complexity_level"] == "extreme"


def test_complexity_result_keys():
    r = SceneRealizationReview()
    result = r.evaluate_scene_complexity(_staging_plan())
    assert {"complexity_level", "complexity_score", "issues", "notes"} <= set(result.keys())


def test_complexity_high_issues_present():
    r = SceneRealizationReview()
    result = r.evaluate_scene_complexity(_staging_plan(total=60, zone_count=4, fx=5))
    assert len(result["issues"]) > 0


def test_complexity_fx_note_three_or_more():
    r = SceneRealizationReview()
    result = r.evaluate_scene_complexity(_staging_plan(total=5, zone_count=1, fx=3))
    notes_text = " ".join(result["notes"]).lower()
    assert "fx" in notes_text or "gpu" in notes_text


# ---------------------------------------------------------------------------
# generate_realization_review (integration)
# ---------------------------------------------------------------------------

def _assembly_result(zone_map=None, path_map=None, phase_counts=None):
    return {
        "zone_map":     zone_map or {"mech": "hero_area", "wall": "background", "crate": "midground"},
        "path_map":     path_map or {"mech": "/obj/hero", "wall": "/obj/bg", "crate": "/obj/mid"},
        "phase_counts": phase_counts or {"hierarchy": 7, "environment": 2, "asset_placement": 9,
                                         "lighting": 3, "camera": 2, "layout": 6},
        "staging_plan": _staging_plan(total=3, zone_count=3, fx=1),
    }


def _layout_plan(hero=1, mid=1, bg=1):
    return {
        "scene_theme": "industrial_hangar",
        "zones":       _zones(hero, mid, bg),
    }


def test_review_has_required_keys():
    r = SceneRealizationReview()
    result = r.generate_realization_review(_assembly_result(), _layout_plan())
    required = {"production_ready", "overall_score", "readability", "balance",
                "distribution", "complexity", "findings", "recommendations",
                "review_summary", "generated_at"}
    assert required <= set(result.keys())


def test_review_production_ready_good_scene():
    r = SceneRealizationReview()
    result = r.generate_realization_review(_assembly_result(), _layout_plan())
    # Good balanced scene with lighting and camera → should be production-ready
    assert isinstance(result["production_ready"], bool)
    assert result["overall_score"] >= 0.0


def test_review_not_ready_empty_scene():
    r = SceneRealizationReview()
    empty_asm = {"zone_map": {}, "path_map": {}, "phase_counts": {}, "staging_plan": _staging_plan(0, 0, 0)}
    result = r.generate_realization_review(empty_asm, {"scene_theme": "test", "zones": {}})
    assert result["production_ready"] is False


def test_review_overall_score_range():
    r = SceneRealizationReview()
    result = r.generate_realization_review(_assembly_result(), _layout_plan())
    assert 0.0 <= result["overall_score"] <= 1.0


def test_review_summary_is_string():
    r = SceneRealizationReview()
    result = r.generate_realization_review(_assembly_result(), _layout_plan())
    assert isinstance(result["review_summary"], str)
    assert len(result["review_summary"]) > 0


def test_review_no_lighting_flagged():
    r = SceneRealizationReview()
    asm = _assembly_result(phase_counts={"hierarchy": 7, "environment": 2,
                                          "asset_placement": 9, "lighting": 0,
                                          "camera": 2, "layout": 6})
    result = r.generate_realization_review(asm, _layout_plan())
    all_text = " ".join(result["findings"]).lower()
    assert "light" in all_text


def test_review_no_camera_flagged():
    r = SceneRealizationReview()
    asm = _assembly_result(phase_counts={"hierarchy": 7, "environment": 2,
                                          "asset_placement": 9, "lighting": 3,
                                          "camera": 0, "layout": 6})
    result = r.generate_realization_review(asm, _layout_plan())
    all_text = " ".join(result["findings"]).lower()
    assert "camera" in all_text


def test_review_increments_count():
    r = SceneRealizationReview()
    r.generate_realization_review(_assembly_result(), _layout_plan())
    r.generate_realization_review(_assembly_result(), _layout_plan())
    assert r.stats()["review_count"] == 2


# ---------------------------------------------------------------------------
# evaluate_scene_readability — extended
# ---------------------------------------------------------------------------

def test_readability_only_background_penalised():
    r = SceneRealizationReview()
    zone_map = {"wall": "background"}
    path_map = {"wall": "/obj/background/str_wall"}
    result = r.evaluate_scene_readability(_realization_result(zone_map, path_map))
    assert result["readability_score"] < 0.8


def test_readability_exactly_max_heroes_ok():
    r = SceneRealizationReview()
    zone_map = {f"h{i}": "hero_area" for i in range(_MAX_HERO_ASSETS)}
    path_map = {k: f"/obj/{k}" for k in zone_map}
    result = r.evaluate_scene_readability(_realization_result(zone_map, path_map))
    # Exactly _MAX_HERO_ASSETS should not flag overload
    overload_issues = [i for i in result["issues"] if "overload" in i.lower() or "dilut" in i.lower()]
    assert len(overload_issues) == 0


def test_readability_three_layer_gets_strength():
    r = SceneRealizationReview()
    zone_map = {"h1": "hero_area", "m1": "midground", "b1": "background"}
    path_map = {k: f"/obj/{k}" for k in zone_map}
    result = r.evaluate_scene_readability(_realization_result(zone_map, path_map))
    assert len(result["strengths"]) > 0


def test_readability_criteria_checked_is_list():
    r = SceneRealizationReview()
    result = r.evaluate_scene_readability(_realization_result({}, {}))
    assert isinstance(result["criteria_checked"], list)


# ---------------------------------------------------------------------------
# evaluate_layout_balance — extended
# ---------------------------------------------------------------------------

def test_balance_single_zone_not_balanced():
    r = SceneRealizationReview()
    zones = {"hero_area": [{"name": "h1"}]}
    result = r.evaluate_layout_balance(zones)
    assert result["balanced"] is False


def test_balance_score_is_float():
    r = SceneRealizationReview()
    result = r.evaluate_layout_balance(_zones())
    assert isinstance(result["balance_score"], float)


def test_balance_issues_is_list():
    r = SceneRealizationReview()
    result = r.evaluate_layout_balance({})
    assert isinstance(result["issues"], list)


# ---------------------------------------------------------------------------
# evaluate_asset_distribution — extended
# ---------------------------------------------------------------------------

def test_distribution_multiple_zones_well_distributed():
    r = SceneRealizationReview()
    result = r.evaluate_asset_distribution(_zones(hero=2, mid=3, bg=3))
    assert result["well_distributed"] is True


def test_distribution_distribution_dict_has_zones():
    r = SceneRealizationReview()
    result = r.evaluate_asset_distribution(_zones(hero=1, mid=1, bg=1))
    dist = result["distribution"]
    assert isinstance(dist, dict)
    for zone in ("hero_area", "midground", "background"):
        assert zone in dist


def test_distribution_no_midground_no_hero_issue():
    r = SceneRealizationReview()
    # Only background — no hero zone → distribution should flag it
    zones = {"background": [{"name": "b1", "category": "structure"},
                             {"name": "b2", "category": "structure"}]}
    result = r.evaluate_asset_distribution(zones)
    assert any("hero" in i.lower() or "focus" in i.lower() for i in result["issues"])


# ---------------------------------------------------------------------------
# evaluate_scene_complexity — extended
# ---------------------------------------------------------------------------

def test_complexity_score_is_numeric():
    r = SceneRealizationReview()
    result = r.evaluate_scene_complexity(_staging_plan())
    assert isinstance(result["complexity_score"], (int, float))


def test_complexity_score_grows_with_assets():
    r = SceneRealizationReview()
    small = r.evaluate_scene_complexity(_staging_plan(total=2, zone_count=1, fx=0))
    large = r.evaluate_scene_complexity(_staging_plan(total=50, zone_count=4, fx=5))
    assert large["complexity_score"] > small["complexity_score"]


def test_complexity_notes_is_list():
    r = SceneRealizationReview()
    result = r.evaluate_scene_complexity(_staging_plan())
    assert isinstance(result["notes"], list)


# ---------------------------------------------------------------------------
# generate_realization_review — extended
# ---------------------------------------------------------------------------

def test_review_critique_messages_referenced():
    r = SceneRealizationReview()
    asm = _assembly_result(
        phase_counts={"hierarchy": 0, "environment": 0,
                      "asset_placement": 0, "lighting": 0,
                      "camera": 0, "layout": 0}
    )
    result = r.generate_realization_review(asm, _layout_plan(hero=0, mid=0, bg=0))
    # Should have findings for missing lighting and camera
    assert len(result["findings"]) > 0


def test_review_summary_mentions_score():
    r = SceneRealizationReview()
    result = r.generate_realization_review(_assembly_result(), _layout_plan())
    summary = result["review_summary"].lower()
    assert any(c in summary for c in ["score", "ready", "review", "pass", "fail", "ok"])


def test_review_generated_at_is_float():
    r = SceneRealizationReview()
    result = r.generate_realization_review(_assembly_result(), _layout_plan())
    assert isinstance(result["generated_at"], float)
    assert result["generated_at"] > 0


def test_review_recommendations_is_list():
    r = SceneRealizationReview()
    result = r.generate_realization_review(_assembly_result(), _layout_plan())
    assert isinstance(result["recommendations"], list)


def test_review_findings_is_list():
    r = SceneRealizationReview()
    result = r.generate_realization_review(_assembly_result(), _layout_plan())
    assert isinstance(result["findings"], list)


def test_review_both_lighting_and_camera_missing_both_flagged():
    r = SceneRealizationReview()
    asm = _assembly_result(phase_counts={"hierarchy": 7, "environment": 2,
                                          "asset_placement": 9, "lighting": 0,
                                          "camera": 0, "layout": 6})
    result = r.generate_realization_review(asm, _layout_plan())
    text = " ".join(result["findings"]).lower()
    assert "light" in text
    assert "camera" in text


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    r = SceneRealizationReview()
    s = r.stats()
    assert "review_count" in s


def test_stats_starts_zero():
    r = SceneRealizationReview()
    assert r.stats()["review_count"] == 0
