"""
Structural Attachment Enforcer (Tier 10.3.5)
============================================
Validates that structural elements in an EnvironmentRealizationPlan have
valid attachment targets after builder execution.

Attachment rules (by element_type):
  Opening types (is_opening=True or element_type in OPENING_TYPES):
      wall_id must be non-empty — "door not attached to wall"

  beam / support_beam (element_type):
      face must contain "ceiling" OR position.y >= 1.5m
      → "beam not attached to ceiling"

  column (element_type):
      face == "floor_perimeter" OR position.y <= 0.05m
      → "column not attached to floor"

  floor (element_type="floor"):
      face must be "bottom" or contain "floor"
      → "floor element not attached to floor_plane"

  ceiling (element_type="ceiling"):
      face must contain "ceiling" or "top"
      → "ceiling element not attached to ceiling_plane"

  fireplace (element_type="fireplace" or structural_role="fireplace"):
      wall_id non-empty OR face contains "wall"
      → "fireplace not attached to wall"

Blocking findings (force production_ready = False):
  "door not attached to wall"
  "beam not attached to ceiling"
  "column not attached to floor"
  "fireplace not attached to wall"

Design rules:
  - No bridge calls. Planning only.
  - Deterministic.
  - Never raises.
  - Singleton pattern.

Public API:
    AttachmentRecord
    AttachmentResult
    StructuralAttachmentEnforcer
    get_structural_attachment_enforcer()
    reset_structural_attachment_enforcer_for_tests()
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.runtime.environment_realization.structural_elements import OPENING_TYPES

# ── Attachment rule tables ─────────────────────────────────────────────────────

# element_type values that require a non-empty wall_id
_OPENING_ELEMENT_TYPES = frozenset({
    "door", "window", "archway", "sliding_door",
    "swing_door", "loading_door", "vent", "service_opening",
    "arrow_slit", "porthole", "hangar_opening",
})

# element_type values that must be at ceiling level
_BEAM_ELEMENT_TYPES = frozenset({"beam", "support_beam"})

# Minimum Y position (meters) considered "at ceiling level"
_BEAM_MIN_Y = 1.5

# Maximum Y position (meters) considered "on the floor"
_COLUMN_MAX_Y = 0.05

_BLOCKING_KEYWORDS = frozenset({
    "door not attached to wall",
    "beam not attached to ceiling",
    "column not attached to floor",
    "fireplace not attached to wall",
})


# ── Data types ─────────────────────────────────────────────────────────────────

@dataclass
class AttachmentRecord:
    """Validation result for one structural element's attachment."""

    element_id:        str  = ""
    element_type:      str  = ""
    structural_role:   str  = ""
    face:              str  = ""
    wall_id:           str  = ""
    position_y:        float = 0.0
    attachment_target: str  = ""  # what it should be attached to
    attachment_valid:  bool = True
    finding:           str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id":       self.element_id,
            "element_type":     self.element_type,
            "structural_role":  self.structural_role,
            "face":             self.face,
            "wall_id":          self.wall_id,
            "position_y":       self.position_y,
            "attachment_target":self.attachment_target,
            "attachment_valid": self.attachment_valid,
            "finding":          self.finding,
        }


@dataclass
class AttachmentResult:
    """Attachment validation summary for all elements in a plan."""

    result_id:       str                   = field(default_factory=lambda: f"ar_{uuid.uuid4().hex[:10]}")
    environment:     str                   = ""
    total_checked:   int                   = 0
    valid_count:     int                   = 0
    invalid_count:   int                   = 0
    records:         List[AttachmentRecord] = field(default_factory=list)
    blocking:        List[str]              = field(default_factory=list)
    findings:        List[str]              = field(default_factory=list)
    production_ready: bool                 = False
    validated_at:    float                 = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id":       self.result_id,
            "environment":     self.environment,
            "total_checked":   self.total_checked,
            "valid_count":     self.valid_count,
            "invalid_count":   self.invalid_count,
            "records":         [r.to_dict() for r in self.records],
            "blocking":        list(self.blocking),
            "findings":        list(self.findings),
            "production_ready":self.production_ready,
            "validated_at":    self.validated_at,
        }


