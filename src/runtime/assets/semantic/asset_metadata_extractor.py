"""
Asset Metadata Extractor (Tier 12.7)
=======================================
Extracts and normalizes structured metadata from multiple source formats:
  - Local manifest files (via AssetManifestReader)
  - Megascans API records (via MegascansMetadataClient)
  - Raw asset dicts from any provider

Produces a canonical ExtractedMetadata record consumed by SemanticAssetEnricher.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExtractedMetadata:
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
    dimensions:      Dict[str, Any] = field(default_factory=dict)
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
            "dimensions":      dict(self.dimensions),
            "metadata_source": str(self.metadata_source),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExtractedMetadata":
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
            dimensions=dict(d.get("dimensions") or {}),
            metadata_source=str(d.get("metadata_source", "")),
        )


class AssetMetadataExtractor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._extract_count = 0

    def extract(self, asset_dict: Dict[str, Any]) -> ExtractedMetadata:
        """Extract and normalize metadata from any asset dict. Never raises."""
        try:
            return self._do_extract(asset_dict if isinstance(asset_dict, dict) else {})
        except Exception:
            return ExtractedMetadata(
                asset_id=str((asset_dict or {}).get("asset_id", "")),
                metadata_source="error",
            )

    def extract_from_manifest(self, manifest_record: Any) -> ExtractedMetadata:
        """Extract from a ManifestRecord object."""
        try:
            d = manifest_record.to_dict() if hasattr(manifest_record, "to_dict") else {}
            d["metadata_source"] = "local_manifest"
            return self._do_extract(d)
        except Exception:
            return ExtractedMetadata(metadata_source="error")

    def extract_from_megascans(self, ms_record: Any) -> ExtractedMetadata:
        """Extract from a MegascansAssetMetadata object."""
        try:
            d = ms_record.to_dict() if hasattr(ms_record, "to_dict") else {}
            d["metadata_source"] = "megascans_api"
            return self._do_extract(d)
        except Exception:
            return ExtractedMetadata(metadata_source="error")

    def _do_extract(self, raw: Dict[str, Any]) -> ExtractedMetadata:
        # Normalize tags
        tags_raw = raw.get("tags") or raw.get("keywords") or raw.get("labels") or []
        if isinstance(tags_raw, str):
            tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]
        tags = list(dict.fromkeys(
            str(t).lower().strip()
            for t in tags_raw
            if str(t).strip()
        ))

        # Normalize formats
        formats_raw = raw.get("formats") or []
        formats = list(dict.fromkeys(
            str(f).lower().lstrip(".")
            for f in formats_raw
            if str(f).strip()
        ))

        with self._lock:
            self._extract_count += 1

        return ExtractedMetadata(
            asset_id=str(
                raw.get("asset_id") or raw.get("id") or ""
            ).strip(),
            name=str(
                raw.get("name") or raw.get("title") or raw.get("asset_id") or ""
            ).strip(),
            provider=str(raw.get("provider", "")).strip(),
            category=str(
                raw.get("category") or raw.get("type") or raw.get("ms_type") or ""
            ).lower().strip(),
            tags=tags,
            description=str(raw.get("description") or "").strip(),
            preview_url=str(raw.get("preview_url") or raw.get("previewUrl") or "").strip(),
            local_path=str(raw.get("local_path") or "").strip(),
            download_url=str(raw.get("download_url") or raw.get("downloadUrl") or "").strip(),
            formats=formats,
            dimensions=dict(raw.get("dimensions") or {}),
            metadata_source=str(raw.get("metadata_source") or "unknown"),
            raw=dict(raw),
        )

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"extract_count": self._extract_count}


_INSTANCE: Optional[AssetMetadataExtractor] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_metadata_extractor() -> AssetMetadataExtractor:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetMetadataExtractor()
    return _INSTANCE


def reset_asset_metadata_extractor_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
