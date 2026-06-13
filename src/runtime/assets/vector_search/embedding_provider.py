"""
Embedding Provider (Tier 12.8)
================================
Deterministic text embeddings with optional sentence-transformers enhancement.

Default (always available):
  DeterministicEmbeddingProvider — 128-dim hash-BOW, no external deps

Optional enhancement (if sentence-transformers installed):
  SentenceTransformersProvider — all-MiniLM-L6-v2 (384 dims)

Provider injection for tests:
  set_embedding_provider(provider)   — override singleton
  reset_embedding_provider_for_tests()
"""
from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .semantic_similarity import l2_normalize

# ---------------------------------------------------------------------------
# Fixed 128-token production vocabulary (position = dimension index 0..127)
# ---------------------------------------------------------------------------
_VOCAB: List[str] = [
    # Environments (0-11)
    "industrial", "hangar", "factory", "crane", "scaffold", "platform",
    "robotics", "robot", "sensor", "scanner", "servo", "automation",
    # Control room (12-17)
    "control", "console", "monitor", "screen", "terminal", "interface",
    # Corridor (18-23)
    "corridor", "door", "vent", "cable", "hatch", "bulkhead",
    # Abandoned (24-29)
    "abandoned", "rust", "decay", "broken", "derelict", "ruin",
    # Production roles (30-35)
    "hero", "support", "foreground", "midground", "background", "dressing",
    # Storytelling (36-40)
    "context", "builder", "reference", "anchor", "atmosphere",
    # Cinematic (41-45)
    "focus", "silhouette", "depth", "balance", "layer",
    # Lookdev (46-55)
    "weathered", "aged", "rusted", "clean", "polished", "worn",
    "damaged", "pristine", "sci_fi", "futuristic",
    # Materials (56-65)
    "metal", "steel", "iron", "concrete", "wood", "glass",
    "plastic", "rubber", "ceramic", "fabric",
    # Asset categories (66-77)
    "prop", "vehicle", "character", "machinery", "architecture", "vegetation",
    "equipment", "furniture", "tool", "electronics", "weapon", "creature",
    # Production concepts (78-89)
    "pipe", "gear", "turbine", "boiler", "valve", "flange",
    "arm", "joint", "beam", "panel", "rack", "module",
    # Descriptors (90-99)
    "large", "small", "heavy", "light", "primary", "secondary",
    "main", "detail", "ambient", "sparse",
    # Cinematic extras (100-109)
    "cinematic", "production", "semantic", "intent", "scene", "layout",
    "zone", "placement", "environment", "story",
    # Overflow buffer (110-127) — used for OOV tokens
    "a", "b", "c", "d", "e", "f", "g", "h",
    "i", "j", "k", "l", "m", "n", "o", "p",
    "q", "r",
]

assert len(_VOCAB) == 128, f"_VOCAB length must be 128, got {len(_VOCAB)}"

_VOCAB_INDEX: Dict[str, int] = {w: i for i, w in enumerate(_VOCAB)}
_OOV_OFFSET = 110  # overflow dimensions start here
_OOV_DIMS = 128 - _OOV_OFFSET  # 18 overflow dims


def _stable_hash(s: str) -> int:
    """Deterministic hash using SHA-256 (not affected by PYTHONHASHSEED)."""
    return int(hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest(), 16)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EmbeddingVector:
    vector:     List[float]
    dimensions: int
    provider:   str
    text:       str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vector":     list(self.vector),
            "dimensions": int(self.dimensions),
            "provider":   str(self.provider),
            "text":       str(self.text),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EmbeddingVector":
        d = d if isinstance(d, dict) else {}
        return cls(
            vector=list(d.get("vector") or []),
            dimensions=int(d.get("dimensions", 0)),
            provider=str(d.get("provider", "")),
            text=str(d.get("text", "")),
        )

    def as_list(self) -> List[float]:
        return list(self.vector)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class EmbeddingProvider:
    """Abstract embedding provider interface."""

    @property
    def dimensions(self) -> int:
        raise NotImplementedError

    @property
    def provider_name(self) -> str:
        raise NotImplementedError

    def embed_text(self, text: str) -> EmbeddingVector:
        raise NotImplementedError

    def embed_asset(self, asset_dict: Dict[str, Any]) -> EmbeddingVector:
        """Build embedding from an asset dict using its semantic fields."""
        text = _asset_to_text(asset_dict)
        return self.embed_text(text)

    def embed_intent(self, intent_text: str) -> EmbeddingVector:
        return self.embed_text(str(intent_text))

    def batch_embed(self, texts: List[str]) -> List[EmbeddingVector]:
        return [self.embed_text(t) for t in texts]


