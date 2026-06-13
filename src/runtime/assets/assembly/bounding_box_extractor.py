"""
Bounding Box Extractor (Tier 9.4 — Real Asset Spatial Intelligence)
===================================================================
Extracts or estimates bounding-box dimensions from asset metadata.
No real file I/O — uses metadata fields and category / placement-type
dimension tables as authoritative defaults.

Dimension priority chain:
  1. Explicit bbox_x / bbox_y / bbox_z fields in asset metadata
  2. Placement-type defaults   (table → 2.2 × 0.8 × 1.3 m)
  3. Category defaults          (furniture → 1.0 × 0.9 × 0.6 m)
  4. Generic fallback           (1.0 × 1.0 × 1.0 m)

All output dimensions are in meters.

DESIGN RULES:
  1. No Houdini imports.  No bridge calls.  Estimation only.
  2. All dimensions ≥ 0.0.
  3. Never raises in public methods.
  4. Same input always produces the same output.

Public API:
    BBoxExtractor
    get_bbox_extractor()
    reset_bbox_extractor_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional, Tuple

from src.runtime.assets.assembly.spatial_metadata import (
    SpatialMetadata,
    _UNIT_TO_METERS,
)
from src.runtime.assets.assembly.unit_normalizer import get_unit_normalizer

# ---------------------------------------------------------------------------
# Placement-type → (bbox_x, bbox_y, bbox_z) in meters
# ---------------------------------------------------------------------------
_PLACEMENT_TYPE_DIMS: Dict[str, Tuple[float, float, float]] = {
    "table":    (2.2,  0.8,  1.3),
    "chair":    (0.6,  1.0,  0.6),
    "bench":    (1.8,  0.9,  0.5),
    "bucket":   (0.4,  0.5,  0.4),
    "barrel":   (0.6,  1.0,  0.6),
    "machine":  (2.5,  2.0,  2.0),
    "crane":    (3.0,  8.0,  3.0),
    "pipe":     (0.2,  3.0,  0.2),
    "wall":     (4.0,  3.0,  0.3),
    "door":     (1.0,  2.2,  0.1),
    "lantern":  (0.3,  0.5,  0.3),
    "column":   (0.5,  4.0,  0.5),
    "platform": (3.0,  0.3,  3.0),
    "vehicle":  (4.5,  2.0,  2.2),
    "terrain":  (10.0, 0.5, 10.0),
}

# Category → (bbox_x, bbox_y, bbox_z) in meters
_CATEGORY_DIMS: Dict[str, Tuple[float, float, float]] = {
    "vehicle":       (4.5,  2.0,  2.2),
    "character":     (0.5,  1.8,  0.5),
    "robot":         (1.2,  1.5,  0.8),
    "machinery":     (2.0,  1.5,  1.5),
    "electronic":    (0.6,  0.5,  0.4),
    "prop":          (0.4,  0.4,  0.4),
    "furniture":     (1.0,  0.9,  0.6),
    "structure":     (3.0,  4.0,  3.0),
    "architectural": (5.0,  6.0,  5.0),
    "terrain":       (10.0, 0.5, 10.0),
    "pipe":          (0.2,  3.0,  0.2),
    "vegetation":    (1.5,  2.5,  1.5),
    "creature":      (1.0,  1.2,  0.8),
    "weapon":        (0.3,  0.1,  1.0),
    "hdri":          (0.0,  0.0,  0.0),
    "material":      (0.0,  0.0,  0.0),
}

_DEFAULT_DIMS: Tuple[float, float, float] = (1.0, 1.0, 1.0)

# Placement types that can anchor (support) child assets
_ANCHOR_TYPES = frozenset({
    "table", "bench", "platform", "terrain", "wall", "column",
})

# Placement types that block walkable floor space
_WALKABLE_OBSTACLES = frozenset({
    "table", "chair", "bench", "barrel", "machine", "crane",
    "column", "platform", "vehicle", "terrain", "wall", "door",
})


class BBoxExtractor:
    """
    Extracts or estimates bounding-box metadata from an asset dict.
    All output dimensions are in meters.
    """

    def extract_bbox(self, asset: Dict[str, Any]) -> Tuple[float, float, float]:
        """
        Return (bbox_x, bbox_y, bbox_z) in meters.
        Priority: explicit metadata → placement_type → category → 1×1×1 m.
        """
        # 1. Explicit bbox fields — use UnitNormalizer to handle cm/mm/inch/ft
        #    correctly, including heuristic detection when unit_system is absent.
        if all(k in asset for k in ("bbox_x", "bbox_y", "bbox_z")):
            try:
                bx_raw = float(asset["bbox_x"])
                by_raw = float(asset["bbox_y"])
                bz_raw = float(asset["bbox_z"])
                if bx_raw > 0 or by_raw > 0 or bz_raw > 0:
                    normalizer = get_unit_normalizer()
                    unit = normalizer.detect_unit(asset)
                    return normalizer.normalize_bbox(bx_raw, by_raw, bz_raw, unit)
            except (TypeError, ValueError):
                pass

        # 2. Placement-type defaults
        pt = str(asset.get("placement_type", "") or "").lower()
        if pt in _PLACEMENT_TYPE_DIMS:
            return _PLACEMENT_TYPE_DIMS[pt]

        # 3. Category defaults
        cat = str(asset.get("category", "") or "").lower()
        if cat in _CATEGORY_DIMS:
            return _CATEGORY_DIMS[cat]

        # 4. Generic fallback
        return _DEFAULT_DIMS

    def extract_dimensions(self, asset: Dict[str, Any]) -> Dict[str, float]:
        """Return {bbox_x, bbox_y, bbox_z, footprint_area, placement_radius}."""
        bx, by, bz = self.extract_bbox(asset)
        return {
            "bbox_x":           bx,
            "bbox_y":           by,
            "bbox_z":           bz,
            "footprint_area":   bx * bz,
            "placement_radius": max(bx, bz) / 2.0,
        }

    def extract_footprint(self, asset: Dict[str, Any]) -> float:
        """Return footprint area (bbox_x × bbox_z) in m²."""
        bx, _by, bz = self.extract_bbox(asset)
        return bx * bz

    def build_spatial_metadata(
        self,
        asset: Dict[str, Any],
        world_scale: float = 1.0,
    ) -> SpatialMetadata:
        """
        Build a complete SpatialMetadata from an asset dict.
        Never raises — falls back to 1×1×1 m defaults on error.
        """
        try:
            bx, by, bz = self.extract_bbox(asset)
            bx = max(0.0, bx * world_scale)
            by = max(0.0, by * world_scale)
            bz = max(0.0, bz * world_scale)

            pt  = str(asset.get("placement_type", "") or "unknown").lower()
            if pt not in _PLACEMENT_TYPE_DIMS and pt != "unknown":
                pt = "unknown"
            cat = str(asset.get("category", "") or "").lower()

            anchor   = (pt in _ANCHOR_TYPES) or cat in {"structure", "architectural", "terrain"}
            obstacle = (pt in _WALKABLE_OBSTACLES) or cat in {
                "vehicle", "machinery", "structure", "architectural",
            }

            return SpatialMetadata(
                asset_id=str(
                    asset.get("asset_id", "")
                    or asset.get("name", "")
                    or ""
                ),
                bbox_x=bx,
                bbox_y=by,
                bbox_z=bz,
                footprint_area=bx * bz,
                placement_radius=max(bx, bz) / 2.0,
                world_scale=world_scale,
                unit_system="meters",
                placement_type=pt,
                anchor_capable=anchor,
                walkable_obstacle=obstacle,
            )
        except Exception:
            return SpatialMetadata()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _to_meters(
        dims: Tuple[float, float, float],
        unit: str,
    ) -> Tuple[float, float, float]:
        factor = _UNIT_TO_METERS.get(unit, 1.0)
        return (dims[0] * factor, dims[1] * factor, dims[2] * factor)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_INSTANCE: Optional[BBoxExtractor] = None
_INSTANCE_LOCK = threading.Lock()


def get_bbox_extractor() -> BBoxExtractor:
    """Return the module-level singleton BBoxExtractor."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = BBoxExtractor()
    return _INSTANCE


def reset_bbox_extractor_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
