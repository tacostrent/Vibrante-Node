"""
wall_attachment_engine.py — §46 Semantic Furniture Layout Engine
================================================================
Places wall-mounted objects (posters, lanterns, signs, shelves)
on the correct wall with the correct height and orientation.

Height rules (eye-level → high):
  poster / painting / wanted_poster / mirror / certificate: 1.4–1.8 m (eye level)
  sign / clock / notice: 1.6–2.0 m
  banner: 1.8–2.5 m
  lantern / torch / sconce: 2.0–2.8 m (above head)
  shelf: 1.2–1.6 m (arm reach)

Wall layout:
  Four walls labelled north/south/east/west.
  Items distributed evenly across walls; up to 3 items per wall
  before rotating to the next wall.

Public API:
    WallAttachment
    WallAttachmentResult
    WallAttachmentEngine
    get_wall_attachment_engine()
    reset_wall_attachment_engine_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.layout.affordance_engine import get_affordance_engine


# Height range (min, max) in meters for each wall-attachable type
_WALL_HEIGHT_RANGES: Dict[str, tuple] = {
    "poster":        (1.40, 1.80),
    "painting":      (1.40, 1.80),
    "wanted_poster": (1.40, 1.80),
    "notice":        (1.40, 1.80),
    "certificate":   (1.40, 1.80),
    "mirror":        (1.20, 1.80),
    "sign":          (1.60, 2.00),
    "clock":         (1.60, 2.00),
    "rack":          (1.40, 1.80),
    "hook":          (1.60, 2.00),
    "coat_hook":     (1.60, 2.00),
    "banner":        (1.80, 2.50),
    "lantern":       (2.00, 2.80),
    "torch":         (1.80, 2.50),
    "sconce":        (2.00, 2.50),
    "shelf":         (1.20, 1.60),
    "trophy_mount":  (1.40, 1.80),
    "mounted_head":  (1.60, 2.00),
}
_DEFAULT_HEIGHT_RANGE = (1.40, 1.80)

# Canonical wall definitions for a rectangular room (room half-width ~4 m)
_WALLS: List[Dict[str, Any]] = [
    {"name": "wall_north", "normal": [0.0, 0.0, -1.0], "base_x": 0.0, "base_z": -4.0},
    {"name": "wall_south", "normal": [0.0, 0.0,  1.0], "base_x": 0.0, "base_z":  4.0},
    {"name": "wall_east",  "normal": [-1.0, 0.0, 0.0], "base_x":  4.0, "base_z": 0.0},
    {"name": "wall_west",  "normal": [ 1.0, 0.0, 0.0], "base_x": -4.0, "base_z": 0.0},
]

_MAX_ITEMS_PER_WALL = 3
_HORIZONTAL_SPACING = 1.20   # meters between items along the wall


@dataclass
class WallAttachment:
    asset_id: str
    asset_name: str
    asset_type: str
    wall_name: str
    wall_normal: List[float]
    mount_height: float
    position: List[float]
    ok: bool = True
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "asset_id":     self.asset_id,
            "asset_name":   self.asset_name,
            "asset_type":   self.asset_type,
            "wall_name":    self.wall_name,
            "wall_normal":  [round(v, 3) for v in self.wall_normal],
            "mount_height": round(self.mount_height, 3),
            "position":     [round(v, 3) for v in self.position],
            "ok":           self.ok,
            "reason":       self.reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WallAttachment":
        return cls(
            asset_id=d.get("asset_id", ""),
            asset_name=d.get("asset_name", ""),
            asset_type=d.get("asset_type", ""),
            wall_name=d.get("wall_name", ""),
            wall_normal=list(d.get("wall_normal", [0.0, 0.0, -1.0])),
            mount_height=float(d.get("mount_height", 1.60)),
            position=list(d.get("position", [0.0, 1.60, -4.0])),
            ok=bool(d.get("ok", True)),
            reason=d.get("reason", ""),
        )


@dataclass
class WallAttachmentResult:
    attachments: List[WallAttachment] = field(default_factory=list)
    rejected: List[Dict[str, Any]] = field(default_factory=list)
    ok: bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "attachments": [a.to_dict() for a in self.attachments],
            "rejected":    list(self.rejected),
            "ok":          self.ok,
            "errors":      list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WallAttachmentResult":
        return cls(
            attachments=[WallAttachment.from_dict(a) for a in d.get("attachments", [])],
            rejected=list(d.get("rejected", [])),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors", [])),
        )


class WallAttachmentEngine:
    """Assigns wall-mounted assets to wall faces at correct heights."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def attach_to_walls(
        self,
        assets: List[Dict[str, Any]],
        room_half_width: float = 4.0,
    ) -> WallAttachmentResult:
        """
        Assign wall-attachable assets to walls.
        Non-wall-attachable assets are added to the rejected list. Never raises.
        """
        try:
            return self._attach(assets, room_half_width)
        except Exception as exc:
            return WallAttachmentResult(
                ok=False,
                errors=[f"WallAttachmentEngine.attach_to_walls failed: {exc}"],
            )

    def _attach(
        self,
        assets: List[Dict[str, Any]],
        room_half_width: float,
    ) -> WallAttachmentResult:
        eng = get_affordance_engine()
        result = WallAttachmentResult()

        wall_idx = 0
        items_on_wall = 0
        item_offset = 0   # horizontal item counter on current wall

        for asset in assets:
            a_type = eng.infer_type(asset)
            if not eng.get_affordances(a_type).is_wall_attachable:
                result.rejected.append({
                    "asset_id": str(asset.get("asset_id") or ""),
                    "asset_type": a_type,
                    "reason": f"'{a_type}' is not wall-attachable",
                })
                continue

            wall = _WALLS[wall_idx % len(_WALLS)]
            height_range = _WALL_HEIGHT_RANGES.get(a_type, _DEFAULT_HEIGHT_RANGE)
            mount_h = (height_range[0] + height_range[1]) / 2.0

            normal = wall["normal"]
            base_x = wall["base_x"] * room_half_width / 4.0
            base_z = wall["base_z"] * room_half_width / 4.0

            # Distribute items horizontally along the wall
            h_shift = (item_offset - (_MAX_ITEMS_PER_WALL - 1) / 2.0) * _HORIZONTAL_SPACING
            if abs(normal[2]) > 0.5:   # north or south wall → vary X
                px = h_shift
                pz = base_z
            else:                       # east or west wall → vary Z
                px = base_x
                pz = h_shift

            result.attachments.append(WallAttachment(
                asset_id=str(asset.get("asset_id") or asset.get("name") or ""),
                asset_name=str(asset.get("name") or asset.get("asset_id") or ""),
                asset_type=a_type,
                wall_name=wall["name"],
                wall_normal=list(normal),
                mount_height=mount_h,
                position=[px, mount_h, pz],
            ))

            items_on_wall += 1
            item_offset += 1
            if items_on_wall >= _MAX_ITEMS_PER_WALL:
                wall_idx += 1
                items_on_wall = 0
                item_offset = 0

        return result

    def get_mount_height(self, asset_type: str) -> float:
        """Return the canonical mounting height (midpoint of range) for an asset type."""
        rng = _WALL_HEIGHT_RANGES.get(asset_type.lower(), _DEFAULT_HEIGHT_RANGE)
        return (rng[0] + rng[1]) / 2.0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[WallAttachmentEngine] = None
_lock = threading.Lock()


def get_wall_attachment_engine() -> WallAttachmentEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = WallAttachmentEngine()
    return _instance


def reset_wall_attachment_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
