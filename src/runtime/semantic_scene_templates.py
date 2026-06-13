"""
Semantic Scene Templates (Tier 2 — Semantic Scene Assembly)
=============================================================
Reusable production scene orchestration templates.

Each template encodes:
  - scene intent
  - preferred asset categories
  - lighting style
  - composition logic
  - FX layers
  - camera logic
  - renderer preferences

Built-in templates (cannot be deregistered):
    cinematic_industrial_hangar
    robotics_repair_facility
    atmospheric_scifi_corridor
    cinematic_control_room

Public API:
    get_semantic_scene_templates() -> SemanticSceneTemplates  (singleton)
    reset_semantic_scene_templates_for_tests()

    SemanticSceneTemplates.list_templates(tag=None) -> list[dict]
    SemanticSceneTemplates.get_template(template_id) -> dict | None
    SemanticSceneTemplates.apply_template(template_id, context) -> dict
    SemanticSceneTemplates.register_template(template_id, template) -> None
    SemanticSceneTemplates.deregister_template(template_id) -> bool
    SemanticSceneTemplates.stats() -> dict
"""

import re
import threading
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------

_BUILTIN_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "cinematic_industrial_hangar": {
        "id":          "cinematic_industrial_hangar",
        "name":        "Cinematic Industrial Hangar",
        "description": (
            "Large-scale industrial hangar with atmospheric volumetrics "
            "and hero machinery."
        ),
        "tags":        ["industrial", "cinematic", "large", "fx"],
        "scene_intent":               "cinematic_industrial_staging",
        "environment":                "industrial_hangar",
        "preferred_asset_categories": [
            "vehicle", "machinery", "container", "pipes", "structure", "tools"
        ],
        "lighting_style": "practical_industrial",
        "lighting_notes": (
            "Mixed practicals with high-contrast shadow pools. "
            "Shaft lights from skylights."
        ),
        "composition_logic": {
            "hero_placement":   "center_low",
            "depth_layers":     3,
            "frame_elements":   ["foreground_pipes", "midground_machinery", "background_structure"],
            "negative_space":   "above_hero",
        },
        "fx_layers": [
            {"type": "volumetric_fog",  "density": "medium", "priority": 1},
            {"type": "dust_particles",  "density": "light",  "priority": 2},
            {"type": "light_shafts",    "density": "medium", "priority": 3},
        ],
        "camera_logic": {
            "primary_shot":       "low_angle_hero",
            "secondary_shot":     "wide_establishing",
            "depth_of_field":     True,
            "focal_length_hint":  "50mm",
        },
        "renderer_preferences": {
            "preferred":    ["arnold", "karma"],
            "min_samples":  128,
            "motion_blur":  True,
        },
        "production_notes": "Allow 2–3 hrs render time per frame at 4K. Pre-cache volumetrics.",
        "tags_semantic": ["moody", "scale", "machinery", "atmospheric"],
    },

    "robotics_repair_facility": {
        "id":          "robotics_repair_facility",
        "name":        "Robotics Repair Facility",
        "description": (
            "Precision technical environment for robotic work scenes "
            "with holographic UI."
        ),
        "tags":        ["technical", "sci_fi", "interior", "clean"],
        "scene_intent":               "technical_workspace_staging",
        "environment":                "robotics_lab",
        "preferred_asset_categories": [
            "robot", "tech_panel", "tools", "machinery", "container", "character"
        ],
        "lighting_style": "clean_white",
        "lighting_notes": (
            "Cool fluorescent overhead with accent blues. "
            "No shadows over the workbench."
        ),
        "composition_logic": {
            "hero_placement":   "workbench_center",
            "depth_layers":     2,
            "frame_elements":   ["foreground_tools", "hero_robot", "background_equipment"],
            "negative_space":   "above_workbench",
        },
        "fx_layers": [
            {"type": "holographic_ui", "density": "medium", "priority": 1},
            {"type": "arc_sparks",     "density": "light",  "priority": 2},
        ],
        "camera_logic": {
            "primary_shot":       "eye_level_work",
            "secondary_shot":     "overhead_diagnostic",
            "depth_of_field":     False,
            "focal_length_hint":  "35mm",
        },
        "renderer_preferences": {
            "preferred":   ["arnold", "karma"],
            "min_samples": 64,
            "motion_blur": False,
        },
        "production_notes": "Clean grade. Keep practicals sharp. Holographic layers in comp.",
        "tags_semantic": ["precision", "technical", "clean", "robotic"],
    },

    "atmospheric_scifi_corridor": {
        "id":          "atmospheric_scifi_corridor",
        "name":        "Atmospheric Sci-Fi Corridor",
        "description": (
            "Moody sci-fi corridor with neon accent lights and "
            "volumetric steam vents."
        ),
        "tags":        ["sci_fi", "corridor", "atmospheric", "neon"],
        "scene_intent":               "corridor_traversal_staging",
        "environment":                "sci_fi_corridor",
        "preferred_asset_categories": [
            "tech_panel", "pipes", "lights", "character", "door", "container"
        ],
        "lighting_style": "neon_accent",
        "lighting_notes": "Mixed cool/warm neon practicals. Strong RIM on character.",
        "composition_logic": {
            "hero_placement":   "center_path",
            "depth_layers":     3,
            "frame_elements":   ["foreground_pipes", "hero_character", "corridor_vanishing_point"],
            "negative_space":   "corridor_ceiling",
        },
        "fx_layers": [
            {"type": "neon_glow",            "density": "medium", "priority": 1},
            {"type": "steam_vents",          "density": "light",  "priority": 2},
            {"type": "holographic_displays", "density": "light",  "priority": 3},
        ],
        "camera_logic": {
            "primary_shot":       "perspective_corridor",
            "secondary_shot":     "tracking_shot",
            "depth_of_field":     True,
            "focal_length_hint":  "28mm",
        },
        "renderer_preferences": {
            "preferred":   ["arnold", "karma", "redshift"],
            "min_samples": 96,
            "motion_blur": True,
        },
        "production_notes": (
            "Strong perspective lines are key to composition. Keep corridor long."
        ),
        "tags_semantic": ["moody", "cyberpunk", "atmospheric", "corridor"],
    },

    "cinematic_control_room": {
        "id":          "cinematic_control_room",
        "name":        "Cinematic Control Room",
        "description": (
            "Dramatic command and control environment with "
            "multi-screen display banks."
        ),
        "tags":        ["command", "dramatic", "screens", "tension"],
        "scene_intent":               "command_environment_staging",
        "environment":                "cinematic_control_room",
        "preferred_asset_categories": [
            "tech_panel", "character", "lights", "structure", "container"
        ],
        "lighting_style": "dramatic_screen_glow",
        "lighting_notes": "Screen glow dominant. Practicals at workstations. Dramatic shadows.",
        "composition_logic": {
            "hero_placement":   "central_console_low",
            "depth_layers":     2,
            "frame_elements":   ["foreground_console", "hero_operator", "screen_background"],
            "negative_space":   "screen_bank_above",
        },
        "fx_layers": [
            {"type": "screen_glow",          "density": "high",   "priority": 1},
            {"type": "holographic_displays", "density": "medium", "priority": 2},
            {"type": "warning_lights",       "density": "light",  "priority": 3},
        ],
        "camera_logic": {
            "primary_shot":       "low_hero_angle",
            "secondary_shot":     "over_shoulder_screens",
            "depth_of_field":     False,
            "focal_length_hint":  "40mm",
        },
        "renderer_preferences": {
            "preferred":   ["arnold", "mantra"],
            "min_samples": 96,
            "motion_blur": False,
        },
        "production_notes": "Practical screen content critical. Time camera to operator beats.",
        "tags_semantic": ["dramatic", "tense", "command", "screens"],
    },
}

