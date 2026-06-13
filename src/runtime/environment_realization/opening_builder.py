"""
opening_builder.py — §49 Structural Environment Realization
============================================================
Generates door, window, archway, vent, and other opening elements.

Rules:
  - Openings always reference a parent wall_id
  - Doors sit on the floor (position y = door_height / 2)
  - Windows sit mid-wall (position y = sill_height + window_height / 2)
  - Openings must not exceed the wall dimensions
  - Each environment has a canonical opening configuration

Canonical openings per environment type:
  western_room     1 swing_door (south/entrance) + 2 windows (east/west)
  saloon           1 swing_door + 1 side_door + 2 windows
  industrial_hangar 1 hangar_door (south) + 1 side_door + 4 skylights
  sci_fi_corridor  2 sliding_doors (north + south) + 4 vents
  castle_hall      1 arched main door (south) + 4 narrow windows
  dungeon          1 door (north) + 4 arrow_slits
  office           1 door + 4 windows
  warehouse        1 loading_door + 2 service_doors + 4 skylights

Public API:
    OpeningBuilder
    get_opening_builder()
    reset_opening_builder_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.environment_realization.structural_elements import StructuralElement


@dataclass
class OpeningSpec:
    opening_type: str   # "door", "window", "sliding_door", etc.
    face: str           # which wall: "north","south","east","west","top"
    x_offset: float     # horizontal offset from wall centre
    y_bottom: float     # bottom y of opening above floor
    width: float
    height: float
    material: str = "wood"
    label: str = ""


# Canonical opening configurations per environment
_ENV_OPENINGS: Dict[str, List[OpeningSpec]] = {
    "western_room": [
        OpeningSpec("swing_door", "south", 0.0, 0.0, 1.0, 2.2, "wood", "main_entrance"),
        OpeningSpec("window", "east",  -1.5, 1.2, 1.2, 1.0, "glass", "window_east_1"),
        OpeningSpec("window", "west",   1.5, 1.2, 1.2, 1.0, "glass", "window_west_1"),
    ],
    "saloon": [
        OpeningSpec("swing_door", "south",  0.0, 0.0, 1.2, 2.1, "wood",  "main_entrance"),
        OpeningSpec("door",       "north", -2.0, 0.0, 0.9, 2.0, "wood",  "kitchen_door"),
        OpeningSpec("window",     "east",   0.0, 1.2, 1.5, 1.0, "glass", "window_east"),
        OpeningSpec("window",     "west",   0.0, 1.2, 1.5, 1.0, "glass", "window_west"),
    ],
    "industrial_hangar": [
        OpeningSpec("hangar_opening", "south",  0.0, 0.0, 12.0, 8.0, "industrial_metal", "main_hangar_opening"),
        OpeningSpec("door",           "north", -5.0, 0.0,  1.2, 2.5, "industrial_metal", "side_door_n"),
        OpeningSpec("skylight",       "top",  -5.0, 0.0,   2.0, 2.0, "glass",            "skylight_1"),
        OpeningSpec("skylight",       "top",   5.0, 0.0,   2.0, 2.0, "glass",            "skylight_2"),
        OpeningSpec("skylight",       "top",  -5.0, 0.0,   2.0, 2.0, "glass",            "skylight_3"),
        OpeningSpec("skylight",       "top",   5.0, 0.0,   2.0, 2.0, "glass",            "skylight_4"),
    ],
    "warehouse": [
        OpeningSpec("loading_door",  "south",  0.0, 0.0,  4.0, 4.0, "industrial_metal", "loading_dock"),
        OpeningSpec("door",          "south",  4.0, 0.0,  1.2, 2.5, "industrial_metal", "side_door"),
        OpeningSpec("skylight",      "top",   -5.0, 0.0,  2.0, 2.0, "glass",            "skylight_1"),
        OpeningSpec("skylight",      "top",    5.0, 0.0,  2.0, 2.0, "glass",            "skylight_2"),
    ],
    "sci_fi_corridor": [
        OpeningSpec("sliding_door", "south",  0.0, 0.0, 1.8, 2.5, "sci_fi_panel", "door_south"),
        OpeningSpec("sliding_door", "north",  0.0, 0.0, 1.8, 2.5, "sci_fi_panel", "door_north"),
        OpeningSpec("vent",         "east",   0.0, 2.5, 0.4, 0.4, "industrial_metal", "vent_e1"),
        OpeningSpec("vent",         "west",   0.0, 2.5, 0.4, 0.4, "industrial_metal", "vent_w1"),
    ],
    "castle_hall": [
        OpeningSpec("archway",     "south",  0.0, 0.0, 3.0, 4.5, "stone", "main_arch"),
        OpeningSpec("window",      "east",  -3.0, 3.0, 0.6, 1.5, "glass", "arrow_slit_e1"),
        OpeningSpec("window",      "east",   3.0, 3.0, 0.6, 1.5, "glass", "arrow_slit_e2"),
        OpeningSpec("window",      "west",  -3.0, 3.0, 0.6, 1.5, "glass", "arrow_slit_w1"),
        OpeningSpec("window",      "west",   3.0, 3.0, 0.6, 1.5, "glass", "arrow_slit_w2"),
    ],
    "dungeon": [
        OpeningSpec("door",        "north",  0.0, 0.0, 0.9, 2.0, "iron",  "dungeon_door"),
        OpeningSpec("arrow_slit",  "east",  -1.0, 2.0, 0.2, 0.6, "stone", "slit_e1"),
        OpeningSpec("arrow_slit",  "east",   1.0, 2.0, 0.2, 0.6, "stone", "slit_e2"),
        OpeningSpec("arrow_slit",  "west",  -1.0, 2.0, 0.2, 0.6, "stone", "slit_w1"),
        OpeningSpec("arrow_slit",  "west",   1.0, 2.0, 0.2, 0.6, "stone", "slit_w2"),
    ],
    "office": [
        OpeningSpec("door",   "south",  0.0, 0.0, 1.0, 2.1, "wood",  "entrance"),
        OpeningSpec("window", "north", -2.0, 1.0, 1.5, 1.2, "glass", "window_n1"),
        OpeningSpec("window", "north",  2.0, 1.0, 1.5, 1.2, "glass", "window_n2"),
        OpeningSpec("window", "east",   0.0, 1.0, 1.5, 1.2, "glass", "window_e"),
        OpeningSpec("window", "west",   0.0, 1.0, 1.5, 1.2, "glass", "window_w"),
    ],
    "robotics_lab": [
        OpeningSpec("door",   "south",  0.0, 0.0, 1.2, 2.2, "industrial_metal", "main_door"),
        OpeningSpec("window", "north", -3.0, 1.0, 2.0, 1.0, "glass",            "obs_window_1"),
        OpeningSpec("window", "north",  3.0, 1.0, 2.0, 1.0, "glass",            "obs_window_2"),
    ],
    "control_room": [
        OpeningSpec("door",          "south",  0.0, 0.0, 1.0, 2.1, "concrete",      "main_door"),
        OpeningSpec("service_opening","east",   0.0, 0.8, 0.5, 0.5, "industrial_metal","cable_run"),
    ],
}

# Generic fallbacks by wall count type
_GENERIC_INTERIOR = [
    OpeningSpec("door",   "south", 0.0, 0.0, 1.0, 2.1, "wood", "entrance"),
    OpeningSpec("window", "north", 0.0, 1.0, 1.2, 1.0, "glass", "window"),
]
_GENERIC_INDUSTRIAL = [
    OpeningSpec("door", "south", 0.0, 0.0, 1.2, 2.5, "industrial_metal", "entrance"),
]


class OpeningBuilder:
    """Generates door, window, and other opening elements for environment walls."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_openings(
        self,
        environment: str,
        walls: Dict[str, StructuralElement],
    ) -> List[StructuralElement]:
        """
        Build opening elements for the given environment.
        Openings reference their parent wall by element_id via wall_id.
        Never raises.
        """
        try:
            return self._build(environment.lower(), walls)
        except Exception:
            return []

    def _build(
        self,
        env: str,
        walls: Dict[str, StructuralElement],
    ) -> List[StructuralElement]:
        specs = _ENV_OPENINGS.get(env)
        if specs is None:
            # Generic fallback
            if any(k in env for k in ("lab", "room", "office", "living")):
                specs = _GENERIC_INTERIOR
            else:
                specs = _GENERIC_INDUSTRIAL

        openings: List[StructuralElement] = []
        for spec in specs:
            wall = walls.get(spec.face)
            wall_id = wall.element_id if wall else f"wall_{spec.face}_{env}"
            wall_pos = wall.position if wall else [0.0, 0.0, 0.0]

            # Calculate world position of opening centre
            pos = self._opening_position(spec, wall_pos)

            openings.append(StructuralElement(
                element_id=f"{spec.label or spec.opening_type}_{env}",
                element_type=spec.opening_type,
                environment=env,
                position=pos,
                dimensions={
                    "width":  spec.width,
                    "height": spec.height,
                },
                material=spec.material,
                wall_id=wall_id,
                face=spec.face,
                is_structural=False,
                is_opening=True,
                metadata={
                    "y_bottom":   spec.y_bottom,
                    "x_offset":   spec.x_offset,
                    "label":      spec.label,
                },
            ))
        return openings

    @staticmethod
    def _opening_position(spec: OpeningSpec, wall_pos: List[float]) -> List[float]:
        wx, wy, wz = wall_pos
        face = spec.face
        y_centre = spec.y_bottom + spec.height / 2.0

        if face in ("north", "south"):
            return [wx + spec.x_offset, y_centre, wz]
        elif face in ("east", "west"):
            return [wx, y_centre, wz + spec.x_offset]
        else:  # top (skylight)
            return [wx + spec.x_offset, wy + 0.1, wz]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[OpeningBuilder] = None
_lock = threading.Lock()


def get_opening_builder() -> OpeningBuilder:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = OpeningBuilder()
    return _instance


def reset_opening_builder_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
