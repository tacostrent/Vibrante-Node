"""Tests for StudioStandards (Tier 11 — §31)."""
import pytest
from src.runtime.studio.studio_standards import (
    StudioStandards,
    get_studio_standards,
    reset_studio_standards_for_tests,
    _BUILTIN_STANDARDS,
)


@pytest.fixture(autouse=True)
def reset():
    reset_studio_standards_for_tests()
    yield
    reset_studio_standards_for_tests()


def test_singleton():
    assert get_studio_standards() is get_studio_standards()


# ---------------------------------------------------------------------------
# Built-in standards
# ---------------------------------------------------------------------------

def test_builtin_count():
    ss = StudioStandards()
    builtins = ss.list_standards(builtin_only=True)
    assert len(builtins) == len(_BUILTIN_STANDARDS)


def test_minimum_review_score_present():
    ss = StudioStandards()
    s = ss.get_standard("minimum_review_score")
    assert s is not None
    assert s["value"] == 0.75
    assert s["builtin"] is True
    assert s["required"] is True


def test_approved_lighting_styles_present():
    ss = StudioStandards()
    styles = ss.get_standard_value("approved_lighting_styles", [])
    assert isinstance(styles, list)
    assert "cinematic_industrial" in styles


def test_approved_camera_modes_present():
    ss = StudioStandards()
    modes = ss.get_standard_value("approved_camera_modes", [])
    assert "cinematic_push_in" in modes


def test_approved_atmosphere_types_present():
    ss = StudioStandards()
    types = ss.get_standard_value("approved_atmosphere_types", [])
    assert "industrial_fog" in types


def test_approved_workflows_present():
    ss = StudioStandards()
    wfs = ss.get_standard_value("approved_workflows", [])
    assert "industrial_hangar_pack" in wfs


def test_hero_zone_max_assets():
    ss = StudioStandards()
    assert ss.get_standard_value("hero_zone_max_assets") == 3


# ---------------------------------------------------------------------------
# register_standard
# ---------------------------------------------------------------------------

def test_register_custom_standard():
    ss = StudioStandards()
    ss.register_standard("custom_threshold", "review_threshold", 0.80, "My threshold")
    s = ss.get_standard("custom_threshold")
    assert s["value"] == 0.80
    assert s["builtin"] is False


def test_register_builtin_name_raises():
    ss = StudioStandards()
    with pytest.raises(ValueError, match="override built-in"):
        ss.register_standard("minimum_review_score", "review_threshold", 0.99)


# ---------------------------------------------------------------------------
# update_standard
# ---------------------------------------------------------------------------

def test_update_builtin_value():
    ss = StudioStandards()
    ok = ss.update_standard("minimum_review_score", 0.85)
    assert ok is True
    assert ss.get_standard_value("minimum_review_score") == 0.85
    s = ss.get_standard("minimum_review_score")
    assert s.get("overridden") is True


def test_update_nonexistent_returns_false():
    ss = StudioStandards()
    assert ss.update_standard("nonexistent", 99) is False


def test_update_custom_standard():
    ss = StudioStandards()
    ss.register_standard("custom_one", "lighting", "old_value")
    ss.update_standard("custom_one", "new_value", "updated description")
    assert ss.get_standard_value("custom_one") == "new_value"


# ---------------------------------------------------------------------------
# remove_standard
# ---------------------------------------------------------------------------

def test_remove_custom_standard():
    ss = StudioStandards()
    ss.register_standard("to_remove", "lighting", "x")
    assert ss.remove_standard("to_remove") is True
    assert ss.get_standard("to_remove") is None


def test_remove_builtin_raises():
    ss = StudioStandards()
    with pytest.raises(ValueError, match="Cannot remove built-in"):
        ss.remove_standard("minimum_review_score")


def test_remove_nonexistent_returns_false():
    ss = StudioStandards()
    assert ss.remove_standard("nonexistent") is False


# ---------------------------------------------------------------------------
# validate_standard
# ---------------------------------------------------------------------------

def test_validate_existing_standard():
    ss = StudioStandards()
    result = ss.validate_standard("minimum_review_score")
    assert result["valid"] is True
    assert result["issues"] == []


def test_validate_missing_standard():
    ss = StudioStandards()
    result = ss.validate_standard("does_not_exist")
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# list_standards
# ---------------------------------------------------------------------------

def test_list_all_sorted():
    ss = StudioStandards()
    standards = ss.list_standards()
    ids = [s["id"] for s in standards]
    assert ids == sorted(ids)


def test_list_by_category():
    ss = StudioStandards()
    review = ss.list_standards(category="review_threshold")
    assert all(s["category"] == "review_threshold" for s in review)
    assert len(review) >= 2  # minimum_review_score + minimum_readability_score


# ---------------------------------------------------------------------------
# is_approved
# ---------------------------------------------------------------------------

def test_is_approved_lighting_known():
    ss = StudioStandards()
    assert ss.is_approved("lighting", "cinematic_industrial") is True


def test_is_approved_lighting_unknown():
    ss = StudioStandards()
    assert ss.is_approved("lighting", "random_unknown_style") is False


def test_is_approved_unknown_category_permissive():
    ss = StudioStandards()
    assert ss.is_approved("unknown_category", "anything") is True


def test_is_approved_workflow():
    ss = StudioStandards()
    assert ss.is_approved("workflow", "industrial_hangar_pack") is True
    assert ss.is_approved("workflow", "custom_pack") is False


# ---------------------------------------------------------------------------
# stats()
# ---------------------------------------------------------------------------

def test_stats_structure():
    ss = StudioStandards()
    s = ss.stats()
    assert s["builtin_count"] == len(_BUILTIN_STANDARDS)
    assert s["custom_count"] == 0
    assert s["total_standards"] == s["builtin_count"] + s["custom_count"]


def test_stats_update_count():
    ss = StudioStandards()
    ss.register_standard("x", "lighting", "y")
    ss.update_standard("x", "z")
    assert ss.stats()["update_count"] == 2


# ---------------------------------------------------------------------------
# get_all_standards copy safety
# ---------------------------------------------------------------------------

def test_get_all_standards_is_copy():
    ss = StudioStandards()
    all_s = ss.get_all_standards()
    all_s["minimum_review_score"]["value"] = 99
    assert ss.get_standard_value("minimum_review_score") == 0.75
