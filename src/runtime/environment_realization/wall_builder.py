"""
wall_builder.py — §49 Structural Environment Realization
=========================================================
Generates four perimeter wall elements for a room (north, south, east, west).
Outdoor environments get no walls (or partial wind-break walls).

Wall material by category:
  wood              western, saloon, residential
  brick             western (alternate), alleyway
  stone             castle, dungeon, ancient
  concrete          industrial, scientific, military, urban
  industrial_metal  hangar, shipyard, sci-fi industrial
  sci_fi_panel      sci-fi corridor, space station
  drywall           office, hotel lobby

Public API:
    WallBuilder
    get_wall_builder()
    reset_wall_builder_for_tests()
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from src.runtime.environment_realization.structural_elements import StructuralElement


# (wall_material, thickness_m)
_WALL_MAP: Dict[str, tuple] = {
    "western_room":      ("wood",            0.20),
    "saloon":            ("wood",            0.20),
    "living_room":       ("plaster",         0.20),
    "restaurant":        ("plaster",         0.20),
    "library":           ("wood",            0.20),
    "hotel_lobby":       ("marble",          0.30),
    "office":            ("drywall",         0.15),
    "workshop":          ("wood",            0.20),
    "warehouse":         ("concrete",        0.30),
    "industrial_hangar": ("industrial_metal",0.40),
    "abandoned_factory": ("cracked_concrete",0.30),
    "shipyard":          ("industrial_metal",0.40),
    "oil_refinery":      ("industrial_metal",0.40),
    "power_station":     ("concrete",        0.30),
    "mining_facility":   ("concrete",        0.30),
    "construction_site": ("concrete",        0.25),
    "robotics_lab":      ("concrete",        0.25),
    "control_room":      ("concrete",        0.25),
    "medical_lab":       ("tile",            0.20),
    "clean_room":        ("tile",            0.20),
    "biohazard_facility":("concrete",        0.25),
    "research_lab":      ("concrete",        0.25),
    "military_base":     ("concrete",        0.35),
    "command_center":    ("concrete",        0.35),
    "military_hangar":   ("industrial_metal",0.40),
    "checkpoint":        ("concrete",        0.25),
    "bunker":            ("concrete",        0.40),
    "sci_fi_corridor":   ("sci_fi_panel",    0.20),
    "space_station":     ("sci_fi_panel",    0.25),
    "spaceship_bridge":  ("sci_fi_panel",    0.20),
    "engineering_bay":   ("sci_fi_panel",    0.25),
    "alien_facility":    ("stone",           0.40),
    "subway_station":    ("concrete",        0.35),
    "parking_garage":    ("concrete",        0.30),
    "shopping_mall":     ("plaster",         0.25),
    "castle_hall":       ("stone",           0.60),
    "dungeon":           ("stone",           0.60),
    "wizard_tower":      ("stone",           0.50),
    "ancient_ruins":     ("stone",           0.50),
    "temple":            ("stone",           0.50),
    "ruined_industrial_site": ("cracked_concrete", 0.30),
}
_DEFAULT_WALL = ("concrete", 0.25)
_NO_WALL_ENVS = frozenset({
    "forest", "jungle", "desert", "canyon", "mountain", "coastline", "swamp",
    "city_street", "alleyway", "rooftop", "survival_camp",
    "abandoned_city", "destroyed_highway", "cyberpunk_city",
})

_FACES = ["north", "south", "east", "west"]


class WallBuilder:
    """Generates perimeter wall StructuralElements for a room."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_walls(
        self,
        environment: str,
        width: float,
        height: float,
        depth: float,
    ) -> Dict[str, StructuralElement]:
        """
        Build all four perimeter walls.
        Returns dict face → StructuralElement, or {} for outdoor environments.
        Never raises.
        """
        try:
            return self._build(environment, width, height, depth)
        except Exception:
            return {}

    def _build(
        self,
        environment: str,
        width: float,
        height: float,
        depth: float,
    ) -> Dict[str, StructuralElement]:
        env = environment.lower()
        if env in _NO_WALL_ENVS:
            return {}

        material, thickness = _WALL_MAP.get(env, _DEFAULT_WALL)
        hw = width / 2.0
        hd = depth / 2.0

        walls: Dict[str, StructuralElement] = {}

        # North wall (z = -depth/2)
        walls["north"] = StructuralElement(
            element_id=f"wall_north_{env}",
            element_type="wall",
            environment=env,
            position=[0.0, height / 2.0, -hd],
            dimensions={"width": width, "height": height, "thickness": thickness},
            rotation=[0.0, 0.0, 0.0],
            material=material,
            face="north",
            is_structural=True,
        )
        # South wall (z = +depth/2)
        walls["south"] = StructuralElement(
            element_id=f"wall_south_{env}",
            element_type="wall",
            environment=env,
            position=[0.0, height / 2.0, hd],
            dimensions={"width": width, "height": height, "thickness": thickness},
            rotation=[0.0, 180.0, 0.0],
            material=material,
            face="south",
            is_structural=True,
        )
        # East wall (x = +width/2)
        walls["east"] = StructuralElement(
            element_id=f"wall_east_{env}",
            element_type="wall",
            environment=env,
            position=[hw, height / 2.0, 0.0],
            dimensions={"width": depth, "height": height, "thickness": thickness},
            rotation=[0.0, 90.0, 0.0],
            material=material,
            face="east",
            is_structural=True,
        )
        # West wall (x = -width/2)
        walls["west"] = StructuralElement(
            element_id=f"wall_west_{env}",
            element_type="wall",
            environment=env,
            position=[-hw, height / 2.0, 0.0],
            dimensions={"width": depth, "height": height, "thickness": thickness},
            rotation=[0.0, 270.0, 0.0],
            material=material,
            face="west",
            is_structural=True,
        )
        return walls

    def get_wall_material(self, environment: str) -> str:
        material, _ = _WALL_MAP.get(environment.lower(), _DEFAULT_WALL)
        return material


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[WallBuilder] = None
_lock = threading.Lock()


def get_wall_builder() -> WallBuilder:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = WallBuilder()
    return _instance


def reset_wall_builder_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
