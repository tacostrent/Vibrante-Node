"""
Scene Intent Validator (Phase 1)
==================================
Validates a SceneIntent for:
  - Required field presence (configurable minimum set)
  - Enum value correctness (every string field must be in its allowed set)
  - Numeric range bounds (confidence, priority, quantity)
  - Logical contradictions (e.g. destruction + peaceful mood, underwater + desert)
  - Asset requirement completeness

Validation is non-destructive: it populates `intent.validation_errors` and
returns a structured result dict. It never mutates other intent fields.

Design:
  - Stateless — no singleton needed; a shared instance is provided for
    convenience but the class is freely instantiable.
  - Two severity levels: "error" (blocks execution) and "warning" (advisory).
  - `validate()` is synchronous — no I/O, no bridge calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..schema.scene_intent_schema import (
    ENVIRONMENT_TYPES,
    STYLE_TYPES,
    MOOD_TYPES,
    TIME_OF_DAY_VALUES,
    WEATHER_TYPES,
    SCALE_VALUES,
    DENSITY_LEVELS,
    DESTRUCTION_LEVELS,
    CINEMATIC_STYLE_VALUES,
    LIGHTING_STYLE_VALUES,
    ZONE_TYPES,
    ATMOSPHERIC_EFFECT_TYPES,
    ASSET_PROVIDER_VALUES,
    SceneIntent,
)

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Structured outcome of a SceneIntent validation pass.

    Attributes:
        valid:          True when zero errors (warnings are allowed).
        errors:         Blocking issues — prevent downstream execution.
        warnings:       Advisory issues — do not block execution.
        contradiction_flags: Detected logical contradictions.
    """
    valid:                bool        = True
    errors:               List[str]   = field(default_factory=list)
    warnings:             List[str]   = field(default_factory=list)
    contradiction_flags:  List[str]   = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid":               self.valid,
            "error_count":         len(self.errors),
            "warning_count":       len(self.warnings),
            "contradiction_count": len(self.contradiction_flags),
            "errors":              list(self.errors),
            "warnings":            list(self.warnings),
            "contradictions":      list(self.contradiction_flags),
        }


# ---------------------------------------------------------------------------
# Contradiction rules
# ---------------------------------------------------------------------------

