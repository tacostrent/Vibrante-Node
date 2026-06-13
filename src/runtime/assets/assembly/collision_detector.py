"""
Collision Detector (Tier 9.4 — Real Asset Spatial Intelligence)
===============================================================
AABB (Axis-Aligned Bounding Box) collision detection for production
asset placement.  Detects overlapping assets and produces collision
reports used by the placement optimizer and spatial review.

DESIGN RULES:
  1. No Houdini imports.  No bridge calls.  Geometry math only.
  2. All positions and dimensions in meters.
  3. Never raises in public methods.
  4. Pure math — deterministic, no randomness.

Public API:
    CollisionPair
    CollisionReport
    CollisionDetector
    get_collision_detector()
    reset_collision_detector_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.assets.assembly.spatial_metadata import SpatialMetadata


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CollisionPair:
    """Two assets whose AABB volumes intersect."""

    asset_a:           str
    asset_b:           str
    overlap_x:         float = 0.0   # penetration depth along X (m)
    overlap_y:         float = 0.0
    overlap_z:         float = 0.0
    separation_needed: float = 0.0   # minimum push to resolve collision (m)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_a":           self.asset_a,
            "asset_b":           self.asset_b,
            "overlap_x":         round(self.overlap_x, 4),
            "overlap_y":         round(self.overlap_y, 4),
            "overlap_z":         round(self.overlap_z, 4),
            "separation_needed": round(self.separation_needed, 4),
        }


@dataclass
class CollisionReport:
    """Summary of all AABB collisions detected in a scene."""

    collision_count: int = 0
    pairs:           List[CollisionPair] = field(default_factory=list)
    ok:              bool = True    # True means no collisions
    asset_ids:       List[str] = field(default_factory=list)  # affected assets

    def to_dict(self) -> Dict[str, Any]:
        return {
            "collision_count": self.collision_count,
            "pairs":           [p.to_dict() for p in self.pairs],
            "ok":              self.ok,
            "asset_ids":       list(self.asset_ids),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class CollisionDetector:
    """AABB collision detection for production asset placement."""

    def intersects(
        self,
        pos_a:  Tuple[float, float, float],
        meta_a: SpatialMetadata,
        pos_b:  Tuple[float, float, float],
        meta_b: SpatialMetadata,
    ) -> bool:
        """
        Return True if two AABB volumes overlap.
        Touching (zero overlap) is NOT a collision.
        All inputs in meters.
        """
        half_ax = meta_a.bbox_x / 2.0
        half_ay = meta_a.bbox_y / 2.0
        half_az = meta_a.bbox_z / 2.0
        half_bx = meta_b.bbox_x / 2.0
        half_by = meta_b.bbox_y / 2.0
        half_bz = meta_b.bbox_z / 2.0

        return (
            abs(pos_a[0] - pos_b[0]) < half_ax + half_bx and
            abs(pos_a[1] - pos_b[1]) < half_ay + half_by and
            abs(pos_a[2] - pos_b[2]) < half_az + half_bz
        )

    def intersects_any(
        self,
        pos:    Tuple[float, float, float],
        meta:   SpatialMetadata,
        placed: List[Tuple[Tuple[float, float, float], SpatialMetadata]],
    ) -> bool:
        """Return True if *meta* at *pos* intersects any already-placed asset."""
        for placed_pos, placed_meta in placed:
            if self.intersects(pos, meta, placed_pos, placed_meta):
                return True
        return False

    def validate_position(
        self,
        pos:    Tuple[float, float, float],
        meta:   SpatialMetadata,
        placed: List[Tuple[Tuple[float, float, float], SpatialMetadata]],
    ) -> Dict[str, Any]:
        """
        Check whether *meta* can be placed at *pos* without colliding
        with any already-placed asset.

        Returns {"valid": bool, "collisions": List[str]}.
        """
        collisions: List[str] = []
        for placed_pos, placed_meta in placed:
            if self.intersects(pos, meta, placed_pos, placed_meta):
                collisions.append(placed_meta.asset_id or "unnamed")
        return {"valid": len(collisions) == 0, "collisions": collisions}

    def validate_scene(
        self,
        placements: List[Tuple[str, Tuple[float, float, float], SpatialMetadata]],
    ) -> CollisionReport:
        """
        Check every pair of assets for AABB intersection.

        Args:
            placements: list of (asset_id, position_xyz, SpatialMetadata)

        Returns:
            CollisionReport with all detected pairs.  Never raises.
        """
        report = CollisionReport()
        try:
            n = len(placements)
            for i in range(n):
                id_a, pos_a, meta_a = placements[i]
                for j in range(i + 1, n):
                    id_b, pos_b, meta_b = placements[j]
                    if self.intersects(pos_a, meta_a, pos_b, meta_b):
                        ov_x = _overlap_1d(pos_a[0], meta_a.bbox_x, pos_b[0], meta_b.bbox_x)
                        ov_y = _overlap_1d(pos_a[1], meta_a.bbox_y, pos_b[1], meta_b.bbox_y)
                        ov_z = _overlap_1d(pos_a[2], meta_a.bbox_z, pos_b[2], meta_b.bbox_z)
                        sep  = min(ov_x, ov_y, ov_z)
                        report.pairs.append(CollisionPair(
                            asset_a=id_a, asset_b=id_b,
                            overlap_x=ov_x, overlap_y=ov_y, overlap_z=ov_z,
                            separation_needed=sep,
                        ))
                        if id_a not in report.asset_ids:
                            report.asset_ids.append(id_a)
                        if id_b not in report.asset_ids:
                            report.asset_ids.append(id_b)
            report.collision_count = len(report.pairs)
            report.ok = report.collision_count == 0
        except Exception:
            pass
        return report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _overlap_1d(ca: float, sa: float, cb: float, sb: float) -> float:
    """Penetration depth along one axis for two intervals."""
    return (sa / 2.0 + sb / 2.0) - abs(ca - cb)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_INSTANCE: Optional[CollisionDetector] = None
_INSTANCE_LOCK = threading.Lock()


def get_collision_detector() -> CollisionDetector:
    """Return the module-level singleton CollisionDetector."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = CollisionDetector()
    return _INSTANCE


def reset_collision_detector_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
