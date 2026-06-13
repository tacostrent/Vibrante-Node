"""
Provider Normalizer (Tier 12 — Asset Ecosystem Expansion)
==========================================================
Normalize all provider outputs to AssetDescriptor.

Handles different provider field names, fills defaults,
and maps provider-specific categories to canonical ASSET_CATEGORIES.

Public API:
    ProviderNormalizer               — class
    get_provider_normalizer()        — singleton
    reset_provider_normalizer_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import (
    ASSET_CATEGORIES, ASSET_FORMATS,
    AssetDescriptor, AssetMetadata, AssetPreview,
)

# Category maps: provider-specific category names → canonical ASSET_CATEGORIES
_SKETCHFAB_CATEGORY_MAP: Dict[str, str] = {
    "vehicles":         "vehicle",
    "vehicle":          "vehicle",
    "characters":       "character",
    "character":        "character",
    "weapons":          "weapon",
    "weapon":           "weapon",
    "architecture":     "structure",
    "architectural":    "architectural",
    "electronics":      "electronic",
    "electronic":       "electronic",
    "nature":           "vegetation",
    "vegetation":       "vegetation",
    "props":            "prop",
    "prop":             "prop",
    "robots":           "robot",
    "robot":            "robot",
    "creatures":        "creature",
    "creature":         "creature",
    "furniture":        "furniture",
    "machinery":        "machinery",
    "structure":        "structure",
    "terrain":          "terrain",
    "environment":      "environment",
    "material":         "material",
    "hdri":             "hdri",
    "abstract":         "abstract",
    "organic":          "organic",
    "other":            "other",
}

_QUIXEL_CATEGORY_MAP: Dict[str, str] = {
    "surfaces":         "material",
    "props":            "prop",
    "atlases":          "material",
    "3d plants":        "vegetation",
    "decals":           "material",
    "brush":            "terrain",
    "3d asset":         "prop",
    "character":        "character",
    "vehicle":          "vehicle",
    "hdri":             "hdri",
    "environment":      "environment",
}

_POLYHAVEN_CATEGORY_MAP: Dict[str, str] = {
    "hdris":            "hdri",
    "hdri":             "hdri",
    "textures":         "material",
    "texture":          "material",
    "material":         "material",
    "models":           "prop",
    "model":            "prop",
    "vegetation":       "vegetation",
    "terrain":          "terrain",
    "environment":      "environment",
}

_PROVIDER_CATEGORY_MAPS: Dict[str, Dict[str, str]] = {
    "sketchfab":       _SKETCHFAB_CATEGORY_MAP,
    "sketchfab_live":  _SKETCHFAB_CATEGORY_MAP,
    "quixel":          _QUIXEL_CATEGORY_MAP,
    "polyhaven":       _POLYHAVEN_CATEGORY_MAP,
}


class ProviderNormalizer:
    """
    Normalizes provider-specific raw dicts to AssetDescriptor.

    Deterministic — same raw input always produces the same output.
    """

    def __init__(self) -> None:
        self._lock:            threading.Lock = threading.Lock()
        self._normalized_count: int = 0

    def normalize_asset(
        self,
        raw_dict: Dict[str, Any],
        provider_name: str,
    ) -> AssetDescriptor:
        """
        Normalize a raw provider dict to AssetDescriptor.

        Handles different field names across providers.
        Fills sensible defaults for missing fields.
        """
        # Determine asset_id
        uid = str(raw_dict.get("uid") or raw_dict.get("id") or raw_dict.get("asset_id") or "")
        prefix = provider_name[:4] if provider_name else "prov"
        asset_id = f"{prefix}_{uid}" if uid and not uid.startswith(prefix) else uid or f"{prefix}_unknown"

        # Normalize name
        name = str(raw_dict.get("name") or raw_dict.get("title") or uid or "unknown")

        # Normalize category
        raw_cat = (
            raw_dict.get("category") or
            (raw_dict.get("categories", [None])[0] if raw_dict.get("categories") else None) or
            "other"
        )
        category = self.normalize_category(str(raw_cat), provider_name)

        # Normalize tags
        raw_tags = (
            raw_dict.get("tags") or
            raw_dict.get("keywords") or
            []
        )
        tags = self.normalize_tags(
            raw_tags if isinstance(raw_tags, list) else [str(raw_tags)],
            provider_name,
        )

        # Formats
        raw_formats = raw_dict.get("formats") or raw_dict.get("file_formats") or []
        formats = [
            f.lower() for f in raw_formats
            if isinstance(f, str) and f.lower() in ASSET_FORMATS
        ]

        # License
        license_raw = raw_dict.get("license") or raw_dict.get("licence") or {}
        if isinstance(license_raw, dict):
            slug = str(license_raw.get("slug") or license_raw.get("type") or "unknown")
        else:
            slug = str(license_raw)
        license_str = _normalize_license(slug)

        # Preview
        preview_url = str(
            raw_dict.get("preview_url") or
            raw_dict.get("thumbnail") or
            ""
        )
        preview_imgs = raw_dict.get("preview", {}).get("images", []) if isinstance(raw_dict.get("preview"), dict) else []
        if preview_imgs and not preview_url:
            preview_url = str(preview_imgs[0].get("url", ""))

        # Download URL
        download_url = str(
            raw_dict.get("download_url") or
            raw_dict.get("viewerUrl") or
            raw_dict.get("local_path") or
            ""
        )

        # Stats
        stats = raw_dict.get("stats") or {}
        if isinstance(stats, dict):
            like_count = int(stats.get("likeCount") or stats.get("likes") or 0)
            view_count = int(stats.get("viewCount") or stats.get("views") or 0)
        else:
            like_count = 0
            view_count = 0
        rating = min(5.0, float(raw_dict.get("rating") or like_count / max(200.0, 1.0)))
        popularity = int(raw_dict.get("popularity") or view_count)

        # Scale / style
        scale = str(raw_dict.get("scale") or "unknown")
        style = str(raw_dict.get("style") or "unknown")

        # Environments
        envs = list(raw_dict.get("environments") or raw_dict.get("environment_suitability") or [])

        metadata = self.normalize_metadata(raw_dict, provider_name)
        preview_obj = self.normalize_preview(raw_dict, provider_name)

        with self._lock:
            self._normalized_count += 1

        return AssetDescriptor(
            asset_id=asset_id,
            provider=provider_name,
            name=name,
            category=category,
            subcategory=str(raw_dict.get("subcategory") or ""),
            tags=tags,
            keywords=list(raw_dict.get("keywords") or []),
            license=license_str,
            formats=formats,
            preview_url=preview_url,
            download_url=download_url,
            preview=preview_obj,
            dimensions={},
            scale=scale,
            rating=rating,
            popularity=popularity,
            style=style,
            environment_suitability=envs,
            metadata=metadata,
        )

    def normalize_metadata(
        self,
        raw_dict: Dict[str, Any],
        provider_name: str,
    ) -> AssetMetadata:
        """Normalize metadata fields from a raw provider dict."""
        return AssetMetadata(
            face_count=int(raw_dict.get("faceCount") or raw_dict.get("face_count") or 0),
            vertex_count=int(raw_dict.get("vertexCount") or raw_dict.get("vertex_count") or 0),
            is_animated=bool(raw_dict.get("isAnimated") or raw_dict.get("is_animated") or False),
            is_rigged=bool(raw_dict.get("isRigged") or raw_dict.get("is_rigged") or False),
            texture_count=int(raw_dict.get("textureCount") or raw_dict.get("texture_count") or 0),
            file_size_mb=float(raw_dict.get("file_size_mb") or 0.0),
            author=str(raw_dict.get("author") or raw_dict.get("user", {}).get("displayName", "") if isinstance(raw_dict.get("user"), dict) else ""),
            source_url=str(raw_dict.get("source_url") or raw_dict.get("viewerUrl") or ""),
        )

    def normalize_preview(
        self,
        raw_dict: Dict[str, Any],
        provider_name: str,
    ) -> Optional[AssetPreview]:
        """Normalize preview data from a raw provider dict."""
        uid = str(raw_dict.get("uid") or raw_dict.get("id") or "")
        asset_id = f"{provider_name[:4]}_{uid}" if uid else f"{provider_name[:4]}_unknown"

        # Extract preview URL from various shapes
        preview_url = ""
        preview_data = raw_dict.get("preview")
        if isinstance(preview_data, dict):
            imgs = preview_data.get("images", [])
            if imgs and isinstance(imgs[0], dict):
                preview_url = str(imgs[0].get("url", ""))
        elif isinstance(preview_data, str):
            preview_url = preview_data

        if not preview_url:
            preview_url = str(raw_dict.get("preview_url") or raw_dict.get("thumbnail") or "")

        if not preview_url:
            return None

        return AssetPreview(
            asset_id=asset_id,
            provider=provider_name,
            url=preview_url,
            thumbnail_url=preview_url,
        )

    def normalize_tags(
        self,
        raw_tags: List[Any],
        provider_name: str,
    ) -> List[str]:
        """
        Normalize a list of raw tags.

        Operations: lowercase, strip, deduplicate, remove empty strings.
        """
        seen: set = set()
        result: List[str] = []
        for tag in raw_tags:
            if not isinstance(tag, (str, int, float)):
                continue
            normalized = str(tag).lower().strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result

    def normalize_category(
        self,
        raw_category: str,
        provider_name: str,
    ) -> str:
        """
        Map a provider-specific category to a canonical ASSET_CATEGORIES value.

        Falls back to "prop" if no match found.
        """
        lower = raw_category.lower().strip()
        # Check provider-specific map
        cat_map = _PROVIDER_CATEGORY_MAPS.get(provider_name, {})
        if lower in cat_map:
            return cat_map[lower]
        # Direct match against ASSET_CATEGORIES
        if lower in ASSET_CATEGORIES:
            return lower
        # Partial match
        for cat in ASSET_CATEGORIES:
            if cat in lower or lower in cat:
                return cat
        return "prop"

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"normalized_count": self._normalized_count}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_LICENSE_SLUG_MAP: Dict[str, str] = {
    "cc0":        "cc0",
    "by":         "cc-by",
    "cc-by":      "cc-by",
    "by-sa":      "cc-by-sa",
    "by-nc":      "cc-by-nc",
    "by-nc-sa":   "cc-by-nc-sa",
    "editorial":  "editorial_only",
    "commercial": "commercial",
    "royalty_free": "royalty_free",
    "unknown":    "unknown",
}


def _normalize_license(slug: str) -> str:
    lower = slug.lower().strip()
    return _LICENSE_SLUG_MAP.get(lower, "unknown")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_NORMALIZER: Optional[ProviderNormalizer] = None
_NORMALIZER_LOCK = threading.Lock()


def get_provider_normalizer() -> ProviderNormalizer:
    """Return the module-level singleton ProviderNormalizer."""
    global _NORMALIZER
    if _NORMALIZER is None:
        with _NORMALIZER_LOCK:
            if _NORMALIZER is None:
                _NORMALIZER = ProviderNormalizer()
    return _NORMALIZER


def reset_provider_normalizer_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _NORMALIZER
    with _NORMALIZER_LOCK:
        _NORMALIZER = None
