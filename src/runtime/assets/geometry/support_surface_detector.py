"""
Support Surface Detector (Tier 9.7 — Geometry Intelligence)
============================================================
Finds valid horizontal surfaces on which child assets can be placed.

Examples:
  table      → tabletop at height_m
  shelf      → multiple shelves at equal intervals
  cabinet    → top surface at height_m
  workbench  → work surface at height_m
  counter    → counter surface + lower shelf
  server_rack→ multiple rack units (every 0.044 m / 1U)

Each SupportSurface has:
  surface_type    — tabletop, shelf, worktop, countertop, top_surface, rack_unit
  height_m        — distance from asset base to surface top (m)
  area_m2         — usable surface area in m²
  normal          — [0, 1, 0] for horizontal surfaces
  load_capacity   — light / medium / heavy

Placement types with NO support surface (do not host child assets):
  chair, stool, bucket, barrel, vehicle, character, terrain, beam,
  wall, column, platform, lantern, tree, plant …

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Deterministic — same asset dict → same surfaces.
  3. Never raises.
  4. Singleton pattern.

Public API:
    SupportSurfaceDetector
    get_support_surface_detector()
    reset_support_surface_detector_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from src.runtime.assets.geometry.asset_metrics import SupportSurface

_UP_NORMAL = [0.0, 1.0, 0.0]

# Rack unit height in meters (1U = 1.75 inches = 0.044 m)
_RACK_UNIT_HEIGHT = 0.044
_RACK_START_HEIGHT = 0.12    # first usable U above the base (cable management section)

# Shelf spacing heuristic: 1 shelf per 0.30 m of height
_SHELF_SPACING = 0.30

# Placement types that DO provide support surfaces
_SURFACE_PROVIDING_TYPES = frozenset({
    "table", "desk", "workbench", "counter", "bar_counter",
    "cabinet", "wardrobe", "shelf", "rack", "server_rack",
    "console", "display_case", "crate", "pallet",
    "bench", "sofa", "bed",
})

# Placement types that do NOT provide support surfaces
_NO_SURFACE_TYPES = frozenset({
    "chair", "stool", "bucket", "barrel", "lantern",
    "vehicle", "vehicle_small", "character", "terrain",
    "beam", "wall", "column", "platform", "tree", "plant",
    "machine", "large_machine", "industrial_machine", "crane",
    "reactor", "engine", "door", "window",
    "hanging_light", "pendant_light", "ceiling_mount",
})


def _top_surface(surface_type: str, height_m: float, w: float, d: float,
                  capacity: str = "light") -> SupportSurface:
    return SupportSurface(
        surface_type  = surface_type,
        height_m      = height_m,
        area_m2       = w * d * 0.85,   # 85% usable (edge clearance)
        normal        = _UP_NORMAL,
        load_capacity = capacity,
    )


class SupportSurfaceDetector:
    """Detects support surfaces on assets that can host child objects."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def detect(
        self,
        asset: Dict[str, Any],
        width_m: float,
        height_m: float,
        depth_m: float,
    ) -> List[SupportSurface]:
        """
        Detect support surfaces.

        Args:
            asset:    asset metadata dict
            width_m, height_m, depth_m: asset dimensions in meters

        Returns:
            List of SupportSurface. Empty list for non-surface types.
            Never raises.
        """
        try:
            return self._detect(asset, width_m, height_m, depth_m)
        except Exception:
            return []

    def _detect(
        self,
        asset: Dict[str, Any],
        w: float,
        h: float,
        d: float,
    ) -> List[SupportSurface]:
        pt  = str(asset.get("placement_type") or "").lower().strip()
        cat = str(asset.get("category") or "").lower().strip()

        # --- Priority 1: no surface for known non-providers ---
        if pt in _NO_SURFACE_TYPES:
            return []

        # --- Priority 2: explicit support_surfaces field ---
        explicit = asset.get("support_surfaces")
        if isinstance(explicit, list) and explicit:
            surfaces = []
            for item in explicit:
                if isinstance(item, dict):
                    surfaces.append(SupportSurface.from_dict(item))
            if surfaces:
                return surfaces

        # --- Priority 3: placement-type rules ---
        if pt == "table":
            return [_top_surface("tabletop", h, w, d, capacity="medium")]

        if pt in ("desk", "workbench"):
            surfaces = [_top_surface("worktop", h, w, d, capacity="medium")]
            if h > 0.95:   # leg clearance for sitting → lower shelf
                surfaces.append(SupportSurface(
                    surface_type  = "lower_shelf",
                    height_m      = 0.30,
                    area_m2       = w * d * 0.60,
                    normal        = _UP_NORMAL,
                    load_capacity = "light",
                    notes         = "Under-desk shelf",
                ))
            return surfaces

        if pt in ("counter", "bar_counter"):
            surfaces = [_top_surface("countertop", h, w, d, capacity="medium")]
            if h > 1.0:
                surfaces.append(SupportSurface(
                    surface_type  = "lower_shelf",
                    height_m      = h * 0.40,
                    area_m2       = w * d * 0.70,
                    normal        = _UP_NORMAL,
                    load_capacity = "light",
                    notes         = "Under-counter storage shelf",
                ))
            return surfaces

        if pt == "cabinet":
            surfaces = [_top_surface("top_surface", h, w, d, capacity="light")]
            # Internal shelves (estimated)
            n_shelves = max(1, int(h / 0.30) - 1)
            for i in range(1, n_shelves + 1):
                shelf_h = h * (i / (n_shelves + 1))
                surfaces.append(SupportSurface(
                    surface_type  = "shelf",
                    height_m      = shelf_h,
                    area_m2       = w * d * 0.80,
                    normal        = _UP_NORMAL,
                    load_capacity = "light",
                    notes         = f"Internal shelf {i} of {n_shelves}",
                ))
            return surfaces

        if pt == "wardrobe":
            return [
                _top_surface("top_surface", h, w, d, capacity="light"),
                SupportSurface(
                    surface_type  = "shelf",
                    height_m      = h * 0.55,
                    area_m2       = w * d * 0.70,
                    normal        = _UP_NORMAL,
                    load_capacity = "light",
                    notes         = "Wardrobe upper shelf",
                ),
            ]

        if pt in ("shelf",):
            n_shelves = max(2, int(h / _SHELF_SPACING))
            surfaces = []
            for i in range(n_shelves):
                shelf_h = _SHELF_SPACING * (i + 1)
                if shelf_h >= h:
                    shelf_h = h
                surfaces.append(SupportSurface(
                    surface_type  = "shelf",
                    height_m      = shelf_h,
                    area_m2       = w * d * 0.90,
                    normal        = _UP_NORMAL,
                    load_capacity = "light",
                    notes         = f"Shelf {i + 1} of {n_shelves} at {shelf_h:.2f} m",
                ))
            return surfaces

        if pt in ("server_rack", "rack"):
            n_units = max(1, int((h - _RACK_START_HEIGHT) / _RACK_UNIT_HEIGHT))
            surfaces = []
            for i in range(min(n_units, 42)):  # max 42U
                unit_h = _RACK_START_HEIGHT + i * _RACK_UNIT_HEIGHT
                surfaces.append(SupportSurface(
                    surface_type  = "rack_unit",
                    height_m      = unit_h,
                    area_m2       = w * d * 0.95,
                    normal        = _UP_NORMAL,
                    load_capacity = "heavy",
                    notes         = f"Rack unit {i + 1}U at {unit_h:.3f} m",
                ))
            return surfaces

        if pt in ("console",):
            return [_top_surface("worktop", h, w, d, capacity="light")]

        if pt in ("display_case",):
            return [
                _top_surface("top_surface", h, w, d, capacity="light"),
                SupportSurface(
                    surface_type  = "display_shelf",
                    height_m      = h * 0.5,
                    area_m2       = w * d * 0.80,
                    normal        = _UP_NORMAL,
                    load_capacity = "light",
                    notes         = "Display case interior shelf",
                ),
            ]

        if pt in ("crate",):
            return [_top_surface("top_surface", h, w, d, capacity="heavy")]

        if pt in ("pallet",):
            return [SupportSurface(
                surface_type  = "pallet_surface",
                height_m      = h,
                area_m2       = w * d * 0.95,
                normal        = _UP_NORMAL,
                load_capacity = "heavy",
                notes         = "Pallet load surface",
            )]

        if pt == "bench":
            return [_top_surface("bench_surface", h, w, d, capacity="light")]

        if pt in ("sofa",):
            return [_top_surface("seat_surface", h * 0.55, w, d * 0.50, capacity="light")]

        if pt in ("bed",):
            return [_top_surface("mattress_surface", h, w, d * 0.90, capacity="medium")]

        # --- Priority 4: category fallback ---
        if cat in ("storage", "cabinet"):
            return [_top_surface("top_surface", h, w, d, capacity="light")]

        if cat in ("furniture",):
            # Generic furniture top surface
            return [_top_surface("top_surface", h, w, d, capacity="light")]

        if pt in _SURFACE_PROVIDING_TYPES:
            # Catch-all for any registered surface provider
            return [_top_surface("top_surface", h, w, d, capacity="light")]

        return []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[SupportSurfaceDetector] = None
_LOCK = threading.Lock()


def get_support_surface_detector() -> SupportSurfaceDetector:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = SupportSurfaceDetector()
        return _INSTANCE


def reset_support_surface_detector_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
