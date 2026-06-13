"""
EnvironmentShellAudit — Tier 10.4
===================================
Generates a structured audit report from an EnvironmentShell.

Audit fields:
  floor_exists
  wall_count
  ceiling_exists
  door_attachment_count
  window_attachment_count
  beam_attachment_count
  environment_ready

Additional derived:
  environment_valid = floor_exists and (ceiling_exists or is_outdoor) and wall_count >= required
  geometry_valid    = room_bounds_valid and floor_area > 0
  semantic_valid    = True (Tier 9.9/14.3 sets this; shell contributes True if ready)
  plausibility_valid = True (Tier 14.3; shell contributes True if ready)
  production_ready   = environment_valid and geometry_valid and semantic_valid and plausibility_valid

Never raises.

Public API:
    ShellAudit
    EnvironmentShellAuditor
    get_environment_shell_auditor()
    reset_environment_shell_auditor_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment_shell.environment_shell_state import EnvironmentShell


@dataclass
class ShellAudit:
    """Structured audit metrics for an environment shell."""

    environment:             str   = ""

    # Core gate fields
    floor_exists:            bool  = False
    wall_count:              int   = 0
    ceiling_exists:          bool  = False
    door_attachment_count:   int   = 0
    window_attachment_count: int   = 0
    beam_attachment_count:   int   = 0
    environment_ready:       bool  = False

    # Derived validity flags
    environment_valid:   bool  = False
    geometry_valid:      bool  = False
    semantic_valid:      bool  = True   # downstream validators refine this
    plausibility_valid:  bool  = True   # downstream validators refine this
    production_ready:    bool  = False

    # Extra context
    floor_area:              float = 0.0
    ceiling_height:          float = 0.0
    is_outdoor:              bool  = False
    phase_statuses:          Dict[str, str] = field(default_factory=dict)
    findings:                List[str]      = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":              self.environment,
            "floor_exists":             self.floor_exists,
            "wall_count":               self.wall_count,
            "ceiling_exists":           self.ceiling_exists,
            "door_attachment_count":    self.door_attachment_count,
            "window_attachment_count":  self.window_attachment_count,
            "beam_attachment_count":    self.beam_attachment_count,
            "environment_ready":        self.environment_ready,
            "environment_valid":        self.environment_valid,
            "geometry_valid":           self.geometry_valid,
            "semantic_valid":           self.semantic_valid,
            "plausibility_valid":       self.plausibility_valid,
            "production_ready":         self.production_ready,
            "floor_area":               self.floor_area,
            "ceiling_height":           self.ceiling_height,
            "is_outdoor":               self.is_outdoor,
            "phase_statuses":           dict(self.phase_statuses),
            "findings":                 list(self.findings),
        }


class EnvironmentShellAuditor:

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def audit(
        self,
        shell:               EnvironmentShell,
        required_wall_count: int  = 4,
        semantic_valid:      bool = True,
        plausibility_valid:  bool = True,
    ) -> ShellAudit:
        """Generate audit report. Never raises."""
        try:
            return self._audit(shell, required_wall_count, semantic_valid, plausibility_valid)
        except Exception as exc:
            a = ShellAudit(environment=getattr(shell, "environment", ""))
            a.findings.append(f"EnvironmentShellAuditor error: {exc}")
            return a

    def _audit(
        self,
        shell:               EnvironmentShell,
        required_walls:      int,
        semantic_valid:      bool,
        plausibility_valid:  bool,
    ) -> ShellAudit:
        a = ShellAudit(environment=shell.environment)

        a.floor_exists            = shell.floor_exists
        a.wall_count              = shell.wall_count
        a.ceiling_exists          = shell.ceiling_exists
        a.door_attachment_count   = shell.door_attachment_count
        a.window_attachment_count = shell.window_attachment_count
        a.beam_attachment_count   = shell.beam_attachment_count
        a.environment_ready       = shell.environment_ready
        a.floor_area              = shell.floor_area
        a.ceiling_height          = shell.ceiling_height
        a.is_outdoor              = shell.is_outdoor
        a.phase_statuses          = dict(shell.phase_statuses)
        a.semantic_valid          = semantic_valid
        a.plausibility_valid      = plausibility_valid

        # environment_valid
        ceiling_ok  = shell.ceiling_exists or shell.is_outdoor
        walls_ok    = shell.is_outdoor or (shell.wall_count >= required_walls)
        a.environment_valid = shell.floor_exists and ceiling_ok and walls_ok

        # geometry_valid
        a.geometry_valid = shell.room_bounds_valid and shell.floor_area > 0

        # production_ready
        a.production_ready = (
            a.environment_valid
            and a.geometry_valid
            and a.semantic_valid
            and a.plausibility_valid
        )

        if not a.environment_valid:
            if not shell.floor_exists:
                a.findings.append("environment_valid=False: floor missing")
            if not ceiling_ok:
                a.findings.append("environment_valid=False: ceiling missing")
            if not walls_ok:
                a.findings.append(
                    f"environment_valid=False: walls {shell.wall_count} < {required_walls}"
                )
        if not a.geometry_valid:
            a.findings.append("geometry_valid=False: room_bounds or floor_area invalid")

        return a


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[EnvironmentShellAuditor] = None
_LOCK = threading.Lock()


def get_environment_shell_auditor() -> EnvironmentShellAuditor:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = EnvironmentShellAuditor()
    return _INSTANCE


def reset_environment_shell_auditor_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
