"""
anchor_layout_engine.py — §46 Semantic Furniture Layout Engine
==============================================================
Places anchor assets first as scene focal points.
Anchors (tables, machines, fireplaces) receive priority zones and
hero status before any other asset is placed.

Public API:
    AnchorPlacement
    AnchorLayoutResult
    AnchorLayoutEngine
    get_anchor_layout_engine()
    reset_anchor_layout_engine_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout.affordance_engine import get_affordance_engine, ANCHOR_TYPES


# Environment half-dimensions (half_width, half_depth) in meters.
# Used to scale zone positions and clamp overflow so no anchor lands outside the room.
_ENV_HALF_DIMS: Dict[str, tuple] = {
    "western_room":      (5.0,  6.0),
    "saloon":            (7.0,  9.0),
    "living_room":       (5.0,  6.0),
    "office":            (5.0,  6.0),
    "hotel_lobby":       (7.5, 10.0),
    "restaurant":        (7.5, 10.0),
    "library":           (7.5, 10.0),
    "workshop":          (4.0,  5.0),
    "industrial_hangar": (15.0, 20.0),
    "warehouse":         (10.0, 15.0),
    "abandoned_factory": (10.0, 15.0),
    "shipyard":          (12.5, 20.0),
    "robotics_lab":      (7.5, 10.0),
    "control_room":      (5.0,  6.0),
    "medical_lab":       (5.0,  7.5),
    "research_lab":      (5.0,  7.5),
    "sci_fi_corridor":   (2.0, 10.0),
    "space_station":     (5.0,  7.5),
    "castle_hall":       (10.0, 15.0),
    "dungeon":           (4.0,  5.0),
    "forest":            (15.0, 15.0),
    "desert":            (25.0, 25.0),
    "city_street":       (10.0, 20.0),
    "survival_camp":     (7.5, 10.0),
    "military_base":     (10.0, 15.0),
}
_DEFAULT_HALF_DIMS: tuple = (5.0, 6.0)

# Priority score per anchor type (higher = placed first)
_ANCHOR_PRIORITY: Dict[str, int] = {
    "table":         10,
    "throne":        10,
    "altar":          9,
    "workbench":      9,
    "bar_counter":    9,
    "machine":        8,
    "large_machine":  8,
    "console":        8,
    "reactor":        8,
    "fireplace":      7,
    "campfire":       7,
    "piano":          6,
    "desk":           6,
    "bed":            5,
    "sofa":           5,
}
_DEFAULT_PRIORITY = 4



@dataclass
class AnchorPlacement:
    anchor_id: str
    anchor_name: str
    anchor_type: str
    zone: str
    position: List[float]
    is_hero: bool = False
    priority: int = 0

    def to_dict(self) -> dict:
        return {
            "anchor_id":   self.anchor_id,
            "anchor_name": self.anchor_name,
            "anchor_type": self.anchor_type,
            "zone":        self.zone,
            "position":    [round(v, 3) for v in self.position],
            "is_hero":     self.is_hero,
            "priority":    self.priority,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AnchorPlacement":
        return cls(
            anchor_id=d.get("anchor_id", ""),
            anchor_name=d.get("anchor_name", ""),
            anchor_type=d.get("anchor_type", ""),
            zone=d.get("zone", "hero_zone"),
            position=list(d.get("position", [0.0, 0.0, 0.0])),
            is_hero=bool(d.get("is_hero", False)),
            priority=int(d.get("priority", 0)),
        )


@dataclass
class AnchorLayoutResult:
    placements: List[AnchorPlacement] = field(default_factory=list)
    hero_anchor: Optional[AnchorPlacement] = None
    ok: bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "placements":  [p.to_dict() for p in self.placements],
            "hero_anchor": self.hero_anchor.to_dict() if self.hero_anchor else None,
            "ok":          self.ok,
            "errors":      list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AnchorLayoutResult":
        placements = [AnchorPlacement.from_dict(p) for p in d.get("placements", [])]
        hero_d = d.get("hero_anchor")
        hero = AnchorPlacement.from_dict(hero_d) if hero_d else None
        return cls(
            placements=placements,
            hero_anchor=hero,
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors", [])),
        )


class AnchorLayoutEngine:
    """Identifies anchor assets and assigns them to primary zones."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def place_anchors(
        self,
        assets: List[Dict[str, Any]],
        environment: str = "",
    ) -> AnchorLayoutResult:
        """
        Identify anchor assets and assign zones.
        Returns placements sorted priority-descending. Never raises.
        """
        try:
            return self._place(assets, environment)
        except Exception as exc:
            return AnchorLayoutResult(
                ok=False,
                errors=[f"AnchorLayoutEngine.place_anchors failed: {exc}"],
            )

    def _place(
        self,
        assets: List[Dict[str, Any]],
        environment: str,
    ) -> AnchorLayoutResult:
        eng = get_affordance_engine()
        anchors: List[AnchorPlacement] = []

        for asset in assets:
            a_type = eng.infer_type(asset)
            if a_type not in ANCHOR_TYPES:
                continue
            priority = _ANCHOR_PRIORITY.get(a_type, _DEFAULT_PRIORITY)
            anchors.append(AnchorPlacement(
                anchor_id=str(asset.get("asset_id") or asset.get("name") or a_type),
                anchor_name=str(asset.get("name") or asset.get("asset_id") or a_type),
                anchor_type=a_type,
                zone="hero_zone",
                position=[0.0, 0.0, 0.0],
                is_hero=False,
                priority=priority,
            ))

        if not anchors:
            return AnchorLayoutResult(placements=[], hero_anchor=None)

        anchors.sort(key=lambda a: a.priority, reverse=True)

        # Room half-dimensions for this environment (clamp positions inside room)
        hw, hd = _ENV_HALF_DIMS.get(environment, _DEFAULT_HALF_DIMS)

        # Zone base positions scaled to room dimensions
        zone_positions = {
            "hero_zone":       [0.0,        0.0, 0.0],
            "support_zone":    [hw * 0.50,  0.0, 0.0],
            "midground":       [0.0,        0.0, hd * 0.33],
            "background_zone": [0.0,        0.0, hd * 0.55],
        }
        # Spread step: at most 40% of half-width so assets stay well inside walls
        spread_step = min(hw * 0.40, 2.0)
        # Maximum X offset (leave 0.5 m clearance from wall)
        max_x = hw - 0.5

        # Hero anchor gets centre
        hero = anchors[0]
        hero.is_hero = True
        hero.zone = "hero_zone"
        hero.position = list(zone_positions["hero_zone"])

        # Secondary anchors spread into other zones, clamped to room bounds
        fallback_zones = ["support_zone", "midground", "background_zone"]
        for i, anchor in enumerate(anchors[1:], 0):
            zone = fallback_zones[i % len(fallback_zones)]
            anchor.zone = zone
            base = list(zone_positions.get(zone, [0.0, 0.0, 0.0]))
            spread = (i // len(fallback_zones)) * spread_step
            anchor.position = [min(base[0] + spread, max_x), base[1], base[2]]

        return AnchorLayoutResult(placements=anchors, hero_anchor=hero)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[AnchorLayoutEngine] = None
_lock = threading.Lock()


def get_anchor_layout_engine() -> AnchorLayoutEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = AnchorLayoutEngine()
    return _instance


def reset_anchor_layout_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
