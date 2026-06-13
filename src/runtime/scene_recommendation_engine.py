"""
Scene Recommendation Engine (Tier 5 — Production Knowledge System)
===================================================================
Recommends production-proven lighting, camera, atmosphere, pattern,
and asset configurations for a given scene type.

Recommendation priority:
    1. ProductionMemory — what actually worked in past sessions
    2. PatternLibrary   — ranked built-in and custom patterns
    3. AssetKnowledgeGraph — commonly used assets for the scene type
    4. Built-in defaults — hard-coded per-environment fallbacks

DESIGN RULE: NO bridge calls. Deterministic. Read-only from Tiers 1–4.

Public API:
    SceneRecommendationEngine
        .recommend_lighting(scene_type, context=None) -> dict
        .recommend_camera(scene_type, context=None) -> dict
        .recommend_atmosphere(scene_type, context=None) -> dict
        .recommend_patterns(scene_type, context=None) -> list
        .recommend_assets(scene_type, context=None) -> list
        .build_scene_recommendations(scene_type, context=None) -> dict
        .stats() -> dict

    get_scene_recommendation_engine() -> SceneRecommendationEngine  (singleton)
    reset_scene_recommendation_engine_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Built-in defaults per scene type
# ---------------------------------------------------------------------------

_SCENE_DEFAULTS: Dict[str, Dict[str, str]] = {
    "industrial_hangar": {
        "lighting":    "cinematic_industrial",
        "camera":      "cinematic_push_in",
        "atmosphere":  "industrial_fog",
        "template_id": "cinematic_industrial_hangar",
    },
    "robotics_lab": {
        "lighting":    "cold_scifi",
        "camera":      "cinematic_push_in",
        "atmosphere":  "volumetric_scifi",
        "template_id": "robotics_repair_facility",
    },
    "sci_fi_corridor": {
        "lighting":    "bladerunner_noir",
        "camera":      "atmospheric_tracking",
        "atmosphere":  "volumetric_scifi",
        "template_id": "atmospheric_scifi_corridor",
    },
    "cinematic_control_room": {
        "lighting":    "warm_control_room",
        "camera":      "orbital_reveal",
        "atmosphere":  "cold_atmosphere",
        "template_id": "cinematic_control_room",
    },
    "abandoned_factory": {
        "lighting":    "atmospheric_lab",
        "camera":      "hero_focus",
        "atmosphere":  "dusty_hangar",
        "template_id": "cinematic_industrial_hangar",
    },
}

_DEFAULT_FALLBACK = {
    "lighting":    "cinematic_industrial",
    "camera":      "cinematic_push_in",
    "atmosphere":  "cinematic_depth_fog",
    "template_id": "cinematic_industrial_hangar",
}

# ---------------------------------------------------------------------------
# Confidence levels
# ---------------------------------------------------------------------------

_CONFIDENCE_MEMORY  = 0.95   # from production_memory (empirically proven)
_CONFIDENCE_PATTERN = 0.80   # from pattern_library (ranked pattern)
_CONFIDENCE_GRAPH   = 0.65   # from asset_knowledge_graph
_CONFIDENCE_DEFAULT = 0.50   # built-in default


class SceneRecommendationEngine:
    """Recommends production-proven scene configurations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recommendation_count = 0

    # ------------------------------------------------------------------
    # Individual dimension recommenders
    # ------------------------------------------------------------------

    def recommend_lighting(
        self,
        scene_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Recommend a lighting style for the given scene type.

        Returns:
            {recommended_style, confidence, source, reasoning}
        """
        # 1. Check production memory for proven styles
        memory_style = self._lighting_from_memory(scene_type)
        if memory_style:
            return {
                "recommended_style": memory_style,
                "confidence":        _CONFIDENCE_MEMORY,
                "source":            "production_memory",
                "reasoning":         f"Used successfully in past {scene_type} scenes.",
            }

        # 2. Check pattern library
        pattern_style = self._lighting_from_patterns(scene_type)
        if pattern_style:
            return {
                "recommended_style": pattern_style,
                "confidence":        _CONFIDENCE_PATTERN,
                "source":            "pattern_library",
                "reasoning":         f"Top-ranked lighting pattern for {scene_type}.",
            }

        # 3. Default
        defaults = _SCENE_DEFAULTS.get(scene_type, _DEFAULT_FALLBACK)
        return {
            "recommended_style": defaults["lighting"],
            "confidence":        _CONFIDENCE_DEFAULT,
            "source":            "builtin_default",
            "reasoning":         f"Default lighting configuration for {scene_type}.",
        }

    def recommend_camera(
        self,
        scene_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Recommend a camera mode for the given scene type."""
        memory_mode = self._camera_from_memory(scene_type)
        if memory_mode:
            return {
                "recommended_mode": memory_mode,
                "confidence":       _CONFIDENCE_MEMORY,
                "source":           "production_memory",
                "reasoning":        f"Camera mode used in successful {scene_type} scenes.",
            }

        pattern_mode = self._camera_from_patterns(scene_type)
        if pattern_mode:
            return {
                "recommended_mode": pattern_mode,
                "confidence":       _CONFIDENCE_PATTERN,
                "source":           "pattern_library",
                "reasoning":        f"Top-ranked camera pattern for {scene_type}.",
            }

        defaults = _SCENE_DEFAULTS.get(scene_type, _DEFAULT_FALLBACK)
        return {
            "recommended_mode": defaults["camera"],
            "confidence":       _CONFIDENCE_DEFAULT,
            "source":           "builtin_default",
            "reasoning":        f"Default camera mode for {scene_type}.",
        }

    def recommend_atmosphere(
        self,
        scene_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Recommend an atmosphere type for the given scene type."""
        memory_atm = self._atmosphere_from_memory(scene_type)
        if memory_atm:
            return {
                "recommended_type": memory_atm,
                "confidence":       _CONFIDENCE_MEMORY,
                "source":           "production_memory",
                "reasoning":        f"Atmosphere used in successful {scene_type} scenes.",
            }

        pattern_atm = self._atmosphere_from_patterns(scene_type)
        if pattern_atm:
            return {
                "recommended_type": pattern_atm,
                "confidence":       _CONFIDENCE_PATTERN,
                "source":           "pattern_library",
                "reasoning":        f"Top-ranked atmosphere pattern for {scene_type}.",
            }

        defaults = _SCENE_DEFAULTS.get(scene_type, _DEFAULT_FALLBACK)
        return {
            "recommended_type": defaults["atmosphere"],
            "confidence":       _CONFIDENCE_DEFAULT,
            "source":           "builtin_default",
            "reasoning":        f"Default atmosphere for {scene_type}.",
        }

    def recommend_patterns(
        self,
        scene_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return ranked scene patterns for the given scene type."""
        try:
            from src.runtime.pattern_library import get_pattern_library
            lib = get_pattern_library()
            patterns = lib.search_patterns(scene_type=scene_type, pattern_type="scene_pattern")
            if not patterns:
                patterns = lib.search_patterns(pattern_type="scene_pattern")
            return patterns[:5]
        except Exception:
            return []

    def recommend_assets(
        self,
        scene_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Return asset ids commonly used for the given scene type."""
        try:
            from src.runtime.asset_knowledge_graph import get_asset_knowledge_graph
            graph = get_asset_knowledge_graph()
            assets = graph.find_scene_assets(scene_type)
            return assets[:10]
        except Exception:
            return []

    def build_scene_recommendations(
        self,
        scene_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return a complete set of recommendations for a scene type.

        Returns:
            {scene_type, lighting, camera, atmosphere, patterns,
             assets, template_id, overall_confidence, generated_at}
        """
        import time

        lighting   = self.recommend_lighting(scene_type, context)
        camera     = self.recommend_camera(scene_type, context)
        atmosphere = self.recommend_atmosphere(scene_type, context)
        patterns   = self.recommend_patterns(scene_type, context)
        assets     = self.recommend_assets(scene_type, context)

        # Template recommendation
        template_id = _SCENE_DEFAULTS.get(scene_type, _DEFAULT_FALLBACK)["template_id"]

        # Overall confidence = average of three primary dimension confidences
        overall_confidence = round(
            (lighting["confidence"] + camera["confidence"] + atmosphere["confidence"]) / 3,
            4,
        )

        with self._lock:
            self._recommendation_count += 1

        return {
            "scene_type":          scene_type,
            "lighting":            lighting,
            "camera":              camera,
            "atmosphere":          atmosphere,
            "patterns":            patterns,
            "assets":              assets,
            "template_id":         template_id,
            "overall_confidence":  overall_confidence,
            "generated_at":        time.time(),
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"recommendation_count": self._recommendation_count}

    # ------------------------------------------------------------------
    # Private helpers — memory queries
    # ------------------------------------------------------------------

    def _lighting_from_memory(self, scene_type: str) -> Optional[str]:
        try:
            from src.runtime.production_memory import get_production_memory
            mem = get_production_memory()
            history = mem.get_scene_history(scene_type=scene_type, status="success", limit=20)
            if not history:
                return None
            # Count frequency of lighting styles
            style_counts: Dict[str, int] = {}
            for record in history:
                s = record.get("lighting_style", "")
                if s:
                    style_counts[s] = style_counts.get(s, 0) + 1
            if not style_counts:
                return None
            return max(style_counts, key=style_counts.get)
        except Exception:
            return None

    def _camera_from_memory(self, scene_type: str) -> Optional[str]:
        try:
            from src.runtime.production_memory import get_production_memory
            mem = get_production_memory()
            history = mem.get_scene_history(scene_type=scene_type, status="success", limit=20)
            if not history:
                return None
            mode_counts: Dict[str, int] = {}
            for record in history:
                m = record.get("camera_style", "")
                if m:
                    mode_counts[m] = mode_counts.get(m, 0) + 1
            return max(mode_counts, key=mode_counts.get) if mode_counts else None
        except Exception:
            return None

    def _atmosphere_from_memory(self, scene_type: str) -> Optional[str]:
        try:
            from src.runtime.production_memory import get_production_memory
            mem = get_production_memory()
            history = mem.get_scene_history(scene_type=scene_type, status="success", limit=20)
            if not history:
                return None
            atm_counts: Dict[str, int] = {}
            for record in history:
                a = record.get("atmosphere_type", "")
                if a:
                    atm_counts[a] = atm_counts.get(a, 0) + 1
            return max(atm_counts, key=atm_counts.get) if atm_counts else None
        except Exception:
            return None

    def _lighting_from_patterns(self, scene_type: str) -> Optional[str]:
        try:
            from src.runtime.pattern_library import get_pattern_library
            lib = get_pattern_library()
            # Only use patterns that are explicitly tied to this scene_type
            patterns = lib.search_patterns(scene_type=scene_type)
            for p in patterns:
                if p.get("scene_type") == scene_type:
                    s = p.get("lighting")
                    if s:
                        return s
            return None
        except Exception:
            return None

    def _camera_from_patterns(self, scene_type: str) -> Optional[str]:
        try:
            from src.runtime.pattern_library import get_pattern_library
            lib = get_pattern_library()
            patterns = lib.search_patterns(scene_type=scene_type)
            for p in patterns:
                if p.get("scene_type") == scene_type:
                    m = p.get("camera")
                    if m:
                        return m
            return None
        except Exception:
            return None

    def _atmosphere_from_patterns(self, scene_type: str) -> Optional[str]:
        try:
            from src.runtime.pattern_library import get_pattern_library
            lib = get_pattern_library()
            patterns = lib.search_patterns(scene_type=scene_type)
            for p in patterns:
                if p.get("scene_type") == scene_type:
                    a = p.get("atmosphere")
                    if a:
                        return a
            return None
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[SceneRecommendationEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_scene_recommendation_engine() -> SceneRecommendationEngine:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = SceneRecommendationEngine()
    return _INSTANCE


def reset_scene_recommendation_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
