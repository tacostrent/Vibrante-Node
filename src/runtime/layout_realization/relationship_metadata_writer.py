"""
relationship_metadata_writer.py — §47 Tier 14.4.4 Relationship Metadata Persistence
======================================================================================
Pure planning module. Derives AssetRelationshipMetadata from ResolvedTransform
objects and builds Houdini user-data dicts ready for write-back.

No bridge calls in this module. All bridge I/O is handled by:
  metadata_application_engine.py  — writes user-data to Houdini nodes
  relationship_persistence_auditor.py — reads and validates user-data

Metadata keys written to every realized Houdini node (vibrante_ prefix avoids
clashing with standard Houdini user-data):

    vibrante_asset_role         role inferred from relationship type
    vibrante_relationship_type  relationship string from ResolvedTransform
    vibrante_expected_parent    planned parent_id
    vibrante_actual_parent      same as expected_parent at write time
    vibrante_support_surface    surface type extracted from transform notes
    vibrante_anchor_id          parent_id for around/supports relationships
    vibrante_anchor_type        anchor type inferred from anchor_id
    vibrante_placement_engine   engine that generated this transform
    vibrante_layout_cluster_id  cluster_id from ResolvedTransform

Public API:
    METADATA_KEYS
    AssetRelationshipMetadata
    RelationshipMetadataWriter
    build_userdata_from_transform          helper (no instance needed)
    get_relationship_metadata_writer()
    reset_relationship_metadata_writer_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout_realization.transform_resolver import ResolvedTransform

# ---------------------------------------------------------------------------
# Metadata key names
# ---------------------------------------------------------------------------

METADATA_KEYS: List[str] = [
    "vibrante_asset_role",
    "vibrante_relationship_type",
    "vibrante_expected_parent",
    "vibrante_actual_parent",
    "vibrante_support_surface",
    "vibrante_anchor_id",
    "vibrante_anchor_type",
    "vibrante_placement_engine",
    "vibrante_layout_cluster_id",
]

# ---------------------------------------------------------------------------
# Role inference from relationship type
# ---------------------------------------------------------------------------

_ROLE_MAP: Dict[str, str] = {
    "anchor":       "anchor",
    "around":       "cluster_member",
    "supports":     "surface_child",
    "on_top_of":    "surface_child",
    "attached_to":  "wall_mount",
    "against":      "wall_adjacent",
    "hanging_from": "ceiling_mount",
    "mounted_on":   "wall_mount",
    "near":         "proximity_prop",
    "inside":       "container_child",
    "contains":     "container",
    "facing":       "cluster_member",
    "scattered":    "decoration",
}

_ENGINE_MAP: Dict[str, str] = {
    "anchor":       "AnchorLayoutEngine",
    "around":       "FurnitureClusterBuilder",
    "supports":     "SurfacePlacementEngine",
    "on_top_of":    "SurfacePlacementEngine",
    "attached_to":  "WallAttachmentEngine",
    "against":      "WallAttachmentEngine",
    "hanging_from": "WallAttachmentEngine",
    "mounted_on":   "WallAttachmentEngine",
    "near":         "DecorationLayoutEngine",
    "inside":       "DecorationLayoutEngine",
    "facing":       "FurnitureClusterBuilder",
    "scattered":    "DecorationLayoutEngine",
}

# Types commonly used as anchors — used for quick anchor_type inference from id strings
_ANCHOR_TYPE_HINTS: List[str] = [
    "table", "machine", "large_machine", "bar_counter", "desk", "workbench",
    "fireplace", "console", "campfire", "shelf", "throne", "altar", "reactor",
    "piano", "bed", "sofa",
]


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class AssetRelationshipMetadata:
    """Full relationship metadata record for one realized asset."""

    asset_id:          str
    asset_name:        str
    node_path:         str

    asset_role:        str = ""
    relationship_type: str = ""
    expected_parent:   str = ""
    actual_parent:     str = ""     # same as expected_parent at write time
    support_surface:   str = ""
    anchor_id:         str = ""
    anchor_type:       str = ""
    placement_engine:  str = ""
    layout_cluster_id: str = ""

    def to_houdini_userdata(self) -> Dict[str, str]:
        """Return dict of Houdini user-data key-value strings ready for setUserData()."""
        return {
            "vibrante_asset_role":         self.asset_role,
            "vibrante_relationship_type":  self.relationship_type,
            "vibrante_expected_parent":    self.expected_parent,
            "vibrante_actual_parent":      self.actual_parent,
            "vibrante_support_surface":    self.support_surface,
            "vibrante_anchor_id":          self.anchor_id,
            "vibrante_anchor_type":        self.anchor_type,
            "vibrante_placement_engine":   self.placement_engine,
            "vibrante_layout_cluster_id":  self.layout_cluster_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":          self.asset_id,
            "asset_name":        self.asset_name,
            "node_path":         self.node_path,
            "asset_role":        self.asset_role,
            "relationship_type": self.relationship_type,
            "expected_parent":   self.expected_parent,
            "actual_parent":     self.actual_parent,
            "support_surface":   self.support_surface,
            "anchor_id":         self.anchor_id,
            "anchor_type":       self.anchor_type,
            "placement_engine":  self.placement_engine,
            "layout_cluster_id": self.layout_cluster_id,
        }


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class RelationshipMetadataWriter:
    """
    Converts a list of ResolvedTransform objects to AssetRelationshipMetadata
    records, one per asset.

    anchor_type_map (optional): {anchor_id → anchor_type_string}
    Callers may supply this from the LayoutPlan anchor_placements list so the
    anchor_type field is populated accurately instead of being inferred from
    the anchor_id string.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_metadata_records(
        self,
        transforms:      List[ResolvedTransform],
        node_path_map:   Dict[str, str],
        anchor_type_map: Optional[Dict[str, str]] = None,
    ) -> List[AssetRelationshipMetadata]:
        """
        Build one AssetRelationshipMetadata per transform.

        Assets without a node_path in node_path_map still get a record
        (node_path="") so the metadata is available for dry-run inspection.

        Never raises.
        """
        try:
            return self._build(transforms, node_path_map, anchor_type_map or {})
        except Exception:
            return []

    def _build(
        self,
        transforms:      List[ResolvedTransform],
        node_path_map:   Dict[str, str],
        anchor_type_map: Dict[str, str],
    ) -> List[AssetRelationshipMetadata]:
        records: List[AssetRelationshipMetadata] = []
        for xf in transforms:
            records.append(_derive_metadata(xf, node_path_map, anchor_type_map))
        return records


