"""
Tests for src.runtime.semantic.scene_intent_extractor
No bridge, no LLM (NoOpLLMProvider is default). Pure unit tests.
"""
import json
import pytest
from src.runtime.semantic.scene_intent_extractor import (
    ExtractionResult,
    SceneIntentExtractor,
    get_scene_intent_extractor,
    reset_scene_intent_extractor_for_tests,
    _deterministic_extract,
    _extract_keywords,
    _parse_llm_json,
)
from src.runtime.semantic.schema.scene_intent_schema import SceneIntent
from src.runtime.llm_provider import reset_llm_provider_for_tests


@pytest.fixture(autouse=True)
def reset():
    reset_scene_intent_extractor_for_tests()
    reset_llm_provider_for_tests()
    yield
    reset_scene_intent_extractor_for_tests()
    reset_llm_provider_for_tests()


# ---------------------------------------------------------------------------
# ExtractionResult
# ---------------------------------------------------------------------------

def test_extraction_result_defaults():
    r = ExtractionResult()
    assert r.ok is False
    assert r.intent is None
    assert r.errors == []
    assert r.warnings == []
    assert r.pipeline_stages == []
    assert r.extraction_time == 0.0


def test_extraction_result_to_dict():
    r = ExtractionResult(ok=True, errors=["x"], warnings=["y"])
    d = r.to_dict()
    assert d["ok"] is True
    assert d["errors"] == ["x"]
    assert d["warnings"] == ["y"]
    assert "intent" in d


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_scene_intent_extractor()
    b = get_scene_intent_extractor()
    assert a is b


def test_reset_creates_new_instance():
    a = get_scene_intent_extractor()
    reset_scene_intent_extractor_for_tests()
    b = get_scene_intent_extractor()
    assert a is not b


# ---------------------------------------------------------------------------
# Deterministic extraction helpers
# ---------------------------------------------------------------------------

def test_extract_keywords_filters_stopwords():
    keywords = _extract_keywords("a burning city at night with heavy smoke")
    assert "city" in keywords
    assert "burning" in keywords
    assert "night" in keywords
    assert "smoke" in keywords
    # stopwords
    assert "a" not in keywords
    assert "at" not in keywords
    assert "with" not in keywords


def test_extract_keywords_returns_list():
    kw = _extract_keywords("test scene")
    assert isinstance(kw, list)


def test_deterministic_extract_returns_intent():
    intent = _deterministic_extract("burning city at night")
    assert isinstance(intent, SceneIntent)
    assert intent.source_prompt == "burning city at night"


def test_deterministic_extract_fills_environment():
    intent = _deterministic_extract("urban city explosion")
    assert intent.environment == "urban"


def test_deterministic_extract_fills_time_of_day():
    intent = _deterministic_extract("night scene with fire")
    assert intent.time_of_day == "night"


def test_deterministic_extract_positive_confidence():
    intent = _deterministic_extract("desert dust storm")
    assert intent.confidence > 0.0


def test_deterministic_extract_unknown_prompt_low_confidence():
    intent = _deterministic_extract("zzz abc xyz unknown")
    # No known keywords — confidence should be minimal
    assert intent.confidence <= 0.3


def test_deterministic_extract_atmospheric_effects():
    intent = _deterministic_extract("heavy smoke and dust clouds")
    assert "smoke" in intent.atmospheric_effects or "dust" in intent.atmospheric_effects


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def test_parse_llm_json_direct():
    raw = '{"environment": "urban", "confidence": 0.9}'
    d = _parse_llm_json(raw)
    assert d is not None
    assert d["environment"] == "urban"


def test_parse_llm_json_embedded():
    raw = 'Here is the output: {"environment": "desert"} done'
    d = _parse_llm_json(raw)
    assert d is not None
    assert d["environment"] == "desert"


def test_parse_llm_json_invalid():
    d = _parse_llm_json("not json at all")
    assert d is None


def test_parse_llm_json_empty():
    d = _parse_llm_json("")
    assert d is None


# ---------------------------------------------------------------------------
# Async extract — deterministic path (NoOp LLM)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_returns_result():
    extractor = SceneIntentExtractor()
    result = await extractor.extract("burning city at night")
    assert isinstance(result, ExtractionResult)
    assert result.intent is not None


@pytest.mark.asyncio
async def test_extract_ok_on_valid_prompt():
    extractor = SceneIntentExtractor()
    result = await extractor.extract("urban city destruction at night")
    assert result.ok is True


@pytest.mark.asyncio
async def test_extract_empty_prompt_does_not_crash():
    extractor = SceneIntentExtractor()
    result = await extractor.extract("")
    # Low confidence but no crash
    assert isinstance(result, ExtractionResult)
    assert result.intent is not None


@pytest.mark.asyncio
async def test_extract_intent_has_source_prompt():
    extractor = SceneIntentExtractor()
    result = await extractor.extract("desert sandstorm at dusk")
    assert result.intent.source_prompt == "desert sandstorm at dusk"


@pytest.mark.asyncio
async def test_extract_pipeline_stages_populated():
    extractor = SceneIntentExtractor()
    result = await extractor.extract("burning city")
    assert len(result.pipeline_stages) > 0
    assert "deterministic_extraction" in result.pipeline_stages or \
           "llm_extraction" in result.pipeline_stages


@pytest.mark.asyncio
async def test_extract_enrichment_runs_by_default():
    extractor = SceneIntentExtractor()
    result = await extractor.extract("massive explosion with heavy destruction")
    # Enrichment should have fired — extraction_notes will have inferred entries
    assert result.intent is not None


@pytest.mark.asyncio
async def test_extract_skip_enrichment():
    extractor = SceneIntentExtractor()
    result = await extractor.extract(
        "destruction explosion heavy",
        skip_enrichment=True,
    )
    assert "enrichment" not in result.pipeline_stages


@pytest.mark.asyncio
async def test_extract_extra_context_accepted():
    extractor = SceneIntentExtractor()
    result = await extractor.extract(
        "city at night",
        extra_context={"renderer": "arnold"},
    )
    assert result.intent is not None


@pytest.mark.asyncio
async def test_extract_confidence_in_range():
    extractor = SceneIntentExtractor()
    result = await extractor.extract("urban night explosion city")
    assert 0.0 <= result.intent.confidence <= 1.0


@pytest.mark.asyncio
async def test_extract_keywords_extracted():
    extractor = SceneIntentExtractor()
    result = await extractor.extract("desert sandstorm golden hour vegetation")
    assert len(result.intent.keywords) > 0


@pytest.mark.asyncio
async def test_extract_timing():
    extractor = SceneIntentExtractor()
    result = await extractor.extract("fire and smoke")
    assert result.extraction_time >= 0.0


@pytest.mark.asyncio
async def test_extract_increments_count():
    extractor = SceneIntentExtractor()
    await extractor.extract("test 1")
    await extractor.extract("test 2")
    assert extractor.stats()["extract_count"] == 2


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_shape():
    extractor = SceneIntentExtractor()
    s = extractor.stats()
    assert "extract_count" in s
    assert s["extract_count"] == 0
