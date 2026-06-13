"""
ceiling_builder.py — §49 Structural Environment Realization
============================================================
Generates ceiling structural elements.

Ceiling types:
  flat_ceiling      office, control_room, medical_lab, research_lab
  beam_ceiling      western_room, saloon, warehouse, workshop
  industrial_ceiling industrial_hangar, abandoned_factory
  high_ceiling      library, hotel_lobby
  arched_ceiling    castle_hall, dungeon
  vaulted_ceiling   castle_hall (large)
  sci_fi_ceiling    sci_fi_corridor, space_station
  open_sky          outdoor environments (no ceiling generated)

Public API:
    CeilingBuilder
    get_ceiling_builder()
    reset_ceiling_builder_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional, Tuple

from src.runtime.environment_realization.structural_elements import StructuralElement


_CEILING_MAP: Dict[str, Tuple[str, str]] = {
    # Interior – western
    "western_room":      ("beam_ceiling",      "wood"),
    "saloon":            ("beam_ceiling",      "wood"),
    "living_room":       ("flat_ceiling",      "plaster"),
    "restaurant":        ("flat_ceiling",      "plaster"),
    "library":           ("high_ceiling",      "wood"),
    "hotel_lobby":       ("high_ceiling",      "plaster"),
    "office":            ("flat_ceiling",      "drywall"),
    "workshop":          ("beam_ceiling",      "wood"),
    # Industrial
    "warehouse":         ("beam_ceiling",      "concrete"),
    "industrial_hangar": ("industrial_ceiling","industrial_metal"),
    "abandoned_factory": ("industrial_ceiling","cracked_concrete"),
    "shipyard":          ("industrial_ceiling","industrial_metal"),
    "oil_refinery":      ("industrial_ceiling","industrial_metal"),
    "power_station":     ("industrial_ceiling","industrial_metal"),
    "mining_facility":   ("industrial_ceiling","concrete"),
    "construction_site": ("industrial_ceiling","concrete"),
    # Scientific
    "robotics_lab":      ("flat_ceiling",      "concrete"),
    "control_room":      ("flat_ceiling",      "concrete"),
    "medical_lab":       ("flat_ceiling",      "tile"),
    "clean_room":        ("flat_ceiling",      "tile"),
    "biohazard_facility":("flat_ceiling",      "tile"),
    "research_lab":      ("flat_ceiling",      "concrete"),
    # Military
    "military_base":     ("flat_ceiling",      "concrete"),
    "command_center":    ("flat_ceiling",      "concrete"),
    "military_hangar":   ("industrial_ceiling","industrial_metal"),
    "checkpoint":        ("flat_ceiling",      "concrete"),
    "bunker":            ("flat_ceiling",      "concrete"),
    # Sci-Fi
    "sci_fi_corridor":   ("sci_fi_ceiling",    "sci_fi_panel"),
    "space_station":     ("sci_fi_ceiling",    "sci_fi_panel"),
    "spaceship_bridge":  ("sci_fi_ceiling",    "sci_fi_panel"),
    "engineering_bay":   ("sci_fi_ceiling",    "sci_fi_panel"),
    "alien_facility":    ("arched_ceiling",    "stone"),
    "cyberpunk_city":    ("open_sky",          "none"),
    # Urban
    "city_street":       ("open_sky",          "none"),
    "alleyway":          ("open_sky",          "none"),
    "subway_station":    ("flat_ceiling",      "concrete"),
    "parking_garage":    ("flat_ceiling",      "concrete"),
    "rooftop":           ("open_sky",          "none"),
    "shopping_mall":     ("high_ceiling",      "plaster"),
    # Fantasy
    "castle_hall":       ("vaulted_ceiling",   "stone"),
    "dungeon":           ("arched_ceiling",    "stone"),
    "wizard_tower":      ("arched_ceiling",    "stone"),
    "ancient_ruins":     ("arched_ceiling",    "stone"),
    "temple":            ("vaulted_ceiling",   "stone"),
    # Nature
    "forest":            ("open_sky",          "none"),
    "jungle":            ("open_sky",          "none"),
    "desert":            ("open_sky",          "none"),
    "canyon":            ("open_sky",          "none"),
    "mountain":          ("open_sky",          "none"),
    "coastline":         ("open_sky",          "none"),
    "swamp":             ("open_sky",          "none"),
    # Post-Apocalyptic
    "abandoned_city":    ("open_sky",          "none"),
    "destroyed_highway": ("open_sky",          "none"),
    "ruined_industrial_site": ("industrial_ceiling","cracked_concrete"),
    "survival_camp":     ("open_sky",          "none"),
}
_DEFAULT_CEILING = ("flat_ceiling", "concrete")

_OUTDOOR_ENVS = frozenset({
    "forest", "jungle", "desert", "canyon", "mountain", "coastline", "swamp",
    "city_street", "alleyway", "rooftop", "survival_camp",
    "abandoned_city", "destroyed_highway", "cyberpunk_city",
})

_CEILING_THICKNESS = 0.25


class CeilingBuilder:
    """Generates ceiling StructuralElements for any environment."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_ceiling(
        self,
        environment: str,
        width: float,
        depth: float,
        height: float,
    ) -> Optional[StructuralElement]:
        """
        Build a ceiling element. Returns None for outdoor environments.
        Never raises.
        """
        try:
            return self._build(environment, width, depth, height)
        except Exception:
            return None

    def _build(
        self,
        environment: str,
        width: float,
        depth: float,
        height: float,
    ) -> Optional[StructuralElement]:
        env = environment.lower()
        ceiling_type, material = _CEILING_MAP.get(env, _DEFAULT_CEILING)

        if ceiling_type == "open_sky" or env in _OUTDOOR_ENVS:
            return None

        return StructuralElement(
            element_id=f"ceiling_{env}",
            element_type="ceiling",
            environment=env,
            position=[0.0, height, 0.0],
            dimensions={
                "width":     round(width, 3),
                "depth":     round(depth, 3),
                "thickness": _CEILING_THICKNESS,
            },
            material=material,
            face="top",
            is_structural=True,
            metadata={"ceiling_type": ceiling_type},
        )

    def get_ceiling_type(self, environment: str) -> str:
        t, _ = _CEILING_MAP.get(environment.lower(), _DEFAULT_CEILING)
        return t

    def is_outdoor(self, environment: str) -> bool:
        return environment.lower() in _OUTDOOR_ENVS


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[CeilingBuilder] = None
_lock = threading.Lock()


def get_ceiling_builder() -> CeilingBuilder:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = CeilingBuilder()
    return _instance


def reset_ceiling_builder_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
