"""
Lighting Recommendation Engine (Tier 15)
==========================================
Recommends production-proven lighting setups from patterns, mood, and environment.
Integrates pattern library and production memory.
Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .lighting_patterns import get_lighting_patterns
from .lighting_strategy_engine import get_lighting_strategy_engine
from .lighting_mood_engine import get_lighting_mood_engine
from .lighting_environment_mapper import get_lighting_environment_mapper


@dataclass
class LightingRecommendation:
    recommendation_id: str = field(default_factory=lambda: f"lr_{uuid.uuid4().hex[:8]}")
    pattern_id: str = ""
    pattern_name: str = ""
    confidence: float = 0.0
    rationale: str = ""
    key_concept: str = ""
    fill_concept: str = ""
    rim_concept: str = ""
    volumetrics: bool = False
    adjustments: List[str] = field(default_factory=list)
    recommended_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": str(self.recommendation_id),
            "pattern_id":        str(self.pattern_id),
            "pattern_name":      str(self.pattern_name),
            "confidence":        float(self.confidence),
            "rationale":         str(self.rationale),
            "key_concept":       str(self.key_concept),
            "fill_concept":      str(self.fill_concept),
            "rim_concept":       str(self.rim_concept),
            "volumetrics":       bool(self.volumetrics),
            "adjustments":       list(self.adjustments),
            "recommended_at":    float(self.recommended_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LightingRecommendation":
        d = d if isinstance(d, dict) else {}
        return cls(
            recommendation_id=str(d.get("recommendation_id") or f"lr_{uuid.uuid4().hex[:8]}"),
            pattern_id=str(d.get("pattern_id", "")),
            pattern_name=str(d.get("pattern_name", "")),
            confidence=float(d.get("confidence") or 0.0),
            rationale=str(d.get("rationale", "")),
            key_concept=str(d.get("key_concept", "")),
            fill_concept=str(d.get("fill_concept", "")),
            rim_concept=str(d.get("rim_concept", "")),
            volumetrics=bool(d.get("volumetrics", False)),
            adjustments=list(d.get("adjustments") or []),
            recommended_at=float(d.get("recommended_at") or time.time()),
        )


class LightingRecommendationEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recommend_count = 0

    def recommend_setup(
        self,
        intent_text: str = "",
        environment: str = "",
        mood: str = "",
    ) -> LightingRecommendation:
        """Recommend a complete lighting setup from intent, environment, and mood."""
        try:
            return self._do_recommend(
                str(intent_text or ""),
                str(environment or ""),
                str(mood or ""),
            )
        except Exception as exc:
            return LightingRecommendation(
                rationale=f"recommend_setup error: {exc}",
                confidence=0.0,
            )

    def _do_recommend(self, intent_text: str, environment: str, mood: str) -> LightingRecommendation:
        # Try mood inference if not provided
        if not mood and intent_text:
            mood = get_lighting_mood_engine().infer_mood(intent_text)

        # Try environment mapping
        env_mapping = get_lighting_environment_mapper().map_environment(environment)
        if not mood and env_mapping.mood_hints:
            mood = env_mapping.mood_hints[0]

        # Rank patterns
        scene_dict = {"intent": intent_text, "environment": environment, "mood": mood}
        ranked = get_lighting_patterns().rank_patterns(scene_dict)

        if ranked:
            best = ranked[0]
            # Confidence based on specificity of match
            confidence = 0.85 if best.environment == environment else 0.65
            if best.mood == mood:
                confidence = min(1.0, confidence + 0.1)

            rationale_parts = [f"Pattern '{best.name}' selected"]
            if best.environment:
                rationale_parts.append(f"for '{best.environment}' environment")
            if best.mood:
                rationale_parts.append(f"in '{best.mood}' mood")
            rationale = " ".join(rationale_parts) + "."

            adjustments: List[str] = []
            if best.notes:
                adjustments.append(best.notes)
            env_notes = env_mapping.notes
            if env_notes:
                adjustments.append(env_notes)

            with self._lock:
                self._recommend_count += 1

            return LightingRecommendation(
                pattern_id=best.pattern_id,
                pattern_name=best.name,
                confidence=round(confidence, 3),
                rationale=rationale,
                key_concept=best.key_concept,
                fill_concept=best.fill_concept,
                rim_concept=best.rim_concept,
                volumetrics=best.volumetrics,
                adjustments=adjustments,
            )

        # Fallback: derive from strategy engine
        strategy = get_lighting_strategy_engine().generate_strategy(
            intent_text=intent_text, environment=environment, mood=mood
        )
        with self._lock:
            self._recommend_count += 1
        return LightingRecommendation(
            pattern_name="derived_from_strategy",
            confidence=0.50,
            rationale=f"No matching pattern — derived from strategy engine ({strategy.approach}).",
            key_concept=strategy.key_concept,
            fill_concept=strategy.fill_concept,
            rim_concept=strategy.rim_concept,
            volumetrics=strategy.volumetrics,
            adjustments=list(strategy.notes),
        )

    def recommend_pattern(self, environment: str = "", mood: str = "") -> Optional[Dict[str, Any]]:
        """Return the best matching pattern dict for the given environment and mood."""
        try:
            pattern = get_lighting_patterns().recommend_pattern(environment=environment, mood=mood)
            if pattern:
                return pattern.to_dict()
            return None
        except Exception:
            return None

    def recommend_adjustments(self, recommendation: LightingRecommendation) -> List[str]:
        """Return actionable adjustment notes for the recommendation."""
        try:
            adjustments = list(recommendation.adjustments)
            if recommendation.confidence < 0.6:
                adjustments.append(
                    f"Low confidence ({recommendation.confidence:.2f}) — verify pattern suitability manually."
                )
            if not recommendation.key_concept:
                adjustments.append("Define a key concept before building the lighting plan.")
            return adjustments
        except Exception:
            return []

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"recommend_calls": self._recommend_count}


_INSTANCE: Optional[LightingRecommendationEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_recommendation_engine() -> LightingRecommendationEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingRecommendationEngine()
    return _INSTANCE


def reset_lighting_recommendation_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
