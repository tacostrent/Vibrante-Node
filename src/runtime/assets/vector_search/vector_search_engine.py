"""
Vector Search Engine (Tier 12.8)
===================================
Nearest-neighbor asset retrieval using the vector store and intent embeddings.

Methods:
  search()              — free-text semantic search
  search_environment()  — assets for a specific environment
  search_role()         — assets for a specific production role
  search_storytelling() — assets for a storytelling role
  search_cinematic()    — assets for a cinematic usage
  search_top_k()        — return top-k asset IDs
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .asset_vector_store import get_asset_vector_store, VectorSearchResult
from .intent_embedding_engine import get_intent_embedding_engine
from .asset_embedding_builder import get_asset_embedding_builder
from .retrieval_statistics import get_retrieval_statistics


@dataclass
class VectorSearchResponse:
    ok:          bool = True
    query_text:  str = ""
    results:     List[Dict[str, Any]] = field(default_factory=list)
    total:       int = 0
    duration_ms: float = 0.0
    provider:    str = ""
    errors:      List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":          bool(self.ok),
            "query_text":  str(self.query_text),
            "results":     list(self.results),
            "total":       int(self.total),
            "duration_ms": float(self.duration_ms),
            "provider":    str(self.provider),
            "errors":      list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VectorSearchResponse":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", True)),
            query_text=str(d.get("query_text", "")),
            results=list(d.get("results") or []),
            total=int(d.get("total", 0)),
            duration_ms=float(d.get("duration_ms", 0.0)),
            provider=str(d.get("provider", "")),
            errors=list(d.get("errors") or []),
        )


class VectorSearchEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._search_count = 0

    def search(
        self,
        query_text: str,
        top_k: int = 10,
        filters: Optional[Dict[str, str]] = None,
    ) -> VectorSearchResponse:
        """Semantic search by query text. Never raises."""
        try:
            return self._do_search(str(query_text), int(top_k), dict(filters or {}))
        except Exception as exc:
            return VectorSearchResponse(
                ok=False,
                query_text=str(query_text),
                errors=[f"search failed: {exc}"],
            )

    def _do_search(
        self,
        query_text: str,
        top_k: int,
        filters: Dict[str, str],
    ) -> VectorSearchResponse:
        t0 = time.perf_counter()
        store = get_asset_vector_store()

        if store.size() == 0:
            return VectorSearchResponse(
                ok=True,
                query_text=query_text,
                results=[],
                total=0,
                duration_ms=0.0,
                errors=["Vector store is empty. Run catalog indexing first."],
            )

        ev = get_intent_embedding_engine().embed_query(query_text)
        if not ev.vector:
            return VectorSearchResponse(
                ok=False,
                query_text=query_text,
                errors=["Failed to build query embedding."],
            )

        raw_results = store.query(ev.vector, top_k=max(top_k * 2, 20))

        # Apply filters if any
        if filters:
            from src.runtime.assets.semantic import get_asset_catalog
            catalog = get_asset_catalog()
            filtered = []
            for r in raw_results:
                entry = catalog.get_asset(r.asset_id)
                if entry and self._passes_filter(entry, filters):
                    filtered.append(r)
            raw_results = filtered[:top_k]
        else:
            raw_results = raw_results[:top_k]

        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        with self._lock:
            self._search_count += 1

        get_retrieval_statistics().record(
            query=query_text,
            environment=filters.get("environment", ""),
            role=filters.get("role", ""),
            top_asset=raw_results[0].asset_id if raw_results else "",
            score=raw_results[0].score if raw_results else 0.0,
            result_count=len(raw_results),
            duration_ms=duration_ms,
        )

        return VectorSearchResponse(
            ok=True,
            query_text=query_text,
            results=[r.to_dict() for r in raw_results],
            total=len(raw_results),
            duration_ms=duration_ms,
            provider=ev.provider,
        )

    @staticmethod
    def _passes_filter(entry: Any, filters: Dict[str, str]) -> bool:
        """Check if a catalog entry passes the given filters."""
        try:
            if "environment" in filters and filters["environment"]:
                if filters["environment"] not in (entry.environments or []):
                    return False
            if "role" in filters and filters["role"]:
                if filters["role"] not in (entry.roles or []):
                    return False
            if "category" in filters and filters["category"]:
                if entry.category.lower() != filters["category"].lower():
                    return False
            if "provider" in filters and filters["provider"]:
                if entry.provider.lower() != filters["provider"].lower():
                    return False
            return True
        except Exception:
            return True

    # ------------------------------------------------------------------
    # Convenience search methods
    # ------------------------------------------------------------------

    def search_environment(self, environment: str, top_k: int = 10) -> VectorSearchResponse:
        """Search for assets suitable for a specific environment."""
        text = environment.replace("_", " ")
        return self.search(text, top_k=top_k, filters={"environment": environment})

    def search_role(self, role: str, top_k: int = 10) -> VectorSearchResponse:
        """Search for assets with a specific production role."""
        text = role.replace("_", " ")
        return self.search(text, top_k=top_k, filters={"role": role})

    def search_storytelling(self, story_role: str, top_k: int = 10) -> VectorSearchResponse:
        """Search for assets with a specific storytelling role."""
        ev = get_intent_embedding_engine().embed_environment_request(
            environment="", context=story_role.replace("_", " ")
        )
        if not ev.vector:
            return VectorSearchResponse(ok=False, query_text=story_role,
                                        errors=["embedding failed"])
        raw = get_asset_vector_store().query(ev.vector, top_k=top_k)
        return VectorSearchResponse(
            ok=True,
            query_text=story_role,
            results=[r.to_dict() for r in raw],
            total=len(raw),
            provider=ev.provider,
        )

    def search_cinematic(self, cinematic_usage: str, top_k: int = 10) -> VectorSearchResponse:
        """Search for assets with a specific cinematic usage."""
        return self.search(cinematic_usage.replace("_", " "), top_k=top_k)

    def search_top_k(self, query_text: str, k: int = 5) -> List[str]:
        """Return top-k asset IDs for a query. Never raises."""
        try:
            result = self.search(query_text, top_k=k)
            return [r["asset_id"] for r in result.results if r.get("asset_id")]
        except Exception:
            return []

    def index_asset(self, asset_dict: Dict[str, Any]) -> bool:
        """Build and store embedding for a single asset. Never raises."""
        try:
            embedded = get_asset_embedding_builder().build_embedding(asset_dict)
            if not embedded.vector:
                return False
            return get_asset_vector_store().add_vector(embedded.asset_id, embedded.vector)
        except Exception:
            return False

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "search_count": self._search_count,
                "store_size":   get_asset_vector_store().size(),
            }


_INSTANCE: Optional[VectorSearchEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_vector_search_engine() -> VectorSearchEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = VectorSearchEngine()
    return _INSTANCE


def reset_vector_search_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
