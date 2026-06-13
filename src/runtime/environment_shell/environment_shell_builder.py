"""
EnvironmentShellBuilder — Tier 10.4
======================================
Main orchestrator for the 6-phase environment shell construction pipeline.

Pipeline:
  1. EnvironmentShellBlueprintFactory  → EnvironmentShellBlueprint
  2. ShellFloorBuilder                 → Phase 1 (FLOOR_CONSTRUCTION_COMPLETE)
  3. ShellWallBuilder                  → Phase 2 (WALL_CONSTRUCTION_COMPLETE)
  4. ShellCeilingBuilder               → Phase 3 (CEILING_CONSTRUCTION_COMPLETE)
  5. StructuralAnchorGenerator         → Phase 4 (STRUCTURAL_ANCHORS_READY)
  6. StructuralElementPlacer           → Phase 5 (STRUCTURAL_PLACEMENT_COMPLETE)
  7. ShellValidator                    → Phase 6 (ENVIRONMENT_VALIDATION_COMPLETE)
  8. EnvironmentReadinessGate          → ENVIRONMENT_READY / ENVIRONMENT_NOT_READY
  9. EnvironmentShellAuditor           → ShellAudit
 10. ShellReview                       → ShellReviewResult
 11. ShellStatistics                   → record

Usage:
    shell, review = get_environment_shell_builder().build("western_room")
    # shell.environment_ready == True
    # review.production_ready == True
    # review.grade == "A"

Public API:
    EnvironmentShellBuildResult
    EnvironmentShellBuilder
    get_environment_shell_builder()
    reset_environment_shell_builder_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.runtime.environment_shell.environment_shell_blueprint import (
    EnvironmentShellBlueprint,
    get_blueprint_factory,
)
from src.runtime.environment_shell.shell_floor_builder   import get_shell_floor_builder
from src.runtime.environment_shell.shell_wall_builder    import get_shell_wall_builder
from src.runtime.environment_shell.shell_ceiling_builder import get_shell_ceiling_builder
from src.runtime.environment_shell.structural_anchor_generator import get_structural_anchor_generator
from src.runtime.environment_shell.structural_element_placer   import get_structural_element_placer
from src.runtime.environment_shell.shell_validator             import get_shell_validator
from src.runtime.environment_shell.environment_shell_state     import EnvironmentShell
from src.runtime.environment_shell.environment_readiness_gate  import (
    get_environment_readiness_gate,
    GateResult,
)
from src.runtime.environment_shell.environment_shell_audit import (
    ShellAudit,
    get_environment_shell_auditor,
)
from src.runtime.environment_shell.shell_review     import ShellReviewResult, get_shell_review
from src.runtime.environment_shell.shell_statistics import get_shell_statistics


@dataclass
class EnvironmentShellBuildResult:
    """Complete result of a shell build run."""

    environment:  str                   = ""
    shell:        Optional[EnvironmentShell] = None
    gate:         Optional[GateResult]       = None
    audit:        Optional[ShellAudit]       = None
    review:       Optional[ShellReviewResult] = None
    blueprint:    Optional[Dict[str, Any]]   = None
    ok:           bool                   = False
    errors:       List[str]              = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment": self.environment,
            "shell":    self.shell.to_dict()   if self.shell   else {},
            "gate":     self.gate.to_dict()    if self.gate    else {},
            "audit":    self.audit.to_dict()   if self.audit   else {},
            "review":   self.review.to_dict()  if self.review  else {},
            "blueprint": self.blueprint        or {},
            "ok":        self.ok,
            "errors":    list(self.errors),
        }


class EnvironmentShellBuilder:
    """
    6-phase environment shell construction + gate + audit + review.

    Always returns an EnvironmentShellBuildResult. Never raises.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build(
        self,
        environment:        str,
        structural_assets:  Optional[List[Dict[str, Any]]] = None,
    ) -> EnvironmentShellBuildResult:
        """
        Build the full environment shell for the given environment name.

        Args:
            environment:       e.g. "western_room"
            structural_assets: optional list of pre-classified structural asset
                               dicts (with _structural_role set by Tier 10.3).
                               Used only in Phase 5. Safe to omit.

        Returns EnvironmentShellBuildResult. Never raises.
        """
        try:
            return self._build(environment, structural_assets or [])
        except Exception as exc:
            res = EnvironmentShellBuildResult(environment=environment)
            res.ok = False
            res.errors.append(f"EnvironmentShellBuilder.build failed: {exc}")
            return res

    def _build(
        self,
        environment:       str,
        structural_assets: List[Dict[str, Any]],
    ) -> EnvironmentShellBuildResult:
        res = EnvironmentShellBuildResult(environment=environment)

        # ── Blueprint ─────────────────────────────────────────────────────────
        bp = get_blueprint_factory().build(environment)
        res.blueprint = bp.to_dict()

        # ── Phase 1: Floor ────────────────────────────────────────────────────
        floor_r = get_shell_floor_builder().build(bp)

        # ── Phase 2: Walls ────────────────────────────────────────────────────
        wall_r  = get_shell_wall_builder().build(bp)

        # ── Phase 3: Ceiling ──────────────────────────────────────────────────
        ceil_r  = get_shell_ceiling_builder().build(bp)

        # ── Phase 4: Structural anchors ───────────────────────────────────────
        anchor_r = get_structural_anchor_generator().generate(bp)

        # ── Phase 5: Structural placement ─────────────────────────────────────
        place_r = get_structural_element_placer().place(
            anchors           = anchor_r.elements,
            structural_assets = structural_assets,
            environment       = environment,
        )

        # ── Phase 6: Validation ───────────────────────────────────────────────
        valid_r = get_shell_validator().validate(
            floor_metrics   = floor_r.metrics,
            wall_metrics    = wall_r.metrics,
            ceiling_metrics = ceil_r.metrics,
            blueprint_dict  = bp.to_dict(),
        )

        # ── Assemble EnvironmentShell ─────────────────────────────────────────
        shell = EnvironmentShell(environment=environment)

        # Phase 1 data
        shell.floor_exists    = bool(floor_r.metrics.get("floor_exists", False))
        shell.floor_area      = float(floor_r.metrics.get("floor_area", 0.0))
        shell.walkable_surface = bool(floor_r.metrics.get("walkable_surface", False))

        # Phase 2 data
        shell.wall_count          = int(wall_r.metrics.get("wall_count", 0))
        shell.walls_form_enclosure = bool(wall_r.metrics.get("walls_form_enclosure", False))
        shell.enclosure_valid     = bool(wall_r.metrics.get("enclosure_valid", False))

        # Phase 3 data
        shell.ceiling_exists  = bool(ceil_r.metrics.get("ceiling_exists", False))
        shell.ceiling_height  = float(ceil_r.metrics.get("ceiling_height", 0.0))
        shell.ceiling_type    = ceil_r.metrics.get("ceiling_type", bp.ceiling_type)
        shell.supports_beams  = bool(ceil_r.metrics.get("supports_beams", False))

        # Phase 4 data
        shell.door_anchor_count     = int(anchor_r.metrics.get("door_anchor_count", 0))
        shell.window_anchor_count   = int(anchor_r.metrics.get("window_anchor_count", 0))
        shell.beam_anchor_count     = int(anchor_r.metrics.get("beam_anchor_count", 0))
        shell.column_anchor_count   = int(anchor_r.metrics.get("column_anchor_count", 0))
        shell.fireplace_anchor_count = int(anchor_r.metrics.get("fireplace_anchor_count", 0))

        # Phase 5 data
        placed = place_r.elements
        shell.door_attachment_count   = int(place_r.metrics.get("door_count", 0))
        shell.window_attachment_count = int(place_r.metrics.get("window_count", 0))
        shell.beam_attachment_count   = int(place_r.metrics.get("beam_count", 0))

        # Phase 6 data
        shell.room_bounds_valid = bool(valid_r.metrics.get("room_bounds_valid", True))
        shell.is_outdoor        = bp.is_outdoor

        # Phase status trail
        shell.phase_statuses = {
            "floor":      floor_r.status,
            "walls":      wall_r.status,
            "ceiling":    ceil_r.status,
            "anchors":    anchor_r.status,
            "placement":  place_r.status,
            "validation": valid_r.status,
        }

        # All structural elements
        shell.structural_elements = (
            floor_r.elements + wall_r.elements + ceil_r.elements + placed
        )
        shell.anchors = anchor_r.elements

        shell.ok = valid_r.ok
        if not valid_r.ok:
            shell.errors = list(valid_r.findings)

        # ── Gate ──────────────────────────────────────────────────────────────
        gate = get_environment_readiness_gate().check(
            shell, required_wall_count=bp.wall_count
        )
        shell.environment_ready = gate.gate_passed

        # ── Audit ─────────────────────────────────────────────────────────────
        audit = get_environment_shell_auditor().audit(shell, required_wall_count=bp.wall_count)

        # ── Review ────────────────────────────────────────────────────────────
        review = get_shell_review().review(shell)

        # ── Statistics ────────────────────────────────────────────────────────
        get_shell_statistics().record(
            environment       = environment,
            floor_exists      = shell.floor_exists,
            wall_count        = shell.wall_count,
            ceiling_exists    = shell.ceiling_exists,
            environment_ready = shell.environment_ready,
            overall_score     = review.overall_score,
            grade             = review.grade,
            production_ready  = review.production_ready,
        )

        res.shell   = shell
        res.gate    = gate
        res.audit   = audit
        res.review  = review
        res.ok      = gate.gate_passed
        return res


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[EnvironmentShellBuilder] = None
_LOCK = threading.Lock()


def get_environment_shell_builder() -> EnvironmentShellBuilder:
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = EnvironmentShellBuilder()
    return _INSTANCE


def reset_environment_shell_builder_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
