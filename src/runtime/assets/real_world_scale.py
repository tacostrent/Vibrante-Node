"""
real_world_scale.py — Real-World Import Scale Resolution
=========================================================
Authoritative import scale resolver for Megascans / Fab / DCC assets.

The ONLY correct way to import a Megascans FBX is at cm-to-meter scale:
    sx = sy = sz = 0.01

This module never computes a "normalize to target size" scale.  Every asset
preserves its authored real-world dimensions after import.

Priority chain:
  1. Explicit unit field in asset metadata (unit / unit_system / bbox_unit …)
  2. Provider identity (megascans / quixel / fab / quixel_bridge → cm → 0.01)
  3. File extension: USD-family files self-describe their units → 1.0
  4. Heuristic: if any raw bbox dimension > 10 Houdini units → assume cm → 0.01
  5. Default: 0.01  (Megascans centimeter export standard)

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Planning only.
  2. Deterministic — same metadata → same scale every call.
  3. Never raises.
  4. Singleton pattern.

Public API:
    RealWorldScaleResolver
    get_real_world_scale_resolver()
    reset_real_world_scale_resolver_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Unit tables
# ---------------------------------------------------------------------------

_UNIT_SCALE: Dict[str, float] = {
    "m":           1.0,
    "meters":      1.0,
    "meter":       1.0,
    "cm":          0.01,
    "centimeters": 0.01,
    "centimeter":  0.01,
    "mm":          0.001,
    "millimeters": 0.001,
    "millimeter":  0.001,
    "in":          0.0254,
    "inch":        0.0254,
    "inches":      0.0254,
    "ft":          0.3048,
    "feet":        0.3048,
    "foot":        0.3048,
}

# Providers that always export in centimeters
_CM_PROVIDERS = frozenset({
    "megascans",
    "quixel",
    "quixel_bridge",
    "fab",
    "megascans_api",
    "local_library",
})

# File extensions that carry their own unit metadata (handled by USD importer)
_SELF_DESCRIBING_FORMATS = frozenset({"usd", "usda", "usdc", "usdz"})

# If any raw bbox scalar exceeds this, we assume the asset is in cm-space
_CM_HEURISTIC_THRESHOLD = 10.0


class RealWorldScaleResolver:
    """
    Returns the correct uniform import scale (sx = sy = sz) for any asset.

    The returned value converts from the asset's native unit space to Houdini
    meters.  It is NEVER a "normalise to target height" scale.

    Examples
    --------
    Megascans chair (84 cm tall FBX) → scale = 0.01
      → imported height in Houdini = 84 * 0.01 = 0.84 m  ✓

    USD prop (already in meters) → scale = 1.0
      → dimensions unchanged  ✓
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_import_scale(self, asset_metadata: Dict[str, Any]) -> float:
        """
        Return sx = sy = sz for importing this asset.

        Never returns a size-normalisation factor.
        Never raises.
        """
        try:
            return self._resolve(asset_metadata)
        except Exception:
            return 0.01

    def describe_scale_decision(self, asset_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Return a debug dict explaining how the scale was determined."""
        scale = self.resolve_import_scale(asset_metadata)
        source_unit = (
            "cm" if abs(scale - 0.01) < 1e-9 else
            "mm" if abs(scale - 0.001) < 1e-9 else
            "m"  if abs(scale - 1.0) < 1e-9 else
            "custom"
        )
        units_per_m = round(1.0 / scale, 1) if scale > 0 else 0.0
        return {
            "scale":        scale,
            "source_unit":  source_unit,
            "units_per_m":  units_per_m,
            "note": (
                "Megascans/Quixel centimeter export — 1 unit = 1 cm = 0.01 m."
                if abs(scale - 0.01) < 1e-9 else
                "Metric — 1 unit = 1 m."
                if abs(scale - 1.0) < 1e-9 else
                f"Custom unit scale {scale}."
            ),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve(self, asset_metadata: Dict[str, Any]) -> float:
        # Priority 1: explicit unit field
        for key in ("unit", "unit_system", "units", "bbox_unit", "source_unit"):
            val = str(asset_metadata.get(key) or "").lower().strip()
            if val in _UNIT_SCALE:
                return _UNIT_SCALE[val]

        # Priority 2: provider signals cm-space
        provider = str(asset_metadata.get("provider") or "").lower().strip()
        if provider in _CM_PROVIDERS:
            return 0.01

        # Priority 3: USD self-describes units → importer handles them
        local_path = str(asset_metadata.get("local_path") or "")
        if local_path:
            ext = local_path.rsplit(".", 1)[-1].lower()
            if ext in _SELF_DESCRIBING_FORMATS:
                return 1.0

        # Priority 4: heuristic — any large raw bbox dim → assume cm
        for key in ("bbox_x", "bbox_y", "bbox_z", "width", "height", "depth"):
            v = asset_metadata.get(key)
            if v is not None:
                try:
                    if float(v) > _CM_HEURISTIC_THRESHOLD:
                        return 0.01
                except (TypeError, ValueError):
                    pass

        # Priority 5: default — Megascans cm-space standard
        return 0.01


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[RealWorldScaleResolver] = None
_LOCK = threading.Lock()


def get_real_world_scale_resolver() -> RealWorldScaleResolver:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = RealWorldScaleResolver()
        return _INSTANCE


def reset_real_world_scale_resolver_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
