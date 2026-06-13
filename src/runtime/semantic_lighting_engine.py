"""
Semantic Lighting Engine (Tier 4 — Cinematic Orchestration)
============================================================
Generates production-aware cinematic lighting orchestration plans.

DESIGN RULE: NO bridge calls. Planning only. Deterministic.
This module reads data structures and returns lighting plans as
structured operation dicts ready for the transaction system.
It never calls get_bridge() or mutates any Houdini state.

Public API:
    SemanticLightingEngine
        .generate_lighting_plan(zones, style, scene_theme) -> dict
        .build_key_light_strategy(style, zones) -> dict
        .build_rim_light_strategy(style, zones) -> dict
        .build_practical_lighting(scene_theme, zones) -> dict
        .build_volumetric_lighting(volumetric_settings) -> dict
        .evaluate_light_balance(lighting_plan) -> dict
        .stats() -> dict

    get_semantic_lighting_engine() -> SemanticLightingEngine
    reset_semantic_lighting_engine_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Lighting presets
# ---------------------------------------------------------------------------

_LIGHTING_PRESETS: Dict[str, Dict[str, Any]] = {
    "cinematic_industrial": {
        "key": {
            "intensity": 2.5,
            "color_temp": 5500,
            "angle": (-45, 30, 0),
            "shadow_density": 0.9,
        },
        "rim": {
            "intensity": 1.5,
            "color_temp": 4500,
            "angle": (-20, -150, 0),
        },
        "fill": {
            "intensity": 0.3,
            "color_temp": 6500,
        },
        "practicals": {
            "type": "area_light",
            "count": 3,
            "distribution": "ceiling",
            "color_temp": 4500,
        },
        "volumetric": {
            "enabled": True,
            "density": 0.05,
            "color": [0.9, 0.85, 0.8],
        },
        "renderer_hints": {
            "arnold": {"exposure": 0.0, "samples": 3},
            "karma":  {"path_trace_samples": 256},
        },
    },
    "bladerunner_noir": {
        "key": {
            "intensity": 3.0,
            "color_temp": 3200,
            "angle": (-30, 90, 0),
            "shadow_density": 1.0,
        },
        "rim": {
            "intensity": 2.0,
            "color_temp": 8000,
            "angle": (-10, -120, 0),
        },
        "fill": {
            "intensity": 0.1,
            "color_temp": 5000,
        },
        "practicals": {
            "type": "spot_light",
            "count": 5,
            "distribution": "background",
            "color_temp": 7000,
        },
        "volumetric": {
            "enabled": True,
            "density": 0.08,
            "color": [0.7, 0.8, 1.0],
        },
        "renderer_hints": {
            "arnold": {"exposure": -0.5, "samples": 4},
            "karma":  {"path_trace_samples": 512},
        },
    },
    "cold_scifi": {
        "key": {
            "intensity": 2.0,
            "color_temp": 7500,
            "angle": (-60, 10, 0),
            "shadow_density": 0.7,
        },
        "rim": {
            "intensity": 1.2,
            "color_temp": 8500,
            "angle": (-25, -160, 0),
        },
        "fill": {
            "intensity": 0.5,
            "color_temp": 7000,
        },
        "practicals": {
            "type": "area_light",
            "count": 4,
            "distribution": "ceiling",
            "color_temp": 6500,
        },
        "volumetric": {
            "enabled": False,
            "density": 0.01,
            "color": [0.85, 0.9, 1.0],
        },
        "renderer_hints": {
            "arnold": {"exposure": 0.3, "samples": 3},
            "karma":  {"path_trace_samples": 256},
        },
    },
    "atmospheric_lab": {
        "key": {
            "intensity": 1.8,
            "color_temp": 5800,
            "angle": (-50, 20, 0),
            "shadow_density": 0.6,
        },
        "rim": {
            "intensity": 0.8,
            "color_temp": 5500,
            "angle": (-30, -140, 0),
        },
        "fill": {
            "intensity": 0.6,
            "color_temp": 5800,
        },
        "practicals": {
            "type": "area_light",
            "count": 6,
            "distribution": "uniform",
            "color_temp": 5500,
        },
        "volumetric": {
            "enabled": False,
            "density": 0.0,
            "color": [1.0, 1.0, 1.0],
        },
        "renderer_hints": {
            "arnold": {"exposure": 0.2, "samples": 3},
            "karma":  {"path_trace_samples": 256},
        },
    },
    "warm_control_room": {
        "key": {
            "intensity": 1.5,
            "color_temp": 3500,
            "angle": (-40, 15, 0),
            "shadow_density": 0.75,
        },
        "rim": {
            "intensity": 1.0,
            "color_temp": 4000,
            "angle": (-15, -135, 0),
        },
        "fill": {
            "intensity": 0.4,
            "color_temp": 3800,
        },
        "practicals": {
            "type": "area_light",
            "count": 4,
            "distribution": "background",
            "color_temp": 3500,
        },
        "volumetric": {
            "enabled": True,
            "density": 0.02,
            "color": [1.0, 0.9, 0.7],
        },
        "renderer_hints": {
            "arnold": {"exposure": -0.2, "samples": 3},
            "karma":  {"path_trace_samples": 256},
        },
    },
}

_DEFAULT_STYLE = "cinematic_industrial"


# ---------------------------------------------------------------------------
# Engine class
# ---------------------------------------------------------------------------


class SemanticLightingEngine:
    """
    Generates production-aware cinematic lighting orchestration plans.
    All output is planning data — no Houdini state is mutated.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._plan_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_lighting_plan(
        self,
        zones: Dict[str, Any],
        style: Optional[str] = None,
        scene_theme: str = "",
    ) -> Dict[str, Any]:
        """
        Generate a complete cinematic lighting plan.

        Unknown style falls back to _DEFAULT_STYLE.

        Returns:
            {
                plan_id:            str,
                lighting_style:     str,
                scene_theme:        str,
                key_strategy:       dict,
                rim_strategy:       dict,
                practical_lighting: dict,
                volumetric:         dict,
                renderer_hints:     dict,
                balance:            dict,
                operations:         list,
                generated_at:       float,
            }
        """
        resolved_style = style if style in _LIGHTING_PRESETS else _DEFAULT_STYLE
        preset = _LIGHTING_PRESETS[resolved_style]

        key_strategy = self.build_key_light_strategy(resolved_style, zones)
        rim_strategy = self.build_rim_light_strategy(resolved_style, zones)
        practical = self.build_practical_lighting(scene_theme, zones)
        volumetric = self.build_volumetric_lighting(preset["volumetric"])
        renderer_hints = dict(preset["renderer_hints"])

        # Build balance eval from the raw intensities
        _balance_input = {
            "key":  {"intensity": preset["key"]["intensity"]},
            "rim":  {"intensity": preset["rim"]["intensity"]},
            "fill": {"intensity": preset["fill"]["intensity"]},
        }
        balance = self.evaluate_light_balance(_balance_input)

        operations = self._build_light_operations(
            resolved_style, key_strategy, rim_strategy, practical, volumetric
        )

        with self._lock:
            self._plan_count += 1

        return {
            "plan_id":            str(uuid.uuid4()),
            "lighting_style":     resolved_style,
            "scene_theme":        scene_theme,
            "key_strategy":       key_strategy,
            "rim_strategy":       rim_strategy,
            "practical_lighting": practical,
            "volumetric":         volumetric,
            "renderer_hints":     renderer_hints,
            "balance":            balance,
            "operations":         operations,
            "generated_at":       time.time(),
        }

    def build_key_light_strategy(
        self,
        style: str,
        zones: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build the key light strategy dict.

        Returns the preset key dict augmented with:
            name:        "key_light"
            type:        "hlight::2.0"
            parent:      "/obj/lighting"
            target_zone: "hero_area" if hero_area is populated, else "midground"

        Falls back to _DEFAULT_STYLE for unknown style.
        """
        resolved_style = style if style in _LIGHTING_PRESETS else _DEFAULT_STYLE
        preset_key = dict(_LIGHTING_PRESETS[resolved_style]["key"])

        hero_assets = zones.get("hero_area", [])
        target_zone = "hero_area" if hero_assets else "midground"

        preset_key["name"] = "key_light"
        preset_key["type"] = "hlight::2.0"
        preset_key["parent"] = "/obj/lighting"
        preset_key["target_zone"] = target_zone

        return preset_key

    def build_rim_light_strategy(
        self,
        style: str,
        zones: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build the rim light strategy dict.

        Returns the preset rim dict augmented with:
            name:   "rim_light"
            type:   "hlight::2.0"
            parent: "/obj/lighting"

        Falls back to _DEFAULT_STYLE for unknown style.
        """
        resolved_style = style if style in _LIGHTING_PRESETS else _DEFAULT_STYLE
        preset_rim = dict(_LIGHTING_PRESETS[resolved_style]["rim"])

        preset_rim["name"] = "rim_light"
        preset_rim["type"] = "hlight::2.0"
        preset_rim["parent"] = "/obj/lighting"

        return preset_rim

    def build_practical_lighting(
        self,
        scene_theme: str,
        zones: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build the practical lighting configuration.

        Uses _DEFAULT_STYLE practicals as the base.  scene_theme is recorded
        in the returned dict but does not alter the preset values in Tier 4.

        Returns:
            {
                type:         str,
                count:        int,
                distribution: str,
                color_temp:   int,
                scene_theme:  str,
                parent:       "/obj/lighting",
            }
        """
        practicals = dict(_LIGHTING_PRESETS[_DEFAULT_STYLE]["practicals"])
        return {
            "type":         practicals["type"],
            "count":        practicals["count"],
            "distribution": practicals["distribution"],
            "color_temp":   practicals["color_temp"],
            "scene_theme":  scene_theme,
            "parent":       "/obj/lighting",
        }

    def build_volumetric_lighting(
        self,
        volumetric_settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build the volumetric lighting configuration.

        Returns:
            {
                enabled: bool,
                density: float,
                color:   list,
                type:    "envlight" if enabled else None,
                parent:  "/obj/lighting",
            }
        """
        enabled = bool(volumetric_settings.get("enabled", False))
        return {
            "enabled": enabled,
            "density": float(volumetric_settings.get("density", 0.0)),
            "color":   list(volumetric_settings.get("color", [1.0, 1.0, 1.0])),
            "type":    "envlight" if enabled else None,
            "parent":  "/obj/lighting",
        }

    def evaluate_light_balance(
        self,
        lighting_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate the three-point lighting balance.

        lighting_plan must contain "key", "rim", and "fill" dicts each with
        an "intensity" key.

        Scoring:
        - rim intensity >= key intensity  → issue: hero loses separation
        - fill intensity > key * 0.5      → issue: depth flattened
        - balance_score = min(1.0, key_ratio * 1.5)
          where key_ratio = key_intensity / total
        - If total == 0: balance_score = 0.0

        Returns:
            {
                balanced:       bool,
                balance_score:  float 0.0–1.0,
                issues:         list[str],
                key_intensity:  float,
                rim_intensity:  float,
                fill_intensity: float,
            }
        """
        issues: List[str] = []

        key_intensity = float(
            lighting_plan.get("key", {}).get("intensity", 0.0)
        )
        rim_intensity = float(
            lighting_plan.get("rim", {}).get("intensity", 0.0)
        )
        fill_intensity = float(
            lighting_plan.get("fill", {}).get("intensity", 0.0)
        )

        total = key_intensity + rim_intensity + fill_intensity

        if total == 0.0:
            balance_score = 0.0
        else:
            key_ratio = key_intensity / total
            balance_score = min(1.0, key_ratio * 1.5)

        if rim_intensity >= key_intensity:
            issues.append(
                "Rim light intensity matches or exceeds key — hero loses separation."
            )

        if key_intensity > 0.0 and fill_intensity > key_intensity * 0.5:
            issues.append("Fill too bright — depth flattened.")
        elif key_intensity == 0.0 and fill_intensity > 0.0:
            issues.append("Fill too bright — depth flattened.")

        return {
            "balanced":       len(issues) == 0,
            "balance_score":  round(balance_score, 3),
            "issues":         issues,
            "key_intensity":  key_intensity,
            "rim_intensity":  rim_intensity,
            "fill_intensity": fill_intensity,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"plan_count": self._plan_count}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_light_operations(
        self,
        style: str,
        key_strategy: Dict[str, Any],
        rim_strategy: Dict[str, Any],
        practicals: Dict[str, Any],
        volumetric: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Generate ordered transaction op dicts for the lighting rig.

        Order:
        1. create key_light node
        2. set_parms on key_light (rx, ry, light_intensity)
        3. create rim_light node
        4. set_parms on rim_light (rx, ry, light_intensity)
        5. If volumetric enabled: create vol_env envlight node
        6. layout_children on /obj/lighting
        """
        ops: List[Dict[str, Any]] = []

        # Key light
        ops.append({
            "op":     "create_node",
            "parent": "/obj/lighting",
            "type":   "hlight::2.0",
            "name":   "key_light",
        })
        key_angle = key_strategy.get("angle", (0, 0, 0))
        ops.append({
            "op":   "set_parms",
            "node": "/obj/lighting/key_light",
            "parms": {
                "rx":              key_angle[0],
                "ry":              key_angle[1],
                "light_intensity": key_strategy.get("intensity", 1.0),
            },
        })

        # Rim light
        ops.append({
            "op":     "create_node",
            "parent": "/obj/lighting",
            "type":   "hlight::2.0",
            "name":   "rim_light",
        })
        rim_angle = rim_strategy.get("angle", (0, 0, 0))
        ops.append({
            "op":   "set_parms",
            "node": "/obj/lighting/rim_light",
            "parms": {
                "rx":              rim_angle[0],
                "ry":              rim_angle[1],
                "light_intensity": rim_strategy.get("intensity", 1.0),
            },
        })

        # Volumetric envlight
        if volumetric.get("enabled", False):
            ops.append({
                "op":     "create_node",
                "parent": "/obj/lighting",
                "type":   "envlight",
                "name":   "vol_env",
            })

        # Layout
        ops.append({
            "op":   "layout_children",
            "path": "/obj/lighting",
        })

        return ops


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[SemanticLightingEngine] = None
_LOCK = threading.Lock()


def get_semantic_lighting_engine() -> SemanticLightingEngine:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = SemanticLightingEngine()
        return _INSTANCE


def reset_semantic_lighting_engine_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
