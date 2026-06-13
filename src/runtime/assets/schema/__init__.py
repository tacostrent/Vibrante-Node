"""
Asset Intelligence Schema (Tier 8)
====================================
Canonical typed representations for the Asset Intelligence Runtime.

All models are dataclasses with to_dict / from_dict / to_json / from_json.
No Houdini imports.  No bridge calls.  Pure data layer.
"""

from .asset_descriptor import (
    SCHEMA_VERSION,
    ASSET_CATEGORIES,
    ASSET_FORMATS,
    LICENSE_TYPES,
    SCALE_TYPES,
    ASSET_STYLES,
    AssetMetadata,
    AssetPreview,
    AssetDescriptor,
    AssetProviderResult,
    AssetQueryResult,
    AssetRecommendation,
)

__all__ = [
    "SCHEMA_VERSION",
    "ASSET_CATEGORIES",
    "ASSET_FORMATS",
    "LICENSE_TYPES",
    "SCALE_TYPES",
    "ASSET_STYLES",
    "AssetMetadata",
    "AssetPreview",
    "AssetDescriptor",
    "AssetProviderResult",
    "AssetQueryResult",
    "AssetRecommendation",
]
