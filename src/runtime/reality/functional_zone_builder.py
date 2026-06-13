"""
functional_zone_builder.py — §54 Reality Intelligence (Tier 15.0+)
===================================================================
Functional Zone System. Before placing any asset, build functional zones;
every asset must belong to a zone. No orphan assets allowed.

Built-in zone types:
    dining   — table + chairs + cups + bottles + plates
    fireplace— fireplace + chairs + lantern + small table
    storage  — crates + barrels + shelves
    sleeping — bed + side table + lamp
    work     — desk + chair + books + tools
    bar      — bar counter + stools + bottles + glasses
    wall_decor — wall-mounted props (posters, paintings, signs)
    structure  — architectural elements (walls, beams, columns, doors, windows)

Public API:
    FunctionalZone
    FunctionalZonePlan
    FunctionalZoneBuilder
    get_functional_zone_builder()
    reset_functional_zone_builder_for_tests()
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
    horizontal_distance,
    is_wall_mounted,
    is_ceiling_mounted,
)

# zone_type → (anchor types, member types, gather radius in metres)
ZONE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "dining":    {"anchors": ["table"],
                  "members": ["chair", "bench", "cup", "bottle", "plate",
                              "lantern", "book", "rug"],
                  "radius": 3.0},
    "fireplace": {"anchors": ["fireplace"],
                  "members": ["chair", "bench", "lantern", "table", "rug",
                              "poster", "tool"],
                  "radius": 3.5},
    "bar":       {"anchors": ["bar"],
                  "members": ["stool", "bottle", "cup", "lantern"],
                  "radius": 3.0},
    "work":      {"anchors": ["desk", "machine"],
                  "members": ["chair", "stool", "book", "tool", "lamp",
                              "lantern", "bucket"],
                  "radius": 3.0},
    "sleeping":  {"anchors": ["bed"],
                  "members": ["table", "lamp", "lantern", "book", "pillow", "rug"],
                  "radius": 2.5},
    "storage":   {"anchors": ["crate", "barrel", "shelf"],
                  "members": ["crate", "barrel", "bucket", "shelf", "rope",
                              "hay", "tool", "book", "bottle"],
                  "radius": 3.0},
}

_ZONE_PRIORITY = ["dining", "fireplace", "bar", "work", "sleeping", "storage"]


@dataclass
class FunctionalZone:
    zone_id:    str
    zone_type:  str
    anchor_id:  str = ""
    anchor_name:str = ""
    center_x:   float = 0.0
    center_z:   float = 0.0
    radius:     float = 3.0
    member_ids: List[str] = field(default_factory=list)

    @property
    def asset_count(self) -> int:
        return len(self.member_ids) + (1 if self.anchor_id else 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id":     self.zone_id,
            "zone_type":   self.zone_type,
            "anchor_id":   self.anchor_id,
            "anchor_name": self.anchor_name,
            "center_x":    round(self.center_x, 4),
            "center_z":    round(self.center_z, 4),
            "radius":      self.radius,
            "member_ids":  list(self.member_ids),
            "asset_count": self.asset_count,
        }


@dataclass
class FunctionalZonePlan:
    environment: str = ""
    zones:       List[FunctionalZone] = field(default_factory=list)
    orphans:     List[Dict[str, Any]] = field(default_factory=list)
    assigned_count: int = 0
    orphan_count:   int = 0
    no_orphans:     bool = True
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":    self.environment,
            "zones":          [z.to_dict() for z in self.zones],
            "orphans":        list(self.orphans),
            "assigned_count": self.assigned_count,
            "orphan_count":   self.orphan_count,
            "no_orphans":     self.no_orphans,
            "findings":       list(self.findings),
        }


class FunctionalZoneBuilder:
    """Builds functional zones from anchors and assigns every asset. Never raises."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build_zones(self, scene_layout: Dict[str, Any]) -> FunctionalZonePlan:
        try:
            return self._build(parse_scene(scene_layout))
        except Exception as exc:
            plan = FunctionalZonePlan(no_orphans=False)
            plan.findings.append(f"FunctionalZoneBuilder internal error: {exc}")
            return plan

    def build_from_snapshot(self, snap: SceneSnapshot) -> FunctionalZonePlan:
        try:
            return self._build(snap)
        except Exception as exc:
            plan = FunctionalZonePlan(no_orphans=False)
            plan.findings.append(f"FunctionalZoneBuilder internal error: {exc}")
            return plan

    # ------------------------------------------------------------------

    def _build(self, snap: SceneSnapshot) -> FunctionalZonePlan:
        plan = FunctionalZonePlan(environment=snap.environment)
        assigned: set = set()

        # --- 1. Create zones from anchors, in priority order -------------
        zones: List[FunctionalZone] = []
        counter: Dict[str, int] = {}
        for zone_type in _ZONE_PRIORITY:
            definition = ZONE_DEFINITIONS[zone_type]
            for anchor_type in definition["anchors"]:
                for anchor in snap.assets_of_type(anchor_type):
                    if anchor.asset_id in assigned:
                        continue
                    # Storage anchors cluster: only the first nearby anchor
                    # founds the zone; the rest join as members below.
                    if zone_type == "storage" and any(
                        z.zone_type == "storage"
                        and abs(z.center_x - anchor.tx) + abs(z.center_z - anchor.tz)
                        <= definition["radius"] * 2
                        for z in zones
                    ):
                        continue
                    counter[zone_type] = counter.get(zone_type, 0) + 1
                    zones.append(FunctionalZone(
                        zone_id=f"{zone_type}_zone_{counter[zone_type]}",
                        zone_type=zone_type,
                        anchor_id=anchor.asset_id,
                        anchor_name=anchor.asset_name,
                        center_x=anchor.tx,
                        center_z=anchor.tz,
                        radius=float(definition["radius"]),
                    ))
                    assigned.add(anchor.asset_id)

        # --- 2. Assign members to the nearest compatible zone -------------
        for asset in snap.assets:
            if asset.asset_id in assigned:
                continue
            best: Optional[FunctionalZone] = None
            best_d = float("inf")
            for zone in zones:
                members = ZONE_DEFINITIONS[zone.zone_type]["members"]
                if asset.asset_type not in members:
                    continue
                d = ((asset.tx - zone.center_x) ** 2
                     + (asset.tz - zone.center_z) ** 2) ** 0.5
                if d <= zone.radius and d < best_d:
                    best, best_d = zone, d
            if best is not None:
                best.member_ids.append(asset.asset_id)
                assigned.add(asset.asset_id)

        # --- 3. Structure and wall-decor catch zones ----------------------
        structure = FunctionalZone(zone_id="structure_zone", zone_type="structure")
        wall_decor = FunctionalZone(zone_id="wall_decor_zone", zone_type="wall_decor")
        for asset in snap.assets:
            if asset.asset_id in assigned:
                continue
            if asset.asset_type in STRUCTURAL_TYPES or asset.asset_type == "column":
                structure.member_ids.append(asset.asset_id)
                assigned.add(asset.asset_id)
            elif asset.asset_type == "poster" or (
                asset.asset_type in ("lantern", "lamp", "shelf")
                and (is_wall_mounted(snap, asset) or is_ceiling_mounted(snap, asset))
            ):
                wall_decor.member_ids.append(asset.asset_id)
                assigned.add(asset.asset_id)
        if structure.member_ids:
            zones.append(structure)
        if wall_decor.member_ids:
            zones.append(wall_decor)

        # --- 4. Orphans ----------------------------------------------------
        for asset in snap.assets:
            if asset.asset_id in assigned:
                continue
            plan.orphans.append({
                "asset_id":   asset.asset_id,
                "asset_name": asset.asset_name,
                "asset_type": asset.asset_type,
                "detail": (
                    f"{asset.asset_name or asset.asset_id} belongs to no functional "
                    "zone — no orphan assets allowed (§54)"
                ),
            })

        plan.zones = zones
        plan.assigned_count = len(assigned)
        plan.orphan_count = len(plan.orphans)
        plan.no_orphans = plan.orphan_count == 0
        for o in plan.orphans:
            plan.findings.append(f"ORPHAN_ASSET: {o['detail']}")
        return plan


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[FunctionalZoneBuilder] = None
_lock = threading.Lock()


def get_functional_zone_builder() -> FunctionalZoneBuilder:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = FunctionalZoneBuilder()
    return _instance


def reset_functional_zone_builder_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
