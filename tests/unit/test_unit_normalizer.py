"""Tests for UnitNormalizer (Tier 9.6)."""

import pytest
from src.runtime.assets.assembly.unit_normalizer import (
    UNIT_FACTORS,
    UnitNormalizer,
    get_unit_normalizer,
    reset_unit_normalizer_for_tests,
)


@pytest.fixture(autouse=True)
def reset():
    reset_unit_normalizer_for_tests()
    yield
    reset_unit_normalizer_for_tests()


class TestSingleton:
    def test_singleton_same_instance(self):
        assert get_unit_normalizer() is get_unit_normalizer()

    def test_reset_new_instance(self):
        a = get_unit_normalizer()
        reset_unit_normalizer_for_tests()
        assert a is not get_unit_normalizer()


class TestToMeters:
    def test_cm_to_meters(self):
        n = get_unit_normalizer()
        assert abs(n.to_meters(48.9, "cm") - 0.489) < 1e-9

    def test_mm_to_meters(self):
        n = get_unit_normalizer()
        assert abs(n.to_meters(489.0, "mm") - 0.489) < 1e-6

    def test_meters_identity(self):
        n = get_unit_normalizer()
        assert n.to_meters(1.5, "m") == 1.5
        assert n.to_meters(1.5, "meters") == 1.5

    def test_inches_to_meters(self):
        n = get_unit_normalizer()
        assert abs(n.to_meters(12.0, "in") - 0.3048) < 1e-6

    def test_feet_to_meters(self):
        n = get_unit_normalizer()
        assert abs(n.to_meters(1.0, "ft") - 0.3048) < 1e-6

    def test_centimeters_alias(self):
        n = get_unit_normalizer()
        assert n.to_meters(100.0, "centimeters") == 1.0
        assert n.to_meters(100.0, "centimetre") == 1.0

    def test_unknown_unit_treated_as_meters(self):
        n = get_unit_normalizer()
        assert n.to_meters(5.0, "parsec") == 5.0

    def test_negative_values_clamped_to_zero(self):
        n = get_unit_normalizer()
        assert n.to_meters(-1.0, "m") == 0.0

    def test_beam_377cm_to_meters(self):
        n = get_unit_normalizer()
        result = n.to_meters(377.7, "cm")
        assert abs(result - 3.777) < 1e-6

    def test_chair_489cm_to_meters(self):
        n = get_unit_normalizer()
        assert abs(n.to_meters(48.9, "cm") - 0.489) < 1e-9


class TestNormalizeBbox:
    def test_bbox_cm_to_meters(self):
        n = get_unit_normalizer()
        x, y, z = n.normalize_bbox(48.9, 83.8, 43.3, "cm")
        assert abs(x - 0.489) < 1e-6
        assert abs(y - 0.838) < 1e-6
        assert abs(z - 0.433) < 1e-6

    def test_bbox_identity_meters(self):
        n = get_unit_normalizer()
        x, y, z = n.normalize_bbox(1.0, 2.0, 3.0, "m")
        assert (x, y, z) == (1.0, 2.0, 3.0)

    def test_bbox_all_non_negative(self):
        n = get_unit_normalizer()
        x, y, z = n.normalize_bbox(-1.0, 0.0, 5.0, "cm")
        assert x == 0.0
        assert y == 0.0
        assert abs(z - 0.05) < 1e-9


class TestDetectUnit:
    def test_explicit_unit_field(self):
        n = get_unit_normalizer()
        assert n.detect_unit({"unit": "cm"}) == "cm"
        assert n.detect_unit({"unit_system": "millimeters"}) == "millimeters"
        assert n.detect_unit({"units": "in"}) == "in"
        assert n.detect_unit({"bbox_unit": "ft"}) == "ft"

    def test_heuristic_large_bbox_returns_cm(self):
        n = get_unit_normalizer()
        # bbox_x = 48.9 → > 10 → assume cm
        asset = {"bbox_x": 48.9, "bbox_y": 83.8, "bbox_z": 43.3}
        assert n.detect_unit(asset) == "cm"

    def test_small_bbox_returns_meters(self):
        n = get_unit_normalizer()
        asset = {"bbox_x": 1.5, "bbox_y": 0.8, "bbox_z": 0.6}
        assert n.detect_unit(asset) == "meters"

    def test_no_bbox_returns_meters(self):
        n = get_unit_normalizer()
        assert n.detect_unit({}) == "meters"

    def test_explicit_overrides_heuristic(self):
        n = get_unit_normalizer()
        asset = {"bbox_x": 48.9, "unit": "meters"}
        assert n.detect_unit(asset) == "meters"


class TestNormalizeAssetBbox:
    def test_chair_cm_to_meters(self):
        n = get_unit_normalizer()
        asset = {"name": "Wooden Chair", "bbox_x": 48.9, "bbox_y": 83.8, "bbox_z": 43.3}
        x, y, z = n.normalize_asset_bbox(asset)
        assert abs(x - 0.489) < 1e-6
        assert abs(y - 0.838) < 1e-6

    def test_no_bbox_returns_zeros(self):
        n = get_unit_normalizer()
        assert n.normalize_asset_bbox({}) == (0.0, 0.0, 0.0)

    def test_beam_normalized(self):
        n = get_unit_normalizer()
        asset = {"name": "Old Wooden Beam", "bbox_x": 377.7, "bbox_y": 36.6, "bbox_z": 36.2}
        x, y, z = n.normalize_asset_bbox(asset)
        assert abs(x - 3.777) < 1e-4
        assert x > 3.0  # definitely larger than 3 m


class TestUnitFactors:
    def test_unit_factors_non_empty(self):
        assert len(UNIT_FACTORS) > 0

    def test_cm_factor(self):
        assert UNIT_FACTORS["cm"] == 0.01

    def test_meters_factor_is_one(self):
        assert UNIT_FACTORS["m"] == 1.0
        assert UNIT_FACTORS["meters"] == 1.0

    def test_factor_for_method(self):
        n = get_unit_normalizer()
        assert n.factor_for("cm") == 0.01
        assert n.factor_for("METERS") == 1.0
        assert n.factor_for("unknown") == 1.0

    def test_supported_units_sorted(self):
        n = get_unit_normalizer()
        units = n.supported_units()
        assert units == sorted(units)
        assert "cm" in units
        assert "meters" in units
