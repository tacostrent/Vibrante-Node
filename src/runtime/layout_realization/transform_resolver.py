"""
transform_resolver.py — §47 Layout Realization & Scene Constraint Solver
=========================================================================
Converts semantic positions (anchor positions, relative offsets, surface
heights, wall mounts) into explicit world-space transforms (tx, ty, tz,
rx, ry, rz, sx, sy, sz).

Rules:
  - Input is any combination of semantic hints (relationship, offset, surface)
  - Output is always a full 9-DOF transform dict
  - Y-up convention (ty = height above floor)
  - Deterministic — same input always produces same output

Public API:
    ResolvedTransform
    TransformResolver
    get_transform_resolver()
    reset_transform_resolver_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ResolvedTransform:
    """Full world-space transform for one asset in the realized scene."""
    asset_id:   str
    asset_name: str

    # World-space position (meters, Y-up)
    tx: float = 0.0
    ty: float = 0.0
    tz: float = 0.0

    # Rotation (degrees, Y-up)
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0

    # Uniform scale
    sx: float = 1.0
    sy: float = 1.0
    sz: float = 1.0

    # Semantic context
    parent_id:       str = ""
    relationship:    str = ""   # "around", "supports", "attached_to", etc.
    cluster_id:      str = ""

    # Real-world bbox half-extents (meters, world-space) — 0.0 if unknown
    # Populated from cooked geometry via from_houdini_bbox() + real-world scale.
    # Used by CollisionSolver for accurate AABB overlap detection.
    bbox_half_x: float = 0.0   # half-width  (X-axis)
    bbox_half_y: float = 0.0   # half-height (Y-axis)
    bbox_half_z: float = 0.0   # half-depth  (Z-axis)

    # Quality flags
    is_collision_free: bool = True
    constraint_ok:     bool = True
    notes:             str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":         self.asset_id,
            "asset_name":       self.asset_name,
            "tx": round(self.tx, 4),
            "ty": round(self.ty, 4),
            "tz": round(self.tz, 4),
            "rx": round(self.rx, 4),
            "ry": round(self.ry, 4),
            "rz": round(self.rz, 4),
            "sx": round(self.sx, 4),
            "sy": round(self.sy, 4),
            "sz": round(self.sz, 4),
            "bbox_half_x":        round(self.bbox_half_x, 4),
            "bbox_half_y":        round(self.bbox_half_y, 4),
            "bbox_half_z":        round(self.bbox_half_z, 4),
            "parent_id":          self.parent_id,
            "relationship":       self.relationship,
            "cluster_id":         self.cluster_id,
            "is_collision_free":  self.is_collision_free,
            "constraint_ok":      self.constraint_ok,
            "notes":              self.notes,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ResolvedTransform":
        return cls(
            asset_id=d.get("asset_id", ""),
            asset_name=d.get("asset_name", ""),
            tx=float(d.get("tx", 0.0)),
            ty=float(d.get("ty", 0.0)),
            tz=float(d.get("tz", 0.0)),
            rx=float(d.get("rx", 0.0)),
            ry=float(d.get("ry", 0.0)),
            rz=float(d.get("rz", 0.0)),
            sx=float(d.get("sx", 1.0)),
            sy=float(d.get("sy", 1.0)),
            sz=float(d.get("sz", 1.0)),
            parent_id=d.get("parent_id", ""),
            relationship=d.get("relationship", ""),
            cluster_id=d.get("cluster_id", ""),
            bbox_half_x=float(d.get("bbox_half_x", 0.0)),
            bbox_half_y=float(d.get("bbox_half_y", 0.0)),
            bbox_half_z=float(d.get("bbox_half_z", 0.0)),
            is_collision_free=bool(d.get("is_collision_free", True)),
            constraint_ok=bool(d.get("constraint_ok", True)),
            notes=d.get("notes", ""),
        )


class TransformResolver:
    """
    Resolves semantic layout data into world-space ResolvedTransform objects.

    Handles:
      - Anchor world positions (direct from LayoutPlan anchor_placements)
      - Cluster member transforms (relative position + anchor world pos)
      - Surface placements (world X/Z from host + surface Y)
      - Wall attachments (wall position + height + wall-normal → ry)
      - Standalone decorations (floor-level world position)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public resolve methods
    # ------------------------------------------------------------------

    def resolve_anchor(self, anchor: Dict[str, Any]) -> ResolvedTransform:
        """Convert an anchor placement dict to a world transform."""
        pos = anchor.get("position") or [0.0, 0.0, 0.0]
        return ResolvedTransform(
            asset_id=anchor.get("anchor_id", ""),
            asset_name=anchor.get("anchor_name", ""),
            tx=float(pos[0]),
            ty=float(pos[1]),
            tz=float(pos[2]),
            ry=0.0,
            relationship="anchor",
        )

    def resolve_cluster_member(
        self,
        member: Dict[str, Any],
        anchor_world_pos: List[float],
        cluster_id: str = "",
    ) -> ResolvedTransform:
        """Convert a cluster member dict (relative pos) to world transform."""
        rel = member.get("relative_position") or [0.0, 0.0, 0.0]
        orient = float(member.get("orientation_deg", 0.0))
        return ResolvedTransform(
            asset_id=member.get("asset_id", ""),
            asset_name=member.get("asset_name", ""),
            tx=float(anchor_world_pos[0]) + float(rel[0]),
            ty=float(anchor_world_pos[1]) + float(rel[1]),
            tz=float(anchor_world_pos[2]) + float(rel[2]),
            ry=orient,
            parent_id=member.get("anchor_asset_id", ""),
            relationship=member.get("relationship", "near"),
            cluster_id=cluster_id,
        )

    def resolve_surface_placement(
        self,
        placement: Dict[str, Any],
    ) -> ResolvedTransform:
        """Convert a surface placement dict to world transform."""
        pos = placement.get("position") or [0.0, 0.0, 0.0]
        return ResolvedTransform(
            asset_id=placement.get("child_asset_id", ""),
            asset_name=placement.get("child_asset_name", ""),
            tx=float(pos[0]),
            ty=float(pos[1]),
            tz=float(pos[2]),
            parent_id=placement.get("host_asset_id", ""),
            relationship="supports",
            notes=f"on {placement.get('surface_type', 'surface')} "
                  f"h={placement.get('surface_height', 0.0):.2f}m",
        )

    def resolve_wall_attachment(
        self,
        attachment: Dict[str, Any],
    ) -> ResolvedTransform:
        """Convert a wall attachment dict to world transform + ry from wall normal."""
        pos    = attachment.get("position") or [0.0, 1.60, -4.0]
        normal = attachment.get("wall_normal") or [0.0, 0.0, -1.0]
        ry     = self._wall_normal_to_ry(normal)
        return ResolvedTransform(
            asset_id=attachment.get("asset_id", ""),
            asset_name=attachment.get("asset_name", ""),
            tx=float(pos[0]),
            ty=float(pos[1]),
            tz=float(pos[2]),
            ry=ry,
            parent_id=attachment.get("wall_name", ""),
            relationship="attached_to",
            notes=f"wall={attachment.get('wall_name', '')} "
                  f"h={attachment.get('mount_height', 0.0):.2f}m",
        )

    def resolve_decoration(
        self,
        item: Dict[str, Any],
    ) -> ResolvedTransform:
        """Convert a decoration layout item to world transform."""
        pos = item.get("position") or [0.0, 0.0, 0.0]
        return ResolvedTransform(
            asset_id=item.get("asset_id", item.get("item_id", "")),
            asset_name=item.get("asset_name", ""),
            tx=float(pos[0]) if len(pos) > 0 else 0.0,
            ty=float(pos[1]) if len(pos) > 1 else 0.0,
            tz=float(pos[2]) if len(pos) > 2 else 0.0,
            relationship=item.get("placement_mode", "scattered"),
            notes=item.get("placement_target", ""),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wall_normal_to_ry(normal: List[float]) -> float:
        """Convert a wall outward normal vector to a Y rotation in degrees.

        Asset on wall faces INTO the room (opposite of outward normal).
          [0, 0, -1]  north wall  → ry=0   (faces south, +Z)
          [0, 0,  1]  south wall  → ry=180 (faces north, -Z)
          [-1, 0, 0]  east wall   → ry=90  (faces west, -X)
          [1,  0, 0]  west wall   → ry=270 (faces east, +X)

        Formula: atan2(-nx, -nz) gives the Y rotation whose front direction
        equals the negated normal (i.e., the asset faces into the room).
        """
        nx = float(normal[0])
        nz = float(normal[2]) if len(normal) > 2 else 0.0
        angle_rad = math.atan2(-nx, -nz)
        return math.degrees(angle_rad) % 360.0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[TransformResolver] = None
_lock = threading.Lock()


def get_transform_resolver() -> TransformResolver:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = TransformResolver()
    return _instance


def reset_transform_resolver_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
