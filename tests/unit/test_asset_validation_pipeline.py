"""
Tests for AssetValidationPipeline (Tier 13)
"""
import pytest

from src.runtime.assets.realization import (
    get_asset_validation_pipeline,
    reset_asset_validation_pipeline_for_tests,
    PipelineValidationResult,
    # Also reset other singletons used internally
    reset_asset_importer_for_tests,
    reset_asset_converter_for_tests,
    reset_asset_normalizer_for_tests,
    reset_asset_dependency_resolver_for_tests,
    reset_scene_asset_realizer_for_tests,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_asset_validation_pipeline_for_tests()
    reset_asset_importer_for_tests()
    reset_asset_converter_for_tests()
    reset_asset_normalizer_for_tests()
    reset_asset_dependency_resolver_for_tests()
    reset_scene_asset_realizer_for_tests()
    yield
    reset_asset_validation_pipeline_for_tests()
    reset_asset_importer_for_tests()
    reset_asset_converter_for_tests()
    reset_asset_normalizer_for_tests()
    reset_asset_dependency_resolver_for_tests()
    reset_scene_asset_realizer_for_tests()


def test_singleton():
    assert get_asset_validation_pipeline() is get_asset_validation_pipeline()


def test_validate_import_has_valid_key():
    mock_import = {"ok": True, "asset_id": "v1", "errors": [], "warnings": []}
    result = get_asset_validation_pipeline().validate_import(mock_import)
    assert "valid" in result
    assert isinstance(result["valid"], bool)


def test_validate_conversion_has_valid_key():
    mock_conv = {"ok": True, "target_format": "usd", "errors": [], "warnings": []}
    result = get_asset_validation_pipeline().validate_conversion(mock_conv)
    assert "valid" in result


def test_validate_normalization_has_valid_key():
    mock_norm = {"ok": True, "errors": [], "warnings": []}
    result = get_asset_validation_pipeline().validate_normalization(mock_norm)
    assert "valid" in result


def test_validate_dependencies_has_valid_key():
    mock_dep = {"ok": True, "missing_deps": [], "errors": [], "warnings": []}
    result = get_asset_validation_pipeline().validate_dependencies(mock_dep)
    assert "valid" in result


def test_validate_realization_has_valid_key():
    mock_plan = {"transaction_ops": [{"op": "create_node"}], "errors": []}
    result = get_asset_validation_pipeline().validate_realization(mock_plan)
    assert "valid" in result


def test_validate_full_pipeline_returns_result():
    result = get_asset_validation_pipeline().validate_full_pipeline({
        "asset_id": "v2",
        "name": "Tank",
        "format": "usd",
    })
    assert isinstance(result, PipelineValidationResult)
    assert "asset_id" in result.to_dict()


def test_pipeline_result_has_all_required_keys():
    result = get_asset_validation_pipeline().validate_full_pipeline({"asset_id": "v3"})
    d = result.to_dict()
    for key in ("ok", "asset_id", "asset_name", "import_valid", "conversion_valid",
                "normalization_valid", "dependency_valid", "realization_valid",
                "errors", "warnings", "checks_passed", "checks_failed", "validated_at"):
        assert key in d


def test_checks_passed_and_failed_are_lists():
    result = get_asset_validation_pipeline().validate_full_pipeline({"asset_id": "v4"})
    assert isinstance(result.checks_passed, list)
    assert isinstance(result.checks_failed, list)


def test_pipeline_result_to_dict_from_dict():
    result = get_asset_validation_pipeline().validate_full_pipeline({"asset_id": "v5"})
    d = result.to_dict()
    restored = PipelineValidationResult.from_dict(d)
    assert restored.asset_id == result.asset_id
    assert restored.ok == result.ok


def test_never_raises():
    result = get_asset_validation_pipeline().validate_full_pipeline(None)  # type: ignore
    assert isinstance(result, PipelineValidationResult)
