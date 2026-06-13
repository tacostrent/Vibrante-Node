import pytest
from src.runtime.lookdev import (
    get_lookdev_validation,
    reset_lookdev_validation_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_lookdev_validation_for_tests()
    yield
    reset_lookdev_validation_for_tests()


def test_singleton_identity():
    assert get_lookdev_validation() is get_lookdev_validation()


def test_validate_material_valid():
    result = get_lookdev_validation().validate_material(
        {"name": "industrial_metal", "category": "industrial_metal"}
    )
    assert result["ok"] is True
    assert result["errors"] == []


def test_validate_material_missing_name():
    result = get_lookdev_validation().validate_material({"category": "glass"})
    assert result["ok"] is False
    assert any("name" in e for e in result["errors"])


def test_validate_material_missing_category():
    result = get_lookdev_validation().validate_material({"name": "my_mat"})
    assert result["ok"] is False
    assert any("category" in e for e in result["errors"])


def test_validate_material_unknown_category_warns():
    result = get_lookdev_validation().validate_material(
        {"name": "my_mat", "category": "unknown_category_xyz"}
    )
    assert result["ok"] is True
    assert len(result["warnings"]) > 0


def test_validate_pattern_valid():
    result = get_lookdev_validation().validate_pattern({
        "name": "test_lookdev", "environment": "industrial_hangar",
        "materials": ["industrial_metal"],
    })
    assert result["ok"] is True


def test_validate_pattern_missing_environment():
    result = get_lookdev_validation().validate_pattern(
        {"name": "test", "materials": ["concrete"]}
    )
    assert result["ok"] is False
    assert any("environment" in e for e in result["errors"])


def test_validate_pattern_empty_materials():
    result = get_lookdev_validation().validate_pattern({
        "name": "test", "environment": "lab", "materials": []
    })
    assert result["ok"] is False


def test_validate_renderer_profile_valid_arnold():
    result = get_lookdev_validation().validate_renderer_profile({
        "renderer": "arnold", "material_class": "standard_surface"
    })
    assert result["ok"] is True


def test_validate_renderer_profile_invalid_renderer():
    result = get_lookdev_validation().validate_renderer_profile({
        "renderer": "mantra", "material_class": "mantra_surface"
    })
    assert result["ok"] is False
    assert any("mantra" in e or "not supported" in e for e in result["errors"])


def test_validate_renderer_profile_missing_class():
    result = get_lookdev_validation().validate_renderer_profile({"renderer": "karma"})
    assert result["ok"] is False


def test_validate_assignment_valid():
    result = get_lookdev_validation().validate_assignment({
        "asset_id": "a1", "material_name": "concrete", "renderer": "usd_preview_surface"
    })
    assert result["ok"] is True


def test_validate_assignment_missing_material():
    result = get_lookdev_validation().validate_assignment({"asset_id": "a1", "renderer": "arnold"})
    assert result["ok"] is False
    assert any("material_name" in e for e in result["errors"])


def test_validate_assignment_unknown_renderer_warns():
    result = get_lookdev_validation().validate_assignment({
        "asset_id": "a1", "material_name": "glass", "renderer": "unknown_renderer"
    })
    assert result["ok"] is True
    assert len(result["warnings"]) > 0


def test_validate_review_threshold_pass():
    result = get_lookdev_validation().validate_review_threshold(0.80, 0.70)
    assert result["ok"] is True
    assert result["production_ready"] is True
    assert result["gap"] == 0.0


def test_validate_review_threshold_fail():
    result = get_lookdev_validation().validate_review_threshold(0.60, 0.70)
    assert result["production_ready"] is False
    assert result["gap"] > 0.0


def test_validate_review_threshold_exact():
    result = get_lookdev_validation().validate_review_threshold(0.70, 0.70)
    assert result["production_ready"] is True


def test_result_has_validated_at():
    result = get_lookdev_validation().validate_material({"name": "m", "category": "glass"})
    assert "validated_at" in result
    assert isinstance(result["validated_at"], float)


def test_never_raises_none_material():
    result = get_lookdev_validation().validate_material(None)  # type: ignore
    assert isinstance(result, dict)
    assert "ok" in result
