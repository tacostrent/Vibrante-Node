"""
Asset Converter (Tier 13)
=========================
Converts asset formats to USD-compatible representations.
No real file conversion — generates conversion plans and metadata.

DESIGN RULES:
  1. No bridge calls, no file I/O.
  2. No randomness — same input → same output.
  3. Never raises in public methods.
  4. Singleton pattern.

Public API:
    CONVERSION_MATRIX
    ConversionResult
    AssetConverter
    get_asset_converter()
    reset_asset_converter_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maps source format → list of supported target formats
CONVERSION_MATRIX: Dict[str, List[str]] = {
    "fbx":  ["usd", "usda", "usdc", "gltf"],
    "obj":  ["usd", "usda", "usdc", "gltf"],
    "gltf": ["usd", "usda", "usdc", "glb"],
    "glb":  ["usd", "usda", "usdc", "gltf"],
    "usd":  ["usda", "usdc", "usdz"],
    "usda": ["usd",  "usdc", "usdz"],
    "usdc": ["usd",  "usda", "usdz"],
    "usdz": ["usd",  "usda", "usdc"],
    "abc":  ["usd",  "usda", "usdc"],
    "bgeo": ["usd",  "usda"],
    "vdb":  ["usd",  "usda"],
}

_USD_FORMATS = frozenset({"usd", "usda", "usdc", "usdz"})


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ConversionResult:
    """Result of an asset format conversion."""

    ok:               bool        = True
    source_format:    str         = ""
    target_format:    str         = ""
    asset_id:         str         = ""
    asset_name:       str         = ""
    conversion_notes: List[str]   = field(default_factory=list)
    errors:           List[str]   = field(default_factory=list)
    warnings:         List[str]   = field(default_factory=list)
    converted_at:     float       = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":               self.ok,
            "source_format":    self.source_format,
            "target_format":    self.target_format,
            "asset_id":         self.asset_id,
            "asset_name":       self.asset_name,
            "conversion_notes": list(self.conversion_notes),
            "errors":           list(self.errors),
            "warnings":         list(self.warnings),
            "converted_at":     self.converted_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConversionResult":
        return cls(
            ok=bool(d.get("ok", True)),
            source_format=str(d.get("source_format", "")),
            target_format=str(d.get("target_format", "")),
            asset_id=str(d.get("asset_id", "")),
            asset_name=str(d.get("asset_name", "")),
            conversion_notes=list(d.get("conversion_notes") or []),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            converted_at=float(d.get("converted_at") or time.time()),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetConverter:
    """
    Converts asset format descriptors to USD-compatible representations.
    No real file operations — generates conversion plans.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conversion_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert(
        self,
        asset_dict: Dict[str, Any],
        target_format: str,
    ) -> ConversionResult:
        """Convert an asset to target_format.

        Never raises. Errors captured in ConversionResult.errors.
        """
        try:
            return self._do_convert(asset_dict, target_format.lower().strip("."))
        except Exception as exc:
            safe = asset_dict if isinstance(asset_dict, dict) else {}
            return ConversionResult(
                ok=False,
                asset_id=str(safe.get("asset_id", "")),
                asset_name=str(safe.get("name", "")),
                errors=[f"Conversion failed: {exc}"],
            )

    def convert_to_usd(self, asset_dict: Dict[str, Any]) -> ConversionResult:
        """Convenience: convert to 'usd' format."""
        return self.convert(asset_dict, "usd")

    def convert_to_gltf(self, asset_dict: Dict[str, Any]) -> ConversionResult:
        """Convenience: convert to 'gltf' format."""
        return self.convert(asset_dict, "gltf")

    def validate_conversion(self, result: ConversionResult) -> Dict[str, Any]:
        """Validate a ConversionResult."""
        errors: List[str] = list(result.errors)
        warnings: List[str] = list(result.warnings)
        if not result.target_format:
            errors.append("No target format specified.")
        return {
            "valid":    len(errors) == 0 and result.ok,
            "errors":   errors,
            "warnings": warnings,
        }

    def build_conversion_report(self, results: List[ConversionResult]) -> Dict[str, Any]:
        """Summarise a list of ConversionResults."""
        total = len(results)
        successful = sum(1 for r in results if r.ok)
        failed = total - successful
        by_target: Dict[str, int] = {}
        for r in results:
            by_target[r.target_format or "unknown"] = (
                by_target.get(r.target_format or "unknown", 0) + 1
            )
        return {
            "total":      total,
            "successful": successful,
            "failed":     failed,
            "by_target":  by_target,
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"conversion_count": self._conversion_count}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_convert(
        self,
        asset_dict: Dict[str, Any],
        target_format: str,
    ) -> ConversionResult:
        asset_id   = str(asset_dict.get("asset_id", ""))
        asset_name = str(asset_dict.get("name", asset_id))
        src_fmt    = str(asset_dict.get("format", "")).lower().strip(".")

        errors:           List[str] = []
        warnings:         List[str] = []
        conversion_notes: List[str] = []

        # Same-format passthrough
        if src_fmt and src_fmt == target_format:
            conversion_notes.append(
                f"Source and target formats are both '{src_fmt}' — no conversion needed."
            )
            with self._lock:
                self._conversion_count += 1
            return ConversionResult(
                ok=True,
                source_format=src_fmt,
                target_format=target_format,
                asset_id=asset_id,
                asset_name=asset_name,
                conversion_notes=conversion_notes,
            )

        # Unsupported target
        if target_format not in {t for targets in CONVERSION_MATRIX.values() for t in targets}:
            if target_format not in CONVERSION_MATRIX:
                errors.append(
                    f"Target format '{target_format}' is not supported. "
                    f"Supported targets: usd, usda, usdc, usdz, gltf, glb."
                )
                return ConversionResult(
                    ok=False,
                    source_format=src_fmt,
                    target_format=target_format,
                    asset_id=asset_id,
                    asset_name=asset_name,
                    errors=errors,
                )

        # Check matrix
        if src_fmt and src_fmt in CONVERSION_MATRIX:
            supported_targets = CONVERSION_MATRIX[src_fmt]
            if target_format not in supported_targets:
                warnings.append(
                    f"Conversion from '{src_fmt}' to '{target_format}' "
                    f"is not in the standard matrix — proceeding with caution."
                )
        elif not src_fmt:
            warnings.append("Source format is unknown — conversion path not validated.")

        # USD note
        if target_format in _USD_FORMATS:
            conversion_notes.append(
                f"Converted to {target_format} — asset is now USD-compatible "
                f"for scene realization."
            )
        else:
            conversion_notes.append(
                f"Converted from '{src_fmt or 'unknown'}' to '{target_format}'."
            )

        with self._lock:
            self._conversion_count += 1

        return ConversionResult(
            ok=True,
            source_format=src_fmt,
            target_format=target_format,
            asset_id=asset_id,
            asset_name=asset_name,
            conversion_notes=conversion_notes,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetConverter] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_converter() -> AssetConverter:
    """Return the module-level singleton AssetConverter."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetConverter()
    return _INSTANCE


def reset_asset_converter_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
