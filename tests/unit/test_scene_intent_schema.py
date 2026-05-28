"""
Tests for src.runtime.semantic.schema.scene_intent_schema
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.semantic.schema.scene_intent_schema import (
    SCHEMA_VERSION,
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
    AssetRequirement,
    SceneZone,
    SceneIntent,
)


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

def test_schema_version_is_string():
    assert isinstance(SCHEMA_VERSION, str)
    assert "." in SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Enum completeness
# ---------------------------------------------------------------------------

def test_environment_types_non_empty():
    assert len(ENVIRONMENT_TYPES) > 5
    assert "urban" in ENVIRONMENT_TYPES
    assert "desert" in ENVIRONMENT_TYPES


def test_destruction_levels_ordered_set():
    assert "none" in DESTRUCTION_LEVELS
    assert "catastrophic" in DESTRUCTION_LEVELS


def test_all_enums_are_frozensets():
    for name, enum in [
        ("environment", ENVIRONMENT_TYPES),
        ("style", STYLE_TYPES),
        ("mood", MOOD_TYPES),
        ("time_of_day", TIME_OF_DAY_VALUES),
        ("weather", WEATHER_TYPES),
        ("scale", SCALE_VALUES),
        ("density", DENSITY_LEVELS),
        ("destruction", DESTRUCTION_LEVELS),
        ("cinematic_style", CINEMATIC_STYLE_VALUES),
        ("lighting_style", LIGHTING_STYLE_VALUES),
        ("zone_types", ZONE_TYPES),
        ("atmospheric", ATMOSPHERIC_EFFECT_TYPES),
        ("providers", ASSET_PROVIDER_VALUES),
    ]:
        assert isinstance(enum, frozenset), f"{name} should be frozenset"
        assert len(enum) > 0, f"{name} should not be empty"


# ---------------------------------------------------------------------------
# AssetRequirement
# ---------------------------------------------------------------------------

def test_asset_requirement_defaults():
    a = AssetRequirement(asset_type="vehicle")
    assert a.asset_type == "vehicle"
    assert a.description is None
    assert a.quantity is None
    assert a.style_hints == []
    assert a.required is False
    assert a.provider == "unknown"


def test_asset_requirement_to_dict():
    a = AssetRequirement(
        asset_type="structure",
        description="damaged building",
        quantity=3,
        style_hints=["brutalist"],
        required=True,
        provider="polyhaven",
    )
    d = a.to_dict()
    assert d["asset_type"] == "structure"
    assert d["description"] == "damaged building"
    assert d["quantity"] == 3
    assert d["style_hints"] == ["brutalist"]
    assert d["required"] is True
    assert d["provider"] == "polyhaven"


def test_asset_requirement_round_trip():
    a = AssetRequirement(asset_type="vegetation", required=True, provider="local")
    d = a.to_dict()
    a2 = AssetRequirement.from_dict(d)
    assert a2.asset_type == "vegetation"
    assert a2.required is True
    assert a2.provider == "local"


def test_asset_requirement_from_dict_missing_fields():
    a = AssetRequirement.from_dict({"asset_type": "rock"})
    assert a.asset_type == "rock"
    assert a.required is False


# ---------------------------------------------------------------------------
# SceneZone
# ---------------------------------------------------------------------------

def test_scene_zone_defaults():
    z = SceneZone(zone_type="center")
    assert z.zone_type == "center"
    assert z.description is None
    assert z.assets == []
    assert z.fx_types == []
    assert z.priority == 5


def test_scene_zone_to_dict():
    z = SceneZone(
        zone_type="foreground",
        description="burning ruins",
        fx_types=["pyro", "rbd"],
        priority=9,
    )
    d = z.to_dict()
    assert d["zone_type"] == "foreground"
    assert d["description"] == "burning ruins"
    assert d["fx_types"] == ["pyro", "rbd"]
    assert d["priority"] == 9


def test_scene_zone_round_trip():
    z = SceneZone(
        zone_type="background",
        assets=[AssetRequirement(asset_type="sky")],
        priority=3,
    )
    d = z.to_dict()
    z2 = SceneZone.from_dict(d)
    assert z2.zone_type == "background"
    assert z2.priority == 3
    assert len(z2.assets) == 1
    assert z2.assets[0].asset_type == "sky"


# ---------------------------------------------------------------------------
# SceneIntent
# ---------------------------------------------------------------------------

def test_scene_intent_defaults():
    intent = SceneIntent()
    assert intent.schema_version == SCHEMA_VERSION
    assert intent.source_prompt == ""
    assert intent.environment is None
    assert intent.confidence == 0.0
    assert intent.asset_requirements == []
    assert intent.zones == []
    assert intent.atmospheric_effects == []
    assert intent.keywords == []
    assert intent.llm_enhanced is False
    assert intent.enrichment_applied is False


def test_scene_intent_is_valid_property_requires_confidence():
    intent = SceneIntent(confidence=0.0)
    assert intent.is_valid is False

    intent2 = SceneIntent(confidence=0.5)
    assert intent2.is_valid is True


def test_scene_intent_is_valid_false_when_validation_errors():
    intent = SceneIntent(confidence=0.8, validation_errors=["bad field"])
    assert intent.is_valid is False


def test_scene_intent_has_fx_from_zone():
    intent = SceneIntent()
    intent.zones = [SceneZone(zone_type="center", fx_types=["pyro"])]
    assert intent.has_fx is True


def test_scene_intent_has_fx_from_keywords():
    intent = SceneIntent(keywords=["explosion", "fire"])
    assert intent.has_fx is True


def test_scene_intent_has_no_fx():
    intent = SceneIntent(keywords=["mountain", "river"])
    assert intent.has_fx is False


def test_scene_intent_primary_fx_types_deduplicates():
    intent = SceneIntent()
    intent.zones = [
        SceneZone(zone_type="center", fx_types=["pyro", "rbd"]),
        SceneZone(zone_type="foreground", fx_types=["rbd", "flip"]),
    ]
    fx = intent.primary_fx_types
    assert "pyro" in fx
    assert "rbd" in fx
    assert "flip" in fx
    assert fx.count("rbd") == 1  # deduplicated


def test_scene_intent_to_dict_all_keys():
    intent = SceneIntent(
        source_prompt="test",
        environment="urban",
        confidence=0.75,
    )
    d = intent.to_dict()
    required_keys = [
        "intent_id", "schema_version", "source_prompt", "extracted_at",
        "environment", "style", "mood", "time_of_day", "weather",
        "scale", "density", "destruction_level", "cinematic_style",
        "lighting_style", "asset_requirements", "zones",
        "atmospheric_effects", "keywords", "confidence",
        "extraction_notes", "llm_enhanced", "validation_errors",
        "enrichment_applied",
    ]
    for key in required_keys:
        assert key in d, f"Missing key: {key}"


def test_scene_intent_round_trip():
    intent = SceneIntent(
        source_prompt="burning city",
        environment="urban",
        style="cinematic",
        mood="dramatic",
        confidence=0.85,
        keywords=["burning", "city"],
        atmospheric_effects=["smoke"],
        llm_enhanced=True,
    )
    d = intent.to_dict()
    intent2 = SceneIntent.from_dict(d)
    assert intent2.source_prompt == "burning city"
    assert intent2.environment == "urban"
    assert intent2.style == "cinematic"
    assert intent2.mood == "dramatic"
    assert intent2.confidence == 0.85
    assert intent2.keywords == ["burning", "city"]
    assert intent2.atmospheric_effects == ["smoke"]
    assert intent2.llm_enhanced is True


def test_scene_intent_from_dict_partial():
    d = {"source_prompt": "desert storm", "environment": "desert"}
    intent = SceneIntent.from_dict(d)
    assert intent.environment == "desert"
    assert intent.style is None
    assert intent.confidence == 0.0


def test_scene_intent_repr():
    intent = SceneIntent(environment="urban", style="cinematic", confidence=0.9)
    r = repr(intent)
    assert "urban" in r
    assert "cinematic" in r
    assert "0.90" in r


def test_scene_intent_unique_ids():
    a = SceneIntent()
    b = SceneIntent()
    assert a.intent_id != b.intent_id
