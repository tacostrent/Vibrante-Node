"""
Intent Embedding Engine (Tier 12.8)
======================================
Transforms structured intent (ParsedIntent) into embedding vectors for
semantic similarity search.

Methods:
  build_intent_embedding()   — embed a ParsedIntent
  embed_query()              — embed a raw query string
  embed_environment_request()— embed an environment + optional context
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from .embedding_provider import EmbeddingVector, get_embedding_provider
from .intent_parser import ParsedIntent, get_intent_parser


class IntentEmbeddingEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._embed_count = 0

    def build_intent_embedding(self, parsed_intent: ParsedIntent) -> EmbeddingVector:
        """Convert a ParsedIntent into an embedding vector. Never raises."""
        try:
            text = parsed_intent.as_query_text() if hasattr(parsed_intent, "as_query_text") else str(parsed_intent)
            if not text.strip():
                text = parsed_intent.raw_text
            ev = get_embedding_provider().embed_text(text)
            with self._lock:
                self._embed_count += 1
            return ev
        except Exception:
            return EmbeddingVector(vector=[], dimensions=0, provider="error")

    def embed_query(self, query_text: str) -> EmbeddingVector:
        """Parse and embed a raw query string. Never raises."""
        try:
            parsed = get_intent_parser().parse(str(query_text))
            return self.build_intent_embedding(parsed)
        except Exception:
            return EmbeddingVector(vector=[], dimensions=0, provider="error")

    def embed_environment_request(
        self,
        environment: str,
        context: str = "",
        role: str = "",
    ) -> EmbeddingVector:
        """Build an embedding specifically for an environment retrieval request. Never raises."""
        try:
            parts = [
                environment.replace("_", " "),
                role.replace("_", " ") if role else "",
                context,
            ]
            text = " ".join(p for p in parts if p).strip()
            if not text:
                text = environment
            ev = get_embedding_provider().embed_text(text)
            with self._lock:
                self._embed_count += 1
            return ev
        except Exception:
            return EmbeddingVector(vector=[], dimensions=0, provider="error")

    def embed_parsed_dict(self, intent_dict: Dict[str, Any]) -> EmbeddingVector:
        """Embed from a ParsedIntent.to_dict() output."""
        try:
            parsed = ParsedIntent.from_dict(intent_dict)
            return self.build_intent_embedding(parsed)
        except Exception:
            return EmbeddingVector(vector=[], dimensions=0, provider="error")

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"embed_count": self._embed_count}


_INSTANCE: Optional[IntentEmbeddingEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_intent_embedding_engine() -> IntentEmbeddingEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = IntentEmbeddingEngine()
    return _INSTANCE


def reset_intent_embedding_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
