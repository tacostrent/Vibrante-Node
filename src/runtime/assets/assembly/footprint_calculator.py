"""
Footprint Calculator (Tier 9.6 — Scale-Aware Spatial Placement)
================================================================
Calculates the real floor area occupied by an asset and derives clearance
radii used by the layout spacing engine to prevent intersections.

Footprint = bbox_x_m × bbox_z_m  (horizontal floor area, m²)

Clearance radius = max(bbox_x_m, bbox_z_m) / 2.0 + clearance_buffer
Zone radius      = clearance_radius + 0.15 m (minimum passing gap)

Example (Wooden Chair):
  BBox:  0.489 × 0.838 × 0.433 m
  Footprint:        0.489 × 0.433 = 0.212 m²
  Clearance radius: max(0.489, 0.433) / 2 = 0.244 m
  Zone radius:      0.244 + 0.15 = 0.394 m

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Deterministic.
  3. Never raises.
  4. Singleton.

Public API:
    FootprintResult
    FootprintCalculator
    get_footprint_calculator()
    reset_footprint_calculator_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.runtime.assets.assembly.unit_normalizer import get_unit_normalizer

# Minimum passing gap added to clearance_radius to get zone_radius
_ZONE_BUFFER = 0.15


@dataclass
class FootprintResult:
    """Footprint and clearance metrics for one asset (all in meters)."""

    asset_id:         str   = ""
    width_m:          float = 0.0   # bbox X (meters)
    height_m:         float = 0.0   # bbox Y (meters)
    depth_m:          float = 0.0   # bbox Z (meters)
    footprint_area:   float = 0.0   # width × depth (m²)
    clearance_radius: float = 0.0   # max(width, depth) / 2
    zone_radius:      float = 0.0   # clearance_radius + _ZONE_BUFFER

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":         self.asset_id,
            "width_m":          self.width_m,
            "height_m":         self.height_m,
            "depth_m":          self.depth_m,
            "footprint_area":   self.footprint_area,
            "clearance_radius": self.clearance_radius,
            "zone_radius":      self.zone_radius,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FootprintResult":
        return cls(
            asset_id         = str(d.get("asset_id", "")),
            width_m          = float(d.get("width_m", 0.0)),
            height_m         = float(d.get("height_m", 0.0)),
            depth_m          = float(d.get("depth_m", 0.0)),
            footprint_area   = float(d.get("footprint_area", 0.0)),
            clearance_radius = float(d.get("clearance_radius", 0.0)),
            zone_radius      = float(d.get("zone_radius", 0.0)),
        )


class FootprintCalculator:
    """Calculates footprint area and clearance radii from asset metadata."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def calculate(self, asset: Dict[str, Any]) -> FootprintResult:
        """Calculate footprint for an asset from its metadata.

        Reads bbox_x/y/z and unit_system, normalizes to meters, then
        computes footprint area and clearance radii.

        Never raises.
        """
        try:
            return self._calculate(asset)
        except Exception:
            d = asset if isinstance(asset, dict) else {}
            return FootprintResult(
                asset_id = str(d.get("asset_id") or d.get("name") or ""),
            )

    def _calculate(self, asset: Dict[str, Any]) -> FootprintResult:
        normalizer = get_unit_normalizer()
        asset_id = str(asset.get("asset_id") or asset.get("name") or "")

        bx_raw = float(asset.get("bbox_x") or 0)
        by_raw = float(asset.get("bbox_y") or 0)
        bz_raw = float(asset.get("bbox_z") or 0)

        if bx_raw == 0 and by_raw == 0 and bz_raw == 0:
            # No bbox data — use BBoxExtractor defaults
            from src.runtime.assets.assembly.bounding_box_extractor import get_bbox_extractor
            meta = get_bbox_extractor().build_spatial_metadata(asset)
            bx_m, by_m, bz_m = meta.bbox_x, meta.bbox_y, meta.bbox_z
        else:
            unit = normalizer.detect_unit(asset)
            bx_m, by_m, bz_m = normalizer.normalize_bbox(bx_raw, by_raw, bz_raw, unit)

        footprint_area   = bx_m * bz_m
        clearance_radius = max(bx_m, bz_m) / 2.0
        zone_radius      = clearance_radius + _ZONE_BUFFER

        return FootprintResult(
            asset_id         = asset_id,
            width_m          = bx_m,
            height_m         = by_m,
            depth_m          = bz_m,
            footprint_area   = footprint_area,
            clearance_radius = clearance_radius,
            zone_radius      = zone_radius,
        )

    def calculate_from_meters(
        self,
        asset_id: str,
        bx_m: float,
        by_m: float,
        bz_m: float,
    ) -> FootprintResult:
        """Calculate footprint when dimensions are already in meters."""
        footprint_area   = bx_m * bz_m
        clearance_radius = max(bx_m, bz_m) / 2.0
        zone_radius      = clearance_radius + _ZONE_BUFFER
        return FootprintResult(
            asset_id         = asset_id,
            width_m          = bx_m,
            height_m         = by_m,
            depth_m          = bz_m,
            footprint_area   = footprint_area,
            clearance_radius = clearance_radius,
            zone_radius      = zone_radius,
        )

    def total_footprint(self, results: list) -> float:
        """Sum the footprint areas of a list of FootprintResults (m²)."""
        return sum(r.footprint_area for r in results)

    def zone_radius_for(self, asset: Dict[str, Any]) -> float:
        """Shortcut — return just the zone_radius for one asset (meters)."""
        return self.calculate(asset).zone_radius


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[FootprintCalculator] = None
_LOCK = threading.Lock()


def get_footprint_calculator() -> FootprintCalculator:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = FootprintCalculator()
        return _INSTANCE


def reset_footprint_calculator_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
