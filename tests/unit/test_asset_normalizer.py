"""
Tests for AssetNormalizer (Tier 13)
"""
import pytest

from src.runtime.assets.realization import (
    get_asset_normalizer,
    reset_asset_normalizer_for_tests,
    NormalizationResult,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_asset_normalizer_for_tests()
    yield
    reset_asset_normalizer_for_tests()


def test_singleton():
    assert get_asset_normalizer() is get_asset_normalizer()


def test_normalize_scale_returns_required_keys():
    result = get_asset_normalizer().normalize_scale({"asset_id": "n1"})
    assert "scale_factor" in result
    assert "applied" in result


def test_normalize_scale_no_change():
    result = get_asset_normalizer().normalize_scale({"scale": 1.0}, target_scale=1.0)
    assert result["applied"] is False
    assert abs(result["scale_factor"] - 1.0) < 1e-6


def test_normalize_orientation_returns_dict():
    result = get_asset_normalizer().normalize_orientation({"up_axis": "Z"}, up_axis="Y")
    assert "source_up" in result
    assert "target_up" in result
    assert "rotation" in result
    assert "applied" in result
    assert result["applied"] is True


def test_normalize_units_cm_to_m():
    result = get_asset_normalizer().normalize_units({"unit": "cm"}, target_unit="m")
    assert abs(result["scale_factor"] - 0.01) < 1e-9
    assert result["applied"] is True


def test_normalize_units_unknown_unit_no_change():
    result = get_asset_normalizer().normalize_units({"unit": "parsec"}, target_unit="m")
    # Unknown unit → scale factor = 1.0 (no change)
    assert abs(result["scale_factor"] - 1.0) < 1e-6


def test_normalize_pivots_returns_dict():
    result = get_asset_normalizer().normalize_pivots({"pivot": [1.0, 2.0, 3.0]})
    assert "pivot_offset" in result
    assert "applied" in result
    assert result["applied"] is True


def test_normalize_metadata_returns_dict():
    result = get_asset_normalizer().normalize_metadata({"name": "  My Asset  "})
    assert "normalized_fields" in result
    assert "metadata" in result
    assert result["applied"] is True
    assert result["metadata"]["name"] == "My Asset"


def test_normalize_full_pipeline_returns_result():
    result = get_asset_normalizer().normalize({
        "asset_id": "n10",
        "name": "Tank",
        "scale": 100.0,
        "unit": "cm",
        "up_axis": "Z",
    })
    assert isinstance(result, NormalizationResult)
    assert result.ok is True


def test_normalization_notes_is_list():
    result = get_asset_normalizer().normalize({"asset_id": "n11"})
    assert isinstance(result.normalization_notes, list)


def test_build_normalization_report():
    norm = get_asset_normalizer()
    r1 = norm.normalize({"asset_id": "n12", "unit": "cm"})
    r2 = norm.normalize({"asset_id": "n13"})
    report = norm.build_normalization_report([r1, r2])
    assert "total" in report
    assert "successful" in report
    assert "failed" in report
    assert report["total"] == 2


def test_to_dict_from_dict_round_trip():
    result = get_asset_normalizer().normalize({"asset_id": "n14"})
    d = result.to_dict()
    restored = NormalizationResult.from_dict(d)
    assert restored.asset_id == result.asset_id
    assert restored.ok == result.ok


def test_never_raises():
    result = get_asset_normalizer().normalize(None)  # type: ignore
    assert isinstance(result, NormalizationResult)
