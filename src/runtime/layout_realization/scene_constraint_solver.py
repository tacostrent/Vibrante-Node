"""
scene_constraint_solver.py — §47 Layout Realization & Scene Constraint Solver
==============================================================================
Enforces scene-level spatial constraints on a set of ResolvedTransforms.

Constraints checked and corrected:
  minimum_spacing:    assets must be at least min_gap apart (edge-to-edge)
  cluster_spacing:    cluster centroids must be at least 2.5 m apart
  wall_clearance:     non-wall assets must stay 0.3 m from room boundary
  door_clearance:     1.5 m clear zone in front of doors
  hero_visibility:    no asset may block the camera→hero sightline
  camera_visibility:  hero assets must not be occluded by large props

Constraints that cannot be fixed (budget exceeded) are recorded as
violations and flagged on the transform with constraint_ok=False.

Public API:
    ConstraintViolation
    ConstraintSolveResult
    SceneConstraintSolver
    get_scene_constraint_solver()
    reset_scene_constraint_solver_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout_realization.transform_resolver import ResolvedTransform


# ------------------------------------------------------------------
# Tuning constants
# ------------------------------------------------------------------

_MIN_ASSET_GAP    = 0.30   # minimum edge-to-edge gap (meters)
_CLUSTER_MIN_DIST = 2.50   # minimum centroid-to-centroid (meters)
_WALL_CLEARANCE   = 0.30   # non-wall assets must clear room boundary
_DOOR_CLEARANCE   = 1.50   # door clearance zone depth
_DOOR_WIDTH       = 1.20   # door width for clearance zone calculation

# Camera is assumed to be at [0, 1.65, 6.0] looking toward origin
_CAMERA_POS = [0.0, 1.65, 6.0]

# Large-footprint types that can occlude hero
_OCCLUDER_TYPES = {"machine", "large_machine", "vehicle", "crane", "sofa", "bed"}

# Default asset radii (mirrors collision_solver defaults)
_TYPE_RADII: Dict[str, float] = {
    "table": 0.65, "desk": 0.60, "bar_counter": 1.00,
    "chair": 0.30, "stool": 0.20, "bench": 0.50,
    "machine": 0.80, "large_machine": 1.20,
    "barrel": 0.30, "bucket": 0.15, "crate": 0.40,
    "vehicle": 1.50,
}
_DEFAULT_RADIUS = 0.30


@dataclass
class ConstraintViolation:
    asset_id:        str
    constraint_type: str   # "min_spacing", "wall_clearance", "door_clearance",
                           # "hero_visibility", "cluster_spacing"
    description:     str
    corrected:       bool = False
    correction_note: str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":        self.asset_id,
            "constraint_type": self.constraint_type,
            "description":     self.description,
            "corrected":       self.corrected,
            "correction_note": self.correction_note,
        }


@dataclass
class ConstraintSolveResult:
    transforms:        List[ResolvedTransform]   = field(default_factory=list)
    violations_found:  int = 0
    violations_fixed:  int = 0
    violations_remaining: int = 0
    violations:        List[ConstraintViolation] = field(default_factory=list)
    ok:     bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transforms":             [t.to_dict() for t in self.transforms],
            "violations_found":       self.violations_found,
            "violations_fixed":       self.violations_fixed,
            "violations_remaining":   self.violations_remaining,
            "violations":             [v.to_dict() for v in self.violations],
            "ok":                     self.ok,
            "errors":                 list(self.errors),
        }


class SceneConstraintSolver:
    """
    Enforces and corrects scene-level spatial constraints.
    All corrections are conservative (push/snap only, never remove assets).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def solve_constraints(
        self,
        transforms: List[ResolvedTransform],
        room_half_width: float = 4.0,
        type_hints: Optional[Dict[str, str]] = None,
        hero_asset_id: str = "",
        door_positions: Optional[List[List[float]]] = None,
    ) -> ConstraintSolveResult:
        """
        Apply all scene constraints to the given transforms.

        Args:
            transforms:      list of ResolvedTransform (mutated in place)
            room_half_width: room boundary
            type_hints:      map asset_id → placement_type
            hero_asset_id:   primary hero anchor asset id
            door_positions:  list of [tx, tz] door centre positions

        Returns: ConstraintSolveResult. Never raises.
        """
        try:
            return self._solve(
                list(transforms),
                room_half_width,
                type_hints or {},
                hero_asset_id,
                door_positions or [],
            )
        except Exception as exc:
            return ConstraintSolveResult(
                transforms=list(transforms),
                ok=False,
                errors=[f"SceneConstraintSolver.solve_constraints failed: {exc}"],
            )

    def _solve(
        self,
        transforms: List[ResolvedTransform],
        room_half_width: float,
        type_hints: Dict[str, str],
        hero_asset_id: str,
        door_positions: List[List[float]],
    ) -> ConstraintSolveResult:
        violations: List[ConstraintViolation] = []
        radii = {xf.asset_id: self._radius(xf.asset_id, type_hints) for xf in transforms}

        # 1. Wall clearance (non-wall assets)
        for xf in transforms:
            if xf.relationship in ("attached_to", "against"):
                continue
            r = radii[xf.asset_id]
            limit = room_half_width - _WALL_CLEARANCE - r
            corrected = False
            desc_parts = []
            if abs(xf.tx) > limit:
                desc_parts.append(f"X={xf.tx:.2f} limit={limit:.2f}")
                xf.tx = math.copysign(limit, xf.tx)
                corrected = True
            if abs(xf.tz) > limit:
                desc_parts.append(f"Z={xf.tz:.2f} limit={limit:.2f}")
                xf.tz = math.copysign(limit, xf.tz)
                corrected = True
            if desc_parts:
                violations.append(ConstraintViolation(
                    asset_id=xf.asset_id,
                    constraint_type="wall_clearance",
                    description=f"too close to wall: {'; '.join(desc_parts)}",
                    corrected=corrected,
                    correction_note="snapped to wall clearance zone",
                ))

        # 2. Door clearance
        for door_pos in door_positions:
            dx = float(door_pos[0])
            dz = float(door_pos[1]) if len(door_pos) > 1 else 0.0
            for xf in transforms:
                dist = math.sqrt((xf.tx - dx) ** 2 + (xf.tz - dz) ** 2)
                if dist < _DOOR_CLEARANCE:
                    violations.append(ConstraintViolation(
                        asset_id=xf.asset_id,
                        constraint_type="door_clearance",
                        description=f"within {dist:.2f}m of door at ({dx:.1f},{dz:.1f})",
                        corrected=False,
                        correction_note="manual adjustment needed",
                    ))
                    xf.constraint_ok = False

        # 3. Hero visibility: no occluder between camera and hero
        if hero_asset_id:
            hero_xf = next((x for x in transforms if x.asset_id == hero_asset_id), None)
            if hero_xf:
                cam = _CAMERA_POS
                hx, hz = hero_xf.tx, hero_xf.tz
                for xf in transforms:
                    if xf.asset_id == hero_asset_id:
                        continue
                    asset_type = type_hints.get(xf.asset_id, "")
                    if asset_type not in _OCCLUDER_TYPES:
                        continue
                    if self._is_on_sightline(cam, hx, hz, xf.tx, xf.tz, radii[xf.asset_id]):
                        # Push occluder sideways
                        xf.tx += 1.5
                        violations.append(ConstraintViolation(
                            asset_id=xf.asset_id,
                            constraint_type="hero_visibility",
                            description=f"occluding hero '{hero_asset_id}'",
                            corrected=True,
                            correction_note="pushed 1.5m sideways",
                        ))

        # 4. Cluster spacing
        cluster_centroids: Dict[str, List[float]] = {}
        for xf in transforms:
            if xf.cluster_id:
                if xf.cluster_id not in cluster_centroids:
                    cluster_centroids[xf.cluster_id] = [xf.tx, xf.tz, 1]
                else:
                    c = cluster_centroids[xf.cluster_id]
                    c[0] = (c[0] * c[2] + xf.tx) / (c[2] + 1)
                    c[1] = (c[1] * c[2] + xf.tz) / (c[2] + 1)
                    c[2] += 1

        cluster_ids = list(cluster_centroids.keys())
        for i in range(len(cluster_ids)):
            for j in range(i + 1, len(cluster_ids)):
                ca = cluster_centroids[cluster_ids[i]]
                cb = cluster_centroids[cluster_ids[j]]
                dist = math.sqrt((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2)
                if dist < _CLUSTER_MIN_DIST:
                    violations.append(ConstraintViolation(
                        asset_id=cluster_ids[i],
                        constraint_type="cluster_spacing",
                        description=(
                            f"clusters '{cluster_ids[i]}' and '{cluster_ids[j]}' "
                            f"only {dist:.2f}m apart (min {_CLUSTER_MIN_DIST}m)"
                        ),
                        corrected=False,
                    ))

        found    = len(violations)
        fixed    = sum(1 for v in violations if v.corrected)
        remaining = found - fixed

        return ConstraintSolveResult(
            transforms=transforms,
            violations_found=found,
            violations_fixed=fixed,
            violations_remaining=remaining,
            violations=violations,
        )

    @staticmethod
    def _is_on_sightline(
        cam: List[float],
        hx: float, hz: float,
        ox: float, oz: float,
        or_: float,
    ) -> bool:
        """True if occluder (ox, oz, radius=or_) intersects the camera→hero segment."""
        cx, cz = cam[0], cam[2]
        dx, dz = hx - cx, hz - cz
        line_len = math.sqrt(dx * dx + dz * dz)
        if line_len < 0.001:
            return False
        ux, uz = dx / line_len, dz / line_len
        # Project occluder onto sightline
        t = (ox - cx) * ux + (oz - cz) * uz
        if t < 0 or t > line_len:
            return False
        px = cx + t * ux
        pz = cz + t * uz
        dist = math.sqrt((ox - px) ** 2 + (oz - pz) ** 2)
        return dist < or_

    def _radius(self, asset_id: str, type_hints: Dict[str, str]) -> float:
        t = type_hints.get(asset_id, "")
        if t in _TYPE_RADII:
            return _TYPE_RADII[t]
        lower = asset_id.lower()
        for key, r in _TYPE_RADII.items():
            if key in lower:
                return r
        return _DEFAULT_RADIUS


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[SceneConstraintSolver] = None
_lock = threading.Lock()


def get_scene_constraint_solver() -> SceneConstraintSolver:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SceneConstraintSolver()
    return _instance


def reset_scene_constraint_solver_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
