"""
support_rule_engine.py — §54 Reality Intelligence (Tier 15.0+)
===============================================================
Support Rules: every asset type that requires a physical or functional
support must have one in the scene, or the placement is rejected.

Rule table (§54):
    bottle    → table | shelf | bar
    cup       → table | shelf
    plate     → table
    lantern   → table | wall | ceiling
    chair     → table | desk | fireplace | bar
    stool     → bar
    fireplace → wall
    window    → wall opening
    door      → wall opening

If support is missing: reject placement (BLOCKING).

Public API:
    SupportCheck
    SupportRuleResult
    SupportRuleEngine
    get_support_rule_engine()
    reset_support_rule_engine_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.reality.reality_scene_model import (
    SceneAsset,
    SceneSnapshot,
    parse_scene,
    raycast_down,
    is_against_wall,
    is_wall_mounted,
    is_ceiling_mounted,
    horizontal_distance,
)

# asset_type → allowed support kinds
SUPPORT_REQUIREMENTS: Dict[str, frozenset] = {
    "bottle":    frozenset({"table", "shelf", "bar"}),
    "cup":       frozenset({"table", "shelf"}),
    "plate":     frozenset({"table"}),
    "lantern":   frozenset({"table", "wall", "ceiling"}),
    "chair":     frozenset({"table", "desk", "fireplace", "bar"}),
    "stool":     frozenset({"bar"}),
    "fireplace": frozenset({"wall"}),
    "window":    frozenset({"wall_opening"}),
    "door":      frozenset({"wall_opening"}),
}

# Max horizontal distance for a "functional" support (chair → table, etc.)
_FUNCTIONAL_RADIUS = 2.0   # metres


@dataclass
class SupportCheck:
    asset_id:     str
    asset_name:   str
    asset_type:   str
    required:     List[str] = field(default_factory=list)
    satisfied_by: str = ""
    support_kind: str = ""
    ok:           bool = False
    severity:     str = "BLOCKING"
    detail:       str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":     self.asset_id,
            "asset_name":   self.asset_name,
            "asset_type":   self.asset_type,
            "required":     list(self.required),
            "satisfied_by": self.satisfied_by,
            "support_kind": self.support_kind,
            "ok":           self.ok,
            "severity":     self.severity,
            "detail":       self.detail,
        }


@dataclass
class SupportRuleResult:
    checks:     List[SupportCheck] = field(default_factory=list)
    violations: List[SupportCheck] = field(default_factory=list)
    checked:    int = 0
    ok:         bool = True
    findings:   List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checks":     [c.to_dict() for c in self.checks],
            "violations": [v.to_dict() for v in self.violations],
            "checked":    self.checked,
            "ok":         self.ok,
            "findings":   list(self.findings),
        }


class SupportRuleEngine:
    """Enforces the §54 support requirement table. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def check_scene(self, scene_layout: Dict[str, Any]) -> SupportRuleResult:
        try:
            return self._check(parse_scene(scene_layout))
        except Exception as exc:
            r = SupportRuleResult(ok=False)
            r.findings.append(f"SupportRuleEngine internal error: {exc}")
            return r

    def check_snapshot(self, snap: SceneSnapshot) -> SupportRuleResult:
        try:
            return self._check(snap)
        except Exception as exc:
            r = SupportRuleResult(ok=False)
            r.findings.append(f"SupportRuleEngine internal error: {exc}")
            return r

    # ------------------------------------------------------------------

    def _check(self, snap: SceneSnapshot) -> SupportRuleResult:
        result = SupportRuleResult()
        for asset in snap.assets:
            required = SUPPORT_REQUIREMENTS.get(asset.asset_type)
            if not required:
                continue
            check = self._check_asset(snap, asset, sorted(required))
            result.checks.append(check)
            result.checked += 1
            if not check.ok:
                result.violations.append(check)
                result.findings.append(
                    f"SUPPORT_MISSING: {check.detail}"
                )
        result.ok = len(result.violations) == 0
        return result

    def _check_asset(self, snap: SceneSnapshot, asset: SceneAsset,
                     required: List[str]) -> SupportCheck:
        check = SupportCheck(
            asset_id=asset.asset_id,
            asset_name=asset.asset_name,
            asset_type=asset.asset_type,
            required=required,
        )

        for kind in required:
            host = self._find_support(snap, asset, kind)
            if host is not None:
                check.ok = True
                check.support_kind = kind
                check.satisfied_by = host if isinstance(host, str) else host.asset_id
                return check

        check.detail = (
            f"{asset.asset_name or asset.asset_id} ({asset.asset_type}) requires "
            f"{' or '.join(required)} but no valid support was found — reject placement"
        )
        return check

    def _find_support(self, snap: SceneSnapshot, asset: SceneAsset, kind: str):
        """Return a supporting SceneAsset, the string 'wall'/'ceiling'/'wall_opening',
        or None when the requirement is not met."""
        if kind == "wall":
            if asset.asset_type == "fireplace":
                return "wall" if is_against_wall(snap, asset) else None
            return "wall" if is_wall_mounted(snap, asset) else None

        if kind == "ceiling":
            return "ceiling" if is_ceiling_mounted(snap, asset) else None

        if kind == "wall_opening":
            return self._find_wall_opening(snap, asset)

        # Furniture-kind support (table/desk/bar/shelf/fireplace host asset)
        hosts = snap.assets_of_type(kind)
        if not hosts:
            return None

        # 1. Explicit parent relationship
        if asset.parent_id:
            for h in hosts:
                if h.asset_id == asset.parent_id:
                    return h

        # 2. Resting directly on the host (small props on a surface)
        support = raycast_down(snap, asset)
        if support is not None and support.asset_type == kind:
            return support

        # 3. Functional proximity (chair near table, stool near bar)
        if asset.asset_type in ("chair", "stool", "bench"):
            nearest = None
            nearest_d = _FUNCTIONAL_RADIUS
            for h in hosts:
                d = horizontal_distance(asset, h)
                if d <= nearest_d:
                    nearest, nearest_d = h, d
            return nearest

        return None

    def _find_wall_opening(self, snap: SceneSnapshot, asset: SceneAsset):
        """Doors/windows need a real wall opening — no decorative fakes (§54)."""
        # Explicit opening list from the shell/realization pipeline
        for opening in snap.openings:
            kind = str(opening.get("kind") or opening.get("type") or "").lower()
            if asset.asset_type in kind or kind in ("opening", "archway"):
                ox = float(opening.get("tx", opening.get("x", 0.0)) or 0.0)
                oz = float(opening.get("tz", opening.get("z", 0.0)) or 0.0)
                if abs(ox - asset.tx) <= 1.0 and abs(oz - asset.tz) <= 1.0:
                    return "wall_opening"
        # Fallback: the asset must at least sit inside a wall plane
        if snap.openings:
            return None
        return "wall_opening" if is_against_wall(snap, asset, proximity=0.30) else None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[SupportRuleEngine] = None
_lock = threading.Lock()


def get_support_rule_engine() -> SupportRuleEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SupportRuleEngine()
    return _instance


def reset_support_rule_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
