"""
Cinematic Composition Engine (Tier 2 — Semantic Scene Assembly)
=================================================================
Procedural cinematic orchestration intelligence.

NOT rendering analysis.
NOT LLM-based.

Deterministic composition heuristics for:
  - visual balance analysis
  - focus distribution calculation
  - depth layer suggestions
  - camera target generation
  - scene readability evaluation

Public API:
    get_cinematic_composition_engine() -> CinematicCompositionEngine  (singleton)
    reset_cinematic_composition_engine_for_tests()

    CinematicCompositionEngine.analyze_visual_balance(zones) -> dict
    CinematicCompositionEngine.calculate_focus_distribution(zones) -> dict
    CinematicCompositionEngine.suggest_camera_targets(layout_plan) -> list[dict]
    CinematicCompositionEngine.evaluate_scene_readability(layout_plan) -> dict
    CinematicCompositionEngine.suggest_depth_layers(scene_theme, asset_count) -> list[dict]
    CinematicCompositionEngine.stats() -> dict
"""

import threading
from typing import Any, Dict, List, Optional

# Per-zone visual weight multipliers (higher = more compositional pull)
_ZONE_WEIGHTS: Dict[str, int] = {
    "hero_area":   3,
    "foreground":  2,
    "midground":   2,
    "background":  1,
    "sides":       1,
    "walls":       1,
    "ceiling":     1,
    "upper_edges": 1,
}

# Maximum recommended hero assets before focal clarity suffers
_MAX_HERO_ASSETS = 3

# Minimum midground/background population for three-layer depth
_MIN_DEPTH_FILL = 1

# Minimum assets per scene before depth layering is worthwhile
_DEPTH_LAYER_MIN_ASSETS = 10


