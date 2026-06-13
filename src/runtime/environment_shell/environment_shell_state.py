"""
EnvironmentShell — Tier 10.4
==============================
Accumulates the results of all 6 shell construction phases.
This is the canonical state object that proves the environment was built.

Public API:
    EnvironmentShell
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class EnvironmentShell:
    """
    Complete state of a constructed environment shell.
    Produced by EnvironmentShellBuilder after all 6 phases succeed.
    Consumed by EnvironmentReadinessGate to block downstream placement.
    """

    environment:          str   = ""

    # Phase 1 — Floor
    floor_exists:         bool  = False
    floor_area:           float = 0.0
    walkable_surface:     bool  = False

    # Phase 2 — Walls
    wall_count:           int   = 0
    walls_form_enclosure: bool  = False
    enclosure_valid:      bool  = False

    # Phase 3 — Ceiling
    ceiling_exists:       bool  = False
    ceiling_height:       float = 0.0
    ceiling_type:         str   = ""
    supports_beams:       bool  = False

    # Phase 4 — Structural anchors
    door_anchor_count:      int = 0
    window_anchor_count:    int = 0
    beam_anchor_count:      int = 0
    column_anchor_count:    int = 0
    fireplace_anchor_count: int = 0

    # Phase 5 — Structural placement
    door_attachment_count:   int = 0
    window_attachment_count: int = 0
    beam_attachment_count:   int = 0

    # Phase 6 — Validation
    room_bounds_valid:    bool  = False
    is_outdoor:           bool  = False

    # Gate outcome
    environment_ready:    bool  = False

    # Phase status trail
    phase_statuses: Dict[str, str] = field(default_factory=dict)

    # All structural elements produced across all phases
    structural_elements: List[Dict[str, Any]] = field(default_factory=list)
    anchors:             List[Dict[str, Any]] = field(default_factory=list)

    ok:     bool        = False
    errors: List[str]   = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment":             self.environment,
            "floor_exists":            self.floor_exists,
            "floor_area":              self.floor_area,
            "walkable_surface":        self.walkable_surface,
            "wall_count":              self.wall_count,
            "walls_form_enclosure":    self.walls_form_enclosure,
            "enclosure_valid":         self.enclosure_valid,
            "ceiling_exists":          self.ceiling_exists,
            "ceiling_height":          self.ceiling_height,
            "ceiling_type":            self.ceiling_type,
            "supports_beams":          self.supports_beams,
            "door_anchor_count":       self.door_anchor_count,
            "window_anchor_count":     self.window_anchor_count,
            "beam_anchor_count":       self.beam_anchor_count,
            "column_anchor_count":     self.column_anchor_count,
            "fireplace_anchor_count":  self.fireplace_anchor_count,
            "door_attachment_count":   self.door_attachment_count,
            "window_attachment_count": self.window_attachment_count,
            "beam_attachment_count":   self.beam_attachment_count,
            "room_bounds_valid":       self.room_bounds_valid,
            "is_outdoor":              self.is_outdoor,
            "environment_ready":       self.environment_ready,
            "phase_statuses":          dict(self.phase_statuses),
            "structural_elements":     list(self.structural_elements),
            "anchors":                 list(self.anchors),
            "ok":                      self.ok,
            "errors":                  list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentShell":
        s = cls()
        s.environment             = d.get("environment", "")
        s.floor_exists            = bool(d.get("floor_exists", False))
        s.floor_area              = float(d.get("floor_area", 0.0))
        s.walkable_surface        = bool(d.get("walkable_surface", False))
        s.wall_count              = int(d.get("wall_count", 0))
        s.walls_form_enclosure    = bool(d.get("walls_form_enclosure", False))
        s.enclosure_valid         = bool(d.get("enclosure_valid", False))
        s.ceiling_exists          = bool(d.get("ceiling_exists", False))
        s.ceiling_height          = float(d.get("ceiling_height", 0.0))
        s.ceiling_type            = d.get("ceiling_type", "")
        s.supports_beams          = bool(d.get("supports_beams", False))
        s.door_anchor_count       = int(d.get("door_anchor_count", 0))
        s.window_anchor_count     = int(d.get("window_anchor_count", 0))
        s.beam_anchor_count       = int(d.get("beam_anchor_count", 0))
        s.column_anchor_count     = int(d.get("column_anchor_count", 0))
        s.fireplace_anchor_count  = int(d.get("fireplace_anchor_count", 0))
        s.door_attachment_count   = int(d.get("door_attachment_count", 0))
        s.window_attachment_count = int(d.get("window_attachment_count", 0))
        s.beam_attachment_count   = int(d.get("beam_attachment_count", 0))
        s.room_bounds_valid       = bool(d.get("room_bounds_valid", False))
        s.is_outdoor              = bool(d.get("is_outdoor", False))
        s.environment_ready       = bool(d.get("environment_ready", False))
        s.phase_statuses          = dict(d.get("phase_statuses", {}))
        s.structural_elements     = list(d.get("structural_elements", []))
        s.anchors                 = list(d.get("anchors", []))
        s.ok                      = bool(d.get("ok", False))
        s.errors                  = list(d.get("errors", []))
        return s
