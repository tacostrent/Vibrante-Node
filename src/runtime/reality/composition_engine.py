"""
composition_engine.py — §54 Reality Intelligence (Tier 15.0+)
==============================================================
Composition Rule. Every room must contain:

    Primary focal point      (e.g. fireplace)
    Secondary focal point    (e.g. dining table)
    Negative space           (empty walking area)

Focal-point priority: fireplace > table > bar > machine > desk > bed >
largest remaining asset.

Public API:
    FocalPoint
    CompositionResult
    CompositionEngine
    get_composition_engine()
    reset_composition_engine_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.reality.reality_scene_model import (
    SceneAsset,
    SceneSnapshot,
    STRUCTURAL_TYPES,
    parse_scene,
)

_FOCAL_PRIORITY = ["fireplace", "table", "bar", "machine", "desk", "bed"]
MIN_NEGATIVE_SPACE = 0.25   # at least 25% of the floor must stay walkable


@dataclass
class FocalPoint:
    asset_id:   str
    asset_name: str
    asset_type: str
    rank:       str   # "primary" | "secondary"
    tx: float = 0.0
    tz: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":   self.asset_id,
            "asset_name": self.asset_name,
            "asset_type": self.asset_type,
            "rank":       self.rank,
            "tx":         round(self.tx, 4),
            "tz":         round(self.tz, 4),
        }


@dataclass
class CompositionResult:
    primary_focal:   Optional[Dict[str, Any]] = None
    secondary_focal: Optional[Dict[str, Any]] = None
    negative_space_ratio: float = 1.0
    occupied_area:        float = 0.0
    room_area:            float = 0.0
    has_primary:    bool = False
    has_secondary:  bool = False
    has_negative_space: bool = False
    composition_ok: bool = False
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_focal":        self.primary_focal,
            "secondary_focal":      self.secondary_focal,
            "negative_space_ratio": round(self.negative_space_ratio, 4),
            "occupied_area":        round(self.occupied_area, 4),
            "room_area":            round(self.room_area, 4),
            "has_primary":          self.has_primary,
            "has_secondary":        self.has_secondary,
            "has_negative_space":   self.has_negative_space,
            "composition_ok":       self.composition_ok,
            "findings":             list(self.findings),
        }


class CompositionEngine:
    """Identifies focal points and validates negative space. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def evaluate(self, scene_layout: Dict[str, Any]) -> CompositionResult:
        try:
            return self._evaluate(parse_scene(scene_layout))
        except Exception as exc:
            r = CompositionResult()
            r.findings.append(f"CompositionEngine internal error: {exc}")
            return r

    def evaluate_snapshot(self, snap: SceneSnapshot) -> CompositionResult:
        try:
            return self._evaluate(snap)
        except Exception as exc:
            r = CompositionResult()
            r.findings.append(f"CompositionEngine internal error: {exc}")
            return r

    # ------------------------------------------------------------------

    def _evaluate(self, snap: SceneSnapshot) -> CompositionResult:
        result = CompositionResult(room_area=snap.room_area)

        # --- Focal points -------------------------------------------------
        primary, secondary = self._focal_points(snap)
        if primary is not None:
            result.primary_focal = FocalPoint(
                asset_id=primary.asset_id, asset_name=primary.asset_name,
                asset_type=primary.asset_type, rank="primary",
                tx=primary.tx, tz=primary.tz,
            ).to_dict()
            result.has_primary = True
        else:
            result.findings.append(
                "NO_PRIMARY_FOCAL: the room has no focal point — every room "
                "needs a primary focal point (§54 Composition Rule)"
            )
        if secondary is not None:
            result.secondary_focal = FocalPoint(
                asset_id=secondary.asset_id, asset_name=secondary.asset_name,
                asset_type=secondary.asset_type, rank="secondary",
                tx=secondary.tx, tz=secondary.tz,
            ).to_dict()
            result.has_secondary = True
        else:
            result.findings.append(
                "NO_SECONDARY_FOCAL: the room has only one point of interest — "
                "add a secondary focal point"
            )

        # --- Negative space -----------------------------------------------
        occupied = 0.0
        for a in snap.assets:
            if a.asset_type in STRUCTURAL_TYPES or a.asset_type in ("poster", "rug"):
                continue
            if a.bottom_y > snap.floor_height + 0.5:
                continue   # items on surfaces don't consume floor space
            occupied += (2.0 * a.half_x) * (2.0 * a.half_z)
        result.occupied_area = occupied
        if snap.room_area > 0:
            result.negative_space_ratio = max(0.0, 1.0 - occupied / snap.room_area)
        result.has_negative_space = result.negative_space_ratio >= MIN_NEGATIVE_SPACE
        if not result.has_negative_space:
            result.findings.append(
                f"NO_NEGATIVE_SPACE: only {result.negative_space_ratio:.0%} of the "
                f"floor is walkable — keep at least {MIN_NEGATIVE_SPACE:.0%} empty"
            )

        result.composition_ok = (
            result.has_primary and result.has_secondary and result.has_negative_space
        )
        return result

    def _focal_points(self, snap: SceneSnapshot):
        candidates: List[SceneAsset] = []
        for asset_type in _FOCAL_PRIORITY:
            for a in snap.assets_of_type(asset_type):
                candidates.append(a)
        # Fallback: largest non-structural asset by footprint
        if len(candidates) < 2:
            extras = sorted(
                (a for a in snap.assets
                 if a.asset_type not in STRUCTURAL_TYPES
                 and a not in candidates),
                key=lambda a: (-(a.half_x * a.half_z), a.asset_id),
            )
            candidates.extend(extras)
        primary = candidates[0] if candidates else None
        secondary = None
        for c in candidates[1:]:
            if primary is not None and c.asset_id != primary.asset_id:
                secondary = c
                break
        return primary, secondary


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[CompositionEngine] = None
_lock = threading.Lock()


def get_composition_engine() -> CompositionEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = CompositionEngine()
    return _instance


def reset_composition_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
