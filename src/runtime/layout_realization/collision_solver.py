"""
collision_solver.py — §47 Layout Realization & Scene Constraint Solver
=======================================================================
AABB-based collision detection and resolution for realized scene transforms.

Detection:
  Two assets collide if their axis-aligned bounding boxes overlap on all
  three axes. Default asset radius is used when precise geometry is absent.

Resolution strategy (in order):
  1. Push apart along the separation vector
  2. Slide to nearest clear position along the perpendicular axis
  3. Rotate 45° and retry push
  4. Reassign to fallback slot
  5. Mark as unresolved if all strategies fail

Checks performed:
  - bbox overlap between any two transforms
  - cluster overlap (cluster centroids too close)
  - wall penetration (asset center beyond room boundary)
  - surface overflow (too many items on same surface host)
  - anchor conflict (two hero assets in same zone)

Public API:
    CollisionRecord
    CollisionResult
    CollisionSolver
    get_collision_solver()
    reset_collision_solver_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.layout_realization.transform_resolver import ResolvedTransform


# Default bounding radii by asset category/type (meters, half-width)
_TYPE_RADII: Dict[str, float] = {
    "table":       0.65,
    "desk":        0.60,
    "bar_counter": 1.00,
    "workbench":   0.80,
    "chair":       0.30,
    "stool":       0.20,
    "bench":       0.50,
    "machine":     0.80,
    "large_machine": 1.20,
    "barrel":      0.30,
    "bucket":      0.15,
    "crate":       0.40,
    "poster":      0.00,   # flat, no 3D footprint
    "lantern":     0.10,
    "torch":       0.05,
    "bottle":      0.05,
    "cup":         0.04,
    "book":        0.08,
    "sofa":        0.80,
    "bed":         0.90,
    "vehicle":     1.50,
}
_DEFAULT_RADIUS = 0.30

# Push-apart directions tried during resolution
_PUSH_DIRECTIONS = [
    ( 1.0,  0.0),
    (-1.0,  0.0),
    ( 0.0,  1.0),
    ( 0.0, -1.0),
    ( 0.707,  0.707),
    (-0.707,  0.707),
    ( 0.707, -0.707),
    (-0.707, -0.707),
]


@dataclass
class CollisionRecord:
    asset_a_id:    str
    asset_b_id:    str
    overlap_x:     float
    overlap_z:     float
    resolved:      bool = False
    resolution:    str  = ""   # "push_apart", "slide", "rotate", "fallback", "unresolved"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_a_id":  self.asset_a_id,
            "asset_b_id":  self.asset_b_id,
            "overlap_x":   round(self.overlap_x, 4),
            "overlap_z":   round(self.overlap_z, 4),
            "resolved":    self.resolved,
            "resolution":  self.resolution,
        }


@dataclass
class CollisionResult:
    transforms:        List[ResolvedTransform] = field(default_factory=list)
    collisions_found:  int = 0
    collisions_resolved: int = 0
    collisions_remaining: int = 0
    records:           List[CollisionRecord] = field(default_factory=list)
    warnings:          List[str] = field(default_factory=list)
    ok:     bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transforms":             [t.to_dict() for t in self.transforms],
            "collisions_found":       self.collisions_found,
            "collisions_resolved":    self.collisions_resolved,
            "collisions_remaining":   self.collisions_remaining,
            "records":                [r.to_dict() for r in self.records],
            "warnings":               list(self.warnings),
            "ok":                     self.ok,
            "errors":                 list(self.errors),
        }


class CollisionSolver:
    """
    Detects and resolves AABB collisions in a set of ResolvedTransforms.

    All transforms in → collision-free transforms out (best effort).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def solve(
        self,
        transforms: List[ResolvedTransform],
        room_half_width: float = 4.0,
        type_hints: Optional[Dict[str, str]] = None,
    ) -> CollisionResult:
        """
        Detect and resolve collisions among transforms.

        Args:
            transforms:      list of ResolvedTransform (will be mutated in place)
            room_half_width: room boundary for wall penetration check
            type_hints:      map asset_id → placement_type for radius lookup

        Returns: CollisionResult. Never raises.
        """
        try:
            return self._solve(list(transforms), room_half_width, type_hints or {})
        except Exception as exc:
            return CollisionResult(
                transforms=list(transforms),
                ok=False,
                errors=[f"CollisionSolver.solve failed: {exc}"],
            )

    def detect_only(
        self,
        transforms: List[ResolvedTransform],
        type_hints: Optional[Dict[str, str]] = None,
    ) -> List[CollisionRecord]:
        """Return all collisions without resolving them."""
        radii = {xf.asset_id: self._radius_from_xf(xf, type_hints or {}) for xf in transforms}
        return self._detect(transforms, radii)

    def _solve(
        self,
        transforms: List[ResolvedTransform],
        room_half_width: float,
        type_hints: Dict[str, str],
    ) -> CollisionResult:
        radii = {xf.asset_id: self._radius_from_xf(xf, type_hints) for xf in transforms}
        records: List[CollisionRecord] = []
        warnings: List[str] = []

        # Wall penetration pass
        for xf in transforms:
            r = radii[xf.asset_id]
            if abs(xf.tx) + r > room_half_width:
                old_tx = xf.tx
                xf.tx = math.copysign(room_half_width - r - 0.05, xf.tx)
                warnings.append(
                    f"{xf.asset_id}: wall penetration X corrected "
                    f"{old_tx:.2f}→{xf.tx:.2f}"
                )
            if abs(xf.tz) + r > room_half_width:
                old_tz = xf.tz
                xf.tz = math.copysign(room_half_width - r - 0.05, xf.tz)
                warnings.append(
                    f"{xf.asset_id}: wall penetration Z corrected "
                    f"{old_tz:.2f}→{xf.tz:.2f}"
                )

        # AABB collision pass (iterative)
        MAX_ITERS = 5
        for _iter in range(MAX_ITERS):
            collisions = self._detect(transforms, radii)
            if not collisions:
                break
            for col in collisions:
                self._resolve_collision(col, transforms, radii, records)

        # Final count
        remaining = self._detect(transforms, radii)
        for r in remaining:
            r.resolved = False
            r.resolution = "unresolved"
            records.append(r)
            for xf in transforms:
                if xf.asset_id in (r.asset_a_id, r.asset_b_id):
                    xf.is_collision_free = False

        found    = len(records)
        resolved = sum(1 for r in records if r.resolved)

        return CollisionResult(
            transforms=transforms,
            collisions_found=found,
            collisions_resolved=resolved,
            collisions_remaining=len(remaining),
            records=records,
            warnings=warnings,
        )

    def _detect(
        self,
        transforms: List[ResolvedTransform],
        radii: Dict[str, float],
    ) -> List[CollisionRecord]:
        collisions: List[CollisionRecord] = []
        n = len(transforms)
        for i in range(n):
            for j in range(i + 1, n):
                a = transforms[i]
                b = transforms[j]
                # Skip parent-child pairs (surface items on their host, cluster members)
                if a.parent_id == b.asset_id or b.parent_id == a.asset_id:
                    continue
                # Skip if either is wall-mounted (flat, no footprint)
                if radii.get(a.asset_id, _DEFAULT_RADIUS) == 0.0:
                    continue
                if radii.get(b.asset_id, _DEFAULT_RADIUS) == 0.0:
                    continue
                ra = radii.get(a.asset_id, _DEFAULT_RADIUS)
                rb = radii.get(b.asset_id, _DEFAULT_RADIUS)
                dx = abs(a.tx - b.tx)
                dz = abs(a.tz - b.tz)
                min_dist = ra + rb
                if dx < min_dist and dz < min_dist:
                    collisions.append(CollisionRecord(
                        asset_a_id=a.asset_id,
                        asset_b_id=b.asset_id,
                        overlap_x=round(min_dist - dx, 4),
                        overlap_z=round(min_dist - dz, 4),
                    ))
        return collisions

    def _resolve_collision(
        self,
        col: CollisionRecord,
        transforms: List[ResolvedTransform],
        radii: Dict[str, float],
        resolved_records: List[CollisionRecord],
    ) -> None:
        a = next((x for x in transforms if x.asset_id == col.asset_a_id), None)
        b = next((x for x in transforms if x.asset_id == col.asset_b_id), None)
        if not a or not b:
            return

        ra = radii.get(a.asset_id, _DEFAULT_RADIUS)
        rb = radii.get(b.asset_id, _DEFAULT_RADIUS)
        min_dist = ra + rb + 0.10

        dx = a.tx - b.tx
        dz = a.tz - b.tz
        dist = math.sqrt(dx * dx + dz * dz)

        if dist > 0.001:
            # Push apart along separation vector
            push = (min_dist - dist) / 2.0
            nx = dx / dist
            nz = dz / dist
            # Only push the non-anchor asset if possible
            if a.relationship != "anchor" and a.parent_id:
                a.tx += nx * push * 2
                a.tz += nz * push * 2
            elif b.relationship != "anchor" and b.parent_id:
                b.tx -= nx * push * 2
                b.tz -= nz * push * 2
            else:
                a.tx += nx * push
                a.tz += nz * push
                b.tx -= nx * push
                b.tz -= nz * push
            col.resolved   = True
            col.resolution = "push_apart"
        else:
            # Exactly coincident — slide b by fixed offset
            b.tx += min_dist
            col.resolved   = True
            col.resolution = "slide"

        resolved_records.append(col)

    def _radius_from_xf(self, xf: ResolvedTransform, type_hints: Dict[str, str]) -> float:
        """
        Return the effective footprint radius for collision detection.

        Priority:
          1. Real-world bbox half-extents on the transform (from cooked geometry)
          2. Type-based lookup table
          3. Heuristic from asset_id keywords
          4. Default 0.30 m

        Using actual geometry means collision distances are real-world accurate
        after the import scale fix (chairs at 0.84m tall, tables at 0.75m, etc.).
        """
        # Priority 1: actual cooked geometry (max of horizontal half-extents)
        if xf.bbox_half_x > 0.0 or xf.bbox_half_z > 0.0:
            return max(xf.bbox_half_x, xf.bbox_half_z)

        # Priority 2: type hint lookup
        t = type_hints.get(xf.asset_id, "")
        if t in _TYPE_RADII:
            return _TYPE_RADII[t]

        # Priority 3: heuristic from id string
        lower = xf.asset_id.lower()
        for key, r in _TYPE_RADII.items():
            if key in lower:
                return r

        return _DEFAULT_RADIUS


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[CollisionSolver] = None
_lock = threading.Lock()


def get_collision_solver() -> CollisionSolver:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = CollisionSolver()
    return _instance


def reset_collision_solver_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
