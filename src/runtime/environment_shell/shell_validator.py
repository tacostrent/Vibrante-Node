"""
ShellValidator — Tier 10.4, Phase 6
=====================================
Validates the completed environment shell.

Validates:
  floor_exists
  ceiling_exists (or is outdoor)
  wall_count >= required
  room_bounds_valid (dimensions non-zero)
  enclosure_valid (indoor only)

Never raises.

Public API:
    ShellValidator
    get_shell_validator()
    reset_shell_validator_for_tests()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from src.runtime.environment_shell.shell_phase_result import (
    ShellPhaseResult,
    ENVIRONMENT_VALIDATION_COMPLETE,
)


class ShellValidator:

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def validate(
        self,
        floor_metrics:   Dict[str, Any],
        wall_metrics:    Dict[str, Any],
        ceiling_metrics: Dict[str, Any],
        blueprint_dict:  Dict[str, Any],
    ) -> ShellPhaseResult:
        """Validate a completed shell. Never raises."""
        try:
            return self._validate(floor_metrics, wall_metrics, ceiling_metrics, blueprint_dict)
        except Exception as exc:
            r = ShellPhaseResult(phase="validation", status="VALIDATION_FAILED")
            r.errors.append(f"ShellValidator error: {exc}")
            return r

    def _validate(
        self,
        floor_m:  Dict[str, Any],
        wall_m:   Dict[str, Any],
        ceil_m:   Dict[str, Any],
        bp:       Dict[str, Any],
    ) -> ShellPhaseResult:
        result   = ShellPhaseResult(phase="validation")
        findings: List[str] = []

        is_outdoor      = bool(bp.get("is_outdoor", False))
        required_walls  = int(bp.get("wall_count", 4))
        w = float(bp.get("room_width",  10.0))
        d = float(bp.get("room_length", 12.0))
        h = float(bp.get("room_height",  4.0))

        # 1. Floor
        floor_exists   = bool(floor_m.get("floor_exists", False))
        floor_area     = float(floor_m.get("floor_area", 0.0))
        if not floor_exists:
            findings.append("BLOCKING: floor_exists = False — no floor element was built.")
        if floor_area <= 0:
            findings.append("BLOCKING: floor_area = 0 — floor has no area.")

        # 2. Walls
        actual_walls    = int(wall_m.get("wall_count", 0))
        enclosure_valid = bool(wall_m.get("enclosure_valid", False)) if not is_outdoor else True
        if not is_outdoor and actual_walls < required_walls:
            findings.append(
                f"BLOCKING: wall_count={actual_walls} < required {required_walls}."
            )

        # 3. Ceiling
        ceiling_exists  = bool(ceil_m.get("ceiling_exists", False))
        ceiling_height  = float(ceil_m.get("ceiling_height", 0.0))
        if not is_outdoor:
            if not ceiling_exists:
                findings.append("BLOCKING: ceiling_exists = False — no ceiling element was built.")
            elif ceiling_height <= 0.0:
                findings.append("BLOCKING: ceiling_height = 0 — ceiling has no height.")

        # 4. Room bounds
        room_bounds_valid = (w > 0) and (d > 0) and (h > 0 or is_outdoor)
        if not room_bounds_valid:
            findings.append(
                f"WARNING: room_bounds invalid — w={w}, d={d}, h={h}."
            )

        blocking = [f for f in findings if f.startswith("BLOCKING")]
        ok       = (len(blocking) == 0)

        result.metrics = {
            "floor_exists":     floor_exists,
            "floor_area":       floor_area,
            "wall_count":       actual_walls,
            "ceiling_exists":   ceiling_exists,
            "ceiling_height":   ceiling_height,
            "enclosure_valid":  enclosure_valid,
            "room_bounds_valid": room_bounds_valid,
            "is_outdoor":       is_outdoor,
            "blocking_count":   len(blocking),
        }
        result.findings = findings
        result.status   = ENVIRONMENT_VALIDATION_COMPLETE
        result.ok       = ok
        return result


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[ShellValidator] = None
_LOCK = threading.Lock()


def get_shell_validator() -> ShellValidator:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = ShellValidator()
    return _INSTANCE


def reset_shell_validator_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
