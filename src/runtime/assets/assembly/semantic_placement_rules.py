"""
Semantic Placement Rules (Tier 9.4 — Real Asset Spatial Intelligence)
====================================================================
Defines semantic relationships between placement types:
  - Which types act as anchors and support child assets
    (table supports chair, lantern, bucket)
  - Where types prefer to be placed (bucket → service_area / wall zone)
  - Preferred facing per type

DESIGN RULES:
  1. No Houdini imports.  No bridge calls.  Rule tables only.
  2. All rules are deterministic lookup tables — no heuristic logic.
  3. Never raises in public methods.

Public API:
    PlacementRule
    SemanticPlacementRules
    get_semantic_placement_rules()
    reset_semantic_placement_rules_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# PlacementRule dataclass
# ---------------------------------------------------------------------------

@dataclass
class PlacementRule:
    """Semantic placement rules for one placement_type."""

    placement_type:      str
    is_anchor:           bool  = False
    supports:            List[str] = field(default_factory=list)  # child types
    preferred_anchor:    Optional[str] = None                      # anchor this attaches to
    preferred_zones:     List[str] = field(default_factory=list)  # zone name fragments
    anchor_distance_min: float = 0.5   # meters
    anchor_distance_max: float = 1.5   # meters
    facing_preferred:    str   = "inward"
    clearance_radius:    float = 0.3   # metres

    def to_dict(self) -> Dict[str, Any]:
        return {
            "placement_type":      self.placement_type,
            "is_anchor":           self.is_anchor,
            "supports":            list(self.supports),
            "preferred_anchor":    self.preferred_anchor,
            "preferred_zones":     list(self.preferred_zones),
            "anchor_distance_min": self.anchor_distance_min,
            "anchor_distance_max": self.anchor_distance_max,
            "facing_preferred":    self.facing_preferred,
            "clearance_radius":    self.clearance_radius,
        }


# ---------------------------------------------------------------------------
# Built-in rule table (16 types)
# ---------------------------------------------------------------------------

_BUILTIN_RULES: List[PlacementRule] = [
    PlacementRule(
        placement_type="table",
        is_anchor=True,
        supports=["chair", "stool", "bucket", "lantern"],
        preferred_zones=["hero_zone", "midground"],
        anchor_distance_min=0.0,
        anchor_distance_max=0.0,
        facing_preferred="camera",
        clearance_radius=1.1,
    ),
    PlacementRule(
        placement_type="chair",
        preferred_anchor="table",
        preferred_zones=["hero_zone", "midground"],
        anchor_distance_min=0.8,
        anchor_distance_max=1.5,
        facing_preferred="face_anchor",
        clearance_radius=0.3,
    ),
    PlacementRule(
        placement_type="bench",
        is_anchor=True,
        supports=["bucket", "lantern"],
        preferred_zones=["midground", "service_area"],
        anchor_distance_min=0.0,
        anchor_distance_max=0.0,
        facing_preferred="camera",
        clearance_radius=0.9,
    ),
    PlacementRule(
        placement_type="bucket",
        preferred_zones=["service_area", "background",
                         "wall_run_left", "wall_run_right"],
        anchor_distance_min=0.2,
        anchor_distance_max=0.8,
        facing_preferred="inward",
        clearance_radius=0.2,
    ),
    PlacementRule(
        placement_type="barrel",
        preferred_zones=["service_area", "background", "midground"],
        anchor_distance_min=0.3,
        anchor_distance_max=1.5,
        facing_preferred="scattered",
        clearance_radius=0.3,
    ),
    PlacementRule(
        placement_type="machine",
        is_anchor=True,
        supports=["pipe", "electronic", "bucket"],
        preferred_zones=["hero_zone", "midground"],
        anchor_distance_min=0.0,
        anchor_distance_max=0.0,
        facing_preferred="camera",
        clearance_radius=2.0,
    ),
    PlacementRule(
        placement_type="crane",
        is_anchor=True,
        supports=["pipe"],
        preferred_zones=["hero_zone"],
        anchor_distance_min=0.0,
        anchor_distance_max=0.0,
        facing_preferred="camera",
        clearance_radius=5.0,
    ),
    PlacementRule(
        placement_type="pipe",
        preferred_anchor="machine",
        preferred_zones=["midground", "background", "service_area"],
        anchor_distance_min=1.0,
        anchor_distance_max=3.0,
        facing_preferred="inward",
        clearance_radius=0.1,
    ),
    PlacementRule(
        placement_type="wall",
        is_anchor=True,
        supports=["lantern", "pipe", "column"],
        preferred_zones=["background",
                         "wall_run_left", "wall_run_right",
                         "wall_panel_left", "wall_panel_right"],
        anchor_distance_min=0.0,
        anchor_distance_max=0.0,
        facing_preferred="inward",
        clearance_radius=0.15,
    ),
    PlacementRule(
        placement_type="door",
        preferred_anchor="wall",
        preferred_zones=["background"],
        anchor_distance_min=0.0,
        anchor_distance_max=0.5,
        facing_preferred="camera",
        clearance_radius=0.5,
    ),
    PlacementRule(
        placement_type="lantern",
        preferred_anchor="table",
        preferred_zones=["hero_zone", "midground",
                         "wall_run_left", "wall_run_right"],
        anchor_distance_min=0.0,
        anchor_distance_max=1.5,
        facing_preferred="inward",
        clearance_radius=0.15,
    ),
    PlacementRule(
        placement_type="column",
        is_anchor=True,
        supports=["lantern"],
        preferred_zones=["background", "midground"],
        anchor_distance_min=0.0,
        anchor_distance_max=0.0,
        facing_preferred="inward",
        clearance_radius=0.3,
    ),
    PlacementRule(
        placement_type="platform",
        is_anchor=True,
        supports=["machine", "chair", "barrel", "bucket"],
        preferred_zones=["hero_zone", "midground"],
        anchor_distance_min=0.0,
        anchor_distance_max=0.0,
        facing_preferred="camera",
        clearance_radius=1.5,
    ),
    PlacementRule(
        placement_type="vehicle",
        preferred_zones=["hero_zone"],
        anchor_distance_min=0.0,
        anchor_distance_max=0.0,
        facing_preferred="camera",
        clearance_radius=2.5,
    ),
    PlacementRule(
        placement_type="terrain",
        is_anchor=True,
        supports=[
            "table", "chair", "bench", "machine",
            "vehicle", "barrel", "bucket",
        ],
        preferred_zones=["background"],
        anchor_distance_min=0.0,
        anchor_distance_max=0.0,
        facing_preferred="inward",
        clearance_radius=5.0,
    ),
    PlacementRule(
        placement_type="unknown",
        preferred_zones=["midground", "background"],
        anchor_distance_min=0.3,
        anchor_distance_max=1.0,
        facing_preferred="camera",
        clearance_radius=0.3,
    ),
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SemanticPlacementRules:
    """Registry and evaluator for semantic placement rules."""

    def __init__(self) -> None:
        self._rules: Dict[str, PlacementRule] = {
            r.placement_type: r for r in _BUILTIN_RULES
        }

    def get_rule(self, placement_type: str) -> PlacementRule:
        """Return the rule for *placement_type*, falling back to 'unknown'."""
        return self._rules.get(placement_type, self._rules["unknown"])

    def is_valid_anchor_relationship(
        self,
        anchor_type: str,
        child_type:  str,
    ) -> bool:
        """Return True if *child_type* is permitted to attach to *anchor_type*."""
        rule = self._rules.get(anchor_type)
        return rule is not None and rule.is_anchor and child_type in rule.supports

    def check_zone_compatibility(
        self,
        placement_type: str,
        zone_name:      str,
    ) -> Dict[str, Any]:
        """
        Return {"compatible": bool, "preferred": bool, "note": str}.
        All placement types are compatible with all zones — only preference varies.
        """
        rule     = self.get_rule(placement_type)
        preferred = any(pz in zone_name for pz in rule.preferred_zones)
        return {
            "compatible": True,
            "preferred":  preferred,
            "note": (
                f"'{placement_type}' prefers {rule.preferred_zones} — "
                f"zone '{zone_name}' is {'preferred' if preferred else 'non-preferred'}."
            ),
        }

    def evaluate_semantic_compliance(
        self,
        placements: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Score how well placed assets comply with semantic zone preferences.

        Each placement dict: {"asset_id", "zone_name", "placement_type"}.
        Returns {"score": float, "violations": List[str], "compliant_count": int, "total": int}.
        """
        violations: List[str] = []
        total   = len(placements)
        compliant = 0

        for p in placements:
            pt   = str(p.get("placement_type", "unknown"))
            zone = str(p.get("zone_name", ""))
            check = self.check_zone_compatibility(pt, zone)
            if check["preferred"]:
                compliant += 1
            else:
                violations.append(
                    f"'{p.get('asset_id', '?')}' ({pt}) placed in "
                    f"non-preferred zone '{zone}'."
                )

        return {
            "score":           1.0 if total == 0 else compliant / total,
            "violations":      violations,
            "compliant_count": compliant,
            "total":           total,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_INSTANCE: Optional[SemanticPlacementRules] = None
_INSTANCE_LOCK = threading.Lock()


def get_semantic_placement_rules() -> SemanticPlacementRules:
    """Return the module-level singleton SemanticPlacementRules."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = SemanticPlacementRules()
    return _INSTANCE


def reset_semantic_placement_rules_for_tests() -> None:
    """Replace the singleton.  For test isolation only."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None
