"""
Environment Structural Affinity (Tier 10.3 — Structural Asset Classification)
==============================================================================
Adjusts structural role confidence based on environment context.  If a role
is preferred for the current environment the confidence is boosted; if it is
irrelevant the confidence is capped.

No bridge calls. Deterministic.

Public API:
    EnvironmentStructuralAffinity
    get_environment_structural_affinity()
    reset_environment_structural_affinity_for_tests()
"""

from __future__ import annotations

import threading
from typing import Dict, FrozenSet, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Affinity tables — (preferred roles, irrelevant roles) per environment
# ──────────────────────────────────────────────────────────────────────────────

# Format: env_name → {"preferred": [...], "irrelevant": [...]}
_ENV_AFFINITY: Dict[str, Dict[str, List[str]]] = {
    "western_room": {
        "preferred":   ["doorway", "beam", "fireplace", "wall_segment", "floor_piece",
                        "door_frame", "railing", "stair"],
        "irrelevant":  ["window_frame", "ceiling_piece", "archway"],
    },
    "saloon": {
        "preferred":   ["doorway", "beam", "fireplace", "wall_segment", "floor_piece",
                        "door_frame", "railing", "stair"],
        "irrelevant":  ["archway", "ceiling_piece"],
    },
    "living_room": {
        "preferred":   ["doorway", "window", "window_frame", "floor_piece",
                        "fireplace", "door_frame"],
        "irrelevant":  ["beam", "column", "archway"],
    },
    "office": {
        "preferred":   ["doorway", "window", "window_frame", "wall_segment",
                        "floor_piece", "ceiling_piece", "door_frame"],
        "irrelevant":  ["fireplace", "archway", "beam"],
    },
    "hotel_lobby": {
        "preferred":   ["doorway", "column", "archway", "stair", "railing",
                        "wall_segment", "floor_piece"],
        "irrelevant":  ["beam", "fireplace"],
    },
    "restaurant": {
        "preferred":   ["doorway", "window", "wall_segment", "floor_piece",
                        "door_frame", "window_frame"],
        "irrelevant":  ["beam", "column", "archway"],
    },
    "library": {
        "preferred":   ["doorway", "window", "wall_segment", "floor_piece",
                        "column", "archway", "railing", "stair"],
        "irrelevant":  ["fireplace", "beam"],
    },
    "industrial_hangar": {
        "preferred":   ["beam", "support_beam", "column", "wall_segment",
                        "floor_piece", "ceiling_piece", "doorway"],
        "irrelevant":  ["fireplace", "archway", "window"],
    },
    "warehouse": {
        "preferred":   ["beam", "support_beam", "column", "wall_segment",
                        "floor_piece", "doorway"],
        "irrelevant":  ["fireplace", "archway", "window"],
    },
    "abandoned_factory": {
        "preferred":   ["beam", "support_beam", "column", "wall_segment",
                        "floor_piece", "window", "doorway"],
        "irrelevant":  ["fireplace", "archway"],
    },
    "shipyard": {
        "preferred":   ["beam", "support_beam", "column", "wall_segment",
                        "floor_piece", "doorway", "railing"],
        "irrelevant":  ["fireplace", "archway"],
    },
    "robotics_lab": {
        "preferred":   ["wall_segment", "floor_piece", "ceiling_piece",
                        "door_frame", "doorway", "window"],
        "irrelevant":  ["fireplace", "archway", "beam"],
    },
    "research_lab": {
        "preferred":   ["wall_segment", "floor_piece", "ceiling_piece",
                        "doorway", "window", "door_frame"],
        "irrelevant":  ["fireplace", "archway", "beam"],
    },
    "medical_lab": {
        "preferred":   ["wall_segment", "floor_piece", "ceiling_piece",
                        "doorway", "door_frame"],
        "irrelevant":  ["fireplace", "beam", "archway"],
    },
    "control_room": {
        "preferred":   ["wall_segment", "floor_piece", "ceiling_piece",
                        "doorway", "door_frame"],
        "irrelevant":  ["fireplace", "archway", "beam"],
    },
    "sci_fi_corridor": {
        "preferred":   ["wall_segment", "ceiling_piece", "floor_piece",
                        "door_frame", "doorway"],
        "irrelevant":  ["fireplace", "archway", "beam", "column"],
    },
    "space_station": {
        "preferred":   ["wall_segment", "ceiling_piece", "floor_piece",
                        "door_frame", "doorway", "column"],
        "irrelevant":  ["fireplace", "archway", "beam"],
    },
    "castle_hall": {
        "preferred":   ["archway", "column", "fireplace", "wall_segment",
                        "floor_piece", "stair", "railing", "doorway"],
        "irrelevant":  ["ceiling_piece", "beam"],
    },
    "dungeon": {
        "preferred":   ["doorway", "archway", "column", "wall_segment",
                        "floor_piece", "stair"],
        "irrelevant":  ["fireplace", "window", "beam"],
    },
    "wizard_tower": {
        "preferred":   ["doorway", "archway", "column", "stair", "railing",
                        "wall_segment", "floor_piece"],
        "irrelevant":  ["beam", "ceiling_piece"],
    },
    "forest": {
        "preferred":   ["floor_piece"],
        "irrelevant":  ["wall_segment", "ceiling_piece", "doorway", "beam",
                        "column", "fireplace", "archway"],
    },
    "desert": {
        "preferred":   ["floor_piece"],
        "irrelevant":  ["wall_segment", "ceiling_piece", "beam", "column",
                        "archway", "fireplace"],
    },
    "city_street": {
        "preferred":   ["doorway", "window", "wall_segment", "floor_piece",
                        "archway", "column", "railing", "stair"],
        "irrelevant":  ["fireplace", "ceiling_piece"],
    },
    "survival_camp": {
        "preferred":   ["floor_piece", "doorway"],
        "irrelevant":  ["archway", "column", "ceiling_piece", "beam"],
    },
    "military_base": {
        "preferred":   ["doorway", "wall_segment", "floor_piece", "beam",
                        "column", "door_frame"],
        "irrelevant":  ["fireplace", "archway"],
    },
}

