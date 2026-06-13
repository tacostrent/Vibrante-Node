"""
Asset Recommendation Engine (Tier 8 — Asset Intelligence Runtime)
==================================================================
Full pipeline orchestrator: Discovery → Validation → Ranking →
Recommendations.

Priority chain for boosted confidence:
    Memory     0.95  (asset in successful production scenes)
    Patterns   0.80  (asset matches successful env patterns)
    Graph      0.65  (asset has strong graph relationships)
    Provider   0.50  (base ranking from provider quality)

Input:  SceneIntent + ScenePlan + optional zone/category filters
Output: AssetRecommendationResult — ranked, deduplicated, explainable

DESIGN RULES:
  - Orchestrates Discovery, Validation, Ranking — no new logic.
  - Deduplicates recommendations by (provider, asset_id) across queries.
  - All pipeline steps wrapped in try/except for graceful degradation.
  - Never raises — errors captured in result.errors.

Public API:
    AssetRecommendationResult
    AssetRecommendationEngine
    get_asset_recommendation_engine()
    reset_asset_recommendation_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import AssetDescriptor, AssetRecommendation
from src.runtime.assets.discovery import get_asset_discovery_engine
from src.runtime.assets.validation import get_asset_validation_engine
from src.runtime.assets.ranking import get_asset_ranking_engine


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class AssetRecommendationResult:
    """
    Final output of the Tier 8 asset intelligence pipeline.

    Contains the top-ranked recommendations for each query zone/category,
    plus full pipeline diagnostics.
    """

    ok:                  bool                      = True
    recommendations:     List[AssetRecommendation] = field(default_factory=list)
    by_zone:             Dict[str, List[AssetRecommendation]] = field(default_factory=dict)
    by_category:         Dict[str, List[AssetRecommendation]] = field(default_factory=dict)
    total_discovered:    int                        = 0
    total_validated:     int                        = 0
    total_ranked:        int                        = 0
    total_rejected:      int                        = 0
    pipeline_time:       float                      = 0.0
    pipeline_stages:     List[str]                  = field(default_factory=list)
    errors:              List[str]                  = field(default_factory=list)
    warnings:            List[str]                  = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":               self.ok,
            "recommendations":  [r.to_dict() for r in self.recommendations],
            "by_zone":          {z: [r.to_dict() for r in recs] for z, recs in self.by_zone.items()},
            "by_category":      {c: [r.to_dict() for r in recs] for c, recs in self.by_category.items()},
            "total_discovered": self.total_discovered,
            "total_validated":  self.total_validated,
            "total_ranked":     self.total_ranked,
            "total_rejected":   self.total_rejected,
            "pipeline_time":    self.pipeline_time,
            "pipeline_stages":  list(self.pipeline_stages),
            "errors":           list(self.errors),
            "warnings":         list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetRecommendationEngine:
    """
    Orchestrates the full Asset Intelligence pipeline.

    Each call to recommend() runs:
      1. Discovery  — query all providers
      2. Validation — filter incompatible assets
      3. Ranking    — score with intent/plan/memory/pattern/graph
      4. Dedup      — remove duplicate assets across queries
      5. Sort       — final ordered recommendation set
    """

    def recommend(
        self,
        queries: List[Dict[str, Any]],
        intent: Optional[Any] = None,
        plan: Optional[Any] = None,
        renderer: str = "",
        scene_scale: str = "",
        top_k_per_query: int = 5,
        limit_per_provider: int = 20,
    ) -> AssetRecommendationResult:
        """
        Run the full recommendation pipeline.

        Args:
            queries:             AssetQuery dicts (from ScenePlan.asset_queries).
            intent:              SceneIntent object or dict for intent matching.
            plan:                ScenePlan object or dict for zone alignment.
            renderer:            Target renderer for format compatibility checks.
            scene_scale:         Overall scene scale for scale validation.
            top_k_per_query:     Max recommendations per (zone, category) group.
            limit_per_provider:  Max raw results per provider.

        Returns:
            :class:`AssetRecommendationResult`.  Never raises.
        """
        t0 = time.perf_counter()
        result = AssetRecommendationResult()

        try:
            # ---- Phase 1: Discovery ----------------------------------------
            try:
                discovery = get_asset_discovery_engine().discover(
                    queries, limit_per_provider=limit_per_provider
                )
                result.total_discovered = discovery.total_assets
                result.pipeline_stages.append("discovery")
                result.warnings.extend(discovery.warnings)
                result.errors.extend(discovery.errors)
            except Exception as exc:
                result.errors.append(f"Discovery phase failed: {exc}")
                result.ok = False
                result.pipeline_time = time.perf_counter() - t0
                return result

            # ---- Phase 2: Validation + Ranking per query --------------------
            seen_asset_keys: set = set()
            all_recommendations: List[AssetRecommendation] = []

            for qr in discovery.query_results:
                zone     = qr.zone
                category = qr.category

                # Validation
                try:
                    validation = get_asset_validation_engine().validate(
                        qr.assets,
                        zone=zone,
                        renderer=renderer,
                        scene_scale=scene_scale,
                    )
                    valid_assets = validation.valid_assets
                    result.total_validated += len(valid_assets)
                    result.total_rejected  += validation.rejected_count
                    result.pipeline_stages.append(f"validation:{category}")
                except Exception as exc:
                    result.warnings.append(f"Validation failed for {category!r}: {exc}")
                    valid_assets = qr.assets  # fall through without validation

                # Ranking
                try:
                    ranking = get_asset_ranking_engine().rank(
                        valid_assets,
                        intent=intent,
                        plan=plan,
                        zone=zone,
                        category=category,
                        top_k=top_k_per_query,
                    )
                    result.total_ranked += ranking.ranked_count
                    result.pipeline_stages.append(f"ranking:{category}")
                    result.warnings.extend(ranking.warnings)
                    # Dedup across queries
                    for rec in ranking.recommendations:
                        if rec.asset:
                            key = (rec.asset.provider, rec.asset.asset_id)
                            if key not in seen_asset_keys:
                                seen_asset_keys.add(key)
                                all_recommendations.append(rec)
                except Exception as exc:
                    result.warnings.append(f"Ranking failed for {category!r}: {exc}")

            # ---- Phase 3: Final sort and grouping --------------------------
            all_recommendations.sort(key=lambda r: (-r.score, r.rank, r.zone))
            result.recommendations = all_recommendations

            # Group by zone and category
            for rec in all_recommendations:
                z = rec.zone or "unknown"
                c = rec.category or "unknown"
                result.by_zone.setdefault(z, []).append(rec)
                result.by_category.setdefault(c, []).append(rec)

            result.pipeline_stages.append("complete")
            result.ok = True

        except Exception as exc:
            result.ok = False
            result.errors.append(f"Recommendation pipeline failed: {exc}")

        result.pipeline_time = time.perf_counter() - t0
        return result

    def recommend_from_plan(
        self,
        plan: Any,
        intent: Optional[Any] = None,
        renderer: str = "",
        scene_scale: str = "",
        top_k_per_query: int = 5,
    ) -> AssetRecommendationResult:
        """Convenience wrapper that extracts queries from a ScenePlan."""
        if hasattr(plan, "asset_queries"):
            queries = [q.to_dict() for q in plan.asset_queries]
        elif isinstance(plan, dict):
            queries = [
                q if isinstance(q, dict) else q.to_dict()
                for q in plan.get("asset_queries", [])
            ]
        else:
            queries = []
        return self.recommend(
            queries, intent=intent, plan=plan,
            renderer=renderer, scene_scale=scene_scale,
            top_k_per_query=top_k_per_query,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetRecommendationEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_recommendation_engine() -> AssetRecommendationEngine:
    """Return the module-level singleton AssetRecommendationEngine."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetRecommendationEngine()
    return _INSTANCE


def reset_asset_recommendation_engine_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
