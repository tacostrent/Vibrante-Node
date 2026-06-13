"""
Local Library Provider (Tier 8 — Asset Intelligence Runtime)
=============================================================
Provider that scans a local asset directory.

When VIBRANTE_LOCAL_ASSET_LIBRARY is set, it scans the directory for
recognised asset file formats and returns AssetDescriptor objects built
from the filesystem metadata.

When the env var is unset or the directory does not exist, the provider
returns empty results without errors — graceful degradation.

DESIGN RULES:
  - No downloads.  No external API calls.
  - Category and tags are inferred from directory structure and filename.
  - All inferred metadata is clearly marked as estimated.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import (
    AssetDescriptor, AssetMetadata, AssetPreview, AssetProviderResult,
)
from .base import AssetProvider

# File extensions we recognise as 3D assets
_3D_EXTENSIONS = frozenset({
    ".fbx", ".obj", ".gltf", ".glb", ".usd", ".usda", ".usdc", ".usdz",
    ".abc", ".ply", ".stl", ".bgeo", ".vdb",
})

# Map directory / filename fragments to categories
_CATEGORY_HINTS: Dict[str, str] = {
    "vehicle":      "vehicle",
    "car":          "vehicle",
    "truck":        "vehicle",
    "character":    "character",
    "char":         "character",
    "human":        "character",
    "robot":        "robot",
    "prop":         "prop",
    "structure":    "structure",
    "building":     "structure",
    "vegetation":   "vegetation",
    "tree":         "vegetation",
    "plant":        "vegetation",
    "machinery":    "machinery",
    "weapon":       "weapon",
    "furniture":    "furniture",
    "material":     "material",
    "terrain":      "terrain",
    "hdri":         "hdri",
}


def _infer_category(path: Path) -> str:
    parts = [p.lower() for p in path.parts] + [path.stem.lower()]
    for part in parts:
        for hint, cat in _CATEGORY_HINTS.items():
            if hint in part:
                return cat
    return "other"


def _infer_tags(path: Path) -> List[str]:
    tags = []
    for part in path.parts:
        words = part.lower().replace("-", "_").replace(" ", "_").split("_")
        tags.extend(w for w in words if len(w) > 2)
    return list(dict.fromkeys(tags))  # deduplicate, preserve order


class LocalLibraryProvider(AssetProvider):
    """
    Scans a local directory for asset files.

    Configure via: ``VIBRANTE_LOCAL_ASSET_LIBRARY=/path/to/library``
    """

    def __init__(self, library_path: Optional[str] = None) -> None:
        self._library_path: Optional[str] = library_path or os.environ.get(
            "VIBRANTE_LOCAL_ASSET_LIBRARY"
        )

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def supported_categories(self) -> List[str]:
        # Local library can hold anything
        return [
            "vehicle", "character", "structure", "prop", "vegetation",
            "creature", "furniture", "machinery", "weapon", "material",
            "hdri", "environment", "robot", "electronic", "organic",
            "abstract", "architectural", "terrain", "other",
        ]

    @property
    def is_available(self) -> bool:
        if not self._library_path:
            return False
        return Path(self._library_path).is_dir()

    def search(
        self,
        category: str,
        tags: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        style_hints: Optional[List[str]] = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> AssetProviderResult:
        t0 = time.perf_counter()
        if not self.is_available:
            return AssetProviderResult(
                provider=self.provider_name,
                query_params={"category": category},
                success=True,
                errors=[],
                query_time=time.perf_counter() - t0,
            )
        try:
            matched = self._scan(category, tags or [], keywords or [], limit)
            normalized = [self.normalize(r) for r in matched]
            return AssetProviderResult(
                provider=self.provider_name,
                query_params={"category": category, "tags": tags or [], "limit": limit},
                raw_data=matched,
                normalized_assets=normalized,
                success=True,
                errors=[],
                query_time=time.perf_counter() - t0,
                cached=False,
            )
        except Exception as exc:
            return AssetProviderResult(
                provider=self.provider_name,
                success=False,
                errors=[str(exc)],
                query_time=time.perf_counter() - t0,
            )

    def normalize(self, raw: Dict[str, Any]) -> AssetDescriptor:
        path = Path(raw.get("path", ""))
        return AssetDescriptor(
            asset_id=f"local_{path.stem}",
            provider=self.provider_name,
            name=path.stem.replace("_", " ").replace("-", " ").title(),
            category=str(raw.get("category", "other")),
            subcategory="",
            tags=list(raw.get("tags", [])),
            keywords=list(raw.get("tags", [])),
            license="unknown",
            formats=[path.suffix.lstrip(".").lower()],
            preview_url="",
            download_url=str(path),
            preview=AssetPreview(
                asset_id=f"local_{path.stem}",
                provider=self.provider_name,
                url="",
                thumbnail_url="",
            ),
            scale="unknown",
            rating=0.0,
            popularity=0,
            style="unknown",
            environment_suitability=[],
            metadata=AssetMetadata(
                file_size_mb=round(path.stat().st_size / 1_048_576, 2) if path.exists() else 0.0,
            ),
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _scan(
        self,
        category: str,
        tags: List[str],
        keywords: List[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        query_terms = {t.lower() for t in tags + keywords}
        root = Path(self._library_path)  # type: ignore[arg-type]
        results = []
        for asset_path in root.rglob("*"):
            if asset_path.suffix.lower() not in _3D_EXTENSIONS:
                continue
            inferred_cat = _infer_category(asset_path)
            cat_match = not category or inferred_cat == category.lower()
            inferred_tags = _infer_tags(asset_path)
            tag_set = {t.lower() for t in inferred_tags}
            tag_match = not query_terms or bool(query_terms & tag_set)
            if cat_match and tag_match:
                results.append({
                    "path":     str(asset_path),
                    "category": inferred_cat,
                    "tags":     inferred_tags,
                })
            if len(results) >= limit:
                break
        return results