class CinematicCompositionEngine:
    """Provides deterministic cinematic composition intelligence.

    All methods are advisory. No bridge calls, no LLM, no I/O.
    """

    def __init__(self) -> None:
        self._lock   = threading.Lock()
        self._eval_count = 0

    # ------------------------------------------------------------------
    # Visual balance
    # ------------------------------------------------------------------

    def analyze_visual_balance(
        self,
        zones: Dict[str, List[Any]],
    ) -> Dict[str, Any]:
        """Evaluate visual balance across scene zones.

        Args:
            zones: Mapping of zone_name -> list of asset dicts.

        Returns:
            {
              "balanced":          bool,
              "balance_score":     float (0.0–1.0),
              "zone_weights":      {zone: int},
              "heaviest_zone":     str | None,
              "lightest_zone":     str | None,
              "recommendations":   list[str],
            }
        """
        zone_weights: Dict[str, int] = {}
        for zone, assets in zones.items():
            base = _ZONE_WEIGHTS.get(zone, 1)
            zone_weights[zone] = base * len(assets)

        total = sum(zone_weights.values())
        recommendations: List[str] = []

        if total == 0:
            return {
                "balanced":        True,
                "balance_score":   1.0,
                "zone_weights":    zone_weights,
                "heaviest_zone":   None,
                "lightest_zone":   None,
                "recommendations": ["Scene has no assets — all zones are empty."],
            }

        heaviest = max(zone_weights, key=lambda z: zone_weights[z])
        lightest = min(zone_weights, key=lambda z: zone_weights[z])

        max_w = zone_weights[heaviest]
        min_w = zone_weights[lightest]

        balance_score = 1.0 - ((max_w - min_w) / max_w) if max_w else 1.0
        balance_score = max(0.0, min(1.0, balance_score))
        balanced = balance_score >= 0.4

        hero_count = len(zones.get("hero_area", []))
        if hero_count > _MAX_HERO_ASSETS:
            recommendations.append(
                f"Hero zone has {hero_count} assets — reduce to {_MAX_HERO_ASSETS} for a clear focal point."
            )
        if not zones.get("midground"):
            recommendations.append("Midground is empty — add supporting assets to create depth.")
        if not zones.get("background"):
            recommendations.append("Background is empty — add distant dressing to avoid flat scenes.")
        if not recommendations and not balanced:
            recommendations.append(
                f"Scene weight concentrated in '{heaviest}' — redistribute assets to other zones."
            )

        return {
            "balanced":        balanced,
            "balance_score":   round(balance_score, 3),
            "zone_weights":    zone_weights,
            "heaviest_zone":   heaviest,
            "lightest_zone":   lightest,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Focus distribution
    # ------------------------------------------------------------------

    def calculate_focus_distribution(
        self,
        zones: Dict[str, List[Any]],
    ) -> Dict[str, Any]:
        """Calculate how visual attention distributes across zones.

        Returns:
            {
              "primary_focus":   str | None,
              "secondary_focus": str | None,
              "focus_clarity":   float (0.0–1.0),
              "distribution":    {zone: float},
            }
        """
        counts = {z: len(assets) for z, assets in zones.items()}
        total  = sum(counts.values())

        if total == 0:
            return {
                "primary_focus":   None,
                "secondary_focus": None,
                "focus_clarity":   0.0,
                "distribution":    {},
            }

        distribution = {z: round(c / total, 3) for z, c in counts.items()}
        sorted_zones = sorted(counts, key=lambda z: counts[z], reverse=True)

        primary   = sorted_zones[0] if sorted_zones else None
        secondary = sorted_zones[1] if len(sorted_zones) > 1 else None
        focus_clarity = distribution.get(primary, 0.0) if primary else 0.0

        return {
            "primary_focus":   primary,
            "secondary_focus": secondary,
            "focus_clarity":   round(focus_clarity, 3),
            "distribution":    distribution,
        }

    # ------------------------------------------------------------------
    # Camera targets
    # ------------------------------------------------------------------

    def suggest_camera_targets(
        self,
        layout_plan: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Suggest semantic camera target positions for a layout plan.

        Returns a list of:
            {name, zone, priority, shot_type, description}

        Always returns at least an establishing shot, even for empty plans.
        """
        targets:      List[Dict[str, Any]] = []
        zones         = layout_plan.get("zones", {})
        layout_rules  = layout_plan.get("layout_rules", {})
        camera_hints  = layout_plan.get("camera_hints", [])
        environment   = layout_plan.get("scene_theme", "generic")

        # Hero-zone shot — highest priority when hero assets exist
        if zones.get("hero_area"):
            targets.append({
                "name":        "hero_focus",
                "zone":        "hero_area",
                "priority":    1,
                "shot_type":   "medium_close",
                "description": f"Primary hero focus in {environment}",
            })

        # Establishing shot — always present
        targets.append({
            "name":        "establishing",
            "zone":        "full_scene",
            "priority":    2,
            "shot_type":   "wide_establishing",
            "description": "Full-environment establishing shot",
        })

        # Depth reveal — mid-to-background if both are populated
        if zones.get("midground") or zones.get("background"):
            targets.append({
                "name":        "depth_reveal",
                "zone":        "midground_to_background",
                "priority":    3,
                "shot_type":   "depth_of_field",
                "description": "Reveal environmental depth through layered dressing",
            })

        # Environment-specific hints (at most 2 extra)
        hero_focus = layout_rules.get("hero_focus", "center")
        for i, hint in enumerate(camera_hints[:2]):
            targets.append({
                "name":        hint,
                "zone":        hero_focus,
                "priority":    4 + i,
                "shot_type":   hint,
                "description": f"Environment-specific: {hint.replace('_', ' ')}",
            })

        return targets

    # ------------------------------------------------------------------
    # Scene readability
    # ------------------------------------------------------------------

    def evaluate_scene_readability(
        self,
        layout_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Evaluate how readable the scene composition is.

        Returns:
            {
              "readable":          bool,
              "readability_score": float (0.0–1.0),
              "issues":            list[str],
              "strengths":         list[str],
            }
        """
        with self._lock:
            self._eval_count += 1

        zones     = layout_plan.get("zones", {})
        issues:    List[str] = []
        strengths: List[str] = []

        hero_count = len(zones.get("hero_area", []))
        mid_count  = len(zones.get("midground",  []))
        bg_count   = len(zones.get("background", []))
        total      = sum(len(v) for v in zones.values())

        score = 1.0

        if total == 0:
            return {
                "readable":          False,
                "readability_score": 0.0,
                "issues":            ["Scene is empty — no assets placed in any zone."],
                "strengths":         [],
            }

        if hero_count > _MAX_HERO_ASSETS:
            issues.append(
                f"Hero zone overloaded ({hero_count} assets) — clear focal point is lost."
            )
            score -= 0.25

        if hero_count == 0:
            issues.append("No hero asset defined — scene lacks a narrative focus point.")
            score -= 0.2
        else:
            strengths.append(f"Clear hero focus with {hero_count} primary asset(s).")

        if mid_count == 0 and bg_count == 0:
            issues.append("No midground or background assets — scene feels flat.")
            score -= 0.3
        elif mid_count == 0:
            issues.append("Midground is empty — no visual bridge between hero and background.")
            score -= 0.15
        elif bg_count == 0:
            issues.append("Background is empty — scene lacks depth and environmental scale.")
            score -= 0.1
        else:
            strengths.append("Three-layer depth composition achieved.")

        score    = max(0.0, min(1.0, score))
        readable = score >= 0.5

        return {
            "readable":          readable,
            "readability_score": round(score, 3),
            "issues":            issues,
            "strengths":         strengths,
        }

    # ------------------------------------------------------------------
    # Depth layers
    # ------------------------------------------------------------------

    def suggest_depth_layers(
        self,
        scene_theme: str,
        asset_count: int,
    ) -> List[Dict[str, Any]]:
        """Suggest depth layer allocation for a scene.

        Args:
            scene_theme:  Environment/theme name.
            asset_count:  Total assets planned for the scene.

        Returns:
            List of {layer_name, purpose, suggested_asset_count, depth_priority}
        """
        hero_alloc   = max(1, min(3, asset_count // 5))
        mid_alloc    = max(1, asset_count // 3)
        bg_alloc     = max(1, asset_count - hero_alloc - mid_alloc)
        detail_alloc = max(0, asset_count // 10)

        layers = [
            {
                "layer_name":             "hero_area",
                "purpose":                "Primary narrative focus — hero assets and key props",
                "suggested_asset_count":  hero_alloc,
                "depth_priority":         1,
            },
            {
                "layer_name":             "midground",
                "purpose":                "Supporting elements — spatial context for the hero",
                "suggested_asset_count":  mid_alloc,
                "depth_priority":         2,
            },
            {
                "layer_name":             "background",
                "purpose":                "Environmental dressing — establishes scale and world-building",
                "suggested_asset_count":  bg_alloc,
                "depth_priority":         3,
            },
        ]

        if asset_count >= _DEPTH_LAYER_MIN_ASSETS:
            layers.append({
                "layer_name":             "foreground_frame",
                "purpose":                "DOF foreground elements to frame the hero",
                "suggested_asset_count":  detail_alloc,
                "depth_priority":         0,
            })

        return layers

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"eval_count": self._eval_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[CinematicCompositionEngine] = None
_LOCK = threading.Lock()


def get_cinematic_composition_engine() -> CinematicCompositionEngine:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = CinematicCompositionEngine()
        return _INSTANCE


def reset_cinematic_composition_engine_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
