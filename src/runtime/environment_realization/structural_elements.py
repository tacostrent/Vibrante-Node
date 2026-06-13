"""
structural_elements.py — §49 Structural Environment Realization
===============================================================
Core data types shared across all environment realization modules.

Public API:
    StructuralElement
    RoomShell
    EnvironmentRealizationPlan
    ELEMENT_TYPES
    MATERIAL_TYPES
    OPENING_TYPES
"""

from __future__ import annotations

import time
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ELEMENT_TYPES = frozenset({
    "floor", "ceiling", "wall",
    "door", "window", "archway", "vent", "service_opening",
    "beam", "column", "platform", "catwalk",
    "room_divider", "skylight", "loading_door",
})

MATERIAL_TYPES = frozenset({
    "wood", "wood_planks", "stone", "brick",
    "concrete", "cracked_concrete", "marble",
    "industrial_metal", "steel", "iron",
    "sci_fi_panel", "glass", "drywall",
    "sand", "dirt", "metal_grating",
    "plaster", "tile",
})

OPENING_TYPES = frozenset({
    "door", "window", "archway", "sliding_door",
    "swing_door", "loading_door", "skylight",
    "vent", "service_opening", "arrow_slit",
    "porthole", "hangar_opening",
})


@dataclass
class StructuralElement:
    """One discrete architectural element (wall, floor, door, beam, …)."""
    element_id:   str
    element_type: str       # from ELEMENT_TYPES
    environment:  str
    position:     List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    dimensions:   Dict[str, float] = field(default_factory=dict)  # width, height, depth/thickness
    rotation:     List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    material:     str = "concrete"
    wall_id:      str = ""   # parent wall for openings
    face:         str = ""   # "north", "south", "east", "west", "top", "bottom"
    is_structural: bool = True
    is_opening:   bool = False
    metadata:     Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id":   self.element_id,
            "element_type": self.element_type,
            "environment":  self.environment,
            "position":     [round(v, 4) for v in self.position],
            "dimensions":   {k: round(v, 4) for k, v in self.dimensions.items()},
            "rotation":     [round(v, 4) for v in self.rotation],
            "material":     self.material,
            "wall_id":      self.wall_id,
            "face":         self.face,
            "is_structural": self.is_structural,
            "is_opening":   self.is_opening,
            "metadata":     dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StructuralElement":
        return cls(
            element_id=d.get("element_id", ""),
            element_type=d.get("element_type", ""),
            environment=d.get("environment", ""),
            position=list(d.get("position", [0.0, 0.0, 0.0])),
            dimensions=dict(d.get("dimensions", {})),
            rotation=list(d.get("rotation", [0.0, 0.0, 0.0])),
            material=d.get("material", "concrete"),
            wall_id=d.get("wall_id", ""),
            face=d.get("face", ""),
            is_structural=bool(d.get("is_structural", True)),
            is_opening=bool(d.get("is_opening", False)),
            metadata=dict(d.get("metadata", {})),
        )