# (condition_a, condition_b, message)
# Checked when BOTH sides of a pair are set on the same intent.
_CONTRADICTION_RULES = [
    # Environment
    ("environment", "desert",       "environment", "ocean",
     "Environment 'desert' contradicts 'ocean'"),
    ("environment", "arctic",       "environment", "desert",
     "Environment 'arctic' contradicts 'desert'"),
    ("environment", "underwater",   "environment", "space",
     "Environment 'underwater' contradicts 'space'"),

    # Mood vs destruction
    ("mood", "peaceful",            "destruction_level", "heavy",
     "Mood 'peaceful' contradicts destruction_level 'heavy'"),
    ("mood", "peaceful",            "destruction_level", "catastrophic",
     "Mood 'peaceful' contradicts destruction_level 'catastrophic'"),

    # Weather vs environment
    ("weather", "snow",             "environment", "desert",
     "Weather 'snow' is unlikely in a desert environment"),

    # Time of day vs lighting
    ("time_of_day", "night",        "lighting_style", "golden_hour",
     "Lighting 'golden_hour' contradicts time_of_day 'night'"),
    ("time_of_day", "noon",         "lighting_style", "night",
     "Lighting 'night' contradicts time_of_day 'noon'"),
]


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class SceneIntentValidator:
    """Validates a SceneIntent against schema rules and logical constraints.

    Usage::

        validator = SceneIntentValidator()
        result = validator.validate(intent)
        if not result.valid:
            for err in result.errors:
                print(err)
    """

    def __init__(self, minimum_confidence: float = 0.1):
        self._minimum_confidence = minimum_confidence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, intent: SceneIntent) -> ValidationResult:
        """Validate a SceneIntent and populate intent.validation_errors.

        Args:
            intent: The SceneIntent to validate. `validation_errors` will
                    be cleared and repopulated.

        Returns:
            ValidationResult with errors, warnings, and contradictions.
        """
        result = ValidationResult()

        self._check_confidence(intent, result)
        self._check_enum_fields(intent, result)
        self._check_asset_requirements(intent, result)
        self._check_zones(intent, result)
        self._check_atmospheric_effects(intent, result)
        self._check_contradictions(intent, result)
        self._check_completeness(intent, result)

        # Determine validity
        result.valid = len(result.errors) == 0

        # Sync errors back onto the intent for downstream consumers
        intent.validation_errors = list(result.errors)

        return result

    # ------------------------------------------------------------------
    # Private checks
    # ------------------------------------------------------------------

    def _check_confidence(self, intent: SceneIntent, result: ValidationResult) -> None:
        if not (0.0 <= intent.confidence <= 1.0):
            result.errors.append(
                f"confidence {intent.confidence} is out of range [0.0, 1.0]"
            )
        elif intent.confidence < self._minimum_confidence:
            result.warnings.append(
                f"confidence {intent.confidence:.2f} is below minimum "
                f"{self._minimum_confidence:.2f} — extraction may be unreliable"
            )

    def _check_enum_fields(self, intent: SceneIntent, result: ValidationResult) -> None:
        enum_checks = [
            ("environment",       intent.environment,       ENVIRONMENT_TYPES),
            ("style",             intent.style,             STYLE_TYPES),
            ("mood",              intent.mood,               MOOD_TYPES),
            ("time_of_day",       intent.time_of_day,        TIME_OF_DAY_VALUES),
            ("weather",           intent.weather,            WEATHER_TYPES),
            ("scale",             intent.scale,              SCALE_VALUES),
            ("density",           intent.density,            DENSITY_LEVELS),
            ("destruction_level", intent.destruction_level, DESTRUCTION_LEVELS),
            ("cinematic_style",   intent.cinematic_style,   CINEMATIC_STYLE_VALUES),
            ("lighting_style",    intent.lighting_style,    LIGHTING_STYLE_VALUES),
        ]
        for field_name, value, allowed in enum_checks:
            if value is not None and value not in allowed:
                result.errors.append(
                    f"'{field_name}' value '{value}' is not in the allowed set "
                    f"({', '.join(sorted(allowed))})"
                )

    def _check_asset_requirements(
        self, intent: SceneIntent, result: ValidationResult
    ) -> None:
        for i, asset in enumerate(intent.asset_requirements):
            if not asset.asset_type:
                result.errors.append(
                    f"asset_requirements[{i}]: 'asset_type' is required"
                )
            if asset.quantity is not None and asset.quantity < 0:
                result.errors.append(
                    f"asset_requirements[{i}]: 'quantity' must be >= 0, got {asset.quantity}"
                )
            if asset.provider not in ASSET_PROVIDER_VALUES:
                result.errors.append(
                    f"asset_requirements[{i}]: 'provider' '{asset.provider}' "
                    f"is not in the allowed set ({', '.join(sorted(ASSET_PROVIDER_VALUES))})"
                )

    def _check_zones(self, intent: SceneIntent, result: ValidationResult) -> None:
        for i, zone in enumerate(intent.zones):
            if zone.zone_type not in ZONE_TYPES:
                result.errors.append(
                    f"zones[{i}]: 'zone_type' '{zone.zone_type}' is not in the allowed set "
                    f"({', '.join(sorted(ZONE_TYPES))})"
                )
            if not (1 <= zone.priority <= 10):
                result.errors.append(
                    f"zones[{i}]: 'priority' {zone.priority} must be between 1 and 10"
                )
            # Validate nested assets in zones
            for j, asset in enumerate(zone.assets):
                if not asset.asset_type:
                    result.errors.append(
                        f"zones[{i}].assets[{j}]: 'asset_type' is required"
                    )

    def _check_atmospheric_effects(
        self, intent: SceneIntent, result: ValidationResult
    ) -> None:
        for effect in intent.atmospheric_effects:
            if effect not in ATMOSPHERIC_EFFECT_TYPES:
                result.errors.append(
                    f"atmospheric_effects: '{effect}' is not in the allowed set "
                    f"({', '.join(sorted(ATMOSPHERIC_EFFECT_TYPES))})"
                )

    def _check_contradictions(
        self, intent: SceneIntent, result: ValidationResult
    ) -> None:
        intent_dict = intent.to_dict()
        for field_a, val_a, field_b, val_b, msg in _CONTRADICTION_RULES:
            if intent_dict.get(field_a) == val_a and intent_dict.get(field_b) == val_b:
                result.contradiction_flags.append(msg)
                result.warnings.append(f"Contradiction: {msg}")

    def _check_completeness(
        self, intent: SceneIntent, result: ValidationResult
    ) -> None:
        core_fields = [
            ("environment",  intent.environment),
            ("style",        intent.style),
            ("mood",         intent.mood),
        ]
        missing = [name for name, val in core_fields if val is None]
        if missing:
            result.warnings.append(
                f"Core fields not extracted: {', '.join(missing)} — "
                "consider providing a more descriptive prompt"
            )


# ---------------------------------------------------------------------------
# Shared instance
# ---------------------------------------------------------------------------

_validator: Optional[SceneIntentValidator] = None


def get_scene_intent_validator(
    minimum_confidence: float = 0.1,
) -> SceneIntentValidator:
    """Return the shared SceneIntentValidator instance."""
    global _validator
    if _validator is None:
        _validator = SceneIntentValidator(minimum_confidence=minimum_confidence)
    return _validator


def reset_scene_intent_validator_for_tests() -> None:
    """Reset shared instance for test isolation."""
    global _validator
    _validator = None
