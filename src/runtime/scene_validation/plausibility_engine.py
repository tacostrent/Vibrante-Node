"""
plausibility_engine.py — §53 Scene Reality Validation (Tier 14.3)
==================================================================
Rule 4 — Human Plausibility.

Simulates five simple human-usage scenarios and produces a
plausibility_score (0.0–1.0).  Score >= 0.90 → plausibility_valid = True.

Checks (equal weight):
    can_sit    — chair seat height near 0.45 m, accessible
    can_access — table has >= 0.5 m navigation clearance around it
    can_reach  — surface props at ty <= 2.0 m (arm reach)
    door_clear — doorways are not blocked by furniture within 0.8 m
    floor_space — estimated free floor fraction >= 30 %

Public API:
    PlausibilityResult
    PlausibilityEngine
    get_plausibility_engine()
    reset_plausibility_engine_for_tests()
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

CHAIR_SEAT_NOMINAL = 0.45   # m
CHAIR_SEAT_TOL     = 0.30   # ± m
TABLE_CLEARANCE    = 0.50   # m — around table for access
DOOR_CLEARANCE     = 0.80   # m — in front of doorway
MAX_REACH_HEIGHT   = 2.00   # m
PLAUSIBILITY_PASS  = 0.90   # threshold


def _is_type(name: str, *keywords: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in keywords)


def _dist_2d(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    dx = float(a.get("tx", 0)) - float(b.get("tx", 0))
    dz = float(a.get("tz", 0)) - float(b.get("tz", 0))
    return math.sqrt(dx * dx + dz * dz)


def _footprint_radius(t: Dict[str, Any], default: float = 0.25) -> float:
    hx = float(t.get("bbox_half_x", 0.0)) or default
    hz = float(t.get("bbox_half_z", 0.0)) or default
    return max(0.10, max(hx, hz))


@dataclass
class PlausibilityResult:
    plausibility_score: float = 0.0
    plausibility_valid: bool  = False

    can_sit:     float = 1.0
    can_access:  float = 1.0
    can_reach:   float = 1.0
    door_clear:  float = 1.0
    floor_space: float = 1.0

    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plausibility_score": round(self.plausibility_score, 4),
            "plausibility_valid": self.plausibility_valid,
            "can_sit":            round(self.can_sit, 4),
            "can_access":         round(self.can_access, 4),
            "can_reach":          round(self.can_reach, 4),
            "door_clear":         round(self.door_clear, 4),
            "floor_space":        round(self.floor_space, 4),
            "findings":           list(self.findings),
        }


class PlausibilityEngine:
    """Simulates human usage to derive a plausibility_score."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def evaluate(self, scene_layout: Dict[str, Any]) -> PlausibilityResult:
        """Compute plausibility score. Never raises."""
        try:
            return self._evaluate(scene_layout)
        except Exception:
            return PlausibilityResult()

    def _evaluate(self, scene: Dict[str, Any]) -> PlausibilityResult:
        transforms = scene.get("transforms") or []
        result = PlausibilityResult()

        if not transforms:
            result.plausibility_score = 0.0
            result.plausibility_valid = False
            result.findings.append("no transforms in scene")
            return result

        chairs  = [t for t in transforms if _is_type(t.get("asset_name", ""), "chair", "stool")]
        tables  = [t for t in transforms if _is_type(t.get("asset_name", ""), "table", "desk",
                                                      "workbench", "counter", "bar_counter")]
        doors   = [t for t in transforms if _is_type(t.get("asset_name", ""), "door", "doorway",
                                                      "archway", "entrance", "swing_door")]
        surface_props = [
            t for t in transforms
            if t.get("relationship") == "supports" and float(t.get("ty", 0)) > 0.3
        ]

        # --- Check 1: can_sit ---
        if chairs:
            # A chair at ty=0 has its base on the floor; the seat is ~0.45m up in local
            # geometry — this is the normal production placement. Accept both:
            #   - ty=0 (floor-based, geometry provides seat height) — VALID
            #   - ty near 0.45m (pivot at seat, e.g. Houdini-centered pivot) — VALID
            valid = sum(
                1 for c in chairs
                if (float(c.get("ty", 0)) <= CHAIR_SEAT_NOMINAL + CHAIR_SEAT_TOL)   # 0–0.75m
            )
            result.can_sit = valid / len(chairs)
            if result.can_sit < 1.0:
                bad = len(chairs) - valid
                result.findings.append(f"{bad} chair(s) placed above floor level (ty > 0.75m)")
        else:
            result.can_sit = 1.0

        # --- Check 2: can_access (table navigation clearance) ---
        if tables:
            non_chair_assets = [
                t for t in transforms
                if not _is_type(t.get("asset_name", ""), "chair", "stool")
                and t not in tables
                and t.get("relationship") != "supports"   # items ON table don't block access
            ]
            accessible = 0
            for table in tables:
                too_close = sum(
                    1 for obs in non_chair_assets
                    if _dist_2d(table, obs) < TABLE_CLEARANCE + _footprint_radius(obs)
                )
                if too_close == 0:
                    accessible += 1
            result.can_access = accessible / len(tables)
            if result.can_access < 0.8:
                result.findings.append(
                    f"only {accessible}/{len(tables)} tables have "
                    f"{TABLE_CLEARANCE}m navigation clearance"
                )
        else:
            result.can_access = 1.0

        # --- Check 3: can_reach (surface props within arm reach) ---
        if surface_props:
            reachable = sum(1 for p in surface_props if float(p.get("ty", 0)) <= MAX_REACH_HEIGHT)
            result.can_reach = reachable / len(surface_props)
            if result.can_reach < 1.0:
                out = len(surface_props) - reachable
                result.findings.append(f"{out} prop(s) above {MAX_REACH_HEIGHT}m arm reach")
        else:
            result.can_reach = 1.0

        # --- Check 4: door_clear (doorway not blocked by furniture) ---
        if doors:
            furniture = [
                t for t in transforms
                if _is_type(t.get("asset_name", ""), "table", "cabinet", "chest", "wardrobe",
                            "machine", "server", "rack")
            ]
            clear = 0
            for door in doors:
                blocked = sum(
                    1 for f in furniture
                    if _dist_2d(door, f) < DOOR_CLEARANCE + _footprint_radius(f)
                )
                if not blocked:
                    clear += 1
            result.door_clear = clear / len(doors)
            if result.door_clear < 1.0:
                num = len(doors) - clear
                result.findings.append(f"{num} doorway(s) blocked by furniture")
        else:
            result.door_clear = 1.0

        # --- Check 5: floor_space ---
        floor_items = [
            t for t in transforms
            if t.get("relationship") not in ("attached_to", "supports")
            and not _is_type(t.get("asset_name", ""), "poster", "painting", "banner",
                             "sign", "torch", "lantern")
        ]
        if floor_items:
            occupied = sum(math.pi * (_footprint_radius(t) ** 2) for t in floor_items)
            room_area = float(scene.get("room_area_m2", 100.0)) or 100.0
            free_frac = max(0.0, 1.0 - occupied / room_area)
            result.floor_space = min(1.0, free_frac / 0.30)  # 30 % free = score 1.0
            if result.floor_space < 0.5:
                result.findings.append(
                    f"floor too packed: ~{free_frac * 100:.0f}% estimated free "
                    f"(need >= 30%)"
                )
        else:
            result.floor_space = 1.0

        result.plausibility_score = (
            result.can_sit + result.can_access + result.can_reach
            + result.door_clear + result.floor_space
        ) / 5.0
        result.plausibility_valid = result.plausibility_score >= PLAUSIBILITY_PASS
        return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[PlausibilityEngine] = None
_lock = threading.Lock()


def get_plausibility_engine() -> PlausibilityEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = PlausibilityEngine()
    return _instance


def reset_plausibility_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
