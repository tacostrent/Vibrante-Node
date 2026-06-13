"""
Megascans Scanner (Tier 12.5)
==============================
Scans local Megascans / Fab Bridge library directories, extracting asset
metadata without any network calls or authentication.

Reads VIBRANTE_MEGASCANS_LIBRARY environment variable for library path.
The actual downloading of Megascans/Fab assets is performed by the user
through the official Fab desktop application. Vibrante only discovers,
indexes, and consumes what is already present on disk.

Supported asset types:
  3d          — 3D props and objects
  3dplant     — Vegetation / 3D plants
  surface     — PBR surface materials
  decal       — Decal materials
  imperfection — Imperfection overlays
  atlas       — Atlas/trim sheet materials
  brush       — VDM/alpha brushes

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

ENV_MEGASCANS_LIBRARY = "VIBRANTE_MEGASCANS_LIBRARY"

# Megascans/Bridge subdirectory names → Vibrante category
_MS_TYPE_TO_CATEGORY: Dict[str, str] = {
    "3d":           "prop",
    "3dplant":      "vegetation",
    "surface":      "material",
    "decal":        "material",
    "imperfection": "material",
    "atlas":        "material",
    "brush":        "material",
    "hdri":         "hdri",
}

# Megascans resolution suffixes (e.g. "4K", "2K", "1K")
_MEGASCANS_RESOLUTIONS = ("8K", "4K", "2K", "1K", "512")

_EXT_TO_FORMAT: Dict[str, str] = {
    ".fbx":  "fbx",  ".obj":  "obj",  ".gltf": "gltf", ".glb": "glb",
    ".usd":  "usd",  ".usda": "usda", ".usdc": "usdc", ".usdz": "usdz",
    ".abc":  "abc",  ".exr":  "exr",  ".hdr":  "hdr",
}

_MS_MAP_TYPES = frozenset({
    "albedo", "diffuse", "roughness", "gloss", "metalness", "normal",
    "displacement", "cavity", "ao", "opacity", "translucency", "fuzz",
    "emissive", "bump", "specular", "curvature",
})

_MAX_SCAN_DEPTH = 3


@dataclass
class MegascansAssetRecord:
    record_id:      str = field(default_factory=lambda: f"ms_{uuid.uuid4().hex[:8]}")
    asset_id:       str = ""
    name:           str = ""
    ms_type:        str = "3d"
    category:       str = "prop"
    tags:           List[str] = field(default_factory=list)
    formats:        List[str] = field(default_factory=list)
    map_types:      List[str] = field(default_factory=list)
    resolution:     str = ""
    local_path:     str = ""
    manifest_path:  str = ""
    provider:       str = "megascans"
    license:        str = "royalty_free"
    lod_count:      int = 0
    metadata:       Dict[str, Any] = field(default_factory=dict)
    discovered_at:  float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id":     str(self.record_id),
            "asset_id":      str(self.asset_id),
            "name":          str(self.name),
            "ms_type":       str(self.ms_type),
            "category":      str(self.category),
            "tags":          list(self.tags),
            "formats":       list(self.formats),
            "map_types":     list(self.map_types),
            "resolution":    str(self.resolution),
            "local_path":    str(self.local_path),
            "manifest_path": str(self.manifest_path),
            "provider":      str(self.provider),
            "license":       str(self.license),
            "lod_count":     int(self.lod_count),
            "metadata":      dict(self.metadata),
            "discovered_at": float(self.discovered_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MegascansAssetRecord":
        d = d if isinstance(d, dict) else {}
        return cls(
            record_id=str(d.get("record_id") or f"ms_{uuid.uuid4().hex[:8]}"),
            asset_id=str(d.get("asset_id", "")),
            name=str(d.get("name", "")),
            ms_type=str(d.get("ms_type", "3d")),
            category=str(d.get("category", "prop")),
            tags=list(d.get("tags") or []),
            formats=list(d.get("formats") or []),
            map_types=list(d.get("map_types") or []),
            resolution=str(d.get("resolution", "")),
            local_path=str(d.get("local_path", "")),
            manifest_path=str(d.get("manifest_path", "")),
            provider=str(d.get("provider", "megascans")),
            license=str(d.get("license", "royalty_free")),
            lod_count=int(d.get("lod_count") or 0),
            metadata=dict(d.get("metadata") or {}),
            discovered_at=float(d.get("discovered_at") or time.time()),
        )


@dataclass
class MegascansScanResult:
    ok:            bool = True
    library_path:  str = ""
    assets_found:  List[MegascansAssetRecord] = field(default_factory=list)
    by_type:       Dict[str, int] = field(default_factory=dict)
    total_scanned: int = 0
    errors:        List[str] = field(default_factory=list)
    warnings:      List[str] = field(default_factory=list)
    scanned_at:    float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":            bool(self.ok),
            "library_path":  str(self.library_path),
            "assets_found":  [a.to_dict() for a in self.assets_found],
            "by_type":       dict(self.by_type),
            "total_scanned": int(self.total_scanned),
            "errors":        list(self.errors),
            "warnings":      list(self.warnings),
            "scanned_at":    float(self.scanned_at),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MegascansScanResult":
        d = d if isinstance(d, dict) else {}
        return cls(
            ok=bool(d.get("ok", True)),
            library_path=str(d.get("library_path", "")),
            assets_found=[
                MegascansAssetRecord.from_dict(a)
                for a in (d.get("assets_found") or [])
                if isinstance(a, dict)
            ],
            by_type=dict(d.get("by_type") or {}),
            total_scanned=int(d.get("total_scanned") or 0),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            scanned_at=float(d.get("scanned_at") or time.time()),
        )


def _detect_map_types(asset_dir: str) -> List[str]:
    """Detect Megascans texture map types from filenames."""
    detected: set = set()
    try:
        for fname in os.listdir(asset_dir):
            lower = fname.lower()
            for mt in _MS_MAP_TYPES:
                if f"_{mt}" in lower or f"_{mt}." in lower:
                    detected.add(mt)
                    break
    except Exception:
        pass
    return sorted(detected)


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


def _detect_resolution(asset_dir: str) -> str:
    try:
        for fname in os.listdir(asset_dir):
            upper = fname.upper()
            for res in _MEGASCANS_RESOLUTIONS:
                if f"_{res}" in upper or f"_{res}." in upper:
                    return res
    except Exception:
        pass
    return ""


def _count_lods(asset_dir: str) -> int:
    count = 0
    try:
        for fname in os.listdir(asset_dir):
            lower = fname.lower()
            if "lod" in lower and os.path.splitext(fname)[1].lower() in _EXT_TO_FORMAT:
                count += 1
    except Exception:
        pass
    return count


def _parse_ms_manifest(manifest_path: str, asset_dir: str, ms_type: str) -> Optional[MegascansAssetRecord]:
    """Parse a Megascans JSON manifest. Returns None if not valid."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    # Megascans manifests always have an "id" and "name" field
    asset_id = str(data.get("id") or data.get("asset_id") or "").strip()
    name = str(data.get("name") or data.get("title") or "").strip()
    if not name:
        return None
    if not asset_id:
        asset_id = f"ms_{uuid.uuid4().hex[:8]}"

    # Infer category from ms_type + manifest "type" field
    raw_type = str(data.get("type") or ms_type).lower().strip()
    category = _MS_TYPE_TO_CATEGORY.get(raw_type, "prop")

    # Tags: from "tags", "semanticTags", "categories"
    raw_tags = []
    for key in ("tags", "semanticTags", "semantic_tags", "categories"):
        val = data.get(key)
        if isinstance(val, list):
            raw_tags.extend(val)
        elif isinstance(val, str):
            raw_tags.append(val)
    tags = sorted({str(t).lower() for t in raw_tags if isinstance(t, (str, int))})

    # Formats: from files in directory
    formats = _detect_formats(asset_dir)

    # Resolution
    resolution = _detect_resolution(asset_dir)

    # Map types: from "maps" key in manifest + from files
    map_types = set(_detect_map_types(asset_dir))
    for m in (data.get("maps") or []):
        if isinstance(m, dict):
            mt = str(m.get("type") or m.get("name") or "").lower()
            if mt in _MS_MAP_TYPES:
                map_types.add(mt)
    map_types_list = sorted(map_types)

    # LOD count
    lod_count = max(
        _count_lods(asset_dir),
        len([m for m in (data.get("geometry") or []) if isinstance(m, dict) and "lod" in str(m.get("lod", "")).lower()]),
    )

    reserved = {"id", "asset_id", "name", "title", "type", "tags", "semanticTags",
                "categories", "maps", "geometry", "semantic_tags"}
    extra = {k: v for k, v in data.items() if k not in reserved}

    return MegascansAssetRecord(
        asset_id=asset_id,
        name=name,
        ms_type=raw_type,
        category=category,
        tags=tags,
        formats=formats,
        map_types=map_types_list,
        resolution=resolution,
        local_path=asset_dir,
        manifest_path=manifest_path,
        provider="megascans",
        license="royalty_free",
        lod_count=lod_count,
        metadata=extra,
    )


