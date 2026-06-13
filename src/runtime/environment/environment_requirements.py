"""
Environment Requirements (§44 — Structural Environment Assembly)
================================================================
Checks whether a built environment meets the structural requirements declared
in its EnvironmentBlueprint.

DESIGN RULES:
  1. No bridge calls. No Houdini imports. Advisory only.
  2. Deterministic — same inputs produce the same result.
  3. Never raises.
  4. Singleton pattern.
  5. Thread-safe.

Public API:
    RequirementsCheckResult
    EnvironmentRequirements
    get_environment_requirements()
    reset_environment_requirements_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment.environment_blueprint import EnvironmentBlueprint


@dataclass
class RequirementsCheckResult:
    """Result of checking environment structural requirements."""

    environment_name: str = ""

    # Individual structural checks
    floor_required: bool = False
    floor_present: bool = False
    wall_required: bool = False
    wall_present: bool = False
    ceiling_required: bool = False
    ceiling_present: bool = False
    door_required: bool = False
    door_present: bool = False
    window_required: bool = False
    window_present: bool = False

    # Anchor checks
    anchor_required: List[str] = field(default_factory=list)
    anchor_present: List[str] = field(default_factory=list)

    # Summary
    all_met: bool = False
    missing: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_name":  self.environment_name,
            "floor_required":    self.floor_required,
            "floor_present":     self.floor_present,
            "wall_required":     self.wall_required,
            "wall_present":      self.wall_present,
            "ceiling_required":  self.ceiling_required,
            "ceiling_present":   self.ceiling_present,
            "door_required":     self.door_required,
            "door_present":      self.door_present,
            "window_required":   self.window_required,
            "window_present":    self.window_present,
            "anchor_required":   list(self.anchor_required),
            "anchor_present":    list(self.anchor_present),
            "all_met":           self.all_met,
            "missing":           list(self.missing),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RequirementsCheckResult":
        return cls(
            environment_name = str(d.get("environment_name", "")),
            floor_required   = bool(d.get("floor_required", False)),
            floor_present    = bool(d.get("floor_present", False)),
            wall_required    = bool(d.get("wall_required", False)),
            wall_present     = bool(d.get("wall_present", False)),
            ceiling_required = bool(d.get("ceiling_required", False)),
            ceiling_present  = bool(d.get("ceiling_present", False)),
            door_required    = bool(d.get("door_required", False)),
            door_present     = bool(d.get("door_present", False)),
            window_required  = bool(d.get("window_required", False)),
            window_present   = bool(d.get("window_present", False)),
            anchor_required  = list(d.get("anchor_required", [])),
            anchor_present   = list(d.get("anchor_present", [])),
            all_met          = bool(d.get("all_met", False)),
            missing          = list(d.get("missing", [])),
        )


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------

def _has_element(elements: List[str], keywords: List[str]) -> bool:
    """Return True if any element string contains any of the keywords."""
    for elem in elements:
        for kw in keywords:
            if kw in elem.lower():
                return True
    return False


class EnvironmentRequirements:
    """Check whether built elements satisfy blueprint requirements."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def check(
        self,
        blueprint: EnvironmentBlueprint,
        structure_elements: List[str],
        anchors_placed: List[str],
    ) -> RequirementsCheckResult:
        """Check requirements.

        Args:
            blueprint:         The environment blueprint to check against.
            structure_elements: List of structural element type strings that
                               have been built (e.g. ["floor", "wall", "ceiling"]).
            anchors_placed:    List of anchor type strings that have been placed
                               (e.g. ["main_table", "fireplace"]).

        Returns:
            RequirementsCheckResult with all_met=True when fully satisfied.
        """
        with self._lock:
            try:
                return self._check(blueprint, structure_elements, anchors_placed)
            except Exception as exc:
                return RequirementsCheckResult(
                    environment_name = blueprint.environment_name,
                    missing          = [f"check error: {exc}"],
                    all_met          = False,
                )

    def _check(
        self,
        blueprint: EnvironmentBlueprint,
        structure_elements: List[str],
        anchors_placed: List[str],
    ) -> RequirementsCheckResult:
        missing: List[str] = []
        elems_lower = [e.lower() for e in structure_elements]

        # Determine what is required from blueprint.required_structure
        required_set = {s.lower() for s in blueprint.required_structure}

        floor_req = any("floor" in r or "ground" in r or "pavement" in r or "plating" in r
                        for r in required_set)
        wall_req  = any("wall" in r or "facade" in r or "panel" in r for r in required_set)
        ceil_req  = any("ceiling" in r or "roof" in r or "canopy" in r for r in required_set)
        door_req  = any("door" in r or "airlock" in r or "gate" in r for r in required_set)
        win_req   = any("window" in r or "viewport" in r for r in required_set)

        floor_pres  = _has_element(elems_lower, ["floor", "ground", "pavement", "plating", "deck"])
        wall_pres   = _has_element(elems_lower, ["wall", "facade", "panel"])
        ceil_pres   = _has_element(elems_lower, ["ceiling", "roof", "canopy", "dome"])
        door_pres   = _has_element(elems_lower, ["door", "airlock", "gate"])
        win_pres    = _has_element(elems_lower, ["window", "viewport", "port"])

        if floor_req and not floor_pres:
            missing.append("floor")
        if wall_req and not wall_pres:
            missing.append("wall")
        if ceil_req and not ceil_pres:
            missing.append("ceiling")
        if door_req and not door_pres:
            missing.append("door")
        if win_req and not win_pres:
            missing.append("window")

        # Anchor check
        anchor_required = list(blueprint.required_anchors)
        anchor_present  = [a for a in anchor_required if a in anchors_placed]
        for a in anchor_required:
            if a not in anchors_placed:
                missing.append(f"anchor:{a}")

        return RequirementsCheckResult(
            environment_name = blueprint.environment_name,
            floor_required   = floor_req,
            floor_present    = floor_pres,
            wall_required    = wall_req,
            wall_present     = wall_pres,
            ceiling_required = ceil_req,
            ceiling_present  = ceil_pres,
            door_required    = door_req,
            door_present     = door_pres,
            window_required  = win_req,
            window_present   = win_pres,
            anchor_required  = anchor_required,
            anchor_present   = anchor_present,
            all_met          = len(missing) == 0,
            missing          = missing,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_INSTANCE: Optional[EnvironmentRequirements] = None
_LOCK = threading.Lock()


def get_environment_requirements() -> EnvironmentRequirements:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = EnvironmentRequirements()
        return _INSTANCE


def reset_environment_requirements_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
