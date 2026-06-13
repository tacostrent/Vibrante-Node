"""
floor_builder.py — §49 Structural Environment Realization
==========================================================
Generates floor structural elements for any environment.

Floor types by environment:
  wood_planks      western_room, saloon, living_room, restaurant, library
  stone            castle_hall, dungeon, ancient_ruins, temple
  concrete         robotics_lab, control_room, office, warehouse, research_lab
  cracked_concrete abandoned_factory, ruined_industrial_site
  metal_grating    industrial_hangar (upper platforms), shipyard
  marble           hotel_lobby
  sand             desert, canyon, outdoor sandy
  dirt             forest, jungle, survival_camp, outdoor earthy
  tile             medical_lab, clean_room
  industrial_metal oil_refinery, power_station

Public API:
    FloorBuilder
    get_floor_builder()
    reset_floor_builder_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.environment_realization.structural_elements import StructuralElement


# Map environment → (floor_type, material)
_FLOOR_MAP: Dict[str, Tuple[str, str]] = {
    # Interior – western
    "western_room":      ("wood_planks",     "wood"),
    "saloon":            ("wood_planks",     "wood"),
    # Interior – residential
    "living_room":       ("wood_planks",     "wood"),
    "restaurant":        ("wood_planks",     "wood"),
    "library":           ("wood_planks",     "wood"),
    "hotel_lobby":       ("marble",          "marble"),
    "office":            ("concrete",        "concrete"),
    # Industrial
    "warehouse":         ("concrete",        "concrete"),
    "industrial_hangar": ("concrete",        "concrete"),
    "abandoned_factory": ("cracked_concrete","cracked_concrete"),
    "shipyard":          ("metal_grating",   "industrial_metal"),
    "oil_refinery":      ("industrial_metal","industrial_metal"),
    "power_station":     ("concrete",        "concrete"),
    "mining_facility":   ("concrete",        "concrete"),
    "construction_site": ("concrete",        "concrete"),
    # Scientific
    "robotics_lab":      ("concrete",        "concrete"),
    "control_room":      ("concrete",        "concrete"),
    "medical_lab":       ("tile",            "tile"),
    "clean_room":        ("tile",            "tile"),
    "biohazard_facility":("tile",            "tile"),
    "research_lab":      ("concrete",        "concrete"),
    # Military
    "military_base":     ("concrete",        "concrete"),
    "command_center":    ("concrete",        "concrete"),
    "military_hangar":   ("concrete",        "concrete"),
    "checkpoint":        ("concrete",        "concrete"),
    "bunker":            ("concrete",        "concrete"),
    # Sci-Fi
    "sci_fi_corridor":   ("metal_grating",   "industrial_metal"),
    "space_station":     ("metal_grating",   "industrial_metal"),
    "spaceship_bridge":  ("metal_grating",   "industrial_metal"),
    "engineering_bay":   ("metal_grating",   "industrial_metal"),
    "alien_facility":    ("stone",           "stone"),
    "cyberpunk_city":    ("concrete",        "concrete"),
    # Urban
    "city_street":       ("concrete",        "concrete"),
    "alleyway":          ("concrete",        "concrete"),
    "subway_station":    ("concrete",        "concrete"),
    "parking_garage":    ("concrete",        "concrete"),
    "rooftop":           ("concrete",        "concrete"),
    "shopping_mall":     ("marble",          "marble"),
    # Fantasy
    "castle_hall":       ("stone",           "stone"),
    "dungeon":           ("stone",           "stone"),
    "wizard_tower":      ("stone",           "stone"),
    "ancient_ruins":     ("stone",           "stone"),
    "temple":            ("stone",           "stone"),
    # Nature (outdoor — thin ground plane)
    "forest":            ("dirt",            "dirt"),
    "jungle":            ("dirt",            "dirt"),
    "desert":            ("sand",            "sand"),
    "canyon":            ("stone",           "stone"),
    "mountain":          ("stone",           "stone"),
    "coastline":         ("sand",            "sand"),
    "swamp":             ("dirt",            "dirt"),
    # Post-Apocalyptic
    "abandoned_city":    ("cracked_concrete","cracked_concrete"),
    "destroyed_highway": ("cracked_concrete","cracked_concrete"),
    "ruined_industrial_site": ("cracked_concrete","cracked_concrete"),
    "survival_camp":     ("dirt",            "dirt"),
    # Interior misc
    "workshop":          ("concrete",        "concrete"),
}
_DEFAULT_FLOOR = ("concrete", "concrete")

# Outdoor environments that use a large ground plane instead of a room floor
_OUTDOOR_ENVS = frozenset({
    "forest", "jungle", "desert", "canyon", "mountain", "coastline", "swamp",
    "city_street", "alleyway", "rooftop", "survival_camp",
    "abandoned_city", "destroyed_highway",
})

# Floor thickness (meters)
_FLOOR_THICKNESS = 0.20

# Ground plane scale for outdoor (larger)
_OUTDOOR_SCALE = 50.0


class FloorBuilder:
    """Generates floor StructuralElements for any environment."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_floor(
        self,
        environment: str,
        width: float,
        depth: float,
    ) -> StructuralElement:
        """
        Build a floor element for the given environment and room dimensions.
        Never raises.
        """
        try:
            return self._build(environment, width, depth)
        except Exception as exc:
            return StructuralElement(
                element_id=f"floor_{environment}",
                element_type="floor",
                environment=environment,
                position=[0.0, 0.0, 0.0],
                dimensions={"width": width, "depth": depth, "thickness": _FLOOR_THICKNESS},
                material="concrete",
                face="bottom",
            )

    def _build(self, environment: str, width: float, depth: float) -> StructuralElement:
        env = environment.lower()
        floor_type, material = _FLOOR_MAP.get(env, _DEFAULT_FLOOR)
        is_outdoor = env in _OUTDOOR_ENVS

        eff_width = _OUTDOOR_SCALE if is_outdoor else width
        eff_depth = _OUTDOOR_SCALE if is_outdoor else depth

        return StructuralElement(
            element_id=f"floor_{env}",
            element_type="floor",
            environment=env,
            position=[0.0, 0.0, 0.0],
            dimensions={
                "width":     round(eff_width, 3),
                "depth":     round(eff_depth, 3),
                "thickness": _FLOOR_THICKNESS,
            },
            material=material,
            face="bottom",
            is_structural=True,
            metadata={
                "floor_type": floor_type,
                "is_outdoor": is_outdoor,
            },
        )

    def get_floor_material(self, environment: str) -> str:
        _, material = _FLOOR_MAP.get(environment.lower(), _DEFAULT_FLOOR)
        return material


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[FloorBuilder] = None
_lock = threading.Lock()


def get_floor_builder() -> FloorBuilder:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = FloorBuilder()
    return _instance


def reset_floor_builder_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
