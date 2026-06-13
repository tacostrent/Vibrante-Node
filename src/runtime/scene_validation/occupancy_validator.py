"""
occupancy_validator.py — §53 Scene Reality Validation (Tier 14.3)
==================================================================
Rule 2 — Occupancy Validation.

Generates AABB occupancy volumes for furniture/structural assets and
detects small props whose world-space centre falls inside those volumes.

Violation code : OCCUPANCY_VIOLATION
Severity       : BLOCKING

Public API:
    OccupancyViolation
    OccupancyValidator
    get_occupancy_validator()
    reset_occupancy_validator_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


_OCCUPANCY_HOST_KEYWORDS: List[str] = [
    "chair", "armchair", "sofa", "couch",
    "table", "desk",
    "cabinet", "wardrobe", "chest",
    "doorway", "door frame",
    "bed", "bench",
    "barrel", "crate",
]

_SMALL_PROP_KEYWORDS: List[str] = [
    "teapot", "bottle", "cup", "glass", "mug",
    "plate", "bowl", "vase",
    "candle", "book", "paper",
    "knife", "fork", "spoon",
    "lantern", "container", "jar", "salt", "pepper",
]


def _is_occupancy_host(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in _OCCUPANCY_HOST_KEYWORDS)


def _is_small_prop(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in _SMALL_PROP_KEYWORDS)


def _aabb(t: Dict[str, Any]) -> Tuple[float, float, float, float, float, float]:
    """Return (min_x, max_x, min_y, max_y, min_z, max_z) for a transform."""
    tx = float(t.get("tx", 0))
    ty = float(t.get("ty", 0))
    tz = float(t.get("tz", 0))
    hx = max(0.15, float(t.get("bbox_half_x", 0.0)) or 0.25)
    hy = max(0.20, float(t.get("bbox_half_y", 0.0)) or 0.45)
    hz = max(0.15, float(t.get("bbox_half_z", 0.0)) or 0.25)
    return (tx - hx, tx + hx, ty, ty + 2 * hy, tz - hz, tz + hz)


def _point_inside_aabb(
    px: float, py: float, pz: float,
    min_x: float, max_x: float,
    min_y: float, max_y: float,
    min_z: float, max_z: float,
) -> bool:
    return (
        min_x <= px <= max_x
        and min_y <= py <= max_y
        and min_z <= pz <= max_z
    )


@dataclass
class OccupancyViolation:
    prop_id:        str
    prop_name:      str
    host_id:        str
    host_name:      str
    violation_code: str = "OCCUPANCY_VIOLATION"
    severity:       str = "BLOCKING"
    detail:         str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prop_id":        self.prop_id,
            "prop_name":      self.prop_name,
            "host_id":        self.host_id,
            "host_name":      self.host_name,
            "violation_code": self.violation_code,
            "severity":       self.severity,
            "detail":         self.detail,
        }


class OccupancyValidator:
    """Detects small props whose centre falls inside a furniture AABB."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def validate(self, scene_layout: Dict[str, Any]) -> List[OccupancyViolation]:
        """Return all OCCUPANCY_VIOLATION records. Never raises."""
        try:
            return self._validate(scene_layout)
        except Exception:
            return []

    def _validate(self, scene: Dict[str, Any]) -> List[OccupancyViolation]:
        transforms = scene.get("transforms") or []
        violations: List[OccupancyViolation] = []

        hosts = [t for t in transforms if _is_occupancy_host(t.get("asset_name", ""))]
        props = [t for t in transforms if _is_small_prop(t.get("asset_name", ""))]

        for prop in props:
            prop_id      = prop.get("asset_id", "")
            prop_parent  = prop.get("parent_id", "")
            prop_cluster = prop.get("cluster_id", "")
            px = float(prop.get("tx", 0))
            py = float(prop.get("ty", 0))
            pz = float(prop.get("tz", 0))

            for host in hosts:
                host_id      = host.get("asset_id", "")
                host_cluster = host.get("cluster_id", "")

                # Parent-child exemption
                if prop_parent and prop_parent == host_id:
                    continue
                # Same-cluster exemption (surface props inside cluster are valid)
                if prop_cluster and prop_cluster == host_cluster and prop_cluster:
                    continue

                min_x, max_x, min_y, max_y, min_z, max_z = _aabb(host)
                if _point_inside_aabb(px, py, pz, min_x, max_x, min_y, max_y, min_z, max_z):
                    violations.append(OccupancyViolation(
                        prop_id=prop_id,
                        prop_name=prop.get("asset_name", ""),
                        host_id=host_id,
                        host_name=host.get("asset_name", ""),
                        detail=(
                            f"{prop.get('asset_name', '')!r} centre "
                            f"({px:.2f},{py:.2f},{pz:.2f}) "
                            f"is inside {host.get('asset_name', '')!r} AABB"
                        ),
                    ))

        return violations


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[OccupancyValidator] = None
_lock = threading.Lock()


def get_occupancy_validator() -> OccupancyValidator:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = OccupancyValidator()
    return _instance


def reset_occupancy_validator_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
