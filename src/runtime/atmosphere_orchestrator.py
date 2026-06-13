"""
Atmosphere Orchestrator (Tier 4 — Cinematic Orchestration)
============================================================
Generates cinematic atmospheric layering plans for scene depth and readability.

DESIGN RULE: NO bridge calls. Planning only. Deterministic.

Public API:
    AtmosphereOrchestrator
        .generate_fog_layers(atmosphere_type, density, zone_depths) -> list
        .generate_depth_atmosphere(zones, layout_rules) -> dict
        .generate_volumetric_density(atmosphere_type, lighting_plan) -> dict
        .build_particle_layers(scene_theme, atmosphere_type) -> list
        .evaluate_atmospheric_readability(atmosphere_plan) -> dict
        .stats() -> dict

    get_atmosphere_orchestrator() -> AtmosphereOrchestrator
    reset_atmosphere_orchestrator_for_tests()
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Atmosphere type presets
# ---------------------------------------------------------------------------

_ATMOSPHERE_TYPES: Dict[str, Dict[str, Any]] = {
    "industrial_fog": {
        "description":    "Dense ground-hugging industrial fog with mid-level density.",
        "density":        0.06,
        "height":         3.0,
        "color":          [0.85, 0.82, 0.78],
        "falloff":        "exponential",
        "particle":       "dust",
        "particle_density": 0.3,
        "volumetric":     True,
        "depth_support":  "strong",
    },
    "volumetric_scifi": {
        "description":    "Thin atmospheric haze supporting visible light shafts.",
        "density":        0.02,
        "height":         8.0,
        "color":          [0.8, 0.85, 1.0],
        "falloff":        "linear",
        "particle":       "haze",
        "particle_density": 0.1,
        "volumetric":     True,
        "depth_support":  "moderate",
    },
    "dusty_hangar": {
        "description":    "Floating dust particles with visible light shafts.",
        "density":        0.04,
        "height":         6.0,
        "color":          [0.9, 0.88, 0.8],
        "falloff":        "exponential",
        "particle":       "dust",
        "particle_density": 0.5,
        "volumetric":     True,
        "depth_support":  "strong",
    },
    "cold_atmosphere": {
        "description":    "Subtle cold ground mist with low density.",
        "density":        0.015,
        "height":         2.0,
        "color":          [0.85, 0.9, 1.0],
        "falloff":        "linear",
        "particle":       "mist",
        "particle_density": 0.15,
        "volumetric":     False,
        "depth_support":  "moderate",
    },
    "cinematic_depth_fog": {
        "description":    "Exponential depth fog maximising depth separation.",
        "density":        0.035,
        "height":         5.0,
        "color":          [0.82, 0.84, 0.88],
        "falloff":        "exponential_squared",
        "particle":       "none",
        "particle_density": 0.0,
        "volumetric":     True,
        "depth_support":  "strong",
    },
}

_DEFAULT_TYPE = "industrial_fog"

_ZONE_FOG_LAYER_NAMES: Dict[str, str] = {
    "hero_area":  "fog_hero",
    "midground":  "fog_mid",
    "background": "fog_bg",
}

# Depth multiplier per zone — background is fully dense, hero is subtle
_ZONE_DEPTH_MULTIPLIERS: Dict[str, float] = {
    "background": 1.0,
    "midground":  0.6,
    "hero_area":  0.3,
}

# fog_density string → (density, atmosphere_type)
_FOG_DENSITY_MAP: Dict[str, tuple] = {
    "none":   (0.0,  "cinematic_depth_fog"),
    "light":  (0.02, "volumetric_scifi"),
    "medium": (0.04, "industrial_fog"),
    "heavy":  (0.08, "dusty_hangar"),
}


class AtmosphereOrchestrator:
    """
    Generates cinematic atmospheric layering plans for scene depth and readability.
    Planning-only — no bridge calls, no randomness.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._plan_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_fog_layers(
        self,
        atmosphere_type: str,
        density: float,
        zone_depths: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """
        Generate a fog layer dict for each zone in zone_depths.

        zone_depths example: {"hero_area": 0.0, "midground": -10.0, "background": -30.0}

        Each layer has:
            name, zone, depth, density, color, falloff,
            op, parent, type
        Density is scaled by a per-zone depth multiplier
        (background=1.0, midground=0.6, hero_area=0.3).

        Unknown atmosphere_type falls back to _DEFAULT_TYPE.
        Returns [] if zone_depths is empty.
        """
        if not zone_depths:
            return []

        preset = _ATMOSPHERE_TYPES.get(atmosphere_type, _ATMOSPHERE_TYPES[_DEFAULT_TYPE])

        layers: List[Dict[str, Any]] = []
        for zone, depth in zone_depths.items():
            multiplier = _ZONE_DEPTH_MULTIPLIERS.get(zone, 0.5)
            layer_name = _ZONE_FOG_LAYER_NAMES.get(zone, f"fog_{zone}")
            layers.append({
                "name":    layer_name,
                "zone":    zone,
                "depth":   depth,
                "density": round(density * multiplier, 6),
                "color":   list(preset["color"]),
                "falloff": preset["falloff"],
                "op":      "create_node",
                "parent":  "/obj/environment",
                "type":    "vdbfrompolygons",
            })

        with self._lock:
            self._plan_count += 1

        return layers

    def generate_depth_atmosphere(
        self,
        zones: Dict[str, Any],
        layout_rules: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyse zones and layout_rules to recommend atmosphere parameters.

        layout_rules may contain: "fog_density" ("none"|"light"|"medium"|"heavy")

        Returns:
            atmosphere_type, recommended_density, depth_support,
            zone_coverage, readability_risk, notes
        """
        notes: List[str] = []

        fog_density_str = layout_rules.get("fog_density", None)

        if fog_density_str in _FOG_DENSITY_MAP:
            recommended_density, atmosphere_type = _FOG_DENSITY_MAP[fog_density_str]
        else:
            # Missing key fallback
            recommended_density = 0.03
            atmosphere_type = "cinematic_depth_fog"

        # Determine depth_support from preset
        preset = _ATMOSPHERE_TYPES.get(atmosphere_type, _ATMOSPHERE_TYPES[_DEFAULT_TYPE])
        if recommended_density == 0.0:
            depth_support = "none"
        else:
            depth_support = preset.get("depth_support", "moderate")

        # Readability risk
        if fog_density_str == "heavy" or recommended_density > 0.06:
            readability_risk = "high"
        else:
            readability_risk = "low"

        # Zone coverage
        zone_coverage: Dict[str, bool] = {
            zone: recommended_density > 0 for zone in zones
        }

        # Notes
        if "background" not in zones:
            notes.append("No background zone — depth atmosphere has no anchor.")
        if recommended_density > 0.06:
            notes.append(
                "High density fog — readability of background assets may suffer."
            )

        with self._lock:
            self._plan_count += 1

        return {
            "atmosphere_type":      atmosphere_type,
            "recommended_density":  recommended_density,
            "depth_support":        depth_support,
            "zone_coverage":        zone_coverage,
            "readability_risk":     readability_risk,
            "notes":                notes,
        }

    def generate_volumetric_density(
        self,
        atmosphere_type: str,
        lighting_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Return volumetric density recommendations for the given atmosphere type.

        scatter_multiplier adjusts based on lighting_plan:
        - None         → 1.0
        - volumetric enabled True  → 1.2
        - volumetric enabled False → 0.8

        Returns:
            enabled, density, scatter_multiplier, absorption, emission, color, notes
        """
        notes: List[str] = []
        preset = _ATMOSPHERE_TYPES.get(atmosphere_type, _ATMOSPHERE_TYPES[_DEFAULT_TYPE])

        enabled: bool = preset.get("volumetric", True)
        density: float = preset.get("density", 0.03)

        # scatter_multiplier
        if lighting_plan is None:
            scatter_multiplier = 1.0
        else:
            volumetric_block = lighting_plan.get("volumetric", {})
            if isinstance(volumetric_block, dict):
                vol_enabled = volumetric_block.get("enabled", None)
                if vol_enabled is True:
                    scatter_multiplier = 1.2
                    notes.append("Volumetric lighting active — scatter multiplier increased.")
                elif vol_enabled is False:
                    scatter_multiplier = 0.8
                    notes.append("Volumetric lighting disabled — scatter multiplier reduced.")
                else:
                    scatter_multiplier = 1.0
            else:
                scatter_multiplier = 1.0

        absorption: float = round(density * 0.3, 6)

        with self._lock:
            self._plan_count += 1

        return {
            "enabled":            enabled,
            "density":            density,
            "scatter_multiplier": scatter_multiplier,
            "absorption":         absorption,
            "emission":           0.0,
            "color":              list(preset.get("color", [1.0, 1.0, 1.0])),
            "notes":              notes,
        }

    def build_particle_layers(
        self,
        scene_theme: str,
        atmosphere_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Return a list of particle layer dicts.

        One particle layer is added when the atmosphere preset has
        particle != "none". Returns [] if particle_type is "none"
        or if atmosphere_type is unknown.
        """
        preset = _ATMOSPHERE_TYPES.get(atmosphere_type)
        if preset is None:
            return []

        particle_type: str = preset.get("particle", "none")
        if particle_type == "none":
            return []

        with self._lock:
            self._plan_count += 1

        return [
            {
                "name":          f"particles_{particle_type}",
                "particle_type": particle_type,
                "density":       preset.get("particle_density", 0.1),
                "scene_theme":   scene_theme,
                "op":            "create_node",
                "parent":        "/obj/fx",
                "type":          "popnet",
            }
        ]

    def evaluate_atmospheric_readability(
        self,
        atmosphere_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate the readability impact of the given atmosphere plan.

        atmosphere_plan is the return value of generate_depth_atmosphere().

        Returns:
            readable, readability_score, issues, strengths, notes
        """
        issues: List[str] = []
        strengths: List[str] = []
        notes: List[str] = []
        score = 1.0

        depth_support = atmosphere_plan.get("depth_support", "none")
        readability_risk = atmosphere_plan.get("readability_risk", "low")
        recommended_density = atmosphere_plan.get("recommended_density", 0.0)

        # Strength: good depth support
        if depth_support in ("strong", "moderate"):
            strengths.append(
                "Atmospheric depth layering supports visual separation."
            )

        # Issue: heavy fog risk
        if readability_risk == "high":
            issues.append(
                "Heavy fog density risks obscuring mid-ground assets."
            )
            score -= 0.3

        # Issue: density above readability threshold
        if recommended_density > 0.07:
            issues.append(
                "Fog density exceeds readability threshold — silhouettes may be lost."
            )
            score -= 0.3

        # Note: no atmosphere
        if recommended_density == 0.0:
            notes.append(
                "No atmosphere applied — depth separation relies on geometry placement only."
            )

        score = max(0.0, min(1.0, score))
        readable = len(issues) == 0

        return {
            "readable":          readable,
            "readability_score": round(score, 3),
            "issues":            issues,
            "strengths":         strengths,
            "notes":             notes,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"plan_count": self._plan_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AtmosphereOrchestrator] = None
_INSTANCE_LOCK = threading.Lock()


def get_atmosphere_orchestrator() -> AtmosphereOrchestrator:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = AtmosphereOrchestrator()
        return _INSTANCE


def reset_atmosphere_orchestrator_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
