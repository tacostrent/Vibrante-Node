"""
Quixel Provider (Tier 12 — Asset Ecosystem Expansion)
=======================================================
Local Megascans library scanner.
Reads from VIBRANTE_MEGASCANS_PATH environment variable.
NO cloud dependency — local-first, offline-capable.

provider_name = "quixel"

DESIGN RULES:
  - No network calls.  No authentication.
  - is_available: True only when VIBRANTE_MEGASCANS_PATH is set and exists.
  - Scans directory for *.uasset, *.png, metadata.json files.
  - Returns empty AssetProviderResult with a warning note when unavailable.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import (
    AssetDescriptor, AssetMetadata, AssetPreview, AssetProviderResult,
)
from .base import AssetProvider

# Category map: Megascans naming → canonical ASSET_CATEGORIES
_QUIXEL_CATEGORY_MAP: Dict[str, str] = {
    "surfaces":   "material",
    "props":      "prop",
    "atlases":    "material",
    "3d plants":  "vegetation",
    "decals":     "material",
    "brush":      "terrain",
    "3d asset":   "prop",
    "character":  "character",
    "vehicle":    "vehicle",
    "hdri":       "hdri",
    "environment": "environment",
}


class QuixelProvider(AssetProvider):
    """
    Local Megascans asset library scanner.
    Reads from VIBRANTE_MEGASCANS_PATH environment variable.
    """

    def __init__(self, library_path: Optional[str] = None) -> None:
        self._library_path = library_path

    @property
    def _resolved_path(self) -> Optional[str]:
        return self._library_path or os.environ.get("VIBRANTE_MEGASCANS_PATH")

    @property
    def provider_name(self) -> str:
        return "quixel"

    @property
    def supported_categories(self) -> List[str]:
        return ["material", "surface", "prop", "vegetation", "terrain", "hdri"]

    @property
    def is_available(self) -> bool:
        path = self._resolved_path
        return bool(path and os.path.isdir(path))

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
                success=True,
                normalized_assets=[],
                errors=[],
                query_time=time.perf_counter() - t0,
                query_params={"note": "VIBRANTE_MEGASCANS_PATH not set or directory not found."},
            )
        try:
            all_assets = self.scan_library()
            matched = self._filter_assets(all_assets, category, tags or [], keywords or [], limit)
            return AssetProviderResult(
                provider=self.provider_name,
                query_params={
                    "category": category,
                    "tags": tags or [],
                    "keywords": keywords or [],
                    "limit": limit,
                },
                raw_data=[],  # Internal objects, not raw dicts
                normalized_assets=matched,
                success=True,
                errors=[],
                query_time=time.perf_counter() - t0,
            )
        except Exception as exc:
            return AssetProviderResult(
                provider=self.provider_name,
                success=False,
                errors=[str(exc)],
                query_time=time.perf_counter() - t0,
            )

    def normalize(self, raw: Dict[str, Any]) -> AssetDescriptor:
        return self.normalize_result(raw)

    def normalize_result(self, raw: Dict[str, Any]) -> AssetDescriptor:
        """Convert a raw Megascans-style dict to AssetDescriptor."""
        cat_raw = str(raw.get("category", "prop")).lower()
        category = _QUIXEL_CATEGORY_MAP.get(cat_raw, "prop")
        tags = [t.lower() for t in raw.get("tags", [])]
        name = str(raw.get("name", raw.get("id", "unknown")))
        asset_id = f"qx_{raw.get('id', name.replace(' ', '_').lower())}"
        preview_url = str(raw.get("preview_url", ""))
        return AssetDescriptor(
            asset_id=asset_id,
            provider=self.provider_name,
            name=name,
            category=category,
            subcategory=cat_raw,
            tags=tags,
            keywords=tags,
            license="commercial",  # Megascans requires subscription
            formats=list(raw.get("formats", ["uasset"])),
            preview_url=preview_url,
            download_url=str(raw.get("local_path", "")),
            preview=AssetPreview(
                asset_id=asset_id,
                provider=self.provider_name,
                url=preview_url,
                thumbnail_url=preview_url,
            ),
            dimensions={},
            scale=str(raw.get("scale", "unknown")),
            rating=float(raw.get("rating", 3.5)),
            popularity=int(raw.get("popularity", 0)),
            style="photorealistic",
            environment_suitability=list(raw.get("environments", [])),
            metadata=self.build_metadata(
                str(raw.get("local_path", "")), raw
            ),
        )

    def scan_library(self) -> List[AssetDescriptor]:
        """
        Scan the Megascans library directory and return all found assets.

        Looks for metadata.json files and *.uasset files.
        Returns empty list when library path is unavailable.
        """
        if not self.is_available:
            return []
        library_path = Path(self._resolved_path)
        assets: List[AssetDescriptor] = []
        seen_ids: set = set()

        for root, dirs, files in os.walk(str(library_path)):
            # Look for metadata.json
            if "metadata.json" in files:
                meta_path = Path(root) / "metadata.json"
                try:
                    with open(str(meta_path), "r", encoding="utf-8") as f:
                        raw_meta = json.load(f)
                    if isinstance(raw_meta, dict):
                        raw_meta["local_path"] = root
                        # Find preview image
                        for fname in files:
                            if fname.lower().endswith(".png") and "preview" in fname.lower():
                                raw_meta["preview_url"] = str(Path(root) / fname)
                                break
                        asset = self.normalize_result(raw_meta)
                        if asset.asset_id not in seen_ids:
                            seen_ids.add(asset.asset_id)
                            assets.append(asset)
                except Exception:
                    pass
            else:
                # Fallback: look for .uasset files
                for fname in files:
                    if fname.lower().endswith(".uasset"):
                        asset_name = Path(fname).stem
                        asset_id = f"qx_{asset_name.lower()}"
                        if asset_id not in seen_ids:
                            seen_ids.add(asset_id)
                            # Find preview
                            preview_url = ""
                            for pf in files:
                                if pf.lower().endswith(".png"):
                                    preview_url = str(Path(root) / pf)
                                    break
                            assets.append(AssetDescriptor(
                                asset_id=asset_id,
                                provider=self.provider_name,
                                name=asset_name,
                                category="prop",
                                tags=[],
                                keywords=[],
                                license="commercial",
                                formats=["uasset"],
                                preview_url=preview_url,
                                download_url=str(Path(root) / fname),
                                scale="unknown",
                                rating=3.5,
                                metadata=AssetMetadata(),
                            ))

        return sorted(assets, key=lambda a: a.name.lower())

    def build_metadata(self, path: str, raw_meta: Dict[str, Any]) -> AssetMetadata:
        """Build AssetMetadata from a path and raw metadata dict."""
        size_mb = 0.0
        if path and os.path.isfile(path):
            try:
                size_mb = os.path.getsize(path) / (1024 * 1024)
            except OSError:
                pass
        return AssetMetadata(
            face_count=int(raw_meta.get("face_count", 0)),
            vertex_count=int(raw_meta.get("vertex_count", 0)),
            is_animated=bool(raw_meta.get("is_animated", False)),
            is_rigged=bool(raw_meta.get("is_rigged", False)),
            texture_count=int(raw_meta.get("texture_count", 0)),
            file_size_mb=size_mb,
            author=str(raw_meta.get("author", "Quixel")),
            source_url=str(raw_meta.get("source_url", "https://quixel.com/megascans")),
        )

    def validate_asset(self, asset: AssetDescriptor) -> Dict[str, Any]:
        """Provider-level validation for Megascans assets."""
        errors: List[str] = []
        warnings: List[str] = []
        if not asset.name:
            errors.append("Asset name is empty.")
        if "uasset" in asset.formats and asset.download_url:
            if not os.path.exists(asset.download_url):
                warnings.append(f"Local asset file not found: {asset.download_url}")
        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _filter_assets(
        self,
        assets: List[AssetDescriptor],
        category: str,
        tags: List[str],
        keywords: List[str],
        limit: int,
    ) -> List[AssetDescriptor]:
        query_terms = {t.lower() for t in tags + keywords}
        results = []
        for asset in assets:
            cat_match = not category or asset.category == category.lower()
            if query_terms:
                asset_terms = {t.lower() for t in asset.tags + asset.keywords}
                asset_terms.add(asset.name.lower())
                tag_match = bool(query_terms & asset_terms)
            else:
                tag_match = True
            if cat_match and tag_match:
                results.append(asset)
            if len(results) >= limit:
                break
        return results
