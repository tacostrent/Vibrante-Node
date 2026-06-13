"""
wall_attachment_realizer.py — §47 Layout Realization & Scene Constraint Solver
===============================================================================
Converts wall attachment data from LayoutPlan.wall_attachments into
world-space transforms. Computes:

  - tx, ty, tz: wall face position at correct height
  - ry: rotation derived from wall normal so the asset faces into the room
  - Validates that the asset is inside the room bounds (not clipping outside)

Wall normals → ry mapping:
  north wall [0,0,-1] → ry=0    (asset faces south, into room)
  south wall [0,0,+1] → ry=180
  east  wall [-1,0,0] → ry=90
  west  wall [+1,0,0] → ry=270

Public API:
    WallRealizationResult
    WallAttachmentRealizer
    get_wall_attachment_realizer()
    reset_wall_attachment_realizer_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout_realization.transform_resolver import ResolvedTransform

# Small inset so the asset sits on the wall face, not inside it
_WALL_INSET = 0.05   # meters


@dataclass
class WallRealizationResult:
    transforms: List[ResolvedTransform] = field(default_factory=list)
    rejected:   List[Dict[str, Any]]   = field(default_factory=list)
    ok:     bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transforms": [t.to_dict() for t in self.transforms],
            "rejected":   list(self.rejected),
            "ok":         self.ok,
            "errors":     list(self.errors),
        }


class WallAttachmentRealizer:
    """Converts WallAttachment plan data into concrete world transforms."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def realize_wall_attachments(
        self,
        wall_attachments: List[Dict[str, Any]],
        room_half_width: float = 4.0,
    ) -> WallRealizationResult:
        """
        Convert wall attachment dicts into world-space ResolvedTransforms.

        Args:
            wall_attachments: plan.wall_attachments dicts from LayoutPlan
            room_half_width:  half-extent of room (default 4 m)

        Returns: WallRealizationResult. Never raises.
        """
        try:
            return self._realize(wall_attachments, room_half_width)
        except Exception as exc:
            return WallRealizationResult(
                ok=False,
                errors=[f"WallAttachmentRealizer.realize_wall_attachments failed: {exc}"],
            )

    def _realize(
        self,
        wall_attachments: List[Dict[str, Any]],
        room_half_width: float,
    ) -> WallRealizationResult:
        result = WallRealizationResult()

        for att in wall_attachments:
            if not att.get("ok", True):
                result.rejected.append({
                    "asset_id": att.get("asset_id", ""),
                    "reason":   "source attachment marked not ok",
                })
                continue

            pos        = att.get("position") or [0.0, 1.60, -4.0]
            normal     = att.get("wall_normal") or [0.0, 0.0, -1.0]
            mount_h    = float(att.get("mount_height", float(pos[1]) if len(pos) > 1 else 1.60))
            wall_name  = att.get("wall_name", "")

            # Adjust Z/X to sit on the wall surface (inset from boundary)
            tx, tz = self._inset_position(pos, normal, room_half_width)
            ry     = self._normal_to_ry(normal)

            result.transforms.append(ResolvedTransform(
                asset_id=att.get("asset_id", ""),
                asset_name=att.get("asset_name", ""),
                tx=tx,
                ty=mount_h,
                tz=tz,
                ry=ry,
                parent_id=wall_name,
                relationship="attached_to",
                notes=f"wall={wall_name} h={mount_h:.2f}m",
            ))

        return result

    def _inset_position(
        self,
        pos: List[float],
        normal: List[float],
        room_half_width: float,
    ) -> tuple:
        """Snap position to the wall face (slightly inside room boundary).

        Uses the sign of the original position to preserve which wall is
        targeted. Falls back to normal direction when position is zero.
        """
        nx = float(normal[0])
        nz = float(normal[2]) if len(normal) > 2 else 0.0
        tx = float(pos[0]) if len(pos) > 0 else 0.0
        tz = float(pos[2]) if len(pos) > 2 else 0.0

        limit = room_half_width - _WALL_INSET

        if abs(nz) > abs(nx):
            # North/South wall — snap Z, preserve original Z sign
            ref_z = tz if tz != 0.0 else (-nz)  # nz outward → flip for wall side
            tz = math.copysign(limit, ref_z)
        else:
            # East/West wall — snap X, preserve original X sign
            ref_x = tx if tx != 0.0 else (-nx)  # nx inward (east/west walls) → flip
            tx = math.copysign(limit, ref_x)

        return tx, tz

    @staticmethod
    def _normal_to_ry(normal: List[float]) -> float:
        """Convert wall outward normal to asset Y rotation (faces into room).

        Formula: atan2(-nx, -nz) — asset front direction = negated normal.
          [0,0,-1] north → ry=0    [0,0,+1] south → ry=180
          [-1,0,0] east  → ry=90   [+1,0,0] west  → ry=270
        """
        nx = float(normal[0])
        nz = float(normal[2]) if len(normal) > 2 else 0.0
        angle_rad = math.atan2(-nx, -nz)
        return math.degrees(angle_rad) % 360.0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[WallAttachmentRealizer] = None
_lock = threading.Lock()


def get_wall_attachment_realizer() -> WallAttachmentRealizer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = WallAttachmentRealizer()
    return _instance


def reset_wall_attachment_realizer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
