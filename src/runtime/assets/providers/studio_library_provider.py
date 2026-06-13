"""
Studio Library Provider (Tier 12 — Asset Ecosystem Expansion)
==============================================================
Studio asset repository integration.
Reads from VIBRANTE_STUDIO_LIBRARY_PATH environment variable.

provider_name = "studio_library"

Expected directory structure: {category}/{asset_name}/{files}
Optionally reads studio_manifest.json at library root for rich metadata.

DESIGN RULES:
  - No network calls.  No authentication.
  - is_available: True when VIBRANTE_STUDIO_LIBRARY_PATH is set and exists.
  - All ASSET_CATEGORIES supported.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.runtime.assets.schema import (
    ASSET_CATEGORIES, AssetDescriptor, AssetMetadata, AssetPreview,
    AssetProviderResult,
)
from .base import AssetProvider

_SUPPORTED_FORMATS = {
    ".fbx", ".obj", ".gltf", ".glb",
    ".usd", ".usda", ".usdc", ".usdz",
    ".abc", ".hip", ".bgeo", ".vdb",
    ".blend", ".ma", ".mb",
}


class StudioLibraryProvider(AssetProvider):
    """
    Studio asset repository provider.
    Reads from VIBRANTE_STUDIO_LIBRARY_PATH environment variable.
    Supports optional studio_manifest.json at library root.
    """

    def __init__(self, library_path: Optional[str] = None) -> None:
        self._library_path = library_path
        self._manifest_cache: Optional[Dict[str, Any]] = None

    @property
    def _resolved_path(self) -> Optional[str]:
        return self._library_path or os.environ.get("VIBRANTE_STUDIO_LIBRARY_PATH")

    @property
    def provider_name(self) -> str:
        return "studio_library"

    @property
    def supported_categories(self) -> List[str]:
        return sorted(ASSET_CATEGORIES)

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
                query_params={"note": "VIBRANTE_STUDIO_LIBRARY_PATH not set or directory not found."},
            )
        try:
            all_assets = self.scan_repository()
            matched = self._filter_assets(
                all_assets, category, tags or [], keywords or [], limit
            )
            return AssetProviderResult(
                provider=self.provider_name,
                query_params={
                    "category": category,
                    "tags": tags or [],
                    "keywords": keywords or [],
                    "limit": limit,
                },
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
        """Convert a raw dict to AssetDescriptor."""
        name = str(raw.get("name", "unknown"))
        category = str(raw.get("category", "prop"))
        local_path = str(raw.get("local_path", ""))
        preview_url = str(raw.get("preview_url", ""))
        asset_id = f"stl_{raw.get('asset_id', name.lower().replace(' ', '_'))}"
        return AssetDescriptor(
            asset_id=asset_id,
            provider=self.provider_name,
            name=name,
            category=category,
            subcategory=str(raw.get("subcategory", "")),
            tags=list(raw.get("tags", [])),
            keywords=list(raw.get("keywords", [])),
            license=str(raw.get("license", "studio_proprietary")),
            formats=list(raw.get("formats", [])),
            preview_url=preview_url,
            download_url=local_path,
            preview=AssetPreview(
                asset_id=asset_id,
                provider=self.provider_name,
                url=preview_url,
                thumbnail_url=preview_url,
            ),
            dimensions={},
            scale=str(raw.get("scale", "unknown")),
            rating=float(raw.get("rating", 4.0)),
            popularity=0,
            style=str(raw.get("style", "photorealistic")),
            environment_suitability=list(raw.get("environments", [])),
            metadata=AssetMetadata(
                author=str(raw.get("author", "")),
                source_url=local_path,
                file_size_mb=float(raw.get("file_size_mb", 0.0)),
            ),
        )

    def build_asset_descriptor(
        self,
        path: str,
        category: str,
        name: str,
        manifest_data: Optional[Dict[str, Any]] = None,
    ) -> AssetDescriptor:
        """Build an AssetDescriptor from a filesystem path."""
        raw: Dict[str, Any] = {
            "asset_id": name.lower().replace(" ", "_"),
            "name": name,
            "category": category,
            "local_path": path,
        }
        if manifest_data:
            raw.update(manifest_data)
        # Detect formats from directory
        formats = []
        parent = str(Path(path).parent)
        if os.path.isdir(parent):
            for f in os.listdir(parent):
                ext = Path(f).suffix.lower()
                if ext in _SUPPORTED_FORMATS:
                    fmt = ext.lstrip(".")
                    if fmt not in formats:
                        formats.append(fmt)
        if formats:
            raw["formats"] = formats
        # Find preview
        preview_url = ""
        parent_dir = str(Path(path).parent)
        if os.path.isdir(parent_dir):
            for f in sorted(os.listdir(parent_dir)):
                if f.lower().endswith(".png") or f.lower().endswith(".jpg"):
                    preview_url = str(Path(parent_dir) / f)
                    break
        raw["preview_url"] = preview_url
        # File size
        if os.path.isfile(path):
            try:
                raw["file_size_mb"] = os.path.getsize(path) / (1024 * 1024)
            except OSError:
                pass
        return self.normalize_result(raw)

    def scan_repository(self) -> List[AssetDescriptor]:
        """
        Scan the studio repository with structure: {category}/{asset_name}/{files}.

        Also reads studio_manifest.json at root if present.
        Returns empty list when unavailable.
        """
        if not self.is_available:
            return []
        library_path = Path(self._resolved_path)
        manifest = self._load_manifest(str(library_path))
        assets: List[AssetDescriptor] = []
        seen: set = set()

        # If manifest present, use it as authoritative source
        if manifest and isinstance(manifest.get("assets"), list):
            for asset_data in manifest["assets"]:
                if not isinstance(asset_data, dict):
                    continue
                local_path = str(
                    library_path / asset_data.get("relative_path", "")
                )
                asset_data = dict(asset_data)
                asset_data["local_path"] = local_path
                desc = self.normalize_result(asset_data)
                if desc.asset_id not in seen:
                    seen.add(desc.asset_id)
                    assets.append(desc)
            return sorted(assets, key=lambda a: a.name.lower())

        # Directory-structure scan: {category}/{asset_name}/{files}
        for cat_dir in sorted(library_path.iterdir()):
            if not cat_dir.is_dir():
                continue
            category = cat_dir.name.lower()
            if category not in ASSET_CATEGORIES:
                category = "other"
            for asset_dir in sorted(cat_dir.iterdir()):
                if not asset_dir.is_dir():
                    continue
                asset_name = asset_dir.name
                # Find primary file
                primary_file = ""
                formats = []
                preview_url = ""
                for f in sorted(asset_dir.iterdir()):
                    ext = f.suffix.lower()
                    if ext in _SUPPORTED_FORMATS:
                        if not primary_file:
                            primary_file = str(f)
                        fmt = ext.lstrip(".")
                        if fmt not in formats:
                            formats.append(fmt)
                    elif ext in (".png", ".jpg") and not preview_url:
                        preview_url = str(f)
                if not primary_file:
                    continue
                raw = {
                    "asset_id": f"{category}_{asset_name.lower().replace(' ', '_')}",
                    "name": asset_name,
                    "category": category,
                    "local_path": primary_file,
                    "formats": formats,
                    "preview_url": preview_url,
                }
                desc = self.normalize_result(raw)
                if desc.asset_id not in seen:
                    seen.add(desc.asset_id)
                    assets.append(desc)

        return sorted(assets, key=lambda a: a.name.lower())

    def query_tags(self, tags: List[str]) -> List[AssetDescriptor]:
        """Return all assets that match at least one tag."""
        all_assets = self.scan_repository()
        tag_set = {t.lower() for t in tags}
        return [
            a for a in all_assets
            if tag_set & {t.lower() for t in a.tags + a.keywords}
        ]

    def query_categories(self) -> List[str]:
        """Return all categories found in the repository."""
        all_assets = self.scan_repository()
        cats = sorted({a.category for a in all_assets})
        return cats

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_manifest(self, library_path: str) -> Optional[Dict[str, Any]]:
        """Load studio_manifest.json if present at library root."""
        manifest_path = os.path.join(library_path, "studio_manifest.json")
        if not os.path.isfile(manifest_path):
            return None
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

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
