"""
Structural Placement Rules (Tier 10.3 — Structural Asset Classification)
=========================================================================
Defines where each structural role must be placed and which layout systems
it is forbidden from entering.  These rules are enforced before SemanticLayoutEngine
and LayoutRealizationEngine run.

No bridge calls. Deterministic.

Public API:
    PlacementIntent
    StructuralPlacementRules
    get_structural_placement_rules()
    reset_structural_placement_rules_for_tests()
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

# ──────────────────────────────────────────────────────────────────────────────
# Roles that are structural (must NOT enter furniture/decoration pipelines)
# ──────────────────────────────────────────────────────────────────────────────

STRUCTURAL_ROLES: FrozenSet[str] = frozenset({
    "wall",
    "wall_segment",
    "doorway",
    "door_frame",
    "window",
    "window_frame",
    "fireplace",
    "beam",
    "support_beam",
    "column",
    "floor_piece",
    "ceiling_piece",
    "stair",
    "railing",
    "archway",
    "architectural_module",
    "structural_unknown",
})

# Roles that are non-structural (furniture layout pipeline)
NON_STRUCTURAL_ROLES: FrozenSet[str] = frozenset({
    "furniture",
    "prop",
    "decoration",
})

# ──────────────────────────────────────────────────────────────────────────────
# Placement target for each structural role
# ──────────────────────────────────────────────────────────────────────────────

# placement_target: where the asset attaches in the room
# route_to: which builder system handles it
_ROLE_RULES: Dict[str, Dict[str, Any]] = {
    "wall": {
        "placement_target": "room_shell",
        "attach_to":        "perimeter",
        "route_to":         "EnvironmentStructureBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop"],
        "notes":            "Full perimeter wall — handled by WallBuilder.",
    },
    "wall_segment": {
        "placement_target": "wall_boundary",
        "attach_to":        "wall_face",
        "route_to":         "EnvironmentStructureBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop"],
        "notes":            "Partial wall section, moulding, or panel.",
    },
    "doorway": {
        "placement_target": "wall_boundary",
        "attach_to":        "wall_opening",
        "route_to":         "OpeningBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop",
                             "anchor_placement", "support_placement"],
        "notes":            "Door opening — must align with wall face.",
    },
    "door_frame": {
        "placement_target": "wall_boundary",
        "attach_to":        "wall_opening",
        "route_to":         "OpeningBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop"],
        "notes":            "Frame surround for doorway opening.",
    },
    "window": {
        "placement_target": "wall_boundary",
        "attach_to":        "wall_opening",
        "route_to":         "OpeningBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop",
                             "anchor_placement"],
        "notes":            "Window opening in wall face.",
    },
    "window_frame": {
        "placement_target": "wall_boundary",
        "attach_to":        "wall_opening",
        "route_to":         "OpeningBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop"],
        "notes":            "Frame surround for window opening.",
    },
    "fireplace": {
        "placement_target": "wall_attachment",
        "attach_to":        "wall_face",
        "route_to":         "AnchorAssetBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "surface_prop",
                             "decoration", "scatter"],
        "notes":            "Wall-attached — always flush against a wall, never free-standing.",
    },
    "beam": {
        "placement_target": "ceiling_support",
        "attach_to":        "ceiling_zone",
        "route_to":         "BeamBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop",
                             "anchor_placement"],
        "notes":            "Horizontal span element — must be above eye level (>2 m).",
    },
    "support_beam": {
        "placement_target": "ceiling_support",
        "attach_to":        "ceiling_zone",
        "route_to":         "BeamBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop",
                             "anchor_placement"],
        "notes":            "Load-bearing horizontal beam.",
    },
    "column": {
        "placement_target": "perimeter_support",
        "attach_to":        "floor_perimeter",
        "route_to":         "BeamBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop"],
        "notes":            "Vertical support — base must touch floor, extends to ceiling.",
    },
    "floor_piece": {
        "placement_target": "floor_generation",
        "attach_to":        "floor_plane",
        "route_to":         "FloorBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop",
                             "anchor_placement", "wall_attachment"],
        "notes":            "Modular floor element — tiles, planks, panels.",
    },
    "ceiling_piece": {
        "placement_target": "ceiling_generation",
        "attach_to":        "ceiling_plane",
        "route_to":         "CeilingBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop",
                             "anchor_placement", "wall_attachment"],
        "notes":            "Modular ceiling element.",
    },
    "stair": {
        "placement_target": "transition_zone",
        "attach_to":        "floor_to_floor",
        "route_to":         "EnvironmentStructureBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop"],
        "notes":            "Staircase — placed at level transitions.",
    },
    "railing": {
        "placement_target": "stair_edge",
        "attach_to":        "stair_or_balcony",
        "route_to":         "EnvironmentStructureBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop"],
        "notes":            "Guard rail — follows stair or balcony edge.",
    },
    "archway": {
        "placement_target": "wall_boundary",
        "attach_to":        "wall_opening",
        "route_to":         "OpeningBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop",
                             "anchor_placement"],
        "notes":            "Arch opening — typically wider than doorway, no door leaf.",
    },
    "architectural_module": {
        "placement_target": "room_shell",
        "attach_to":        "structure_zone",
        "route_to":         "EnvironmentStructureBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop"],
        "notes":            "Generic modular architectural kit piece.",
    },
    "structural_unknown": {
        "placement_target": "room_shell",
        "attach_to":        "structure_zone",
        "route_to":         "EnvironmentStructureBuilder",
        "forbidden_in":     ["furniture_cluster", "seating", "decoration", "surface_prop"],
        "notes":            "Structural role could not be determined — route to structure.",
    },
}


@dataclass
class PlacementIntent:
    """Routing and attachment instructions for one classified asset."""

    asset_id:         str       = ""
    structural_role:  str       = "prop"
    placement_target: str       = "scatter"
    attach_to:        str       = "floor"
    route_to:         str       = "SemanticLayoutEngine"
    forbidden_in:     List[str] = field(default_factory=list)
    is_structural:    bool      = False
    notes:            str       = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id":         self.asset_id,
            "structural_role":  self.structural_role,
            "placement_target": self.placement_target,
            "attach_to":        self.attach_to,
            "route_to":         self.route_to,
            "forbidden_in":     list(self.forbidden_in),
            "is_structural":    self.is_structural,
            "notes":            self.notes,
        }


class StructuralPlacementRules:
    """
    Derive placement intent (routing, attachment, forbidden pipelines) for
    a classified structural role.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def get_intent(
        self,
        asset_id:        str,
        structural_role: str,
    ) -> PlacementIntent:
        """
        Return PlacementIntent for the given role.

        Non-structural roles (furniture/prop/decoration) return a generic
        SemanticLayoutEngine intent.  Never raises.
        """
        try:
            return self._get_intent(asset_id, structural_role)
        except Exception:
            return PlacementIntent(
                asset_id        = asset_id,
                structural_role = structural_role,
                route_to        = "SemanticLayoutEngine",
            )

    def _get_intent(self, asset_id: str, role: str) -> PlacementIntent:
        if role in NON_STRUCTURAL_ROLES:
            return PlacementIntent(
                asset_id        = asset_id,
                structural_role = role,
                placement_target= "scene_zone",
                attach_to       = "floor",
                route_to        = "SemanticLayoutEngine",
                forbidden_in    = [],
                is_structural   = False,
                notes           = "Non-structural — enters furniture/layout pipeline.",
            )

        rule = _ROLE_RULES.get(role)
        if rule is None:
            # Unknown structural role
            return PlacementIntent(
                asset_id        = asset_id,
                structural_role = role,
                placement_target= "room_shell",
                attach_to       = "structure_zone",
                route_to        = "EnvironmentStructureBuilder",
                forbidden_in    = ["furniture_cluster", "seating", "decoration", "surface_prop"],
                is_structural   = True,
                notes           = f"Unknown structural role '{role}' — defaulting to StructureBuilder.",
            )

        return PlacementIntent(
            asset_id        = asset_id,
            structural_role = role,
            placement_target= rule["placement_target"],
            attach_to       = rule["attach_to"],
            route_to        = rule["route_to"],
            forbidden_in    = list(rule["forbidden_in"]),
            is_structural   = True,
            notes           = rule["notes"],
        )

    def is_forbidden(self, structural_role: str, pipeline: str) -> bool:
        """
        Return True if `structural_role` must not enter `pipeline`.
        Never raises.
        """
        try:
            rule = _ROLE_RULES.get(structural_role, {})
            return pipeline in rule.get("forbidden_in", [])
        except Exception:
            return False

    def route_to(self, structural_role: str) -> str:
        """Return the builder system that should handle this role."""
        rule = _ROLE_RULES.get(structural_role, {})
        return rule.get("route_to", "SemanticLayoutEngine")

    def all_structural_roles(self) -> List[str]:
        return sorted(STRUCTURAL_ROLES)

    def all_non_structural_roles(self) -> List[str]:
        return sorted(NON_STRUCTURAL_ROLES)


# ──────────────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────────────

_INSTANCE: Optional[StructuralPlacementRules] = None
_LOCK = threading.Lock()


def get_structural_placement_rules() -> StructuralPlacementRules:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = StructuralPlacementRules()
        return _INSTANCE


def reset_structural_placement_rules_for_tests() -> None:
    global _INSTANCE
    with _LOCK:
        _INSTANCE = None
