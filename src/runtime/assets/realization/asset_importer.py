"""
Asset Importer (Tier 13)
========================
First step in the realization pipeline. Imports an AssetDescriptor dict
into the pipeline with provenance tracking.

No real file I/O. No network calls. Advisory and planning only.

DESIGN RULES:
  1. No bridge calls, no Houdini imports.
  2. No randomness — same input → same output.
  3. Never raises in public methods.
  4. Singleton pattern.

Public API:
    SUPPORTED_FORMATS
    ImportResult
    AssetImporter
    get_asset_importer()
    reset_asset_importer_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_FORMATS = frozenset({
    "fbx", "obj", "gltf", "glb",
    "usd", "usda", "usdc", "usdz",
})

_FORMAT_NOTES: Dict[str, str] = {
    "fbx":  "FBX — requires conversion to USD for scene realization.",
    "obj":  "OBJ — requires conversion to USD for scene realization.",
    "gltf": "glTF — requires conversion to USD for scene realization.",
    "glb":  "glTF binary — requires conversion to USD for scene realization.",
    "usd":  "USD — ready for scene realization.",
    "usda": "USD ASCII — ready for scene realization.",
    "usdc": "USD crate — ready for scene realization.",
    "usdz": "USDZ archive — ready for scene realization.",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ImportResult:
    """Result of an asset import operation."""

    ok:           bool = True
    asset_id:     str  = ""
    asset_name:   str  = ""
    format:       str  = ""
    source_type:  str  = "provider"
    file_path:    str  = ""
    metadata:     Dict[str, Any] = field(default_factory=dict)
    provenance:   Dict[str, Any] = field(default_factory=dict)
    errors:       List[str]      = field(default_factory=list)
    warnings:     List[str]      = field(default_factory=list)
    imported_at:  float          = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":          self.ok,
            "asset_id":    self.asset_id,
            "asset_name":  self.asset_name,
            "format":      self.format,
            "source_type": self.source_type,
            "file_path":   self.file_path,
            "metadata":    dict(self.metadata),
            "provenance":  dict(self.provenance),
            "errors":      list(self.errors),
            "warnings":    list(self.warnings),
            "imported_at": self.imported_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ImportResult":
        return cls(
            ok=bool(d.get("ok", True)),
            asset_id=str(d.get("asset_id", "")),
            asset_name=str(d.get("asset_name", "")),
            format=str(d.get("format", "")),
            source_type=str(d.get("source_type", "provider")),
            file_path=str(d.get("file_path", "")),
            metadata=dict(d.get("metadata") or {}),
            provenance=dict(d.get("provenance") or {}),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            imported_at=float(d.get("imported_at") or time.time()),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetImporter:
    """
    Imports AssetDescriptor dicts into the realization pipeline.
    Records provenance. Never performs real file I/O.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._import_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def import_asset(
        self,
        asset_dict: Dict[str, Any],
        source_path: str = "",
        source_type: str = "provider",
    ) -> ImportResult:
        """Import an asset dict into the pipeline.

        Never raises. Errors are captured in ImportResult.errors.
        """
        try:
            return self._do_import(asset_dict, source_path, source_type)
        except Exception as exc:
            safe = asset_dict if isinstance(asset_dict, dict) else {}
            return ImportResult(
                ok=False,
                asset_id=str(safe.get("asset_id", "")),
                asset_name=str(safe.get("name", "")),
                errors=[f"Import failed: {exc}"],
            )

    def import_from_storage(
        self,
        asset_id: str,
        storage_path: str = "",
    ) -> ImportResult:
        """Import an asset by ID from local storage."""
        try:
            asset_dict = {
                "asset_id":  asset_id,
                "name":      asset_id,
                "source":    "local_storage",
                "file_path": storage_path,
            }
            return self._do_import(asset_dict, storage_path, "storage")
        except Exception as exc:
            return ImportResult(
                ok=False,
                asset_id=asset_id,
                errors=[f"Storage import failed: {exc}"],
            )

    def import_from_provider(
        self,
        provider_name: str,
        asset_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ImportResult:
        """Import an asset from a named provider."""
        try:
            asset_dict = {
                "asset_id": asset_id,
                "name":     asset_id,
                "provider": provider_name,
                **(metadata or {}),
            }
            return self._do_import(asset_dict, "", provider_name)
        except Exception as exc:
            return ImportResult(
                ok=False,
                asset_id=asset_id,
                errors=[f"Provider import failed: {exc}"],
            )

    def validate_import(self, result: ImportResult) -> Dict[str, Any]:
        """Validate an ImportResult. Returns {'valid', 'errors', 'warnings'}."""
        errors: List[str] = []
        warnings: List[str] = []
        if not result.asset_id:
            errors.append("Import result has no asset_id.")
        if not result.asset_name:
            warnings.append("Import result has no asset_name.")
        if result.errors:
            errors.extend(result.errors)
        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    def build_import_report(self, results: List[ImportResult]) -> Dict[str, Any]:
        """Summarise a list of ImportResults."""
        total = len(results)
        successful = sum(1 for r in results if r.ok)
        failed = total - successful
        formats: Dict[str, int] = {}
        for r in results:
            fmt = r.format or "unknown"
            formats[fmt] = formats.get(fmt, 0) + 1
        return {
            "total":      total,
            "successful": successful,
            "failed":     failed,
            "by_format":  formats,
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"import_count": self._import_count}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_import(
        self,
        asset_dict: Dict[str, Any],
        source_path: str,
        source_type: str,
    ) -> ImportResult:
        asset_id   = str(asset_dict.get("asset_id", "") or str(uuid.uuid4()))
        asset_name = str(asset_dict.get("name", asset_id))
        fmt        = str(asset_dict.get("format", "")).lower().strip(".")
        file_path  = source_path or str(asset_dict.get("file_path", ""))

        warnings: List[str] = []
        if fmt and fmt not in SUPPORTED_FORMATS:
            warnings.append(
                f"Format '{fmt}' is not in SUPPORTED_FORMATS — "
                "downstream conversion may be required."
            )
        if fmt in _FORMAT_NOTES:
            note = _FORMAT_NOTES[fmt]
            if "conversion" in note:
                warnings.append(note)

        provenance = {
            "source_type": source_type,
            "provider":    str(asset_dict.get("provider", "")),
            "import_time": time.time(),
            "original_id": asset_id,
        }

        metadata = {
            k: v for k, v in asset_dict.items()
            if k not in {"asset_id", "name", "format", "file_path", "provider"}
        }

        with self._lock:
            self._import_count += 1

        return ImportResult(
            ok=True,
            asset_id=asset_id,
            asset_name=asset_name,
            format=fmt,
            source_type=source_type,
            file_path=file_path,
            metadata=metadata,
            provenance=provenance,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetImporter] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_importer() -> AssetImporter:
    """Return the module-level singleton AssetImporter."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetImporter()
    return _INSTANCE


def reset_asset_importer_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
