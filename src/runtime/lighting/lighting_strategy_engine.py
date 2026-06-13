"""
Lighting Strategy Engine (Tier 15)
=====================================
Generates holistic lighting strategies from environment, mood, lookdev, and story intent.
Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .lighting_environment_mapper import get_lighting_environment_mapper
from .lighting_mood_engine import get_lighting_mood_engine
from .lighting_color_engine import get_lighting_color_engine
from .lighting_exposure_engine import get_lighting_exposure_engine
from .lighting_patterns import get_lighting_patterns


@dataclass
class LightingStrategy:
    strategy_id: str = field(default_factory=lambda: f"ls_{uuid.uuid4().hex[:8]}")
    intent_text: str = ""
    environment: str = ""
    mood: str = ""
    approach: str = ""
    key_concept: str = ""
    fill_concept: str = ""
    rim_concept: str = ""
    volumetrics: bool = False
    color_temperature: str = "neutral"
    color_temperature_k: int = 5000
    contrast: str = "medium"
    ev_target: float = 0.0
    recommended_sources: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id":        str(self.strategy_id),
            "intent_text":        str(self.intent_text),
            "environment":        str(self.environment),
            "mood":               str(self.mood),
            "approach":           str(self.approach),
            "key_concept":        str(self.key_concept),
            "fill_concept":       str(self.fill_concept),
            "rim_concept":        str(self.rim_concept),
            "volumetrics":        bool(self.volumetrics),
            "color_temperature":  str(self.color_temperature),
            "color_temperature_k": int(self.color_temperature_k),
            "contrast":           str(self.contrast),
            "ev_target":          float(self.ev_target),
            "recommended_sources": list(self.recommended_sources),
            "notes":              list(self.notes),
            "generated_at":       float(self.generated_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LightingStrategy":
        d = d if isinstance(d, dict) else {}
        return cls(
            strategy_id=str(d.get("strategy_id") or f"ls_{uuid.uuid4().hex[:8]}"),
            intent_text=str(d.get("intent_text", "")),
            environment=str(d.get("environment", "")),
            mood=str(d.get("mood", "")),
            approach=str(d.get("approach", "")),
            key_concept=str(d.get("key_concept", "")),
            fill_concept=str(d.get("fill_concept", "")),
            rim_concept=str(d.get("rim_concept", "")),
            volumetrics=bool(d.get("volumetrics", False)),
            color_temperature=str(d.get("color_temperature", "neutral")),
            color_temperature_k=int(d.get("color_temperature_k") or 5000),
            contrast=str(d.get("contrast", "medium")),
            ev_target=float(d.get("ev_target") or 0.0),
            recommended_sources=list(d.get("recommended_sources") or []),
            notes=list(d.get("notes") or []),
            generated_at=float(d.get("generated_at") or time.time()),
        )


def _describe_approach(mood: str, contrast: str, volumetrics: bool) -> str:
    parts = []
    if mood:
        parts.append(mood.replace("_", " ").title())
    if contrast == "high":
        parts.append("high-contrast")
    elif contrast == "low":
        parts.append("soft low-contrast")
    if volumetrics:
        parts.append("with volumetric atmosphere")
    return " ".join(parts) if parts else "balanced three-point"


class LightingStrategyEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._generate_count = 0

    def generate_strategy(
        self,
        intent_text: str = "",
        environment: str = "",
        mood: str = "",
        lookdev_dict: Optional[Dict[str, Any]] = None,
    ) -> LightingStrategy:
        """Generate a complete LightingStrategy from intent, environment, and mood."""
        try:
            return self._do_generate(
                str(intent_text or ""),
                str(environment or ""),
                str(mood or ""),
                lookdev_dict if isinstance(lookdev_dict, dict) else {},
            )
        except Exception as exc:
            return LightingStrategy(
                intent_text=str(intent_text or ""),
                notes=[f"generate_strategy error: {exc}"],
            )

    def _do_generate(
        self,
        intent_text: str,
        environment: str,
        mood: str,
        lookdev_dict: Dict[str, Any],
    ) -> LightingStrategy:
        # Resolve mood from intent if not provided
        if not mood and intent_text:
            mood = get_lighting_mood_engine().infer_mood(intent_text)

        # Get environment mapping
        env_mapping = get_lighting_environment_mapper().map_environment(environment)
        if not mood and env_mapping.mood_hints:
            mood = env_mapping.mood_hints[0]

        # Get mood profile
        mood_profile = get_lighting_mood_engine().build_mood_profile(mood)

        # Get color strategy
        color_strategy = get_lighting_color_engine().recommend_palette(mood=mood, environment=environment)

        # Get exposure strategy
        exposure_strategy = get_lighting_exposure_engine().recommend_exposure(mood=mood)

        # Try to match a lighting pattern
        pattern = get_lighting_patterns().recommend_pattern(environment=environment, mood=mood)

        # Determine concepts from pattern or environment mapping
        key_concept  = pattern.key_concept  if pattern else (env_mapping.recommended_sources[0] if env_mapping.recommended_sources else "key_light")
        fill_concept = pattern.fill_concept if pattern else (env_mapping.recommended_sources[1] if len(env_mapping.recommended_sources) > 1 else "fill_light")
        rim_concept  = pattern.rim_concept  if pattern else (env_mapping.recommended_sources[2] if len(env_mapping.recommended_sources) > 2 else "rim_light")
        volumetrics  = pattern.volumetrics  if pattern else env_mapping.volumetrics

        approach = _describe_approach(mood, mood_profile.contrast, volumetrics)

        notes: List[str] = []
        if env_mapping.notes:
            notes.append(env_mapping.notes)
        if pattern and pattern.notes:
            notes.append(pattern.notes)
        if mood_profile.color_notes:
            notes.append(mood_profile.color_notes)
        if exposure_strategy.tone_mapping_notes:
            notes.append(exposure_strategy.tone_mapping_notes)

        with self._lock:
            self._generate_count += 1

        return LightingStrategy(
            intent_text=intent_text,
            environment=environment or env_mapping.environment,
            mood=mood,
            approach=approach,
            key_concept=key_concept,
            fill_concept=fill_concept,
            rim_concept=rim_concept,
            volumetrics=volumetrics,
            color_temperature=color_strategy.temperature,
            color_temperature_k=color_strategy.temperature_k,
            contrast=mood_profile.contrast,
            ev_target=exposure_strategy.ev_target,
            recommended_sources=list(env_mapping.recommended_sources),
            notes=notes,
        )

    def evaluate_strategy(self, strategy: LightingStrategy) -> Dict[str, Any]:
        """Evaluate a LightingStrategy for completeness and coherence."""
        try:
            findings: List[str] = []
            warnings: List[str] = []
            score = 1.0

            if not strategy.key_concept:
                findings.append("No key concept — strategy is incomplete.")
                score -= 0.3
            if not strategy.mood:
                warnings.append("No mood specified — strategy may lack emotional direction.")
                score -= 0.1
            if not strategy.environment:
                warnings.append("No environment specified — using generic defaults.")
                score -= 0.05
            if not strategy.recommended_sources:
                warnings.append("No recommended lighting sources.")
                score -= 0.1

            return {
                "score":    round(max(0.0, score), 3),
                "complete": len(findings) == 0,
                "findings": findings,
                "warnings": warnings,
            }
        except Exception as exc:
            return {"score": 0.0, "complete": False, "findings": [str(exc)], "warnings": []}

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"generate_calls": self._generate_count}


_INSTANCE: Optional[LightingStrategyEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_strategy_engine() -> LightingStrategyEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingStrategyEngine()
    return _INSTANCE


def reset_lighting_strategy_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
