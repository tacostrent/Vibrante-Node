"""
correction_pass_engine.py — §54 Reality Intelligence (Tier 15.0+)
==================================================================
Relationship Correction Pass. After layout, fix:

    floating props            → drop onto support or floor
    unsupported assets        → relocate next to a valid support
    chairs not facing tables  → rotate to face their anchor
    objects intersecting walls→ push inside the room
    isolated assets           → move into the nearest functional zone

This module PLANS the corrections deterministically (op dicts). The actual
Houdini geometry mutation is performed by CorrectionApplier — geometry, not
metadata, is what gets fixed.

Public API:
    CorrectionOp
    CorrectionPlan
    RealityCorrectionPass
    get_reality_correction_pass()
    reset_reality_correction_pass_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.reality.reality_scene_model import (
    SceneAsset,
    SceneSnapshot,
    parse_scene,
    horizontal_distance,
    facing_ry_towards,
)
from src.runtime.reality.floating_object_detector import get_floating_object_detector
from src.runtime.reality.functional_zone_builder import get_functional_zone_builder

_FACING_TOLERANCE = 30.0   # degrees — chair may deviate this much from its anchor
_CHAIR_ANCHOR_TYPES = ("table", "desk", "bar", "fireplace")


@dataclass
class CorrectionOp:
    asset_id:   str
    asset_name: str
    op:         str                      # always "set_parms"
    parms:      Dict[str, float] = field(default_factory=dict)
    reason:     str = ""
    category:   str = ""                 # floating | facing | wall_intersection | isolation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":   self.asset_id,
            "asset_name": self.asset_name,
            "op":         self.op,
            "parms":      {k: round(v, 4) for k, v in self.parms.items()},
            "reason":     self.reason,
            "category":   self.category,
        }


@dataclass
class CorrectionPlan:
    ops: List[CorrectionOp] = field(default_factory=list)
    floating_fixes:     int = 0
    facing_fixes:       int = 0
    wall_fixes:         int = 0
    isolation_fixes:    int = 0
    clean:              bool = True
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ops":             [o.to_dict() for o in self.ops],
            "floating_fixes":  self.floating_fixes,
            "facing_fixes":    self.facing_fixes,
            "wall_fixes":      self.wall_fixes,
            "isolation_fixes": self.isolation_fixes,
            "clean":           self.clean,
            "findings":        list(self.findings),
        }


class RealityCorrectionPass:
    """Plans deterministic geometry corrections for a scene. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_correction_plan(self, scene_layout: Dict[str, Any]) -> CorrectionPlan:
        try:
            return self._build(scene_layout, parse_scene(scene_layout))
        except Exception as exc:
            plan = CorrectionPlan(clean=False)
            plan.findings.append(f"RealityCorrectionPass internal error: {exc}")
            return plan

    # ------------------------------------------------------------------

    def _build(self, scene_layout: Dict[str, Any],
               snap: SceneSnapshot) -> CorrectionPlan:
        plan = CorrectionPlan()

        self._fix_floating(scene_layout, snap, plan)
        self._fix_chair_facing(snap, plan)
        self._fix_wall_intersections(snap, plan)
        self._fix_isolation(scene_layout, snap, plan)

        plan.clean = len(plan.ops) == 0
        for op in plan.ops:
            plan.findings.append(f"CORRECTION[{op.category}]: {op.reason}")
        return plan

    def _fix_floating(self, scene_layout: Dict[str, Any],
                      snap: SceneSnapshot, plan: CorrectionPlan) -> None:
        floating = get_floating_object_detector().detect_snapshot(snap)
        for v in floating.violations:
            plan.ops.append(CorrectionOp(
                asset_id=v.asset_id,
                asset_name=v.asset_name,
                op="set_parms",
                parms={"ty": v.suggested_ty},
                category="floating",
                reason=(
                    f"{v.asset_name or v.asset_id}: no support beneath at "
                    f"ty={v.ty:.2f} — drop to ty={v.suggested_ty:.2f}"
                    + (f" (onto {v.support_id})" if v.support_id else " (onto floor)")
                ),
            ))
            plan.floating_fixes += 1

    def _fix_chair_facing(self, snap: SceneSnapshot,
                          plan: CorrectionPlan) -> None:
        anchors = [a for a in snap.assets if a.asset_type in _CHAIR_ANCHOR_TYPES]
        for chair in snap.assets:
            if chair.asset_type not in ("chair", "stool"):
                continue
            anchor: Optional[SceneAsset] = None
            anchor_d = 2.0
            for a in anchors:
                d = horizontal_distance(chair, a)
                if d < anchor_d:
                    anchor, anchor_d = a, d
            if anchor is None:
                continue
            desired = facing_ry_towards(chair.tx, chair.tz, anchor.tx, anchor.tz)
            deviation = abs((chair.ry - desired + 180.0) % 360.0 - 180.0)
            if deviation > _FACING_TOLERANCE:
                plan.ops.append(CorrectionOp(
                    asset_id=chair.asset_id,
                    asset_name=chair.asset_name,
                    op="set_parms",
                    parms={"ry": round(desired, 2)},
                    category="facing",
                    reason=(
                        f"{chair.asset_name or chair.asset_id} faces away from "
                        f"{anchor.asset_name or anchor.asset_id} "
                        f"(off by {deviation:.0f}°) — rotate to ry={desired:.0f}"
                    ),
                ))
                plan.facing_fixes += 1

    def _fix_wall_intersections(self, snap: SceneSnapshot,
                                plan: CorrectionPlan) -> None:
        for asset in snap.assets:
            if asset.asset_type in ("wall", "door", "window", "beam",
                                    "floor", "ceiling", "poster"):
                continue
            parms: Dict[str, float] = {}
            limit_x = snap.wall_x - asset.half_x
            limit_z = snap.wall_z - asset.half_z
            if abs(asset.tx) > limit_x + 0.05 and limit_x > 0:
                parms["tx"] = limit_x if asset.tx > 0 else -limit_x
            if abs(asset.tz) > limit_z + 0.05 and limit_z > 0:
                parms["tz"] = limit_z if asset.tz > 0 else -limit_z
            if parms:
                plan.ops.append(CorrectionOp(
                    asset_id=asset.asset_id,
                    asset_name=asset.asset_name,
                    op="set_parms",
                    parms=parms,
                    category="wall_intersection",
                    reason=(
                        f"{asset.asset_name or asset.asset_id} intersects the room "
                        "perimeter — push inside the walls"
                    ),
                ))
                plan.wall_fixes += 1

    def _fix_isolation(self, scene_layout: Dict[str, Any],
                       snap: SceneSnapshot, plan: CorrectionPlan) -> None:
        zone_plan = get_functional_zone_builder().build_from_snapshot(snap)
        if not zone_plan.zones:
            return
        for orphan in zone_plan.orphans:
            asset = snap.find(str(orphan.get("asset_id", "")))
            if asset is None:
                continue
            # Move the orphan to the edge of the nearest zone that accepts it,
            # else to the edge of the nearest zone of any type.
            target = None
            target_d = float("inf")
            for zone in zone_plan.zones:
                if zone.zone_type in ("structure", "wall_decor"):
                    continue
                d = ((asset.tx - zone.center_x) ** 2
                     + (asset.tz - zone.center_z) ** 2) ** 0.5
                if d < target_d:
                    target, target_d = zone, d
            if target is None or target_d <= target.radius:
                continue
            # Place on the zone boundary along the approach direction.
            scale = (target.radius * 0.8) / target_d if target_d > 0 else 0.0
            new_x = target.center_x + (asset.tx - target.center_x) * scale
            new_z = target.center_z + (asset.tz - target.center_z) * scale
            plan.ops.append(CorrectionOp(
                asset_id=asset.asset_id,
                asset_name=asset.asset_name,
                op="set_parms",
                parms={"tx": round(new_x, 4), "tz": round(new_z, 4)},
                category="isolation",
                reason=(
                    f"{asset.asset_name or asset.asset_id} is isolated "
                    f"({target_d:.1f} m from any zone) — move into the "
                    f"{target.zone_type} zone"
                ),
            ))
            plan.isolation_fixes += 1


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RealityCorrectionPass] = None
_lock = threading.Lock()


def get_reality_correction_pass() -> RealityCorrectionPass:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RealityCorrectionPass()
    return _instance


def reset_reality_correction_pass_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
