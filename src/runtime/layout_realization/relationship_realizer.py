"""
relationship_realizer.py — §47 Layout Realization & Scene Constraint Solver
============================================================================
Converts semantic relationships (around, supports, attached_to, against,
near, hanging_from) into concrete world-space transforms.

For each relationship type the realizer knows the spatial contract:
  around     → orbit at fixed radius, face inward
  supports   → place on host surface at surface height Y
  attached_to → mount on wall/ceiling at height, face outward from surface
  against    → push flush against host surface
  near       → place within proximity radius without overlap
  hanging_from → place below host at drop distance

Public API:
    RelationshipRealization
    RelationshipRealizationResult
    RelationshipRealizer
    get_relationship_realizer()
    reset_relationship_realizer_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout_realization.transform_resolver import ResolvedTransform


# Orbit radius per relationship context (meters)
_ORBIT_RADIUS: Dict[str, float] = {
    "around":      0.90,
    "near":        0.60,
    "against":     0.10,
    "hanging_from": 0.50,
}

# Cardinal orbit offsets: [angle_deg, dx, dz, ry]
_ORBIT_SLOTS = [
    (  0.0,  0.00,  0.90, 180.0),   # south  → faces north
    (180.0,  0.00, -0.90,   0.0),   # north  → faces south
    ( 90.0,  0.90,  0.00, 270.0),   # east   → faces west
    (270.0, -0.90,  0.00,  90.0),   # west   → faces east
]

# Surface height fallback table (meters above floor)
_SURFACE_HEIGHTS: Dict[str, float] = {
    "table":       0.75,
    "desk":        0.75,
    "workbench":   0.90,
    "bar_counter": 1.05,
    "shelf":       1.40,
    "counter":     0.90,
    "crate":       0.60,
    "pallet":      0.15,
    "mantle":      1.20,
    "cabinet":     1.60,
    "console":     0.85,
}

_DROP_DISTANCE = 0.50   # hanging_from: distance below host bottom


@dataclass
class RelationshipRealization:
    """World-space transform result for one asset relationship."""
    asset_id:         str
    asset_name:       str
    relationship_type: str
    parent_id:        str

    world_position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    world_rotation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])   # rx, ry, rz

    ok:    bool = True
    notes: str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":          self.asset_id,
            "asset_name":        self.asset_name,
            "relationship_type": self.relationship_type,
            "parent_id":         self.parent_id,
            "world_position":    [round(v, 4) for v in self.world_position],
            "world_rotation":    [round(v, 4) for v in self.world_rotation],
            "ok":                self.ok,
            "notes":             self.notes,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RelationshipRealization":
        return cls(
            asset_id=d.get("asset_id", ""),
            asset_name=d.get("asset_name", ""),
            relationship_type=d.get("relationship_type", ""),
            parent_id=d.get("parent_id", ""),
            world_position=list(d.get("world_position", [0.0, 0.0, 0.0])),
            world_rotation=list(d.get("world_rotation", [0.0, 0.0, 0.0])),
            ok=bool(d.get("ok", True)),
            notes=d.get("notes", ""),
        )


@dataclass
class RelationshipRealizationResult:
    realizations: List[RelationshipRealization] = field(default_factory=list)
    ok:     bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "realizations": [r.to_dict() for r in self.realizations],
            "ok":           self.ok,
            "errors":       list(self.errors),
        }


class RelationshipRealizer:
    """
    Converts semantic relationship data from a LayoutPlan into world transforms.

    Handles the spatial contract for each relationship type without requiring
    any bridge or renderer connection.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def realize_relationships(
        self,
        relationships: List[Dict[str, Any]],
        anchor_transforms: Dict[str, ResolvedTransform],
        host_types: Dict[str, str],
    ) -> RelationshipRealizationResult:
        """
        Realize a list of relationship dicts from LayoutPlan.relationships.

        Args:
            relationships:     plan.relationships dicts
            anchor_transforms: map asset_id → ResolvedTransform for anchors
            host_types:        map asset_id → placement_type string

        Returns: RelationshipRealizationResult. Never raises.
        """
        try:
            return self._realize(relationships, anchor_transforms, host_types)
        except Exception as exc:
            return RelationshipRealizationResult(
                ok=False,
                errors=[f"RelationshipRealizer.realize_relationships failed: {exc}"],
            )

    def _realize(
        self,
        relationships: List[Dict[str, Any]],
        anchor_transforms: Dict[str, ResolvedTransform],
        host_types: Dict[str, str],
    ) -> RelationshipRealizationResult:
        result = RelationshipRealizationResult()
        slot_counters: Dict[str, int] = {}   # parent_id → orbit slot index

        for rel in relationships:
            from_id  = rel.get("from_asset_id", "")
            to_id    = rel.get("to_asset_id", "")
            rel_type = rel.get("relationship_type", "near")

            parent_xf = anchor_transforms.get(to_id)
            parent_pos = (
                [parent_xf.tx, parent_xf.ty, parent_xf.tz]
                if parent_xf else [0.0, 0.0, 0.0]
            )

            realization = self._realize_one(
                from_id=from_id,
                rel_type=rel_type,
                to_id=to_id,
                parent_pos=parent_pos,
                host_type=host_types.get(to_id, ""),
                slot_counters=slot_counters,
            )
            result.realizations.append(realization)

        return result

    def _realize_one(
        self,
        from_id: str,
        rel_type: str,
        to_id: str,
        parent_pos: List[float],
        host_type: str,
        slot_counters: Dict[str, int],
    ) -> RelationshipRealization:
        px, py, pz = float(parent_pos[0]), float(parent_pos[1]), float(parent_pos[2])

        if rel_type == "around":
            slot = slot_counters.get(to_id, 0)
            slot_counters[to_id] = slot + 1
            if slot < len(_ORBIT_SLOTS):
                _, dx, dz, ry = _ORBIT_SLOTS[slot]
            else:
                # Overflow: distribute at equal angles
                import math
                angle_rad = (slot * 2 * math.pi / max(slot + 1, 4))
                import math as _m
                radius = _ORBIT_RADIUS["around"]
                dx = _m.sin(angle_rad) * radius
                dz = _m.cos(angle_rad) * radius
                ry = (_m.degrees(-angle_rad) + 180.0) % 360.0
            return RelationshipRealization(
                asset_id=from_id, asset_name=from_id,
                relationship_type="around", parent_id=to_id,
                world_position=[px + dx, py, pz + dz],
                world_rotation=[0.0, ry, 0.0],
                notes=f"orbit slot {slot_counters[to_id] - 1}",
            )

        if rel_type == "supports":
            surf_h = _SURFACE_HEIGHTS.get(host_type, 0.75)
            slot = slot_counters.get(f"surf_{to_id}", 0)
            slot_counters[f"surf_{to_id}"] = slot + 1
            x_offset = (slot - 1) * 0.25
            return RelationshipRealization(
                asset_id=from_id, asset_name=from_id,
                relationship_type="supports", parent_id=to_id,
                world_position=[px + x_offset, py + surf_h, pz],
                world_rotation=[0.0, 0.0, 0.0],
                notes=f"surface_y={py + surf_h:.2f}m",
            )

        if rel_type == "attached_to":
            # Wall attachment: use the parent transform position directly
            return RelationshipRealization(
                asset_id=from_id, asset_name=from_id,
                relationship_type="attached_to", parent_id=to_id,
                world_position=[px, py, pz],
                world_rotation=[0.0, 0.0, 0.0],
                notes="wall mount",
            )

        if rel_type == "against":
            return RelationshipRealization(
                asset_id=from_id, asset_name=from_id,
                relationship_type="against", parent_id=to_id,
                world_position=[px + _ORBIT_RADIUS["against"], py, pz],
                world_rotation=[0.0, 0.0, 0.0],
                notes="flush against",
            )

        if rel_type == "hanging_from":
            return RelationshipRealization(
                asset_id=from_id, asset_name=from_id,
                relationship_type="hanging_from", parent_id=to_id,
                world_position=[px, py - _DROP_DISTANCE, pz],
                world_rotation=[0.0, 0.0, 0.0],
                notes=f"hanging at y={py - _DROP_DISTANCE:.2f}m",
            )

        # Default: near / generic
        slot = slot_counters.get(f"near_{to_id}", 0)
        slot_counters[f"near_{to_id}"] = slot + 1
        offset = _ORBIT_RADIUS["near"] * (1 + slot * 0.5)
        return RelationshipRealization(
            asset_id=from_id, asset_name=from_id,
            relationship_type=rel_type, parent_id=to_id,
            world_position=[px + offset, py, pz],
            world_rotation=[0.0, 0.0, 0.0],
            notes=f"near offset={offset:.2f}m",
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[RelationshipRealizer] = None
_lock = threading.Lock()


def get_relationship_realizer() -> RelationshipRealizer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RelationshipRealizer()
    return _instance


def reset_relationship_realizer_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
