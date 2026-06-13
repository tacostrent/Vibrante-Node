"""
surface_placement_engine.py — §46 Semantic Furniture Layout Engine
=================================================================
Places small objects on the actual support surfaces of host assets.
Uses estimated surface heights per host type (Tier 9.7 geometry data
can override these when available).

Rules:
  - Object must fit the surface (surface has a max-item cap)
  - Surface height provides the Y coordinate
  - Objects are spread deterministically along the surface width
  - Overflow objects are rejected, not placed on the floor

Public API:
    SurfacePlacement
    SurfacePlacementResult
    SurfacePlacementEngine
    get_surface_placement_engine()
    reset_surface_placement_engine_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Surface height by host type (meters above floor)
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

# Max items per surface type
_MAX_ITEMS: Dict[str, int] = {
    "table":       6,
    "desk":        4,
    "workbench":   5,
    "bar_counter": 8,
    "shelf":       5,
    "counter":     4,
    "crate":       2,
    "pallet":      3,
    "mantle":      3,
    "cabinet":     2,
    "console":     3,
}

# Usable surface width for item distribution (meters)
_SURFACE_WIDTHS: Dict[str, float] = {
    "table":       1.20,
    "desk":        1.20,
    "workbench":   1.80,
    "bar_counter": 3.00,
    "shelf":       1.00,
    "counter":     1.50,
    "crate":       0.50,
    "pallet":      0.80,
    "mantle":      1.00,
    "cabinet":     0.80,
    "console":     1.00,
}

_DEFAULT_SURFACE_HEIGHT = 0.75
_DEFAULT_MAX_ITEMS = 4
_DEFAULT_SURFACE_WIDTH = 1.00


@dataclass
class SurfacePlacement:
    child_asset_id: str
    child_asset_name: str
    host_asset_id: str
    host_asset_name: str
    surface_type: str
    surface_height: float
    position: List[float]
    ok: bool = True
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "child_asset_id":   self.child_asset_id,
            "child_asset_name": self.child_asset_name,
            "host_asset_id":    self.host_asset_id,
            "host_asset_name":  self.host_asset_name,
            "surface_type":     self.surface_type,
            "surface_height":   round(self.surface_height, 3),
            "position":         [round(v, 3) for v in self.position],
            "ok":               self.ok,
            "reason":           self.reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SurfacePlacement":
        return cls(
            child_asset_id=d.get("child_asset_id", ""),
            child_asset_name=d.get("child_asset_name", ""),
            host_asset_id=d.get("host_asset_id", ""),
            host_asset_name=d.get("host_asset_name", ""),
            surface_type=d.get("surface_type", ""),
            surface_height=float(d.get("surface_height", 0.0)),
            position=list(d.get("position", [0.0, 0.0, 0.0])),
            ok=bool(d.get("ok", True)),
            reason=d.get("reason", ""),
        )


@dataclass
class SurfacePlacementResult:
    host_asset_id: str
    host_asset_name: str
    surface_type: str
    surface_height: float
    placements: List[SurfacePlacement] = field(default_factory=list)
    rejected: List[dict] = field(default_factory=list)
    ok: bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "host_asset_id":   self.host_asset_id,
            "host_asset_name": self.host_asset_name,
            "surface_type":    self.surface_type,
            "surface_height":  round(self.surface_height, 3),
            "placements":      [p.to_dict() for p in self.placements],
            "rejected":        list(self.rejected),
            "ok":              self.ok,
            "errors":          list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SurfacePlacementResult":
        return cls(
            host_asset_id=d.get("host_asset_id", ""),
            host_asset_name=d.get("host_asset_name", ""),
            surface_type=d.get("surface_type", ""),
            surface_height=float(d.get("surface_height", 0.0)),
            placements=[SurfacePlacement.from_dict(p) for p in d.get("placements", [])],
            rejected=list(d.get("rejected", [])),
            ok=bool(d.get("ok", True)),
            errors=list(d.get("errors", [])),
        )


class SurfacePlacementEngine:
    """Places small objects on host asset surfaces at the correct Y height."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def place_on_surface(
        self,
        host_asset: Dict[str, Any],
        child_assets: List[Dict[str, Any]],
        host_position: Optional[List[float]] = None,
    ) -> SurfacePlacementResult:
        """
        Place child_assets on the primary surface of host_asset.

        host_position: world-space [x, y, z] of the host asset (default origin).
        Never raises.
        """
        try:
            return self._place(host_asset, child_assets, host_position or [0.0, 0.0, 0.0])
        except Exception as exc:
            return SurfacePlacementResult(
                host_asset_id=str(host_asset.get("asset_id") or ""),
                host_asset_name=str(host_asset.get("name") or ""),
                surface_type="unknown",
                surface_height=0.0,
                ok=False,
                errors=[f"surface placement error: {exc}"],
            )

    def _place(
        self,
        host: Dict[str, Any],
        children: List[Dict[str, Any]],
        host_pos: List[float],
    ) -> SurfacePlacementResult:
        host_id   = str(host.get("asset_id") or host.get("name") or "host")
        host_name = str(host.get("name") or host.get("asset_id") or "")
        host_type = self._get_type(host)

        surf_h   = _SURFACE_HEIGHTS.get(host_type, _DEFAULT_SURFACE_HEIGHT)
        surf_w   = _SURFACE_WIDTHS.get(host_type, _DEFAULT_SURFACE_WIDTH)
        max_items = _MAX_ITEMS.get(host_type, _DEFAULT_MAX_ITEMS)
        surface_y = host_pos[1] + surf_h

        result = SurfacePlacementResult(
            host_asset_id=host_id,
            host_asset_name=host_name,
            surface_type=f"{host_type}_surface",
            surface_height=surf_h,
        )

        if len(children) > max_items:
            result.rejected.extend(
                {"asset_id": str(c.get("asset_id") or ""), "reason": "surface full"}
                for c in children[max_items:]
            )
            children = children[:max_items]

        n = len(children)
        if n == 0:
            return result

        step = surf_w / max(n, 1)
        start_x = host_pos[0] - surf_w / 2.0 + step / 2.0

        for i, child in enumerate(children):
            child_id   = str(child.get("asset_id") or child.get("name") or f"child_{i}")
            child_name = str(child.get("name") or child_id)
            result.placements.append(SurfacePlacement(
                child_asset_id=child_id,
                child_asset_name=child_name,
                host_asset_id=host_id,
                host_asset_name=host_name,
                surface_type=f"{host_type}_surface",
                surface_height=surf_h,
                position=[start_x + i * step, surface_y, host_pos[2]],
            ))

        return result

    def get_surface_height(self, host_type: str) -> float:
        """Return estimated surface height for a host type."""
        return _SURFACE_HEIGHTS.get(host_type.lower(), _DEFAULT_SURFACE_HEIGHT)

    def _get_type(self, asset: Dict[str, Any]) -> str:
        return (
            asset.get("placement_type")
            or asset.get("type")
            or asset.get("asset_type")
            or "table"
        ).lower()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[SurfacePlacementEngine] = None
_lock = threading.Lock()


def get_surface_placement_engine() -> SurfacePlacementEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SurfacePlacementEngine()
    return _instance


def reset_surface_placement_engine_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
