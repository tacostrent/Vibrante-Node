"""
Material Recommendation Engine (Tier 14)
=========================================
Recommends production-proven materials for assets using a 3-tier priority chain:
  1. Lookdev Patterns  (confidence 0.85) — environment-proven material sets
  2. Material Knowledge (confidence 0.70) — semantic inference from asset metadata
  3. Renderer Default   (confidence 0.50) — fallback to renderer base material

Deterministic, thread-safe, no Houdini dependency, no AI.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .lookdev_patterns import get_lookdev_patterns
from .material_knowledge import get_material_knowledge
from .renderer_profiles import get_renderer_profiles, SUPPORTED_RENDERERS


@dataclass
class MaterialRecommendation:
    recommendation_id: str = field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:8]}")
    asset_id: str = ""
    material_name: str = ""
    renderer: str = "usd_preview_surface"
    confidence: float = 0.5
    source: str = "renderer_default"
    reasoning: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": str(self.recommendation_id),
            "asset_id":          str(self.asset_id),
            "material_name":     str(self.material_name),
            "renderer":          str(self.renderer),
            "confidence":        float(self.confidence),
            "source":            str(self.source),
            "reasoning":         str(self.reasoning),
            "created_at":        float(self.created_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MaterialRecommendation":
        d = d if isinstance(d, dict) else {}
        return cls(
            recommendation_id=str(d.get("recommendation_id") or f"rec_{uuid.uuid4().hex[:8]}"),
            asset_id=str(d.get("asset_id", "")),
            material_name=str(d.get("material_name", "")),
            renderer=str(d.get("renderer", "usd_preview_surface")),
            confidence=float(d.get("confidence") or 0.5),
            source=str(d.get("source", "renderer_default")),
            reasoning=str(d.get("reasoning", "")),
            created_at=float(d.get("created_at") or time.time()),
        )


@dataclass
class MaterialRecommendationResult:
    ok: bool = True
    asset_id: str = ""
    recommendations: List[MaterialRecommendation] = field(default_factory=list)
    renderer: str = "usd_preview_surface"
    strategy_used: str = "renderer_default"
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":              bool(self.ok),
            "asset_id":        str(self.asset_id),
            "recommendations": [r.to_dict() for r in self.recommendations],
            "renderer":        str(self.renderer),
            "strategy_used":   str(self.strategy_used),
            "errors":          list(self.errors),
            "warnings":        list(self.warnings),
            "created_at":      float(self.created_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MaterialRecommendationResult":
        d = d if isinstance(d, dict) else {}
        recs = [
            MaterialRecommendation.from_dict(r)
            for r in (d.get("recommendations") or [])
            if isinstance(r, dict)
        ]
        return cls(
            ok=bool(d.get("ok", True)),
            asset_id=str(d.get("asset_id", "")),
            recommendations=recs,
            renderer=str(d.get("renderer", "usd_preview_surface")),
            strategy_used=str(d.get("strategy_used", "renderer_default")),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            created_at=float(d.get("created_at") or time.time()),
        )


def _normalize_renderer(renderer: str) -> str:
    r = str(renderer or "usd_preview_surface").lower().strip()
    return r if r in SUPPORTED_RENDERERS else "usd_preview_surface"


class MaterialRecommendationEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recommend_count = 0

    def recommend_material(
        self,
        asset_dict: Dict[str, Any],
        renderer: str = "usd_preview_surface",
    ) -> MaterialRecommendationResult:
        try:
            return self._do_recommend(asset_dict, renderer)
        except Exception as exc:
            safe = asset_dict if isinstance(asset_dict, dict) else {}
            return MaterialRecommendationResult(
                ok=False,
                asset_id=str(safe.get("asset_id", "")),
                renderer=_normalize_renderer(renderer),
                errors=[f"Recommendation failed: {exc}"],
            )

    def _do_recommend(
        self,
        asset_dict: Dict[str, Any],
        renderer: str,
    ) -> MaterialRecommendationResult:
        asset_dict = asset_dict if isinstance(asset_dict, dict) else {}
        renderer = _normalize_renderer(renderer)
        asset_id = str(asset_dict.get("asset_id", ""))
        warnings: List[str] = []

        # Tier 1: Lookdev Patterns
        patterns = get_lookdev_patterns().rank_patterns(asset_dict)
        if patterns:
            top = patterns[0]
            # Estimate score: top pattern always has some score; use it if it has materials
            if top.materials:
                mat_name = top.materials[0]
                rec = MaterialRecommendation(
                    asset_id=asset_id,
                    material_name=mat_name,
                    renderer=renderer,
                    confidence=0.85,
                    source="lookdev_pattern",
                    reasoning=(
                        f"Pattern '{top.name}' matched environment '{top.environment}'. "
                        f"First material: {mat_name}."
                    ),
                )
                with self._lock:
                    self._recommend_count += 1
                return MaterialRecommendationResult(
                    ok=True,
                    asset_id=asset_id,
                    recommendations=[rec],
                    renderer=renderer,
                    strategy_used="lookdev_pattern",
                    warnings=warnings,
                )

        # Tier 2: Material Knowledge
        inference = get_material_knowledge().build_material_profile(asset_dict)
        if inference.material_type:
            rec = MaterialRecommendation(
                asset_id=asset_id,
                material_name=inference.material_type,
                renderer=renderer,
                confidence=0.70,
                source="material_knowledge",
                reasoning=(
                    f"Inferred '{inference.material_type}' from asset metadata. "
                    f"Age: {inference.surface_age}, condition: {inference.surface_condition}."
                ),
            )
            with self._lock:
                self._recommend_count += 1
            return MaterialRecommendationResult(
                ok=True,
                asset_id=asset_id,
                recommendations=[rec],
                renderer=renderer,
                strategy_used="material_knowledge",
                warnings=warnings,
            )

        # Tier 3: Renderer default
        profile = get_renderer_profiles().get_profile(renderer)
        warnings.append("No pattern or knowledge match — using renderer default material.")
        rec = MaterialRecommendation(
            asset_id=asset_id,
            material_name="industrial_metal",
            renderer=renderer,
            confidence=0.50,
            source="renderer_default",
            reasoning=f"No match found. Default renderer '{renderer}' class: {profile.material_class}.",
        )
        with self._lock:
            self._recommend_count += 1
        return MaterialRecommendationResult(
            ok=True,
            asset_id=asset_id,
            recommendations=[rec],
            renderer=renderer,
            strategy_used="renderer_default",
            warnings=warnings,
        )

    def recommend_material_set(
        self,
        asset_dict: Dict[str, Any],
        renderer: str = "usd_preview_surface",
    ) -> MaterialRecommendationResult:
        """Return multiple ranked material recommendations."""
        try:
            asset_dict = asset_dict if isinstance(asset_dict, dict) else {}
            renderer = _normalize_renderer(renderer)
            asset_id = str(asset_dict.get("asset_id", ""))
            recs: List[MaterialRecommendation] = []

            # From top-ranked pattern: all materials
            patterns = get_lookdev_patterns().rank_patterns(asset_dict)
            if patterns:
                top = patterns[0]
                for i, mat in enumerate(top.materials):
                    recs.append(MaterialRecommendation(
                        asset_id=asset_id,
                        material_name=mat,
                        renderer=renderer,
                        confidence=round(0.85 - i * 0.05, 2),
                        source="lookdev_pattern",
                        reasoning=f"Pattern '{top.name}', position {i + 1}.",
                    ))

            # From knowledge
            inference = get_material_knowledge().build_material_profile(asset_dict)
            if inference.material_type and not any(r.material_name == inference.material_type for r in recs):
                recs.append(MaterialRecommendation(
                    asset_id=asset_id,
                    material_name=inference.material_type,
                    renderer=renderer,
                    confidence=0.70,
                    source="material_knowledge",
                    reasoning=f"Semantic inference: {inference.material_type}.",
                ))

            if not recs:
                recs.append(MaterialRecommendation(
                    asset_id=asset_id,
                    material_name="industrial_metal",
                    renderer=renderer,
                    confidence=0.50,
                    source="renderer_default",
                    reasoning="No match — renderer default.",
                ))

            with self._lock:
                self._recommend_count += 1
            return MaterialRecommendationResult(
                ok=True,
                asset_id=asset_id,
                recommendations=recs,
                renderer=renderer,
                strategy_used="material_set",
            )
        except Exception as exc:
            safe = asset_dict if isinstance(asset_dict, dict) else {}
            return MaterialRecommendationResult(
                ok=False,
                asset_id=str(safe.get("asset_id", "")),
                renderer=_normalize_renderer(renderer),
                errors=[f"recommend_material_set failed: {exc}"],
            )

    def recommend_environment_materials(
        self,
        environment: str,
        renderer: str = "usd_preview_surface",
    ) -> MaterialRecommendationResult:
        """Return the material set for a named environment from its lookdev pattern."""
        try:
            renderer = _normalize_renderer(renderer)
            env_lower = str(environment or "").lower().strip()
            patterns = get_lookdev_patterns().search_patterns(environment=env_lower)
            if not patterns:
                # Try partial match
                patterns = get_lookdev_patterns().search_patterns(query=env_lower)
            if patterns:
                top = patterns[0]
                recs = [
                    MaterialRecommendation(
                        asset_id="",
                        material_name=mat,
                        renderer=renderer,
                        confidence=round(0.85 - i * 0.05, 2),
                        source="lookdev_pattern",
                        reasoning=f"Environment '{environment}' → pattern '{top.name}'.",
                    )
                    for i, mat in enumerate(top.materials)
                ]
                with self._lock:
                    self._recommend_count += 1
                return MaterialRecommendationResult(
                    ok=True,
                    asset_id="",
                    recommendations=recs,
                    renderer=renderer,
                    strategy_used="lookdev_pattern",
                )
            return MaterialRecommendationResult(
                ok=True,
                asset_id="",
                renderer=renderer,
                strategy_used="renderer_default",
                warnings=[f"No lookdev pattern found for environment: {environment!r}"],
                recommendations=[
                    MaterialRecommendation(
                        material_name="industrial_metal",
                        renderer=renderer,
                        confidence=0.50,
                        source="renderer_default",
                        reasoning="No environment pattern — using default.",
                    )
                ],
            )
        except Exception as exc:
            return MaterialRecommendationResult(
                ok=False,
                renderer=_normalize_renderer(renderer),
                errors=[f"recommend_environment_materials failed: {exc}"],
            )

    def recommend_renderer_materials(
        self,
        renderer: str,
    ) -> MaterialRecommendationResult:
        """Return default materials suitable for a renderer."""
        try:
            renderer = _normalize_renderer(renderer)
            profile = get_renderer_profiles().get_profile(renderer)
            defaults = ["industrial_metal", "concrete", "plastic", "glass"]
            recs = [
                MaterialRecommendation(
                    asset_id="",
                    material_name=mat,
                    renderer=renderer,
                    confidence=0.60,
                    source="renderer_default",
                    reasoning=f"Renderer '{renderer}' ({profile.material_class}) default palette.",
                )
                for mat in defaults
            ]
            with self._lock:
                self._recommend_count += 1
            return MaterialRecommendationResult(
                ok=True,
                asset_id="",
                recommendations=recs,
                renderer=renderer,
                strategy_used="renderer_default",
            )
        except Exception as exc:
            return MaterialRecommendationResult(
                ok=False,
                renderer=_normalize_renderer(renderer),
                errors=[f"recommend_renderer_materials failed: {exc}"],
            )


_INSTANCE: Optional[MaterialRecommendationEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_material_recommendation_engine() -> MaterialRecommendationEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = MaterialRecommendationEngine()
    return _INSTANCE


def reset_material_recommendation_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
