"""
Asset Metrics (Tier 9.7 — Geometry Intelligence & Asset Metrics)
================================================================
Core data models for geometry intelligence. AssetMetrics is the authoritative
descriptor of an asset's physical characteristics: dimensions, pivot, support
surfaces, ground contacts, scale class, and production role.

All placement, environment construction, lookdev, and cinematic systems
consume AssetMetrics as the single source of truth for asset geometry.

Scale classes (6 total, extending Tier 9.6 with 'hero'):
  tiny       max_dim < 0.15 m   cup, bottle, button, small prop
  small      max_dim < 0.50 m   bucket, stool, lantern, small crate
  medium     max_dim < 1.50 m   chair, cabinet, barrel
  large      max_dim < 4.00 m   table, bench, door, shelf
  structural max_dim >= 4.00 m  beam, wall, column, roof
             OR placement_type in STRUCTURAL_PLACEMENT_TYPES
             OR category in STRUCTURAL_CATEGORIES
  hero       placement_type in HERO_PLACEMENT_TYPES (machine, vehicle, crane)
             — dominant scene focal element regardless of size

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Pure data models.
  2. Deterministic — same input → same output.
  3. Never raises.
  4. Singleton pattern for AssetMetricsBuilder.

Public API:
    GEOMETRY_SCALE_CLASSES
    PIVOT_TYPES
    GEOMETRY_ROLES
    HERO_PLACEMENT_TYPES
    STRUCTURAL_PLACEMENT_TYPES
    STRUCTURAL_CATEGORIES
    SupportSurface
    GroundContact
    AssetMetrics
    AssetMetricsBuilder
    get_asset_metrics_builder()
    reset_asset_metrics_builder_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GEOMETRY_SCALE_CLASSES = frozenset({
    "tiny", "small", "medium", "large", "structural", "hero",
})

PIVOT_TYPES = frozenset({
    "bottom_center", "center", "bottom_left", "top_center", "custom",
})

GEOMETRY_ROLES = frozenset({
    "prop", "furniture", "structure", "vehicle", "character",
    "vegetation", "hero_asset", "unknown",
})

# Hero placement types — dominant focal elements classified as "hero" scale
HERO_PLACEMENT_TYPES = frozenset({
    "machine", "large_machine", "vehicle", "crane", "main_prop",
    "industrial_machine", "reactor", "engine",
})

# Placement types that always route to structural
STRUCTURAL_PLACEMENT_TYPES = frozenset({
    "wall", "column", "platform", "crane", "terrain",
    "beam", "roof", "support_column", "support_beam",
    "floor_panel", "ceiling", "door_frame", "arch",
})

# Asset categories that default to structural
STRUCTURAL_CATEGORIES = frozenset({
    "structure", "architectural", "terrain",
})

# Scale thresholds (max_dim in meters)
_SCALE_THRESHOLDS = [
    (0.15, "tiny"),
    (0.50, "small"),
    (1.50, "medium"),
    (4.00, "large"),
]

# Placement types expected to provide support surfaces
_SURFACE_PROVIDING_TYPES = frozenset({
    "table", "desk", "workbench", "shelf", "cabinet",
    "counter", "bar_counter", "console", "rack",
    "server_rack", "display_case", "crate", "pallet",
})

# Role mapping from placement type
_PLACEMENT_TO_ROLE: Dict[str, str] = {
    "table":           "furniture",
    "chair":           "furniture",
    "desk":            "furniture",
    "stool":           "furniture",
    "bench":           "furniture",
    "cabinet":         "furniture",
    "shelf":           "furniture",
    "workbench":       "furniture",
    "sofa":            "furniture",
    "bed":             "furniture",
    "wardrobe":        "furniture",
    "wall":            "structure",
    "column":          "structure",
    "beam":            "structure",
    "roof":            "structure",
    "floor_panel":     "structure",
    "ceiling":         "structure",
    "platform":        "structure",
    "door_frame":      "structure",
    "arch":            "structure",
    "terrain":         "structure",
    "machine":         "hero_asset",
    "large_machine":   "hero_asset",
    "industrial_machine": "hero_asset",
    "crane":           "hero_asset",
    "reactor":         "hero_asset",
    "engine":          "hero_asset",
    "vehicle":         "vehicle",
    "character":       "character",
    "vegetation":      "vegetation",
    "tree":            "vegetation",
    "plant":           "vegetation",
    "main_prop":       "hero_asset",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SupportSurface:
    """A horizontal surface on which child assets can be placed."""

    surface_type:  str         = ""               # tabletop, shelf, worktop, countertop, floor
    height_m:      float       = 0.0              # distance from asset base to surface top (m)
    area_m2:       float       = 0.0              # usable surface area in m²
    normal:        List[float] = field(default_factory=lambda: [0.0, 1.0, 0.0])
    load_capacity: str         = "light"          # light / medium / heavy
    notes:         str         = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "surface_type":  self.surface_type,
            "height_m":      self.height_m,
            "area_m2":       self.area_m2,
            "normal":        list(self.normal),
            "load_capacity": self.load_capacity,
            "notes":         self.notes,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SupportSurface":
        return cls(
            surface_type  = str(d.get("surface_type", "")),
            height_m      = float(d.get("height_m", 0.0)),
            area_m2       = float(d.get("area_m2", 0.0)),
            normal        = list(d.get("normal", [0.0, 1.0, 0.0])),
            load_capacity = str(d.get("load_capacity", "light")),
            notes         = str(d.get("notes", "")),
        )


@dataclass
class GroundContact:
    """Points where the asset makes contact with the floor."""

    contact_type: str              = ""    # leg, base_ring, base_plane, wheel, foot, skid, track
    count:        int              = 0     # number of contact points
    positions:    List[List[float]] = field(default_factory=list)  # [[x,y,z], ...]
    description:  str              = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contact_type": self.contact_type,
            "count":        self.count,
            "positions":    [list(p) for p in self.positions],
            "description":  self.description,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GroundContact":
        return cls(
            contact_type = str(d.get("contact_type", "")),
            count        = int(d.get("count", 0)),
            positions    = [list(p) for p in d.get("positions", [])],
            description  = str(d.get("description", "")),
        )


@dataclass
class AssetMetrics:
    """
    Complete geometry intelligence for one asset.

    This is the authoritative source of truth for all placement, environment
    construction, lookdev, and cinematic systems. Replaces SpatialMetadata
    and AssetScaleProfile for geometry-aware workflows.
    """

    asset_id:          str   = ""
    asset_name:        str   = ""

    # Bounding box in meters (authoritative)
    width_m:           float = 1.0       # X axis
    height_m:          float = 1.0       # Y axis (up)
    depth_m:           float = 1.0       # Z axis
    volume_m3:         float = 1.0
    footprint_m2:      float = 1.0
    placement_radius:  float = 0.5

    # Raw bbox corners in object space
    bbox_min:          List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    bbox_max:          List[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])

    # Pivot
    pivot_type:        str         = "bottom_center"
    pivot_position:    List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    pivot_confidence:  float       = 1.0

    # Surfaces and contacts
    support_surfaces:  List[SupportSurface] = field(default_factory=list)
    ground_contacts:   List[GroundContact]  = field(default_factory=list)

    # Classification
    scale_class:       str   = "medium"   # tiny/small/medium/large/structural/hero
    role:              str   = "prop"     # furniture/structure/vehicle/hero_asset/prop/…
    placement_type:    str   = ""
    category:          str   = ""
    is_structural:     bool  = False
    is_hero:           bool  = False

    # Provenance
    source:            str   = "estimated"   # explicit/format_metadata/estimated
    source_unit:       str   = "meters"
    format:            str   = ""            # fbx/obj/gltf/usd/etc.

    # Quality
    errors:            List[str] = field(default_factory=list)
    warnings:          List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":         self.asset_id,
            "asset_name":       self.asset_name,
            "width_m":          self.width_m,
            "height_m":         self.height_m,
            "depth_m":          self.depth_m,
            "volume_m3":        self.volume_m3,
            "footprint_m2":     self.footprint_m2,
            "placement_radius": self.placement_radius,
            "bbox_min":         list(self.bbox_min),
            "bbox_max":         list(self.bbox_max),
            "pivot_type":       self.pivot_type,
            "pivot_position":   list(self.pivot_position),
            "pivot_confidence": self.pivot_confidence,
            "support_surfaces": [s.to_dict() for s in self.support_surfaces],
            "ground_contacts":  [c.to_dict() for c in self.ground_contacts],
            "scale_class":      self.scale_class,
            "role":             self.role,
            "placement_type":   self.placement_type,
            "category":         self.category,
            "is_structural":    self.is_structural,
            "is_hero":          self.is_hero,
            "source":           self.source,
            "source_unit":      self.source_unit,
            "format":           self.format,
            "errors":           list(self.errors),
            "warnings":         list(self.warnings),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssetMetrics":
        obj = cls(
            asset_id         = str(d.get("asset_id", "")),
            asset_name       = str(d.get("asset_name", "")),
            width_m          = float(d.get("width_m", 1.0)),
            height_m         = float(d.get("height_m", 1.0)),
            depth_m          = float(d.get("depth_m", 1.0)),
            volume_m3        = float(d.get("volume_m3", 1.0)),
            footprint_m2     = float(d.get("footprint_m2", 1.0)),
            placement_radius = float(d.get("placement_radius", 0.5)),
            bbox_min         = list(d.get("bbox_min", [0.0, 0.0, 0.0])),
            bbox_max         = list(d.get("bbox_max", [1.0, 1.0, 1.0])),
            pivot_type       = str(d.get("pivot_type", "bottom_center")),
            pivot_position   = list(d.get("pivot_position", [0.0, 0.0, 0.0])),
            pivot_confidence = float(d.get("pivot_confidence", 1.0)),
            scale_class      = str(d.get("scale_class", "medium")),
            role             = str(d.get("role", "prop")),
            placement_type   = str(d.get("placement_type", "")),
            category         = str(d.get("category", "")),
            is_structural    = bool(d.get("is_structural", False)),
            is_hero          = bool(d.get("is_hero", False)),
            source           = str(d.get("source", "estimated")),
            source_unit      = str(d.get("source_unit", "meters")),
            format           = str(d.get("format", "")),
            errors           = list(d.get("errors", [])),
            warnings         = list(d.get("warnings", [])),
        )
        obj.support_surfaces = [
            SupportSurface.from_dict(s)
            for s in d.get("support_surfaces", [])
        ]
        obj.ground_contacts = [
            GroundContact.from_dict(c)
            for c in d.get("ground_contacts", [])
        ]
        return obj


def classify_geometry_scale(
    max_dim: float,
    placement_type: str,
    category: str,
) -> tuple:
    """Return (scale_class, is_structural, is_hero) for the given asset."""
    pt = placement_type.lower().strip()
    cat = category.lower().strip()

    if pt in STRUCTURAL_PLACEMENT_TYPES or cat in STRUCTURAL_CATEGORIES:
        return "structural", True, False

    if pt in HERO_PLACEMENT_TYPES:
        return "hero", False, True

    if max_dim >= 4.0:
        return "structural", True, False

    for threshold, cls in _SCALE_THRESHOLDS:
        if max_dim < threshold:
            return cls, False, False

    return "large", False, False


def infer_role(placement_type: str, category: str, scale_class: str) -> str:
    """Infer the production role for an asset."""
    pt = placement_type.lower().strip()
    if pt in _PLACEMENT_TO_ROLE:
        return _PLACEMENT_TO_ROLE[pt]
    cat = category.lower().strip()
    if cat in ("structure", "architectural"):
        return "structure"
    if cat in ("vehicle",):
        return "vehicle"
    if cat in ("character", "human", "humanoid"):
        return "character"
    if cat in ("vegetation", "foliage", "plant"):
        return "vegetation"
    if scale_class == "structural":
        return "structure"
    if scale_class == "hero":
        return "hero_asset"
    return "prop"


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class AssetMetricsBuilder:
    """
    Creates AssetMetrics by orchestrating all geometry detectors.

    This is a thin coordinator; the actual extraction logic lives in the
    individual detector modules (bounding_box_extractor, pivot_detector, etc.).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build(self, asset: Dict[str, Any]) -> AssetMetrics:
        """Build AssetMetrics for one asset. Never raises."""
        try:
            return self._build(asset)
        except Exception as exc:
            d = asset if isinstance(asset, dict) else {}
            m = AssetMetrics(
                asset_id   = str(d.get("asset_id") or d.get("name") or ""),
                asset_name = str(d.get("name") or d.get("asset_id") or ""),
            )
            m.errors.append(f"AssetMetricsBuilder.build failed: {exc}")
            return m

    def _build(self, asset: Dict[str, Any]) -> AssetMetrics:
        from src.runtime.assets.geometry.bounding_box_extractor import get_geometry_bbox_extractor
        from src.runtime.assets.geometry.pivot_detector import get_pivot_detector
        from src.runtime.assets.geometry.ground_contact_detector import get_ground_contact_detector
        from src.runtime.assets.geometry.support_surface_detector import get_support_surface_detector

        asset_id   = str(asset.get("asset_id") or asset.get("id") or "")
        asset_name = str(asset.get("name") or asset_id)
        pt = str(asset.get("placement_type") or "").lower().strip()
        cat = str(asset.get("category") or "").lower().strip()
        fmt = str(asset.get("format") or asset.get("file_format") or "").lower().strip()

        # 1. Bounding box
        bbox_result = get_geometry_bbox_extractor().extract(asset)
        w = bbox_result["width_m"]
        h = bbox_result["height_m"]
        d = bbox_result["depth_m"]
        max_dim = max(w, h, d)

        # 2. Scale classification
        scale_class, is_structural, is_hero = classify_geometry_scale(max_dim, pt, cat)
        role = infer_role(pt, cat, scale_class)

        # 3. Pivot
        pivot_result = get_pivot_detector().detect(asset, h)

        # 4. Ground contacts
        contacts = get_ground_contact_detector().detect(asset, w, h, d)

        # 5. Support surfaces
        surfaces = get_support_surface_detector().detect(asset, w, h, d)

        metrics = AssetMetrics(
            asset_id         = asset_id,
            asset_name       = asset_name,
            width_m          = w,
            height_m         = h,
            depth_m          = d,
            volume_m3        = w * h * d,
            footprint_m2     = w * d,
            placement_radius = max(w, d) / 2.0,
            bbox_min         = bbox_result["bbox_min"],
            bbox_max         = bbox_result["bbox_max"],
            pivot_type       = pivot_result["pivot_type"],
            pivot_position   = pivot_result["pivot_position"],
            pivot_confidence = pivot_result["confidence"],
            support_surfaces = surfaces,
            ground_contacts  = contacts,
            scale_class      = scale_class,
            role             = role,
            placement_type   = pt,
            category         = cat,
            is_structural    = is_structural,
            is_hero          = is_hero,
            source           = bbox_result["source"],
            source_unit      = bbox_result.get("source_unit", "meters"),
            format           = fmt,
            warnings         = bbox_result.get("warnings", []),
        )
        return metrics


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetMetricsBuilder] = None
_LOCK = threading.Lock()


def get_asset_metrics_builder() -> AssetMetricsBuilder:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = AssetMetricsBuilder()
        return _INSTANCE


def reset_asset_metrics_builder_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
