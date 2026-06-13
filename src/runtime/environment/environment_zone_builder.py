"""
Environment Zone Builder (§44 — Structural Environment Assembly)
================================================================
Constructs the canonical set of zones for an environment. Every environment
gets at minimum: hero_zone, entrance_zone, decoration_zone, atmosphere_zone.
Additional zones are added based on the blueprint's required_zones list.

9 canonical zone types:
  hero_zone        — primary focal point, major anchors
  entrance_zone    — viewer entry / camera approach
  seating_zone     — seating clusters (interior)
  service_zone     — service / utility areas
  wall_zone        — wall-adjacent assets
  background_zone  — distant fills / architectural
  decoration_zone  — small props and surface dressing
  atmosphere_zone  — lighting, volumetrics, HDRI
  support_zone     — secondary context assets

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Advisory only.
  2. Deterministic — same environment always produces the same zone set.
  3. Never raises.
  4. Singleton pattern.
  5. Thread-safe.

Public API:
    EnvironmentZone
    ZonePlan
    EnvironmentZoneBuilder
    get_environment_zone_builder()
    reset_environment_zone_builder_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment.environment_blueprint import EnvironmentBlueprint


# ---------------------------------------------------------------------------
# Zone definitions
# ---------------------------------------------------------------------------

@dataclass
class EnvironmentZone:
    """A named spatial zone within an environment."""

    zone_id: str = ""
    zone_type: str = ""       # one of the 9 canonical types
    display_name: str = ""
    description: str = ""
    max_assets: int = 5
    required: bool = False
    position_hint: str = ""   # center / foreground / perimeter / background / ceiling / scattered

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id":      self.zone_id,
            "zone_type":    self.zone_type,
            "display_name": self.display_name,
            "description":  self.description,
            "max_assets":   self.max_assets,
            "required":     self.required,
            "position_hint": self.position_hint,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentZone":
        return cls(
            zone_id      = str(d.get("zone_id", "")),
            zone_type    = str(d.get("zone_type", "")),
            display_name = str(d.get("display_name", "")),
            description  = str(d.get("description", "")),
            max_assets   = int(d.get("max_assets", 5)),
            required     = bool(d.get("required", False)),
            position_hint = str(d.get("position_hint", "")),
        )


@dataclass
class ZonePlan:
    """The complete zone layout for an environment."""

    environment_name: str = ""
    zones: List[EnvironmentZone] = field(default_factory=list)
    zone_count: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_name": self.environment_name,
            "zones":            [z.to_dict() for z in self.zones],
            "zone_count":       self.zone_count,
            "errors":           list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ZonePlan":
        return cls(
            environment_name = str(d.get("environment_name", "")),
            zones            = [EnvironmentZone.from_dict(z) for z in d.get("zones", [])],
            zone_count       = int(d.get("zone_count", 0)),
            errors           = list(d.get("errors", [])),
        )


# ---------------------------------------------------------------------------
# Per-zone prototype definitions
# ---------------------------------------------------------------------------

_ZONE_PROTOTYPES: Dict[str, Dict[str, Any]] = {
    "hero_zone": {
        "display_name": "Hero Zone",
        "description": "Primary focal point — major anchor assets placed here.",
        "max_assets": 8,
        "required": True,
        "position_hint": "center",
    },
    "entrance_zone": {
        "display_name": "Entrance Zone",
        "description": "Viewer entry point and camera approach area.",
        "max_assets": 4,
        "required": True,
        "position_hint": "foreground",
    },
    "seating_zone": {
        "display_name": "Seating Zone",
        "description": "Chairs, stools, and seating clusters.",
        "max_assets": 10,
        "required": False,
        "position_hint": "midground",
    },
    "service_zone": {
        "display_name": "Service Zone",
        "description": "Service counters, utility areas, and operational equipment.",
        "max_assets": 6,
        "required": False,
        "position_hint": "perimeter",
    },
    "wall_zone": {
        "display_name": "Wall Zone",
        "description": "Wall-adjacent props, wall-mounted decorations, and shelving.",
        "max_assets": 8,
        "required": False,
        "position_hint": "perimeter",
    },
    "background_zone": {
        "display_name": "Background Zone",
        "description": "Distant architectural fills and background dressing.",
        "max_assets": 6,
        "required": False,
        "position_hint": "background",
    },
    "decoration_zone": {
        "display_name": "Decoration Zone",
        "description": "Small surface dressing and detail props.",
        "max_assets": 15,
        "required": True,
        "position_hint": "scattered",
    },
    "atmosphere_zone": {
        "display_name": "Atmosphere Zone",
        "description": "Lighting rigs, volumetric effects, and HDRI elements.",
        "max_assets": 4,
        "required": True,
        "position_hint": "ceiling",
    },
    "support_zone": {
        "display_name": "Support Zone",
        "description": "Secondary context assets supporting the hero elements.",
        "max_assets": 6,
        "required": False,
        "position_hint": "midground",
    },
}

# Per-environment zone sets — which canonical zone_types to include
_ENV_ZONES: Dict[str, List[str]] = {
    "western_room":      ["hero_zone", "entrance_zone", "wall_zone", "decoration_zone", "atmosphere_zone"],
    "saloon":            ["hero_zone", "entrance_zone", "seating_zone", "service_zone", "wall_zone", "decoration_zone", "atmosphere_zone"],
    "living_room":       ["hero_zone", "entrance_zone", "seating_zone", "wall_zone", "decoration_zone", "atmosphere_zone"],
    "office":            ["hero_zone", "entrance_zone", "support_zone", "wall_zone", "decoration_zone", "atmosphere_zone"],
    "hotel_lobby":       ["hero_zone", "entrance_zone", "seating_zone", "service_zone", "decoration_zone", "atmosphere_zone"],
    "restaurant":        ["hero_zone", "entrance_zone", "seating_zone", "service_zone", "wall_zone", "decoration_zone", "atmosphere_zone"],
    "library":           ["hero_zone", "entrance_zone", "seating_zone", "support_zone", "wall_zone", "decoration_zone", "atmosphere_zone"],
    "warehouse":         ["hero_zone", "entrance_zone", "support_zone", "background_zone", "decoration_zone", "atmosphere_zone"],
    "industrial_hangar": ["hero_zone", "entrance_zone", "support_zone", "wall_zone", "background_zone", "decoration_zone", "atmosphere_zone"],
    "abandoned_factory": ["hero_zone", "entrance_zone", "support_zone", "wall_zone", "decoration_zone", "atmosphere_zone"],
    "robotics_lab":      ["hero_zone", "entrance_zone", "support_zone", "wall_zone", "decoration_zone", "atmosphere_zone"],
    "control_room":      ["hero_zone", "entrance_zone", "support_zone", "decoration_zone", "atmosphere_zone"],
    "medical_lab":       ["hero_zone", "entrance_zone", "support_zone", "wall_zone", "decoration_zone", "atmosphere_zone"],
    "research_lab":      ["hero_zone", "entrance_zone", "support_zone", "wall_zone", "decoration_zone", "atmosphere_zone"],
    "sci_fi_corridor":   ["hero_zone", "entrance_zone", "support_zone", "wall_zone", "decoration_zone", "atmosphere_zone"],
    "city_street":       ["hero_zone", "entrance_zone", "support_zone", "background_zone", "decoration_zone", "atmosphere_zone"],
    "forest":            ["hero_zone", "entrance_zone", "support_zone", "background_zone", "decoration_zone", "atmosphere_zone"],
    "desert":            ["hero_zone", "entrance_zone", "background_zone", "decoration_zone", "atmosphere_zone"],
    "castle_hall":       ["hero_zone", "entrance_zone", "seating_zone", "wall_zone", "decoration_zone", "atmosphere_zone"],
    "survival_camp":     ["hero_zone", "entrance_zone", "service_zone", "decoration_zone", "atmosphere_zone"],
}

# Minimum zones for any environment not in the list
_DEFAULT_ZONES = ["hero_zone", "entrance_zone", "decoration_zone", "atmosphere_zone"]


def _build_zone(env_name: str, zone_type: str, idx: int) -> EnvironmentZone:
    proto = _ZONE_PROTOTYPES.get(zone_type, {})
    return EnvironmentZone(
        zone_id      = f"{env_name}_{zone_type}_{idx}",
        zone_type    = zone_type,
        display_name = proto.get("display_name", zone_type.replace("_", " ").title()),
        description  = proto.get("description", ""),
        max_assets   = int(proto.get("max_assets", 5)),
        required     = bool(proto.get("required", False)),
        position_hint = str(proto.get("position_hint", "scattered")),
    )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class EnvironmentZoneBuilder:
    """Build and validate environment zone plans."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_zones(
        self,
        environment_name: str,
        blueprint: Optional[EnvironmentBlueprint] = None,
    ) -> ZonePlan:
        """Build the zone plan for the given environment.

        Args:
            environment_name: Canonical environment name.
            blueprint: Optional blueprint; used to supplement zone list from
                       blueprint.required_zones if provided.

        Returns:
            ZonePlan with at least 4 zones (hero, entrance, decoration, atmosphere).
        """
        with self._lock:
            try:
                return self._build(environment_name, blueprint)
            except Exception as exc:
                return ZonePlan(
                    environment_name = environment_name,
                    errors           = [f"Zone build error: {exc}"],
                )

    def _build(
        self,
        environment_name: str,
        blueprint: Optional[EnvironmentBlueprint],
    ) -> ZonePlan:
        key = (environment_name or "").strip().lower()

        # Collect zone types: start from env-specific list or defaults
        zone_types_list = list(_ENV_ZONES.get(key, _DEFAULT_ZONES))

        # Merge required_zones from blueprint if provided
        if blueprint and blueprint.required_zones:
            for z in blueprint.required_zones:
                if z not in zone_types_list:
                    zone_types_list.append(z)

        # Ensure minimums
        for required in _DEFAULT_ZONES:
            if required not in zone_types_list:
                zone_types_list.append(required)

        # Build zone objects (deduplicated, preserving order)
        seen = set()
        zones: List[EnvironmentZone] = []
        for idx, zt in enumerate(zone_types_list):
            if zt not in seen:
                seen.add(zt)
                zones.append(_build_zone(key or environment_name, zt, idx))

        return ZonePlan(
            environment_name = environment_name,
            zones            = zones,
            zone_count       = len(zones),
            errors           = [],
        )

    def validate_zones(self, zone_plan: ZonePlan) -> List[str]:
        """Return a list of validation errors for the given ZonePlan."""
        errors: List[str] = []
        if zone_plan.zone_count == 0:
            errors.append("no zones defined")
        zone_types = {z.zone_type for z in zone_plan.zones}
        if "hero_zone" not in zone_types:
            errors.append("hero_zone is missing")
        if "entrance_zone" not in zone_types:
            errors.append("entrance_zone is missing")
        if "decoration_zone" not in zone_types:
            errors.append("decoration_zone is missing")
        if "atmosphere_zone" not in zone_types:
            errors.append("atmosphere_zone is missing")
        return errors

    def get_zone(self, zone_plan: ZonePlan, zone_type: str) -> Optional[EnvironmentZone]:
        """Return the first zone matching ``zone_type``, or None."""
        for z in zone_plan.zones:
            if z.zone_type == zone_type:
                return z
        return None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentZoneBuilder] = None
_LOCK = threading.Lock()


def get_environment_zone_builder() -> EnvironmentZoneBuilder:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = EnvironmentZoneBuilder()
        return _INSTANCE


def reset_environment_zone_builder_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
