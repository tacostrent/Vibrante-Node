"""
Composition Planner (Tier 7 — Scene Planning Runtime)
======================================================
Generates CompositionRule objects from a SceneIntent and its zone list.

Rules are procedural and inspectable — no AI-generated prose.
Every rule includes a description explaining WHY it applies to this scene.

DESIGN RULES:
  - No bridge calls. No LLM calls.
  - Deterministic: same intent + zones → same rules.
  - All rules have named types from COMPOSITION_RULE_TYPES.
  - camera_safe_zone is always included as a baseline rule.

Public API:
    CompositionPlanner
        .plan_composition(intent, zones) -> List[CompositionRule]
    get_composition_planner() -> CompositionPlanner   (singleton)
    reset_composition_planner_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.planning.schema.scene_plan import CompositionRule

# ---------------------------------------------------------------------------
# Rule templates: (rule_type, applies_to, base_priority, description_template)
# ---------------------------------------------------------------------------

_STYLE_RULES: Dict[str, List[Tuple[str, str, float, str]]] = {
    "cinematic": [
        ("layered_depth",     "full_scene", 0.95,
         "Cinematic style demands clear foreground/midground/background depth separation."),
        ("rule_of_thirds",    "full_scene", 0.85,
         "Cinematic framing uses rule of thirds to place the primary subject off-center."),
    ],
    "noir": [
        ("high_contrast",     "full_scene", 0.90,
         "Noir style requires strong light/shadow contrast as the primary visual language."),
        ("shadow_framing",    "foreground", 0.85,
         "Noir silhouetting frames subjects with deep foreground shadows."),
        ("leading_lines",     "full_scene", 0.75,
         "Noir environments use architectural lines to guide the eye to focal points."),
    ],
    "sci_fi": [
        ("geometric_lines",   "full_scene", 0.85,
         "Sci-fi environments use strong geometric lines and angular structures."),
        ("perspective_convergence", "midground", 0.80,
         "Sci-fi corridors and structures create converging perspective lines."),
    ],
    "photorealistic": [
        ("horizon_rule",      "full_scene", 0.80,
         "Photorealistic scenes need a clear horizon reference for depth calibration."),
    ],
    "stylized": [
        ("asymmetric_balance", "full_scene", 0.75,
         "Stylized scenes use deliberate asymmetric balance for visual interest."),
    ],
    "abstract": [
        ("asymmetric_balance", "full_scene", 0.80,
         "Abstract scenes leverage asymmetric balance as a primary compositional device."),
        ("depth_of_field_guidance", "full_scene", 0.75,
         "Abstract scenes guide depth through selective focus areas."),
    ],
    "fantasy": [
        ("layered_depth",     "full_scene", 0.85,
         "Fantasy environments use depth layering to create a sense of epic scale."),
        ("leading_lines",     "full_scene", 0.75,
         "Fantasy environments use natural leading lines (rivers, paths) to guide the viewer."),
    ],
    "documentary": [
        ("horizon_rule",      "full_scene", 0.85,
         "Documentary framing maintains a clear horizon for spatial grounding."),
        ("rule_of_thirds",    "full_scene", 0.80,
         "Documentary style uses rule of thirds for naturalistic framing."),
    ],
}

_MOOD_RULES: Dict[str, List[Tuple[str, str, float, str]]] = {
    "dramatic": [
        ("hero_focal_point",       "full_scene", 0.95,
         "Dramatic mood demands a single dominant hero focal point for maximum impact."),
        ("silhouette_preservation", "background", 0.85,
         "Dramatic scenes preserve strong silhouettes against the background for contrast."),
    ],
    "tense": [
        ("tension_diagonal",       "full_scene", 0.85,
         "Tense scenes use diagonal compositions to create visual unease."),
        ("silhouette_preservation", "background", 0.80,
         "Tension is amplified by strong silhouettes in background elements."),
    ],
    "peaceful": [
        ("symmetric_balance",      "full_scene", 0.80,
         "Peaceful scenes benefit from symmetric or near-symmetric balance."),
        ("horizon_rule",           "full_scene", 0.75,
         "Peaceful scenes use a clear, calm horizon as a compositional anchor."),
    ],
    "chaotic": [
        ("tension_diagonal",       "full_scene", 0.90,
         "Chaotic mood amplifies instability with strong diagonal compositions."),
        ("asymmetric_balance",     "full_scene", 0.85,
         "Chaos is visually expressed through deliberate asymmetric imbalance."),
    ],
    "melancholic": [
        ("symmetric_balance",      "full_scene", 0.75,
         "Melancholic scenes use near-symmetric balance to convey stillness."),
        ("layered_depth",          "full_scene", 0.70,
         "Melancholic depth uses layered distance to evoke loneliness."),
    ],
    "triumphant": [
        ("hero_focal_point",       "full_scene", 0.90,
         "Triumphant mood places the hero element prominently at a focal point."),
        ("leading_lines",          "full_scene", 0.80,
         "Triumphant compositions use converging lines to draw attention to the hero."),
    ],
    "ominous": [
        ("silhouette_preservation", "background", 0.90,
         "Ominous scenes preserve threatening silhouettes in the background."),
        ("high_contrast",          "full_scene", 0.85,
         "Ominous atmosphere is reinforced by high-contrast lighting ratios."),
        ("shadow_framing",         "foreground", 0.80,
         "Ominous foregrounds use shadow framing to create a sense of enclosure."),
    ],
    "neutral": [
        ("rule_of_thirds", "full_scene", 0.70,
         "Neutral scenes use standard rule of thirds for competent framing."),
    ],
}

_ZONE_RULES: Dict[int, List[Tuple[str, str, float, str]]] = {
    2: [
        ("layered_depth", "full_scene", 0.75,
         "Two-zone scene benefits from layered depth to create separation."),
    ],
    3: [
        ("layered_depth", "full_scene", 0.90,
         "Three-zone scene requires explicit depth layering for visual clarity."),
        ("depth_of_field_guidance", "full_scene", 0.75,
         "Three-zone depth is reinforced by depth-of-field focus guidance."),
    ],
}

_BASELINE_RULES: List[Tuple[str, str, float, str]] = [
    ("camera_safe_zone", "full_scene", 0.60,
     "Camera safe zone ensures no critical elements are placed at screen edges."),
]


class CompositionPlanner:
    """Generates CompositionRule objects from a SceneIntent and its zone list."""

    def plan_composition(self, intent: Any, zones: List[Any]) -> List[CompositionRule]:
        """Return composition rules for the given intent and zones.

        Args:
            intent: A SceneIntent (or duck-typed object with .style, .mood).
            zones:  List of SceneZonePlan objects.

        Returns:
            Deduplicated list of :class:`CompositionRule`, sorted by priority desc.
        """
        style = (getattr(intent, "style", None) or "").lower()
        mood  = (getattr(intent, "mood", None) or "").lower()

        raw: List[Tuple[str, str, float, str]] = []

        # Style-based rules
        raw.extend(_STYLE_RULES.get(style, []))

        # Mood-based rules
        raw.extend(_MOOD_RULES.get(mood, []))

        # Zone-count rules
        n_zones = len(zones)
        for min_count, zone_rules in _ZONE_RULES.items():
            if n_zones >= min_count:
                raw.extend(zone_rules)

        # Baseline (always present)
        raw.extend(_BASELINE_RULES)

        # Deduplicate by rule_type (first occurrence wins — highest priority first)
        seen: set = set()
        rules: List[CompositionRule] = []
        for rule_type, applies_to, priority, description in raw:
            if rule_type not in seen:
                seen.add(rule_type)
                rules.append(CompositionRule(
                    rule_type=rule_type,
                    description=description,
                    applies_to=applies_to,
                    priority=priority,
                ))

        return sorted(rules, key=lambda r: r.priority, reverse=True)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[CompositionPlanner] = None
_INSTANCE_LOCK = threading.Lock()


def get_composition_planner() -> CompositionPlanner:
    """Return the module-level singleton CompositionPlanner."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = CompositionPlanner()
    return _INSTANCE


def reset_composition_planner_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
