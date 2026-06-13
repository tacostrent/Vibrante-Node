"""
Fab Library Scanner (Tier 12.5)
================================
Scans local Fab asset directories, builds asset descriptor dicts from manifests.

Reads VIBRANTE_FAB_LIBRARY environment variable for library path.
Never makes network calls. Never requires authentication.
Vibrante only discovers and indexes locally acquired assets — downloading
is performed externally through the official Fab desktop application.

Deterministic, thread-safe, no Houdini dependency.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

ENV_FAB_LIBRARY = "VIBRANTE_FAB_LIBRARY"

_FAB_METADATA_FILENAMES = frozenset({
    "manifest.json",
    "asset.json",
    "metadata.json",
    "fab_asset.json",
    "product.json",
    "info.json",
})

_FAB_CATEGORY_MAP: Dict[str, str] = {
    "architecture":  "architectural",
    "architectural": "architectural",
    "vehicles":      "vehicle",
    "vehicle":       "vehicle",
    "characters":    "character",
    "character":     "character",
    "props":         "prop",
    "prop":          "prop",
    "environments":  "environment",
    "environment":   "environment",
    "materials":     "material",
    "material":      "material",
    "textures":      "material",
    "texture":       "material",
    "vfx":           "effects",
    "effects":       "effects",
    "hdri":          "hdri",
    "animations":    "animation",
    "animation":     "animation",
    "vegetation":    "vegetation",
    "terrain":       "terrain",
    "furniture":     "furniture",
    "machinery":     "machinery",
    "weapon":        "weapon",
    "robot":         "robot",
    "electronic":    "electronic",
}

_EXT_TO_FORMAT: Dict[str, str] = {
    ".fbx": "fbx", ".obj": "obj",  ".gltf": "gltf", ".glb": "glb",
    ".usd": "usd", ".usda": "usda", ".usdc": "usdc", ".usdz": "usdz",
    ".abc": "abc", ".blend": "blend", ".ma": "ma",   ".mb": "mb",
    ".hip": "hip", ".bgeo": "bgeo",
}

_MAX_SCAN_DEPTH = 4


@dataclass
class FabAssetRecord:
    record_id:     str = field(default_factory=lambda: f"fab_{uuid.uuid4().hex[:8]}")
    asset_id:      str = ""
    name:          str = ""
    category:      str = "prop"
    tags:          List[str] = field(default_factory=list)
    formats:       List[str] = field(default_factory=list)
    local_path:    str = ""
    manifest_path: str = ""
    provider:      str = "fab"
    license:       str = "royalty_free"
    metadata:      Dict[str, Any] = field(default_factory=dict)
    discovered_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id":     str(self.record_id),
            "asset_id":      str(self.asset_id),
            "name":          str(self.name),
            "category":      str(self.category),
            "tags":          list(self.tags),
            "formats":       list(self.formats),
            "local_path":    str(self.local_path),
            "manifest_path": str(self.manifest_path),
            "provider":      str(self.provider),
            "license":       str(self.license),
            "metadata":      dict(self.metadata),
            "discovered_at": float(self.discovered_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FabAssetRecord":
        d = d if isinstance(d, dict) else {}
        return cls(
            record_id=str(d.get("record_id") or f"fab_{uuid.uuid4().hex[:8]}"),
            asset_id=str(d.get("asset_id", "")),
            name=str(d.get("name", "")),
            category=str(d.get("category", "prop")),
            tags=list(d.get("tags") or []),
            formats=list(d.get("formats") or []),
            local_path=str(d.get("local_path", "")),
            manifest_path=str(d.get("manifest_path", "")),
            provider=str(d.get("provider", "fab")),
            license=str(d.get("license", "royalty_free")),
            metadata=dict(d.get("metadata") or {}),
            discovered_at=float(d.get("discovered_at") or time.time()),
        )


@dataclass
class FabScanResult:
    ok:            bool = True
    library_path:  str = ""
    assets_found:  List[FabAssetRecord] = field(default_factory=list)
    total_scanned: int = 0
    errors:        List[str] = field(default_factory=list)
    warnings:      List[str] = field(default_factory=list)
    scanned_at:    float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":            bool(self.ok),
            "library_path":  str(self.library_path),
            "assets_found":  [a.to_dict() for a in self.assets_found],
            "total_scanned": int(self.total_scanned),
            "errors":        list(self.errors),
            "warnings":      list(self.warnings),
            "scanned_at":    float(self.scanned_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FabScanResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", True)),
            library_path=str(d.get("library_path", "")),
            assets_found=[
                FabAssetRecord.from_dict(a)
                for a in (d.get("assets_found") or [])
                if isinstance(a, dict)
            ],
            total_scanned=int(d.get("total_scanned") or 0),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            scanned_at=float(d.get("scanned_at") or time.time()),
        )


def _detect_formats(asset_dir: str) -> List[str]:
    formats: List[str] = []
    try:
        for fname in os.listdir(asset_dir):
            ext = os.path.splitext(fname)[1].lower()
            fmt = _EXT_TO_FORMAT.get(ext)
            if fmt and fmt not in formats:
                formats.append(fmt)
    except Exception:
        pass
    return sorted(formats)


def _parse_manifest(manifest_path: str, asset_dir: str) -> Optional[FabAssetRecord]:
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    name = str(
        data.get("name") or data.get("title") or data.get("display_name")
        or data.get("product_name") or ""
    ).strip()
    if not name:
        return None

    raw_id = data.get("id") or data.get("asset_id") or data.get("product_id") or ""
    asset_id = str(raw_id).strip() or f"fab_{uuid.uuid4().hex[:8]}"

    raw_cat = str(
        data.get("category") or data.get("asset_type") or data.get("type") or ""
    ).lower().strip()
    category = _FAB_CATEGORY_MAP.get(raw_cat, "prop")

    raw_tags = data.get("tags") or data.get("keywords") or []
    tags = sorted({str(t).lower() for t in raw_tags if isinstance(t, (str, int))})

    formats = _detect_formats(asset_dir)
    # Also pick up declared formats from manifest
    for fmt_entry in (data.get("formats") or []):
        if isinstance(fmt_entry, str) and fmt_entry.lower() in _EXT_TO_FORMAT.values():
            if fmt_entry.lower() not in formats:
                formats.append(fmt_entry.lower())

    raw_license = str(
        data.get("license") or data.get("license_type") or "royalty_free"
    ).lower()

    # Store non-standard manifest keys in metadata
    reserved = {"name", "title", "display_name", "product_name", "id", "asset_id",
                "product_id", "category", "asset_type", "type", "tags", "keywords",
                "formats", "license", "license_type"}
    extra_meta = {k: v for k, v in data.items() if k not in reserved}

    return FabAssetRecord(
        asset_id=asset_id,
        name=name,
        category=category,
        tags=tags,
        formats=formats,
        local_path=asset_dir,
        manifest_path=manifest_path,
        provider="fab",
        license=raw_license,
        metadata=extra_meta,
    )


class FabLibraryScanner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._scan_count = 0
        self._last_result: Optional[FabScanResult] = None

    def _library_path(self) -> str:
        from src.utils.vibrante_config import apply_vibrante_config
        apply_vibrante_config(force=True)
        return os.environ.get(ENV_FAB_LIBRARY, "").strip()

    def scan_library(self, library_path: str = "") -> FabScanResult:
        """Scan the Fab local library. Never raises."""
        try:
            return self._do_scan(library_path.strip() or self._library_path())
        except Exception as exc:
            return FabScanResult(
                ok=False,
                library_path=library_path,
                errors=[f"Fab scan failed: {exc}"],
            )

    def _do_scan(self, path: str) -> FabScanResult:
        if not path:
            return FabScanResult(
                ok=True,
                warnings=[f"{ENV_FAB_LIBRARY} not set — no Fab library to scan."],
            )
        if not os.path.isdir(path):
            return FabScanResult(
                ok=False,
                library_path=path,
                errors=[f"Fab library path does not exist: {path!r}"],
            )

        assets: List[FabAssetRecord] = []
        warnings: List[str] = []
        dirs_scanned = 0
        seen_ids: set = set()

        root_path = Path(path)
        for root, dirs, files in os.walk(path):
            dirs.sort()  # deterministic traversal
            current_path = Path(root)
            depth = len(current_path.relative_to(root_path).parts)
            if depth > _MAX_SCAN_DEPTH:
                dirs.clear()
                continue
            dirs_scanned += 1

            manifest = None
            for fname in files:
                if fname.lower() in _FAB_METADATA_FILENAMES:
                    manifest = os.path.join(root, fname)
                    break
            # Fallback: any *.json at depth ≤ 2
            if manifest is None and depth <= 2:
                for fname in sorted(files):
                    if fname.lower().endswith(".json"):
                        manifest = os.path.join(root, fname)
                        break

            if manifest:
                try:
                    record = _parse_manifest(manifest, root)
                    if record and record.asset_id not in seen_ids:
                        seen_ids.add(record.asset_id)
                        assets.append(record)
                except Exception as exc:
                    warnings.append(f"Skipped {manifest}: {exc}")

        with self._lock:
            self._scan_count += 1
            result = FabScanResult(
                ok=True,
                library_path=path,
                assets_found=assets,
                total_scanned=dirs_scanned,
                warnings=warnings,
            )
            self._last_result = result
        return result

    def index_assets(self, library_path: str = "") -> Dict[str, FabAssetRecord]:
        """Return {asset_id: FabAssetRecord} index."""
        result = self.scan_library(library_path)
        return {a.asset_id: a for a in result.assets_found}

    def extract_metadata(self, manifest_path: str) -> Optional[FabAssetRecord]:
        """Parse a single manifest file. Returns None on failure."""
        try:
            asset_dir = os.path.dirname(manifest_path)
            return _parse_manifest(manifest_path, asset_dir)
        except Exception:
            return None

    def build_asset_descriptor(self, record: FabAssetRecord) -> Dict[str, Any]:
        """Convert FabAssetRecord to an AssetDescriptor-compatible dict."""
        return {
            "asset_id":               record.asset_id,
            "provider":               "fab",
            "name":                   record.name,
            "category":               record.category,
            "tags":                   list(record.tags),
            "keywords":               list(record.tags),
            "formats":                list(record.formats),
            "license":                record.license,
            "download_url":           "",
            "preview_url":            "",
            "style":                  "photorealistic",
            "scale":                  "unknown",
            "environment_suitability": [],
            "metadata": {
                "extra": {
                    "local_path":    record.local_path,
                    "manifest_path": record.manifest_path,
                    "source":        "fab_local_library",
                    **record.metadata,
                }
            },
        }

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            last = self._last_result
        return {
            "scan_count":    self._scan_count,
            "last_scan_ok":  last.ok if last else None,
            "assets_in_last_scan": len(last.assets_found) if last else 0,
            "library_path":  self._library_path(),
        }


_INSTANCE: Optional[FabLibraryScanner] = None
_INSTANCE_LOCK = threading.Lock()


def get_fab_library_scanner() -> FabLibraryScanner:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = FabLibraryScanner()
    return _INSTANCE


def reset_fab_library_scanner_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
