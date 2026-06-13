"""
identity_metadata_writer.py — Tier 14.4.5 Asset Identity Audit
===============================================================
Extends the Tier 14.4.4 relationship metadata with 3 identity keys that
make per-asset semantic identity auditable from Houdini user-data alone.

New Houdini user-data keys (vibrante_ prefix):
    vibrante_asset_id         catalog asset_id (the canonical identifier)
    vibrante_asset_name       human-readable display name (never an opaque ID)
    vibrante_asset_category   semantic category (furniture / prop / structural / …)

These 3 keys are written alongside the 9 existing Tier 14.4.4 relationship keys,
giving every realized Houdini node a complete 12-key identity block.

No bridge calls in this module. All write-back is handled by
metadata_application_engine.py, which already calls set_user_data() for the
existing 9 keys and is extended to call the identity writer as well.

Public API:
    IDENTITY_KEYS
    AssetIdentityMetadata
    IdentityMetadataWriter
    build_identity_userdata            helper (no instance needed)
    get_identity_metadata_writer()
    reset_identity_metadata_writer_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.runtime.layout_realization.transform_resolver import ResolvedTransform

# ---------------------------------------------------------------------------
# Key names
# ---------------------------------------------------------------------------

IDENTITY_KEYS: List[str] = [
    "vibrante_asset_id",
    "vibrante_asset_name",
    "vibrante_asset_category",
]

# Category inference: relationship type and asset_name keywords → category
_NAME_CATEGORY_HINTS: List[tuple] = [
    # (substring_in_name, category)
    ("chair",     "furniture"),
    ("table",     "furniture"),
    ("bench",     "furniture"),
    ("stool",     "furniture"),
    ("sofa",      "furniture"),
    ("desk",      "furniture"),
    ("shelf",     "furniture"),
    ("cabinet",   "furniture"),
    ("wardrobe",  "furniture"),
    ("counter",   "furniture"),
    ("bar_",      "furniture"),
    ("barrel",    "prop"),
    ("crate",     "prop"),
    ("bottle",    "prop"),
    ("bucket",    "prop"),
    ("lantern",   "prop"),
    ("torch",     "prop"),
    ("lamp",      "lighting"),
    ("light",     "lighting"),
    ("candle",    "prop"),
    ("poster",    "signage"),
    ("sign",      "signage"),
    ("banner",    "signage"),
    ("painting",  "artwork"),
    ("mirror",    "prop"),
    ("clock",     "prop"),
    ("book",      "prop"),
    ("machine",   "machine"),
    ("reactor",   "machine"),
    ("console",   "machine"),
    ("server",    "machine"),
    ("crane",     "machine"),
    ("beam",      "structural"),
    ("column",    "structural"),
    ("pillar",    "structural"),
    ("wall",      "structural"),
    ("floor",     "structural"),
    ("arch",      "structural"),
    ("stair",     "structural"),
    ("railing",   "structural"),
    ("door",      "structural"),
    ("window",    "structural"),
    ("vehicle",   "vehicle"),
    ("cart",      "vehicle"),
    ("wagon",     "vehicle"),
    ("barrel",    "prop"),
    ("rope",      "prop"),
    ("chain",     "prop"),
]

_ROLE_CATEGORY_DEFAULTS: Dict[str, str] = {
    "anchor":          "furniture",
    "cluster_member":  "furniture",
    "surface_child":   "prop",
    "wall_mount":      "prop",
    "ceiling_mount":   "lighting",
    "wall_adjacent":   "furniture",
    "decoration":      "prop",
    "proximity_prop":  "prop",
    "prop":            "prop",
    "container":       "prop",
    "container_child": "prop",
}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class AssetIdentityMetadata:
    """Identity metadata record for one realized asset."""

    asset_id:       str
    asset_name:     str
    asset_category: str

    def to_houdini_userdata(self) -> Dict[str, str]:
        """Return dict of Houdini user-data key-value strings."""
        return {
            "vibrante_asset_id":       self.asset_id,
            "vibrante_asset_name":     self.asset_name,
            "vibrante_asset_category": self.asset_category,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":       self.asset_id,
            "asset_name":     self.asset_name,
            "asset_category": self.asset_category,
        }


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class IdentityMetadataWriter:
    """
    Derives AssetIdentityMetadata from a ResolvedTransform and an optional
    asset_category override.

    asset_category resolution order:
      1. Explicit override passed to build_metadata_records() / build_identity_userdata()
      2. Keyword match against asset_name
      3. Default by vibrante_asset_role
      4. Fallback: "prop"
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_metadata_records(
        self,
        transforms:      List[ResolvedTransform],
        category_map:    Optional[Dict[str, str]] = None,
    ) -> List[AssetIdentityMetadata]:
        """
        Build one AssetIdentityMetadata per transform.
        category_map: {asset_id → category_string}  (optional explicit overrides)
        Never raises.
        """
        try:
            return self._build(transforms, category_map or {})
        except Exception:
            return []

    def _build(
        self,
        transforms:   List[ResolvedTransform],
        category_map: Dict[str, str],
    ) -> List[AssetIdentityMetadata]:
        records: List[AssetIdentityMetadata] = []
        for xf in transforms:
            explicit_cat = category_map.get(xf.asset_id, "")
            records.append(_derive_identity(xf, explicit_cat))
        return records


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------

def build_identity_userdata(
    xf:              ResolvedTransform,
    asset_category:  str = "",
) -> Dict[str, str]:
    """
    Derive Houdini user-data dict from a single ResolvedTransform.
    Returns the to_houdini_userdata() dict (all string values).
    """
    meta = _derive_identity(xf, asset_category)
    return meta.to_houdini_userdata()


# ---------------------------------------------------------------------------
# Derivation (private)
# ---------------------------------------------------------------------------

def _derive_identity(
    xf:              ResolvedTransform,
    explicit_cat:    str,
) -> AssetIdentityMetadata:
    asset_id   = xf.asset_id   or ""
    asset_name = xf.asset_name or ""

    category = explicit_cat.strip()
    if not category:
        category = _infer_category_from_name(asset_name)
    if not category:
        role = getattr(xf, "relationship", "") or getattr(xf, "asset_role", "") or ""
        category = _ROLE_CATEGORY_DEFAULTS.get(role, "prop")

    return AssetIdentityMetadata(
        asset_id       = asset_id,
        asset_name     = asset_name,
        asset_category = category,
    )


def _infer_category_from_name(name: str) -> str:
    lower = name.lower()
    for hint, cat in _NAME_CATEGORY_HINTS:
        if hint in lower:
            return cat
    return ""


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[IdentityMetadataWriter] = None
_lock = threading.Lock()


def get_identity_metadata_writer() -> IdentityMetadataWriter:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = IdentityMetadataWriter()
    return _instance


def reset_identity_metadata_writer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
