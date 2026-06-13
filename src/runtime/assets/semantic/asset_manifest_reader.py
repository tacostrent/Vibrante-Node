"""
Asset Manifest Reader (Tier 12.7)
====================================
Reads asset metadata directly from local asset folders.

Supported manifest filenames (searched in order):
  asset.json, manifest.json, metadata.json

Returns a normalized metadata structure compatible with the semantic catalog.
No network calls. No DCC calls.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MANIFEST_FILENAMES = ("asset.json", "manifest.json", "metadata.json")
# Megascans stores manifests as {assetId}.json — resolved dynamically in read_manifest


@dataclass
class ManifestRecord:
    asset_id:     str = ""
    name:         str = ""
    provider:     str = ""
    category:     str = ""
    tags:         List[str] = field(default_factory=list)
    description:  str = ""
    preview_url:  str = ""
    local_path:   str = ""
    formats:      List[str] = field(default_factory=list)
    dimensions:   Dict[str, Any] = field(default_factory=dict)
    source_file:  str = ""
    raw:          Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":    str(self.asset_id),
            "name":        str(self.name),
            "provider":    str(self.provider),
            "category":    str(self.category),
            "tags":        list(self.tags),
            "description": str(self.description),
            "preview_url": str(self.preview_url),
            "local_path":  str(self.local_path),
            "formats":     list(self.formats),
            "dimensions":  dict(self.dimensions),
            "source_file": str(self.source_file),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ManifestRecord":
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
            formats=list(d.get("formats") or []),
            dimensions=dict(d.get("dimensions") or {}),
            source_file=str(d.get("source_file", "")),
        )


class AssetManifestReader:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._read_count = 0

    def read_manifest(self, folder_path: str) -> Optional[ManifestRecord]:
        """Read the first supported manifest file found in folder_path.

        Returns None if no manifest found or folder doesn't exist.
        Never raises.
        """
        try:
            folder_path = str(folder_path).strip()
            if not folder_path or not os.path.isdir(folder_path):
                return None
            # Try fixed names first, then {folder_basename}.json (Megascans convention)
            folder_basename = os.path.basename(folder_path.rstrip("/\\"))
            # Strip trailing asset-id suffix: "Historical_Wild West_uknjbb2bw" → "uknjbb2bw"
            megascans_id = folder_basename.split("_")[-1] if "_" in folder_basename else folder_basename
            dynamic_names = []
            if megascans_id:
                dynamic_names.append(f"{megascans_id}.json")
            if folder_basename != megascans_id:
                dynamic_names.append(f"{folder_basename}.json")
            for fname in list(_MANIFEST_FILENAMES) + dynamic_names:
                fpath = os.path.join(folder_path, fname)
                if os.path.isfile(fpath):
                    record = self._parse_manifest_file(fpath, folder_path)
                    if record:
                        with self._lock:
                            self._read_count += 1
                        return record
            return None
        except Exception:
            return None

    def _parse_manifest_file(self, fpath: str, folder_path: str) -> Optional[ManifestRecord]:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None

            record = ManifestRecord(source_file=fpath, raw=dict(data))
            record.local_path = folder_path

            # Normalize common manifest field names
            record.asset_id = str(
                data.get("id") or data.get("asset_id") or data.get("assetId") or
                os.path.basename(folder_path)
            ).strip()
            record.name = str(
                data.get("name") or data.get("title") or data.get("displayName") or
                record.asset_id
            ).strip()
            record.provider = str(data.get("provider", "local")).strip()
            record.category = str(
                data.get("category") or data.get("type") or data.get("assetType") or ""
            ).lower().strip()
            record.description = str(data.get("description") or data.get("overview") or "").strip()
            record.preview_url = str(data.get("previewUrl") or data.get("preview") or "").strip()

            record.tags = self.extract_tags(data)
            record.formats = self._extract_formats(data, folder_path)
            record.dimensions = self.extract_dimensions(data)

            return record
        except Exception:
            return None

    def extract_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract normalized metadata from a raw manifest dict."""
        if not isinstance(data, dict):
            return {}
        return {
            "asset_id":   str(data.get("id") or data.get("asset_id") or ""),
            "name":       str(data.get("name") or data.get("title") or ""),
            "category":   str(data.get("category") or data.get("type") or "").lower(),
            "tags":       self.extract_tags(data),
            "description": str(data.get("description") or ""),
        }

    def extract_tags(self, data: Dict[str, Any]) -> List[str]:
        """Extract and normalize tags from a manifest dict."""
        if not isinstance(data, dict):
            return []
        raw_tags = data.get("tags") or data.get("keywords") or data.get("labels") or []
        if isinstance(raw_tags, str):
            raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        return [str(t).lower().strip() for t in raw_tags if str(t).strip()]

    def extract_categories(self, data: Dict[str, Any]) -> List[str]:
        """Extract category breadcrumb from a manifest dict."""
        if not isinstance(data, dict):
            return []
        cats = []
        for field_name in ("category", "type", "assetType", "categories"):
            val = data.get(field_name)
            if isinstance(val, str) and val.strip():
                cats.append(val.strip().lower())
            elif isinstance(val, list):
                cats.extend(str(c).lower().strip() for c in val if str(c).strip())
        return list(dict.fromkeys(cats))

    def extract_preview(self, data: Dict[str, Any]) -> str:
        """Extract preview URL from a manifest dict."""
        if not isinstance(data, dict):
            return ""
        for field_name in ("previewUrl", "preview", "thumbnail", "image"):
            val = data.get(field_name)
            if val and isinstance(val, str):
                return str(val).strip()
        return ""

    def extract_dimensions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract geometry/texture dimensions from a manifest dict."""
        if not isinstance(data, dict):
            return {}
        dims: Dict[str, Any] = {}
        for key in ("dimensions", "size", "resolution", "texelDensity"):
            val = data.get(key)
            if val:
                dims[key] = val
        return dims

    def _extract_formats(self, data: Dict[str, Any], folder_path: str) -> List[str]:
        """Detect file formats from manifest and folder contents."""
        formats: List[str] = []
        # From manifest fields
        for key in ("formats", "fileFormats", "extensions"):
            val = data.get(key)
            if isinstance(val, list):
                formats.extend(str(f).lower().lstrip(".") for f in val if f)
        # From folder files
        try:
            for fname in os.listdir(folder_path):
                ext = os.path.splitext(fname)[1].lower().lstrip(".")
                if ext and ext not in formats:
                    formats.append(ext)
        except Exception:
            pass
        return list(dict.fromkeys(formats))

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {"read_count": self._read_count}


_INSTANCE: Optional[AssetManifestReader] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_manifest_reader() -> AssetManifestReader:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetManifestReader()
    return _INSTANCE


def reset_asset_manifest_reader_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
