"""
ShellWallBuilder — Tier 10.4, Phase 2
======================================
Constructs the perimeter walls of the environment shell.

Requirements:
  wall_count  >= blueprint.wall_count
  walls form a closed boundary (enclosure_valid = True for indoor)
  walls define room limits

Generates: wall_north, wall_south, wall_east, wall_west

Never raises.

Public API:
    ShellWallBuilder
    get_shell_wall_builder()
    reset_shell_wall_builder_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from src.runtime.environment_shell.environment_shell_blueprint import EnvironmentShellBlueprint
from src.runtime.environment_shell.shell_phase_result import (
    ShellPhaseResult,
    WALL_CONSTRUCTION_COMPLETE,
)

_WALL_MATERIALS: Dict[str, str] = {
    "western_room": "wood", "saloon": "wood",
    "living_room": "plaster", "office": "drywall",
    "hotel_lobby": "marble", "restaurant": "plaster",
    "library": "wood", "industrial_hangar": "industrial_metal",
    "warehouse": "concrete", "abandoned_factory": "concrete",
    "robotics_lab": "concrete", "research_lab": "concrete",
    "medical_lab": "tile", "clean_room": "tile",
    "control_room": "concrete", "biohazard_facility": "tile",
    "sci_fi_corridor": "sci_fi_panel", "space_station": "sci_fi_panel",
    "spaceship_bridge": "sci_fi_panel", "engineering_bay": "sci_fi_panel",
    "alien_facility": "alien_metal",
    "castle_hall": "stone", "dungeon": "stone",
    "wizard_tower": "stone", "temple": "stone",
    "military_base": "concrete", "command_center": "concrete",
    "military_hangar": "industrial_metal", "bunker": "concrete",
    "checkpoint": "concrete", "workshop": "concrete",
    "subway_station": "concrete", "parking_garage": "concrete",
    "shopping_mall": "drywall",
}


class ShellWallBuilder:

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build(self, blueprint: EnvironmentShellBlueprint) -> ShellPhaseResult:
        """Build perimeter walls. Never raises."""
        try:
            return self._build(blueprint)
        except Exception as exc:
            r = ShellPhaseResult(phase="walls", status="WALL_FAILED")
            r.errors.append(f"ShellWallBuilder error: {exc}")
            return r

    def _build(self, bp: EnvironmentShellBlueprint) -> ShellPhaseResult:
        result = ShellPhaseResult(phase="walls")

        if bp.is_outdoor or bp.wall_count == 0:
            result.status = WALL_CONSTRUCTION_COMPLETE
            result.ok     = True
            result.metrics = {
                "wall_count":         0,
                "walls_form_enclosure": False,
                "is_outdoor":         True,
            }
            result.findings.append("Outdoor environment: no perimeter walls required.")
            return result

        w   = bp.room_width  if bp.room_width  > 0 else 10.0
        d   = bp.room_length if bp.room_length > 0 else 12.0
        h   = bp.room_height if bp.room_height > 0 else  4.0
        mat = _WALL_MATERIALS.get(bp.environment_type, "concrete")
        thick = 0.3  # standard wall thickness

        walls: List[Dict[str, Any]] = [
            {
                "element_type": "wall",
                "element_id":   f"wall_north_{bp.environment_type}",
                "face":         "north",
                "environment":  bp.environment_type,
                "material":     mat,
                "width":        w, "height": h, "depth": thick,
                "tx": 0.0, "ty": h / 2.0, "tz": -(d / 2.0),
            },
            {
                "element_type": "wall",
                "element_id":   f"wall_south_{bp.environment_type}",
                "face":         "south",
                "environment":  bp.environment_type,
                "material":     mat,
                "width":        w, "height": h, "depth": thick,
                "tx": 0.0, "ty": h / 2.0, "tz": d / 2.0,
            },
            {
                "element_type": "wall",
                "element_id":   f"wall_east_{bp.environment_type}",
                "face":         "east",
                "environment":  bp.environment_type,
                "material":     mat,
                "width":        thick, "height": h, "depth": d,
                "tx": w / 2.0, "ty": h / 2.0, "tz": 0.0,
            },
            {
                "element_type": "wall",
                "element_id":   f"wall_west_{bp.environment_type}",
                "face":         "west",
                "environment":  bp.environment_type,
                "material":     mat,
                "width":        thick, "height": h, "depth": d,
                "tx": -(w / 2.0), "ty": h / 2.0, "tz": 0.0,
            },
        ]

        result.elements = walls
        result.metrics  = {
            "wall_count":           len(walls),
            "walls_form_enclosure": True,
            "enclosure_valid":      True,
        }
        result.status = WALL_CONSTRUCTION_COMPLETE
        result.ok     = True
        return result


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[ShellWallBuilder] = None
_LOCK = threading.Lock()


def get_shell_wall_builder() -> ShellWallBuilder:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = ShellWallBuilder()
    return _INSTANCE


def reset_shell_wall_builder_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
