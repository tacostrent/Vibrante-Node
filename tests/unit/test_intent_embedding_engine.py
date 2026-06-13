"""Tests for intent_embedding_engine.py (Tier 12.8)."""
from __future__ import annotations
import pytest
from src.runtime.assets.vector_search import (
    DeterministicEmbeddingProvider, ParsedIntent,
    get_intent_embedding_engine, reset_intent_embedding_engine_for_tests,
    get_intent_parser, reset_intent_parser_for_tests,
    set_embedding_provider, reset_embedding_provider_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_intent_embedding_engine_for_tests()
    reset_intent_parser_for_tests()
    reset_embedding_provider_for_tests()
    set_embedding_provider(DeterministicEmbeddingProvider())
    yield
    reset_intent_embedding_engine_for_tests()
    reset_intent_parser_for_tests()
    reset_embedding_provider_for_tests()


class TestIntentEmbeddingEngine:
    def test_embed_query_returns_vector(self):
        ev = get_intent_embedding_engine().embed_query("industrial hangar hero machinery")
        assert len(ev.vector) == 128

    def test_build_intent_embedding(self):
        parsed = get_intent_parser().parse("robotics lab support sensor")
        ev = get_intent_embedding_engine().build_intent_embedding(parsed)
        assert len(ev.vector) == 128

    def test_embed_environment_request(self):
        ev = get_intent_embedding_engine().embed_environment_request("industrial_hangar")
        assert len(ev.vector) == 128

    def test_embed_environment_with_context(self):
        ev = get_intent_embedding_engine().embed_environment_request(
            "industrial_hangar", context="weathered machinery", role="hero"
        )
        assert len(ev.vector) == 128

    def test_embed_empty_query(self):
        ev = get_intent_embedding_engine().embed_query("")
        assert len(ev.vector) == 128

    def test_embed_parsed_dict(self):
        parsed = get_intent_parser().parse("control room console monitor")
        ev = get_intent_embedding_engine().embed_parsed_dict(parsed.to_dict())
        assert len(ev.vector) == 128

    def test_different_intents_differ(self):
        e1 = get_intent_embedding_engine().embed_query("industrial hangar")
        e2 = get_intent_embedding_engine().embed_query("robotics lab")
        assert e1.vector != e2.vector

    def test_deterministic(self):
        e1 = get_intent_embedding_engine().embed_query("abandoned factory rust decay")
        e2 = get_intent_embedding_engine().embed_query("abandoned factory rust decay")
        assert e1.vector == e2.vector

    def test_statistics_increments(self):
        before = get_intent_embedding_engine().get_statistics()["embed_count"]
        get_intent_embedding_engine().embed_query("test")
        assert get_intent_embedding_engine().get_statistics()["embed_count"] > before