@dataclass
class RoomShell:
    """Complete architectural shell for one environment."""
    shell_id:    str = field(default_factory=lambda: f"shell_{uuid.uuid4().hex[:8]}")
    environment: str = ""

    # Room dimensions (meters)
    width:  float = 10.0
    height: float = 4.0
    depth:  float = 12.0

    # Primary material
    primary_material: str = "wood"

    # Structural layers
    floor:   Optional[StructuralElement] = None
    ceiling: Optional[StructuralElement] = None
    walls:   Dict[str, StructuralElement] = field(default_factory=dict)  # face → element
    openings:  List[StructuralElement] = field(default_factory=list)
    beams:     List[StructuralElement] = field(default_factory=list)
    columns:   List[StructuralElement] = field(default_factory=list)
    platforms: List[StructuralElement] = field(default_factory=list)

    # Metadata
    is_outdoor:  bool = False
    room_closed: bool = False   # floor + 4 walls + ceiling
    ok:     bool = True
    errors: List[str] = field(default_factory=list)

    def all_elements(self) -> List[StructuralElement]:
        """Return all elements as a flat list."""
        elems: List[StructuralElement] = []
        if self.floor:
            elems.append(self.floor)
        if self.ceiling:
            elems.append(self.ceiling)
        elems.extend(self.walls.values())
        elems.extend(self.openings)
        elems.extend(self.beams)
        elems.extend(self.columns)
        elems.extend(self.platforms)
        return elems

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shell_id":        self.shell_id,
            "environment":     self.environment,
            "width":           round(self.width, 4),
            "height":          round(self.height, 4),
            "depth":           round(self.depth, 4),
            "primary_material": self.primary_material,
            "floor":           self.floor.to_dict() if self.floor else None,
            "ceiling":         self.ceiling.to_dict() if self.ceiling else None,
            "walls":           {k: v.to_dict() for k, v in self.walls.items()},
            "openings":        [e.to_dict() for e in self.openings],
            "beams":           [e.to_dict() for e in self.beams],
            "columns":         [e.to_dict() for e in self.columns],
            "platforms":       [e.to_dict() for e in self.platforms],
            "is_outdoor":      self.is_outdoor,
            "room_closed":     self.room_closed,
            "ok":              self.ok,
            "errors":          list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoomShell":
        walls = {k: StructuralElement.from_dict(v) for k, v in d.get("walls", {}).items()}
        return cls(
            shell_id=d.get("shell_id", ""),
            environment=d.get("environment", ""),
            width=float(d.get("width", 10.0)),
            height=float(d.get("height", 4.0)),
            depth=float(d.get("depth", 12.0)),
            primary_material=d.get("primary_material", "wood"),
            floor=StructuralElement.from_dict(d["floor"]) if d.get("floor") else None,
            ceiling=StructuralElement.from_dict(d["ceiling"]) if d.get("ceiling") else None,
            walls=walls,
            openings=[StructuralElement.from_dict(e) for e in d.get("openings", [])],
            beams=[StructuralElement.from_dict(e) for e in d.get("beams", [])],
            columns=[StructuralElement.from_dict(e) for e in d.get("columns", [])],
            platforms=[StructuralElement.from_dict(e) for e in d.get("platforms", [])],
            is_outdoor=bool(d.get("is_outdoor", False)),
            room_closed=bool(d.get("room_closed", False)),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors", [])),
        )


@dataclass
class EnvironmentRealizationPlan:
    """Complete output of the environment realization pipeline."""
    plan_id:     str = field(default_factory=lambda: f"envplan_{uuid.uuid4().hex[:10]}")
    environment: str = ""

    room_shell:          Optional[RoomShell] = None
    structural_elements: List[StructuralElement] = field(default_factory=list)
    zone_regions:        List[Dict[str, Any]] = field(default_factory=list)
    transaction_ops:     List[Dict[str, Any]] = field(default_factory=list)

    # Counts
    wall_count:     int = 0
    floor_count:    int = 0
    ceiling_count:  int = 0
    door_count:     int = 0
    window_count:   int = 0
    beam_count:     int = 0
    column_count:   int = 0
    zone_count:     int = 0
    room_closed:    bool = False

    production_ready: bool = False
    ok:     bool = True
    errors: List[str] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id":             self.plan_id,
            "environment":         self.environment,
            "room_shell":          self.room_shell.to_dict() if self.room_shell else None,
            "structural_elements": [e.to_dict() for e in self.structural_elements],
            "zone_regions":        list(self.zone_regions),
            "transaction_ops":     list(self.transaction_ops),
            "wall_count":          self.wall_count,
            "floor_count":         self.floor_count,
            "ceiling_count":       self.ceiling_count,
            "door_count":          self.door_count,
            "window_count":        self.window_count,
            "beam_count":          self.beam_count,
            "column_count":        self.column_count,
            "zone_count":          self.zone_count,
            "room_closed":         self.room_closed,
            "production_ready":    self.production_ready,
            "ok":                  self.ok,
            "errors":              list(self.errors),
            "generated_at":        self.generated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentRealizationPlan":
        shell_d = d.get("room_shell")
        return cls(
            plan_id=d.get("plan_id", ""),
            environment=d.get("environment", ""),
            room_shell=RoomShell.from_dict(shell_d) if shell_d else None,
            structural_elements=[StructuralElement.from_dict(e) for e in d.get("structural_elements", [])],
            zone_regions=list(d.get("zone_regions", [])),
            transaction_ops=list(d.get("transaction_ops", [])),
            wall_count=int(d.get("wall_count", 0)),
            floor_count=int(d.get("floor_count", 0)),
            ceiling_count=int(d.get("ceiling_count", 0)),
            door_count=int(d.get("door_count", 0)),
            window_count=int(d.get("window_count", 0)),
            beam_count=int(d.get("beam_count", 0)),
            column_count=int(d.get("column_count", 0)),
            zone_count=int(d.get("zone_count", 0)),
            room_closed=bool(d.get("room_closed", False)),
            production_ready=bool(d.get("production_ready", False)),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors", [])),
            generated_at=float(d.get("generated_at", 0.0)),
        )
