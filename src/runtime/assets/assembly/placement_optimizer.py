"""
Placement Optimizer (Tier 9.4 — Real Asset Spatial Intelligence)
================================================================
Finds valid, collision-free, clearance-compliant world-space positions
for production assets.  All candidate generation is deterministic.

Algorithm per asset:
  1. Try the proposed slot position.
  2. If invalid (collision or clearance violation), expand search in a
     deterministic grid of candidate offsets (radii × angles).
  3. Accept the first valid candidate found.
  4. If no valid candidate exists within N_MAX_ATTEMPTS, keep the
     original position and record a warning.

DESIGN RULES:
  1. No Houdini imports.  No bridge calls.  Geometry math only.
  2. Fully deterministic — same inputs → same output every time.
  3. Never raises in public methods.

Public API:
    OptimizedPlacement
    OptimizationPlan
    PlacementOptimizer
    get_placement_optimizer()
    reset_placement_optimizer_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.assets.assembly.spatial_metadata import SpatialMetadata
from src.runtime.assets.assembly.collision_detector import get_collision_detector
from src.runtime.assets.assembly.clearance_validator import get_clearance_validator

# Candidate search parameters
_SEARCH_RADII  = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0]   # metres
_ANGLE_STEPS   = [0.0, 90.0, 180.0, 270.0, 45.0, 135.0, 225.0, 315.0]   # degrees
_N_MAX_ATTEMPTS = len(_SEARCH_RADII) * len(_ANGLE_STEPS) + 1


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class OptimizedPlacement:
    """Optimization result for one asset."""

    asset_id:     str
    original_pos: Tuple[float, float, float]
    final_pos:    Tuple[float, float, float]
    repositioned: bool  = False
    attempts:     int   = 1
    ok:           bool  = True
    reason:       str   = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":     self.asset_id,
            "original_pos": list(self.original_pos),
            "final_pos":    list(self.final_pos),
            "repositioned": self.repositioned,
            "attempts":     self.attempts,
            "ok":           self.ok,
            "reason":       self.reason,
        }


@dataclass
class OptimizationPlan:
    """Optimization results for an entire placement plan."""

    total_assets:       int = 0
    repositioned_count: int = 0
    failed_count:       int = 0
    placements:         List[OptimizedPlacement] = field(default_factory=list)
    ok:                 bool = True
    errors:             List[str] = field(default_factory=list)
    warnings:           List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_assets":       self.total_assets,
            "repositioned_count": self.repositioned_count,
            "failed_count":       self.failed_count,
            "placements":         [p.to_dict() for p in self.placements],
            "ok":                 self.ok,
            "errors":             list(self.errors),
            "warnings":           list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PlacementOptimizer:
    """
    Finds valid, collision-free positions for production assets.
    All candidate positions are computed deterministically.
    """

    def find_valid_position(
        self,
        proposed_pos: Tuple[float, float, float],
        meta:         SpatialMetadata,
        placed:       List[Tuple[Tuple[float, float, float], SpatialMetadata]],
    ) -> Tuple[bool, Tuple[float, float, float], int]:
        """
        Find a valid position for *meta* near *proposed_pos*.

        Returns (found: bool, final_position, attempts_used).
        """
        detector  = get_collision_detector()
        validator = get_clearance_validator()

        # Attempt 1: original slot position
        if _is_valid(proposed_pos, meta, placed, detector, validator):
            return (True, proposed_pos, 1)

        # Attempts 2…N: expanding grid search
        attempts = 1
        for radius in _SEARCH_RADII:
            for angle_deg in _ANGLE_STEPS:
                rad = math.radians(angle_deg)
                candidate: Tuple[float, float, float] = (
                    proposed_pos[0] + radius * math.cos(rad),
                    proposed_pos[1],
                    proposed_pos[2] + radius * math.sin(rad),
                )
                attempts += 1
                if _is_valid(candidate, meta, placed, detector, validator):
                    return (True, candidate, attempts)

        return (False, proposed_pos, attempts)

    def resolve_collision(
        self,
        pos_a:  Tuple[float, float, float],
        meta_a: SpatialMetadata,
        pos_b:  Tuple[float, float, float],
        meta_b: SpatialMetadata,
    ) -> Tuple[float, float, float]:
        """
        Suggest a new position for *asset_a* to resolve its collision with
        *asset_b*.  Pushes *a* away from *b* along the X-Z plane.
        """
        dx   = pos_a[0] - pos_b[0]
        dz   = pos_a[2] - pos_b[2]
        dist = math.sqrt(dx * dx + dz * dz) or 1.0
        required = meta_a.placement_radius + meta_b.placement_radius + 0.1  # 10 cm buffer
        if dist >= required:
            return pos_a
        push = required - dist
        nx   = dx / dist
        nz   = dz / dist
        return (
            pos_a[0] + nx * push,
            pos_a[1],
            pos_a[2] + nz * push,
        )

    def expand_search_radius(self, current_radius: float) -> float:
        """Return the next predefined search radius larger than *current_radius*."""
        for r in _SEARCH_RADII:
            if r > current_radius:
                return r
        return current_radius + 1.0

    def optimize_layout(
        self,
        placements: List[Tuple[str, Tuple[float, float, float], SpatialMetadata]],
    ) -> OptimizationPlan:
        """
        Optimize positions for all assets ensuring no collisions and
        sufficient clearance between each consecutive pair.

        Args:
            placements: list of (asset_id, proposed_position_xyz, SpatialMetadata)

        Returns:
            OptimizationPlan.  Never raises.
        """
        plan = OptimizationPlan(total_assets=len(placements))
        placed: List[Tuple[Tuple[float, float, float], SpatialMetadata]] = []

        try:
            for asset_id, proposed_pos, meta in placements:
                found, final_pos, attempts = self.find_valid_position(
                    proposed_pos, meta, placed
                )
                repositioned = (final_pos != proposed_pos)

                if not found:
                    plan.failed_count += 1
                    plan.warnings.append(
                        f"Could not find collision-free position for '{asset_id}' "
                        f"after {attempts} attempt(s) — kept original position."
                    )
                elif repositioned:
                    plan.repositioned_count += 1

                reason = (
                    "repositioned" if repositioned
                    else ("failed_no_valid_slot" if not found else "original_ok")
                )
                plan.placements.append(OptimizedPlacement(
                    asset_id=asset_id,
                    original_pos=proposed_pos,
                    final_pos=final_pos,
                    repositioned=repositioned,
                    attempts=attempts,
                    ok=found or (not repositioned),
                    reason=reason,
                ))
                placed.append((final_pos, meta))

        except Exception as exc:
            plan.errors.append(f"Optimization failed: {exc}")
            plan.ok = False

        plan.ok = plan.ok and not plan.errors
        return plan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_valid(
    pos:       Tuple[float, float, float],
    meta:      SpatialMetadata,
    placed:    List[Tuple[Tuple[float, float, float], SpatialMetadata]],
    detector,
    validator,
) -> bool:
    """True if *pos* is collision-free AND meets clearance for all placed assets."""
    for placed_pos, placed_meta in placed:
        if detector.intersects(pos, meta, placed_pos, placed_meta):
            return False
        check = validator.validate_clearance(pos, meta, placed_pos, placed_meta)
        if not check["ok"]:
            return False
    return True


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_INSTANCE: Optional[PlacementOptimizer] = None
_INSTANCE_LOCK = threading.Lock()


def get_placement_optimizer() -> PlacementOptimizer:
    """Return the module-level singleton PlacementOptimizer."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = PlacementOptimizer()
    return _INSTANCE


def reset_placement_optimizer_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
