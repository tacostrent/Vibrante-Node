"""
surface_realizer.py — §47 Layout Realization & Scene Constraint Solver
=======================================================================
Converts surface placement data into world-space transforms.

Uses Tier 9.7 surface height data when available; falls back to known
height table. Ensures objects land on the actual surface, not float or
sink through it.

Rules:
  - ty = host_world_y + surface_height_above_floor + child_half_height
  - child_half_height defaults to 0.0 (conservative: place at surface level)
  - Items spread linearly across the surface width (deterministic)

Public API:
    SurfaceRealizationResult
    SurfaceRealizer
    get_surface_realizer()
    reset_surface_realizer_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout_realization.transform_resolver import ResolvedTransform


# Surface height (meters above floor) per host type
_SURFACE_HEIGHTS: Dict[str, float] = {
    "table":       0.75,
    "desk":        0.75,
    "workbench":   0.90,
    "bar_counter": 1.05,
    "shelf":       1.40,
    "counter":     0.90,
    "crate":       0.60,
    "pallet":      0.15,
    "mantle":      1.20,
    "cabinet":     1.60,
    "console":     0.85,
    "display_case": 0.90,
}

# Half-height estimates for small prop types (meters)
_HALF_HEIGHTS: Dict[str, float] = {
    "bottle":        0.15,
    "whiskey_bottle": 0.15,
    "cup":           0.06,
    "glass":         0.06,
    "mug":           0.06,
    "plate":         0.02,
    "book":          0.03,
    "candle":        0.08,
    "lantern":       0.15,
    "tool":          0.05,
    "container":     0.10,
    "bowl":          0.05,
    "vase":          0.15,
    "small_prop":    0.05,
}

_DEFAULT_SURFACE_HEIGHT = 0.75
_DEFAULT_HALF_HEIGHT = 0.05
_DEFAULT_SURFACE_WIDTH = 1.20


@dataclass
class SurfaceRealizationResult:
    host_asset_id:   str
    host_asset_name: str
    surface_height:  float
    transforms:      List[ResolvedTransform] = field(default_factory=list)
    rejected:        List[str] = field(default_factory=list)
    ok:     bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host_asset_id":   self.host_asset_id,
            "host_asset_name": self.host_asset_name,
            "surface_height":  round(self.surface_height, 4),
            "transforms":      [t.to_dict() for t in self.transforms],
            "rejected":        list(self.rejected),
            "ok":              self.ok,
            "errors":          list(self.errors),
        }


class SurfaceRealizer:
    """Realizes surface placements from LayoutPlan.surface_placements."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def realize_surface_placements(
        self,
        surface_placements: List[Dict[str, Any]],
        anchor_transforms: Dict[str, ResolvedTransform],
    ) -> List[ResolvedTransform]:
        """
        Convert surface placement dicts into world-space transforms.

        Each child asset gets a correct ty based on:
          host_world_y + surface_height + child_half_height

        Never raises.
        """
        try:
            return self._realize(surface_placements, anchor_transforms)
        except Exception as exc:
            return []

    def _realize(
        self,
        surface_placements: List[Dict[str, Any]],
        anchor_transforms: Dict[str, ResolvedTransform],
    ) -> List[ResolvedTransform]:
        results: List[ResolvedTransform] = []
        host_counters: Dict[str, int] = {}

        for sp in surface_placements:
            child_id   = sp.get("child_asset_id", "")
            child_name = sp.get("child_asset_name", "")
            host_id    = sp.get("host_asset_id", "")
            surf_type  = sp.get("surface_type", "")
            surf_h     = float(sp.get("surface_height", 0.0))

            # Derive host world position
            host_xf = anchor_transforms.get(host_id)
            host_pos = [host_xf.tx, host_xf.ty, host_xf.tz] if host_xf else [0.0, 0.0, 0.0]

            # Determine host type from surface_type (e.g. "table_surface" → "table")
            host_type = surf_type.replace("_surface", "").replace("_top", "")
            if surf_h == 0.0:
                surf_h = _SURFACE_HEIGHTS.get(host_type, _DEFAULT_SURFACE_HEIGHT)

            # Infer child type from name/id for half-height estimate
            child_lower = child_name.lower()
            half_h = _DEFAULT_HALF_HEIGHT
            for key, hh in _HALF_HEIGHTS.items():
                if key in child_lower:
                    half_h = hh
                    break

            # Spread items horizontally on the surface
            slot = host_counters.get(host_id, 0)
            host_counters[host_id] = slot + 1
            surf_w = _DEFAULT_SURFACE_WIDTH
            step   = surf_w / 5.0 if slot < 5 else 0.25
            x_off  = (slot - 2) * step

            ty = float(host_pos[1]) + surf_h + half_h

            results.append(ResolvedTransform(
                asset_id=child_id,
                asset_name=child_name,
                tx=float(host_pos[0]) + x_off,
                ty=ty,
                tz=float(host_pos[2]),
                parent_id=host_id,
                relationship="supports",
                notes=f"surface={surf_type} h={surf_h:.2f}m",
            ))

        return results

    def get_surface_height(self, host_type: str) -> float:
        """Return canonical surface height for a host asset type."""
        return _SURFACE_HEIGHTS.get(host_type.lower(), _DEFAULT_SURFACE_HEIGHT)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[SurfaceRealizer] = None
_lock = threading.Lock()


def get_surface_realizer() -> SurfaceRealizer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SurfaceRealizer()
    return _instance


def reset_surface_realizer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
