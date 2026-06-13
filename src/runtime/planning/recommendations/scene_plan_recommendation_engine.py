"""
Scene Plan Recommendation Engine (Tier 7 — Scene Planning Runtime)
===================================================================
Enriches a ScenePlan with recommendations from Tier 5 knowledge sources.

Priority order (same as Tier 6 IntentRecommendationEngine):
  1. ProductionMemory   (confidence 0.95)
  2. PatternLibrary     (confidence 0.80)
  3. AssetKnowledgeGraph(confidence 0.65)
  4. Built-in defaults  (confidence 0.50)

Recommendations are typed dicts attached to ScenePlan.recommendations.

DESIGN RULES:
  - No bridge calls. No LLM calls.
  - All Tier 5 source failures are caught silently.
  - Deterministic: same plan + empty memory → same default recommendations.
  - Deduplicates by (type, value) pair.

Public API:
    PlanRecommendation             — typed recommendation dict shape
    ScenePlanRecommendationEngine
        .get_recommendations(plan, max_per_source=5) -> List[dict]   [async]
        .get_recommendations_sync(plan, max_per_source=5) -> List[dict]
    get_scene_plan_recommendation_engine() -> ScenePlanRecommendationEngine
    reset_scene_plan_recommendation_engine_for_tests()
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Built-in defaults per environment
# ---------------------------------------------------------------------------

_DEFAULT_RECS: Dict[str, List[Dict[str, Any]]] = {
    "industrial": [
        {"type": "lighting",    "value": "practical_industrial", "reason": "Default lighting for industrial environments"},
        {"type": "camera",      "value": "cinematic_push_in",    "reason": "Default camera for industrial environments"},
        {"type": "atmosphere",  "value": "industrial_fog",       "reason": "Default atmosphere for industrial environments"},
    ],
    "urban": [
        {"type": "lighting",    "value": "practical",            "reason": "Default lighting for urban environments"},
        {"type": "camera",      "value": "orbital_reveal",       "reason": "Default camera for urban environments"},
        {"type": "atmosphere",  "value": "industrial_fog",       "reason": "Default atmosphere for urban environments"},
    ],
    "space": [
        {"type": "lighting",    "value": "natural",              "reason": "Default lighting for space environments"},
        {"type": "camera",      "value": "orbital_reveal",       "reason": "Default camera for space environments"},
        {"type": "atmosphere",  "value": "volumetric_scifi",     "reason": "Default atmosphere for space environments"},
    ],
    "interior": [
        {"type": "lighting",    "value": "three_point",          "reason": "Default lighting for interior environments"},
        {"type": "camera",      "value": "cinematic_push_in",    "reason": "Default camera for interior environments"},
        {"type": "atmosphere",  "value": "cold_atmosphere",      "reason": "Default atmosphere for interior environments"},
    ],
    "desert": [
        {"type": "lighting",    "value": "hdri",                 "reason": "Default lighting for desert environments"},
        {"type": "camera",      "value": "hero_focus",           "reason": "Default camera for desert environments"},
        {"type": "atmosphere",  "value": "dusty_hangar",         "reason": "Default atmosphere for desert environments"},
    ],
    "forest": [
        {"type": "lighting",    "value": "natural",              "reason": "Default lighting for forest environments"},
        {"type": "camera",      "value": "atmospheric_tracking", "reason": "Default camera for forest environments"},
        {"type": "atmosphere",  "value": "cinematic_depth_fog",  "reason": "Default atmosphere for forest environments"},
    ],
}


def _get_default_recommendations(environment: Optional[str]) -> List[Dict[str, Any]]:
    env_key = (environment or "").lower().split("_")[0]
    defaults = _DEFAULT_RECS.get(env_key) or _DEFAULT_RECS.get("interior", [])
    return [
        {**d, "confidence": 0.50, "source": "default"}
        for d in defaults
    ]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ScenePlanRecommendationEngine:
    """Multi-source planning recommendation engine."""

    async def get_recommendations(
        self,
        plan: Any,
        max_per_source: int = 5,
    ) -> List[Dict[str, Any]]:
        """Return ranked, deduplicated recommendations for *plan*.

        Args:
            plan:            A :class:`ScenePlan`.
            max_per_source:  Max recommendations from each Tier 5 source.

        Returns:
            List of recommendation dicts sorted by confidence desc.
        """
        env = getattr(plan, "environment", None)
        recs: List[Dict[str, Any]] = []

        # Priority 1: ProductionMemory (0.95)
        try:
            from src.runtime.production_memory import get_production_memory
            mem = get_production_memory()
            scenes = mem.get_scene_history(scene_type=env, status="success",
                                           limit=max_per_source * 3)
            added = 0
            for scene in scenes:
                if added >= max_per_source:
                    break
                score = scene.get("score", 0.0)
                st    = scene.get("scene_type", env or "")
                for field_key, rec_type in (
                    ("lighting_style",  "lighting"),
                    ("camera_style",    "camera"),
                    ("atmosphere_type", "atmosphere"),
                ):
                    if scene.get(field_key) and added < max_per_source:
                        recs.append({
                            "type":       rec_type,
                            "value":      scene[field_key],
                            "confidence": 0.95,
                            "source":     "memory",
                            "reason":     f"Used in successful {st!r} scene (score={score:.2f})",
                        })
                        added += 1
        except Exception:
            pass

        # Priority 2: PatternLibrary (0.80)
        try:
            from src.runtime.pattern_library import get_pattern_library
            lib = get_pattern_library()
            patterns = lib.search_patterns(scene_type=env, pattern_type="scene_pattern")
            for p in patterns[:max_per_source]:
                pid = p.get("pattern_id", "")
                if pid:
                    recs.append({
                        "type":       "template",
                        "value":      pid,
                        "confidence": 0.80,
                        "source":     "pattern",
                        "reason":     f"Pattern {pid!r} matches {env or 'this'} environment",
                    })
        except Exception:
            pass

        # Priority 3: AssetKnowledgeGraph (0.65)
        try:
            from src.runtime.asset_knowledge_graph import get_asset_knowledge_graph
            graph = get_asset_knowledge_graph()
            assets = graph.find_scene_assets(env or "")
            for asset_id in assets[:max_per_source]:
                recs.append({
                    "type":       "asset",
                    "value":      asset_id,
                    "confidence": 0.65,
                    "source":     "graph",
                    "reason":     f"Asset {asset_id!r} is commonly used in {env or 'this'} environment",
                })
        except Exception:
            pass

        # Priority 4: Built-in defaults (0.50)
        recs.extend(_get_default_recommendations(env))

        # Sort + deduplicate by (type, value)
        seen: set = set()
        final: List[Dict[str, Any]] = []
        for r in sorted(recs, key=lambda x: x.get("confidence", 0), reverse=True):
            key = (r.get("type", ""), r.get("value", ""))
            if key not in seen and r.get("value"):
                seen.add(key)
                final.append(r)

        return final

    def get_recommendations_sync(
        self,
        plan: Any,
        max_per_source: int = 5,
    ) -> List[Dict[str, Any]]:
        """Synchronous wrapper for Houdini node execute() methods."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(asyncio.run,
                                      self.get_recommendations(plan, max_per_source))
                    return fut.result(timeout=30)
            return loop.run_until_complete(
                self.get_recommendations(plan, max_per_source)
            )
        except Exception:
            return _get_default_recommendations(getattr(plan, "environment", None))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[ScenePlanRecommendationEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_scene_plan_recommendation_engine() -> ScenePlanRecommendationEngine:
    """Return the module-level singleton."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = ScenePlanRecommendationEngine()
    return _INSTANCE


def reset_scene_plan_recommendation_engine_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
