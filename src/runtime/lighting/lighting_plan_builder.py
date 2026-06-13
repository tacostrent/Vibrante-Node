"""
Lighting Plan Builder (Tier 15)
=================================
Builds renderer-agnostic lighting plans from strategies and recommendations.
Never creates Houdini nodes — produces plan dicts only.
Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .lighting_strategy_engine import LightingStrategy, get_lighting_strategy_engine
from .lighting_color_engine import ColorStrategy, get_lighting_color_engine
from .lighting_exposure_engine import ExposureStrategy, get_lighting_exposure_engine
from .lighting_hierarchy_engine import FocusHierarchy, get_lighting_hierarchy_engine
from .lighting_knowledge import get_lighting_knowledge

_INTENSITY_BY_ROLE: Dict[str, float] = {
    "key":        0.90,
    "fill":       0.25,
    "rim":        0.55,
    "bounce":     0.15,
    "practical":  0.40,
    "motivated":  0.60,
    "atmospheric": 0.20,
    "volumetric": 0.30,
}

_SOFTNESS_BY_ROLE: Dict[str, float] = {
    "key":        0.3,
    "fill":       0.8,
    "rim":        0.2,
    "bounce":     0.9,
    "practical":  0.5,
    "motivated":  0.7,
    "atmospheric": 1.0,
    "volumetric": 0.9,
}


@dataclass
class LightSpec:
    role: str = ""
    name: str = ""
    concept: str = ""
    intensity: float = 0.5
    color_temperature_k: int = 5000
    color_rgb: List[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    angle: str = ""
    softness: float = 0.5
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role":               str(self.role),
            "name":               str(self.name),
            "concept":            str(self.concept),
            "intensity":          float(self.intensity),
            "color_temperature_k": int(self.color_temperature_k),
            "color_rgb":          list(self.color_rgb),
            "angle":              str(self.angle),
            "softness":           float(self.softness),
            "notes":              str(self.notes),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LightSpec":
        d = d if isinstance(d, dict) else {}
        return cls(
            role=str(d.get("role", "")),
            name=str(d.get("name", "")),
            concept=str(d.get("concept", "")),
            intensity=float(d.get("intensity") or 0.5),
            color_temperature_k=int(d.get("color_temperature_k") or 5000),
            color_rgb=list(d.get("color_rgb") or [1.0, 1.0, 1.0]),
            angle=str(d.get("angle", "")),
            softness=float(d.get("softness") or 0.5),
            notes=str(d.get("notes", "")),
        )


@dataclass
class LightPlan:
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    intent: str = ""
    environment: str = ""
    mood: str = ""
    key_light: Optional[LightSpec] = None
    fill_light: Optional[LightSpec] = None
    rim_light: Optional[LightSpec] = None
    practicals: List[LightSpec] = field(default_factory=list)
    volumetrics: Dict[str, Any] = field(default_factory=dict)
    color_strategy: Dict[str, Any] = field(default_factory=dict)
    exposure: Dict[str, Any] = field(default_factory=dict)
    hierarchy_notes: Dict[str, Any] = field(default_factory=dict)
    strategy_notes: List[str] = field(default_factory=list)
    built_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":         str(self.plan_id),
            "intent":          str(self.intent),
            "environment":     str(self.environment),
            "mood":            str(self.mood),
            "key_light":       self.key_light.to_dict() if self.key_light else {},
            "fill_light":      self.fill_light.to_dict() if self.fill_light else {},
            "rim_light":       self.rim_light.to_dict() if self.rim_light else {},
            "practicals":      [p.to_dict() for p in self.practicals],
            "volumetrics":     dict(self.volumetrics),
            "color_strategy":  dict(self.color_strategy),
            "exposure":        dict(self.exposure),
            "hierarchy_notes": dict(self.hierarchy_notes),
            "strategy_notes":  list(self.strategy_notes),
            "built_at":        float(self.built_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LightPlan":
        d = d if isinstance(d, dict) else {}
        return cls(
            plan_id=str(d.get("plan_id") or f"plan_{uuid.uuid4().hex[:8]}"),
            intent=str(d.get("intent", "")),
            environment=str(d.get("environment", "")),
            mood=str(d.get("mood", "")),
            key_light=LightSpec.from_dict(d["key_light"]) if d.get("key_light") else None,
            fill_light=LightSpec.from_dict(d["fill_light"]) if d.get("fill_light") else None,
            rim_light=LightSpec.from_dict(d["rim_light"]) if d.get("rim_light") else None,
            practicals=[LightSpec.from_dict(p) for p in (d.get("practicals") or [])],
            volumetrics=dict(d.get("volumetrics") or {}),
            color_strategy=dict(d.get("color_strategy") or {}),
            exposure=dict(d.get("exposure") or {}),
            hierarchy_notes=dict(d.get("hierarchy_notes") or {}),
            strategy_notes=list(d.get("strategy_notes") or []),
            built_at=float(d.get("built_at") or time.time()),
        )


def _build_light_spec(concept_name: str, role: str, color_strategy: ColorStrategy) -> LightSpec:
    """Build a LightSpec from a concept name and color strategy."""
    concept = get_lighting_knowledge().lookup_concept(concept_name)
    intensity = _INTENSITY_BY_ROLE.get(role, 0.5)
    softness = _SOFTNESS_BY_ROLE.get(role, 0.5)

    # Determine color from strategy
    temp_k = color_strategy.temperature_k
    if role == "key":
        rgb = list(color_strategy.primary_color[:3]) if len(color_strategy.primary_color) >= 3 else [1.0, 1.0, 1.0]
    elif role in ("rim", "practical"):
        rgb = list(color_strategy.accent_color[:3]) if len(color_strategy.accent_color) >= 3 else [1.0, 1.0, 1.0]
    else:
        rgb = [1.0, 1.0, 1.0]

    angle = ""
    if concept:
        intensity = float(
            concept.properties.get("intensity_range", [intensity])[0]
            if isinstance(concept.properties.get("intensity_range"), list)
            else intensity
        )
        if role == "key":
            angle = str(concept.properties.get("typical_angle", "45_high"))

    notes = concept.description if concept else f"No concept data found for '{concept_name}'."

    return LightSpec(
        role=role,
        name=f"{role}_{concept_name}",
        concept=concept_name,
        intensity=round(intensity, 3),
        color_temperature_k=temp_k,
        color_rgb=rgb,
        angle=angle,
        softness=round(softness, 3),
        notes=notes,
    )


class LightingPlanBuilder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._build_count = 0

    def build_plan(
        self,
        intent_text: str = "",
        environment: str = "",
        mood: str = "",
        subjects: Optional[List[Any]] = None,
    ) -> LightPlan:
        """Build a complete renderer-agnostic lighting plan."""
        try:
            return self._do_build(
                str(intent_text or ""),
                str(environment or ""),
                str(mood or ""),
                subjects if isinstance(subjects, list) else [],
            )
        except Exception as exc:
            return LightPlan(
                intent=str(intent_text or ""),
                strategy_notes=[f"build_plan error: {exc}"],
            )

    def _do_build(
        self,
        intent_text: str,
        environment: str,
        mood: str,
        subjects: List[Any],
    ) -> LightPlan:
        # Generate strategy
        strategy = get_lighting_strategy_engine().generate_strategy(
            intent_text=intent_text,
            environment=environment,
            mood=mood,
        )

        # Color and exposure
        color_strategy = get_lighting_color_engine().recommend_palette(
            mood=strategy.mood, environment=strategy.environment
        )
        exposure_strategy = get_lighting_exposure_engine().recommend_exposure(mood=strategy.mood)

        # Build light specs
        key_light  = _build_light_spec(strategy.key_concept or "key_light",  "key",  color_strategy)
        fill_light = _build_light_spec(strategy.fill_concept or "fill_light", "fill", color_strategy)
        rim_light  = _build_light_spec(strategy.rim_concept or "rim_light",  "rim",  color_strategy)

        # Build hierarchy
        hierarchy = get_lighting_hierarchy_engine().build_focus_hierarchy(subjects)
        hierarchy_notes = {
            "hero":       [e.subject for e in hierarchy.hero],
            "support":    [e.subject for e in hierarchy.support],
            "background": [e.subject for e in hierarchy.background],
            "atmosphere": [e.subject for e in hierarchy.atmosphere],
        }

        # Practicals
        practicals: List[LightSpec] = []
        if strategy.volumetrics:
            practicals.append(LightSpec(
                role="practical",
                name="volumetric_source",
                concept="volumetric_light",
                intensity=0.30,
                color_temperature_k=color_strategy.temperature_k,
                color_rgb=list(color_strategy.primary_color[:3]),
                softness=0.9,
                notes="Volumetric atmosphere source.",
            ))

        # Volumetrics settings
        volumetrics: Dict[str, Any] = {}
        if strategy.volumetrics:
            volumetrics = {
                "enabled":   True,
                "density":   0.05,
                "color_rgb": list(color_strategy.primary_color[:3]),
                "notes":     "Light scattering enabled for atmospheric depth.",
            }

        with self._lock:
            self._build_count += 1

        return LightPlan(
            intent=intent_text,
            environment=strategy.environment,
            mood=strategy.mood,
            key_light=key_light,
            fill_light=fill_light,
            rim_light=rim_light,
            practicals=practicals,
            volumetrics=volumetrics,
            color_strategy=color_strategy.to_dict(),
            exposure=exposure_strategy.to_dict(),
            hierarchy_notes=hierarchy_notes,
            strategy_notes=list(strategy.notes),
        )

    def build_from_strategy(self, strategy: LightingStrategy, subjects: Optional[List[Any]] = None) -> LightPlan:
        """Build a LightPlan directly from an existing LightingStrategy."""
        try:
            return self._do_build(
                intent_text=strategy.intent_text,
                environment=strategy.environment,
                mood=strategy.mood,
                subjects=subjects if isinstance(subjects, list) else [],
            )
        except Exception as exc:
            return LightPlan(
                intent=strategy.intent_text,
                strategy_notes=[f"build_from_strategy error: {exc}"],
            )

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"build_calls": self._build_count}


_INSTANCE: Optional[LightingPlanBuilder] = None
_INSTANCE_LOCK = threading.Lock()


def get_lighting_plan_builder() -> LightingPlanBuilder:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LightingPlanBuilder()
    return _INSTANCE


def reset_lighting_plan_builder_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
