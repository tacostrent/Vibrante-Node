"""
Environment Rules (Tier 2 — Semantic Scene Assembly)
========================================================
Environment-specific orchestration rules for scene layout planning.

Rules define how assets should be arranged in a given environment type.
No bridge calls, no I/O, no LLM.  Pure deterministic rule tables.

Public API:
    get_environment_rules() -> EnvironmentRules     (singleton)
    reset_environment_rules_for_tests()

    EnvironmentRules.get_rules(environment) -> dict
    EnvironmentRules.get_supported_environments() -> list[str]
    EnvironmentRules.apply_rules(environment, layout_plan) -> dict
    EnvironmentRules.get_lighting_recommendation(environment) -> str
    EnvironmentRules.get_fx_recommendation(environment) -> list[str]
    EnvironmentRules.register_environment(environment_id, rules) -> None
    EnvironmentRules.stats() -> dict
"""

import threading
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Built-in environment rule table
# ---------------------------------------------------------------------------

_ENVIRONMENT_RULES: Dict[str, Dict[str, Any]] = {
    "industrial_hangar": {
        "hero_zone": "center",
        "asset_placements": {
            "machinery":  "midground",
            "vehicle":    "hero_area",
            "pipes":      "walls",
            "containers": "background",
            "tools":      "midground",
            "lights":     "upper_edges",
            "structure":  "background",
            "character":  "hero_area",
        },
        "lighting_style":    "practical_industrial",
        "fog_density":       "medium",
        "camera_hints":      ["low_angle_hero", "wide_establishing", "detail_closeup"],
        "fx_recommendations": ["volumetric_fog", "dust_particles", "light_shafts"],
        "depth_layers":      ["hero_area", "midground", "background", "ceiling"],
        "scale":             "large",
        "atmosphere":        "industrial",
    },
    "sci_fi_corridor": {
        "hero_zone": "center_path",
        "asset_placements": {
            "tech_panel": "walls",
            "pipes":      "ceiling",
            "lights":     "walls",
            "character":  "hero_area",
            "vehicle":    "background",
            "container":  "sides",
            "door":       "background",
            "structure":  "walls",
        },
        "lighting_style":    "neon_accent",
        "fog_density":       "light",
        "camera_hints":      ["perspective_corridor", "tracking_shot", "over_shoulder"],
        "fx_recommendations": ["neon_glow", "steam_vents", "holographic_displays"],
        "depth_layers":      ["hero_area", "mid_corridor", "end_point"],
        "scale":             "medium",
        "atmosphere":        "sci_fi",
    },
    "abandoned_factory": {
        "hero_zone": "center",
        "asset_placements": {
            "machinery": "midground",
            "debris":    "foreground",
            "structure": "background",
            "pipes":     "ceiling",
            "container": "midground",
            "vehicle":   "background",
            "character": "hero_area",
        },
        "lighting_style":    "natural_decay",
        "fog_density":       "heavy",
        "camera_hints":      ["dutch_angle", "low_angle_hero", "wide_desolation"],
        "fx_recommendations": ["dust_motes", "falling_debris", "rust_particles", "volumetric_light"],
        "depth_layers":      ["foreground_debris", "hero_area", "midground_machinery", "collapsed_background"],
        "scale":             "large",
        "atmosphere":        "post_apocalyptic",
    },
    "robotics_lab": {
        "hero_zone": "workbench_center",
        "asset_placements": {
            "tech_panel": "walls",
            "machinery":  "midground",
            "character":  "hero_area",
            "vehicle":    "background",
            "tools":      "hero_area",
            "container":  "sides",
            "lights":     "ceiling",
            "structure":  "walls",
        },
        "lighting_style":    "clean_white",
        "fog_density":       "none",
        "camera_hints":      ["overhead_diagnostic", "eye_level_work", "detail_closeup"],
        "fx_recommendations": ["holographic_ui", "arc_sparks", "servo_dust"],
        "depth_layers":      ["workbench_hero", "equipment_mid", "storage_background"],
        "scale":             "medium",
        "atmosphere":        "technical",
    },
    "cinematic_control_room": {
        "hero_zone": "central_console",
        "asset_placements": {
            "tech_panel": "hero_area",
            "lights":     "ceiling",
            "character":  "hero_area",
            "structure":  "walls",
            "container":  "background",
            "vehicle":    "background",
        },
        "lighting_style":    "dramatic_screen_glow",
        "fog_density":       "none",
        "camera_hints":      ["low_hero_angle", "wide_console_shot", "over_shoulder_screens"],
        "fx_recommendations": ["screen_glow", "holographic_displays", "warning_lights"],
        "depth_layers":      ["console_hero", "operator_mid", "screen_background"],
        "scale":             "medium",
        "atmosphere":        "command_tension",
    },
}

_DEFAULT_RULES: Dict[str, Any] = {
    "hero_zone":          "center",
    "asset_placements":   {},
    "lighting_style":     "natural",
    "fog_density":        "none",
    "camera_hints":       ["establishing_shot", "hero_closeup"],
    "fx_recommendations": [],
    "depth_layers":       ["hero_area", "midground", "background"],
    "scale":              "medium",
    "atmosphere":         "neutral",
}


class EnvironmentRules:
    """Environment-specific orchestration rule library.

    All methods are deterministic and require no bridge or LLM calls.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: Dict[str, Dict[str, Any]] = {
            k: dict(v) for k, v in _ENVIRONMENT_RULES.items()
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_supported_environments(self) -> List[str]:
        """Return sorted list of all registered environment ids."""
        with self._lock:
            return sorted(self._rules.keys())

    def get_rules(self, environment: str) -> Dict[str, Any]:
        """Return a copy of the rules dict for the given environment.

        Falls back to _DEFAULT_RULES for unknown environments.
        """
        with self._lock:
            return dict(self._rules.get(environment, _DEFAULT_RULES))

    def apply_rules(
        self,
        environment: str,
        layout_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply environment rules onto an existing layout plan dict.

        Returns a new dict — does NOT mutate the input.
        """
        rules = self.get_rules(environment)
        plan  = dict(layout_plan)
        plan["environment"] = environment

        layout_rules = dict(plan.get("layout_rules", {}))
        layout_rules["hero_focus"]     = rules["hero_zone"]
        layout_rules["fog_density"]    = rules["fog_density"]
        layout_rules["lighting_style"] = rules["lighting_style"]
        layout_rules["atmosphere"]     = rules["atmosphere"]
        layout_rules["scale"]          = rules["scale"]
        plan["layout_rules"] = layout_rules

        plan["recommended_fx"]    = list(rules["fx_recommendations"])
        plan["camera_hints"]      = list(rules["camera_hints"])
        plan["depth_layers"]      = list(rules["depth_layers"])
        plan["asset_placements"]  = dict(rules["asset_placements"])
        return plan

    def get_lighting_recommendation(self, environment: str) -> str:
        """Return the lighting style string for an environment."""
        return self.get_rules(environment).get("lighting_style", "natural")

    def get_fx_recommendation(self, environment: str) -> List[str]:
        """Return the list of recommended FX types for an environment."""
        return list(self.get_rules(environment).get("fx_recommendations", []))

    def register_environment(
        self,
        environment_id: str,
        rules: Dict[str, Any],
    ) -> None:
        """Register or overwrite an environment rule set."""
        with self._lock:
            self._rules[environment_id] = dict(rules)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"environment_count": len(self._rules)}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentRules] = None
_LOCK = threading.Lock()


def get_environment_rules() -> EnvironmentRules:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = EnvironmentRules()
        return _INSTANCE


def reset_environment_rules_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
