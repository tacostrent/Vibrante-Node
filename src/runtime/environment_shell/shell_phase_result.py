"""
ShellPhaseResult — Tier 10.4
============================
Data types for each phase's result and the canonical phase status constants.

Phase status strings:
    FLOOR_CONSTRUCTION_COMPLETE
    WALL_CONSTRUCTION_COMPLETE
    CEILING_CONSTRUCTION_COMPLETE
    STRUCTURAL_ANCHORS_READY
    STRUCTURAL_PLACEMENT_COMPLETE
    ENVIRONMENT_VALIDATION_COMPLETE
    ENVIRONMENT_NOT_READY          (gate failure)
    ENVIRONMENT_READY              (gate passed)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# ── Phase status constants ─────────────────────────────────────────────────────

FLOOR_CONSTRUCTION_COMPLETE    = "FLOOR_CONSTRUCTION_COMPLETE"
WALL_CONSTRUCTION_COMPLETE     = "WALL_CONSTRUCTION_COMPLETE"
CEILING_CONSTRUCTION_COMPLETE  = "CEILING_CONSTRUCTION_COMPLETE"
STRUCTURAL_ANCHORS_READY       = "STRUCTURAL_ANCHORS_READY"
STRUCTURAL_PLACEMENT_COMPLETE  = "STRUCTURAL_PLACEMENT_COMPLETE"
ENVIRONMENT_VALIDATION_COMPLETE = "ENVIRONMENT_VALIDATION_COMPLETE"
ENVIRONMENT_NOT_READY          = "ENVIRONMENT_NOT_READY"
ENVIRONMENT_READY              = "ENVIRONMENT_READY"

ALL_PHASE_STATUSES = (
    FLOOR_CONSTRUCTION_COMPLETE,
    WALL_CONSTRUCTION_COMPLETE,
    CEILING_CONSTRUCTION_COMPLETE,
    STRUCTURAL_ANCHORS_READY,
    STRUCTURAL_PLACEMENT_COMPLETE,
    ENVIRONMENT_VALIDATION_COMPLETE,
)


# ── Per-phase result ───────────────────────────────────────────────────────────

@dataclass
class ShellPhaseResult:
    """Result of one shell construction phase."""

    phase:    str  = ""          # e.g. "floor", "walls", "ceiling", "anchors", "placement", "validation"
    status:   str  = ""          # one of the constants above
    ok:       bool = False
    elements: List[Dict[str, Any]] = field(default_factory=list)
    metrics:  Dict[str, Any]       = field(default_factory=dict)
    findings: List[str]            = field(default_factory=list)
    errors:   List[str]            = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase":    self.phase,
            "status":   self.status,
            "ok":       self.ok,
            "elements": list(self.elements),
            "metrics":  dict(self.metrics),
            "findings": list(self.findings),
            "errors":   list(self.errors),
        }
