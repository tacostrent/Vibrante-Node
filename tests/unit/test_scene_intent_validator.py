"""
Tests for src.runtime.semantic.validators.scene_intent_validator
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.semantic.validators.scene_intent_validator import (
    ValidationResult,
    SceneIntentValidator,
    get_scene_intent_validator,
    reset_scene_intent_validator_for_tests,
)
from src.runtime.semantic.schema.scene_intent_schema import (
    AssetRequirement,
    SceneIntent,
    SceneZone,
)


@pytest.fixture(autouse=True)
def reset():
    reset_scene_intent_validator_for_tests()
    yield
    reset_scene_intent_validator_for_tests()


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

def test_validation_result_defaults():
    r = ValidationResult()
    assert r.valid is True
    assert r.errors == []
    assert r.warnings == []
    assert r.contradiction_flags == []


def test_validation_result_to_dict():
    r = ValidationResult(valid=False, errors=["bad field"], warnings=["advisory"])
    d = r.to_dict()
    assert d["valid"] is False
    assert d["error_count"] == 1
    assert d["warning_count"] == 1
    assert "bad field" in d["errors"]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_scene_intent_validator()
    b = get_scene_intent_validator()
    assert a is b


def test_reset_creates_new_instance():
    a = get_scene_intent_validator()
    reset_scene_intent_validator_for_tests()
    b = get_scene_intent_validator()
    assert a is not b


# ---------------------------------------------------------------------------
# Valid intent — no errors
# ---------------------------------------------------------------------------

def test_valid_minimal_intent():
    intent = SceneIntent(confidence=0.5)
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert result.valid is True
    assert result.errors == []


def test_valid_full_intent():
    intent = SceneIntent(
        environment="urban",
        style="cinematic",
        mood="dramatic",
        time_of_day="night",
        weather="smoke",
        scale="urban",
        density="dense",
        destruction_level="heavy",
        cinematic_style="action",
        lighting_style="practical_fire",
        atmospheric_effects=["smoke", "embers"],
        confidence=0.92,
    )
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert result.valid is True


# ---------------------------------------------------------------------------
# Confidence checks
# ---------------------------------------------------------------------------

def test_confidence_out_of_range_high():
    intent = SceneIntent(confidence=1.5)
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid
    assert any("confidence" in e for e in result.errors)


def test_confidence_out_of_range_low():
    intent = SceneIntent(confidence=-0.1)
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid


def test_confidence_below_minimum_warns():
    intent = SceneIntent(confidence=0.05)
    validator = SceneIntentValidator(minimum_confidence=0.1)
    result = validator.validate(intent)
    assert result.valid is True  # warning only, not error
    assert any("minimum" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Enum field validation
# ---------------------------------------------------------------------------

def test_invalid_environment():
    intent = SceneIntent(environment="underwater_cave", confidence=0.5)
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid
    assert any("environment" in e for e in result.errors)


def test_invalid_style():
    intent = SceneIntent(style="not_a_style", confidence=0.5)
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid


def test_invalid_mood():
    intent = SceneIntent(mood="furious", confidence=0.5)
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid


def test_invalid_destruction_level():
    intent = SceneIntent(destruction_level="total_annihilation", confidence=0.5)
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid


def test_none_fields_are_valid():
    # All None is valid (partial extraction is OK)
    intent = SceneIntent(confidence=0.3)
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert result.valid is True


# ---------------------------------------------------------------------------
# Asset requirement validation
# ---------------------------------------------------------------------------

def test_asset_missing_asset_type():
    intent = SceneIntent(confidence=0.5)
    intent.asset_requirements = [AssetRequirement(asset_type="")]
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid
    assert any("asset_type" in e for e in result.errors)


def test_asset_negative_quantity():
    intent = SceneIntent(confidence=0.5)
    intent.asset_requirements = [AssetRequirement(asset_type="tree", quantity=-1)]
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid


def test_asset_invalid_provider():
    intent = SceneIntent(confidence=0.5)
    intent.asset_requirements = [
        AssetRequirement(asset_type="tree", provider="made_up_provider")
    ]
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid


def test_asset_valid_provider():
    intent = SceneIntent(confidence=0.5)
    intent.asset_requirements = [
        AssetRequirement(asset_type="rock", provider="polyhaven")
    ]
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert result.valid is True


# ---------------------------------------------------------------------------
# Zone validation
# ---------------------------------------------------------------------------

def test_zone_invalid_type():
    intent = SceneIntent(confidence=0.5)
    intent.zones = [SceneZone(zone_type="invalid_zone_type")]
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid


def test_zone_priority_out_of_range():
    intent = SceneIntent(confidence=0.5)
    intent.zones = [SceneZone(zone_type="center", priority=0)]
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid
    assert any("priority" in e for e in result.errors)


def test_zone_priority_11_invalid():
    intent = SceneIntent(confidence=0.5)
    intent.zones = [SceneZone(zone_type="center", priority=11)]
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid


def test_zone_priority_10_valid():
    intent = SceneIntent(confidence=0.5)
    intent.zones = [SceneZone(zone_type="center", priority=10)]
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert result.valid is True


# ---------------------------------------------------------------------------
# Atmospheric effects validation
# ---------------------------------------------------------------------------

def test_invalid_atmospheric_effect():
    intent = SceneIntent(confidence=0.5, atmospheric_effects=["lava_flow"])
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not result.valid


def test_valid_atmospheric_effects():
    intent = SceneIntent(confidence=0.5, atmospheric_effects=["smoke", "embers"])
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert result.valid is True


# ---------------------------------------------------------------------------
# Contradiction detection
# ---------------------------------------------------------------------------

def test_contradiction_peaceful_heavy_destruction():
    intent = SceneIntent(
        confidence=0.6,
        mood="peaceful",
        destruction_level="heavy",
    )
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert len(result.contradiction_flags) > 0
    assert any("peaceful" in f for f in result.contradiction_flags)
    # Contradictions are warnings not errors — still valid
    assert result.valid is True


def test_contradiction_night_golden_hour():
    intent = SceneIntent(
        confidence=0.6,
        time_of_day="night",
        lighting_style="golden_hour",
    )
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert len(result.contradiction_flags) > 0


def test_contradiction_desert_snow():
    intent = SceneIntent(
        confidence=0.6,
        environment="desert",
        weather="snow",
    )
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert len(result.contradiction_flags) > 0


# ---------------------------------------------------------------------------
# Completeness warnings
# ---------------------------------------------------------------------------

def test_completeness_warning_no_core_fields():
    intent = SceneIntent(confidence=0.3, keywords=["test"])
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert result.valid is True
    assert any("Core fields" in w for w in result.warnings)


def test_no_completeness_warning_with_core_fields():
    intent = SceneIntent(
        confidence=0.7,
        environment="urban",
        style="cinematic",
        mood="dramatic",
    )
    validator = SceneIntentValidator()
    result = validator.validate(intent)
    assert not any("Core fields" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Validation_errors sync
# ---------------------------------------------------------------------------

def test_validation_errors_synced_to_intent():
    intent = SceneIntent(environment="invalid_env", confidence=0.5)
    validator = SceneIntentValidator()
    validator.validate(intent)
    assert len(intent.validation_errors) > 0
    assert any("environment" in e for e in intent.validation_errors)
