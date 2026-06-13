"""
support_surface_validator.py — §53 Scene Reality Validation (Tier 14.3)
========================================================================
Rule 1 — Support Surface Validation.

Detects small surface-affinity props (teapot, bottle, cup, book, …) that
are resting on the floor (ty < FLOOR_THRESHOLD) when a valid support host
(table, shelf, bar_counter, …) exists anywhere in the scene.

Violation code : INVALID_SUPPORT_RELATION
Severity       : BLOCKING

Public API:
    SupportViolation
    SupportSurfaceValidator
    get_support_surface_validator()
    reset_support_surface_validator_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

FLOOR_THRESHOLD = 0.35  # metres — ty below this is considered "on the floor"

# Keywords for assets that SHOULD rest on a surface host
_SURFACE_PROP_KEYWORDS: List[str] = [
    "teapot", "bottle", "whiskey", "beer bottle",
    "cup", "glass", "mug", "beer mug",
    "plate", "bowl", "vase",
    "candle", "book", "paper",
    "knife", "fork", "spoon",
    "salt", "pepper", "sugar", "jar",
    "small_prop", "small prop",
]

# Keywords for assets that CAN HOST surface props
_SURFACE_HOST_KEYWORDS: List[str] = [
    "table", "desk", "workbench", "bar_counter", "bar counter",
    "shelf", "counter", "cabinet", "mantle", "crate", "console",
]


def _is_surface_prop(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in _SURFACE_PROP_KEYWORDS)


def _is_surface_host(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in _SURFACE_HOST_KEYWORDS)


@dataclass
class SupportViolation:
    asset_id:       str
    asset_name:     str
    ty:             float
    violation_code: str = "INVALID_SUPPORT_RELATION"
    severity:       str = "BLOCKING"
    detail:         str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":       self.asset_id,
            "asset_name":     self.asset_name,
            "ty":             round(self.ty, 4),
            "violation_code": self.violation_code,
            "severity":       self.severity,
            "detail":         self.detail,
        }


class SupportSurfaceValidator:
    """Validates that surface-affinity props are placed on surfaces, not floors."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def validate(self, scene_layout: Dict[str, Any]) -> List[SupportViolation]:
        """
        Scan all transforms and return INVALID_SUPPORT_RELATION violations.
        Never raises.
        """
        try:
            return self._validate(scene_layout)
        except Exception:
            return []

    def _validate(self, scene: Dict[str, Any]) -> List[SupportViolation]:
        transforms = scene.get("transforms") or []
        violations: List[SupportViolation] = []

        # Collect host names present in scene
        hosts_in_scene = [
            t.get("asset_name", "")
            for t in transforms
            if _is_surface_host(t.get("asset_name", ""))
        ]
        if not hosts_in_scene:
            return []  # no valid hosts → rule does not apply

        for t in transforms:
            name = t.get("asset_name", "")
            ty   = float(t.get("ty", 0.0))
            rel  = t.get("relationship", "")

            # Wall-mounted items are exempt
            if rel == "attached_to":
                continue

            # Already correctly on a surface
            if rel == "supports" and ty >= FLOOR_THRESHOLD:
                continue

            if not _is_surface_prop(name):
                continue

            if ty < FLOOR_THRESHOLD:
                violations.append(SupportViolation(
                    asset_id=t.get("asset_id", ""),
                    asset_name=name,
                    ty=ty,
                    detail=(
                        f"{name!r} is at floor level (ty={ty:.2f}m) "
                        f"but surface host {hosts_in_scene[0]!r} exists in scene"
                    ),
                ))

        return violations


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[SupportSurfaceValidator] = None
_lock = threading.Lock()


def get_support_surface_validator() -> SupportSurfaceValidator:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SupportSurfaceValidator()
    return _instance


def reset_support_surface_validator_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
