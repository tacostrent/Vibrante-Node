"""
floating_object_detector.py — §54 Reality Intelligence (Tier 15.0+)
====================================================================
No Floating Objects Rule. Any asset whose bottom is more than 0.10 m above
the floor must pass raycast_down(): support geometry must exist directly
beneath it. If no support is detected the asset FAILS and a relocation is
suggested automatically.

Exemptions (validated by other §54 rules instead):
    - structural types (beam, column, wall, floor, ceiling, door, window)
    - wall-mounted assets (posters, sconces, mounted lanterns)
    - ceiling-mounted assets (hanging lights)

Public API:
    FloatingViolation
    FloatingObjectResult
    FloatingObjectDetector
    get_floating_object_detector()
    reset_floating_object_detector_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.reality.reality_scene_model import (
    FLOAT_TOLERANCE,
    STRUCTURAL_TYPES,
    SceneAsset,
    SceneSnapshot,
    parse_scene,
    raycast_down,
    is_wall_mounted,
    is_ceiling_mounted,
)


@dataclass
class FloatingViolation:
    asset_id:     str
    asset_name:   str
    asset_type:   str
    ty:           float
    bottom_y:     float
    suggested_ty: float
    support_id:   str = ""
    violation_code: str = "FLOATING_OBJECT"
    severity:       str = "BLOCKING"
    detail:         str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":       self.asset_id,
            "asset_name":     self.asset_name,
            "asset_type":     self.asset_type,
            "ty":             round(self.ty, 4),
            "bottom_y":       round(self.bottom_y, 4),
            "suggested_ty":   round(self.suggested_ty, 4),
            "support_id":     self.support_id,
            "violation_code": self.violation_code,
            "severity":       self.severity,
            "detail":         self.detail,
        }


@dataclass
class FloatingObjectResult:
    violations:  List[FloatingViolation] = field(default_factory=list)
    checked:     int = 0
    exempt:      int = 0
    supported:   int = 0
    ok:          bool = True
    findings:    List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violations": [v.to_dict() for v in self.violations],
            "checked":    self.checked,
            "exempt":     self.exempt,
            "supported":  self.supported,
            "ok":         self.ok,
            "findings":   list(self.findings),
        }


class FloatingObjectDetector:
    """Detects unsupported floating assets and suggests relocations. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def detect(self, scene_layout: Dict[str, Any]) -> FloatingObjectResult:
        try:
            return self._detect(parse_scene(scene_layout))
        except Exception as exc:
            r = FloatingObjectResult(ok=False)
            r.findings.append(f"FloatingObjectDetector internal error: {exc}")
            return r

    def detect_snapshot(self, snap: SceneSnapshot) -> FloatingObjectResult:
        try:
            return self._detect(snap)
        except Exception as exc:
            r = FloatingObjectResult(ok=False)
            r.findings.append(f"FloatingObjectDetector internal error: {exc}")
            return r

    # ------------------------------------------------------------------

    def _detect(self, snap: SceneSnapshot) -> FloatingObjectResult:
        result = FloatingObjectResult()
        floor = snap.floor_height

        for asset in snap.assets:
            result.checked += 1

            if self._is_exempt(snap, asset):
                result.exempt += 1
                continue

            # On (or sunk into) the floor — fine.
            if asset.bottom_y <= floor + FLOAT_TOLERANCE:
                result.supported += 1
                continue

            support = raycast_down(snap, asset)
            if support is not None:
                result.supported += 1
                continue

            # FAIL — suggest a relocation: drop onto the highest surface
            # below the asset's footprint, else onto the floor.
            suggested_ty, support_id = self._relocation(snap, asset, floor)
            result.violations.append(FloatingViolation(
                asset_id=asset.asset_id,
                asset_name=asset.asset_name,
                asset_type=asset.asset_type,
                ty=asset.ty,
                bottom_y=asset.bottom_y,
                suggested_ty=suggested_ty,
                support_id=support_id,
                detail=(
                    f"{asset.asset_name or asset.asset_id} floats at "
                    f"ty={asset.ty:.2f} (bottom {asset.bottom_y:.2f} > floor+"
                    f"{FLOAT_TOLERANCE}) with no support geometry beneath — "
                    f"relocate to ty={suggested_ty:.2f}"
                ),
            ))

        result.ok = len(result.violations) == 0
        for v in result.violations:
            result.findings.append(f"FLOATING_OBJECT: {v.detail}")
        return result

    def _is_exempt(self, snap: SceneSnapshot, asset: SceneAsset) -> bool:
        if asset.asset_type in STRUCTURAL_TYPES:
            return True
        if asset.relationship in ("attached_to", "mounted_on", "wall_mount",
                                  "hanging_from"):
            return True
        if is_wall_mounted(snap, asset) or is_ceiling_mounted(snap, asset):
            return True
        return False

    def _relocation(self, snap: SceneSnapshot, asset: SceneAsset,
                    floor: float):
        """Best landing surface below the asset, else the floor."""
        best_top = floor
        best_id = ""
        for other in snap.assets:
            if other is asset or other.asset_id == asset.asset_id:
                continue
            if other.asset_type in ("poster", "rug"):
                continue
            if (abs(asset.tx - other.tx) <= other.half_x
                    and abs(asset.tz - other.tz) <= other.half_z
                    and other.top_y < asset.bottom_y
                    and other.top_y > best_top):
                best_top = other.top_y
                best_id = other.asset_id
        return best_top + asset.half_y, best_id


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[FloatingObjectDetector] = None
_lock = threading.Lock()


def get_floating_object_detector() -> FloatingObjectDetector:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = FloatingObjectDetector()
    return _instance


def reset_floating_object_detector_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
