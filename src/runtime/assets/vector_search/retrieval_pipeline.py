"""
Retrieval Pipeline (Tier 12.8)
================================
Full semantic retrieval: Intent → Embedding → Vector Search → Hybrid Ranking → Assets.

Methods:
  retrieve()                    — main entry point for any intent text
  retrieve_environment_assets() — assets for a specific environment + role
  retrieve_hero_assets()        — hero-importance assets
  retrieve_storytelling_assets()— assets by storytelling role

Design rules:
  - No DCC calls, no network calls
  - Falls back gracefully when vector store is empty (uses catalog search)
  - Never raises in public methods
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .intent_parser import get_intent_parser, ParsedIntent
from .intent_embedding_engine import get_intent_embedding_engine
from .vector_search_engine import get_vector_search_engine
from .hybrid_ranking_engine import get_hybrid_ranking_engine, RankedAsset
from .retrieval_statistics import get_retrieval_statistics


@dataclass
class RetrievalResult:
    ok:            bool = True
    intent:        str = ""
    assets:        List[Dict[str, Any]] = field(default_factory=list)
    total:         int = 0
    parsed_intent: Optional[Dict[str, Any]] = None
    strategy:      str = ""
    duration_ms:   float = 0.0
    errors:        List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":            bool(self.ok),
            "intent":        str(self.intent),
            "assets":        list(self.assets),
            "total":         int(self.total),
            "parsed_intent": self.parsed_intent,
            "strategy":      str(self.strategy),
            "duration_ms":   float(self.duration_ms),
            "errors":        list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RetrievalResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", True)),
            intent=str(d.get("intent", "")),
            assets=list(d.get("assets") or []),
            total=int(d.get("total", 0)),
            parsed_intent=d.get("parsed_intent"),
            strategy=str(d.get("strategy", "")),
            duration_ms=float(d.get("duration_ms", 0.0)),
            errors=list(d.get("errors") or []),
        )


class RetrievalPipeline:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._retrieve_count = 0

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def retrieve(
        self,
        intent_text: str,
        top_k: int = 10,
        use_vector_search: bool = True,
    ) -> RetrievalResult:
        """
        Full retrieval pipeline.

        1. Parse intent → ParsedIntent
        2. Embed intent → EmbeddingVector
        3. Vector search → top candidates
        4. Hybrid ranking → ranked candidates
        5. Enrich with catalog entries
        6. Return RetrievalResult

        Falls back to catalog-only search if vector store is empty.
        Never raises.
        """
        try:
            return self._do_retrieve(
                str(intent_text).strip(),
                int(top_k),
                bool(use_vector_search),
            )
        except Exception as exc:
            return RetrievalResult(
                ok=False,
                intent=str(intent_text),
                errors=[f"retrieve failed: {exc}"],
            )

    def _do_retrieve(
        self,
        intent_text: str,
        top_k: int,
        use_vector: bool,
    ) -> RetrievalResult:
        t0 = time.perf_counter()

        parsed = get_intent_parser().parse(intent_text)
        ctx    = parsed.to_dict()

        store  = get_vector_search_engine()
        vector_scores: Dict[str, float] = {}
        strategy = "catalog_fallback"

        if use_vector and store.get_statistics()["store_size"] > 0:
            vs_response = store.search(intent_text, top_k=max(top_k * 3, 30))
            if vs_response.ok and vs_response.results:
                vector_scores = {r["asset_id"]: r["score"] for r in vs_response.results}
                strategy = "vector+hybrid"
        else:
            strategy = "catalog_fallback"

        # Retrieve candidates from catalog
        candidates = self._fetch_candidates(parsed, vector_scores, top_k)

        # Hybrid ranking
        ranked = get_hybrid_ranking_engine().rank_assets(
            candidates=candidates,
            query_context=ctx,
            vector_scores=vector_scores,
        )[:top_k]

        assets = [
            {**r.to_dict(), **r.asset_dict}
            for r in ranked
        ]

        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        with self._lock:
            self._retrieve_count += 1

        get_retrieval_statistics().record(
            query=intent_text,
            environment=parsed.environment,
            role=parsed.role,
            top_asset=ranked[0].asset_id if ranked else "",
            score=ranked[0].total_score if ranked else 0.0,
            result_count=len(ranked),
            duration_ms=duration_ms,
        )

        return RetrievalResult(
            ok=True,
            intent=intent_text,
            assets=assets,
            total=len(assets),
            parsed_intent=parsed.to_dict(),
            strategy=strategy,
            duration_ms=duration_ms,
        )

    def _fetch_candidates(
        self,
        parsed: ParsedIntent,
        vector_scores: Dict[str, float],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Fetch candidates from catalog. Combines vector hits + filter search."""
        from src.runtime.assets.semantic import get_asset_catalog
        catalog = get_asset_catalog()

        candidates: Dict[str, Dict[str, Any]] = {}

        # Include all vector hit assets
        for asset_id in list(vector_scores.keys()):
            entry = catalog.get_asset(asset_id)
            if entry:
                candidates[asset_id] = entry.to_dict()

        # Fill remaining slots from filter search
        if len(candidates) < top_k:
            filters = parsed.to_filter_dict()
            remaining = top_k - len(candidates)
            entries = catalog.search_assets(
                query=parsed.raw_text[:100],
                environment=filters.get("environment", ""),
                role=filters.get("role", ""),
                lookdev=filters.get("lookdev", ""),
                storytelling=filters.get("storytelling", ""),
                cinematic=filters.get("cinematic", ""),
                limit=remaining + top_k,
            )
            for entry in entries:
                if entry.asset_id not in candidates:
                    candidates[entry.asset_id] = entry.to_dict()
                    if len(candidates) >= top_k * 3:
                        break

        return list(candidates.values())

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def retrieve_environment_assets(
        self,
        environment: str,
        role: str = "",
        top_k: int = 10,
    ) -> RetrievalResult:
        """Retrieve assets for a specific environment and optional role."""
        parts = [environment.replace("_", " ")]
        if role:
            parts.append(role.replace("_", " "))
        return self.retrieve(" ".join(parts), top_k=top_k)

    def retrieve_hero_assets(
        self,
        environment: str = "",
        top_k: int = 10,
    ) -> RetrievalResult:
        """Retrieve hero-importance assets, optionally filtered by environment."""
        parts = ["hero"]
        if environment:
            parts.append(environment.replace("_", " "))
        return self.retrieve(" ".join(parts), top_k=top_k)

    def retrieve_storytelling_assets(
        self,
        story_role: str,
        environment: str = "",
        top_k: int = 10,
    ) -> RetrievalResult:
        """Retrieve assets for a specific storytelling role."""
        parts = [story_role.replace("_", " ")]
        if environment:
            parts.append(environment.replace("_", " "))
        return self.retrieve(" ".join(parts), top_k=top_k)

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "retrieve_count": self._retrieve_count,
                **get_retrieval_statistics().get_summary(),
            }


_INSTANCE: Optional[RetrievalPipeline] = None
_INSTANCE_LOCK = threading.Lock()


def get_retrieval_pipeline() -> RetrievalPipeline:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = RetrievalPipeline()
    return _INSTANCE


def reset_retrieval_pipeline_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