# ── Enforcer ───────────────────────────────────────────────────────────────────

class StructuralAttachmentEnforcer:
    """
    Validates that all structural elements have proper attachment targets.

    Usage:
        enforcer = get_structural_attachment_enforcer()
        result = enforcer.validate_from_dict(plan.to_dict())
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def validate(self, plan: Any) -> AttachmentResult:
        """
        Validate an EnvironmentRealizationPlan object.
        Never raises.
        """
        try:
            if hasattr(plan, "to_dict"):
                return self.validate_from_dict(plan.to_dict())
            return self.validate_from_dict(dict(plan))
        except Exception as exc:
            r = AttachmentResult()
            r.findings.append(f"StructuralAttachmentEnforcer.validate error: {exc}")
            return r

    def validate_from_dict(self, plan_dict: Dict[str, Any]) -> AttachmentResult:
        """
        Validate from an EnvironmentRealizationPlan dict.
        Never raises.
        """
        try:
            return self._validate(plan_dict)
        except Exception as exc:
            r = AttachmentResult()
            r.findings.append(f"StructuralAttachmentEnforcer error: {exc}")
            return r

    def validate_elements(
        self,
        elements:    List[Dict[str, Any]],
        environment: str = "",
    ) -> AttachmentResult:
        """
        Validate a raw list of StructuralElement dicts.
        Never raises.
        """
        try:
            result = AttachmentResult(environment=environment)
            for elem in elements:
                rec = self._check_element(elem)
                result.records.append(rec)
                if not rec.attachment_valid:
                    result.findings.append(f"Element '{rec.element_id}': {rec.finding}")
                    for kw in _BLOCKING_KEYWORDS:
                        if kw in rec.finding:
                            result.blocking.append(kw)
            self._finalise(result)
            return result
        except Exception as exc:
            r = AttachmentResult(environment=environment)
            r.findings.append(f"StructuralAttachmentEnforcer.validate_elements error: {exc}")
            return r

    # ── Internal ───────────────────────────────────────────────────────────────

    def _validate(self, plan_dict: Dict[str, Any]) -> AttachmentResult:
        env    = str(plan_dict.get("environment", ""))
        result = AttachmentResult(environment=env)

        # Collect elements from all sections of the plan
        elements: List[Dict[str, Any]] = []

        shell = plan_dict.get("room_shell") or {}
        if isinstance(shell, dict):
            # Floor
            if isinstance(shell.get("floor"), dict):
                elements.append(shell["floor"])
            # Ceiling
            if isinstance(shell.get("ceiling"), dict):
                elements.append(shell["ceiling"])
            # Walls (dict of face → element_dict)
            walls = shell.get("walls") or {}
            if isinstance(walls, dict):
                for w in walls.values():
                    if isinstance(w, dict):
                        elements.append(w)
            # Openings
            openings = shell.get("openings") or []
            if isinstance(openings, list):
                elements.extend(o for o in openings if isinstance(o, dict))
            # Beams
            beams = shell.get("beams") or []
            if isinstance(beams, list):
                elements.extend(b for b in beams if isinstance(b, dict))
            # Columns
            columns = shell.get("columns") or []
            if isinstance(columns, list):
                elements.extend(c for c in columns if isinstance(c, dict))

        # Also check structural_elements list if present
        for se in plan_dict.get("structural_elements") or []:
            if isinstance(se, dict):
                elements.append(se)

        for elem in elements:
            rec = self._check_element(elem)
            result.records.append(rec)
            if not rec.attachment_valid:
                result.findings.append(f"Element '{rec.element_id}': {rec.finding}")
                for kw in _BLOCKING_KEYWORDS:
                    if kw in rec.finding:
                        if kw not in result.blocking:
                            result.blocking.append(kw)

        self._finalise(result)
        return result

    def _check_element(self, elem: Dict[str, Any]) -> AttachmentRecord:
        element_id   = str(elem.get("element_id", ""))
        element_type = str(elem.get("element_type", "")).lower()
        face         = str(elem.get("face", "")).lower()
        wall_id      = str(elem.get("wall_id", ""))
        is_opening   = bool(elem.get("is_opening", False))
        position     = elem.get("position") or [0.0, 0.0, 0.0]
        position_y   = float(position[1]) if len(position) > 1 else 0.0
        metadata     = elem.get("metadata") or {}
        structural_role = str(metadata.get("structural_role", ""))

        rec = AttachmentRecord(
            element_id      = element_id,
            element_type    = element_type,
            structural_role = structural_role,
            face            = face,
            wall_id         = wall_id,
            position_y      = position_y,
        )

        # ── Opening: must have wall_id ────────────────────────────────────────
        if is_opening or element_type in _OPENING_ELEMENT_TYPES:
            rec.attachment_target = "wall"
            if not wall_id:
                rec.attachment_valid = False
                rec.finding = (
                    f"door not attached to wall — "
                    f"element_type='{element_type}' has empty wall_id."
                )
            return rec

        # ── Beam / support_beam: must be at ceiling level ──────────────────────
        if element_type in _BEAM_ELEMENT_TYPES:
            rec.attachment_target = "ceiling"
            at_ceiling = "ceiling" in face or position_y >= _BEAM_MIN_Y
            if not at_ceiling:
                rec.attachment_valid = False
                rec.finding = (
                    f"beam not attached to ceiling — "
                    f"element_type='{element_type}' face='{face}' y={position_y:.2f}m "
                    f"(expected >= {_BEAM_MIN_Y}m or face contains 'ceiling')."
                )
            return rec

        # ── Column: must touch the floor ──────────────────────────────────────
        if element_type == "column":
            rec.attachment_target = "floor"
            at_floor = "floor" in face or "perimeter" in face or position_y <= _COLUMN_MAX_Y
            if not at_floor:
                rec.attachment_valid = False
                rec.finding = (
                    f"column not attached to floor — "
                    f"face='{face}' y={position_y:.2f}m "
                    f"(expected y <= {_COLUMN_MAX_Y}m or face contains 'floor'/'perimeter')."
                )
            return rec

        # ── Floor: must use floor face ────────────────────────────────────────
        if element_type == "floor":
            rec.attachment_target = "floor_plane"
            if face and "floor" not in face and face != "bottom":
                rec.attachment_valid = False
                rec.finding = (
                    f"floor element not attached to floor_plane — "
                    f"face='{face}' (expected 'bottom' or containing 'floor')."
                )
            return rec

        # ── Ceiling: must use ceiling face ────────────────────────────────────
        if element_type == "ceiling":
            rec.attachment_target = "ceiling_plane"
            if face and "ceiling" not in face and "top" not in face:
                rec.attachment_valid = False
                rec.finding = (
                    f"ceiling element not attached to ceiling_plane — "
                    f"face='{face}' (expected 'top' or containing 'ceiling')."
                )
            return rec

        # ── Fireplace: must attach to wall ────────────────────────────────────
        if element_type == "fireplace" or structural_role == "fireplace":
            rec.attachment_target = "wall_face"
            attached = wall_id or "wall" in face
            if not attached:
                rec.attachment_valid = False
                rec.finding = (
                    f"fireplace not attached to wall — "
                    f"wall_id='{wall_id}' face='{face}'."
                )
            return rec

        # All other element types: no specific attachment rule → valid
        return rec

    @staticmethod
    def _finalise(result: AttachmentResult) -> None:
        result.total_checked = len(result.records)
        result.valid_count   = sum(1 for r in result.records if r.attachment_valid)
        result.invalid_count = result.total_checked - result.valid_count
        result.production_ready = not result.blocking


# ── Singleton ──────────────────────────────────────────────────────────────────

_INSTANCE: Optional[StructuralAttachmentEnforcer] = None
_LOCK = threading.Lock()


def get_structural_attachment_enforcer() -> StructuralAttachmentEnforcer:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = StructuralAttachmentEnforcer()
        return _INSTANCE


def reset_structural_attachment_enforcer_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
