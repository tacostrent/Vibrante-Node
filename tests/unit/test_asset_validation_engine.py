"""
Tests for src/runtime/assets/validation/asset_validation_engine.py
"""

import pytest

from src.runtime.assets.validation import (
    ValidationReport,
    AssetValidationEngine,
    get_asset_validation_engine,
    reset_asset_validation_engine_for_tests,
)
from src.runtime.assets.schema import AssetDescriptor


@pytest.fixture(autouse=True)
def reset():
    reset_asset_validation_engine_for_tests()
    yield
    reset_asset_validation_engine_for_tests()


def make_asset(**kwargs) -> AssetDescriptor:
    defaults = dict(
        asset_id="test_001",
        provider="sketchfab",
        name="Test Asset",
        category="prop",
        tags=["industrial"],
        license="cc-by",
        formats=["fbx", "gltf"],
        rating=3.5,
        scale="human",
        style="photorealistic",
    )
    defaults.update(kwargs)
    return AssetDescriptor(**defaults)


class TestAssetValidationEngine:
    def test_singleton_identity(self):
        v1 = get_asset_validation_engine()
        v2 = get_asset_validation_engine()
        assert v1 is v2

    def test_valid_asset_passes(self):
        report = get_asset_validation_engine().validate([make_asset()])
        assert report.valid_count == 1
        assert report.rejected_count == 0

    def test_empty_name_is_rejected(self):
        asset = make_asset(name="")
        report = get_asset_validation_engine().validate([asset])
        assert report.rejected_count == 1

    def test_invalid_rating_rejected(self):
        asset = make_asset(rating=6.0)
        report = get_asset_validation_engine().validate([asset])
        assert report.rejected_count == 1
        key = f"{asset.provider}:{asset.asset_id}"
        assert any("invalid_rating" in r for r in report.rejection_reasons.get(key, []))

    def test_negative_rating_rejected(self):
        asset = make_asset(rating=-1.0)
        report = get_asset_validation_engine().validate([asset])
        assert report.rejected_count == 1

    def test_format_incompatible_with_renderer(self):
        asset = make_asset(formats=["bgeo"], category="terrain")
        report = get_asset_validation_engine().validate([asset], renderer="arnold")
        assert report.rejected_count == 1

    def test_compatible_format_passes(self):
        asset = make_asset(formats=["gltf", "fbx"])
        report = get_asset_validation_engine().validate([asset], renderer="arnold")
        assert report.valid_count == 1

    def test_duplicate_detection(self):
        asset = make_asset(asset_id="dup1")
        report = get_asset_validation_engine().validate([asset, asset])
        assert report.rejected_count == 1  # second duplicate rejected

    def test_scale_mismatch_warning(self):
        asset = make_asset(scale="planetary")
        report = get_asset_validation_engine().validate([asset], zone="foreground")
        key = f"{asset.provider}:{asset.asset_id}"
        warnings = report.warnings.get(key, [])
        assert any("scale_mismatch" in w for w in warnings)

    def test_scale_unknown_always_passes(self):
        asset = make_asset(scale="unknown")
        report = get_asset_validation_engine().validate([asset], zone="foreground")
        assert report.valid_count == 1

    def test_style_conflict_warning(self):
        asset = make_asset(category="vegetation")
        report = get_asset_validation_engine().validate(
            [asset], existing_categories=["electronic"]
        )
        key = f"{asset.provider}:{asset.asset_id}"
        warnings = report.warnings.get(key, [])
        assert any("style_conflict" in w for w in warnings)

    def test_multiple_assets_mixed(self):
        good = make_asset(asset_id="good", name="Good Asset")
        bad  = make_asset(asset_id="bad",  name="", rating=7.0)
        report = get_asset_validation_engine().validate([good, bad])
        assert report.valid_count == 1
        assert report.rejected_count == 1

    def test_checks_run_with_renderer(self):
        report = get_asset_validation_engine().validate(
            [make_asset()], renderer="arnold"
        )
        assert "format_compatibility" in report.checks_run

    def test_checks_run_without_renderer(self):
        report = get_asset_validation_engine().validate([make_asset()])
        assert "format_compatibility" not in report.checks_run

    def test_validate_one_valid(self):
        result = get_asset_validation_engine().validate_one(make_asset())
        assert result["valid"] is True
        assert result["errors"] == []

    def test_validate_one_invalid(self):
        result = get_asset_validation_engine().validate_one(make_asset(name=""))
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_validate_one_returns_checks_passed(self):
        result = get_asset_validation_engine().validate_one(make_asset())
        assert "checks_passed" in result
        assert len(result["checks_passed"]) > 0

    def test_report_to_dict_structure(self):
        report = get_asset_validation_engine().validate([make_asset()])
        d = report.to_dict()
        assert "valid_assets" in d
        assert "rejected_assets" in d
        assert "checks_run" in d
        assert "valid_count" in d
        assert "rejected_count" in d

    def test_no_assets_returns_empty_report(self):
        report = get_asset_validation_engine().validate([])
        assert report.valid_count == 0
        assert report.rejected_count == 0
