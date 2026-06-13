"""
StructuralAnchorGenerator — Tier 10.4, Phase 4
================================================
Generates structural attachment anchor points for the shell.

Anchor types:
  door_anchor    — attachment point on a wall face for a door opening
  window_anchor  — attachment point on a wall face for a window opening
  beam_anchor    — attachment point on the ceiling for a beam
  column_anchor  — floor+ceiling pair for a vertical column
  fireplace_anchor — wall-face attachment for a fireplace

Never raises.

Public API:
    StructuralAnchorGenerator
    get_structural_anchor_generator()
    reset_structural_anchor_generator_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from src.runtime.environment_shell.environment_shell_blueprint import EnvironmentShellBlueprint
from src.runtime.environment_shell.shell_phase_result import (
    ShellPhaseResult,
    STRUCTURAL_ANCHORS_READY,
)

# Environments that have fireplaces
_FIREPLACE_ENVS = frozenset({
    "western_room", "saloon", "living_room",
    "castle_hall", "dungeon", "library",
    "restaurant", "survival_camp",
})

# Environments that have beams in the ceiling
_BEAM_ENVS = frozenset({
    "western_room", "saloon", "warehouse", "library",
    "industrial_hangar", "abandoned_factory", "castle_hall",
    "dungeon", "workshop", "shipyard",
})

# Number of beam anchors per environment
_BEAM_COUNTS: Dict[str, int] = {
    "western_room": 4, "saloon": 6, "warehouse": 6,
    "library": 4, "industrial_hangar": 8, "abandoned_factory": 6,
    "castle_hall": 4, "dungeon": 2, "workshop": 3, "shipyard": 10,
}

# Number of column anchors per environment
_COLUMN_COUNTS: Dict[str, int] = {
    "industrial_hangar": 6, "warehouse": 4, "castle_hall": 8,
    "hotel_lobby": 6, "library": 4, "shopping_mall": 8,
    "robotics_lab": 4, "subway_station": 8, "temple": 6,
}


class StructuralAnchorGenerator:

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def generate(self, blueprint: EnvironmentShellBlueprint) -> ShellPhaseResult:
        """Generate structural anchor points. Never raises."""
        try:
            return self._generate(blueprint)
        except Exception as exc:
            r = ShellPhaseResult(phase="anchors", status="ANCHORS_FAILED")
            r.errors.append(f"StructuralAnchorGenerator error: {exc}")
            return r

    def _generate(self, bp: EnvironmentShellBlueprint) -> ShellPhaseResult:
        result = ShellPhaseResult(phase="anchors")
        anchors: List[Dict[str, Any]] = []
        env = bp.environment_type
        h   = bp.room_height  if bp.room_height  > 0 else 4.0
        w   = bp.room_width   if bp.room_width   > 0 else 10.0
        d   = bp.room_length  if bp.room_length  > 0 else 12.0

        # Door anchors — south wall (main entrance)
        for i in range(bp.door_count):
            offset_x = (i - (bp.door_count - 1) / 2.0) * (w / max(bp.door_count, 1))
            anchors.append({
                "anchor_type":  "door_anchor",
                "anchor_id":    f"door_anchor_{i}_{env}",
                "environment":  env,
                "wall_face":    "south",
                "tx": offset_x, "ty": h * 0.45, "tz": d / 2.0,
                "door_height":  min(2.2, h * 0.9),
                "door_width":   0.9,
            })

        # Window anchors — east and west walls
        total_windows = bp.window_count
        east_count  = total_windows // 2
        west_count  = total_windows - east_count
        for i in range(east_count):
            offset_z = (i - (east_count - 1) / 2.0) * (d / max(east_count, 1))
            anchors.append({
                "anchor_type": "window_anchor",
                "anchor_id":   f"window_anchor_east_{i}_{env}",
                "environment": env,
                "wall_face":   "east",
                "tx": w / 2.0, "ty": h * 0.55, "tz": offset_z,
                "window_height": min(1.2, h * 0.4),
                "window_width":  1.0,
            })
        for i in range(west_count):
            offset_z = (i - (west_count - 1) / 2.0) * (d / max(west_count, 1))
            anchors.append({
                "anchor_type": "window_anchor",
                "anchor_id":   f"window_anchor_west_{i}_{env}",
                "environment": env,
                "wall_face":   "west",
                "tx": -(w / 2.0), "ty": h * 0.55, "tz": offset_z,
                "window_height": min(1.2, h * 0.4),
                "window_width":  1.0,
            })

        # Beam anchors — ceiling
        beam_count = _BEAM_COUNTS.get(env, 0) if env in _BEAM_ENVS else 0
        beam_spacing = w / max(beam_count + 1, 1)
        for i in range(beam_count):
            bx = -w / 2.0 + beam_spacing * (i + 1)
            anchors.append({
                "anchor_type": "beam_anchor",
                "anchor_id":   f"beam_anchor_{i}_{env}",
                "environment": env,
                "tx": bx, "ty": h - 0.1, "tz": 0.0,
                "beam_span":   d,
                "attachment":  "ceiling",
            })

        # Column anchors — floor+ceiling pairs
        col_count = _COLUMN_COUNTS.get(env, 0)
        if col_count > 0:
            cols_per_side = col_count // 2
            col_spacing   = d / max(cols_per_side + 1, 1)
            for side_idx, side_x in enumerate([-w * 0.35, w * 0.35]):
                for i in range(cols_per_side):
                    cz = -d / 2.0 + col_spacing * (i + 1)
                    anchors.append({
                        "anchor_type":  "column_anchor",
                        "anchor_id":    f"column_anchor_{side_idx}_{i}_{env}",
                        "environment":  env,
                        "tx": side_x, "ty": h / 2.0, "tz": cz,
                        "column_height": h,
                        "floor_attachment":   True,
                        "ceiling_attachment": True,
                    })

        # Fireplace anchor — north wall
        if env in _FIREPLACE_ENVS:
            anchors.append({
                "anchor_type": "fireplace_anchor",
                "anchor_id":   f"fireplace_anchor_{env}",
                "environment": env,
                "wall_face":   "north",
                "tx": 0.0, "ty": 0.0, "tz": -(d / 2.0) + 0.3,
                "fireplace_height": 1.5,
                "fireplace_width":  1.2,
                "attachment": "wall_face",
            })

        result.elements = anchors
        result.metrics  = {
            "door_anchor_count":      bp.door_count,
            "window_anchor_count":    total_windows,
            "beam_anchor_count":      beam_count,
            "column_anchor_count":    col_count,
            "fireplace_anchor_count": 1 if env in _FIREPLACE_ENVS else 0,
            "total_anchors":          len(anchors),
        }
        result.status = STRUCTURAL_ANCHORS_READY
        result.ok     = True
        return result


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[StructuralAnchorGenerator] = None
_LOCK = threading.Lock()


def get_structural_anchor_generator() -> StructuralAnchorGenerator:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = StructuralAnchorGenerator()
    return _INSTANCE


def reset_structural_anchor_generator_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
