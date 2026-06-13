"""
Layout Transform Engine (Tier 3)
==================================
Calculates deterministic world-space transforms for scene assets based on
cinematic composition rules, zone dimensions, and asset metadata.

CRITICAL: NO RANDOMNESS. All positions, rotations, and scales are calculated
using deterministic arithmetic from layout rules, zone dimensions, asset
counts, and semantic categories. Same input always produces same output.

Public API:
    LayoutTransformEngine
        .calculate_asset_positions(assets, zone, layout_rules) -> dict
        .calculate_asset_rotations(assets, zone) -> dict
        .calculate_spacing_offsets(asset_count, zone_width) -> list[float]
        .generate_depth_layers(zones, depth_layers) -> dict
        .calculate_camera_focus_targets(zones, layout_rules) -> list[dict]

    get_layout_transform_engine() -> LayoutTransformEngine
    reset_layout_transform_engine_for_tests()
"""

from __future__ import annotations

import math
import threading
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Zone spatial configuration (all units in Houdini world units = metres)
# ---------------------------------------------------------------------------

_ZONE_DEPTHS: Dict[str, float] = {
    "background":  -30.0,
    "midground":    -10.0,
    "hero_area":      0.0,
    "ceiling":       15.0,
    "floor":         -1.0,
    "walls":          0.0,
}

_ZONE_WIDTHS: Dict[str, float] = {
    "background":  60.0,
    "midground":   40.0,
    "hero_area":   20.0,
    "ceiling":     30.0,
    "floor":       30.0,
    "walls":       30.0,
}

# Category → default Y offset (height off ground)
_CATEGORY_Y_OFFSET: Dict[str, float] = {
    "vehicle":        0.0,
    "character":      0.0,
    "robot":          0.0,
    "creature":       0.0,
    "container":      0.0,
    "structure":      0.0,
    "terrain":       -0.5,
    "sky":           20.0,
    "ceiling":       12.0,
    "tech_panel":     1.2,
    "vegetation":     0.0,
    "misc":           0.0,
    "hero_prop":      0.0,
    "machinery_hero": 0.0,
    "weapon":         0.0,
}

# Category → default facing rotation (degrees, around Y axis)
_CATEGORY_BASE_ROTATION: Dict[str, float] = {
    "vehicle":        0.0,
    "character":      0.0,
    "robot":          0.0,
    "creature":      15.0,
    "container":      0.0,
    "structure":      0.0,
    "terrain":        0.0,
    "sky":            0.0,
    "ceiling":        0.0,
    "tech_panel":    90.0,
    "vegetation":    30.0,
    "misc":           0.0,
}

# Cinematic facing angles for hero assets (slight angles for depth)
_HERO_FACING_ANGLES: List[float] = [0.0, -15.0, 15.0]


