"""
architectural_plan.py — Tier 10.5 Structural Openings & Architectural Features
===============================================================================
All data models for Tier 10.5.

ArchitecturalOpening  — door or window cutout (boolean void in a wall)
FireplacePlacement    — fireplace attached to a wall face
BeamPlacement         — beam hanging from a ceiling anchor
WallShelfPlacement    — shelf mounted on a wall
ArchitecturalPlan     — the complete plan for one environment

Design rules:
  - No bridge calls. All models are pure data.
  - Deterministic — same input always produces the same plan.
  - Never raises in public methods.
  - dataclass + to_dict() / from_dict() on everything.
  - Houdini node name stored on every spec for traceability.

Node naming convention:
  /obj/sh_door_opening_{idx}
  /obj/sh_window_opening_{idx}
  /obj/sh_beam_{idx}
  /obj/sh_fireplace_{idx}
  /obj/sh_shelf_{idx}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


# ── Wall-face helpers ──────────────────────────────────────────────────────────

# Wall-face → outward normal
_WALL_NORMALS: Dict[str, List[float]] = {
    "north": [ 0.0, 0.0, -1.0],
    "south": [ 0.0, 0.0,  1.0],
    "east":  [ 1.0, 0.0,  0.0],
    "west":  [-1.0, 0.0,  0.0],
}

# Wall-face → room-interior forward vector (opposite of outward normal)
_INTERIOR_VECTORS: Dict[str, List[float]] = {
    "north": [ 0.0, 0.0,  1.0],
    "south": [ 0.0, 0.0, -1.0],
    "east":  [-1.0, 0.0,  0.0],
    "west":  [ 1.0, 0.0,  0.0],
}

WALL_THICKNESS: float = 0.40   # standard wall thickness (m)


# ── ArchitecturalOpening ──────────────────────────────────────────────────────

@dataclass
class ArchitecturalOpening:
    """
    A physical void (door or window cutout) in a wall plane.

    Geometry: box positioned at (cx, cy, cz) with dimensions
    (width × height × depth) where depth >= wall_thickness so the
    cut goes all the way through.

    Houdini node: /obj/{houdini_node_name} — a geo with a box SOP
    inside representing the void volume.
    """
    opening_id:        str
    opening_type:      str           # "door" | "window"
    anchor_id:         str
    wall_face:         str           # "north" | "south" | "east" | "west"
    wall_normal:       List[float]   # outward normal of the wall

    # World-space centre of the opening
    cx: float
    cy: float
    cz: float

    # Dimensions of the cutout
    width:  float
    height: float
    depth:  float     # along wall-normal direction (≥ wall_thickness)

    houdini_node_name: str = ""

    validated:  bool = True
    note:       str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opening_id":        self.opening_id,
            "opening_type":      self.opening_type,
            "anchor_id":         self.anchor_id,
            "wall_face":         self.wall_face,
            "wall_normal":       [round(v, 3) for v in self.wall_normal],
            "cx": round(self.cx, 4), "cy": round(self.cy, 4), "cz": round(self.cz, 4),
            "width":  round(self.width,  4),
            "height": round(self.height, 4),
            "depth":  round(self.depth,  4),
            "houdini_node_name": self.houdini_node_name,
            "validated":         self.validated,
            "note":              self.note,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ArchitecturalOpening":
        return cls(
            opening_id=d.get("opening_id", ""),
            opening_type=d.get("opening_type", ""),
            anchor_id=d.get("anchor_id", ""),
            wall_face=d.get("wall_face", ""),
            wall_normal=list(d.get("wall_normal", [0.0, 0.0, -1.0])),
            cx=float(d.get("cx", 0.0)), cy=float(d.get("cy", 0.0)), cz=float(d.get("cz", 0.0)),
            width=float(d.get("width", 0.9)),
            height=float(d.get("height", 2.1)),
            depth=float(d.get("depth", WALL_THICKNESS + 0.1)),
            houdini_node_name=d.get("houdini_node_name", ""),
            validated=bool(d.get("validated", True)),
            note=d.get("note", ""),
        )


# ── FireplacePlacement ─────────────────────────────────────────────────────────

@dataclass
class FireplacePlacement:
    """
    A fireplace attached to a wall face.

    Validation rules:
      back_face_distance ≤ 0.05m
      forward_axis == room interior vector for the wall
      center_offset ≈ 0 (centred on wall)
    """
    feature_id:          str
    anchor_id:           str
    wall_face:           str
    wall_normal:         List[float]
    forward_axis:        List[float]    # should equal _INTERIOR_VECTORS[wall_face]

    # World-space position of fireplace centre
    tx: float
    ty: float
    tz: float

    # Geometry
    width:  float
    height: float
    depth:  float   # front-to-back depth

    # Validation metrics
    wall_coord:          float   # coordinate of the wall plane along its axis
    back_face_coord:     float   # coordinate of the fireplace's rear face
    back_face_distance:  float   # abs(back_face_coord − wall_coord)  ≤ 0.05m
    center_offset:       float   # abs(lateral offset from wall centre)

    houdini_node_name: str = ""
    validated:         bool = True
    note:              str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id":         self.feature_id,
            "anchor_id":          self.anchor_id,
            "wall_face":          self.wall_face,
            "wall_normal":        [round(v, 3) for v in self.wall_normal],
            "forward_axis":       [round(v, 3) for v in self.forward_axis],
            "tx": round(self.tx, 4), "ty": round(self.ty, 4), "tz": round(self.tz, 4),
            "width":  round(self.width,  4),
            "height": round(self.height, 4),
            "depth":  round(self.depth,  4),
            "wall_coord":         round(self.wall_coord,         4),
            "back_face_coord":    round(self.back_face_coord,    4),
            "back_face_distance": round(self.back_face_distance, 4),
            "center_offset":      round(self.center_offset,      4),
            "houdini_node_name":  self.houdini_node_name,
            "validated":          self.validated,
            "note":               self.note,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FireplacePlacement":
        return cls(
            feature_id=d.get("feature_id", ""),
            anchor_id=d.get("anchor_id", ""),
            wall_face=d.get("wall_face", "north"),
            wall_normal=list(d.get("wall_normal", [0.0, 0.0, -1.0])),
            forward_axis=list(d.get("forward_axis", [0.0, 0.0, 1.0])),
            tx=float(d.get("tx", 0.0)),
            ty=float(d.get("ty", 0.0)),
            tz=float(d.get("tz", 0.0)),
            width=float(d.get("width", 1.2)),
            height=float(d.get("height", 1.5)),
            depth=float(d.get("depth", 0.6)),
            wall_coord=float(d.get("wall_coord", 0.0)),
            back_face_coord=float(d.get("back_face_coord", 0.0)),
            back_face_distance=float(d.get("back_face_distance", 0.0)),
            center_offset=float(d.get("center_offset", 0.0)),
            houdini_node_name=d.get("houdini_node_name", ""),
            validated=bool(d.get("validated", True)),
            note=d.get("note", ""),
        )


# ── BeamPlacement ──────────────────────────────────────────────────────────────

@dataclass
class BeamPlacement:
    """
    A structural beam hanging from a ceiling anchor.

    Validation rules:
      beam_top_y == ceiling_height (within 0.05m)
      NOT intersects_wall
      long_axis in ("x", "z")
    """
    feature_id:      str
    anchor_id:       str

    # World-space centre of beam
    tx: float
    ty: float
    tz: float

    # Geometry
    long_axis:  str    # "x" (spans room width) | "z" (spans room length)
    length:     float  # full span length along long_axis
    width:      float  # cross-section perpendicular to long_axis (horizontal)
    height:     float  # cross-section height (vertical)

    # Validation metrics
    ceiling_height: float
    beam_top_y:     float   # ty + height/2; should equal ceiling_height
    gap_to_ceiling: float   # abs(ceiling_height - beam_top_y)  ≤ 0.05m
    intersects_wall: bool   # True → FAIL
    is_below_ceiling: bool  # True → OK (beam entirely within room)

    houdini_node_name: str = ""
    validated:         bool = True
    note:              str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id":     self.feature_id,
            "anchor_id":      self.anchor_id,
            "tx": round(self.tx, 4), "ty": round(self.ty, 4), "tz": round(self.tz, 4),
            "long_axis":      self.long_axis,
            "length":         round(self.length,  4),
            "width":          round(self.width,   4),
            "height":         round(self.height,  4),
            "ceiling_height": round(self.ceiling_height, 4),
            "beam_top_y":     round(self.beam_top_y,     4),
            "gap_to_ceiling": round(self.gap_to_ceiling, 4),
            "intersects_wall":  self.intersects_wall,
            "is_below_ceiling": self.is_below_ceiling,
            "houdini_node_name": self.houdini_node_name,
            "validated":      self.validated,
            "note":           self.note,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BeamPlacement":
        return cls(
            feature_id=d.get("feature_id", ""),
            anchor_id=d.get("anchor_id", ""),
            tx=float(d.get("tx", 0.0)),
            ty=float(d.get("ty", 0.0)),
            tz=float(d.get("tz", 0.0)),
            long_axis=d.get("long_axis", "z"),
            length=float(d.get("length", 10.0)),
            width=float(d.get("width", 0.20)),
            height=float(d.get("height", 0.30)),
            ceiling_height=float(d.get("ceiling_height", 4.0)),
            beam_top_y=float(d.get("beam_top_y", 4.0)),
            gap_to_ceiling=float(d.get("gap_to_ceiling", 0.0)),
            intersects_wall=bool(d.get("intersects_wall", False)),
            is_below_ceiling=bool(d.get("is_below_ceiling", True)),
            houdini_node_name=d.get("houdini_node_name", ""),
            validated=bool(d.get("validated", True)),
            note=d.get("note", ""),
        )


# ── WallShelfPlacement ─────────────────────────────────────────────────────────

@dataclass
class WallShelfPlacement:
    """
    A shelf mounted on a wall at a specific height.

    Validation rules:
      NOT is_floating (must be parented to a wall attachment point)
      ty > 0 (above floor)
    """
    feature_id:   str
    anchor_id:    str
    wall_face:    str

    # World-space position of shelf centre
    tx: float
    ty: float   # mount height (centre of shelf)
    tz: float

    # Geometry
    width:     float
    depth:     float      # protrusion from wall
    thickness: float      # shelf thickness

    # Validation
    wall_coord:  float    # coordinate of the wall plane
    is_floating: bool     # True → FAIL

    houdini_node_name: str = ""
    validated:         bool = True
    note:              str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id":  self.feature_id,
            "anchor_id":   self.anchor_id,
            "wall_face":   self.wall_face,
            "tx": round(self.tx, 4), "ty": round(self.ty, 4), "tz": round(self.tz, 4),
            "width":       round(self.width,     4),
            "depth":       round(self.depth,     4),
            "thickness":   round(self.thickness, 4),
            "wall_coord":  round(self.wall_coord, 4),
            "is_floating": self.is_floating,
            "houdini_node_name": self.houdini_node_name,
            "validated":   self.validated,
            "note":        self.note,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WallShelfPlacement":
        return cls(
            feature_id=d.get("feature_id", ""),
            anchor_id=d.get("anchor_id", ""),
            wall_face=d.get("wall_face", ""),
            tx=float(d.get("tx", 0.0)),
            ty=float(d.get("ty", 1.40)),
            tz=float(d.get("tz", 0.0)),
            width=float(d.get("width", 1.0)),
            depth=float(d.get("depth", 0.30)),
            thickness=float(d.get("thickness", 0.05)),
            wall_coord=float(d.get("wall_coord", 0.0)),
            is_floating=bool(d.get("is_floating", False)),
            houdini_node_name=d.get("houdini_node_name", ""),
            validated=bool(d.get("validated", True)),
            note=d.get("note", ""),
        )


# ── ArchitecturalPlan ──────────────────────────────────────────────────────────

@dataclass
class ArchitecturalPlan:
    """
    Complete architectural feature plan for one environment.

    Built by ArchitecturalPlanBuilder from EnvironmentShell + blueprint anchors.
    Validated by EnvironmentArchitectureReview.
    Realized to Houdini geometry by ArchitecturalFeatureRealizer.
    """
    environment:          str

    door_openings:        List[ArchitecturalOpening]   = field(default_factory=list)
    window_openings:      List[ArchitecturalOpening]   = field(default_factory=list)
    fireplace_placements: List[FireplacePlacement]     = field(default_factory=list)
    beam_placements:      List[BeamPlacement]          = field(default_factory=list)
    shelf_placements:     List[WallShelfPlacement]     = field(default_factory=list)

    # Room geometry (from shell / blueprint)
    room_width:   float = 10.0
    room_length:  float = 12.0
    room_height:  float = 4.0
    is_outdoor:   bool  = False

    ok:     bool       = True
    errors: List[str]  = field(default_factory=list)

    @property
    def total_features(self) -> int:
        return (
            len(self.door_openings) + len(self.window_openings)
            + len(self.fireplace_placements) + len(self.beam_placements)
            + len(self.shelf_placements)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":          self.environment,
            "door_openings":        [o.to_dict() for o in self.door_openings],
            "window_openings":      [o.to_dict() for o in self.window_openings],
            "fireplace_placements": [f.to_dict() for f in self.fireplace_placements],
            "beam_placements":      [b.to_dict() for b in self.beam_placements],
            "shelf_placements":     [s.to_dict() for s in self.shelf_placements],
            "room_width":   round(self.room_width,  4),
            "room_length":  round(self.room_length, 4),
            "room_height":  round(self.room_height, 4),
            "is_outdoor":   self.is_outdoor,
            "total_features": self.total_features,
            "ok":           self.ok,
            "errors":       list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ArchitecturalPlan":
        return cls(
            environment=d.get("environment", ""),
            door_openings=[ArchitecturalOpening.from_dict(o) for o in d.get("door_openings", [])],
            window_openings=[ArchitecturalOpening.from_dict(o) for o in d.get("window_openings", [])],
            fireplace_placements=[FireplacePlacement.from_dict(f) for f in d.get("fireplace_placements", [])],
            beam_placements=[BeamPlacement.from_dict(b) for b in d.get("beam_placements", [])],
            shelf_placements=[WallShelfPlacement.from_dict(s) for s in d.get("shelf_placements", [])],
            room_width=float(d.get("room_width", 10.0)),
            room_length=float(d.get("room_length", 12.0)),
            room_height=float(d.get("room_height", 4.0)),
            is_outdoor=bool(d.get("is_outdoor", False)),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors", [])),
        )