def _asset_to_text(asset: Dict[str, Any]) -> str:
    """Convert an asset dict to a rich text representation for embedding."""
    parts = [
        str(asset.get("name", "")),
        str(asset.get("category", "")),
        " ".join(asset.get("tags", [])),
        " ".join(asset.get("semantic_tags", [])),
        " ".join(asset.get("environments", [])),
        " ".join(asset.get("roles", [])),
        " ".join(asset.get("lookdev", []) or asset.get("lookdev_tags", [])),
        str(asset.get("storytelling", "") or asset.get("story_role", "")),
        " ".join(asset.get("cinematic_usage", [])),
    ]
    return " ".join(p for p in parts if p).lower()


# ---------------------------------------------------------------------------
# DeterministicEmbeddingProvider
# ---------------------------------------------------------------------------

class DeterministicEmbeddingProvider(EmbeddingProvider):
    """
    128-dimensional deterministic bag-of-words embedding.

    Uses a fixed production vocabulary for the first 110 dimensions,
    then stable-hash overflow for unknown tokens.
    No external dependencies. Same input always produces the same output.
    """

    @property
    def dimensions(self) -> int:
        return 128

    @property
    def provider_name(self) -> str:
        return "deterministic"

    def embed_text(self, text: str) -> EmbeddingVector:
        """Embed text to a 128-dim deterministic vector. Never raises."""
        try:
            text = str(text or "").lower()
            tokens = text.split()
            vec = [0.0] * 128

            for token in tokens:
                if token in _VOCAB_INDEX:
                    vec[_VOCAB_INDEX[token]] += 1.0
                else:
                    # Overflow: map to [110, 127] via stable hash
                    idx = _OOV_OFFSET + (_stable_hash(token) % _OOV_DIMS)
                    vec[idx] += 1.0

            return EmbeddingVector(
                vector=l2_normalize(vec),
                dimensions=128,
                provider="deterministic",
                text=text[:200],
            )
        except Exception:
            return EmbeddingVector(vector=[0.0] * 128, dimensions=128, provider="deterministic")


# ---------------------------------------------------------------------------
# SentenceTransformersProvider (optional)
# ---------------------------------------------------------------------------

class SentenceTransformersProvider(EmbeddingProvider):
    """
    Sentence-transformers based provider using all-MiniLM-L6-v2 (384 dims).
    Falls back gracefully if sentence_transformers is not installed or model
    is not cached.
    """

    _MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self) -> None:
        self._model = None
        self._dims = 384
        self._load_model()

    def _load_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._model = SentenceTransformer(self._MODEL_NAME)
        except Exception:
            self._model = None

    @property
    def dimensions(self) -> int:
        return self._dims

    @property
    def provider_name(self) -> str:
        return "sentence_transformers"

    @property
    def is_available(self) -> bool:
        return self._model is not None

    def embed_text(self, text: str) -> EmbeddingVector:
        if self._model is None:
            raise RuntimeError("sentence_transformers model not available")
        try:
            vec = self._model.encode(str(text), show_progress_bar=False).tolist()
            return EmbeddingVector(
                vector=vec,
                dimensions=len(vec),
                provider="sentence_transformers",
                text=str(text)[:200],
            )
        except Exception as exc:
            raise RuntimeError(f"SentenceTransformersProvider.embed_text failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EmbeddingProvider] = None
_INSTANCE_LOCK = threading.Lock()


def _create_best_provider() -> EmbeddingProvider:
    try:
        p = SentenceTransformersProvider()
        if p.is_available:
            return p
    except Exception:
        pass
    return DeterministicEmbeddingProvider()


def get_embedding_provider() -> EmbeddingProvider:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = _create_best_provider()
    return _INSTANCE


def set_embedding_provider(provider: EmbeddingProvider) -> None:
    """Override the singleton — for tests and dependency injection."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = provider


def reset_embedding_provider_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
