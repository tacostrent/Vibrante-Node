"""
Layout Spacing Engine (Tier 9.6 — Scale-Aware Spatial Placement)
=================================================================
Replaces fixed-index spacing (tx = index × 3.0) with dimension-aware
spacing derived from real asset bounding boxes.

Before:  Chair at (0,0,0), Table at (3,0,0), Beam at (6,0,0) — ignores size.
After:   Chair radius=0.24 + gap + Table radius=0.35 → spacing=0.74 m centred
         correctly; Beam routed to structure builder, not placed as furniture.

Spacing formula (centre-to-centre):
  spacing = radius_a + clearance_margin + radius_b
  where clearance_margin is determined by scale class pair.

Cluster positioning (e.g. chairs around a table):
  chairs placed at anchor_radius + gap + chair_radius, angularly distributed.

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Deterministic — same inputs → same positions.
  3. Never raises — errors produce fallback positions.
  4. Singleton.

Public API:
    SpacedPosition
    LayoutSpacingEngine
    get_layout_spacing_engine()
    reset_layout_spacing_engine_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.assets.assembly.asset_scale_analyzer import (
    AssetScaleProfile,
    get_asset_scale_analyzer,
)

# ---------------------------------------------------------------------------
# Clearance margins between scale class pairs (meters)
# ---------------------------------------------------------------------------

# (scale_class_a, scale_class_b) → clearance margin
_SCALE_PAIR_MARGIN: Dict[Tuple[str, str], float] = {
    ("tiny",   "tiny"):      0.05,
    ("tiny",   "small"):     0.08,
    ("tiny",   "medium"):    0.10,
    ("tiny",   "large"):     0.12,
    ("small",  "small"):     0.10,
    ("small",  "medium"):    0.12,
    ("small",  "large"):     0.15,
    ("medium", "medium"):    0.20,
    ("medium", "large"):     0.25,
    ("large",  "large"):     0.35,
}

_DEFAULT_MARGIN = 0.15


def _margin(cls_a: str, cls_b: str) -> float:
    key = (min(cls_a, cls_b), max(cls_a, cls_b))
    return _SCALE_PAIR_MARGIN.get(key, _DEFAULT_MARGIN)


@dataclass
class SpacedPosition:
    """World-space position for one asset, computed from real dimensions."""

    asset_id:    str   = ""
    position:    Tuple[float, float, float] = (0.0, 0.0, 0.0)
    spacing_used: float = 0.0   # actual centre-to-centre gap applied
    source:      str   = "scale_aware"  # "scale_aware" | "template" | "fallback"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":    self.asset_id,
            "position":    list(self.position),
            "spacing_used": self.spacing_used,
            "source":      self.source,
        }


class LayoutSpacingEngine:
    """Computes dimension-aware world-space positions for asset sequences.

    All positions are in meters. Y is always 0 (ground plane).
    Zone depth (Z offset) is applied by the caller.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Linear row layout
    # ------------------------------------------------------------------

    def linear_positions(
        self,
        profiles: List[AssetScaleProfile],
        start_x: float = 0.0,
        depth_z: float = 0.0,
        centre: bool = True,
    ) -> List[SpacedPosition]:
        """Lay out assets in a row along the X axis, using real radii for spacing.

        Args:
            profiles:  ordered list of AssetScaleProfiles to position.
            start_x:   X offset for the first asset.
            depth_z:   Z offset applied to every position (zone depth).
            centre:    if True, shift the whole row so its midpoint is at start_x.

        Returns:
            List of SpacedPosition in the same order as *profiles*.
        """
        if not profiles:
            return []

        try:
            positions: List[Tuple[float, float, float]] = []
            spacings_used: List[float] = []
            cursor = 0.0

            for i, profile in enumerate(profiles):
                if i == 0:
                    x = profile.placement_radius
                else:
                    gap = _margin(profiles[i-1].asset_scale_class, profile.asset_scale_class)
                    spacing = profiles[i-1].placement_radius + gap + profile.placement_radius
                    spacings_used.append(spacing)
                    cursor += spacing
                    x = cursor + profile.placement_radius

                positions.append((x, 0.0, depth_z))

            # Centre if requested
            if centre and positions:
                total_width = positions[-1][0] + profiles[-1].placement_radius
                shift = total_width / 2.0 + start_x - total_width / 2.0
                # shift so midpoint is at start_x
                mid = (positions[0][0] + positions[-1][0]) / 2.0
                offset = start_x - mid
                positions = [(p[0] + offset, p[1], p[2]) for p in positions]

            result: List[SpacedPosition] = []
            for i, (profile, pos) in enumerate(zip(profiles, positions)):
                result.append(SpacedPosition(
                    asset_id     = profile.asset_id or profile.asset_name,
                    position     = pos,
                    spacing_used = spacings_used[i-1] if i > 0 else 0.0,
                    source       = "scale_aware",
                ))
            return result

        except Exception:
            # Graceful fallback — 1.5 m apart
            return [
                SpacedPosition(
                    asset_id = p.asset_id or p.asset_name,
                    position = (start_x + i * 1.5, 0.0, depth_z),
                    spacing_used = 1.5,
                    source = "fallback",
                )
                for i, p in enumerate(profiles)
            ]

    # ------------------------------------------------------------------
    # Cluster layout (children around an anchor)
    # ------------------------------------------------------------------

    def cluster_positions(
        self,
        anchor_profile: AssetScaleProfile,
        child_profiles: List[AssetScaleProfile],
        anchor_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        start_angle_deg: float = 0.0,
    ) -> List[SpacedPosition]:
        """Position child assets around an anchor at the correct radius.

        Children are distributed angularly around the anchor. The radial
        distance is anchor_radius + clearance + child_radius.

        Args:
            anchor_profile:  the anchor asset (e.g. table).
            child_profiles:  child assets (e.g. chairs, cups).
            anchor_pos:      world-space position of the anchor.
            start_angle_deg: starting angle in degrees (0 = +X axis).

        Returns:
            List of SpacedPositions for each child.
        """
        if not child_profiles:
            return []

        try:
            n = len(child_profiles)
            angle_step = 360.0 / n
            result: List[SpacedPosition] = []

            for i, child in enumerate(child_profiles):
                angle_deg = start_angle_deg + i * angle_step
                angle_rad = math.radians(angle_deg)
                margin = _margin(anchor_profile.asset_scale_class, child.asset_scale_class)
                radius = anchor_profile.placement_radius + margin + child.placement_radius

                cx = anchor_pos[0] + radius * math.cos(angle_rad)
                cz = anchor_pos[2] + radius * math.sin(angle_rad)

                result.append(SpacedPosition(
                    asset_id     = child.asset_id or child.asset_name,
                    position     = (cx, anchor_pos[1], cz),
                    spacing_used = radius,
                    source       = "scale_aware",
                ))
            return result

        except Exception:
            # Fallback: evenly around anchor at 1.0 m
            n = len(child_profiles)
            result = []
            for i, child in enumerate(child_profiles):
                angle = math.radians(i * 360.0 / max(1, n))
                result.append(SpacedPosition(
                    asset_id  = child.asset_id or child.asset_name,
                    position  = (
                        anchor_pos[0] + math.cos(angle),
                        anchor_pos[1],
                        anchor_pos[2] + math.sin(angle),
                    ),
                    spacing_used = 1.0,
                    source       = "fallback",
                ))
            return result

    # ------------------------------------------------------------------
    # Single overflow position (replaces fixed index * 3.0)
    # ------------------------------------------------------------------

    def overflow_position(
        self,
        profile: AssetScaleProfile,
        previous_pos: Tuple[float, float, float],
        previous_profile: AssetScaleProfile,
        axis: str = "x",
    ) -> SpacedPosition:
        """Compute the next overflow position given the previous asset and profile.

        Replaces: last_x + index * 3.0
        With:     last_x + prev_radius + margin + curr_radius

        Args:
            profile:          the asset to place.
            previous_pos:     world position of the previously placed asset.
            previous_profile: scale profile of the previously placed asset.
            axis:             "x" or "z" — which axis to advance along.

        Returns:
            SpacedPosition for *profile*.
        """
        try:
            margin = _margin(
                previous_profile.asset_scale_class,
                profile.asset_scale_class,
            )
            step = previous_profile.placement_radius + margin + profile.placement_radius

            if axis == "z":
                new_pos = (
                    previous_pos[0],
                    previous_pos[1],
                    previous_pos[2] - step,  # advance into the scene (negative Z)
                )
            else:
                new_pos = (
                    previous_pos[0] + step,
                    previous_pos[1],
                    previous_pos[2],
                )

            return SpacedPosition(
                asset_id     = profile.asset_id or profile.asset_name,
                position     = new_pos,
                spacing_used = step,
                source       = "scale_aware",
            )
        except Exception:
            return SpacedPosition(
                asset_id  = profile.asset_id or profile.asset_name,
                position  = (previous_pos[0] + 1.5, previous_pos[1], previous_pos[2]),
                spacing_used = 1.5,
                source    = "fallback",
            )

    # ------------------------------------------------------------------
    # Convenience: analyse and space a list of asset dicts
    # ------------------------------------------------------------------

    def space_assets(
        self,
        assets: List[Dict[str, Any]],
        depth_z: float = 0.0,
        start_x: float = 0.0,
    ) -> List[SpacedPosition]:
        """Build scale profiles for *assets* then return linear positions.

        Structural assets are skipped (they should go to StructureBuilder).
        """
        analyzer = get_asset_scale_analyzer()
        profiles: List[AssetScaleProfile] = []
        indices:  List[int] = []

        for i, asset in enumerate(assets):
            profile = analyzer.analyze_asset(asset)
            if not profile.is_structural:
                profiles.append(profile)
                indices.append(i)

        spaced = self.linear_positions(profiles, start_x=start_x, depth_z=depth_z)

        # Re-expand to full list, inserting None for skipped structural assets
        result: List[Optional[SpacedPosition]] = [None] * len(assets)
        for idx_in_spaced, asset_idx in enumerate(indices):
            result[asset_idx] = spaced[idx_in_spaced]

        return [r for r in result if r is not None]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[LayoutSpacingEngine] = None
_LOCK = threading.Lock()


def get_layout_spacing_engine() -> LayoutSpacingEngine:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = LayoutSpacingEngine()
        return _INSTANCE


def reset_layout_spacing_engine_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
