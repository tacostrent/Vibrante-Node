"""
Camera Planner (Tier 7 — Scene Planning Runtime)
=================================================
Generates CameraTarget objects from a SceneIntent and its zone list.

Targets specify WHAT to aim at and WHERE to place the camera — not the actual
camera transform values. Tier 3+ scene assembly nodes convert targets into
real Houdini camera rigs.

Rule: one establishing shot is always produced (full-scene context).
      One hero target per high-priority zone (foreground/midground).
      Mood-based extras (tension track, reaction angle).

DESIGN RULES:
  - No bridge calls. No LLM calls.
  - Deterministic: same intent + zones → same targets.
  - Every target includes position_hint, look_at_hint, shot_type, importance.

Public API:
    CameraPlanner
        .plan_cameras(intent, zones) -> List[CameraTarget]
    get_camera_planner() -> CameraPlanner   (singleton)
    reset_camera_planner_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.planning.schema.scene_plan import CameraTarget

# ---------------------------------------------------------------------------
# Zone → target mapping
# (zone_type, shot_type, position_hint, look_at_hint, base_importance)
# ---------------------------------------------------------------------------

_ZONE_TARGET_MAP: Dict[str, Tuple[str, str, str, float]] = {
    "foreground":  ("detail",       "center",      "center_mass",    0.70),
    "midground":   ("hero",         "left_third",  "center_mass",    0.85),
    "background":  ("establishing", "center",      "horizon_center", 0.90),
    "overhead":    ("aerial",       "center",      "ground_center",  0.75),
    "ground":      ("detail",       "center",      "surface_detail", 0.60),
    "interior_wall": ("detail",     "right_third", "wall_feature",   0.55),
    "ceiling":     ("aerial",       "center",      "ceiling_feature",0.50),
}

# Establishing shot always present
_ESTABLISHING_TARGET: Tuple[str, str, str, str, float] = (
    "scene_overview", "establishing", "center", "scene_center_mass", 0.95
)

# Mood-based extra targets
_MOOD_EXTRA_TARGETS: Dict[str, List[Tuple[str, str, str, str, float]]] = {
    "tense": [
        ("tension_angle", "tracking", "right_third", "focal_element", 0.65),
    ],
    "dramatic": [
        ("dramatic_low_angle", "hero", "left_third", "hero_silhouette", 0.80),
    ],
    "chaotic": [
        ("chaotic_dutch_angle", "reaction", "center", "action_center", 0.70),
    ],
    "mysterious": [
        ("mystery_reveal", "tracking", "right_third", "hidden_element", 0.65),
    ],
    "triumphant": [
        ("triumph_low_angle", "hero", "center", "hero_element", 0.85),
    ],
    "ominous": [
        ("ominous_wide_angle", "establishing", "center", "threat_source", 0.75),
    ],
}

# Environment-based look-at refinements
_ENV_LOOK_AT_HINTS: Dict[str, str] = {
    "urban":       "building_facade",
    "industrial":  "machinery_cluster",
    "desert":      "horizon_silhouette",
    "forest":      "tree_canopy",
    "space":       "station_module",
    "underground": "cavern_feature",
    "interior":    "room_focal_element",
}


class CameraPlanner:
    """Generates CameraTarget list from a SceneIntent and zone list."""

    def plan_cameras(self, intent: Any, zones: List[Any]) -> List[CameraTarget]:
        """Return camera targets for the given intent and zones.

        Args:
            intent: A SceneIntent (or duck-typed object with .mood, .environment).
            zones:  List of SceneZonePlan objects.

        Returns:
            List of :class:`CameraTarget`, sorted by importance desc.
        """
        mood = (getattr(intent, "mood", None) or "").lower()
        env  = (getattr(intent, "environment", None) or "").lower()
        env_look = _ENV_LOOK_AT_HINTS.get(env, "center_mass")

        targets: List[CameraTarget] = []
        seen_names: set = set()

        # 1. Always: establishing shot (full-scene context)
        name, shot_type, pos, look_at, importance = _ESTABLISHING_TARGET
        targets.append(CameraTarget(
            name=name,
            zone="background",
            position_hint=pos,
            look_at_hint=env_look if env else look_at,
            importance=importance,
            shot_type=shot_type,
        ))
        seen_names.add(name)

        # 2. One target per zone (except background, which is establishing)
        for zone in zones:
            zt = getattr(zone, "zone_type", "")
            if zt == "background":
                continue
            tpl = _ZONE_TARGET_MAP.get(zt)
            if not tpl:
                continue
            shot_type, pos, look_at, importance = tpl
            target_name = f"{zt}_{shot_type}"
            if target_name in seen_names:
                continue
            seen_names.add(target_name)
            targets.append(CameraTarget(
                name=target_name,
                zone=zt,
                position_hint=pos,
                look_at_hint=look_at,
                importance=importance,
                shot_type=shot_type,
            ))

        # 3. Mood-based extras
        for name, shot_type, pos, look_at, importance in _MOOD_EXTRA_TARGETS.get(mood, []):
            if name not in seen_names:
                seen_names.add(name)
                targets.append(CameraTarget(
                    name=name,
                    zone="midground",
                    position_hint=pos,
                    look_at_hint=look_at,
                    importance=importance,
                    shot_type=shot_type,
                ))

        return sorted(targets, key=lambda t: t.importance, reverse=True)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[CameraPlanner] = None
_INSTANCE_LOCK = threading.Lock()


def get_camera_planner() -> CameraPlanner:
    """Return the module-level singleton CameraPlanner."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = CameraPlanner()
    return _INSTANCE


def reset_camera_planner_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
