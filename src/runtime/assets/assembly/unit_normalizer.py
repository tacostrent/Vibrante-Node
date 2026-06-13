"""
Unit Normalizer (Tier 9.6 — Scale-Aware Spatial Placement)
===========================================================
Converts asset dimensions from any supported source unit into meters.
This is the root-cause fix for assets imported in centimeter space being
placed using meter-space offsets, causing all dimensions to appear 100x
larger than intended and producing invalid layouts.

Supported source units:
  cm / centimeters / centimetre
  mm / millimeters / millimetre
  m  / meters      / metre
  in / inch        / inches
  ft / feet        / foot

All output is in meters. Same input → same output (deterministic).

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Pure arithmetic.
  2. Deterministic — same value + unit → same meter value.
  3. Never raises — unknown units treated as meters (factor 1.0).
  4. Singleton pattern.

Public API:
    UNIT_FACTORS
    UnitNormalizer
    get_unit_normalizer()
    reset_unit_normalizer_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Conversion factors → meters
# ---------------------------------------------------------------------------

UNIT_FACTORS: Dict[str, float] = {
    # Centimeters
    "cm":          0.01,
    "centimeter":  0.01,
    "centimeters": 0.01,
    "centimetre":  0.01,
    "centimetres": 0.01,
    # Millimeters
    "mm":          0.001,
    "millimeter":  0.001,
    "millimeters": 0.001,
    "millimetre":  0.001,
    "millimetres": 0.001,
    # Meters (identity)
    "m":           1.0,
    "meter":       1.0,
    "meters":      1.0,
    "metre":       1.0,
    "metres":      1.0,
    # Inches
    "in":          0.0254,
    "inch":        0.0254,
    "inches":      0.0254,
    # Feet
    "ft":          0.3048,
    "foot":        0.3048,
    "feet":        0.3048,
}

# Threshold above which explicit bbox values are presumed to be centimeters
# (heuristic — a 10 m wide chair is implausible; 10 cm is plausible)
_CM_HEURISTIC_THRESHOLD = 10.0


class UnitNormalizer:
    """Converts asset dimensions from source units to meters.

    Primary use: fix the mismatch between Megascans/Fab assets imported in
    centimeter space and the placement engine's meter-based coordinate system.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Core conversion
    # ------------------------------------------------------------------

    def to_meters(self, value: float, from_unit: str) -> float:
        """Convert *value* from *from_unit* to meters.

        Returns max(0.0, value * factor). Unknown units → factor 1.0.
        """
        factor = UNIT_FACTORS.get(from_unit.lower().strip(), 1.0)
        return max(0.0, value * factor)

    def normalize_bbox(
        self,
        x: float,
        y: float,
        z: float,
        from_unit: str,
    ) -> Tuple[float, float, float]:
        """Convert (x, y, z) bounding box from *from_unit* to meters."""
        factor = UNIT_FACTORS.get(from_unit.lower().strip(), 1.0)
        return (
            max(0.0, x * factor),
            max(0.0, y * factor),
            max(0.0, z * factor),
        )

    # ------------------------------------------------------------------
    # Unit detection
    # ------------------------------------------------------------------

    def detect_unit(self, asset: Dict[str, Any]) -> str:
        """Detect the source unit system from asset metadata.

        Detection order:
          1. Explicit fields: unit, unit_system, units, bbox_unit, source_unit
          2. Heuristic: if any bbox dimension > 10 → assume centimeters
          3. Default: meters

        Returns a canonical lowercase unit string (e.g. "cm", "meters").
        Never raises.
        """
        try:
            for key in ("unit", "unit_system", "units", "bbox_unit", "source_unit"):
                raw = str(asset.get(key) or "").lower().strip()
                if raw in UNIT_FACTORS:
                    return raw

            # Heuristic fallback: implausibly large explicit bbox → centimeters
            bx = float(asset.get("bbox_x") or 0)
            by = float(asset.get("bbox_y") or 0)
            bz = float(asset.get("bbox_z") or 0)
            if any(v > _CM_HEURISTIC_THRESHOLD for v in (bx, by, bz)):
                return "cm"

        except Exception:
            pass

        return "meters"

    def normalize_asset_bbox(
        self, asset: Dict[str, Any]
    ) -> Tuple[float, float, float]:
        """Extract and normalize the bounding box from asset metadata to meters.

        Reads bbox_x/bbox_y/bbox_z, detects their unit, and returns
        (x_m, y_m, z_m) all in meters. Returns (0, 0, 0) if no bbox data.
        """
        try:
            bx = float(asset.get("bbox_x") or 0)
            by = float(asset.get("bbox_y") or 0)
            bz = float(asset.get("bbox_z") or 0)
            if bx == 0 and by == 0 and bz == 0:
                return (0.0, 0.0, 0.0)
            unit = self.detect_unit(asset)
            return self.normalize_bbox(bx, by, bz, unit)
        except Exception:
            return (0.0, 0.0, 0.0)

    def factor_for(self, unit: str) -> float:
        """Return the conversion factor to meters for the given unit string."""
        return UNIT_FACTORS.get(unit.lower().strip(), 1.0)

    def supported_units(self) -> list:
        """Return a sorted list of all recognised unit strings."""
        return sorted(UNIT_FACTORS.keys())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[UnitNormalizer] = None
_LOCK = threading.Lock()


def get_unit_normalizer() -> UnitNormalizer:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = UnitNormalizer()
        return _INSTANCE


def reset_unit_normalizer_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
