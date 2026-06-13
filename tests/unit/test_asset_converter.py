"""
Tests for AssetConverter (Tier 13)
"""
import pytest

from src.runtime.assets.realization import (
    get_asset_converter,
    reset_asset_converter_for_tests,
    ConversionResult,
    CONVERSION_MATRIX,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_asset_converter_for_tests()
    yield
    reset_asset_converter_for_tests()


def test_singleton():
    assert get_asset_converter() is get_asset_converter()


def test_reset_gives_new_instance():
    a = get_asset_converter()
    reset_asset_converter_for_tests()
    b = get_asset_converter()
    assert a is not b


def test_convert_fbx_to_usd():
    result = get_asset_converter().convert(
        {"asset_id": "c1", "name": "Tank", "format": "fbx"}, "usd"
    )
    assert isinstance(result, ConversionResult)
    assert result.ok is True
    assert result.target_format == "usd"
    assert result.source_format == "fbx"


def test_convert_usd_to_usd_same_format():
    result = get_asset_converter().convert(
        {"asset_id": "c2", "format": "usd"}, "usd"
    )
    assert result.ok is True
    assert len(result.conversion_notes) > 0
    # Should note no conversion needed
    assert any("no conversion" in n.lower() for n in result.conversion_notes)


def test_convert_unsupported_target_format():
    result = get_asset_converter().convert(
        {"asset_id": "c3", "format": "fbx"}, "docx"
    )
    assert result.ok is False
    assert len(result.errors) > 0


def test_convert_to_usd_shorthand():
    result = get_asset_converter().convert_to_usd({"asset_id": "c4", "format": "obj"})
    assert result.ok is True
    assert result.target_format == "usd"


def test_convert_to_gltf_shorthand():
    result = get_asset_converter().convert_to_gltf({"asset_id": "c5", "format": "fbx"})
    assert result.ok is True
    assert result.target_format == "gltf"


def test_conversion_matrix_is_dict():
    assert isinstance(CONVERSION_MATRIX, dict)
    assert len(CONVERSION_MATRIX) > 0
    assert "fbx" in CONVERSION_MATRIX


def test_validate_conversion_valid():
    result = get_asset_converter().convert({"asset_id": "c6", "format": "obj"}, "usd")
    validation = get_asset_converter().validate_conversion(result)
    assert validation["valid"] is True


def test_build_conversion_report():
    conv = get_asset_converter()
    r1 = conv.convert({"asset_id": "c7", "format": "fbx"}, "usd")
    r2 = conv.convert({"asset_id": "c8", "format": "gltf"}, "usd")
    report = conv.build_conversion_report([r1, r2])
    assert "total" in report
    assert "successful" in report
    assert "failed" in report
    assert report["total"] == 2


def test_to_dict_from_dict_round_trip():
    result = get_asset_converter().convert({"asset_id": "c9", "format": "fbx"}, "usd")
    d = result.to_dict()
    restored = ConversionResult.from_dict(d)
    assert restored.asset_id == result.asset_id
    assert restored.target_format == result.target_format
    assert restored.ok == result.ok


def test_never_raises():
    result = get_asset_converter().convert(None, "usd")  # type: ignore
    assert isinstance(result, ConversionResult)
