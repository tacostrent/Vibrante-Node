"""
Scene Intent Enricher (Phase 1)
=================================
Infers implied requirements from the scene type and fills in missing
fields on a SceneIntent that passed validation.

Examples of enrichment:
  - "apocalyptic city" → adds smoke + debris_particles to atmospheric_effects
  - destruction_level "heavy" → infers rbd FX in center zone if none present
  - environment "desert" + weather "dust" → infers haze atmospheric effect
  - lighting_style "practical_fire" → adds embers to atmospheric effects
  - time_of_day "night" with no lighting_style → infers "night" lighting_style

Enrichment is deterministic: same input always produces the same output.
It only ADDS information — never removes or overwrites existing fields.
`enrichment_applied` is set to True when any inference fires.

Design rules:
  1. Never overwrite a field that is already populated.
  2. Never call the bridge or any LLM provider.
  3. All inference rules are explicit, named, and documented.
  4. The enricher records which rules fired in `intent.extraction_notes`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..schema.scene_intent_schema import (
    AssetRequirement,
    SceneIntent,
    SceneZone,
)

# ---------------------------------------------------------------------------
# Inference rule tables
# ---------------------------------------------------------------------------

# (trigger_field, trigger_value, target_field, inferred_value, note)
# Applied to SINGLE fields only.  target_field must NOT already have a value.
_FIELD_INFERENCE_RULES: List[Tuple[str, Any, str, Any, str]] = [
    # Destruction level → mood
    ("destruction_level", "heavy",        "mood",         "dramatic",
     "Inferred mood 'dramatic' from destruction_level 'heavy'"),
    ("destruction_level", "catastrophic", "mood",         "chaotic",
     "Inferred mood 'chaotic' from destruction_level 'catastrophic'"),
    ("destruction_level", "moderate",     "cinematic_style", "action",
     "Inferred cinematic_style 'action' from destruction_level 'moderate'"),
    ("destruction_level", "heavy",        "cinematic_style", "action",
     "Inferred cinematic_style 'action' from destruction_level 'heavy'"),

    # Time of day → lighting style
    ("time_of_day", "night",   "lighting_style", "night",
     "Inferred lighting_style 'night' from time_of_day 'night'"),
    ("time_of_day", "dusk",    "lighting_style", "golden_hour",
     "Inferred lighting_style 'golden_hour' from time_of_day 'dusk'"),
    ("time_of_day", "dawn",    "lighting_style", "golden_hour",
     "Inferred lighting_style 'golden_hour' from time_of_day 'dawn'"),
    ("time_of_day", "overcast","lighting_style", "overcast_diffuse",
     "Inferred lighting_style 'overcast_diffuse' from time_of_day 'overcast'"),

    # Lighting style → time of day
    ("lighting_style", "night",        "time_of_day", "night",
     "Inferred time_of_day 'night' from lighting_style 'night'"),
    ("lighting_style", "golden_hour",  "time_of_day", "dusk",
     "Inferred time_of_day 'dusk' from lighting_style 'golden_hour'"),

    # Environment → scale
    ("environment", "urban",       "scale", "urban",
     "Inferred scale 'urban' from environment 'urban'"),
    ("environment", "landscape",   "scale", "landscape",
     "Inferred scale 'landscape' from environment 'landscape'"),
    ("environment", "interior",    "scale", "architectural",
     "Inferred scale 'architectural' from environment 'interior'"),
    ("environment", "space",       "scale", "planetary",
     "Inferred scale 'planetary' from environment 'space'"),

    # Weather → atmospheric effects (handled separately via list merge)
]


# (trigger_field, trigger_value, effect_to_add)
_ATMOSPHERIC_INFERENCE_RULES: List[Tuple[str, Any, str]] = [
    ("weather",            "smoke",          "smoke"),
    ("weather",            "dust",           "dust"),
    ("weather",            "dust",           "haze"),
    ("weather",            "fog",            "haze"),
    ("weather",            "fog",            "mist"),
    ("weather",            "rain",           "mist"),
    ("weather",            "storm",          "rain"),
    ("lighting_style",     "practical_fire", "embers"),
    ("lighting_style",     "practical_fire", "smoke"),
    ("destruction_level",  "heavy",          "smoke"),
    ("destruction_level",  "heavy",          "debris_particles"),
    ("destruction_level",  "catastrophic",   "smoke"),
    ("destruction_level",  "catastrophic",   "debris_particles"),
    ("destruction_level",  "catastrophic",   "embers"),
]


# (trigger_field, trigger_value, fx_type_to_add)
# Adds FX hints to existing zones or creates a center zone if none exists.
_FX_INFERENCE_RULES: List[Tuple[str, Any, str]] = [
    ("destruction_level", "heavy",        "rbd"),
    ("destruction_level", "catastrophic", "rbd"),
    ("weather",           "dust",         "dust"),
    ("weather",           "smoke",        "pyro"),
    ("weather",           "storm",        "pyro"),
]


# Keyword-based environment inferences: (keyword, field, value)
_KEYWORD_INFERENCE_RULES: List[Tuple[str, str, Any]] = [
    ("explosion",   "destruction_level", "heavy"),
    ("explode",     "destruction_level", "heavy"),
    ("apocalyptic", "destruction_level", "catastrophic"),
    ("apocalypse",  "destruction_level", "catastrophic"),
    ("ruins",       "destruction_level", "moderate"),
    ("ruin",        "destruction_level", "moderate"),
    ("battlefield", "destruction_level", "heavy"),
    ("warzone",     "destruction_level", "heavy"),
    ("missile",     "destruction_level", "heavy"),
    ("bomb",        "destruction_level", "heavy"),
    ("wildfire",    "weather",           "smoke"),
    ("hurricane",   "weather",           "storm"),
    ("typhoon",     "weather",           "storm"),
    ("blizzard",    "weather",           "snow"),
    ("night",       "time_of_day",       "night"),
    ("sunset",      "time_of_day",       "dusk"),
    ("sunrise",     "time_of_day",       "dawn"),
    ("golden hour", "time_of_day",       "dusk"),
]


# Asset type suggestions by keyword: (keyword, asset_type, description, required)
_KEYWORD_ASSET_RULES: List[Tuple[str, str, str, bool]] = [
    ("city",       "structure",  "urban building",          True),
    ("urban",      "structure",  "urban building",          True),
    ("building",   "structure",  "building",                True),
    ("vehicle",    "vehicle",    "vehicle",                 False),
    ("car",        "vehicle",    "automobile",              False),
    ("truck",      "vehicle",    "heavy vehicle",           False),
    ("tree",       "vegetation", "tree",                    False),
    ("forest",     "vegetation", "forest tree",             True),
    ("military",   "vehicle",    "military vehicle",        False),
    ("tank",       "vehicle",    "military tank",           False),
    ("aircraft",   "vehicle",    "aircraft",                False),
    ("plane",      "vehicle",    "aircraft",                False),
    ("helicopter", "vehicle",    "helicopter",              False),
    ("crowd",      "character",  "crowd character",         False),
    ("people",     "character",  "pedestrian character",    False),
]


class SceneIntentEnricher:
    """Deterministic inference engine that fills in implied scene intent fields.

    Usage::

        enricher = SceneIntentEnricher()
        enricher.enrich(intent)   # mutates intent in place; sets enrichment_applied
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enrich(self, intent: SceneIntent) -> None:
        """Run all inference rules against `intent` (mutates in place).

        Args:
            intent: A validated SceneIntent. Non-validated intents are safe
                    to enrich but results may include invalid enum values if
                    the source fields are bad.
        """
        notes_before = len(intent.extraction_notes)

        self._apply_keyword_field_rules(intent)
        self._apply_field_inference_rules(intent)
        self._apply_atmospheric_inference(intent)
        self._apply_fx_inference(intent)
        self._apply_keyword_assets(intent)

        if len(intent.extraction_notes) > notes_before:
            intent.enrichment_applied = True

    # ------------------------------------------------------------------
    # Private inference phases
    # ------------------------------------------------------------------

    def _apply_keyword_field_rules(self, intent: SceneIntent) -> None:
        """Infer field values from keywords when the field is not set."""
        for keyword, target_field, target_value in _KEYWORD_INFERENCE_RULES:
            # Check if any keyword matches (case-insensitive)
            if not any(keyword.lower() in kw.lower() for kw in intent.keywords):
                continue
            current = getattr(intent, target_field, None)
            if current is None:
                setattr(intent, target_field, target_value)
                intent.extraction_notes.append(
                    f"Inferred {target_field}='{target_value}' from keyword '{keyword}'"
                )

    def _apply_field_inference_rules(self, intent: SceneIntent) -> None:
        """Infer fields from other fields using the rule table."""
        intent_dict = intent.to_dict()
        for trigger_field, trigger_val, target_field, target_val, note in _FIELD_INFERENCE_RULES:
            if intent_dict.get(trigger_field) != trigger_val:
                continue
            current = getattr(intent, target_field, None)
            if current is None:
                setattr(intent, target_field, target_val)
                intent.extraction_notes.append(note)

    def _apply_atmospheric_inference(self, intent: SceneIntent) -> None:
        """Add inferred atmospheric effects that are not already present."""
        intent_dict = intent.to_dict()
        existing = set(intent.atmospheric_effects)
        for trigger_field, trigger_val, effect in _ATMOSPHERIC_INFERENCE_RULES:
            if intent_dict.get(trigger_field) != trigger_val:
                continue
            if effect not in existing:
                intent.atmospheric_effects.append(effect)
                existing.add(effect)
                intent.extraction_notes.append(
                    f"Inferred atmospheric_effect '{effect}' from {trigger_field}='{trigger_val}'"
                )

    def _apply_fx_inference(self, intent: SceneIntent) -> None:
        """Add inferred FX types to the scene's center zone (creating it if needed)."""
        intent_dict = intent.to_dict()
        fired_fx: List[str] = []

        for trigger_field, trigger_val, fx_type in _FX_INFERENCE_RULES:
            if intent_dict.get(trigger_field) == trigger_val:
                fired_fx.append(fx_type)

        if not fired_fx:
            return

        # Collect FX already declared across all zones
        existing_fx: set = set()
        for z in intent.zones:
            existing_fx.update(z.fx_types)

        new_fx = [fx for fx in fired_fx if fx not in existing_fx]
        if not new_fx:
            return

        # Add to existing center zone or create one
        center_zones = [z for z in intent.zones if z.zone_type == "center"]
        if center_zones:
            target_zone = center_zones[0]
        else:
            target_zone = SceneZone(zone_type="center", priority=8)
            intent.zones.append(target_zone)

        for fx in new_fx:
            target_zone.fx_types.append(fx)
            intent.extraction_notes.append(
                f"Inferred FX type '{fx}' for center zone"
            )

    def _apply_keyword_assets(self, intent: SceneIntent) -> None:
        """Add asset requirements implied by prompt keywords."""
        existing_types = {a.asset_type for a in intent.asset_requirements}

        for keyword, asset_type, description, required in _KEYWORD_ASSET_RULES:
            if asset_type in existing_types:
                continue
            if not any(keyword.lower() in kw.lower() for kw in intent.keywords):
                continue
            intent.asset_requirements.append(
                AssetRequirement(
                    asset_type=asset_type,
                    description=description,
                    required=required,
                    provider="unknown",
                )
            )
            existing_types.add(asset_type)
            intent.extraction_notes.append(
                f"Inferred asset_requirement type='{asset_type}' from keyword '{keyword}'"
            )


# ---------------------------------------------------------------------------
# Shared instance
# ---------------------------------------------------------------------------

_enricher: Optional[SceneIntentEnricher] = None


def get_scene_intent_enricher() -> SceneIntentEnricher:
    """Return the shared SceneIntentEnricher instance."""
    global _enricher
    if _enricher is None:
        _enricher = SceneIntentEnricher()
    return _enricher


def reset_scene_intent_enricher_for_tests() -> None:
    """Reset shared instance for test isolation."""
    global _enricher
    _enricher = None
