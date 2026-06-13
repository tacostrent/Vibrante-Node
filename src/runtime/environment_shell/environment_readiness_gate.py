"""
EnvironmentReadinessGate — Tier 10.4
======================================
Evaluates whether an EnvironmentShell is ready for asset placement.

Gate condition:
  environment_ready = (
      floor_exists
      and (ceiling_exists or is_outdoor)
      and (wall_count >= required_wall_count or is_outdoor)
      and enclosure_valid
  )

If gate fails → ENVIRONMENT_NOT_READY, severity=BLOCKING.
  Aborts: FurnitureClusterBuilder, SurfacePlacementEngine,
          DecorationLayoutEngine, SceneRealityValidation.

If gate passes → ENVIRONMENT_READY.

Never raises. Deterministic.

Public API:
    BLOCKED_SYSTEMS
    GateResult
    EnvironmentReadinessGate
    get_environment_readiness_gate()
    reset_environment_readiness_gate_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

from src.runtime.environment_shell.environment_shell_state import EnvironmentShell
from src.runtime.environment_shell.shell_phase_result import (
    ENVIRONMENT_NOT_READY,
    ENVIRONMENT_READY,
)

# Systems that must be blocked when environment_ready = False
BLOCKED_SYSTEMS: FrozenSet[str] = frozenset({
    "FurnitureClusterBuilder",
    "SurfacePlacementEngine",
    "DecorationLayoutEngine",
    "SceneRealityValidation",
})


@dataclass
class GateResult:
    """Outcome of the environment readiness gate check."""

    environment:       str  = ""
    gate_passed:       bool = False
    gate_status:       str  = ""     # ENVIRONMENT_READY or ENVIRONMENT_NOT_READY
    severity:          str  = ""     # "OK" or "BLOCKING"
    floor_exists:      bool = False
    ceiling_exists:    bool = False
    wall_count:        int  = 0
    enclosure_valid:   bool = False
    is_outdoor:        bool = False
    blocked_systems:   List[str] = field(default_factory=list)
    findings:          List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":     self.environment,
            "gate_passed":     self.gate_passed,
            "gate_status":     self.gate_status,
            "severity":        self.severity,
            "floor_exists":    self.floor_exists,
            "ceiling_exists":  self.ceiling_exists,
            "wall_count":      self.wall_count,
            "enclosure_valid": self.enclosure_valid,
            "is_outdoor":      self.is_outdoor,
            "blocked_systems": list(self.blocked_systems),
            "findings":        list(self.findings),
        }


class EnvironmentReadinessGate:

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def check(
        self,
        shell: EnvironmentShell,
        required_wall_count: int = 4,
    ) -> GateResult:
        """Evaluate whether the shell is ready for asset placement. Never raises."""
        try:
            return self._check(shell, required_wall_count)
        except Exception as exc:
            r = GateResult(
                environment  = getattr(shell, "environment", ""),
                gate_passed  = False,
                gate_status  = ENVIRONMENT_NOT_READY,
                severity     = "BLOCKING",
                blocked_systems = list(BLOCKED_SYSTEMS),
            )
            r.findings.append(f"EnvironmentReadinessGate internal error: {exc}")
            return r

    def _check(self, shell: EnvironmentShell, required_walls: int) -> GateResult:
        result = GateResult(
            environment   = shell.environment,
            floor_exists  = shell.floor_exists,
            ceiling_exists = shell.ceiling_exists,
            wall_count    = shell.wall_count,
            enclosure_valid = shell.enclosure_valid,
            is_outdoor    = shell.is_outdoor,
        )

        findings: List[str] = []

        # 1. Floor must always exist
        if not shell.floor_exists:
            findings.append("BLOCKING: floor_exists = False")

        # 2. Ceiling or outdoor
        ceiling_ok = shell.ceiling_exists or shell.is_outdoor
        if not ceiling_ok:
            findings.append("BLOCKING: ceiling_exists = False and not outdoor")

        # 3. Wall count (only for indoor)
        walls_ok = shell.is_outdoor or (shell.wall_count >= required_walls)
        if not walls_ok:
            findings.append(
                f"BLOCKING: wall_count={shell.wall_count} < required {required_walls}"
            )

        # 4. Enclosure valid (only for indoor)
        enc_ok = shell.is_outdoor or shell.enclosure_valid
        if not enc_ok:
            findings.append("BLOCKING: enclosure_valid = False")

        gate_passed = (
            shell.floor_exists
            and ceiling_ok
            and walls_ok
            and enc_ok
        )

        result.gate_passed   = gate_passed
        result.gate_status   = ENVIRONMENT_READY if gate_passed else ENVIRONMENT_NOT_READY
        result.severity      = "OK" if gate_passed else "BLOCKING"
        result.blocked_systems = [] if gate_passed else list(BLOCKED_SYSTEMS)
        result.findings      = findings
        return result

    def check_dict(
        self,
        shell_dict: Dict[str, Any],
        required_wall_count: int = 4,
    ) -> GateResult:
        """Convenience overload accepting a dict instead of EnvironmentShell."""
        try:
            shell = EnvironmentShell.from_dict(shell_dict)
            return self.check(shell, required_wall_count)
        except Exception as exc:
            r = GateResult(gate_passed=False, gate_status=ENVIRONMENT_NOT_READY, severity="BLOCKING")
            r.findings.append(f"check_dict error: {exc}")
            return r


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[EnvironmentReadinessGate] = None
_LOCK = threading.Lock()


def get_environment_readiness_gate() -> EnvironmentReadinessGate:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = EnvironmentReadinessGate()
    return _INSTANCE


def reset_environment_readiness_gate_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