# Fields required in any user-registered template
_REQUIRED_FIELDS = frozenset({
    "scene_intent",
    "environment",
    "preferred_asset_categories",
    "lighting_style",
    "fx_layers",
    "camera_logic",
})


class SemanticSceneTemplates:
    """Registry of production scene orchestration templates.

    Built-in templates cannot be deregistered.
    All methods are deterministic.  No I/O, no bridge calls, no LLM.
    """

    def __init__(self) -> None:
        self._lock        = threading.Lock()
        self._templates: Dict[str, Dict[str, Any]] = {
            k: dict(v) for k, v in _BUILTIN_TEMPLATES.items()
        }
        self._builtin_ids = frozenset(_BUILTIN_TEMPLATES.keys())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_templates(
        self,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return summary dicts for all templates, optionally filtered by tag.

        Returns:
            [{id, name, description, tags, environment, scene_intent}, ...]
        """
        with self._lock:
            results = []
            for tid, tmpl in sorted(self._templates.items()):
                all_tags = tmpl.get("tags", []) + tmpl.get("tags_semantic", [])
                if tag and tag not in all_tags:
                    continue
                results.append({
                    "id":           tid,
                    "name":         tmpl.get("name",         tid),
                    "description":  tmpl.get("description",  ""),
                    "tags":         list(tmpl.get("tags",    [])),
                    "environment":  tmpl.get("environment",  ""),
                    "scene_intent": tmpl.get("scene_intent", ""),
                })
            return results

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the full template dict, or None if not found."""
        with self._lock:
            tmpl = self._templates.get(template_id)
            return dict(tmpl) if tmpl else None

    def apply_template(
        self,
        template_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply a template with {variable} interpolation.

        Args:
            template_id:  Registered template id.
            context:      Dict of variable_name → value for substitution.

        Returns:
            Fully resolved template dict.

        Raises:
            KeyError:   If template_id is not registered.
            ValueError: If a required context variable is missing.
        """
        tmpl = self.get_template(template_id)
        if tmpl is None:
            raise KeyError(f"Template not found: {template_id!r}")
        return _interpolate(tmpl, context)

    def register_template(
        self,
        template_id: str,
        template: Dict[str, Any],
    ) -> None:
        """Register a custom template.

        Args:
            template_id:  Unique identifier.
            template:     Template dict; must contain all _REQUIRED_FIELDS.

        Raises:
            ValueError: If required fields are missing.
        """
        missing = _REQUIRED_FIELDS - set(template.keys())
        if missing:
            raise ValueError(
                f"Template missing required fields: {sorted(missing)}"
            )
        with self._lock:
            entry = dict(template)
            entry["id"] = template_id
            self._templates[template_id] = entry

    def deregister_template(self, template_id: str) -> bool:
        """Remove a user-registered template.

        Returns True if removed; False if not found.
        Raises ValueError for built-in templates.
        """
        if template_id in self._builtin_ids:
            raise ValueError(
                f"Cannot deregister built-in template: {template_id!r}"
            )
        with self._lock:
            if template_id in self._templates:
                del self._templates[template_id]
                return True
            return False

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_templates":  len(self._templates),
                "builtin_count":    len(self._builtin_ids),
                "custom_count":     len(self._templates) - len(self._builtin_ids),
            }


# ---------------------------------------------------------------------------
# Interpolation helper
# ---------------------------------------------------------------------------

def _interpolate(obj: Any, context: Dict[str, Any]) -> Any:
    """Recursively substitute {varname} placeholders in string values."""
    if isinstance(obj, str):
        placeholders = re.findall(r"\{(\w+)\}", obj)
        for ph in placeholders:
            if ph not in context:
                raise ValueError(
                    f"Template variable '{{{ph}}}' not provided. "
                    f"Provided keys: {sorted(context.keys())}"
                )
        return obj.format(**{ph: context[ph] for ph in placeholders}) if placeholders else obj
    if isinstance(obj, dict):
        return {k: _interpolate(v, context) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate(item, context) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[SemanticSceneTemplates] = None
_LOCK = threading.Lock()


def get_semantic_scene_templates() -> SemanticSceneTemplates:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = SemanticSceneTemplates()
        return _INSTANCE


def reset_semantic_scene_templates_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
