"""
architectural_integrity_validator.py — §54 Reality Intelligence (Tier 15.0+)
=============================================================================
Architectural Integrity Rule. Walls, windows, doors, ceilings, floors,
columns and beams form one system.

    If a door exists  → a door opening must exist.
    If a window exists → a window opening must exist.
    No decorative fake doors. No decorative fake windows.

Additional checks:
    - doors/windows must lie in a wall plane (not free-standing in the room)
    - fireplaces must back onto a wall
    - assets must not poke through the room perimeter

Public API:
    IntegrityViolation
    ArchitecturalIntegrityResult
    ArchitecturalIntegrityValidator
    get_architectural_integrity_validator()
    reset_architectural_integrity_validator_for_tests()
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
    is_against_wall,
)

_WALL_PLANE_TOLERANCE = 0.30   # door/window centre must be this close to a wall plane


@dataclass
class IntegrityViolation:
    asset_id:       str
    asset_name:     str
    asset_type:     str
    violation_code: str
    severity:       str = "BLOCKING"
    detail:         str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":       self.asset_id,
            "asset_name":     self.asset_name,
            "asset_type":     self.asset_type,
            "violation_code": self.violation_code,
            "severity":       self.severity,
            "detail":         self.detail,
        }


@dataclass
class ArchitecturalIntegrityResult:
    violations: List[IntegrityViolation] = field(default_factory=list)
    door_count:    int = 0
    window_count:  int = 0
    opening_count: int = 0
    architecturally_valid: bool = True
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violations":            [v.to_dict() for v in self.violations],
            "door_count":            self.door_count,
            "window_count":          self.window_count,
            "opening_count":         self.opening_count,
            "architecturally_valid": self.architecturally_valid,
            "findings":              list(self.findings),
        }


class ArchitecturalIntegrityValidator:
    """Validates that architecture forms one coherent system. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def validate(self, scene_layout: Dict[str, Any]) -> ArchitecturalIntegrityResult:
        try:
            return self._validate(parse_scene(scene_layout))
        except Exception as exc:
            r = ArchitecturalIntegrityResult(architecturally_valid=False)
            r.findings.append(f"ArchitecturalIntegrityValidator internal error: {exc}")
            return r

    def validate_snapshot(self, snap: SceneSnapshot) -> ArchitecturalIntegrityResult:
        try:
            return self._validate(snap)
        except Exception as exc:
            r = ArchitecturalIntegrityResult(architecturally_valid=False)
            r.findings.append(f"ArchitecturalIntegrityValidator internal error: {exc}")
            return r

    # ------------------------------------------------------------------

    def _validate(self, snap: SceneSnapshot) -> ArchitecturalIntegrityResult:
        result = ArchitecturalIntegrityResult()
        result.opening_count = len(snap.openings)

        for asset in snap.assets:
            if asset.asset_type == "door":
                result.door_count += 1
                self._check_portal(snap, asset, "door", result)
            elif asset.asset_type == "window":
                result.window_count += 1
                self._check_portal(snap, asset, "window", result)
            elif asset.asset_type == "fireplace":
                if not is_against_wall(snap, asset):
                    result.violations.append(IntegrityViolation(
                        asset_id=asset.asset_id,
                        asset_name=asset.asset_name,
                        asset_type=asset.asset_type,
                        violation_code="FIREPLACE_OFF_WALL",
                        detail=(
                            f"{asset.asset_name or asset.asset_id} is free-standing — "
                            "a fireplace requires a wall (masonry backing)"
                        ),
                    ))
            elif asset.asset_type not in STRUCTURAL_TYPES:
                self._check_perimeter(snap, asset, result)

        result.architecturally_valid = len(result.violations) == 0
        for v in result.violations:
            result.findings.append(f"{v.violation_code}: {v.detail}")
        return result

    def _check_portal(self, snap: SceneSnapshot, asset: SceneAsset,
                      kind: str, result: ArchitecturalIntegrityResult) -> None:
        """A door/window must correspond to a real wall opening."""
        # 1. In a wall plane at all?
        in_plane = (
            abs(abs(asset.tx) - snap.wall_x) <= _WALL_PLANE_TOLERANCE
            or abs(abs(asset.tz) - snap.wall_z) <= _WALL_PLANE_TOLERANCE
        )
        if not in_plane:
            result.violations.append(IntegrityViolation(
                asset_id=asset.asset_id,
                asset_name=asset.asset_name,
                asset_type=asset.asset_type,
                violation_code=f"FAKE_{kind.upper()}",
                detail=(
                    f"{asset.asset_name or asset.asset_id} is a decorative fake "
                    f"{kind} — it sits at ({asset.tx:.2f}, {asset.tz:.2f}), not in "
                    "any wall plane. Create a real wall opening or remove it."
                ),
            ))
            return

        # 2. When the scene carries an explicit opening list, the portal must
        #    match one of the openings.
        if snap.openings:
            for opening in snap.openings:
                okind = str(opening.get("kind") or opening.get("type") or "").lower()
                if kind not in okind and okind not in ("opening", "archway"):
                    continue
                ox = float(opening.get("tx", opening.get("x", 0.0)) or 0.0)
                oz = float(opening.get("tz", opening.get("z", 0.0)) or 0.0)
                if abs(ox - asset.tx) <= 1.0 and abs(oz - asset.tz) <= 1.0:
                    return
            result.violations.append(IntegrityViolation(
                asset_id=asset.asset_id,
                asset_name=asset.asset_name,
                asset_type=asset.asset_type,
                violation_code=f"MISSING_{kind.upper()}_OPENING",
                detail=(
                    f"{asset.asset_name or asset.asset_id} has no matching "
                    f"{kind} opening in the wall — if a {kind} exists, create a "
                    f"{kind} opening (§54 Architectural Integrity)"
                ),
            ))

    def _check_perimeter(self, snap: SceneSnapshot, asset: SceneAsset,
                         result: ArchitecturalIntegrityResult) -> None:
        """Non-structural assets must stay inside the room shell."""
        over_x = abs(asset.tx) + asset.half_x - snap.wall_x
        over_z = abs(asset.tz) + asset.half_z - snap.wall_z
        overshoot = max(over_x, over_z)
        if overshoot > 0.05:
            result.violations.append(IntegrityViolation(
                asset_id=asset.asset_id,
                asset_name=asset.asset_name,
                asset_type=asset.asset_type,
                violation_code="WALL_INTERSECTION",
                detail=(
                    f"{asset.asset_name or asset.asset_id} intersects the room "
                    f"perimeter by {overshoot:.2f} m — push it inside the walls"
                ),
            ))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[ArchitecturalIntegrityValidator] = None
_lock = threading.Lock()


def get_architectural_integrity_validator() -> ArchitecturalIntegrityValidator:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ArchitecturalIntegrityValidator()
    return _instance


def reset_architectural_integrity_validator_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
