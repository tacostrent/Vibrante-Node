"""
Hybrid Ranking Engine (Tier 12.8)
====================================
Combines multiple ranking signals into a production-aware final score.

Weights:
  vector_similarity   = 0.40
  environment_fit     = 0.20
  storytelling_match  = 0.15
  lookdev_match       = 0.10
  knowledge_graph     = 0.10
  production_memory   = 0.05

Design rules:
  - No DCC calls, no network calls
  - Deterministic — same inputs always produce same ranking
  - Never raises in public methods
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .semantic_similarity import normalize_scores

_WEIGHTS: Dict[str, float] = {
    "vector_similarity":  0.40,
    "environment_fit":    0.20,
    "storytelling_match": 0.15,
    "lookdev_match":      0.10,
    "knowledge_graph":    0.10,
    "production_memory":  0.05,
}

assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


@dataclass
class RankedAsset:
    asset_id:        str = ""
    total_score:     float = 0.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    rank:            int = 0
    asset_dict:      Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":        str(self.asset_id),
            "total_score":     round(float(self.total_score), 6),
            "score_breakdown": {k: round(float(v), 6) for k, v in self.score_breakdown.items()},
            "rank":            int(self.rank),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RankedAsset":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            total_score=float(d.get("total_score", 0.0)),
            score_breakdown=dict(d.get("score_breakdown") or {}),
            rank=int(d.get("rank", 0)),
        )


class HybridRankingEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rank_count = 0

    def rank_assets(
        self,
        candidates: List[Dict[str, Any]],
        query_context: Dict[str, Any],
        vector_scores: Optional[Dict[str, float]] = None,
    ) -> List[RankedAsset]:
        """
        Rank candidate assets using hybrid scoring.

        Args:
            candidates:    List of asset dicts (from catalog) to rank.
            query_context: ParsedIntent.to_dict() or search context with
                           environment, role, storytelling, lookdev, cinematic.
            vector_scores: Optional mapping of asset_id → vector similarity score.

        Returns: Sorted list of RankedAsset, best first.
        Never raises.
        """
        try:
            return self._do_rank(
                [a for a in candidates if isinstance(a, dict)],
                dict(query_context) if isinstance(query_context, dict) else {},
                dict(vector_scores) if vector_scores else {},
            )
        except Exception:
            return []

    def _do_rank(
        self,
        candidates: List[Dict[str, Any]],
        ctx: Dict[str, Any],
        vs: Dict[str, float],
    ) -> List[RankedAsset]:
        if not candidates:
            return []

        # Normalize vector scores to [0, 1]
        ids = [a.get("asset_id", "") for a in candidates]
        raw_vs = [vs.get(aid, 0.0) for aid in ids]
        norm_vs = normalize_scores(raw_vs)
        vs_norm = {aid: s for aid, s in zip(ids, norm_vs)}

        ranked: List[RankedAsset] = []
        for asset in candidates:
            aid = str(asset.get("asset_id", ""))
            breakdown = self.calculate_score(asset, ctx, vs_norm.get(aid, 0.0))
            total = sum(breakdown[k] * _WEIGHTS[k] for k in _WEIGHTS if k in breakdown)
            ranked.append(RankedAsset(
                asset_id=aid,
                total_score=round(total, 6),
                score_breakdown=breakdown,
                asset_dict=dict(asset),
            ))

        with self._lock:
            self._rank_count += 1

        return self.sort_results(ranked)

    def calculate_score(
        self,
        candidate: Dict[str, Any],
        ctx: Dict[str, Any],
        vector_score: float,
    ) -> Dict[str, float]:
        """Compute each scoring dimension for a candidate against query context."""
        return {
            "vector_similarity":  float(vector_score),
            "environment_fit":    self._env_score(candidate, ctx),
            "storytelling_match": self._story_score(candidate, ctx),
            "lookdev_match":      self._lookdev_score(candidate, ctx),
            "knowledge_graph":    self._graph_score(candidate, ctx),
            "production_memory":  self._memory_score(candidate, ctx),
        }

    @staticmethod
    def _env_score(asset: Dict[str, Any], ctx: Dict[str, Any]) -> float:
        """Environment fit: 1.0 if primary_env matches, 0.5 if any env matches, 0.0 otherwise."""
        req_env = str(ctx.get("environment", "")).strip()
        if not req_env:
            return 0.5
        primary = str(asset.get("primary_env", "")).strip()
        if primary == req_env:
            return 1.0
        if req_env in (asset.get("environments") or []):
            return 0.6
        return 0.0

    @staticmethod
    def _story_score(asset: Dict[str, Any], ctx: Dict[str, Any]) -> float:
        """Storytelling match: exact or partial role match."""
        req = str(ctx.get("storytelling", "") or ctx.get("story_role", "")).strip()
        if not req:
            return 0.5
        asset_story = str(asset.get("storytelling", "") or asset.get("story_role", "")).strip()
        if asset_story == req:
            return 1.0
        # Partial: hero_object → hero match
        if req.split("_")[0] in asset_story:
            return 0.5
        return 0.0

    @staticmethod
    def _lookdev_score(asset: Dict[str, Any], ctx: Dict[str, Any]) -> float:
        """Lookdev match: tag presence score."""
        req = str(ctx.get("lookdev", "")).strip()
        if not req:
            return 0.5
        lookdev = asset.get("lookdev") or asset.get("lookdev_tags") or []
        if req in lookdev:
            return 1.0
        primary = str(asset.get("primary_lookdev", "")).strip()
        if primary == req:
            return 0.9
        return 0.0

    @staticmethod
    def _graph_score(asset: Dict[str, Any], ctx: Dict[str, Any]) -> float:
        """Knowledge graph score: neighbors of query context assets."""
        try:
            ref_ids = ctx.get("reference_asset_ids") or []
            if not ref_ids:
                return 0.5
            from src.runtime.assets.semantic import get_asset_knowledge_graph
            graph = get_asset_knowledge_graph()
            aid = str(asset.get("asset_id", ""))
            for ref_id in ref_ids:
                neighbors = graph.get_neighbors(ref_id)
                if aid in neighbors:
                    return 1.0
            return 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _memory_score(asset: Dict[str, Any], ctx: Dict[str, Any]) -> float:
        """Production memory score: use importance as proxy."""
        importance = str(asset.get("importance", "ambient"))
        _importance_scores = {"primary": 1.0, "secondary": 0.7, "tertiary": 0.4, "ambient": 0.2}
        return _importance_scores.get(importance, 0.2)

    @staticmethod
    def sort_results(ranked: List[RankedAsset]) -> List[RankedAsset]:
        """Sort by total_score descending, assign sequential ranks."""
        sorted_list = sorted(ranked, key=lambda r: r.total_score, reverse=True)
        for i, r in enumerate(sorted_list):
            r.rank = i + 1
        return sorted_list

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"rank_count": self._rank_count, "weights": dict(_WEIGHTS)}


_INSTANCE: Optional[HybridRankingEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_hybrid_ranking_engine() -> HybridRankingEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = HybridRankingEngine()
    return _INSTANCE


def reset_hybrid_ranking_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