class LayoutTransformEngine:
    """
    Calculates deterministic world-space transforms for scene assembly.

    All algorithms are pure arithmetic — no randomness, no bridge calls.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calc_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_asset_positions(
        self,
        assets: List[Dict[str, Any]],
        zone: str,
        layout_rules: Dict[str, Any],
    ) -> Dict[str, Tuple[float, float, float]]:
        """
        Calculate (tx, ty, tz) for each asset in a zone.

        Deterministic algorithm:
          - Z is the zone's canonical depth
          - X positions are evenly spaced across the zone width, centred at 0
          - Y is the category Y offset
          - Hero zone assets get slight cinematic angle offsets

        Returns {asset_name: (tx, ty, tz)}
        """
        n = len(assets)
        if n == 0:
            return {}

        zone_depth = _ZONE_DEPTHS.get(zone, -10.0)
        zone_width = _ZONE_WIDTHS.get(zone, 30.0)
        offsets = self.calculate_spacing_offsets(n, zone_width)

        result: Dict[str, Tuple[float, float, float]] = {}
        for i, asset in enumerate(assets):
            name = asset.get("name", f"asset_{i}")
            category = asset.get("category", "misc")
            y_offset = _CATEGORY_Y_OFFSET.get(category, 0.0)

            # Apply Z depth variation for background layers (stagger slightly)
            z_stagger = 0.0
            if zone == "background" and n > 1:
                # Deterministic stagger: assets alternate between 0, -2, +2, -4, ...
                sign = 1 if i % 2 == 0 else -1
                z_stagger = sign * (i // 2) * 2.0

            tx = offsets[i]
            ty = y_offset
            tz = zone_depth + z_stagger

            result[name] = (round(tx, 4), round(ty, 4), round(tz, 4))

        with self._lock:
            self._calc_count += 1

        return result

    def calculate_asset_rotations(
        self,
        assets: List[Dict[str, Any]],
        zone: str,
    ) -> Dict[str, Tuple[float, float, float]]:
        """
        Calculate (rx, ry, rz) rotation for each asset in a zone.

        Deterministic:
          - Hero assets get slight cinematic Y angles for depth
          - Tech panels get 90° base rotation
          - Background assets get incremental Y offsets for natural variety
          - All RX/RZ are zero unless category requires otherwise

        Returns {asset_name: (rx, ry, rz)}
        """
        result: Dict[str, Tuple[float, float, float]] = {}

        for i, asset in enumerate(assets):
            name = asset.get("name", f"asset_{i}")
            category = asset.get("category", "misc")
            base_ry = _CATEGORY_BASE_ROTATION.get(category, 0.0)

            rx = 0.0
            rz = 0.0

            if zone == "hero_area":
                # Subtle cinematic angle for first 3 heroes
                hero_angle = _HERO_FACING_ANGLES[i % len(_HERO_FACING_ANGLES)]
                ry = base_ry + hero_angle
            elif zone == "background" and i > 0:
                # Deterministic rotation variety: 0, 45, 90, 135 ...
                ry = base_ry + (i * 45) % 360
            else:
                ry = base_ry

            # Ceiling/floor elements face down/up
            if category == "ceiling":
                rx = -90.0
            elif category == "floor":
                rx = 90.0

            result[name] = (round(rx, 2), round(ry, 2), round(rz, 2))

        return result

    def calculate_spacing_offsets(
        self,
        asset_count: int,
        zone_width: float,
    ) -> List[float]:
        """
        Calculate evenly spaced X offsets centred at 0.

        For N assets across a width W:
          spacing = W / (N + 1)
          offsets = [-(N-1)/2 * spacing, ..., +(N-1)/2 * spacing]

        Returns a list of N X-offset values.
        """
        if asset_count == 0:
            return []
        if asset_count == 1:
            return [0.0]

        spacing = zone_width / (asset_count + 1)
        start = -((asset_count - 1) / 2.0) * spacing
        return [round(start + i * spacing, 4) for i in range(asset_count)]

    def generate_depth_layers(
        self,
        zones: Dict[str, List[Dict[str, Any]]],
        depth_layers: List[str],
    ) -> Dict[str, Any]:
        """
        Generate depth layer transform data for the full scene.

        Returns:
            {
                layer_order:  [zone_name, ...] (back-to-front for rendering)
                zone_depths:  {zone: z_value}
                layer_bounds: {zone: {"min_z": float, "max_z": float, "width": float}}
            }
        """
        # depth_layers is hero-first per env_rules convention;
        # back-to-front render order is the reverse
        render_order = list(reversed(depth_layers))

        zone_depths: Dict[str, float] = {}
        layer_bounds: Dict[str, Dict[str, float]] = {}

        for zone in depth_layers:
            z = _ZONE_DEPTHS.get(zone, -10.0)
            w = _ZONE_WIDTHS.get(zone, 30.0)
            zone_depths[zone] = z
            layer_bounds[zone] = {
                "min_z":  z - 2.0,
                "max_z":  z + 2.0,
                "width":  w,
            }

        return {
            "layer_order":   render_order,
            "zone_depths":   zone_depths,
            "layer_bounds":  layer_bounds,
        }

    def calculate_camera_focus_targets(
        self,
        zones: Dict[str, List[Dict[str, Any]]],
        layout_rules: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Calculate deterministic camera focus target positions.

        Returns a list of camera target dicts:
            [{name, zone, position: (tx,ty,tz), shot_type, priority}, ...]
        """
        targets: List[Dict[str, Any]] = []
        hero_focus = layout_rules.get("hero_focus", "center")

        # Primary hero focus
        hero_assets = zones.get("hero_area", [])
        if hero_assets:
            # Focus on the first hero asset (highest priority)
            first_hero = hero_assets[0]
            hero_name = first_hero.get("name", "hero")
            targets.append({
                "name":      f"focus_{hero_name}",
                "zone":      "hero_area",
                "position":  (0.0, 1.5, 0.0),  # eye level at scene centre
                "shot_type": "hero_focus",
                "priority":  1,
            })

        # Mid-ground establishing target
        mid_assets = zones.get("midground", [])
        if mid_assets:
            mid_depth = _ZONE_DEPTHS.get("midground", -10.0)
            targets.append({
                "name":      "focus_midground",
                "zone":      "midground",
                "position":  (0.0, 1.8, mid_depth * 0.5),
                "shot_type": "establishing",
                "priority":  2,
            })

        # Full establishing (widest)
        bg_depth = _ZONE_DEPTHS.get("background", -30.0)
        targets.append({
            "name":      "focus_establishing",
            "zone":      "background",
            "position":  (0.0, 3.0, bg_depth * 0.3),
            "shot_type": "wide_establishing",
            "priority":  3,
        })

        return targets

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"calc_count": self._calc_count}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[LayoutTransformEngine] = None
_INSTANCE_LOCK = threading.Lock()


def get_layout_transform_engine() -> LayoutTransformEngine:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = LayoutTransformEngine()
        return _INSTANCE


def reset_layout_transform_engine_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
