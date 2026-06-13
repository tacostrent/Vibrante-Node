"""
Asset Normalizer (Tier 13)
==========================
Normalizes asset scale, orientation, units, and pivots to production
standards. All normalization is deterministic — no randomness.

No real mesh operations — generates normalization plans.

DESIGN RULES:
  1. No bridge calls, no file I/O.
  2. No randomness — same input → same output.
  3. Never raises in public methods.
  4. Singleton pattern.

Public API:
    NormalizationResult
    AssetNormalizer
    get_asset_normalizer()
    reset_asset_normalizer_for_tests()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_UNIT_SCALE_FACTORS: Dict[str, float] = {
    "m":     1.0,
    "meter": 1.0,
    "cm":    0.01,
    "centimeter": 0.01,
    "mm":    0.001,
    "millimeter": 0.001,
    "inch":  0.0254,
    "in":    0.0254,
    "foot":  0.3048,
    "ft":    0.3048,
    "yard":  0.9144,
    "km":    1000.0,
}

_VALID_UP_AXES = frozenset({"X", "Y", "Z", "-X", "-Y", "-Z"})

_ORIENTATION_ROTATIONS: Dict[str, Dict[str, float]] = {
    "Y": {"rx": 0.0,   "ry": 0.0, "rz": 0.0},
    "Z": {"rx": -90.0, "ry": 0.0, "rz": 0.0},
    "X": {"rx": 0.0,   "ry": 0.0, "rz": 90.0},
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class NormalizationResult:
    """Result of a full asset normalization pass."""

    ok:                   bool      = True
    asset_id:             str       = ""
    asset_name:           str       = ""
    scale_applied:        bool      = False
    orientation_applied:  bool      = False
    units_normalized:     bool      = False
    pivot_normalized:     bool      = False
    metadata_normalized:  bool      = False
    normalization_notes:  List[str] = field(default_factory=list)
    errors:               List[str] = field(default_factory=list)
    warnings:             List[str] = field(default_factory=list)
    normalized_at:        float     = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok":                  self.ok,
            "asset_id":            self.asset_id,
            "asset_name":          self.asset_name,
            "scale_applied":       self.scale_applied,
            "orientation_applied": self.orientation_applied,
            "units_normalized":    self.units_normalized,
            "pivot_normalized":    self.pivot_normalized,
            "metadata_normalized": self.metadata_normalized,
            "normalization_notes": list(self.normalization_notes),
            "errors":              list(self.errors),
            "warnings":            list(self.warnings),
            "normalized_at":       self.normalized_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NormalizationResult":
        return cls(
            ok=bool(d.get("ok", True)),
            asset_id=str(d.get("asset_id", "")),
            asset_name=str(d.get("asset_name", "")),
            scale_applied=bool(d.get("scale_applied", False)),
            orientation_applied=bool(d.get("orientation_applied", False)),
            units_normalized=bool(d.get("units_normalized", False)),
            pivot_normalized=bool(d.get("pivot_normalized", False)),
            metadata_normalized=bool(d.get("metadata_normalized", False)),
            normalization_notes=list(d.get("normalization_notes") or []),
            errors=list(d.get("errors") or []),
            warnings=list(d.get("warnings") or []),
            normalized_at=float(d.get("normalized_at") or time.time()),
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AssetNormalizer:
    """
    Normalizes asset descriptors to production standards.
    All normalization is deterministic.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._normalize_count = 0

    # ------------------------------------------------------------------
    # Public API — individual steps
    # ------------------------------------------------------------------

    def normalize_scale(
        self,
        asset_dict: Dict[str, Any],
        target_scale: float = 1.0,
    ) -> Dict[str, Any]:
        """Compute scale normalization. Returns {'scale_factor', 'applied'}."""
        current_scale = float(asset_dict.get("scale", 1.0) or 1.0)
        if current_scale == 0.0:
            current_scale = 1.0
        scale_factor = target_scale / current_scale
        applied = abs(scale_factor - 1.0) > 1e-6
        return {
            "scale_factor": scale_factor,
            "applied":      applied,
            "note": (
                f"Scale factor {scale_factor:.4f} applied (from {current_scale} to {target_scale})."
                if applied else "No scale normalization needed."
            ),
        }

    def normalize_orientation(
        self,
        asset_dict: Dict[str, Any],
        up_axis: str = "Y",
    ) -> Dict[str, Any]:
        """Compute orientation normalization to up_axis."""
        up = up_axis.upper()
        src_up = str(asset_dict.get("up_axis", "Y")).upper()
        applied = src_up != up
        rotation = _ORIENTATION_ROTATIONS.get(src_up, {"rx": 0.0, "ry": 0.0, "rz": 0.0})
        return {
            "source_up":  src_up,
            "target_up":  up,
            "rotation":   rotation,
            "applied":    applied,
            "note": (
                f"Orientation correction: {src_up} → {up} ({rotation})."
                if applied else f"Up axis is already {up} — no rotation needed."
            ),
        }

    def normalize_units(
        self,
        asset_dict: Dict[str, Any],
        target_unit: str = "m",
    ) -> Dict[str, Any]:
        """Compute unit normalization. Returns {'scale_factor', 'source_unit'}."""
        src_unit = str(asset_dict.get("unit", "m") or "m").lower()
        target   = target_unit.lower()
        src_factor = _UNIT_SCALE_FACTORS.get(src_unit, 1.0)
        tgt_factor = _UNIT_SCALE_FACTORS.get(target, 1.0)
        if tgt_factor == 0.0:
            tgt_factor = 1.0
        scale_factor = src_factor / tgt_factor
        applied = abs(scale_factor - 1.0) > 1e-9
        return {
            "source_unit": src_unit,
            "target_unit": target,
            "scale_factor": scale_factor,
            "applied":      applied,
            "note": (
                f"Unit conversion: {src_unit} → {target} (factor {scale_factor:.6f})."
                if applied else f"Units already in {target} — no conversion needed."
            ),
        }

    def normalize_pivots(self, asset_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Compute pivot normalization to scene origin."""
        pivot = asset_dict.get("pivot", None)
        if pivot and isinstance(pivot, (list, tuple)) and len(pivot) >= 3:
            px, py, pz = float(pivot[0]), float(pivot[1]), float(pivot[2])
            applied = abs(px) > 1e-6 or abs(py) > 1e-6 or abs(pz) > 1e-6
        else:
            px, py, pz = 0.0, 0.0, 0.0
            applied = False

        return {
            "pivot_offset": {"tx": -px, "ty": -py, "tz": -pz},
            "applied":      applied,
            "note": (
                f"Pivot offset applied: ({-px:.3f}, {-py:.3f}, {-pz:.3f})."
                if applied else "Pivot is at scene origin — no offset needed."
            ),
        }

    def normalize_metadata(self, asset_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize metadata fields (lowercase strings, strip whitespace)."""
        normalized: Dict[str, Any] = {}
        for k, v in asset_dict.items():
            if isinstance(v, str):
                normalized[k] = v.strip()
            else:
                normalized[k] = v
        return {
            "normalized_fields": list(normalized.keys()),
            "metadata":          normalized,
            "applied":           True,
        }

    def normalize(self, asset_dict: Dict[str, Any]) -> NormalizationResult:
        """Run all normalization steps. Never raises."""
        try:
            return self._do_normalize(asset_dict)
        except Exception as exc:
            safe = asset_dict if isinstance(asset_dict, dict) else {}
            return NormalizationResult(
                ok=False,
                asset_id=str(safe.get("asset_id", "")),
                asset_name=str(safe.get("name", "")),
                errors=[f"Normalization failed: {exc}"],
            )

    def build_normalization_report(
        self,
        results: List[NormalizationResult],
    ) -> Dict[str, Any]:
        """Summarise a list of NormalizationResults."""
        total = len(results)
        successful = sum(1 for r in results if r.ok)
        return {
            "total":       total,
            "successful":  successful,
            "failed":      total - successful,
            "scale_applied":       sum(1 for r in results if r.scale_applied),
            "orientation_applied": sum(1 for r in results if r.orientation_applied),
            "units_normalized":    sum(1 for r in results if r.units_normalized),
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"normalize_count": self._normalize_count}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_normalize(self, asset_dict: Dict[str, Any]) -> NormalizationResult:
        asset_id   = str(asset_dict.get("asset_id", ""))
        asset_name = str(asset_dict.get("name", asset_id))
        notes: List[str] = []

        scale_r       = self.normalize_scale(asset_dict)
        orientation_r = self.normalize_orientation(asset_dict)
        units_r       = self.normalize_units(asset_dict)
        pivot_r       = self.normalize_pivots(asset_dict)
        meta_r        = self.normalize_metadata(asset_dict)

        for r in (scale_r, orientation_r, units_r, pivot_r):
            if r.get("note"):
                notes.append(r["note"])

        with self._lock:
            self._normalize_count += 1

        return NormalizationResult(
            ok=True,
            asset_id=asset_id,
            asset_name=asset_name,
            scale_applied=bool(scale_r.get("applied")),
            orientation_applied=bool(orientation_r.get("applied")),
            units_normalized=bool(units_r.get("applied")),
            pivot_normalized=bool(pivot_r.get("applied")),
            metadata_normalized=bool(meta_r.get("applied")),
            normalization_notes=notes,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[AssetNormalizer] = None
_INSTANCE_LOCK = threading.Lock()


def get_asset_normalizer() -> AssetNormalizer:
    """Return the module-level singleton AssetNormalizer."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AssetNormalizer()
    return _INSTANCE


def reset_asset_normalizer_for_tests() -> None:
    """Replace the singleton. For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
