"""
ShellFloorBuilder — Tier 10.4, Phase 1
=======================================
Constructs the floor element of the environment shell.

Requirements:
  floor_exists = True
  floor_area   > 0
  walkable_surface = True

All asset placement must reference the floor. Never raises.

Public API:
    ShellFloorBuilder
    get_shell_floor_builder()
    reset_shell_floor_builder_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from src.runtime.environment_shell.environment_shell_blueprint import EnvironmentShellBlueprint
from src.runtime.environment_shell.shell_phase_result import (
    ShellPhaseResult,
    FLOOR_CONSTRUCTION_COMPLETE,
)


class ShellFloorBuilder:

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build(self, blueprint: EnvironmentShellBlueprint) -> ShellPhaseResult:
        """Build the floor element from a blueprint. Never raises."""
        try:
            return self._build(blueprint)
        except Exception as exc:
            r = ShellPhaseResult(phase="floor", status="FLOOR_FAILED")
            r.errors.append(f"ShellFloorBuilder error: {exc}")
            return r

    def _build(self, bp: EnvironmentShellBlueprint) -> ShellPhaseResult:
        result = ShellPhaseResult(phase="floor")

        # For outdoor environments the "floor" is a ground plane
        floor_type = bp.floor_type or ("ground_plane" if bp.is_outdoor else "concrete")
        w = bp.room_width if bp.room_width > 0 else 10.0
        d = bp.room_length if bp.room_length > 0 else 12.0
        area = w * d

        element: Dict[str, Any] = {
            "element_type": "floor",
            "element_id":   f"floor_{bp.environment_type}",
            "environment":  bp.environment_type,
            "floor_exists": True,
            "floor_area":   area,
            "walkable_surface": True,
            "material":     floor_type,
            "width":        w,
            "depth":        d,
            "tx": 0.0, "ty": 0.0, "tz": 0.0,
            "is_outdoor_ground": bp.is_outdoor,
        }
        result.elements.append(element)
        result.metrics = {
            "floor_exists": True,
            "floor_area":   area,
            "walkable_surface": True,
        }
        result.status = FLOOR_CONSTRUCTION_COMPLETE
        result.ok     = True
        return result


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[ShellFloorBuilder] = None
_LOCK = threading.Lock()


def get_shell_floor_builder() -> ShellFloorBuilder:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = ShellFloorBuilder()
    return _INSTANCE


def reset_shell_floor_builder_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