# ---------------------------------------------------------------------------
# Module-level helper — used by layout_application_engine to avoid an instance
# ---------------------------------------------------------------------------

def build_userdata_from_transform(
    xf: ResolvedTransform,
    anchor_type_map: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Derive Houdini user-data dict from a single ResolvedTransform.
    Returns the to_houdini_userdata() dict — all values are strings.
    """
    meta = _derive_metadata(xf, {}, anchor_type_map or {})
    return meta.to_houdini_userdata()


# ---------------------------------------------------------------------------
# Derivation logic (private)
# ---------------------------------------------------------------------------

def _derive_metadata(
    xf:              ResolvedTransform,
    node_path_map:   Dict[str, str],
    anchor_type_map: Dict[str, str],
) -> AssetRelationshipMetadata:
    rel      = xf.relationship or ""
    parent   = xf.parent_id    or ""
    cluster  = xf.cluster_id   or ""
    notes    = xf.notes        or ""

    role     = _ROLE_MAP.get(rel, "prop")
    engine   = _ENGINE_MAP.get(rel, "SemanticLayoutEngine")
    surface  = _extract_surface(notes)

    # anchor_id: the parent when the relationship implies a structural parent
    anchor_id = parent if rel in ("around", "supports", "on_top_of", "near", "facing") else ""

    # anchor_type: try explicit map first, then heuristic from id
    anchor_type = ""
    if anchor_id:
        anchor_type = anchor_type_map.get(anchor_id) or _infer_anchor_type(anchor_id)

    return AssetRelationshipMetadata(
        asset_id          = xf.asset_id,
        asset_name        = xf.asset_name,
        node_path         = node_path_map.get(xf.asset_id, ""),
        asset_role        = role,
        relationship_type = rel,
        expected_parent   = parent,
        actual_parent     = parent,
        support_surface   = surface,
        anchor_id         = anchor_id,
        anchor_type       = anchor_type,
        placement_engine  = engine,
        layout_cluster_id = cluster,
    )


def _extract_surface(notes: str) -> str:
    """
    Extract the surface-type word from a SurfacePlacementEngine notes string.
    Examples:
      "on table surface h=0.75m"  → "table"
      "on bar_counter h=1.05m"    → "bar_counter"
      "wall=wall_north h=1.60m"   → ""
    """
    if "on " not in notes:
        return ""
    after = notes[notes.index("on ") + 3:]
    # Strip " surface h=..." or " h=..." suffix
    surface = after.split(" h=")[0].replace(" surface", "").strip()
    return surface


def _infer_anchor_type(anchor_id: str) -> str:
    """Heuristic: match common anchor type names inside the anchor_id string."""
    lower = anchor_id.lower()
    for hint in _ANCHOR_TYPE_HINTS:
        if hint in lower:
            return hint
    return ""


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RelationshipMetadataWriter] = None
_lock = threading.Lock()


def get_relationship_metadata_writer() -> RelationshipMetadataWriter:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RelationshipMetadataWriter()
    return _instance


def reset_relationship_metadata_writer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
