"""
Intent Recommendation Engine (Tier 6 — Semantic Scene Intent Runtime)
======================================================================
Generates structured, explainable recommendations for a SceneIntent by
querying three existing Tier 5 knowledge sources in priority order:

  Priority 1 — ProductionMemory   (confidence 0.95): proven historical configurations
  Priority 2 — PatternLibrary     (confidence 0.80): ranked reusable production patterns
  Priority 3 — AssetKnowledgeGraph(confidence 0.65): commonly used asset relationships
  Priority 4 — Built-in defaults  (confidence 0.50): environment-based hardcoded fallbacks

DESIGN RULES:
  - No bridge calls. No LLM calls. Pure read from Tier 5 singletons.
  - All failures from Tier 5 lookups are caught and silently ignored.
  - Deterministic: same SceneIntent → same default recommendations.
  - Deduplicates by (recommendation_type, value).

Public API:
    IntentRecommendation       — single typed recommendation
    RecommendationResult       — full result from get_recommendations()
    IntentRecommendationEngine
        .get_recommendations(intent, max_per_source=5) -> RecommendationResult   [async]
        .get_recommendations_sync(intent, max_per_source=5) -> RecommendationResult
    get_intent_recommendation_engine() -> IntentRecommendationEngine   (singleton)
    reset_intent_recommendation_engine_for_tests()
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.semantic.schema.scene_intent_schema import SceneIntent

# ---------------------------------------------------------------------------
# IntentRecommendation
# ---------------------------------------------------------------------------

@dataclass
class IntentRecommendation:
    """A single typed recommendation for a SceneIntent.

    Attributes:
        recommendation_type:  "lighting" | "camera" | "atmosphere" |
                              "asset" | "template" | "environment"
        value:                The recommended value or ID.
        confidence:           0.0–1.0. Higher = more certain.
        source:               "memory" | "pattern" | "graph" | "default"
        reason:               Human-readable explanation.
        metadata:             Optional extra data (score, pattern_id, etc.).
    """

    recommendation_type: str = ""
    value:               str = ""
    confidence:          float = 0.0
    source:              str = ""
    reason:              str = ""
    metadata:            Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_type": self.recommendation_type,
            "value":               self.value,
            "confidence":          self.confidence,
            "source":              self.source,
            "reason":              self.reason,
            "metadata":            dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "IntentRecommendation":
        return cls(
            recommendation_type=d.get("recommendation_type", ""),
            value=d.get("value", ""),
            confidence=float(d.get("confidence", 0.0)),
            source=d.get("source", ""),
            reason=d.get("reason", ""),
            metadata=dict(d.get("metadata") or {}),
        )


# ---------------------------------------------------------------------------
# RecommendationResult
# ---------------------------------------------------------------------------

@dataclass
class RecommendationResult:
    """Full output of IntentRecommendationEngine.get_recommendations().

    Attributes:
        recommendations:     All recommendations, sorted by confidence desc.
        source_counts:       Number of recommendations per source.
        environment:         The environment from the input SceneIntent.
        generated_at:        Unix timestamp.
    """

    recommendations: List[IntentRecommendation] = field(default_factory=list)
    source_counts:   Dict[str, int]             = field(default_factory=dict)
    environment:     Optional[str]              = None
    generated_at:    float                      = field(default_factory=time.time)

    @property
    def top_recommendation(self) -> Optional[IntentRecommendation]:
        """Highest-confidence recommendation, or None if empty."""
        return self.recommendations[0] if self.recommendations else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendations": [r.to_dict() for r in self.recommendations],
            "source_counts":   dict(self.source_counts),
            "environment":     self.environment,
            "generated_at":    self.generated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RecommendationResult":
        return cls(
            recommendations=[IntentRecommendation.from_dict(r)
                             for r in (d.get("recommendations") or [])],
            source_counts=dict(d.get("source_counts") or {}),
            environment=d.get("environment"),
            generated_at=float(d.get("generated_at", time.time())),
        )


# ---------------------------------------------------------------------------
# Built-in defaults per environment (Priority 4 — confidence 0.50)
# ---------------------------------------------------------------------------

_DEFAULT_RECS: Dict[str, Dict[str, str]] = {
    "industrial": {
        "lighting":    "practical_industrial",
        "camera":      "cinematic_push_in",
        "atmosphere":  "industrial_fog",
        "template":    "cinematic_industrial_hangar",
    },
    "urban": {
        "lighting":    "practical",
        "camera":      "orbital_reveal",
        "atmosphere":  "industrial_fog",
        "template":    "urban_exterior",
    },
    "space": {
        "lighting":    "natural",
        "camera":      "orbital_reveal",
        "atmosphere":  "volumetric_scifi",
        "template":    "atmospheric_scifi_corridor",
    },
    "interior": {
        "lighting":    "three_point",
        "camera":      "cinematic_push_in",
        "atmosphere":  "cold_atmosphere",
        "template":    "cinematic_control_room",
    },
    "desert": {
        "lighting":    "hdri",
        "camera":      "hero_focus",
        "atmosphere":  "dusty_hangar",
        "template":    "",
    },
    "forest": {
        "lighting":    "natural",
        "camera":      "atmospheric_tracking",
        "atmosphere":  "cinematic_depth_fog",
        "template":    "",
    },
    "underground": {
        "lighting":    "practical",
        "camera":      "atmospheric_tracking",
        "atmosphere":  "industrial_fog",
        "template":    "",
    },
    "arctic": {
        "lighting":    "overcast_diffuse",
        "camera":      "orbital_reveal",
        "atmosphere":  "cold_atmosphere",
        "template":    "",
    },
    "mountain": {
        "lighting":    "natural",
        "camera":      "orbital_reveal",
        "atmosphere":  "cinematic_depth_fog",
        "template":    "",
    },
    "ocean": {
        "lighting":    "hdri",
        "camera":      "orbital_reveal",
        "atmosphere":  "cinematic_depth_fog",
        "template":    "",
    },
    "abstract": {
        "lighting":    "three_point",
        "camera":      "hero_focus",
        "atmosphere":  "volumetric_scifi",
        "template":    "",
    },
}


def _get_default_recommendations(environment: Optional[str]) -> List[IntentRecommendation]:
    """Return hardcoded default recommendations for the given environment."""
    env_key = (environment or "").lower().split("_")[0]
    defaults = _DEFAULT_RECS.get(env_key) or _DEFAULT_RECS.get("interior", {})
    recs: List[IntentRecommendation] = []
    type_map = {
        "lighting":   "lighting",
        "camera":     "camera",
        "atmosphere": "atmosphere",
        "template":   "template",
    }
    for field_key, rec_type in type_map.items():
        value = defaults.get(field_key, "")
        if value:
            recs.append(IntentRecommendation(
                recommendation_type=rec_type,
                value=value,
                confidence=0.50,
                source="default",
                reason=f"Default {rec_type} for {env_key or 'unknown'} environment",
            ))
    return recs


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class IntentRecommendationEngine:
    """Multi-source recommendation engine for SceneIntent.

    Queries ProductionMemory, PatternLibrary, AssetKnowledgeGraph, then falls
    back to built-in defaults.  All source failures are caught silently so the
    engine always returns at least the default recommendations.

    Usage::

        engine = get_intent_recommendation_engine()
        result = await engine.get_recommendations(intent)
        # or synchronously:
        result = engine.get_recommendations_sync(intent)
    """

    async def get_recommendations(
        self,
        intent: SceneIntent,
        max_per_source: int = 5,
    ) -> RecommendationResult:
        """Return ranked, deduplicated recommendations for *intent*.

        Args:
            intent:          The SceneIntent to generate recommendations for.
            max_per_source:  Maximum recommendations per Tier 5 source.

        Returns:
            :class:`RecommendationResult` with all recommendations sorted by
            confidence descending.
        """
        recs: List[IntentRecommendation] = []
        env = intent.environment

        # --- Priority 1: ProductionMemory (confidence 0.95) ---
        try:
            from src.runtime.production_memory import get_production_memory
            mem = get_production_memory()
            scenes = mem.get_scene_history(
                scene_type=env, status="success", limit=max_per_source * 3
            )
            added = 0
            for scene in scenes:
                if added >= max_per_source:
                    break
                score = scene.get("score", 0.0)
                scene_type = scene.get("scene_type", env or "")
                if scene.get("lighting_style"):
                    recs.append(IntentRecommendation(
                        recommendation_type="lighting",
                        value=scene["lighting_style"],
                        confidence=0.95,
                        source="memory",
                        reason=(
                            f"Used successfully in {scene_type!r} scene "
                            f"(score: {score:.2f})"
                        ),
                        metadata={"scene_score": score},
                    ))
                    added += 1
                if scene.get("camera_style") and added < max_per_source:
                    recs.append(IntentRecommendation(
                        recommendation_type="camera",
                        value=scene["camera_style"],
                        confidence=0.95,
                        source="memory",
                        reason=f"Proven camera style for {scene_type!r} environment",
                        metadata={"scene_score": score},
                    ))
                    added += 1
                if scene.get("atmosphere_type") and added < max_per_source:
                    recs.append(IntentRecommendation(
                        recommendation_type="atmosphere",
                        value=scene["atmosphere_type"],
                        confidence=0.95,
                        source="memory",
                        reason=f"Proven atmosphere for {scene_type!r} environment",
                        metadata={"scene_score": score},
                    ))
                    added += 1
        except Exception:
            pass

        # --- Priority 2: PatternLibrary (confidence 0.80) ---
        try:
            from src.runtime.pattern_library import get_pattern_library
            lib = get_pattern_library()
            patterns = lib.search_patterns(scene_type=env, pattern_type="scene_pattern")
            for p in patterns[:max_per_source]:
                pid = p.get("pattern_id", "")
                if pid:
                    recs.append(IntentRecommendation(
                        recommendation_type="template",
                        value=pid,
                        confidence=0.80,
                        source="pattern",
                        reason=(
                            f"Pattern {pid!r} matches {env or 'this'} environment "
                            f"(score: {p.get('score', 0.5):.2f})"
                        ),
                        metadata={"score": p.get("score", 0.5)},
                    ))
        except Exception:
            pass

        # --- Priority 3: AssetKnowledgeGraph (confidence 0.65) ---
        try:
            from src.runtime.asset_knowledge_graph import get_asset_knowledge_graph
            graph = get_asset_knowledge_graph()
            assets = graph.find_scene_assets(env or "")
            for asset_id in assets[:max_per_source]:
                recs.append(IntentRecommendation(
                    recommendation_type="asset",
                    value=asset_id,
                    confidence=0.65,
                    source="graph",
                    reason=(
                        f"Asset {asset_id!r} is commonly used in "
                        f"{env or 'this'} environment"
                    ),
                ))
        except Exception:
            pass

        # --- Priority 4: Built-in defaults (confidence 0.50) ---
        recs.extend(_get_default_recommendations(env))

        # --- Sort + deduplicate ---
        seen: set = set()
        final: List[IntentRecommendation] = []
        for r in sorted(recs, key=lambda x: x.confidence, reverse=True):
            key = (r.recommendation_type, r.value)
            if key not in seen and r.value:
                seen.add(key)
                final.append(r)

        # --- Build source_counts ---
        counts: Dict[str, int] = {}
        for r in final:
            counts[r.source] = counts.get(r.source, 0) + 1

        return RecommendationResult(
            recommendations=final,
            source_counts=counts,
            environment=env,
            generated_at=time.time(),
        )

    def get_recommendations_sync(
        self,
        intent: SceneIntent,
        max_per_source: int = 5,
    ) -> RecommendationResult:
        """Synchronous wrapper around :meth:`get_recommendations`.

        Safe to call from Houdini node ``execute()`` methods (which run on the
        asyncio event loop via ``AsyncRuntime``).  Falls back to defaults if the
        coroutine cannot be driven.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We are already inside an event loop (AsyncRuntime) — run in a
                # thread pool to avoid blocking the loop.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(
                        asyncio.run,
                        self.get_recommendations(intent, max_per_source),
                    )
                    return fut.result(timeout=30)
            return loop.run_until_complete(
                self.get_recommendations(intent, max_per_source)
            )
        except Exception:
            return RecommendationResult(
                recommendations=_get_default_recommendations(intent.environment),
                source_counts={"default": len(_get_default_recommendations(intent.environment))},
                environment=intent.environment,
            )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[IntentRecommendationEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_intent_recommendation_engine() -> IntentRecommendationEngine:
    """Return the module-level singleton IntentRecommendationEngine."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = IntentRecommendationEngine()
    return _INSTANCE


def reset_intent_recommendation_engine_for_tests() -> None:
    """Replace the singleton with a fresh instance. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
