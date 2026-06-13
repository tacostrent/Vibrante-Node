"""
Asset Scale Analyzer (Tier 9.6 — Scale-Aware Spatial Placement)
================================================================
Classifies each asset into a physical scale class based on its real-world
bounding box dimensions (in meters). Scale classes drive spacing, zone
assignment, and structural routing decisions.

Scale classes:
  tiny       max_dim < 0.15 m   cup, bottle, book, small prop
  small      max_dim < 0.50 m   bucket, stool, lantern, small crate
  medium     max_dim < 1.50 m   chair, cabinet, barrel, crate
  large      max_dim < 4.00 m   table, bench, door, machine, vehicle
  structural max_dim >= 4.00 m  beam, wall, column, roof, crane, platform
             OR placement_type in STRUCTURAL_PLACEMENT_TYPES
             OR category in STRUCTURAL_CATEGORIES

A beam at 3.777 m → structural.
A chair at 0.84 m → medium.
A table at 0.70 m → medium.
A cup at 0.08 m → tiny.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Pure classification logic.
  2. Deterministic — same asset metadata → same scale class.
  3. Never raises — errors produce scale_class="medium" as safe default.
  4. Singleton pattern.

Public API:
    SCALE_CLASSES
    STRUCTURAL_PLACEMENT_TYPES
    STRUCTURAL_CATEGORIES
    AssetScaleProfile
    AssetScaleAnalyzer
    get_asset_scale_analyzer()
    reset_asset_scale_analyzer_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.assets.assembly.unit_normalizer import get_unit_normalizer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCALE_CLASSES = frozenset({"tiny", "small", "medium", "large", "structural"})

# Placement types that always route to structural, regardless of size
STRUCTURAL_PLACEMENT_TYPES = frozenset({
    "wall", "column", "platform", "crane", "terrain",
    # Common name variants
    "beam", "roof", "support_column", "support_beam",
})

# Asset categories that default to structural routing
STRUCTURAL_CATEGORIES = frozenset({
    "structure", "architectural", "terrain",
})

# max_dim thresholds (meters)
_THRESHOLDS: List[Tuple[float, str]] = [
    (0.15, "tiny"),
    (0.50, "small"),
    (1.50, "medium"),
    (4.00, "large"),
]
# Anything >= 4.00 m → structural (unless overridden by type/category)


@dataclass
class AssetScaleProfile:
    """Physical scale characteristics for one asset."""

    asset_id:          str   = ""
    asset_name:        str   = ""
    source_unit:       str   = "meters"

    # Raw values from metadata (in whatever source unit)
    bbox_raw:          Tuple[float, float, float] = (0.0, 0.0, 0.0)

    # Converted to meters
    bbox_meters:       Tuple[float, float, float] = (1.0, 1.0, 1.0)

    footprint_area:    float = 1.0     # bbox_x_m * bbox_z_m (m²)
    placement_radius:  float = 0.5     # max(bbox_x_m, bbox_z_m) / 2.0
    max_dimension:     float = 1.0     # max(bbox_x_m, bbox_y_m, bbox_z_m)

    asset_scale_class: str   = "medium"  # tiny/small/medium/large/structural
    is_structural:     bool  = False     # True → route to structure builder

    placement_type:    str   = "unknown"
    category:         str   = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":          self.asset_id,
            "asset_name":        self.asset_name,
            "source_unit":       self.source_unit,
            "bbox_raw":          list(self.bbox_raw),
            "bbox_meters":       list(self.bbox_meters),
            "footprint_area":    self.footprint_area,
            "placement_radius":  self.placement_radius,
            "max_dimension":     self.max_dimension,
            "asset_scale_class": self.asset_scale_class,
            "is_structural":     self.is_structural,
            "placement_type":    self.placement_type,
            "category":          self.category,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetScaleProfile":
        return cls(
            asset_id          = str(d.get("asset_id", "")),
            asset_name        = str(d.get("asset_name", "")),
            source_unit       = str(d.get("source_unit", "meters")),
            bbox_raw          = tuple(d.get("bbox_raw", [0.0, 0.0, 0.0])),         # type: ignore
            bbox_meters       = tuple(d.get("bbox_meters", [1.0, 1.0, 1.0])),      # type: ignore
            footprint_area    = float(d.get("footprint_area", 1.0)),
            placement_radius  = float(d.get("placement_radius", 0.5)),
            max_dimension     = float(d.get("max_dimension", 1.0)),
            asset_scale_class = str(d.get("asset_scale_class", "medium")),
            is_structural     = bool(d.get("is_structural", False)),
            placement_type    = str(d.get("placement_type", "unknown")),
            category          = str(d.get("category", "")),
        )


class AssetScaleAnalyzer:
    """Analyzes and classifies assets by their physical scale.

    Primary consumers: LayoutSpacingEngine (spacing), PlacementRelationships
    (routing), AssetPlacementEngine (zone assignment).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def analyze_asset(self, asset: Dict[str, Any]) -> AssetScaleProfile:
        """Build a complete AssetScaleProfile for one asset.

        Args:
            asset: asset metadata dict. May contain bbox_x/y/z, unit_system,
                   category, placement_type, name, asset_id.

        Returns:
            AssetScaleProfile. Never raises.
        """
        try:
            return self._analyze(asset)
        except Exception:
            d = asset if isinstance(asset, dict) else {}
            return AssetScaleProfile(
                asset_id   = str(d.get("asset_id") or d.get("name") or ""),
                asset_name = str(d.get("name") or d.get("asset_id") or ""),
            )

    def _analyze(self, asset: Dict[str, Any]) -> AssetScaleProfile:
        normalizer = get_unit_normalizer()

        asset_id   = str(asset.get("asset_id") or asset.get("id") or "")
        asset_name = str(asset.get("name") or asset_id)
        category   = str(asset.get("category") or "").lower().strip()
        p_type     = str(asset.get("placement_type") or "").lower().strip()

        # Step 1: detect source unit and raw bbox
        source_unit = normalizer.detect_unit(asset)
        bx_raw = float(asset.get("bbox_x") or 0)
        by_raw = float(asset.get("bbox_y") or 0)
        bz_raw = float(asset.get("bbox_z") or 0)

        # Step 2: convert to meters
        bx_m, by_m, bz_m = normalizer.normalize_bbox(bx_raw, by_raw, bz_raw, source_unit)

        # If zero (no explicit bbox), use the BBoxExtractor defaults
        if bx_m == 0 and by_m == 0 and bz_m == 0:
            from src.runtime.assets.assembly.bounding_box_extractor import get_bbox_extractor
            meta = get_bbox_extractor().build_spatial_metadata(asset)
            bx_m, by_m, bz_m = meta.bbox_x, meta.bbox_y, meta.bbox_z

        # Step 3: derived quantities
        footprint_area   = bx_m * bz_m
        placement_radius = max(bx_m, bz_m) / 2.0
        max_dim          = max(bx_m, by_m, bz_m)

        # Step 4: classify
        scale_class, is_structural = self.classify_scale(
            max_dim, footprint_area, p_type, category
        )

        return AssetScaleProfile(
            asset_id          = asset_id,
            asset_name        = asset_name,
            source_unit       = source_unit,
            bbox_raw          = (bx_raw, by_raw, bz_raw),
            bbox_meters       = (bx_m, by_m, bz_m),
            footprint_area    = footprint_area,
            placement_radius  = placement_radius,
            max_dimension     = max_dim,
            asset_scale_class = scale_class,
            is_structural     = is_structural,
            placement_type    = p_type,
            category          = category,
        )

    def classify_scale(
        self,
        max_dim: float,
        footprint_area: float,
        placement_type: str,
        category: str,
    ) -> Tuple[str, bool]:
        """Return (scale_class, is_structural) for the given dimensions and type.

        Structural override:
          - placement_type in STRUCTURAL_PLACEMENT_TYPES → structural, True
          - category in STRUCTURAL_CATEGORIES → structural, True
          - max_dim >= 4.0 → structural, True

        Otherwise classified by max_dim thresholds.
        """
        # Hard structural overrides first
        if placement_type in STRUCTURAL_PLACEMENT_TYPES:
            return "structural", True
        if category in STRUCTURAL_CATEGORIES:
            return "structural", True
        if max_dim >= 4.0:
            return "structural", True

        # Dimension-based thresholds
        for threshold, cls in _THRESHOLDS:
            if max_dim < threshold:
                return cls, False

        return "large", False

    def are_compatible_scale_classes(self, cls_a: str, cls_b: str) -> bool:
        """Return True if two assets of these scale classes can share a zone."""
        if cls_a == "structural" or cls_b == "structural":
            return False
        return True

    def spacing_from_profiles(
        self,
        profile_a: AssetScaleProfile,
        profile_b: AssetScaleProfile,
        clearance_margin: float = 0.15,
    ) -> float:
        """Return the minimum centre-to-centre spacing between two assets (meters).

        spacing = radius_a + clearance_margin + radius_b
        """
        return profile_a.placement_radius + clearance_margin + profile_b.placement_radius


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetScaleAnalyzer] = None
_LOCK = threading.Lock()


def get_asset_scale_analyzer() -> AssetScaleAnalyzer:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = AssetScaleAnalyzer()
        return _INSTANCE


def reset_asset_scale_analyzer_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
