"""
Asset Metadata Provider (Tier 12.7)
======================================
Unified metadata access layer with priority-chain resolution.

Priority order:
  1. Local Asset Manifest  (via AssetManifestReader)
  2. Local Semantic Catalog (via AssetCatalog)
  3. Megascans API          (via MegascansMetadataClient)
  4. Provider Fallback      (returns partial data from input)

Never queries Megascans API if local metadata exists.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .asset_manifest_reader import get_asset_manifest_reader
from .asset_metadata_extractor import get_asset_metadata_extractor, ExtractedMetadata
from .megascans_metadata_client import get_megascans_metadata_client

_SOURCE_MANIFEST  = "local_manifest"
_SOURCE_CATALOG   = "catalog"
_SOURCE_API       = "megascans_api"
_SOURCE_FALLBACK  = "provider_fallback"


@dataclass
class MetadataRecord:
    asset_id:        str = ""
    name:            str = ""
    provider:        str = ""
    category:        str = ""
    tags:            List[str] = field(default_factory=list)
    description:     str = ""
    preview_url:     str = ""
    local_path:      str = ""
    download_url:    str = ""
    formats:         List[str] = field(default_factory=list)
    metadata_source: str = ""
    raw:             Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":        str(self.asset_id),
            "name":            str(self.name),
            "provider":        str(self.provider),
            "category":        str(self.category),
            "tags":            list(self.tags),
            "description":     str(self.description),
            "preview_url":     str(self.preview_url),
            "local_path":      str(self.local_path),
            "download_url":    str(self.download_url),
            "formats":         list(self.formats),
            "metadata_source": str(self.metadata_source),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MetadataRecord":
        d = d if isinstance(d, dict) else {}
        return cls(
            asset_id=str(d.get("asset_id", "")),
            name=str(d.get("name", "")),
            provider=str(d.get("provider", "")),
            category=str(d.get("category", "")),
            tags=list(d.get("tags") or []),
            description=str(d.get("description", "")),
            preview_url=str(d.get("preview_url", "")),
            local_path=str(d.get("local_path", "")),
            download_url=str(d.get("download_url", "")),
            formats=list(d.get("formats") or []),
            metadata_source=str(d.get("metadata_source", "")),
        )

    @classmethod
    def from_extracted(cls, ex: ExtractedMetadata) -> "MetadataRecord":
        return cls(
            asset_id=ex.asset_id,
            name=ex.name,
            provider=ex.provider,
            category=ex.category,
            tags=list(ex.tags),
            description=ex.description,
            preview_url=ex.preview_url,
            local_path=ex.local_path,
            download_url=ex.download_url,
            formats=list(ex.formats),
            metadata_source=ex.metadata_source,
            raw=dict(ex.raw),
        )


class AssetMetadataProvider:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._resolve_count = 0
        self._cache: Dict[str, MetadataRecord] = {}

    def get_metadata(
        self,
        asset_id: str,
        provider: str = "",
        local_path: str = "",
    ) -> MetadataRecord:
        """Resolve metadata using the priority chain. Never raises."""
        try:
            key = f"{provider}:{asset_id}"
            with self._lock:
                cached = self._cache.get(key)
                if cached:
                    return cached
            record = self._resolve(str(asset_id).strip(), str(provider).strip(), str(local_path).strip())
            with self._lock:
                self._cache[key] = record
                self._resolve_count += 1
            return record
        except Exception:
            return MetadataRecord(asset_id=str(asset_id), metadata_source=_SOURCE_FALLBACK)

    def get_asset(self, asset_id: str, provider: str = "", local_path: str = "") -> Dict[str, Any]:
        """Return metadata as a dict."""
        return self.get_metadata(asset_id, provider, local_path).to_dict()

    def resolve_metadata_source(
        self,
        asset_id: str,
        provider: str = "",
        local_path: str = "",
    ) -> str:
        """Return the source string without fetching full metadata."""
        try:
            record = self.get_metadata(asset_id, provider, local_path)
            return record.metadata_source
        except Exception:
            return _SOURCE_FALLBACK

    def refresh_metadata(
        self,
        asset_id: str,
        provider: str = "",
        local_path: str = "",
    ) -> MetadataRecord:
        """Invalidate cache and re-resolve."""
        try:
            key = f"{provider}:{asset_id}"
            with self._lock:
                self._cache.pop(key, None)
            return self.get_metadata(asset_id, provider, local_path)
        except Exception:
            return MetadataRecord(asset_id=str(asset_id), metadata_source=_SOURCE_FALLBACK)

    # ------------------------------------------------------------------
    # Priority chain
    # ------------------------------------------------------------------

    def _resolve(self, asset_id: str, provider: str, local_path: str) -> MetadataRecord:
        extractor = get_asset_metadata_extractor()

        # 1. Local manifest
        if local_path:
            manifest = get_asset_manifest_reader().read_manifest(local_path)
            if manifest and manifest.asset_id:
                ex = extractor.extract_from_manifest(manifest)
                ex.metadata_source = _SOURCE_MANIFEST
                return MetadataRecord.from_extracted(ex)

        # 2. Catalog (import lazily to avoid circular)
        try:
            from .asset_catalog import get_asset_catalog
            entry = get_asset_catalog().get_asset(asset_id)
            if entry:
                return MetadataRecord(
                    asset_id=entry.asset_id,
                    name=entry.name,
                    provider=entry.provider,
                    category=entry.category,
                    tags=list(entry.tags),
                    local_path=entry.local_path,
                    download_url=entry.download_url,
                    preview_url=entry.preview_url,
                    metadata_source=_SOURCE_CATALOG,
                )
        except Exception:
            pass

        # 3. Megascans API
        if provider in ("megascans", "quixel", ""):
            ms_record = get_megascans_metadata_client().get_asset(asset_id)
            if ms_record and ms_record.asset_id:
                ex = extractor.extract_from_megascans(ms_record)
                ex.metadata_source = _SOURCE_API
                return MetadataRecord.from_extracted(ex)

        # 4. Fallback
        return MetadataRecord(
            asset_id=asset_id,
            provider=provider or "unknown",
            metadata_source=_SOURCE_FALLBACK,
        )

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "resolve_count": self._resolve_count,
                "cache_size":    len(self._cache),
            }

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()


_INSTANCE: Optional[AssetMetadataProvider] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_metadata_provider() -> AssetMetadataProvider:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetMetadataProvider()
    return _INSTANCE


def reset_asset_metadata_provider_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