class MegascansScanner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._scan_count = 0
        self._last_result: Optional[MegascansScanResult] = None

    def _library_path(self) -> str:
        from src.utils.vibrante_config import apply_vibrante_config
        apply_vibrante_config(force=True)
        return os.environ.get(ENV_MEGASCANS_LIBRARY, "").strip()

    def scan_megascans(self, library_path: str = "") -> MegascansScanResult:
        """Scan the local Megascans library. Never raises."""
        try:
            return self._do_scan(library_path.strip() or self._library_path())
        except Exception as exc:
            return MegascansScanResult(
                ok=False,
                library_path=library_path,
                errors=[f"Megascans scan failed: {exc}"],
            )

    def _do_scan(self, path: str) -> MegascansScanResult:
        if not path:
            return MegascansScanResult(
                ok=True,
                warnings=[f"{ENV_MEGASCANS_LIBRARY} not set — no Megascans library to scan."],
            )
        if not os.path.isdir(path):
            return MegascansScanResult(
                ok=False,
                library_path=path,
                errors=[f"Megascans library path does not exist: {path!r}"],
            )

        assets: List[MegascansAssetRecord] = []
        warnings: List[str] = []
        dirs_scanned = 0
        by_type: Dict[str, int] = {}
        seen_ids: set = set()
        root_path = Path(path)

        # Walk: top-level dirs are ms_types (3d, surface, decal, …)
        for type_dir_name in sorted(os.listdir(path)):
            type_dir = os.path.join(path, type_dir_name)
            if not os.path.isdir(type_dir):
                continue
            ms_type = type_dir_name.lower()

            # Each subdirectory inside the type dir is one asset
            try:
                asset_dirs = sorted(os.listdir(type_dir))
            except Exception:
                continue

            for asset_dir_name in asset_dirs:
                asset_dir = os.path.join(type_dir, asset_dir_name)
                if not os.path.isdir(asset_dir):
                    continue
                dirs_scanned += 1

                # Find manifest: prefer ms-named JSON, then any JSON
                manifest = None
                try:
                    files = sorted(os.listdir(asset_dir))
                except Exception:
                    continue

                for fname in files:
                    lower = fname.lower()
                    if lower.endswith(".json") and (
                        lower.startswith(asset_dir_name.lower())
                        or lower in ("ms_meta.json", "metadata.json", "manifest.json", "asset.json")
                    ):
                        manifest = os.path.join(asset_dir, fname)
                        break
                # Fallback: first JSON
                if manifest is None:
                    for fname in files:
                        if fname.lower().endswith(".json"):
                            manifest = os.path.join(asset_dir, fname)
                            break

                if manifest:
                    try:
                        record = _parse_ms_manifest(manifest, asset_dir, ms_type)
                        if record and record.asset_id not in seen_ids:
                            seen_ids.add(record.asset_id)
                            assets.append(record)
                            by_type[ms_type] = by_type.get(ms_type, 0) + 1
                    except Exception as exc:
                        warnings.append(f"Skipped {asset_dir}: {exc}")
                else:
                    # No manifest — try to infer from directory structure
                    record = self._infer_from_dir(asset_dir, asset_dir_name, ms_type)
                    if record and record.asset_id not in seen_ids:
                        seen_ids.add(record.asset_id)
                        assets.append(record)
                        by_type[ms_type] = by_type.get(ms_type, 0) + 1

        with self._lock:
            self._scan_count += 1
            result = MegascansScanResult(
                ok=True,
                library_path=path,
                assets_found=assets,
                by_type=by_type,
                total_scanned=dirs_scanned,
                warnings=warnings,
            )
            self._last_result = result
        return result

    def _infer_from_dir(
        self,
        asset_dir: str,
        dir_name: str,
        ms_type: str,
    ) -> Optional[MegascansAssetRecord]:
        """Infer basic metadata when no manifest exists."""
        try:
            formats = _detect_formats(asset_dir)
            if not formats:
                return None
            category = _MS_TYPE_TO_CATEGORY.get(ms_type, "prop")
            return MegascansAssetRecord(
                asset_id=dir_name,
                name=dir_name.replace("_", " ").strip(),
                ms_type=ms_type,
                category=category,
                formats=formats,
                map_types=_detect_map_types(asset_dir),
                resolution=_detect_resolution(asset_dir),
                local_path=asset_dir,
                provider="megascans",
            )
        except Exception:
            return None

    def build_metadata(self, record: MegascansAssetRecord) -> Dict[str, Any]:
        """Build enriched metadata dict from a MegascansAssetRecord."""
        return {
            "asset_id":    record.asset_id,
            "provider":    "megascans",
            "ms_type":     record.ms_type,
            "name":        record.name,
            "category":    record.category,
            "tags":        list(record.tags),
            "formats":     list(record.formats),
            "map_types":   list(record.map_types),
            "resolution":  record.resolution,
            "lod_count":   record.lod_count,
            "local_path":  record.local_path,
        }

    def infer_semantics(self, record: MegascansAssetRecord) -> Dict[str, Any]:
        """Infer semantic meaning from Megascans asset metadata."""
        # Environment suitability from tags and ms_type
        env_hints: List[str] = []
        tag_set = set(record.tags)
        type_env_map = {
            "3d":           ["industrial_hangar", "abandoned_factory"],
            "3dplant":      ["outdoor", "forest", "landscape"],
            "surface":      ["industrial_hangar", "abandoned_factory", "sci_fi_corridor"],
            "decal":        ["industrial_hangar", "abandoned_factory"],
            "imperfection": ["industrial_hangar", "abandoned_factory"],
            "atlas":        ["sci_fi_corridor", "control_room"],
        }
        env_hints = list(type_env_map.get(record.ms_type, []))

        # Style
        style = "photorealistic"
        if any(t in tag_set for t in ("stylized", "cartoon", "low_poly")):
            style = "stylized"

        # Scale estimate
        scale_map = {
            "3d":           "architectural",
            "3dplant":      "architectural",
            "surface":      "small",
            "decal":        "small",
            "imperfection": "tiny",
            "atlas":        "small",
        }
        scale = scale_map.get(record.ms_type, "unknown")

        return {
            "environment_suitability": env_hints,
            "style":                   style,
            "scale":                   scale,
            "has_textures":            len(record.map_types) > 0,
            "has_geometry":            bool(set(record.formats) & {"fbx", "obj", "gltf", "glb", "usd", "usda", "usdc", "usdz"}),
            "lod_ready":               record.lod_count > 1,
        }

    def build_asset_descriptor(self, record: MegascansAssetRecord) -> Dict[str, Any]:
        """Convert MegascansAssetRecord to an AssetDescriptor-compatible dict."""
        sem = self.infer_semantics(record)
        return {
            "asset_id":                record.asset_id,
            "provider":                "megascans",
            "name":                    record.name,
            "category":                record.category,
            "tags":                    list(record.tags),
            "keywords":                list(record.tags) + [record.ms_type],
            "formats":                 list(record.formats),
            "license":                 record.license,
            "download_url":            "",
            "preview_url":             "",
            "style":                   sem.get("style", "photorealistic"),
            "scale":                   sem.get("scale", "unknown"),
            "environment_suitability": sem.get("environment_suitability", []),
            "metadata": {
                "extra": {
                    "local_path":   record.local_path,
                    "ms_type":      record.ms_type,
                    "map_types":    record.map_types,
                    "resolution":   record.resolution,
                    "lod_count":    record.lod_count,
                    "source":       "megascans_local_library",
                    **record.metadata,
                }
            },
        }

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            last = self._last_result
        return {
            "scan_count":          self._scan_count,
            "last_scan_ok":        last.ok if last else None,
            "assets_in_last_scan": len(last.assets_found) if last else 0,
            "by_type":             dict(last.by_type) if last else {},
            "library_path":        self._library_path(),
        }


_INSTANCE: Optional[MegascansScanner] = None
_INSTANCE_LOCK = threading.Lock()


def get_megascans_scanner() -> MegascansScanner:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = MegascansScanner()
    return _INSTANCE


def reset_megascans_scanner_for_tests() -> None:
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
