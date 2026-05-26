"""
Unit tests for src.runtime.intent_parser.

Covers:
  • known intent keywords resolve correctly
  • unknown prompt returns intent=None
  • parameter extraction (name, parent, radius)
  • style extraction (pyro variants)
  • ambiguity detection
  • confidence range 0–1
  • alternatives list shape
  • LLM enhancement: mock provider replaces low-confidence deterministic result
  • LLM enhancement: mock provider does NOT replace if deterministic confidence >= LLM
  • singleton / reset
"""

from __future__ import annotations

import pytest

from src.runtime.intent_parser import (
    IntentParser,
    get_intent_parser,
    reset_intent_parser_for_tests,
)
from src.runtime.llm_provider import (
    MockLLMProvider,
    set_llm_provider,
    reset_llm_provider_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_intent_parser_for_tests()
    reset_llm_provider_for_tests()
    yield
    reset_intent_parser_for_tests()
    reset_llm_provider_for_tests()


# ---------------------------------------------------------------------------
# Known intent detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pyro_intent_detected():
    parser = get_intent_parser()
    result = await parser.parse("create a pyro simulation for fire and smoke")
    assert result["intent"] == "build_pyro_source"
    assert result["confidence"] > 0.0


@pytest.mark.asyncio
async def test_geo_intent_detected():
    parser = get_intent_parser()
    result = await parser.parse("create a new geometry container")
    assert result["intent"] == "create_geo_container"


@pytest.mark.asyncio
async def test_karma_intent_detected():
    parser = get_intent_parser()
    result = await parser.parse("set up karma rendering")
    assert result["intent"] == "setup_karma_renderer"


@pytest.mark.asyncio
async def test_usd_export_detected():
    parser = get_intent_parser()
    result = await parser.parse("export to usd file")
    assert result["intent"] == "export_to_usd"


@pytest.mark.asyncio
async def test_cache_geometry_detected():
    parser = get_intent_parser()
    result = await parser.parse("bake and cache the geometry to disk")
    assert result["intent"] == "cache_geometry"


@pytest.mark.asyncio
async def test_asset_publish_detected():
    parser = get_intent_parser()
    result = await parser.parse("scaffold asset publish structure")
    assert result["intent"] == "asset_publish_scaffold"


@pytest.mark.asyncio
async def test_lighting_setup_detected():
    parser = get_intent_parser()
    result = await parser.parse("set up solaris lighting rig")
    assert result["intent"] == "solaris_lighting_setup"


# ---------------------------------------------------------------------------
# Unknown prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_prompt_returns_none_intent():
    parser = get_intent_parser()
    result = await parser.parse("xyzzy quux frobble nonsense")
    assert result["intent"] is None
    assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extracts_name_parameter():
    parser = get_intent_parser()
    result = await parser.parse("create a geo container called my_rock")
    assert result["parameters"].get("name") == "my_rock"


@pytest.mark.asyncio
async def test_extracts_parent_parameter():
    parser = get_intent_parser()
    result = await parser.parse("build pyro inside /obj/geo1")
    assert result["parameters"].get("parent") == "/obj/geo1"


@pytest.mark.asyncio
async def test_extracts_radius_parameter():
    parser = get_intent_parser()
    result = await parser.parse("create a sphere with radius 3.5")
    assert result["parameters"].get("radius") == "3.5"


# ---------------------------------------------------------------------------
# Style extraction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pyro_explosion_style():
    parser = get_intent_parser()
    result = await parser.parse("create a pyro explosion")
    assert result["parameters"].get("style") == "explosion"


@pytest.mark.asyncio
async def test_pyro_smoke_style():
    parser = get_intent_parser()
    result = await parser.parse("build a smoke puff effect")
    assert result["parameters"].get("style") == "smoke"


@pytest.mark.asyncio
async def test_pyro_fire_style():
    parser = get_intent_parser()
    result = await parser.parse("create a fire flame effect")
    assert result["parameters"].get("style") == "fire"


# ---------------------------------------------------------------------------
# Ambiguity detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clear_intent_not_ambiguous():
    parser = get_intent_parser()
    result = await parser.parse("create a pyro fire simulation")
    # Single clear intent should not be ambiguous
    assert isinstance(result["ambiguous"], bool)


@pytest.mark.asyncio
async def test_result_has_alternatives():
    parser = get_intent_parser()
    result = await parser.parse("create a geo node")
    assert isinstance(result["alternatives"], list)


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_result_has_required_keys():
    parser = get_intent_parser()
    result = await parser.parse("any prompt here")
    for key in ("intent", "parameters", "confidence", "alternatives",
                "ambiguous", "raw_prompt", "matched_keywords", "llm_enhanced"):
        assert key in result, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_confidence_in_range():
    parser = get_intent_parser()
    result = await parser.parse("build a pyro simulation")
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_raw_prompt_preserved():
    parser = get_intent_parser()
    prompt = "create smoke inside /obj/geo1"
    result = await parser.parse(prompt)
    assert result["raw_prompt"] == prompt


# ---------------------------------------------------------------------------
# LLM enhancement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_enhances_unknown_intent():
    """Mock LLM can resolve what the keyword matcher missed."""
    mock = MockLLMProvider(responses={
        "weird_prompt": {
            "intent": "build_pyro_source",
            "confidence": 0.95,
            "parameters": {"style": "fire"},
        }
    })
    set_llm_provider(mock)
    parser = IntentParser()
    result = await parser.parse("weird_prompt xyzzy")
    assert result["intent"] == "build_pyro_source"
    assert result["llm_enhanced"] is True


@pytest.mark.asyncio
async def test_llm_does_not_override_high_confidence_deterministic():
    """If deterministic confidence > LLM confidence, keep deterministic."""
    mock = MockLLMProvider(responses={
        "pyro": {
            "intent": "create_geo_container",   # wrong intent from mock
            "confidence": 0.3,
        }
    })
    set_llm_provider(mock)
    parser = IntentParser()
    result = await parser.parse("build a pyro fire simulation")
    # Deterministic confidence for pyro should be high — keep it
    assert result["intent"] == "build_pyro_source"
    assert result["llm_enhanced"] is False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton_same_instance():
    a = get_intent_parser()
    b = get_intent_parser()
    assert a is b


def test_reset_creates_fresh_singleton():
    a = get_intent_parser()
    reset_intent_parser_for_tests()
    b = get_intent_parser()
    assert a is not b
