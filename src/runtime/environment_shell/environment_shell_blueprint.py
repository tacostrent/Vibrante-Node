"""
EnvironmentShellBlueprint — Tier 10.4
======================================
Describes the structural requirements for an environment before any asset
can be placed. Derived deterministically from environment_type.

No bridge calls. No randomness. Never raises in public methods.

Public API:
    EnvironmentShellBlueprint
    EnvironmentShellBlueprintFactory
    get_blueprint_factory()
    reset_blueprint_factory_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# (width_m, height_m, length_m)
_ENV_DIMS: Dict[str, tuple] = {
    "western_room":      (10.0,  4.0, 12.0),
    "saloon":            (14.0,  4.5, 18.0),
    "living_room":       ( 8.0,  3.0, 10.0),
    "office":            (10.0,  3.0, 14.0),
    "hotel_lobby":       (20.0,  6.0, 25.0),
    "restaurant":        (15.0,  4.0, 20.0),
    "library":           (12.0,  5.0, 18.0),
    "industrial_hangar": (30.0, 12.0, 40.0),
    "warehouse":         (20.0,  8.0, 30.0),
    "abandoned_factory": (25.0, 10.0, 35.0),
    "robotics_lab":      (15.0,  3.5, 20.0),
    "research_lab":      (12.0,  3.0, 16.0),
    "medical_lab":       (10.0,  3.0, 15.0),
    "control_room":      (12.0,  3.0, 16.0),
    "sci_fi_corridor":   ( 4.0,  3.0, 20.0),
    "space_station":     (15.0,  4.0, 20.0),
    "spaceship_bridge":  (10.0,  3.0, 14.0),
    "engineering_bay":   (15.0,  4.5, 20.0),
    "alien_facility":    (18.0,  5.0, 22.0),
    "cyberpunk_city":    (30.0,  0.0, 50.0),
    "castle_hall":       (20.0, 10.0, 30.0),
    "dungeon":           ( 8.0,  3.0, 10.0),
    "wizard_tower":      ( 8.0, 20.0,  8.0),
    "ancient_ruins":     (30.0,  0.0, 40.0),
    "temple":            (15.0,  8.0, 20.0),
    "military_base":     (30.0,  6.0, 40.0),
    "command_center":    (15.0,  4.0, 20.0),
    "military_hangar":   (25.0, 10.0, 35.0),
    "checkpoint":        ( 5.0,  3.0,  8.0),
    "bunker":            (10.0,  3.0, 15.0),
    "city_street":       (30.0,  0.0, 50.0),
    "alleyway":          ( 4.0,  0.0, 20.0),
    "subway_station":    (15.0,  5.0, 60.0),
    "parking_garage":    (25.0,  3.0, 40.0),
    "rooftop":           (20.0,  0.0, 30.0),
    "shopping_mall":     (40.0,  8.0, 60.0),
    "workshop":          ( 8.0,  3.5, 10.0),
    "shipyard":          (40.0, 15.0, 60.0),
    "oil_refinery":      (40.0, 20.0, 60.0),
    "power_station":     (30.0, 15.0, 50.0),
    "mining_facility":   (35.0, 12.0, 50.0),
    "construction_site": (50.0,  0.0, 80.0),
    "biohazard_facility":(15.0,  4.0, 20.0),
    "clean_room":        (10.0,  3.0, 15.0),
    "forest":            (50.0,  0.0, 50.0),
    "jungle":            (50.0,  0.0, 50.0),
    "desert":            (50.0,  0.0, 50.0),
    "canyon":            (50.0,  0.0, 80.0),
    "mountain":          (50.0,  0.0, 50.0),
    "coastline":         (50.0,  0.0, 60.0),
    "swamp":             (50.0,  0.0, 50.0),
    "abandoned_city":    (50.0,  0.0, 80.0),
    "destroyed_highway": (20.0,  0.0, 80.0),
    "ruined_industrial_site": (50.0, 0.0, 60.0),
    "survival_camp":     (20.0,  0.0, 20.0),
}

_OUTDOOR_ENVS = frozenset({
    "city_street", "alleyway", "rooftop", "cyberpunk_city",
    "forest", "jungle", "desert", "canyon", "mountain",
    "coastline", "swamp", "ancient_ruins", "construction_site",
    "abandoned_city", "destroyed_highway", "ruined_industrial_site",
    "survival_camp",
})

_FLOOR_MATERIALS: Dict[str, str] = {
    "western_room": "wood_planks", "saloon": "wood_planks",
    "living_room": "hardwood", "office": "tile", "hotel_lobby": "marble",
    "restaurant": "hardwood", "library": "hardwood",
    "industrial_hangar": "concrete", "warehouse": "concrete",
    "abandoned_factory": "concrete", "robotics_lab": "concrete",
    "research_lab": "tile", "medical_lab": "tile", "clean_room": "tile",
    "control_room": "tile", "sci_fi_corridor": "sci_fi_panel",
    "space_station": "sci_fi_panel", "spaceship_bridge": "sci_fi_panel",
    "engineering_bay": "sci_fi_panel", "alien_facility": "alien_metal",
    "castle_hall": "stone", "dungeon": "stone", "wizard_tower": "stone",
    "temple": "stone", "ancient_ruins": "dirt",
    "military_base": "concrete", "command_center": "concrete",
    "military_hangar": "concrete", "bunker": "concrete",
    "checkpoint": "concrete", "biohazard_facility": "tile",
    "city_street": "asphalt", "subway_station": "concrete",
    "parking_garage": "concrete", "shopping_mall": "marble",
    "workshop": "concrete", "shipyard": "concrete",
    "forest": "dirt", "jungle": "dirt", "desert": "sand",
    "canyon": "rock", "mountain": "rock", "coastline": "sand",
    "swamp": "mud", "survival_camp": "dirt",
    "cyberpunk_city": "asphalt",
}

_CEILING_TYPES: Dict[str, str] = {
    "western_room": "beam_ceiling", "saloon": "beam_ceiling",
    "living_room": "flat_ceiling", "office": "flat_ceiling",
    "hotel_lobby": "high_ceiling", "restaurant": "flat_ceiling",
    "library": "high_ceiling", "industrial_hangar": "industrial_ceiling",
    "warehouse": "beam_ceiling", "abandoned_factory": "industrial_ceiling",
    "robotics_lab": "flat_ceiling", "research_lab": "flat_ceiling",
    "medical_lab": "flat_ceiling", "clean_room": "flat_ceiling",
    "control_room": "flat_ceiling", "biohazard_facility": "flat_ceiling",
    "sci_fi_corridor": "sci_fi_ceiling", "space_station": "sci_fi_ceiling",
    "spaceship_bridge": "sci_fi_ceiling", "engineering_bay": "sci_fi_ceiling",
    "alien_facility": "sci_fi_ceiling",
    "castle_hall": "vaulted_ceiling", "dungeon": "arched_ceiling",
    "wizard_tower": "vaulted_ceiling", "temple": "vaulted_ceiling",
    "military_base": "flat_ceiling", "command_center": "flat_ceiling",
    "military_hangar": "industrial_ceiling", "bunker": "flat_ceiling",
    "workshop": "beam_ceiling", "subway_station": "industrial_ceiling",
    "parking_garage": "flat_ceiling", "shopping_mall": "high_ceiling",
}

_DOOR_COUNTS: Dict[str, int] = {
    "western_room": 1, "saloon": 2, "living_room": 1, "office": 1,
    "hotel_lobby": 2, "restaurant": 2, "library": 1,
    "industrial_hangar": 2, "warehouse": 2, "abandoned_factory": 1,
    "robotics_lab": 1, "research_lab": 1, "medical_lab": 1,
    "clean_room": 2, "control_room": 1, "biohazard_facility": 2,
    "sci_fi_corridor": 2, "space_station": 2, "spaceship_bridge": 1,
    "engineering_bay": 2, "alien_facility": 2,
    "castle_hall": 1, "dungeon": 1, "wizard_tower": 1, "temple": 1,
    "military_base": 2, "command_center": 1, "military_hangar": 2,
    "bunker": 1, "checkpoint": 1, "workshop": 1,
    "subway_station": 2, "parking_garage": 2, "shopping_mall": 4,
}

_WINDOW_COUNTS: Dict[str, int] = {
    "western_room": 2, "saloon": 2, "living_room": 2, "office": 4,
    "hotel_lobby": 6, "restaurant": 4, "library": 6,
    "industrial_hangar": 4, "warehouse": 2, "abandoned_factory": 2,
    "robotics_lab": 2, "research_lab": 4, "medical_lab": 2,
    "clean_room": 0, "control_room": 0, "biohazard_facility": 0,
    "sci_fi_corridor": 0, "space_station": 4, "spaceship_bridge": 4,
    "engineering_bay": 2, "alien_facility": 2,
    "castle_hall": 4, "dungeon": 0, "wizard_tower": 4, "temple": 2,
    "military_base": 2, "command_center": 0, "military_hangar": 4,
    "bunker": 0, "checkpoint": 2, "workshop": 2,
    "subway_station": 0, "parking_garage": 0, "shopping_mall": 8,
}


@dataclass
class EnvironmentShellBlueprint:
    """Complete structural specification for an environment shell."""

    environment_type: str   = ""
    room_width:       float = 10.0
    room_length:      float = 12.0
    room_height:      float = 4.0
    wall_count:       int   = 4
    door_count:       int   = 1
    window_count:     int   = 2
    ceiling_type:     str   = "flat_ceiling"
    floor_type:       str   = "concrete"
    is_outdoor:       bool  = False
    support_zones:    List[str] = field(default_factory=lambda: [
        "hero_zone", "midground", "background_zone"
    ])
    navigation_zones: List[str] = field(default_factory=lambda: [
        "entrance_zone", "walkable_floor"
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_type": self.environment_type,
            "room_width":       self.room_width,
            "room_length":      self.room_length,
            "room_height":      self.room_height,
            "wall_count":       self.wall_count,
            "door_count":       self.door_count,
            "window_count":     self.window_count,
            "ceiling_type":     self.ceiling_type,
            "floor_type":       self.floor_type,
            "is_outdoor":       self.is_outdoor,
            "support_zones":    list(self.support_zones),
            "navigation_zones": list(self.navigation_zones),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentShellBlueprint":
        return cls(
            environment_type  = d.get("environment_type", ""),
            room_width        = float(d.get("room_width", 10.0)),
            room_length       = float(d.get("room_length", 12.0)),
            room_height       = float(d.get("room_height", 4.0)),
            wall_count        = int(d.get("wall_count", 4)),
            door_count        = int(d.get("door_count", 1)),
            window_count      = int(d.get("window_count", 2)),
            ceiling_type      = d.get("ceiling_type", "flat_ceiling"),
            floor_type        = d.get("floor_type", "concrete"),
            is_outdoor        = bool(d.get("is_outdoor", False)),
            support_zones     = list(d.get("support_zones", ["hero_zone", "midground", "background_zone"])),
            navigation_zones  = list(d.get("navigation_zones", ["entrance_zone", "walkable_floor"])),
        )


class EnvironmentShellBlueprintFactory:
    """Produces EnvironmentShellBlueprint for any environment name."""

    def build(self, environment: str) -> EnvironmentShellBlueprint:
        """Return blueprint for the given environment. Never raises."""
        try:
            return self._build(environment)
        except Exception as exc:
            return EnvironmentShellBlueprint(
                environment_type = environment,
            )

    def _build(self, environment: str) -> EnvironmentShellBlueprint:
        env = (environment or "").strip().lower()
        is_outdoor = env in _OUTDOOR_ENVS
        w, h, d = _ENV_DIMS.get(env, (10.0, 4.0, 12.0))
        return EnvironmentShellBlueprint(
            environment_type  = env,
            room_width        = w,
            room_length       = d,
            room_height       = h,
            wall_count        = 0 if is_outdoor else 4,
            door_count        = _DOOR_COUNTS.get(env, 1) if not is_outdoor else 0,
            window_count      = _WINDOW_COUNTS.get(env, 0) if not is_outdoor else 0,
            ceiling_type      = "open_sky" if is_outdoor else _CEILING_TYPES.get(env, "flat_ceiling"),
            floor_type        = _FLOOR_MATERIALS.get(env, "concrete"),
            is_outdoor        = is_outdoor,
            support_zones     = ["hero_zone", "midground", "background_zone"],
            navigation_zones  = ["entrance_zone", "walkable_floor"],
        )


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[EnvironmentShellBlueprintFactory] = None
_LOCK = threading.Lock()


def get_blueprint_factory() -> EnvironmentShellBlueprintFactory:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = EnvironmentShellBlueprintFactory()
    return _INSTANCE


def reset_blueprint_factory_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
