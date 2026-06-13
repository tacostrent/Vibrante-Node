"""
Spatial Metadata (Tier 9.4 — Real Asset Spatial Intelligence)
=============================================================
SpatialMetadata stores the physical dimensions and placement semantics
of a real production asset: bounding box, footprint, placement radius,
unit system, placement type, and obstacle flags.

All dimensions are stored in meters after unit normalization.

DESIGN RULES:
  1. No Houdini imports.  No bridge calls.  Data model only.
  2. All dimensions are non-negative floats.
  3. placement_radius = max(bbox_x, bbox_z) / 2.0 by default.
  4. footprint_area = bbox_x * bbox_z.
  5. Never raises in public methods.

Public API:
    PLACEMENT_TYPES
    UNIT_SYSTEMS
    SpatialMetadata
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

PLACEMENT_TYPES = frozenset({
    "table", "chair", "bench", "bucket", "barrel",
    "machine", "crane", "pipe", "wall", "door",
    "lantern", "column", "platform", "vehicle", "terrain",
    "unknown",
})

UNIT_SYSTEMS = frozenset({
    "meters", "centimeters", "millimeters", "inches", "feet",
})

# Conversion factor to meters
_UNIT_TO_METERS: Dict[str, float] = {
    "meters":      1.0,
    "centimeters": 0.01,
    "millimeters": 0.001,
    "inches":      0.0254,
    "feet":        0.3048,
}


@dataclass
class SpatialMetadata:
    """Physical dimensions and placement semantics for one production asset."""

    asset_id:          str   = ""
    bbox_x:            float = 1.0    # width  (X axis, meters)
    bbox_y:            float = 1.0    # height (Y axis, meters)
    bbox_z:            float = 1.0    # depth  (Z axis, meters)
    footprint_area:    float = 1.0    # bbox_x * bbox_z
    placement_radius:  float = 0.5    # max(bbox_x, bbox_z) / 2.0
    world_scale:       float = 1.0
    unit_system:       str   = "meters"
    placement_type:    str   = "unknown"
    anchor_capable:    bool  = False
    walkable_obstacle: bool  = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":          self.asset_id,
            "bbox_x":            self.bbox_x,
            "bbox_y":            self.bbox_y,
            "bbox_z":            self.bbox_z,
            "footprint_area":    self.footprint_area,
            "placement_radius":  self.placement_radius,
            "world_scale":       self.world_scale,
            "unit_system":       self.unit_system,
            "placement_type":    self.placement_type,
            "anchor_capable":    self.anchor_capable,
            "walkable_obstacle": self.walkable_obstacle,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SpatialMetadata":
        return cls(
            asset_id=str(d.get("asset_id", "")),
            bbox_x=float(d.get("bbox_x", 1.0)),
            bbox_y=float(d.get("bbox_y", 1.0)),
            bbox_z=float(d.get("bbox_z", 1.0)),
            footprint_area=float(d.get("footprint_area", 1.0)),
            placement_radius=float(d.get("placement_radius", 0.5)),
            world_scale=float(d.get("world_scale", 1.0)),
            unit_system=str(d.get("unit_system", "meters")),
            placement_type=str(d.get("placement_type", "unknown")),
            anchor_capable=bool(d.get("anchor_capable", False)),
            walkable_obstacle=bool(d.get("walkable_obstacle", True)),
        )

    def normalized_to(self, target: str = "meters") -> "SpatialMetadata":
        """Return a copy with all dimensions converted to *target* unit system."""
        if target not in UNIT_SYSTEMS:
            target = "meters"
        if self.unit_system == target:
            return SpatialMetadata(**self.to_dict())
        factor = _UNIT_TO_METERS.get(self.unit_system, 1.0) / _UNIT_TO_METERS.get(target, 1.0)
        bx = max(0.0, self.bbox_x * factor)
        by = max(0.0, self.bbox_y * factor)
        bz = max(0.0, self.bbox_z * factor)
        return SpatialMetadata(
            asset_id=self.asset_id,
            bbox_x=bx,
            bbox_y=by,
            bbox_z=bz,
            footprint_area=bx * bz,
            placement_radius=max(bx, bz) / 2.0,
            world_scale=self.world_scale,
            unit_system=target,
            placement_type=self.placement_type,
            anchor_capable=self.anchor_capable,
            walkable_obstacle=self.walkable_obstacle,
        )
