"""
Tests for src.runtime.semantic.enrichers.scene_intent_enricher
No bridge, no LLM. Pure unit tests.
"""
import pytest
from src.runtime.semantic.enrichers.scene_intent_enricher import (
    SceneIntentEnricher,
    get_scene_intent_enricher,
    reset_scene_intent_enricher_for_tests,
)
from src.runtime.semantic.schema.scene_intent_schema import SceneIntent, SceneZone


@pytest.fixture(autouse=True)
def reset():
    reset_scene_intent_enricher_for_tests()
    yield
    reset_scene_intent_enricher_for_tests()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_scene_intent_enricher()
    b = get_scene_intent_enricher()
    assert a is b


def test_reset_creates_new_instance():
    a = get_scene_intent_enricher()
    reset_scene_intent_enricher_for_tests()
    b = get_scene_intent_enricher()
    assert a is not b


# ---------------------------------------------------------------------------
# Field inference
# ---------------------------------------------------------------------------

def test_infer_mood_from_heavy_destruction():
    intent = SceneIntent(destruction_level="heavy", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert intent.mood == "dramatic"
    assert intent.enrichment_applied is True


def test_infer_mood_from_catastrophic_destruction():
    intent = SceneIntent(destruction_level="catastrophic", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert intent.mood == "chaotic"


def test_infer_lighting_from_night():
    intent = SceneIntent(time_of_day="night", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert intent.lighting_style == "night"


def test_infer_lighting_from_dusk():
    intent = SceneIntent(time_of_day="dusk", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert intent.lighting_style == "golden_hour"


def test_infer_time_from_lighting_night():
    intent = SceneIntent(lighting_style="night", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert intent.time_of_day == "night"


def test_infer_scale_from_urban_environment():
    intent = SceneIntent(environment="urban", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert intent.scale == "urban"


def test_no_overwrite_existing_field():
    intent = SceneIntent(
        destruction_level="heavy",
        mood="peaceful",   # already set — should NOT be overwritten
        confidence=0.5,
    )
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    # mood was already set to "peaceful" — enricher must not overwrite
    assert intent.mood == "peaceful"


# ---------------------------------------------------------------------------
# Atmospheric effect inference
# ---------------------------------------------------------------------------

def test_atmospheric_from_smoke_weather():
    intent = SceneIntent(weather="smoke", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert "smoke" in intent.atmospheric_effects


def test_atmospheric_from_dust_weather():
    intent = SceneIntent(weather="dust", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert "dust" in intent.atmospheric_effects
    assert "haze" in intent.atmospheric_effects


def test_atmospheric_from_practical_fire_lighting():
    intent = SceneIntent(lighting_style="practical_fire", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert "embers" in intent.atmospheric_effects
    assert "smoke" in intent.atmospheric_effects


def test_atmospheric_no_duplicate():
    intent = SceneIntent(
        weather="smoke",
        atmospheric_effects=["smoke"],  # already present
        confidence=0.5,
    )
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert intent.atmospheric_effects.count("smoke") == 1


def test_atmospheric_from_heavy_destruction():
    intent = SceneIntent(destruction_level="heavy", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert "smoke" in intent.atmospheric_effects
    assert "debris_particles" in intent.atmospheric_effects


# ---------------------------------------------------------------------------
# FX inference
# ---------------------------------------------------------------------------

def test_fx_inferred_from_heavy_destruction():
    intent = SceneIntent(destruction_level="heavy", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    all_fx = [fx for z in intent.zones for fx in z.fx_types]
    assert "rbd" in all_fx


def test_fx_center_zone_created_when_none():
    intent = SceneIntent(destruction_level="heavy", confidence=0.5)
    assert len(intent.zones) == 0
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert any(z.zone_type == "center" for z in intent.zones)


def test_fx_added_to_existing_center_zone():
    intent = SceneIntent(destruction_level="heavy", confidence=0.5)
    intent.zones = [SceneZone(zone_type="center", priority=8)]
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    center_zones = [z for z in intent.zones if z.zone_type == "center"]
    assert len(center_zones) == 1  # no duplicate zone created
    assert "rbd" in center_zones[0].fx_types


def test_fx_no_duplicate():
    intent = SceneIntent(destruction_level="heavy", confidence=0.5)
    intent.zones = [SceneZone(zone_type="center", fx_types=["rbd"], priority=8)]
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    all_fx = [fx for z in intent.zones for fx in z.fx_types]
    assert all_fx.count("rbd") == 1


# ---------------------------------------------------------------------------
# Keyword-based field inference
# ---------------------------------------------------------------------------

def test_keyword_explosion_infers_destruction():
    intent = SceneIntent(keywords=["explosion"], confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert intent.destruction_level == "heavy"


def test_keyword_apocalyptic_infers_catastrophic():
    intent = SceneIntent(keywords=["apocalyptic", "city"], confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert intent.destruction_level == "catastrophic"


def test_keyword_night_infers_time_of_day():
    intent = SceneIntent(keywords=["night", "rain"], confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert intent.time_of_day == "night"


# ---------------------------------------------------------------------------
# Keyword asset inference
# ---------------------------------------------------------------------------

def test_keyword_city_infers_structure_asset():
    intent = SceneIntent(keywords=["city", "explosion"], confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    types = [a.asset_type for a in intent.asset_requirements]
    assert "structure" in types


def test_keyword_forest_infers_vegetation_required():
    intent = SceneIntent(keywords=["forest", "fire"], confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    veg = [a for a in intent.asset_requirements if a.asset_type == "vegetation"]
    assert len(veg) == 1
    assert veg[0].required is True


def test_no_duplicate_asset_type():
    intent = SceneIntent(keywords=["city", "buildings", "urban"], confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    types = [a.asset_type for a in intent.asset_requirements]
    assert types.count("structure") == 1


# ---------------------------------------------------------------------------
# enrichment_applied flag
# ---------------------------------------------------------------------------

def test_enrichment_applied_when_rules_fire():
    intent = SceneIntent(weather="smoke", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert intent.enrichment_applied is True


def test_enrichment_not_applied_when_no_rules_fire():
    intent = SceneIntent(confidence=0.5)  # no fields set — no rules fire
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert intent.enrichment_applied is False


# ---------------------------------------------------------------------------
# Extraction notes
# ---------------------------------------------------------------------------

def test_extraction_notes_populated():
    intent = SceneIntent(destruction_level="heavy", confidence=0.5)
    enricher = SceneIntentEnricher()
    enricher.enrich(intent)
    assert len(intent.extraction_notes) > 0