# Boost / cap magnitudes
_PREFERRED_BOOST = 0.10
_IRRELEVANT_CAP  = 0.50


class EnvironmentStructuralAffinity:
    """
    Apply environment context to adjust structural role confidence.

    Usage:
        affinity = get_environment_structural_affinity()
        adjusted_conf = affinity.adjust(role, conf, environment)
        preferred      = affinity.preferred_roles(environment)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def adjust(
        self,
        role:        str,
        confidence:  float,
        environment: str,
    ) -> float:
        """
        Adjust confidence by environment affinity.

        Preferred roles get a +0.10 boost (capped at 1.0).
        Irrelevant roles are capped at 0.50.

        Returns adjusted confidence. Never raises.
        """
        try:
            env = environment.lower().strip() if environment else ""
            table = _ENV_AFFINITY.get(env, {})
            preferred = table.get("preferred", [])
            irrelevant = table.get("irrelevant", [])

            if role in preferred:
                return min(1.0, confidence + _PREFERRED_BOOST)
            if role in irrelevant:
                return min(confidence, _IRRELEVANT_CAP)
            return confidence
        except Exception:
            return confidence

    def preferred_roles(self, environment: str) -> List[str]:
        """Return the preferred structural roles for an environment."""
        env = environment.lower().strip() if environment else ""
        table = _ENV_AFFINITY.get(env, {})
        return list(table.get("preferred", []))

    def irrelevant_roles(self, environment: str) -> List[str]:
        """Return roles that are irrelevant for the given environment."""
        env = environment.lower().strip() if environment else ""
        table = _ENV_AFFINITY.get(env, {})
        return list(table.get("irrelevant", []))

    def supported_environments(self) -> List[str]:
        """Return all environments with registered affinity data."""
        return sorted(_ENV_AFFINITY.keys())

    def affinity_score(
        self,
        role:        str,
        environment: str,
    ) -> float:
        """
        Return a raw affinity score for (role, environment):
          +1.0 → preferred
           0.0 → neutral
          -1.0 → irrelevant
        """
        env = environment.lower().strip() if environment else ""
        table = _ENV_AFFINITY.get(env, {})
        if role in table.get("preferred", []):
            return 1.0
        if role in table.get("irrelevant", []):
            return -1.0
        return 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_INSTANCE: Optional[EnvironmentStructuralAffinity] = None
_LOCK = threading.Lock()


def get_environment_structural_affinity() -> EnvironmentStructuralAffinity:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = EnvironmentStructuralAffinity()
        return _INSTANCE


def reset_environment_structural_affinity_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
