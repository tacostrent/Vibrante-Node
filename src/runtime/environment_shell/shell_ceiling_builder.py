"""
ShellCeilingBuilder — Tier 10.4, Phase 3
==========================================
Constructs the ceiling element of the environment shell.

Requirements:
  ceiling_exists     = True (indoor only; outdoor → open_sky, no element)
  ceiling_height     > floor_height
  supports_beams     = True (for beam-type ceilings)

Never raises.

Public API:
    ShellCeilingBuilder
    get_shell_ceiling_builder()
    reset_shell_ceiling_builder_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from src.runtime.environment_shell.environment_shell_blueprint import EnvironmentShellBlueprint
from src.runtime.environment_shell.shell_phase_result import (
    ShellPhaseResult,
    CEILING_CONSTRUCTION_COMPLETE,
)

_BEAM_CEILINGS = frozenset({
    "beam_ceiling", "vaulted_ceiling", "arched_ceiling",
    "high_ceiling", "industrial_ceiling",
})


class ShellCeilingBuilder:

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build(self, blueprint: EnvironmentShellBlueprint) -> ShellPhaseResult:
        """Build the ceiling element. Never raises."""
        try:
            return self._build(blueprint)
        except Exception as exc:
            r = ShellPhaseResult(phase="ceiling", status="CEILING_FAILED")
            r.errors.append(f"ShellCeilingBuilder error: {exc}")
            return r

    def _build(self, bp: EnvironmentShellBlueprint) -> ShellPhaseResult:
        result = ShellPhaseResult(phase="ceiling")

        if bp.is_outdoor or bp.ceiling_type == "open_sky":
            result.status = CEILING_CONSTRUCTION_COMPLETE
            result.ok     = True
            result.metrics = {
                "ceiling_exists":  False,
                "ceiling_type":    "open_sky",
                "ceiling_height":  0.0,
                "supports_beams":  False,
            }
            result.findings.append("Outdoor environment: open sky, no ceiling element.")
            return result

        h  = bp.room_height if bp.room_height > 0 else 4.0
        w  = bp.room_width  if bp.room_width  > 0 else 10.0
        d  = bp.room_length if bp.room_length > 0 else 12.0
        ct = bp.ceiling_type or "flat_ceiling"
        supports_beams = ct in _BEAM_CEILINGS

        element: Dict[str, Any] = {
            "element_type": "ceiling",
            "element_id":   f"ceiling_{bp.environment_type}",
            "environment":  bp.environment_type,
            "ceiling_type": ct,
            "material":     "wood" if "beam" in ct else ("stone" if "vaulted" in ct or "arched" in ct else "concrete"),
            "width":        w,
            "depth":        d,
            "tx": 0.0, "ty": h, "tz": 0.0,
            "ceiling_exists":  True,
            "ceiling_height":  h,
            "supports_beams":  supports_beams,
        }
        result.elements.append(element)
        result.metrics = {
            "ceiling_exists":  True,
            "ceiling_type":    ct,
            "ceiling_height":  h,
            "supports_beams":  supports_beams,
        }
        result.status = CEILING_CONSTRUCTION_COMPLETE
        result.ok     = True
        return result


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[ShellCeilingBuilder] = None
_LOCK = threading.Lock()


def get_shell_ceiling_builder() -> ShellCeilingBuilder:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = ShellCeilingBuilder()
    return _INSTANCE


def reset_shell_ceiling_builder_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
