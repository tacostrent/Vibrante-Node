"""Tests for embedding_provider.py (Tier 12.8)."""
from __future__ import annotations
import pytest
from src.runtime.assets.vector_search import (
    DeterministicEmbeddingProvider,
    EmbeddingVector,
    get_embedding_provider,
    set_embedding_provider,
    reset_embedding_provider_for_tests,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_embedding_provider_for_tests()
    yield
    reset_embedding_provider_for_tests()


@pytest.fixture(autouse=True)
def _use_deterministic():
    set_embedding_provider(DeterministicEmbeddingProvider())
    yield


class TestDeterministicEmbeddingProvider:
    def test_dimensions(self):
        p = DeterministicEmbeddingProvider()
        assert p.dimensions == 128

    def test_provider_name(self):
        assert DeterministicEmbeddingProvider().provider_name == "deterministic"

    def test_embed_text_returns_128_dims(self):
        ev = DeterministicEmbeddingProvider().embed_text("industrial pipe factory")
        assert len(ev.vector) == 128

    def test_embed_empty_text(self):
        ev = DeterministicEmbeddingProvider().embed_text("")
        assert len(ev.vector) == 128

    def test_embed_none_text(self):
        ev = DeterministicEmbeddingProvider().embed_text(None)
        assert len(ev.vector) == 128

    def test_deterministic_same_input(self):
        p = DeterministicEmbeddingProvider()
        v1 = p.embed_text("industrial hangar machinery")
        v2 = p.embed_text("industrial hangar machinery")
        assert v1.vector == v2.vector

    def test_different_texts_differ(self):
        p = DeterministicEmbeddingProvider()
        v1 = p.embed_text("industrial hangar")
        v2 = p.embed_text("robotics lab sensor")
        # Different texts should produce different vectors
        assert v1.vector != v2.vector

    def test_l2_normalized(self):
        p = DeterministicEmbeddingProvider()
        ev = p.embed_text("pipe factory industrial gear turbine")
        norm_sq = sum(x * x for x in ev.vector)
        # Either zero vector or unit vector
        assert abs(norm_sq - 1.0) < 1e-6 or norm_sq == 0.0

    def test_embed_asset(self):
        p = DeterministicEmbeddingProvider()
        asset = {
            "asset_id": "test", "name": "Industrial Pipe",
            "category": "prop", "tags": ["pipe", "industrial"],
            "environments": ["industrial_hangar"],
        }
        ev = p.embed_asset(asset)
        assert len(ev.vector) == 128

    def test_embed_intent(self):
        p = DeterministicEmbeddingProvider()
        ev = p.embed_intent("industrial hangar hero machinery")
        assert len(ev.vector) == 128
        assert ev.provider == "deterministic"

    def test_batch_embed(self):
        p = DeterministicEmbeddingProvider()
        results = p.batch_embed(["pipe", "robot arm", "control panel"])
        assert len(results) == 3
        assert all(len(ev.vector) == 128 for ev in results)

    def test_to_dict_from_dict(self):
        p = DeterministicEmbeddingProvider()
        ev = p.embed_text("pipe factory")
        d = ev.to_dict()
        r = EmbeddingVector.from_dict(d)
        assert r.vector == ev.vector
        assert r.provider == ev.provider
        assert r.dimensions == 128

    def test_as_list(self):
        p = DeterministicEmbeddingProvider()
        ev = p.embed_text("test")
        assert isinstance(ev.as_list(), list)
        assert len(ev.as_list()) == 128


class TestSingletonProvider:
    def test_get_returns_deterministic_when_st_unavailable(self):
        provider = get_embedding_provider()
        assert provider is not None
        assert provider.dimensions > 0

    def test_set_overrides_singleton(self):
        p = DeterministicEmbeddingProvider()
        set_embedding_provider(p)
        assert get_embedding_provider() is p

    def test_reset_clears_singleton(self):
        set_embedding_provider(DeterministicEmbeddingProvider())
        reset_embedding_provider_for_tests()
        # Next call creates new instance
        p2 = get_embedding_provider()
        assert p2 is not None
