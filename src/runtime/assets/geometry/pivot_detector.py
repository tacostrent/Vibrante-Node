"""
Pivot Detector (Tier 9.7 — Geometry Intelligence)
==================================================
Determines the pivot point type and position for an asset based on its
geometry metadata and placement type.

Pivot types:
  bottom_center  — pivot at the centroid of the bottom face (most common)
                   floor-placed furniture and props
  center         — pivot at the geometric center of the bbox
                   suspended or floating objects
  bottom_left    — pivot at the bottom-left corner
                   modular assets designed for grid snapping
  top_center     — pivot at the centroid of the top face
                   ceiling-mounted lights, hanging objects
  custom         — pivot from explicit metadata field

Confidence scoring:
  1.0  — explicit pivot data in metadata
  0.9  — known placement type with expected pivot
  0.7  — inferred from category
  0.5  — generic fallback

DESIGN RULES:
  1. No bridge calls. No Houdini imports.
  2. Deterministic — same asset dict → same pivot.
  3. Never raises.
  4. Singleton pattern.

Public API:
    PivotDetector
    get_pivot_detector()
    reset_pivot_detector_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

# Placement types that should have bottom_center pivot (floor-placed)
_FLOOR_PLACED_TYPES = frozenset({
    "table", "desk", "workbench", "chair", "stool", "bench", "cabinet",
    "shelf", "server_rack", "rack", "machine", "large_machine",
    "industrial_machine", "crane", "reactor", "engine", "vehicle",
    "vehicle_small", "barrel", "crate", "pallet", "bucket", "sofa",
    "bed", "wardrobe", "counter", "bar_counter", "console", "display_case",
    "terrain", "tree", "plant", "wall", "column", "beam", "platform",
    "door", "window",
})

# Placement types with top_center pivot (ceiling-mounted or hanging)
_CEILING_MOUNTED_TYPES = frozenset({
    "hanging_light", "pendant_light", "overhead_sign",
    "ceiling_mount", "sprinkler", "hanging_prop",
})

# Placement types with center pivot (floating or symmetric)
_CENTER_PIVOT_TYPES = frozenset({
    "particle_emitter", "light_volume", "trigger_volume",
    "ambient_prop", "floating_prop",
})

# Placement types where bottom_left is preferred (modular / grid-snap)
_BOTTOM_LEFT_TYPES = frozenset({
    "floor_panel", "ceiling_panel", "wall_tile", "floor_tile",
    "modular_wall", "modular_floor",
})


class PivotDetector:
    """Detects pivot type and estimated position for an asset."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def detect(
        self,
        asset: Dict[str, Any],
        height_m: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Detect pivot information.

        Args:
            asset:    asset metadata dict
            height_m: asset height in meters (for position computation)

        Returns dict:
            {
                "pivot_type":     str,
                "pivot_position": [x, y, z],  # in object space
                "confidence":     float,
            }
        Never raises.
        """
        try:
            return self._detect(asset, height_m)
        except Exception:
            return {
                "pivot_type":     "bottom_center",
                "pivot_position": [0.0, 0.0, 0.0],
                "confidence":     0.5,
            }

    def _detect(self, asset: Dict[str, Any], height_m: float) -> Dict[str, Any]:
        pt = str(asset.get("placement_type") or "").lower().strip()
        cat = str(asset.get("category") or "").lower().strip()

        # --- Priority 1: explicit pivot field ---
        explicit = asset.get("pivot") or asset.get("pivot_point") or asset.get("pivot_type")
        if explicit:
            if isinstance(explicit, str):
                ptype = explicit.lower().strip()
                if ptype in ("bottom_center", "center", "bottom_left", "top_center", "custom"):
                    return {
                        "pivot_type":     ptype,
                        "pivot_position": self._position_for_type(ptype, height_m),
                        "confidence":     1.0,
                    }
            elif isinstance(explicit, (list, tuple)) and len(explicit) == 3:
                pos = [float(v) for v in explicit]
                ptype = self._classify_from_position(pos, height_m)
                return {
                    "pivot_type":     ptype,
                    "pivot_position": pos,
                    "confidence":     1.0,
                }

        # --- Priority 2: explicit pivot position ---
        pivot_pos = asset.get("pivot_position")
        if isinstance(pivot_pos, (list, tuple)) and len(pivot_pos) == 3:
            try:
                pos = [float(v) for v in pivot_pos]
                # Classify from position
                ptype = self._classify_from_position(pos, height_m)
                return {
                    "pivot_type":     ptype,
                    "pivot_position": pos,
                    "confidence":     1.0,
                }
            except (TypeError, ValueError):
                pass

        # --- Priority 3: infer from placement type ---
        if pt in _CEILING_MOUNTED_TYPES:
            return {
                "pivot_type":     "top_center",
                "pivot_position": self._position_for_type("top_center", height_m),
                "confidence":     0.9,
            }

        if pt in _CENTER_PIVOT_TYPES:
            return {
                "pivot_type":     "center",
                "pivot_position": self._position_for_type("center", height_m),
                "confidence":     0.9,
            }

        if pt in _BOTTOM_LEFT_TYPES:
            return {
                "pivot_type":     "bottom_left",
                "pivot_position": self._position_for_type("bottom_left", height_m),
                "confidence":     0.9,
            }

        if pt in _FLOOR_PLACED_TYPES:
            return {
                "pivot_type":     "bottom_center",
                "pivot_position": [0.0, 0.0, 0.0],
                "confidence":     0.9,
            }

        # --- Priority 4: infer from category ---
        if cat in ("furniture", "seating", "storage", "industrial", "vehicle"):
            return {
                "pivot_type":     "bottom_center",
                "pivot_position": [0.0, 0.0, 0.0],
                "confidence":     0.7,
            }

        if cat in ("structure", "architectural"):
            return {
                "pivot_type":     "bottom_left",
                "pivot_position": self._position_for_type("bottom_left", height_m),
                "confidence":     0.7,
            }

        if cat in ("lighting",):
            # Lights can be ceiling-mounted or floor-standing
            return {
                "pivot_type":     "bottom_center",
                "pivot_position": [0.0, 0.0, 0.0],
                "confidence":     0.6,
            }

        # --- Fallback ---
        return {
            "pivot_type":     "bottom_center",
            "pivot_position": [0.0, 0.0, 0.0],
            "confidence":     0.5,
        }

    @staticmethod
    def _position_for_type(pivot_type: str, height_m: float) -> List[float]:
        if pivot_type == "bottom_center":
            return [0.0, 0.0, 0.0]
        if pivot_type == "center":
            return [0.0, height_m / 2.0, 0.0]
        if pivot_type == "top_center":
            return [0.0, height_m, 0.0]
        if pivot_type == "bottom_left":
            return [0.0, 0.0, 0.0]   # local origin at bottom-left corner
        return [0.0, 0.0, 0.0]

    @staticmethod
    def _classify_from_position(pos: List[float], height_m: float) -> str:
        y = pos[1] if len(pos) > 1 else 0.0
        tol = 0.05
        if y < tol:
            return "bottom_center"
        if abs(y - height_m / 2.0) < tol:
            return "center"
        if abs(y - height_m) < tol:
            return "top_center"
        return "custom"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[PivotDetector] = None
_LOCK = threading.Lock()


def get_pivot_detector() -> PivotDetector:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = PivotDetector()
        return _INSTANCE


def reset_pivot_detector_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
