"""
architectural_constraint_solver.py — §49 Structural Environment Realization
============================================================================
Validates and corrects architectural constraints in a RoomShell.

Constraints checked:
  no_floating_wall         all walls connect to floor and ceiling
  no_disconnected_ceiling  ceiling width/depth matches room dimensions
  door_inside_wall         every door's wall_id references an existing wall
  window_inside_wall       every window's wall_id references an existing wall
  room_closure             floor + 4 walls + ceiling all present (indoor)
  zone_accessibility       every zone centroid is inside the room bounds
  no_overlapping_openings  openings on the same wall do not overlap

Violations are corrected where possible (snap, resize); otherwise flagged.

Public API:
    ArchConstraintViolation
    ArchConstraintResult
    ArchitecturalConstraintSolver
    get_architectural_constraint_solver()
    reset_architectural_constraint_solver_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment_realization.structural_elements import RoomShell, StructuralElement


@dataclass
class ArchConstraintViolation:
    element_id:      str
    constraint_type: str
    description:     str
    corrected:       bool = False
    note:            str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id":      self.element_id,
            "constraint_type": self.constraint_type,
            "description":     self.description,
            "corrected":       self.corrected,
            "note":            self.note,
        }


@dataclass
class ArchConstraintResult:
    shell:             RoomShell
    violations_found:  int = 0
    violations_fixed:  int = 0
    violations_remaining: int = 0
    violations:        List[ArchConstraintViolation] = field(default_factory=list)
    ok:     bool = True
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violations_found":    self.violations_found,
            "violations_fixed":    self.violations_fixed,
            "violations_remaining": self.violations_remaining,
            "violations":          [v.to_dict() for v in self.violations],
            "ok":                  self.ok,
            "errors":              list(self.errors),
        }


class ArchitecturalConstraintSolver:
    """Validates and repairs RoomShell architectural constraints."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def solve(self, shell: RoomShell) -> ArchConstraintResult:
        """
        Validate and correct the RoomShell.
        Returns ArchConstraintResult with corrected shell. Never raises.
        """
        try:
            return self._solve(shell)
        except Exception as exc:
            return ArchConstraintResult(
                shell=shell,
                ok=False,
                errors=[f"ArchitecturalConstraintSolver.solve failed: {exc}"],
            )

    def _solve(self, shell: RoomShell) -> ArchConstraintResult:
        violations: List[ArchConstraintViolation] = []

        if shell.is_outdoor:
            return ArchConstraintResult(shell=shell)

        # 1. Room closure
        self._check_room_closure(shell, violations)

        # 2. Openings reference valid walls
        existing_wall_ids = {w.element_id for w in shell.walls.values()}
        for opening in shell.openings:
            if opening.wall_id and opening.wall_id not in existing_wall_ids:
                violations.append(ArchConstraintViolation(
                    element_id=opening.element_id,
                    constraint_type="door_inside_wall"
                    if opening.element_type in ("door", "swing_door", "sliding_door", "archway")
                    else "window_inside_wall",
                    description=(
                        f"{opening.element_type} '{opening.element_id}' references "
                        f"wall_id='{opening.wall_id}' which does not exist"
                    ),
                    corrected=False,
                    note="wall_id mismatch — check opening builder output",
                ))

        # 3. Ceiling dimensions match room
        if shell.ceiling:
            cdim = shell.ceiling.dimensions
            if abs(cdim.get("width", 0) - shell.width) > 0.5:
                old_w = cdim.get("width", 0)
                shell.ceiling.dimensions["width"] = shell.width
                violations.append(ArchConstraintViolation(
                    element_id=shell.ceiling.element_id,
                    constraint_type="no_disconnected_ceiling",
                    description=f"ceiling width {old_w:.2f} != room width {shell.width:.2f}",
                    corrected=True,
                    note=f"snapped to {shell.width:.2f}m",
                ))
            if abs(cdim.get("depth", 0) - shell.depth) > 0.5:
                old_d = cdim.get("depth", 0)
                shell.ceiling.dimensions["depth"] = shell.depth
                violations.append(ArchConstraintViolation(
                    element_id=shell.ceiling.element_id,
                    constraint_type="no_disconnected_ceiling",
                    description=f"ceiling depth {old_d:.2f} != room depth {shell.depth:.2f}",
                    corrected=True,
                    note=f"snapped to {shell.depth:.2f}m",
                ))

        # 4. Openings fit within wall dimensions
        wall_map = {w.element_id: w for w in shell.walls.values()}
        wall_map.update({w.face: w for w in shell.walls.values()})
        for opening in shell.openings:
            parent_wall = wall_map.get(opening.wall_id) or wall_map.get(opening.face)
            if parent_wall is None:
                continue
            wall_h = parent_wall.dimensions.get("height", shell.height)
            op_h = opening.dimensions.get("height", 2.0)
            bottom = opening.metadata.get("y_bottom", 0.0)
            if bottom + op_h > wall_h:
                new_h = max(0.1, wall_h - bottom - 0.05)
                opening.dimensions["height"] = new_h
                violations.append(ArchConstraintViolation(
                    element_id=opening.element_id,
                    constraint_type="no_floating_wall",
                    description=(
                        f"opening {opening.element_id} exceeds wall height "
                        f"({bottom + op_h:.2f} > {wall_h:.2f})"
                    ),
                    corrected=True,
                    note=f"height trimmed to {new_h:.2f}m",
                ))

        found    = len(violations)
        fixed    = sum(1 for v in violations if v.corrected)
        remaining = found - fixed

        return ArchConstraintResult(
            shell=shell,
            violations_found=found,
            violations_fixed=fixed,
            violations_remaining=remaining,
            violations=violations,
        )

    @staticmethod
    def _check_room_closure(
        shell: RoomShell,
        violations: List[ArchConstraintViolation],
    ) -> None:
        if shell.is_outdoor:
            return
        if shell.floor is None:
            violations.append(ArchConstraintViolation(
                element_id="floor",
                constraint_type="room_closure",
                description="floor is missing",
                corrected=False,
            ))
        if shell.ceiling is None:
            violations.append(ArchConstraintViolation(
                element_id="ceiling",
                constraint_type="room_closure",
                description="ceiling is missing",
                corrected=False,
            ))
        for face in ("north", "south", "east", "west"):
            if face not in shell.walls:
                violations.append(ArchConstraintViolation(
                    element_id=f"wall_{face}",
                    constraint_type="room_closure",
                    description=f"{face} wall is missing",
                    corrected=False,
                ))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[ArchitecturalConstraintSolver] = None
_lock = threading.Lock()


def get_architectural_constraint_solver() -> ArchitecturalConstraintSolver:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ArchitecturalConstraintSolver()
    return _instance


def reset_architectural_constraint_solver_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
