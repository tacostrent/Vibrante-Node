"""
USD Library Provider (Tier 12 — Asset Ecosystem Expansion)
============================================================
USD asset library scanner.
Reads from VIBRANTE_USD_LIBRARY_PATH environment variable.

provider_name = "usd_library"

DESIGN RULES:
  - No network calls.  No authentication.
  - is_available: True when VIBRANTE_USD_LIBRARY_PATH is set and exists.
  - Scans for *.usd, *.usda, *.usdc, *.usdz files.
  - extract_metadata() reads file header, no full USD parse.
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

_USD_EXTENSIONS = {".usd", ".usda", ".usdc", ".usdz"}

_FORMAT_MAP = {
    ".usd":  "usd",
    ".usda": "usda",
    ".usdc": "usdc",
    ".usdz": "usdz",
}

# USD binary magic bytes
_USD_MAGIC = b"PXR-USDC"
_USDA_START = b"#usda"


class UsdLibraryProvider(AssetProvider):
    """
    USD asset library scanner.
    Reads from VIBRANTE_USD_LIBRARY_PATH environment variable.
    """

    def __init__(self, library_path: Optional[str] = None) -> None:
        self._library_path = library_path

    @property
    def _resolved_path(self) -> Optional[str]:
        return self._library_path or os.environ.get("VIBRANTE_USD_LIBRARY_PATH")

    @property
    def provider_name(self) -> str:
        return "usd_library"

    @property
    def supported_categories(self) -> List[str]:
        return [
            "prop", "structure", "character", "vehicle",
            "environment", "material",
        ]

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
                query_params={"note": "VIBRANTE_USD_LIBRARY_PATH not set or directory not found."},
            )
        try:
            all_assets = self.scan_directory(self._resolved_path)
            matched = self._filter_assets(all_assets, category, tags or [], keywords or [], limit)
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
        """Convert a raw dict (from scan_directory) to AssetDescriptor."""
        name = str(raw.get("name", "unknown"))
        asset_id = f"usdlib_{raw.get('asset_id', name.lower().replace(' ', '_'))}"
        category = str(raw.get("category", "prop"))
        formats = list(raw.get("formats", ["usd"]))
        local_path = str(raw.get("local_path", ""))
        preview_url = str(raw.get("preview_url", ""))
        return AssetDescriptor(
            asset_id=asset_id,
            provider=self.provider_name,
            name=name,
            category=category,
            subcategory=str(raw.get("subcategory", "")),
            tags=list(raw.get("tags", [])),
            keywords=list(raw.get("keywords", [])),
            license="unknown",
            formats=formats,
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
            rating=float(raw.get("rating", 3.0)),
            popularity=0,
            style="unknown",
            environment_suitability=list(raw.get("environments", [])),
            metadata=self.extract_metadata(local_path),
        )

    def scan_directory(self, path: str) -> List[AssetDescriptor]:
        """
        Scan a directory for USD files and return AssetDescriptor objects.

        Recursively walks the directory tree.
        Returns empty list when path is unavailable.
        """
        if not path or not os.path.isdir(path):
            return []
        assets: List[AssetDescriptor] = []
        seen: set = set()
        for root, dirs, files in os.walk(path):
            for fname in sorted(files):
                ext = Path(fname).suffix.lower()
                if ext not in _USD_EXTENSIONS:
                    continue
                full_path = str(Path(root) / fname)
                asset_name = Path(fname).stem
                asset_id = f"usdlib_{asset_name.lower().replace(' ', '_')}"
                if asset_id in seen:
                    continue
                seen.add(asset_id)
                # Try to find a preview image alongside
                preview_url = ""
                for pf in files:
                    if pf.lower().endswith(".png") or pf.lower().endswith(".jpg"):
                        preview_url = str(Path(root) / pf)
                        break
                raw = {
                    "asset_id": asset_name.lower().replace(" ", "_"),
                    "name": asset_name,
                    "category": "prop",
                    "formats": [_FORMAT_MAP.get(ext, "usd")],
                    "local_path": full_path,
                    "preview_url": preview_url,
                    "tags": [ext.lstrip(".")],
                }
                assets.append(self.normalize_result(raw))
        return assets

    def extract_metadata(self, path: str) -> AssetMetadata:
        """
        Extract metadata from a USD file header.
        Does not perform full USD parse — reads first bytes only.
        """
        if not path or not os.path.isfile(path):
            return AssetMetadata()
        try:
            size_mb = os.path.getsize(path) / (1024 * 1024)
        except OSError:
            size_mb = 0.0
        return AssetMetadata(
            file_size_mb=size_mb,
            source_url=path,
        )

    def validate_usd(self, path: str) -> Dict[str, Any]:
        """
        Validate a USD file.

        Returns:
            {"valid": bool, "format": str, "size_bytes": int,
             "has_references": bool}
        """
        result: Dict[str, Any] = {
            "valid": False,
            "format": "unknown",
            "size_bytes": 0,
            "has_references": False,
        }
        if not path or not os.path.isfile(path):
            return result
        ext = Path(path).suffix.lower()
        try:
            size = os.path.getsize(path)
            result["size_bytes"] = size
            result["valid"] = True
            if ext == ".usdc":
                result["format"] = "binary"
                try:
                    with open(path, "rb") as f:
                        header = f.read(8)
                    result["valid"] = header[:8] == _USD_MAGIC
                except OSError:
                    pass
            elif ext == ".usda":
                result["format"] = "text"
                try:
                    with open(path, "rb") as f:
                        header = f.read(5)
                    result["valid"] = header == _USDA_START
                except OSError:
                    pass
            elif ext == ".usdz":
                result["format"] = "zip"
            else:
                result["format"] = "usd"
            # Simple reference scan
            if ext in (".usd", ".usda"):
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(4096)
                    result["has_references"] = "@" in content or "references" in content
                except OSError:
                    pass
        except Exception:
            pass
        return result

    def collect_dependencies(self, path: str) -> List[str]:
        """
        Collect dependency references from a USD file.

        Simple string scan — no full USD parse.
        Returns list of referenced file paths.
        """
        deps: List[str] = []
        if not path or not os.path.isfile(path):
            return deps
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            # Look for @...@ asset references
            import re
            for match in re.finditer(r'@([^@]+)@', content):
                ref = match.group(1).strip()
                if ref and ref not in deps:
                    deps.append(ref)
        except Exception:
            pass
        return sorted(deps)

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
