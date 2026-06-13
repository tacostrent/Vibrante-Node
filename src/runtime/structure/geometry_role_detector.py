"""
Geometry Role Detector (Tier 10.3 — Structural Asset Classification)
=====================================================================
Classify an asset's structural role from its physical dimensions alone.
Uses height dominance, aspect ratios, and volume thresholds to distinguish
beams, columns, doorways, wall segments, floor pieces, and furniture.

No external ML. No bridge calls. Deterministic.

Public API:
    GeometryRoleDetector
    get_geometry_role_detector()
    reset_geometry_role_detector_for_tests()
"""

from __future__ import annotations

import threading
from typing import Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Dimension thresholds
# ──────────────────────────────────────────────────────────────────────────────

_FURNITURE_MAX_DIM   = 2.0   # above this, likely not furniture
_BEAM_MIN_LEN        = 2.0   # minimum horizontal span for a beam
_BEAM_MAX_CROSS      = 0.6   # max cross-section (height or depth) for a beam
_BEAM_RATIO          = 4.0   # span / cross-section ratio for beam
_COLUMN_MIN_H        = 2.0   # minimum height for a column
_COLUMN_MAX_FOOT     = 0.8   # maximum footprint dim (w or d) for a column
_COLUMN_RATIO        = 3.5   # height / max-footprint ratio for column
_DOORWAY_MIN_H       = 1.8   # minimum doorway height
_DOORWAY_MIN_W       = 0.5   # minimum doorway width
_DOORWAY_MAX_D       = 0.5   # maximum doorway depth (thin element)
_DOORWAY_DEPTH_RATIO = 3.0   # h / d ratio to confirm thin profile
_WALL_MIN_H          = 2.0
_WALL_MIN_W          = 1.5
_WALL_MAX_D          = 0.5
_FLOOR_MAX_H         = 0.25  # very flat
_FLOOR_MIN_FOOTPRINT = 1.0   # large footprint area (w×d)
_ARCHWAY_MIN_H       = 2.0
_ARCHWAY_MIN_W       = 1.5
_ARCHWAY_MAX_D       = 0.8
_STAIR_MIN_W         = 0.8
_STAIR_MAX_H         = 2.5
_STAIR_ASPECT        = 1.5   # w/d roughly square-ish footprint but not too tall


class GeometryRoleDetector:
    """
    Classify structural role from bounding-box dimensions (all in metres).

    Returns (role: str, confidence: float).
    Role is one of the Tier 10.3 structural roles or "furniture"/"prop".
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def detect(
        self,
        width_m:  float,
        height_m: float,
        depth_m:  float,
    ) -> Tuple[str, float]:
        """
        Classify role from dimensions.

        Args:
            width_m:  X extent in metres
            height_m: Y extent (up) in metres
            depth_m:  Z extent in metres

        Returns:
            (role, confidence) — never raises.
        """
        try:
            return self._detect(width_m, height_m, depth_m)
        except Exception:
            return "structural_unknown", 0.30

    def _detect(self, w: float, h: float, d: float) -> Tuple[str, float]:
        w = max(w, 0.001)
        h = max(h, 0.001)
        d = max(d, 0.001)

        # ── 1. Beam: long horizontal, tiny cross-section ──────────────────
        # Longest axis is horizontal (w or d), very small in the other two dims.
        if w >= _BEAM_MIN_LEN and h <= _BEAM_MAX_CROSS and d <= _BEAM_MAX_CROSS:
            ratio = w / max(h, d)
            if ratio >= _BEAM_RATIO:
                confidence = min(1.0, 0.70 + (ratio - _BEAM_RATIO) * 0.02)
                return "beam", round(confidence, 2)

        # Depth-dominant beam (e.g. oriented along Z)
        if d >= _BEAM_MIN_LEN and h <= _BEAM_MAX_CROSS and w <= _BEAM_MAX_CROSS:
            ratio = d / max(h, w)
            if ratio >= _BEAM_RATIO:
                confidence = min(1.0, 0.70 + (ratio - _BEAM_RATIO) * 0.02)
                return "beam", round(confidence, 2)

        # ── 2. Column: tall, small footprint ─────────────────────────────
        max_foot = max(w, d)
        if h >= _COLUMN_MIN_H and max_foot <= _COLUMN_MAX_FOOT:
            ratio = h / max_foot
            if ratio >= _COLUMN_RATIO:
                confidence = min(1.0, 0.70 + (ratio - _COLUMN_RATIO) * 0.03)
                return "column", round(confidence, 2)

        # ── 3. Doorway: tall (>= 1.8m), moderate width, very thin depth ──
        if (h >= _DOORWAY_MIN_H and w >= _DOORWAY_MIN_W
                and d <= _DOORWAY_MAX_D and h / d >= _DOORWAY_DEPTH_RATIO):
            # h/w ratio distinguishes doorway (taller than wide) vs archway
            if h / w >= 1.1:
                return "doorway", 0.78
            else:
                return "archway", 0.65

        # ── 4. Wall segment: tall, wide, thin ────────────────────────────
        if h >= _WALL_MIN_H and w >= _WALL_MIN_W and d <= _WALL_MAX_D:
            return "wall_segment", 0.75

        # Rotated wall (depth dominant width)
        if h >= _WALL_MIN_H and d >= _WALL_MIN_W and w <= _WALL_MAX_D:
            return "wall_segment", 0.72

        # ── 5. Floor piece: very flat, large footprint ────────────────────
        footprint = w * d
        if h <= _FLOOR_MAX_H and footprint >= _FLOOR_MIN_FOOTPRINT:
            return "floor_piece", 0.80

        # ── 6. Fireplace: roughly cuboid, deeper than wide, moderate height
        # Typically: w 0.8–1.8, h 1.0–2.2, d 0.4–1.0
        if 0.6 <= w <= 2.0 and 0.8 <= h <= 2.5 and 0.3 <= d <= 1.2:
            # Fireplaces tend to be roughly as tall as or taller than wide
            if h / w >= 0.8 and d / w <= 0.8:
                # No strong geometric signal — return low confidence;
                # metadata will override if keywords match.
                pass  # fall through

        # ── 7. Stair: medium height, wide footprint, not too tall ─────────
        if (h <= _STAIR_MAX_H and w >= _STAIR_MIN_W
                and d >= _STAIR_MIN_W and abs(w / d - 1.0) < _STAIR_ASPECT):
            # Stairs are typically taller than floor pieces but shorter than walls
            if 0.4 <= h <= 2.5 and footprint >= 1.0:
                pass  # low-confidence stair — metadata is more reliable

        # ── 8. Furniture range: all dims below furniture threshold ─────────
        max_dim = max(w, h, d)
        if max_dim < _FURNITURE_MAX_DIM:
            # Distinguish furniture from large prop
            if max_dim < 1.5:
                return "furniture", 0.65
            else:
                # Between 1.5 and 2.0 m — could be large furniture or small structural
                return "furniture", 0.55

        # ── 9. Large architectural module catch-all ───────────────────────
        return "architectural_module", 0.45


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_INSTANCE: Optional[GeometryRoleDetector] = None
_LOCK = threading.Lock()


def get_geometry_role_detector() -> GeometryRoleDetector:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = GeometryRoleDetector()
        return _INSTANCE


def reset_geometry_role_detector_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
