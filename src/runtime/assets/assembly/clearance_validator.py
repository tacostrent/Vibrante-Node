"""
Clearance Validator (Tier 9.4 — Real Asset Spatial Intelligence)
================================================================
Enforces minimum separation distances (edge-to-edge) between asset
placement types.  Clearance = center_distance − sum_of_placement_radii.

DESIGN RULES:
  1. No Houdini imports.  No bridge calls.  Math only.
  2. All distances in meters.
  3. Default minimum clearance: 0.3 m between any two assets.
  4. Rule lookup is order-insensitive (pair is alphabetically sorted).
  5. Never raises in public methods.

Public API:
    ClearanceViolation
    ClearanceReport
    ClearanceValidator
    get_clearance_validator()
    reset_clearance_validator_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.assets.assembly.spatial_metadata import SpatialMetadata

# ---------------------------------------------------------------------------
# Clearance rule table
# Key: alphabetically sorted (type_a, type_b) pair
# Value: minimum edge-to-edge clearance in meters
# ---------------------------------------------------------------------------
_CLEARANCE_RULES: Dict[Tuple[str, str], float] = {
    ("barrel",   "barrel"):   0.5,
    ("barrel",   "machine"):  1.5,
    ("barrel",   "wall"):     0.3,
    ("bucket",   "bucket"):   0.2,
    ("chair",    "chair"):    0.4,
    ("column",   "column"):   1.5,
    ("crane",    "crane"):    5.0,
    ("crane",    "wall"):     2.0,
    ("door",     "machine"):  1.5,
    ("door",     "vehicle"):  2.0,
    ("machine",  "machine"):  2.0,
    ("machine",  "wall"):     1.0,
    ("platform", "platform"): 0.5,
    ("table",    "table"):    1.0,
    ("table",    "wall"):     0.5,
    ("vehicle",  "machine"):  2.0,
    ("vehicle",  "vehicle"):  2.5,
    ("vehicle",  "wall"):     1.0,
}

_DEFAULT_CLEARANCE = 0.3  # meters — fallback for any unlisted pair


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ClearanceViolation:
    """A pair of assets that are closer together than their required clearance."""

    asset_a:            str
    asset_b:            str
    type_a:             str
    type_b:             str
    actual_clearance:   float   # edge-to-edge distance (m)
    required_clearance: float
    shortfall:          float   # required − actual

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_a":            self.asset_a,
            "asset_b":            self.asset_b,
            "type_a":             self.type_a,
            "type_b":             self.type_b,
            "actual_clearance":   round(self.actual_clearance, 4),
            "required_clearance": round(self.required_clearance, 4),
            "shortfall":          round(self.shortfall, 4),
        }


@dataclass
class ClearanceReport:
    """Summary of all clearance violations in a scene."""

    violation_count: int = 0
    violations:      List[ClearanceViolation] = field(default_factory=list)
    ok:              bool = True   # True means all clearances satisfied

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violation_count": self.violation_count,
            "violations":      [v.to_dict() for v in self.violations],
            "ok":              self.ok,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ClearanceValidator:
    """Validates minimum edge-to-edge clearance distances between placed assets."""

    def get_clearance_requirement(self, type_a: str, type_b: str) -> float:
        """Return the required edge-to-edge clearance (m) for this type pair."""
        pair: Tuple[str, str] = tuple(sorted([type_a, type_b]))  # type: ignore[assignment]
        return _CLEARANCE_RULES.get(pair, _DEFAULT_CLEARANCE)

    def validate_clearance(
        self,
        pos_a:  Tuple[float, float, float],
        meta_a: SpatialMetadata,
        pos_b:  Tuple[float, float, float],
        meta_b: SpatialMetadata,
    ) -> Dict[str, Any]:
        """
        Check edge-to-edge clearance between two assets.

        Returns {"ok": bool, "actual": float, "required": float, "shortfall": float}.
        """
        center_dist = math.sqrt(
            (pos_a[0] - pos_b[0]) ** 2 +
            (pos_a[1] - pos_b[1]) ** 2 +
            (pos_a[2] - pos_b[2]) ** 2
        )
        edge_to_edge = center_dist - meta_a.placement_radius - meta_b.placement_radius
        required     = self.get_clearance_requirement(
            meta_a.placement_type, meta_b.placement_type,
        )
        shortfall = max(0.0, required - edge_to_edge)
        return {
            "ok":       edge_to_edge >= required,
            "actual":   edge_to_edge,
            "required": required,
            "shortfall": shortfall,
        }

    def validate_scene_clearance(
        self,
        placements: List[Tuple[str, Tuple[float, float, float], SpatialMetadata]],
    ) -> ClearanceReport:
        """
        Check all pairs in *placements* for clearance violations.

        Args:
            placements: list of (asset_id, position_xyz, SpatialMetadata)

        Returns:
            ClearanceReport.  Never raises.
        """
        report = ClearanceReport()
        try:
            n = len(placements)
            for i in range(n):
                id_a, pos_a, meta_a = placements[i]
                for j in range(i + 1, n):
                    id_b, pos_b, meta_b = placements[j]
                    check = self.validate_clearance(pos_a, meta_a, pos_b, meta_b)
                    if not check["ok"]:
                        report.violations.append(ClearanceViolation(
                            asset_a=id_a,
                            asset_b=id_b,
                            type_a=meta_a.placement_type,
                            type_b=meta_b.placement_type,
                            actual_clearance=check["actual"],
                            required_clearance=check["required"],
                            shortfall=check["shortfall"],
                        ))
            report.violation_count = len(report.violations)
            report.ok = report.violation_count == 0
        except Exception:
            pass
        return report


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_INSTANCE: Optional[ClearanceValidator] = None
_INSTANCE_LOCK = threading.Lock()


def get_clearance_validator() -> ClearanceValidator:
    """Return the module-level singleton ClearanceValidator."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = ClearanceValidator()
    return _INSTANCE


def reset_clearance_validator_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
