"""
Asset Ranking Engine (Tier 8 — Asset Intelligence Runtime)
===========================================================
Scores and ranks AssetDescriptors using six deterministic factors.

Score factors and weights:
    intent_match   (0.25) — category + tag overlap with SceneIntent
    plan_match     (0.20) — zone + priority alignment with ScenePlan
    pattern_match  (0.20) — PatternLibrary success history for the env
    graph_match    (0.15) — AssetKnowledgeGraph relationship score
    history_score  (0.15) — ProductionMemory successful scene count
    provider_score (0.05) — normalised provider rating + popularity

All boosts are named and recorded in AssetRecommendation.score_breakdown
so every decision is fully explainable.

DESIGN RULES:
  - No bridge calls.  No LLM calls.  Deterministic weights.
  - Tier 5 integrations (Memory, PatternLibrary, KnowledgeGraph) wrapped
    in try/except — ranking degrades gracefully if any source is missing.
  - Same input always produces the same ranking.
  - Never raises — errors captured in RankingResult.errors.

Public API:
    RankingResult
    AssetRankingEngine
    get_asset_ranking_engine()
    reset_asset_ranking_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import AssetDescriptor, AssetRecommendation

# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

_WEIGHTS: Dict[str, float] = {
    "intent_match":   0.25,
    "plan_match":     0.20,
    "pattern_match":  0.20,
    "graph_match":    0.15,
    "history_score":  0.15,
    "provider_score": 0.05,
}


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class RankingResult:
    """Result of one AssetRankingEngine.rank() call."""

    ok:              bool                      = True
    recommendations: List[AssetRecommendation] = field(default_factory=list)
    ranked_count:    int                       = 0
    ranking_time:    float                     = 0.0
    errors:          List[str]                 = field(default_factory=list)
    warnings:        List[str]                 = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":              self.ok,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "ranked_count":    self.ranked_count,
            "ranking_time":    self.ranking_time,
            "errors":          list(self.errors),
            "warnings":        list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetRankingEngine:
    """
    Ranks validated AssetDescriptors against a SceneIntent + ScenePlan.

    Integrates with Tier 5 knowledge systems (ProductionMemory,
    PatternLibrary, AssetKnowledgeGraph) for boosted scoring.
    """

    def rank(
        self,
        assets: List[AssetDescriptor],
        intent: Optional[Any] = None,
        plan: Optional[Any] = None,
        zone: str = "",
        category: str = "",
        top_k: int = 10,
    ) -> RankingResult:
        """
        Score and rank assets.

        Args:
            assets:    AssetDescriptors to rank (should be pre-validated).
            intent:    SceneIntent object or dict (optional).
            plan:      ScenePlan object or dict (optional).
            zone:      Target zone name.
            category:  Target asset category.
            top_k:     Maximum number of recommendations to return.

        Returns:
            :class:`RankingResult`.  Never raises.
        """
        t0 = time.perf_counter()
        result = RankingResult()
        try:
            context = _build_context(intent, plan, zone, category)
            memory_counts  = self._fetch_memory_counts(context)
            pattern_scores = self._fetch_pattern_scores(context)
            graph_scores   = self._fetch_graph_scores(assets)

            scored = []
            for asset in assets:
                breakdown, score = self._score_asset(
                    asset, context, memory_counts, pattern_scores, graph_scores
                )
                source = _determine_source(breakdown, memory_counts, pattern_scores, graph_scores, asset)
                confidence = _determine_confidence(score, source)
                scored.append((score, asset, breakdown, source, confidence))

            # Sort descending by score, then by name for determinism
            scored.sort(key=lambda x: (-x[0], x[1].name))

            recommendations = []
            for rank_idx, (score, asset, breakdown, source, confidence) in enumerate(scored[:top_k], 1):
                boost_reasons = _build_boost_reasons(breakdown)
                rec = AssetRecommendation(
                    asset=asset,
                    score=round(score, 4),
                    rank=rank_idx,
                    zone=zone,
                    category=category or asset.category,
                    score_breakdown=breakdown,
                    boost_reasons=boost_reasons,
                    source=source,
                    confidence=confidence,
                    notes=[f"Ranked {rank_idx}/{min(len(scored), top_k)} for {category!r} in {zone!r}"],
                )
                recommendations.append(rec)

            result.recommendations = recommendations
            result.ranked_count = len(recommendations)
            result.ok = True

        except Exception as exc:
            result.ok = False
            result.errors.append(f"Ranking failed: {exc}")

        result.ranking_time = time.perf_counter() - t0
        return result

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_asset(
        self,
        asset: AssetDescriptor,
        context: Dict[str, Any],
        memory_counts: Dict[str, int],
        pattern_scores: Dict[str, float],
        graph_scores: Dict[str, float],
    ) -> tuple:
        breakdown: Dict[str, float] = {}

        # 1. Intent match — category + tag overlap
        breakdown["intent_match"] = self._intent_match(asset, context)
        # 2. Plan match — zone + priority alignment
        breakdown["plan_match"] = self._plan_match(asset, context)
        # 3. Pattern match
        env = context.get("environment", "")
        breakdown["pattern_match"] = pattern_scores.get(env, 0.0)
        # 4. Knowledge graph match
        breakdown["graph_match"] = graph_scores.get(asset.asset_id, 0.0)
        # 5. History score
        count = memory_counts.get(asset.asset_id, 0)
        breakdown["history_score"] = min(1.0, count / 5.0)
        # 6. Provider score (normalised rating + popularity)
        breakdown["provider_score"] = self._provider_score(asset)

        total = sum(_WEIGHTS[k] * v for k, v in breakdown.items())
        return breakdown, total

    def _intent_match(self, asset: AssetDescriptor, context: Dict[str, Any]) -> float:
        score = 0.0
        # Category match
        target_cats = set(context.get("categories", []))
        if not target_cats or asset.category in target_cats:
            score += 0.5
        # Tag overlap
        intent_tags = set(context.get("tags", []))
        if intent_tags:
            overlap = len(asset.tag_set & intent_tags)
            score += min(0.5, overlap * 0.1)
        return min(1.0, score)

    def _plan_match(self, asset: AssetDescriptor, context: Dict[str, Any]) -> float:
        zone = context.get("zone", "")
        priority = context.get("priority", "recommended")
        score = 0.5  # base
        # Environment suitability
        env = context.get("environment", "")
        if env and env in asset.environment_suitability:
            score += 0.3
        # Style match
        intent_style = context.get("style", "")
        if intent_style and intent_style != "unknown":
            if asset.style == intent_style or asset.style == "unknown":
                score += 0.2
        return min(1.0, score)

    def _provider_score(self, asset: AssetDescriptor) -> float:
        rating_norm = asset.rating / 5.0
        pop_norm = min(1.0, asset.popularity / 50000.0)
        return round(rating_norm * 0.6 + pop_norm * 0.4, 4)

    # ------------------------------------------------------------------
    # Tier 5 integrations (graceful degradation)
    # ------------------------------------------------------------------

    def _fetch_memory_counts(self, context: Dict[str, Any]) -> Dict[str, int]:
        try:
            from src.runtime.production_memory import get_production_memory
            mem = get_production_memory()
            env = context.get("environment", "")
            records = mem.get_successful_patterns(scene_type=env) if env else []
            counts: Dict[str, int] = {}
            for rec in records:
                aid = rec.get("asset_id", "")
                if aid:
                    counts[aid] = counts.get(aid, 0) + 1
            return counts
        except Exception:
            return {}

    def _fetch_pattern_scores(self, context: Dict[str, Any]) -> Dict[str, float]:
        try:
            from src.runtime.pattern_library import get_pattern_library
            lib = get_pattern_library()
            env = context.get("environment", "")
            results = lib.search_patterns(scene_type=env, pattern_type="scene_pattern") if env else []
            scores: Dict[str, float] = {}
            for p in results:
                eid = p.get("id", "")
                if eid:
                    scores[eid] = min(1.0, p.get("score", 0.5))
            return scores
        except Exception:
            return {}

    def _fetch_graph_scores(self, assets: List[AssetDescriptor]) -> Dict[str, float]:
        try:
            from src.runtime.asset_knowledge_graph import get_asset_knowledge_graph
            graph = get_asset_knowledge_graph()
            scores: Dict[str, float] = {}
            for asset in assets:
                related = graph.find_related_assets(
                    asset.asset_id, rel_type="commonly_used_with"
                )
                # Score based on number of successful pairings
                scores[asset.asset_id] = min(1.0, len(related) * 0.15)
            return scores
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_context(intent: Any, plan: Any, zone: str, category: str) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {"zone": zone, "categories": {category} if category else set()}
    if intent is not None:
        if hasattr(intent, "environment"):
            ctx["environment"] = intent.environment or ""
            ctx["style"] = intent.style or ""
            ctx["mood"] = intent.mood or ""
            ctx["tags"] = set(getattr(intent, "keywords", []))
            if category:
                ctx["categories"] = {category}
        elif isinstance(intent, dict):
            ctx["environment"] = intent.get("environment", "")
            ctx["style"] = intent.get("style", "")
            ctx["mood"] = intent.get("mood", "")
            ctx["tags"] = set(intent.get("keywords", []))
    if plan is not None:
        # Extract priority for the target zone from plan.zones
        zones = getattr(plan, "zones", None) or (plan.get("zones", []) if isinstance(plan, dict) else [])
        for z in zones:
            z_type = getattr(z, "zone_type", None) or (z.get("zone_type", "") if isinstance(z, dict) else "")
            if z_type == zone:
                priority = getattr(z, "priority", None) or (z.get("priority", 5) if isinstance(z, dict) else 5)
                ctx["priority"] = "required" if int(priority) >= 8 else "recommended"
                break
    return ctx


def _determine_source(
    breakdown: Dict[str, float],
    memory_counts: Dict[str, int],
    pattern_scores: Dict[str, float],
    graph_scores: Dict[str, float],
    asset: AssetDescriptor,
) -> str:
    if breakdown.get("history_score", 0) > 0.5:
        return "memory"
    if breakdown.get("pattern_match", 0) > 0.5:
        return "pattern"
    if breakdown.get("graph_match", 0) > 0.3:
        return "graph"
    return "provider"


def _determine_confidence(score: float, source: str) -> float:
    base = {"memory": 0.95, "pattern": 0.80, "graph": 0.65, "provider": 0.50}
    return round(min(1.0, base.get(source, 0.50) * score + 0.1), 3)


def _build_boost_reasons(breakdown: Dict[str, float]) -> List[str]:
    reasons = []
    if breakdown.get("history_score", 0) > 0.3:
        reasons.append(f"Used in successful scenes (history={breakdown['history_score']:.2f})")
    if breakdown.get("pattern_match", 0) > 0.3:
        reasons.append(f"Matches successful environment pattern (pattern={breakdown['pattern_match']:.2f})")
    if breakdown.get("graph_match", 0) > 0.2:
        reasons.append(f"Commonly paired with other assets in scene (graph={breakdown['graph_match']:.2f})")
    if breakdown.get("intent_match", 0) > 0.6:
        reasons.append(f"Strong intent match (intent={breakdown['intent_match']:.2f})")
    return reasons


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetRankingEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_ranking_engine() -> AssetRankingEngine:
    """Return the module-level singleton AssetRankingEngine."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetRankingEngine()
    return _INSTANCE


def reset_asset_ranking_engine_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
